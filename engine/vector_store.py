# -*- coding: utf-8 -*-
"""向量库：切块 → embedding → 落盘 → 余弦检索。

为什么不用 FAISS / Chroma
------------------------
知识库 200–300 块，暴力余弦是 10 万次乘加，毫秒级。ANN 索引在这个规模上
带来的复杂度（依赖、构建时间、内存）远大于收益。等块数上千再换。

存储格式
--------
向量按 float32 二进制打包成 base64 存 JSON，比逐个写十进制文本小一半以上，
且不损失精度；块本身仍存在 kb.json，这里只存 id 与向量，天然对齐。
"""

import array
import base64
import hashlib
import json
import math
import os

try:
    import numpy as np
except Exception:
    np = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, "data", "vectors.json")


def _pack(vectors):
    a = array.array("f")
    for v in vectors:
        a.extend(v)
    return base64.b64encode(a.tobytes()).decode("ascii")


def _unpack(blob, n, dim):
    a = array.array("f")
    a.frombytes(base64.b64decode(blob))
    return [list(a[i * dim:(i + 1) * dim]) for i in range(n)]


def _norm(vec):
    s = math.sqrt(sum(x * x for x in vec))
    return [x / s for x in vec] if s else list(vec)


class VectorStore:
    def __init__(self, chunks=None, backend=None, path=STORE_PATH):
        self.chunks = list(chunks or [])
        self.backend = backend
        self.path = path
        self.ids = []
        self.vectors = []
        self.meta = {}

    # ---------- 构建 ----------

    def signature(self):
        h = hashlib.md5()
        h.update((self.backend.name if self.backend else "none").encode())
        for c in self.chunks:
            h.update((str(c.get("id")) + str(c.get("text", ""))[:120]).encode("utf-8"))
        return h.hexdigest()

    def build(self, batch=32, normalise=True):
        if not self.chunks:
            raise RuntimeError("没有可索引的块")
        if self.backend is None:
            raise RuntimeError("没有可用的 embedding 后端")
        texts = [c.get("text", "") for c in self.chunks]
        vecs = []
        for i in range(0, len(texts), batch):
            vecs.extend(self.backend.encode(texts[i:i + batch]))
        if normalise:
            vecs = [_norm(v) for v in vecs]
        self.ids = [c.get("id") for c in self.chunks]
        self.vectors = vecs
        self.meta = {
            "backend": self.backend.kind,
            "model": self.backend.name,
            "dim": len(vecs[0]) if vecs else 0,
            "count": len(vecs),
            "signature": self.signature(),
            "normalised": bool(normalise),
        }
        return self

    # ---------- 检索 ----------

    def search(self, query, k=6, doc=None):
        if not self.vectors or self.backend is None:
            return []
        qv = _norm(self.backend.encode([query])[0])
        if np is not None:
            M = np.asarray(self.vectors, dtype=np.float64)
            sims = M @ np.asarray(qv, dtype=np.float64)
            order = np.argsort(-sims)
            picks = [(int(i), float(sims[i])) for i in order]
        else:
            scored = []
            for i, v in enumerate(self.vectors):
                s = 0.0
                for a, b in zip(qv, v):
                    s += a * b
                scored.append((s, i))
            scored.sort(reverse=True)
            picks = [(i, s) for s, i in scored]

        out = []
        by_id = {c.get("id"): c for c in self.chunks}
        for i, s in picks:
            cid = self.ids[i]
            c = by_id.get(cid)
            if not c:
                continue
            if doc and c.get("doc") != doc:
                continue
            out.append({
                "id": cid,
                "doc": c.get("doc"),
                "doc_title": c.get("doc_title"),
                "page": c.get("page"),
                "section": c.get("section"),
                "text": c.get("text"),
                "score": round(float(s), 4),
                "retriever": "vector",
            })
            if len(out) >= k:
                break
        return out

    # ---------- 落盘 ----------

    def to_dict(self):
        return {
            "meta": self.meta,
            "ids": self.ids,
            "dim": self.meta.get("dim", 0),
            "count": len(self.ids),
            "vectors": _pack(self.vectors),
        }

    def save(self, path=None):
        path = path or self.path
        tmp = path + ".tmp"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False)
        os.replace(tmp, path)
        return path

    @classmethod
    def load(cls, chunks, backend, path=None):
        """签名不一致（换了模型或切块变了）时返回 None，由调用方重建。"""
        path = path or STORE_PATH
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        obj = cls(chunks, backend, path)
        obj.meta = data.get("meta") or {}
        if obj.meta.get("signature") != obj.signature():
            return None
        dim = int(data.get("dim") or obj.meta.get("dim") or 0)
        n = int(data.get("count") or 0)
        if not dim or not n:
            return None
        obj.ids = data.get("ids") or []
        obj.vectors = _unpack(data.get("vectors", ""), n, dim)
        return obj
