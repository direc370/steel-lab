# -*- coding: utf-8 -*-
"""轻量向量检索：LSA 潜在语义索引（可选 numpy 加速）+ 无依赖哈希向量兜底。

设计取舍
--------
- **规模匹配**：知识库只有一百多个块，暴力余弦足够，不引入 FAISS/Chroma。
  上千块以后再考虑 HNSW。
- **零依赖优先**：有 numpy 时用一次 SVD 求潜在语义空间；没有 numpy 时降级为
  feature hashing（词项哈希到固定维度），接口完全一致，只是语义粗糙些。
- **可复现**：所有随机初值固定种子，同一份知识库每次构建结果一致。

和 BM25 的关系
--------------
BM25 只看"查询词出现在哪块、出现几次"，查不到同义改写；LSA 把词项压到低维
语义空间，"脱硫剂加多少" 和 "脱硫渣量计算" 即使不共享字面词也可能靠近。
两者互补，融合检索见 engine/hybrid.py。
"""

import hashlib
import json
import math
import os
from collections import Counter

try:
    import numpy as np
except Exception:  # numpy 只是加速项，缺了不影响功能
    np = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VEC_PATH = os.path.join(ROOT, "data", "vec_index.json")


def _default_tokenize(text):
    from .kb import tokenize
    return tokenize(text)


def _l2(vec):
    s = math.sqrt(sum(x * x for x in vec))
    return [x / s for x in vec] if s else list(vec)


class VectorIndex:
    """词项-文档矩阵上的潜在语义索引。

    参数
    ----
    chunks : list[dict]   知识块，需含 text / section 字段
    dim    : int          潜在语义维度，100 块左右取 48–96 足够
    tokenize : callable   tokenizer，默认复用 kb.tokenize
    """

    def __init__(self, chunks, dim=64, tokenize=None):
        self.chunks = list(chunks or [])
        self.dim = int(dim)
        self._tok = tokenize or _default_tokenize
        self.backend = "empty"
        self.vocab = {}
        self.idf = {}
        self.doc_vecs = []
        self._hashed = []
        self._A = None
        self._U = None
        self._S = None
        if self.chunks:
            self._build()

    # ---------- 构建 ----------

    def _docs_tfidf(self):
        toks_per_doc = []
        df = Counter()
        for c in self.chunks:
            toks = list(self._tok(c.get("text", "")))
            toks += list(self._tok(c.get("section", ""))) * 2
            cnt = Counter(toks)
            toks_per_doc.append(cnt)
            for t in cnt:
                df[t] += 1
        return toks_per_doc, df

    def _build(self):
        docs, df = self._docs_tfidf()
        n = len(docs)
        self.vocab = {t: i for i, t in enumerate(sorted(df))}
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}
        self._counts = docs

        if np is not None:
            self._build_lsa(n)
        else:
            self._build_hash(n)

    def _build_matrix(self):
        """重建词项-文档矩阵（不做 SVD，很快），供查询投影使用。"""
        V = len(self.vocab)
        A = np.zeros((len(self._counts), V), dtype=np.float64)
        for i, cnt in enumerate(self._counts):
            for t, c in cnt.items():
                j = self.vocab.get(t)
                if j is not None:
                    A[i, j] = (1.0 + math.log(c)) * self.idf[t]
        norms = np.linalg.norm(A, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return A / norms

    def _build_lsa(self, n):
        self._A = self._build_matrix()

        k = min(self.dim, n - 1) if n > 1 else 1
        U, S, _ = np.linalg.svd(self._A, full_matrices=False)
        U, S = U[:, :k], S[:k]
        # 丢掉接近零的奇异值，否则投影时 1/S 会放大噪声
        keep = S > max(1e-9, float(S[0]) * 1e-4) if S.size else S > 0
        U, S = U[:, keep], S[keep]
        self._U, self._S = U, S
        doc = U * S
        dn = np.linalg.norm(doc, axis=1, keepdims=True)
        dn[dn == 0] = 1.0
        self.doc_vecs = (doc / dn).tolist()
        self.backend = "lsa"

    def _hash_bucket(self, token):
        h = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(h[:4], "big") % self.dim

    def _build_hash(self, n):
        for cnt in self._counts:
            vec = [0.0] * self.dim
            for t, c in cnt.items():
                vec[self._hash_bucket(t)] += (1.0 + math.log(c)) * self.idf[t]
            self.doc_vecs.append(_l2(vec))
        self.backend = "hash"

    # ---------- 查询 ----------

    def embed_query(self, query):
        qt = [t for t in self._tok(query) if t in self.vocab]
        if not qt:
            return None
        qc = Counter(qt)
        if self.backend == "lsa":
            q = np.zeros(self._A.shape[1], dtype=np.float64)
            for t, c in qc.items():
                q[self.vocab[t]] = (1.0 + math.log(c)) * self.idf[t]
            nrm = np.linalg.norm(q)
            if nrm:
                q = q / nrm
            proj = (self._A @ q) @ (self._U / self._S)
            return _l2(proj.tolist())
        vec = [0.0] * self.dim
        for t, c in qc.items():
            vec[self._hash_bucket(t)] += (1.0 + math.log(c)) * self.idf[t]
        return _l2(vec)

    def search(self, query, k=6, doc=None, min_score=0.0):
        if not self.chunks:
            return []
        qv = self.embed_query(query)
        if qv is None:
            return []
        scored = []
        for i, dv in enumerate(self.doc_vecs):
            if doc and self.chunks[i].get("doc") != doc:
                continue
            s = sum(a * b for a, b in zip(qv, dv))
            if s > min_score:
                scored.append((s, i))
        scored.sort(reverse=True)
        out = []
        for s, i in scored[:k]:
            c = self.chunks[i]
            out.append({
                "id": c.get("id"),
                "doc": c.get("doc"),
                "doc_title": c.get("doc_title"),
                "page": c.get("page"),
                "section": c.get("section"),
                "text": c.get("text"),
                "score": round(float(s), 4),
                "retriever": "vector",
            })
        return out

    # ---------- 缓存 ----------

    def signature(self):
        h = hashlib.md5()
        for c in self.chunks:
            h.update((str(c.get("id")) + c.get("text", "")[:80]).encode("utf-8"))
        return h.hexdigest()

    def to_dict(self):
        data = {
            "signature": self.signature(),
            "backend": self.backend,
            "dim": self.dim,
            "vocab": self.vocab,
            "idf": self.idf,
            "doc_vecs": self.doc_vecs,
        }
        if self.backend == "lsa" and self._U is not None:
            # U/S 是缓存里真正值钱的部分：重建矩阵很快，SVD 才是慢的一步
            data["U"] = [[round(float(x), 6) for x in row] for row in self._U]
            data["S"] = [round(float(x), 6) for x in self._S]
        return data

    @classmethod
    def from_dict(cls, data, chunks, dim=None, tokenize=None):
        obj = cls([], dim=dim or data.get("dim", 64), tokenize=tokenize)
        obj.chunks = list(chunks or [])
        obj.backend = data.get("backend", "hash")
        obj.vocab = data.get("vocab") or {}
        obj.idf = data.get("idf") or {}
        obj.doc_vecs = data.get("doc_vecs") or []
        obj.dim = data.get("dim", obj.dim)
        if obj.backend == "lsa" and np is not None:
            obj._counts, _ = obj._docs_tfidf()
            obj._A = obj._build_matrix()
            U, S = data.get("U"), data.get("S")
            if U and S:
                obj._U = np.array(U, dtype=np.float64)
                obj._S = np.array(S, dtype=np.float64)
            else:
                obj._build_lsa(len(obj.chunks))
        elif obj.backend == "lsa":
            obj.backend = "empty"
            obj.doc_vecs = []
        return obj

    def save(self, path=VEC_PATH):
        if not self.chunks or self.backend == "empty":
            return False
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False)
        os.replace(tmp, path)
        return True

    @classmethod
    def load(cls, path, chunks, dim=None, tokenize=None):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        probe = cls([], dim=data.get("dim", 64), tokenize=tokenize)
        probe.chunks = list(chunks or [])
        if data.get("signature") != probe.signature():
            return None
        return cls.from_dict(data, chunks, dim=dim, tokenize=tokenize)


def build(chunks, dim=64):
    return VectorIndex(chunks, dim=dim)
