# -*- coding: utf-8 -*-
"""构建 / 检查向量库。

用法：
    python tools/build_vectors.py            # 自动选后端，构建并落盘
    python tools/build_vectors.py --status   # 只报告当前可用后端
    python tools/build_vectors.py --api      # 指定尝试远程 embedding 接口
    python tools/build_vectors.py --lsa      # 指定纯标准库 LSA 兜底

产物：data/vectors.json（稠密向量，kb.json 变更后签名不一致会自动重建）
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.kb import KnowledgeBase  # noqa: E402
from engine import embed as E  # noqa: E402
from engine.vector_store import VectorStore  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", action="store_true", help="只报告可用后端")
    ap.add_argument("--api", action="store_true", help="优先尝试远程 embedding")
    ap.add_argument("--lsa", action="store_true", help="强制用纯标准库 LSA")
    ap.add_argument("--rebuild", action="store_true", help="忽略缓存重新编码")
    args = ap.parse_args()

    if args.status:
        st = E.status()
        print("本地 fastembed：", "可用" if st["local"] else "未安装")
        if st["local_models"]:
            zh = [m for m in st["local_models"] if "zh" in m.lower() or "multilingual" in m.lower()]
            print("  中文/多语模型：", ", ".join(zh[:6]) or "（列表为空）")
        print("远程 API 已配置：", "是" if st["api_configured"] else "否")
        return 0

    kb = KnowledgeBase()
    if not kb.chunks:
        print("知识库为空：先放手册并运行 tools/build_kb.py")
        return 1
    print(f"知识库 {kb.N} 块")

    if args.lsa:
        from engine.vec import VectorIndex
        vi = VectorIndex(kb.chunks, dim=64)
        vi.save()
        print(f"已用 LSA 兜底：backend={vi.backend} dim={vi.dim} -> data/vec_index.json")
        return 0

    backend = E.get_backend(prefer="api" if args.api else None)
    if backend is None:
        print("没有可用的 embedding 后端，退回 LSA")
        from engine.vec import VectorIndex
        vi = VectorIndex(kb.chunks, dim=64)
        vi.save()
        print(f"LSA：dim={vi.dim} -> data/vec_index.json")
        return 0

    print(f"后端 {backend.kind} / 模型 {backend.name}")
    vs = None if args.rebuild else VectorStore.load(kb.chunks, backend)
    if vs is not None:
        print(f"命中缓存：{len(vs.ids)} 条，维度 {vs.meta.get('dim')}")
        return 0

    import time
    t0 = time.time()
    vs = VectorStore(kb.chunks, backend).build()
    path = vs.save()
    print(f"编码完成：{len(vs.ids)} 条，维度 {vs.meta['dim']}，"
          f"耗时 {time.time() - t0:.1f}s -> {os.path.basename(path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())