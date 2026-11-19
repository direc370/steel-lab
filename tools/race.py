# -*- coding: utf-8 -*-
"""比赛现场快通道：把模拟器给的实测数据一次性转成「下一步怎么点」。

用法一（推荐，命令行直接给数）：
    py -X utf8 tools/race.py eaf mass=82 temp=1580 C=0.50 Si=0.05 Mn=0.30 Cr=0.90 O2=150 power=90

用法二（把模拟器摘要素材整段粘进来，脚本自己认字段）：
    py -X utf8 tools/race.py eaf --paste state.txt

用法三（标准 JSON，前后端同一份结构）：
    py -X utf8 tools/race.py --json state.json

支持的元素键：C Si Mn Cr Mo Ni Cu Al P S O N H Ti V Nb Sn As
支持的状态键：mass temp o2 power carbon target_c grade stage horizon alloy_margin tap_temp
  阶段 stage 可选：melt / blow / sample / alloy / tap（二次精炼：casob / degas / lf / cast）
输出：停氧判断表 + 下一步动作 + 停氧后合金 10 kg 配方 + 成本，可直接照着点。
"""

import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.dynamics import advise  # noqa: E402
from engine.data import EAF_GRADES, SM_GRADES  # noqa: E402

ELEMENTS = ["C", "Si", "Mn", "Cr", "Mo", "Ni", "Cu", "Al", "P", "S",
            "O", "N", "H", "Ti", "V", "Nb", "Sn", "As", "B", "Ca"]
STATE_NUM = {"mass", "temp", "o2", "power", "carbon", "target_c",
             "horizon", "alloy_margin", "temp_start"}
STATE_STR = {"grade", "stage", "sm_grade", "eaf_grade"}

# 粘贴文本里可能出现的别名（中文界面 + 英文缩写）
ALIAS = {
    "温度": "temp", "钢水温度": "temp", "钢水量": "mass", "出钢量": "mass",
    "氧流量": "o2", "氧气": "o2", "供氧": "o2", "电功率": "power", "功率": "power",
    "碳枪": "carbon", "喷碳": "carbon", "目标碳": "target_c", "停氧碳": "target_c",
    "阶段": "stage", "钢种": "grade",
}
STATUS_CN = {"ok": "合格", "high": "偏高", "low": "偏低", "blow": "继续吹"}


def _to_float(txt):
    try:
        return float(str(txt).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_kv(args):
    """解析 mass=82 temp=1580 C=0.50 这类参数。"""
    state, track = {}, "eaf"
    for a in args:
        if a in ("eaf", "sm"):
            track = a
            continue
        if "=" not in a:
            continue
        k, v = a.split("=", 1)
        k = k.strip()
        k = ALIAS.get(k, k)
        if k in ELEMENTS:
            f = _to_float(v)
            if f is not None:
                state.setdefault("comp", {})[k] = f
        elif k in STATE_NUM:
            f = _to_float(v)
            if f is not None:
                state[k] = f
        elif k in STATE_STR:
            state[k] = v.strip()
    return track, state


def parse_paste(text):
    """从模拟器摘要里抓数字：逐行找 'C 0.52' / 'C: 0.52%' / '碳 0.52' 等。"""
    state = {"comp": {}}
    comp = state["comp"]
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # 元素 + 数字（允许 % 和前后缀）
        for el in ELEMENTS:
            pat = rf"(?<![A-Za-z]){el}(?![A-Za-z])\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)\s*%?"
            m = re.search(pat, line)
            if m and el not in comp:
                v = float(m.group(1))
                # ppm 转 %
                if "ppm" in line.lower() and v > 50:
                    v = v / 10000.0
                comp[el] = round(v, 5)
        for cn, key in ALIAS.items():
            if cn in line:
                m = re.search(rf"{cn}\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)", line)
                if m:
                    v = float(m.group(1))
                    if key == "mass" and v > 400:  # 可能是 kg
                        v = v / 1000.0
                    state[key] = v if key not in STATE_STR else m.group(1)
    return state


def fmt_alloy(plan, mass):
    if not plan:
        return ["  （无可行合金方案：请补充实测元素，或检查是否已全部合格）"]
    out = []
    adds = sorted(plan.get("additions") or [], key=lambda x: -float(x.get("mass") or 0))
    for a in adds:
        if float(a.get("mass") or 0) <= 0:
            continue
        out.append(f"  {a.get('name'):<8} {float(a['mass']):>6.0f} kg   ${float(a.get('cost') or 0):>7.0f}")
    if not out:
        out.append("  （无需补加）")
    out.append(f"  合计 ${float(plan.get('cost') or 0):,.0f}"
               f"（${float(plan.get('cost') or 0) / max(mass, 1e-6):.2f}/t）"
               f"  温降 {float(plan.get('temperature_drop') or 0):.1f}°C")
    fp = plan.get("final") or {}
    keys = [k for k in ("C", "Si", "Mn", "Cr", "Mo") if k in fp]
    if keys:
        out.append("  合金化后：" + "  ".join(f"{k} {fp[k]:.4f}" for k in keys))
    oos = plan.get("out_of_spec") or []
    real = [x for x in oos if (x.get("element") if isinstance(x, dict) else str(x)) not in ("O", "H", "N")]
    if real:
        txt = []
        for x in real:
            if isinstance(x, dict):
                txt.append(f"{x.get('element')} {x.get('value')}（窗口 {x.get('target')}）")
            else:
                txt.append(str(x))
        out.append("  ⚠ 10 kg 档仍越限：" + "；".join(txt))
    return out


def render(track, state):
    payload = {"track": track, "state": state}
    res = advise(payload)
    mass = float(state.get("mass") or 0) or 85.0
    lines = []
    lines.append("=" * 62)
    lines.append(f"  {'EAF 电弧炉' if track != 'sm' else '二次精炼'} · 现场动作卡")
    lines.append("=" * 62)
    lines.append("")
    lines.append("[判断]")
    for ln in _wrap(res.get("summary") or "", 58):
        lines.append("  " + ln)

    stop = res.get("stop") or {}
    rows = stop.get("elements") or []
    if rows:
        lines.append("")
        lines.append("[停氧/元素 / 窗口]")
        for r in rows:
            tg = r.get("target") or [None, None]
            lo = "—" if tg[0] is None else f"{tg[0]:g}"
            hi = "—" if len(tg) < 2 or tg[1] is None else f"{tg[1]:g}"
            st = STATUS_CN.get(r.get("status"), r.get("status"))
            mark = "  " if r.get("status") == "ok" else "→ "
            lines.append(f"{mark}{r.get('element'):<3}{float(r.get('value') or 0):>9.4f}"
                         f"   窗口 {lo}–{hi}   {st}")

    acts = res.get("actions") or []
    full = "--full" in sys.argv
    if not full:
        # 简洁模式：把「已纳入全局合金方案」这类解释性条目折叠掉，现场只看要做的动作
        acts = [a for a in acts if "已纳入全局合金方案" not in str(a.get("label") or "")]
    if acts:
        lines.append("")
        lines.append("[下一步，按顺序]")
        for i, a in enumerate(acts, 1):
            lines.append(f"  {i}. {a.get('label')}")
            why = a.get("why") or ""
            for ln in _wrap(why, 56):
                lines.append("     " + ln)

    lines.append("")
    lines.append(f"[停氧后合金（10 kg 档，{mass:.0f} t）]")
    lines.extend(fmt_alloy(res.get("alloy_plan"), mass))

    # 现场保护：数据填得太少或离窗口太远时，LP 会给出"软约束最低可达"解，
    # 数字看起来很夸张（几吨合金、温降几十度），不能直接照点。
    ap = res.get("alloy_plan") or {}
    added = float(ap.get("added_total") or 0)
    drop = abs(float(ap.get("temperature_drop") or 0))
    if added > 0.03 * mass * 1000 or drop > 25:
        lines.append("")
        lines.append("  ⚠ 结果可疑：合金量或温降明显超出常规，通常是元素没填全或")
        lines.append("    实测值离窗口太远。请补全成分后再算，不要直接照这个数点。")

    samp = res.get("sample") or {}
    if samp:
        lines.append("")
        lines.append(f"[取样节奏] 建议 {samp.get('in_min')} min 后取样；"
                     f"到停点约 {samp.get('to_target_min')} min")
    lines.append("")
    return "\n".join(lines)


def _wrap(text, width):
    text = re.sub(r"\s+", " ", str(text)).strip()
    if not text:
        return [""]
    out, line = [], ""
    for ch in text:
        line += ch
        if len(line) >= width:
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return out


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if "--json" in argv:
        i = argv.index("--json")
        path = argv[i + 1] if len(argv) > i + 1 else ""
        data = json.load(io.open(path, encoding="utf-8")) if path else json.load(sys.stdin)
        track = data.get("track", "eaf")
        state = data.get("state") or data
        print(render(track, state))
        return 0

    if "--paste" in argv:
        i = argv.index("--paste")
        path = argv[i + 1] if len(argv) > i + 1 else ""
        text = io.open(path, encoding="utf-8").read() if path else sys.stdin.read()
        track = "sm" if "sm" in argv or "精炼" in text else "eaf"
        state = parse_paste(text)
        if not state.get("comp"):
            print("没认出成分，请手动用 mass=82 temp=1580 C=0.50 形式给数。")
            return 2
        print(f"（识别到：{state}）")
        print(render(track, state))
        return 0

    track, state = parse_kv(argv[1:])
    if not state.get("comp"):
        print(__doc__)
        return 2
    print(render(track, state))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
