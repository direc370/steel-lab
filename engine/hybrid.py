# -*- coding: utf-8 -*-
"""混合检索：BM25 与向量检索的结果融合。

用 RRF（Reciprocal Rank Fusion）而不是分数加权，原因很实际：
BM25 的分数无上界、依赖查询词长度，余弦相似度是 0–1，两者量纲不同，
任何线性加权都要为每个查询重新调参。RRF 只看排名，`1/(k+rank)` 累加，
对分数尺度免疫，是检索系统里最稳的默认融合方式。

k 默认 60 来自 RRF 原论文的经验值：k 越大，靠后的名次衰减越慢，
适合两路结果质量接近的情况；如果某一路明显更强，可以调小 k 或加权重。
"""


def fuse(ranked_lists, k=60, weights=None, limit=None):
    """把多路排序结果融合成一路。

    ranked_lists : [(名称, [item, ...]), ...]  item 需带唯一 id
    weights      : {名称: 权重}，默认等权
    返回按 RRF 分数降序的 item 列表，每项附加 rrf / hit_by 字段
    """
    weights = weights or {}
    scores = {}
    store = {}
    hits = {}

    for name, items in ranked_lists:
        w = float(weights.get(name, 1.0))
        if w <= 0:
            continue
        for rank, item in enumerate(items, start=1):
            key = item.get("id") or (item.get("doc"), item.get("page"))
            if key is None:
                continue
            scores[key] = scores.get(key, 0.0) + w / (k + rank)
            hits.setdefault(key, []).append(name)
            if key not in store:
                store[key] = dict(item)
                store[key]["rank_" + name] = rank
            else:
                store[key].setdefault("rank_" + name, rank)

    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if limit:
        ordered = ordered[:limit]

    out = []
    for key, s in ordered:
        item = dict(store[key])
        item["rrf"] = round(s, 6)
        # 融合后的排序依据是 RRF 分，原始 BM25/余弦分只作参考，别让它冒充排序分
        item["raw_score"] = item.get("score", 0)
        item["score"] = round(s, 6)
        item["hit_by"] = hits.get(key, [])
        out.append(item)
    return out


def search(kb, query, k=6, doc=None, mode="hybrid", pool=12, weights=None,
           rrf_k=60):
    """在 KnowledgeBase 上做三种模式的检索。

    mode : "bm25" | "vector" | "hybrid"
    pool : 每一路先取多少个候选再融合，取 2×k 通常够
    """
    query = (query or "").strip()
    if not query:
        return []

    if mode == "bm25":
        return kb.search(query, k=k, doc=doc)

    if mode == "vector":
        vi = kb.vector_index()
        if vi is None:
            return kb.search(query, k=k, doc=doc)
        return vi.search(query, k=k, doc=doc)

    vi = kb.vector_index()
    bm = kb.search(query, k=pool, doc=doc)
    if vi is None:
        return bm[:k]
    vec = vi.search(query, k=pool, doc=doc)
    if not vec:
        return bm[:k]
    if not bm:
        return vec[:k]

    fused = fuse([("bm25", bm), ("vector", vec)], k=rrf_k,
                 weights=weights, limit=k)
    for item in fused:
        item["retriever"] = "+".join(item.get("hit_by", [])) or "hybrid"
    return fused
