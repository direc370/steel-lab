# -*- coding: utf-8 -*-
"""手册知识库：BM25 检索 + 带页码引用的离线问答。"""

import json
import math
import os
import re
import unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(ROOT, "data", "kb.json")

_WORD = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*%?")
_CN = re.compile(r"[\u4e00-\u9fff]+")

SYNONYMS = {
    "铝": ["al"], "氧": ["o"], "碳": ["c"], "硅": ["si"], "锰": ["mn"],
    "硫": ["s"], "磷": ["p"], "铬": ["cr"], "钼": ["mo"], "镍": ["ni"],
    "铌": ["nb"], "钛": ["ti"], "钒": ["v"], "钙": ["ca"], "硼": ["b"],
    "氮": ["n"], "氢": ["h"], "渣": ["slag"], "碱度": ["basicity"],
}
REV_SYN = {}
for _cn, _ens in SYNONYMS.items():
    for _en in _ens:
        REV_SYN.setdefault(_en, []).append(_cn)

STOP = {
    "怎么", "么算", "多少", "如何", "为多", "什么", "需要", "要加", "加多", "计算",
    "公式", "可以", "以及", "的是", "是在", "有哪", "哪些", "为什", "么是", "一下",
    "请问", "告诉", "我该", "应该", "是否", "这个", "那个", "一个", "怎样", "么样",
    "为何", "时候", "的话", "就是", "还是", "或者", "而且", "所以", "因为", "如果",
    "现在", "具体", "一般", "大约", "大概", "帮我", "给我", "我想", "我要", "想问",
}


def tokenize(text, drop_stop=False):
    text = unicodedata.normalize("NFKC", text or "").lower()
    toks = _WORD.findall(text)
    for run in _CN.findall(text):
        if len(run) == 1:
            toks.append(run)
        else:
            toks.extend(run[i:i + 2] for i in range(len(run) - 1))
            if len(run) <= 6:
                toks.append(run)
    low = text
    for cn, ens in SYNONYMS.items():
        if cn in low:
            toks.extend(ens)
    for en, cns in REV_SYN.items():
        if en in toks:
            toks.extend(cns)
    if drop_stop:
        toks = [t for t in toks if t not in STOP]
    return toks


class KnowledgeBase:
    def __init__(self, path=KB_PATH):
        # 手册原文有版权，默认不随仓库分发；缺失时降级为空库，检索返回空结果，
        # 其余计算功能不受影响。自行放入 data/manuals/*.txt 后跑 tools/build_kb.py 重建。
        try:
            with open(path, encoding="utf-8") as f:
                self.chunks = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            self.chunks = []
        self.N = len(self.chunks)
        self.tf = []
        self.len = []
        df = Counter()
        for c in self.chunks:
            toks = tokenize(c["text"])
            # 标题/小节加权
            toks += tokenize(c.get("section", "")) * 2
            cnt = Counter(toks)
            self.tf.append(cnt)
            self.len.append(len(toks))
            for t in cnt:
                df[t] += 1
        self.avg = sum(self.len) / max(1, self.N)
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.k1, self.b = 1.5, 0.75
        self._vec = None
        self._vec_tried = False

    def vector_index(self, dim=64, rebuild=False):
        """懒加载向量索引。

        优先用 embedding 后端（fastembed 本地模型 / 远程 API）构建的稠密向量；
        一个都用不了时退到纯标准库的 LSA 索引。都没有知识库就返回 None。
        """
        if self._vec_tried and not rebuild:
            return self._vec
        self._vec_tried = True
        if not self.chunks:
            self._vec = None
            return None

        try:
            from .embed import get_backend
            from .vector_store import VectorStore
            backend = get_backend()
            if backend is not None:
                vs = None if rebuild else VectorStore.load(self.chunks, backend)
                if vs is None:
                    vs = VectorStore(self.chunks, backend).build()
                    try:
                        vs.save()
                    except Exception:
                        pass
                self._vec = vs
                return vs
        except Exception:
            pass

        try:
            from .vec import VectorIndex, VEC_PATH
            vi = None if rebuild else VectorIndex.load(VEC_PATH, self.chunks, dim=dim)
            if vi is None:
                vi = VectorIndex(self.chunks, dim=dim)
                try:
                    vi.save(VEC_PATH)
                except Exception:
                    pass
            self._vec = vi
            return vi
        except Exception:
            self._vec = None
            return None

    def vector_label(self):
        vi = self._vec
        if vi is None:
            return "none"
        meta = getattr(vi, "meta", None)
        if meta:
            return f"{meta.get('backend')}:{meta.get('model')}"
        return getattr(vi, "backend", "unknown")

    def search_hybrid(self, query, k=6, doc=None, mode="hybrid"):
        """三种模式：bm25（原有）/ vector / hybrid（RRF 融合）。"""
        from . import hybrid as H
        return H.search(self, query, k=k, doc=doc, mode=mode)

    def search(self, query, k=6, doc=None):
        qt = tokenize(query, drop_stop=True)
        if not qt:
            return []
        qcnt = Counter(qt)
        scored = []
        for i, c in enumerate(self.chunks):
            if doc and c["doc"] != doc:
                continue
            s = 0.0
            for t, qn in qcnt.items():
                f = self.tf[i].get(t, 0)
                if not f:
                    continue
                idf = self.idf.get(t, 0.0)
                denom = f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
                s += idf * (f * (self.k1 + 1) / denom) * min(qn, 3)
            if s > 0:
                scored.append((s, i))
        scored.sort(reverse=True)
        # 覆盖度重排：同时命中多个查询词的块优先
        qset = set(qt)
        reranked = []
        for sc, i in scored[:30]:
            doc_terms = set(self.tf[i].keys())
            cov = len(qset & doc_terms) / max(1, len(qset))
            reranked.append((sc * (0.65 + 0.7 * cov), i))
        reranked.sort(reverse=True)
        out = []
        for s, i in reranked[:k]:
            c = dict(self.chunks[i])
            c["score"] = round(s, 3)
            out.append(c)
        return out

    def sections(self):
        out = {}
        for c in self.chunks:
            key = (c["doc"], c.get("section") or "（未分节）")
            out.setdefault(key, []).append(c["page"])
        result = []
        for (doc, sec), pages in out.items():
            result.append({"doc": doc, "section": sec, "pages": sorted(set(pages))})
        return result


KB = KnowledgeBase()

INTENTS = [
    {"key": "charge", "label": "炉料配比", "view": "charge",
     "kw": ["配比", "配料", "废钢", "炉料", "料斗", "装料", "成本", "收得率", "出钢量", "原料"]},
    {"key": "alloy", "label": "合金补加", "view": "alloy",
     "kw": ["合金", "锰铁", "硅铁", "增碳", "回收率", "补加", "钼铁", "铌铁", "钛铁"]},
    {"key": "deox", "label": "铝脱氧", "view": "refine",
     "kw": ["脱氧", "铝", "氧含量", "氧活度", "Al2O3", "夹杂"]},
    {"key": "desulf", "label": "脱硫 / 造渣", "view": "refine",
     "kw": ["脱硫", "硫", "碱度", "炉渣", "石灰", "萤石", "白云石", "Ls"]},
    {"key": "decarb", "label": "脱碳", "view": "refine",
     "kw": ["脱碳", "碳含量", "RH", "真空", "循环脱气", "超低碳"]},
    {"key": "hydrogen", "label": "除氢", "view": "refine",
     "kw": ["除氢", "氢", "脱气", "H含量", "ppm氢"]},
    {"key": "temp", "label": "温度 / 液相线", "view": "refine",
     "kw": ["温度", "液相线", "过热", "加热", "温降", "出钢温度", "熔点"]},
    {"key": "stir", "label": "搅拌", "view": "refine",
     "kw": ["搅拌", "氩气", "功率密度", "混匀"]},
    {"key": "basket", "label": "料斗与装料", "view": "charge",
     "kw": ["料斗", "料篮", "装料", "体积", "40", "粗废料", "电极"]},
]

GRADE_KEYS = [
    ("tinb_ulc", ["tinb", "ti-nb", "超低碳", "ulc", "汽车车身"]),
    ("pipeline", ["管线", "管道", "pipeline"]),
    ("sc21_engineering", ["2026", "赛题", "高铬工程钢"]),
    ("engineering", ["工程钢", "工程用钢", "4140", "低合金"]),
    ("structural", ["结构钢", "建筑钢", "通用钢", "建筑梁"]),
]


def detect_intent(q):
    ql = q.lower()
    best, hits = None, 0
    for it in INTENTS:
        n = sum(1 for k in it["kw"] if k.lower() in ql)
        if n > hits:
            best, hits = it, n
    return best


def detect_grade(q):
    ql = q.lower()
    for key, kws in GRADE_KEYS:
        if any(k.lower() in ql for k in kws):
            return key
    return None


def _split_sent(text):
    return [s.strip() for s in re.split(r"(?<=[。；!?！？])", text) if len(s.strip()) > 8]


def offline_answer(q, k=6):
    intent = detect_intent(q)
    results = KB.search(q, k=k)
    qset = set(tokenize(q))
    scored = []
    for r in results[:5]:
        for s in _split_sent(r["text"]):
            st = set(tokenize(s))
            if not st:
                continue
            overlap = len(qset & st) / (1 + math.sqrt(len(st)))
            bonus = 0.10 if re.search(r"\d", s) else 0.0
            if "=" in s or "公式" in s:
                bonus += 0.12
            scored.append((overlap + r["score"] * 0.02 + bonus, s, r))
    scored.sort(key=lambda x: -x[0])
    picked, seen = [], set()
    for score, s, r in scored:
        key = s[:30]
        if key in seen:
            continue
        seen.add(key)
        picked.append({"text": s, "doc_title": r["doc_title"], "page": r["page"],
                       "section": r.get("section", ""), "score": round(score, 3)})
        if len(picked) >= 3:
            break

    if not picked:
        return {"answer": "手册中没有检索到直接相关内容。可以换一个关键词，或直接使用左侧的计算器。",
                "citations": [], "intent": intent, "actions": []}

    lines = []
    for p in picked:
        sec = f"（{p['section']}）" if p["section"] else ""
        lines.append(f"《{p['doc_title']}》第 {p['page']} 页{sec}：{p['text']}")
    body = "\n\n".join(lines)

    tip = ""
    if intent:
        tips = {
            "charge": "配料时先用 LP 求最小成本，再检查 P/S/Cr/Mo/Ni/Cu 等不可去除残余元素；C、Si、Mn 可在熔化/精炼阶段调整。",
            "alloy": "按 m = Δ%×钢水质量/(母合金含量×回收率) 计算；注意母合金会带入 C、Si、P 等二次元素，低碳钢种要用低碳/高纯锰铁。",
            "deox": "铝脱氧量 = (54/48)×[%O] + 目标残铝；再用回收率折算合金质量。一次性算准可获得夹杂物奖励。",
            "desulf": "先铝脱氧到低氧活度，再用 CaO 基渣强搅拌；渣量 Ws = (Wm/Ls)×(S0-Saim)/Saim。",
            "decarb": "RH 脱碳遵循指数动力学 [%C]f = [%C]eq + ([%C]i-[%C]eq)exp(-kc·t)，真空度决定平衡碳。",
            "hydrogen": "除氢受传质控制，kH 随氩气流量增加；罐式脱气 kH = 0.0576V̇ + 0.02。",
            "temp": "先算液相线温度，再叠加出钢温降 −60°C、等待 −0.5°C/min、合金 −6°C/t、搅拌 −1.5°C/min、电加热 +3°C/min（满功率）。",
            "stir": "搅拌功率 ε = 14.23(VT/M)·log((1+H)/(1.48P0))；ε>70 W/t 时脱硫速率常数快速上升。",
            "basket": "单斗 40 m³，总容积约 100 m³；每个料斗粗废料不超过 30%，否则电极折断风险上升。",
        }
        tip = tips.get(intent["key"], "")
    answer = body
    if tip:
        answer += "\n\n**操作要点**：" + tip
    actions = []
    if intent:
        actions.append({"label": f"打开{intent['label']}计算器", "view": intent["view"]})
    return {"answer": answer, "citations": picked, "intent": intent, "actions": actions}
