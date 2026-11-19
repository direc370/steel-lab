# -*- coding: utf-8 -*-
"""检索质量评测：BM25 / 向量 / 混合三种模式对比。

评测集两部分
------------
1. **章节题**：把有明确章节归属的知识块的小节标题去掉编号当查询，正例是该小节
   覆盖的页。这部分偏字面匹配，BM25 天然占优，用来确认向量没有把基线拉坏。
2. **口语题**：人工写的真实问法（不照抄标题），正例给可接受页集合。这部分才是
   向量检索该赢的地方——用户不会用手册目录的措辞提问。

指标：Recall@k、MRR@10、Hit@1。跑法：
    python tools/eval_retrieval.py
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.kb import KnowledgeBase  # noqa: E402
from engine.hybrid import search as hybrid_search  # noqa: E402

# 口语题：(查询, 可接受页集合)。页数经人工核对手册原文确认，tol=1 容忍相邻页。
ORAL = [
    ("废钢怎么搭配最省钱", {10, 12, 13, 14}),
    ("料斗一次能装多少", {16, 25}),
    ("电极有哪几档功率", {27}),
    ("出钢温度取多少度", {40}),
    ("合金加多少怎么算", {41, 42}),
    ("铝脱氧要加几公斤", {45, 46}),
    ("石灰加多少合适", {32, 48}),
    ("渣子太稀了拉不住弧", {32, 47}),
    ("脱硫需要多长时间", {48, 56}),
    ("碳吹过头了怎么办", {30, 32, 33}),
    ("真空脱气主要脱什么", {8, 49, 50}),
    ("成分分析报告在哪看", {21, 36, 38}),
]


def norm_section(s):
    return re.sub(r"^[\d.]+\s*", "", (s or "").strip())


def build_section_set(kb):
    items = []
    seen = set()
    for c in kb.chunks:
        sec = c.get("section") or ""
        if not sec or sec.startswith("（未分节）"):
            continue
        q = norm_section(sec)
        if len(q) < 3:
            continue
        key = (c.get("doc"), q)
        if key in seen:
            continue
        seen.add(key)
        pages = {c2["page"] for c2 in kb.chunks
                 if c2.get("doc") == c.get("doc") and c2.get("section") == sec}
        items.append((q, pages, c.get("doc")))
    return items


def hits_at(results, pages, tol=1):
    for r in results:
        if any(abs(r["page"] - p) <= tol for p in pages):
            return True
    return False


def first_rank(results, pages, tol=1):
    for i, r in enumerate(results, 1):
        if any(abs(r["page"] - p) <= tol for p in pages):
            return i
    return 0


def evaluate(kb, items, mode, k=5, tol=1, doc=None):
    rec = 0
    rr = 0.0
    hit1 = 0
    for q, pages, d in items:
        r = hybrid_search(kb, q, k=k, mode=mode, doc=doc or d)
        if hits_at(r, pages, tol):
            rec += 1
        rank = first_rank(r, pages, tol)
        if rank:
            rr += 1.0 / rank
            if rank == 1:
                hit1 += 1
    n = max(1, len(items))
    return {"recall": rec / n, "mrr": rr / n, "hit1": hit1 / n, "n": len(items)}


def main():
    kb = KnowledgeBase()
    if not kb.chunks:
        print("知识库为空：先放手册并运行 tools/build_kb.py")
        return 1
    vi = kb.vector_index()
    label = kb.vector_label()
    dim = 0
    if vi is not None:
        dim = (getattr(vi, "meta", {}) or {}).get("dim") or getattr(vi, "dim", 0)
    print(f"知识库 {kb.N} 块，向量后端 {label}，维度 {dim}\n")

    sec = build_section_set(kb)
    sets = [("章节题", sec, 1), ("口语题", [(q, p, None) for q, p in ORAL], 1)]

    for name, items, tol in sets:
        print(f"== {name}（{len(items)} 条）==")
        print(f"{'模式':<8}{'Recall@5':>10}{'MRR@10':>10}{'Hit@1':>8}")
        for mode in ("bm25", "vector", "hybrid"):
            m = evaluate(kb, items, mode, k=5, tol=tol)
            print(f"{mode:<8}{m['recall']:>10.3f}{m['mrr']:>10.3f}{m['hit1']:>8.3f}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
