# -*- coding: utf-8 -*-
"""合金补加的全局线性规划（比逐元素贪心更省成本）。

变量：每种金属添加剂的加入量 y_j（kg）。
约束：最终钢液成分落在目标窗口内（质量随合金加入而变化，已线性化）；
      添加剂用量上限；总合金量上限。
目标：最小化 Σ y_j × 单价。

与 `engine/alloys.py` 的贪心算法相比，本模块会同时考虑：
- 高碳锰铁 vs 低碳锰铁的 C 夹带；
- 高碳铬铁 vs 硅铬的 Cr/Si 联产；
- 普通硅铁 vs 高纯硅铁的 Al 夹带；
- 加入合金导致钢液质量增加、成分被稀释的二次效应。
"""

from .data import EAF_ADDITIVES, RECOVERY
from .simplex import minimize

# 只对需要主动配到的元素留安全余量；P/S/Ni/Cu 等残余元素保留原上限，
# 否则初始值本来就在上限附近时会把 LP 逼成不可行。
MARGIN_ELEMENTS = ("C", "Si", "Mn", "Cr", "Mo")

MAX_KG = {
    "c": 500.0,
    "c_sm": 500.0,
    "al": 100.0,
    "al_sm": 100.0,
    "femo": 1000.0,
    "femo_sm": 1000.0,
    "fev": 1000.0,
    "fev_sm": 1000.0,
    "sic": 1000.0,
    "fesi75": 2000.0,
    "fesi75hp": 2000.0,
    "fesi_sm": 2000.0,
    "cr_ore": 5000.0,
    "cr_ore_ls": 5000.0,
    "fecr_hc_sm": 5000.0,
    "fecr_mc_sm": 5000.0,
    "fecr_lc_sm": 5000.0,
    "femn_hc": 3000.0,
    "femn_lc": 3000.0,
    "femn_hc_sm": 3000.0,
    "femn_mc_sm": 3000.0,
    "femn_lc_sm": 3000.0,
    "simn_sm": 3000.0,
    "sicr": 3000.0,
}


def _profile_dict(profile):
    if isinstance(profile, str):
        profile = RECOVERY.get(profile, RECOVERY["eaf_cal"])
    return {k: float(v) for k, v in profile.items() if k != "label"}


def optimize_alloy_lp(mass_t, initial, specs, catalog=None, profile="eaf_cal",
                      margin=0.2, max_kg=None, total_max_kg=None, drift_caps=None,
                      forbidden=None):
    """最小成本合金补加 LP。

    mass_t: 初始钢水质量（吨）
    initial: 初始成分 {元素: wt%}
    specs: 目标窗口 {元素: [下限, 上限]}
    catalog: 添加剂列表，默认 EAF 金属添加剂（排除熔剂）
    profile: 回收率表或名称（默认 eaf_cal）
    margin: 对 C/Si/Mn/Cr 窗口向内收缩的比例（0.2 = 两侧各留 20% 余量）
    max_kg: 单种添加剂上限（覆盖默认）
    total_max_kg: 总合金量上限（默认 15000 kg）
    drift_caps: 已合格元素允许的最大上漂量，例如 {"Si": 0.01} 表示
        初始 Si 已在窗口内时，最终 Si 最多比初始高 0.01 个百分点，
        防止为省成本用硅锰把已经合格的 Si 顶到上限。
    """
    catalog = catalog or EAF_ADDITIVES
    forbid = set(forbidden or [])
    adds = [a for a in catalog if not a.get("flux") and a["key"] not in forbid]
    rec = _profile_dict(profile)
    max_kg = {**MAX_KG, **(max_kg or {})}
    total_max_kg = float(total_max_kg if total_max_kg is not None else 15000.0)
    drift_caps = drift_caps or {}
    m0 = float(mass_t) * 1000.0

    elements = [e for e in specs if e in initial or any(e in a["comp"] for a in adds)]
    n = len(adds)
    if n == 0:
        return {"status": "infeasible", "message": "没有可用金属添加剂"}

    # 快速检查：初始值已经超过上限时，LP 必然不可行，给出可操作提示
    for e in MARGIN_ELEMENTS:
        if e not in specs:
            continue
        lo, hi = specs[e]
        v = float(initial.get(e, 0.0))
        if hi is not None and v > hi + 1e-9:
            action = "先吹氧脱碳" if e == "C" else ("先吹氧降硅" if e == "Si" else "先稀释/氧化")
            return {"status": "infeasible",
                    "message": f"初始 {e} {v:.4f}% 高于上限 {hi}%；合金只能增加不能降低，请{action}。"}

    c = [a["price"] / 1000.0 for a in adds]  # $/kg
    A_ub, b_ub = [], []

    for e in elements:
        lo, hi = specs[e]
        lo0, hi0 = lo, hi
        if margin and e in MARGIN_ELEMENTS and lo is not None and hi is not None:
            span = hi - lo
            lo = lo + span * margin
            hi = hi - span * margin
        # 初始值本来就在合格窗口内：允许“保持”，不强制补到收缩后的下限。
        # 否则会出现“Si 已经 0.24–0.32% 合格，还要加硅锰补到 0.264%”的怪事。
        v_start = initial.get(e)
        if (v_start is not None and lo0 is not None and hi0 is not None
                and float(lo0) - 1e-9 <= float(v_start) <= float(hi0) + 1e-9):
            if lo is not None:
                lo = min(float(lo), float(v_start))
        # 初始值已经在（收缩后的）上限之上：合金只能增加不能降低，
        # 不能再要求“降到 margin 上限”，否则会误判无解。允许保持原值。
        v_initial = initial.get(e)
        if v_initial is not None and hi is not None and float(v_initial) > float(hi):
            hi = float(v_initial)
        # 已合格元素不允许被“顺手”顶到上限：例如 Si 已经 0.28%，加硅锰补 Mn
        # 最多把 Si 带到 0.29%，剩余 Mn 改用低碳/高碳锰铁。
        if e in drift_caps:
            v0 = initial.get(e)
            if v0 is not None and lo is not None and float(v0) >= float(lo) - 1e-9:
                cap = float(v0) + float(drift_caps[e])
                hi = cap if hi is None else min(float(hi), cap)
        init_kg = float(initial.get(e, 0.0)) / 100.0 * m0
        r = rec.get(e, 100.0) / 100.0
        # 上限：Σ y_j (a_je r - hi/100) <= hi/100 * M0 - init_kg
        if hi is not None:
            row = [a["comp"].get(e, 0.0) / 100.0 * r - hi / 100.0 for a in adds]
            A_ub.append(row)
            b_ub.append(hi / 100.0 * m0 - init_kg)
        # 下限：Σ y_j (lo/100 - a_je r) <= init_kg - lo/100 * M0
        if lo is not None and lo > 0:
            row = [lo / 100.0 - a["comp"].get(e, 0.0) / 100.0 * r for a in adds]
            A_ub.append(row)
            b_ub.append(init_kg - lo / 100.0 * m0)

    # 总合金量上限，防止用极便宜但大量带入杂质的添加剂
    A_ub.append([1.0] * n)
    b_ub.append(total_max_kg)
    bounds = [(0.0, float(max_kg.get(a["key"], 5000.0))) for a in adds]

    res = minimize(c, A_ub, b_ub, None, None, bounds)
    if res.status != "optimal":
        return {"status": "infeasible" if res.status == "infeasible" else res.status,
                "message": res.message or "合金 LP 无可行解"}

    # 取整到 1 kg，再按实际质量复核
    plan = []
    total_cost = 0.0
    mass = m0
    comp = {e: float(initial.get(e, 0.0)) / 100.0 * m0 for e in elements}
    for a, y in zip(adds, res.x):
        kg = round(y, 0)
        if kg < 1:
            continue
        plan.append({
            "key": a["key"], "name": a["name"], "mass": kg,
            "cost": round(kg * a["price"] / 1000.0, 1),
            "elements": {e: round(kg * v / 100.0 * rec.get(e, 100.0) / 100.0, 2)
                         for e, v in a["comp"].items() if v > 0},
        })
        total_cost += kg * a["price"] / 1000.0
        mass += kg
        for e, v in a["comp"].items():
            if e in comp:
                comp[e] += kg * v / 100.0 * rec.get(e, 100.0) / 100.0

    final = {e: comp.get(e, 0.0) / mass * 100.0 for e in elements}
    out_of_spec = []
    for e, (lo, hi) in specs.items():
        v = final.get(e)
        if v is None:
            continue
        if lo is not None and v < lo - 1e-4:
            out_of_spec.append(f"{e} {v:.4f}% < 下限 {lo}%")
        if hi is not None and v > hi + 1e-4:
            out_of_spec.append(f"{e} {v:.4f}% > 上限 {hi}%")

    return {
        "status": "ok",
        "mass_before": round(mass_t, 2),
        "mass_after": round(mass / 1000.0, 3),
        "additions": plan,
        "added_total": round(sum(p["mass"] for p in plan), 1),
        "cost": round(total_cost, 1),
        "cost_per_t": round(total_cost / (mass / 1000.0), 2) if mass else 0,
        "temperature_drop": round(sum(p["mass"] for p in plan) / 1000.0 * 6.0, 1),
        "final": {e: round(v, 4) for e, v in final.items()},
        "out_of_spec": out_of_spec,
        "warnings": out_of_spec[:],
        "unmet": [],
        "method": "LP",
        "margin": margin,
    }
