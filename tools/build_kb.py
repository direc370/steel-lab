# -*- coding: utf-8 -*-
"""把两份手册的文本切成知识库块，输出 data/kb.json。

用法：python tools/build_kb.py
"""

import json
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = [
    ("eaf", "电弧炉模拟使用指南", "MAN0105601-CN", "data/manuals/eaf.txt"),
    ("sm", "二次炼钢模拟使用指南 2.0", "MAN0106601-CN", "data/manuals/sm.txt"),
]

HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s*[.。]?\s*(.{2,40})$")
NOISE = re.compile(
    r"^(Lesson\s*\d+\s*of\s*\d+|课程\s*\d+\s*of\s*\d+|第\s*\d+\s*页|Page\s*\d+.*)$",
    re.I,
)


def clean_page(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u3000", " ")
    lines = []
    for ln in text.split("\n"):
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        if not ln:
            continue
        if NOISE.match(ln):
            continue
        # 去掉常见的页眉页脚
        if ln.startswith("MAN010") or ln == "steeluniversity":
            continue
        lines.append(ln)
    return lines


def split_sentences(lines):
    joined = " ".join(lines)
    # 在中文句号/分号后断句，保留单位与小数
    parts = re.split(r"(?<=[。；!?！？])\s*", joined)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 700:
            # 长段按逗号再切
            sub = re.split(r"(?<=[，,])", p)
            buf = ""
            for s in sub:
                if len(buf) + len(s) > 700 and buf:
                    out.append(buf)
                    buf = s
                else:
                    buf += s
            if buf:
                out.append(buf)
        else:
            out.append(p)
    return out


def pack_sentences(sents, size=320, overlap=60):
    """把句子打包成定长块，相邻块之间保留 overlap 字符的重叠。

    切块是检索的第一道质量关：块太长（整页）会让向量被稀释、BM25 的词频也被
    平均掉；块之间不留重叠，答案恰好跨在切点两边时两半都召回不到。
    这里按句子边界切，块内不截断句子，重叠部分回退整句。
    """
    chunks = []
    buf = []
    length = 0
    i = 0
    while i < len(sents):
        s = sents[i]
        if length + len(s) <= size or not buf:
            buf.append(s)
            length += len(s)
            i += 1
            continue
        text = " ".join(buf).strip()
        if text:
            chunks.append(text)
        tail = []
        tlen = 0
        for s2 in reversed(buf):
            if tlen + len(s2) > overlap:
                break
            tail.insert(0, s2)
            tlen += len(s2)
        buf, length = tail, tlen
    if buf:
        text = " ".join(buf).strip()
        if text:
            chunks.append(text)
    return chunks


def build_doc(doc_key, title, code, rel_path, size=320, overlap=60):
    path = os.path.join(ROOT, rel_path)
    raw = open(path, encoding="utf-8").read()
    pages = re.split(r"===== PAGE (\d+) =====", raw)
    out = []
    for i in range(1, len(pages), 2):
        page_no = int(pages[i])
        body = pages[i + 1] if i + 1 < len(pages) else ""
        lines = clean_page(body)
        sec = ""
        for ln in lines[:8]:
            m = HEADING.match(ln)
            if m and len(m.group(1)) <= 6:
                cand = m.group(2).strip(" 。.")
                bad = any(ch in cand for ch in "%.,，。：:;；()（）")
                if 2 <= len(cand) <= 24 and not bad and not cand.replace(".", "").isdigit():
                    sec = f"{m.group(1)} {cand}"
                    break
        sents = split_sentences(lines)
        for text in pack_sentences(sents, size=size, overlap=overlap):
            if len(text) < 25:
                continue
            out.append({
                "id": f"{doc_key}-p{page_no}-{len(out):04d}",
                "doc": doc_key,
                "doc_title": title,
                "code": code,
                "page": page_no,
                "section": sec,
                "text": text,
            })
    return out


def main():
    kb = []
    for d in DOCS:
        kb.extend(build_doc(*d))
    path = os.path.join(ROOT, "data", "kb.json")
    json.dump(kb, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"chunks: {len(kb)} -> {path}")
    for d in DOCS:
        n = sum(1 for c in kb if c["doc"] == d[0])
        print(" ", d[0], n)


if __name__ == "__main__":
    main()
