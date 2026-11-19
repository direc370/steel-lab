# -*- coding: utf-8 -*-
"""废钢配料：线性规划最小成本、熔炼收得率修正、成分核算、料斗分配。

说明：EAF 熔化/吹氧过程中 C、Si、Mn、P、S 等会被部分氧化，
因此配料约束建立在“熔炼后（出钢前）成分”上，而不是废钢原始成分。
收得率可在界面中调整，并可用实际炉次结果校准。
"""

import math

from .data import SCRAPS, SCRAP_BY_KEY, EAF_GRADES, ELEMENTS
from .simplex import minimize

# 熔炼收得率默认值（元素从废钢进入钢液的比例）
# 注意：这是“强精炼”假设下的经验值，实际模拟中会随渣碱度、吹氧量、温度变化。
# 界面可逐项修改，并可用实际炉次数据校准。C/Si/Mn 不参与硬约束，只做提示。
MELT_RETENTION = {
    # 按 steeluniversity EAF 模拟器实炉反算
    # 2026-11-17 修正：模拟器「步骤1 配废钢」的 Ni 是**纯加权、不去除**。
    # 实测对照（82 t：30 捆包 + 29 一号重废 + 19 二号重废 + 2 DRI + 2 车屑）：
    #   模拟器 Ni 0.119 = 加权值 0.1191，说明 Ni 在熔化期完全不损失。
    # 原 0.45 会把 Ni 算低一半以上，导致推荐出实际超标的配料（Ni 上限仅 0.085）。
    "C": 0.90, "Si": 0.60, "Mn": 0.85, "P": 0.37, "S": 1.00,
    "Cr": 0.35, "Mo": 1.00, "Ni": 1.00, "Cu": 1.00, "N": 1.00,
    "Nb": 0.90, "Ti": 0.60, "V": 0.85, "Al": 0.50, "B": 0.70,
    "Ca": 0.20, "Pb": 1.00, "Sn": 0.90, "W": 1.00, "Ce": 0.10,
}

# 参与配料硬约束（可被 EAF 精炼去除或由合金补加调整的元素不在此列）
CHARGE_HARD_ELEMENTS = ["P", "S", "Cr", "Mo", "Ni", "Cu", "N", "Nb", "Ti", "Sn", "Pb", "As", "W", "Ca"]


def empty_comp():
    return {e: 0.0 for e in ELEMENTS}


def mix_totals(mix):
    total = sum(max(0.0, v) for v in mix.values())
    vol = sum(max(0.0, v) / SCRAP_BY_KEY[k]["density"] for k, v in mix.items() if k in SCRAP_BY_KEY)
    cost = sum(max(0.0, v) * SCRAP_BY_KEY[k]["price"] for k, v in mix.items() if k in SCRAP_BY_KEY)
    return total, vol, cost


def mix_composition(mix, retention=None):
    """返回 (原始成分, -5%波动, +5%波动)；retention 不为空时返回熔炼后成分。

    粉末料（电炉除尘灰）的 comp_scale < 1：未进入熔池的那部分既不贡献成分，
    也不计入成分基准质量。2026-11-17 已用模拟器「步骤1」面板反推校准。
    """
    _, _, _ = mix_totals(mix)
    total = 0.0
    for k, m in mix.items():
        if k not in SCRAP_BY_KEY or m <= 0:
            continue
        total += m * SCRAP_BY_KEY[k].get("comp_scale", 1.0)
    if total <= 1e-9:
        return empty_comp(), empty_comp(), empty_comp()
    comp = empty_comp()
    low = empty_comp()
    high = empty_comp()
    retention = retention or {}
    for k, m in mix.items():
        if k not in SCRAP_BY_KEY or m <= 0:
            continue
        s = SCRAP_BY_KEY[k]
        eff = m * s.get("comp_scale", 1.0)
        for e in ELEMENTS:
            c = s["comp"].get(e, 0.0)
            if c:
                r = retention.get(e, 1.0)
                comp[e] += eff * c * r
                low[e] += eff * c * r * 0.95
                high[e] += eff * c * r * 1.05
    for e in ELEMENTS:
        comp[e] /= total
        low[e] /= total
        high[e] /= total
    comp["Fe"] = max(0.0, 100.0 - sum(comp[e] for e in ELEMENTS))
    return comp, low, high


def _specs(grade_key, specs_override=None):
    if specs_override:
        return specs_override
    return EAF_GRADES[grade_key]["specs"]


def _material_keys(mass_t, material_limits):
    keys, bounds = [], []
    for s in SCRAPS:
        k = s["key"]
        lim = (material_limits or {}).get(k, {})
        if lim.get("enabled", True) is False:
            continue
        hi = lim.get("max", mass_t)
        hi = min(float(hi), mass_t) if hi is not None else mass_t
        lo = float(lim.get("min", 0.0) or 0.0)
        if hi <= 1e-6:
            continue
        lo = min(lo, hi)
        keys.append(k)
        bounds.append((lo, hi))
    return keys, bounds


def optimize_charge(grade_key, mass_t=82.0, material_limits=None, volume_limit=100.0,
                    enforce_min=False, carbon_cap=None, retention=None, soft=True,
                    specs_override=None, margin=0.0, objective_credit=None):
    """最小成本配料（约束作用于熔炼后成分）。

    soft=True 时，元素上限带松弛变量：无解时返回“最低可达”的方案并标出超标量，
    而不是直接报不可行。体积与总质量始终为硬约束。
    """
    if material_limits is None:
        # 赛题「工厂情况」带来的原料限量（2026 学生级：1 号打包块每炉最多 30 t）
        material_limits = (EAF_GRADES.get(grade_key) or {}).get("material_limits")
    specs = _specs(grade_key, specs_override)
    lp_specs = specs
    if margin and margin > 0:
        lp_specs = {}
        for e, (lo, hi) in specs.items():
            lp_specs[e] = [None if lo is None else lo * (1 + margin),
                           None if hi is None else hi * (1 - margin)]
    retention = {**MELT_RETENTION, **(retention or {})}
    keys, bounds = _material_keys(mass_t, material_limits)
    if not keys:
        return {"status": "infeasible", "message": "没有可用废钢"}

    n = len(keys)
    hard = [e for e in CHARGE_HARD_ELEMENTS
            if e in lp_specs and lp_specs[e][1] is not None]
    # 整炉规划会给 EAF 传入“二次精炼进站上限”（specs_override）；
    # Mn 正常可由合金补加，但上限无法靠合金降低，因此有 override 时按硬约束处理。
    if specs_override and "Mn" in lp_specs and lp_specs["Mn"][1] is not None and "Mn" not in hard:
        hard.append("Mn")
    n_soft = len(hard) if soft else 0
    nt = n + n_soft

    def _eff_price(k):
        """废钢有效价格：扣除其 Mn/Cr/Si 对后续合金成本的替代价值（$/t）。"""
        price = SCRAP_BY_KEY[k]["price"]
        if objective_credit:
            comp = SCRAP_BY_KEY[k]["comp"]
            for e, credit in objective_credit.items():
                price -= float(credit) * comp.get(e, 0.0)
        return price

    c = [_eff_price(k) for k in keys] + [100000.0] * n_soft
    A_eq = [[1.0] * n + [0.0] * n_soft]
    b_eq = [float(mass_t)]
    A_ub, b_ub = [], []

    # 元素上限：Σ x_i*c_i*r_e - slack_e <= max_e*Σx
    for si, e in enumerate(hard):
        hi = lp_specs[e][1]
        r = retention.get(e, 1.0)
        row = [SCRAP_BY_KEY[k].get("comp_scale", 1.0)
               * (SCRAP_BY_KEY[k]["comp"].get(e, 0.0) * r - hi) for k in keys]
        if max(row) <= 1e-12:
            continue
        if soft:
            row = row + [(-1.0 if j == si else 0.0) for j in range(n_soft)]
        A_ub.append(row)
        b_ub.append(0.0)
    if enforce_min:
        for e, (lo, hi) in lp_specs.items():
            if lo is None or lo <= 0:
                continue
            r = retention.get(e, 1.0)
            row = [SCRAP_BY_KEY[k].get("comp_scale", 1.0)
                   * (lo - SCRAP_BY_KEY[k]["comp"].get(e, 0.0) * r) for k in keys] + [0.0] * n_soft
            A_ub.append(row)
            b_ub.append(0.0)
    # 体积
    A_ub.append([1.0 / SCRAP_BY_KEY[k]["density"] for k in keys] + [0.0] * n_soft)
    # 预留 0.1 m³，抵消 0.1 t 取整带来的体积上浮
    b_ub.append(max(0.0, float(volume_limit) - 0.1))
    # 可选碳上限——口径是**入炉碳**（等于模拟器「步骤1」面板显示值），不乘收得率。
    # 碳在炉内靠吹氧脱除，不受这里的收得率约束；若乘 0.9，实际入炉碳会高出 11%。
    if carbon_cap is not None:
        A_ub.append([SCRAP_BY_KEY[k].get("comp_scale", 1.0)
                     * (SCRAP_BY_KEY[k]["comp"].get("C", 0.0) - float(carbon_cap)) for k in keys]
                    + [0.0] * n_soft)
        b_ub.append(0.0)
    # 单料下限
    for idx, k in enumerate(keys):
        lo = bounds[idx][0]
        if lo > 1e-9:
            row = [0.0] * nt
            row[idx] = -1.0
            A_ub.append(row)
            b_ub.append(-lo)

    res = minimize(c, A_ub, b_ub, A_eq, b_eq, bounds + [(0.0, None)] * n_soft)
    if res.status != "optimal":
        return {
            "status": res.status,
            "message": "无可行配料方案" if res.status == "infeasible" else res.message,
            "diagnosis": diagnose(grade_key, mass_t, material_limits, volume_limit, retention,
                                   lp_specs if margin else specs_override),
        }

    # 取整到 0.1 t：先向下取整，再把余量给“成分压力最小”的料
    floors = {}
    for k, v in zip(keys, res.x[:n]):
        if v >= 0.05:
            floors[k] = int(v * 10 + 1e-9) / 10.0
    surplus = round(mass_t - sum(floors.values()), 1)
    mix = dict(floors)
    if surplus > 1e-9:
        best, best_score = None, None
        for k in keys:
            trial = dict(mix)
            trial[k] = round(trial.get(k, 0.0) + surplus, 1)
            score = _violation_score(trial, grade_key, retention, specs_override)
            if best_score is None or score < best_score - 1e-12:
                best, best_score = k, score
        if best:
            mix[best] = round(mix.get(best, 0.0) + surplus, 1)
    mix = {k: v for k, v in mix.items() if v > 0}

    out = evaluate_mix(mix, grade_key, volume_limit, retention, specs_override)
    # 松弛量（%·t）换算成百分比
    if soft:
        slack = {"%s" % hard[i]: round(res.x[n + i] / mass_t, 4)
                 for i in range(n_soft) if res.x[n + i] > 1e-4}
        out["slack"] = slack
    return out


def _violation_score(mix, grade_key, retention, specs_override=None):
    comp, _, _ = mix_composition(mix, retention)
    specs = _specs(grade_key, specs_override)
    score = 0.0
    for e in CHARGE_HARD_ELEMENTS:
        if e not in specs or specs[e][1] is None:
            continue
        hi = specs[e][1]
        over = comp.get(e, 0.0) - hi
        if over > 0:
            score += over / max(hi, 1e-6) * 100
    return score


def evaluate_mix(mix, grade_key, volume_limit=100.0, retention=None, specs_override=None):
    specs = _specs(grade_key, specs_override)
    retention = {**MELT_RETENTION, **(retention or {})}
    total, vol, cost = mix_totals(mix)
    raw, _, _ = mix_composition(mix, None)
    comp, low, high = mix_composition(mix, retention)

    checks, warnings, need_alloy, violations = [], [], [], []
    for e, (lo, hi) in specs.items():
        val = comp.get(e, 0.0)
        adjustable = e not in CHARGE_HARD_ELEMENTS
        if hi is not None:
            if val > hi + 1e-6:
                if adjustable:
                    status = "adjust"
                    warnings.append(f"{e} 熔炼后 {val:.4f}% 高于目标 {hi:.4f}%：需吹氧/合金调整")
                else:
                    status = "fail"
                    warnings.append(f"{e} 熔炼后 {val:.4f}% 超上限 {hi:.4f}%")
                    violations.append({"element": e, "value": round(val, 4), "limit": hi,
                                       "excess": round(val - hi, 4)})
            elif high.get(e, 0) > hi + 1e-6 and e not in ("C", "Si", "Mn"):
                # C/Si/Mn 在熔化、吹氧和合金阶段会主动调整，不用 ±5% 废钢波动来预警
                status = "risk"
                warnings.append(f"{e} 均值合格，但 +5% 废钢波动可能超限（{high.get(e):.4f}% > {hi}%）")
            else:
                status = "pass"
        else:
            status = "pass"
        if lo is not None and val < lo - 1e-9:
            need_alloy.append({"element": e, "current": round(val, 4), "target_min": lo,
                               "gap": round(lo - val, 4)})
            if status == "pass":
                status = "low"
        checks.append({"element": e, "min": lo, "max": hi, "value": round(val, 4),
                       "raw": round(raw.get(e, 0), 4),
                       "low": round(low.get(e, 0), 4), "high": round(high.get(e, 0), 4),
                       "status": status})

    items = []
    for k, m in sorted(mix.items(), key=lambda kv: -kv[1]):
        if m <= 0:
            continue
        s = SCRAP_BY_KEY[k]
        items.append({"key": k, "name": s["name"], "form": s["form"], "mass": round(m, 2),
                      "share": round(m / total * 100, 2) if total else 0,
                      "volume": round(m / s["density"], 2), "price": s["price"],
                      "cost": round(m * s["price"], 1), "density": s["density"]})

    return {
        "status": "ok", "grade": grade_key,
        "mix": {k: round(v, 2) for k, v in mix.items() if v > 0},
        "items": items,
        "total_mass": round(total, 2),
        "volume": round(vol, 2), "volume_limit": volume_limit,
        "cost": round(cost, 1),
        "cost_per_t": round(cost / total, 2) if total else 0,
        "composition": {e: round(comp.get(e, 0), 4) for e in ELEMENTS if comp.get(e, 0) > 0},
        "raw_composition": {e: round(raw.get(e, 0), 4) for e in ELEMENTS if raw.get(e, 0) > 0},
        "checks": checks, "warnings": warnings, "need_alloy": need_alloy,
        "violations": violations,
        "baskets": plan_baskets(mix),
        "retention": retention,
    }


def diagnose(grade_key, mass_t, material_limits, volume_limit, retention, specs_override=None):
    specs = _specs(grade_key, specs_override)
    keys, bounds = _material_keys(mass_t, material_limits)
    if not keys:
        return []
    n = len(keys)
    A_ub = [[1.0 / SCRAP_BY_KEY[k]["density"] for k in keys]]
    b_ub = [volume_limit]
    issues = []
    for e, (lo, hi) in specs.items():
        if hi is None:
            continue
        r = retention.get(e, 1.0)
        cvec = [SCRAP_BY_KEY[k]["comp"].get(e, 0.0) * r for k in keys]
        res = minimize(cvec, A_ub, b_ub, [[1.0] * n], [mass_t], bounds)
        if res.status == "optimal":
            minv = sum(res.x[i] * cvec[i] for i in range(n)) / mass_t
            if minv > hi + 1e-6:
                issues.append({"element": e, "type": "max", "achievable_min": round(minv, 4),
                               "limit": hi,
                               "message": f"即使全部用最低{e}料，熔炼后 {e} 仍为 {minv:.4f}%（上限 {hi}%）"})
    cvol = [1.0 / SCRAP_BY_KEY[k]["density"] for k in keys]
    rv = minimize(cvol, [], [], [[1.0] * n], [mass_t], bounds)
    if rv.status == "optimal":
        mv = sum(rv.x[i] * cvol[i] for i in range(n))
        if mv > volume_limit + 1e-6:
            issues.append({"element": "体积", "type": "volume", "achievable_min": round(mv, 1),
                           "limit": volume_limit,
                           "message": f"最密配料体积仍需 {mv:.1f} m³（上限 {volume_limit} m³）"})
    return issues


def _integer_baskets(mix):
    """整吨装料时的料斗分配：按 DRI/炉尘优先、单斗 ≤40 m³ 贪心装。"""
    order = ["dri", "eaf_dust", "no1_heavy", "no2_heavy", "plate_structural",
             "internal_low_alloy", "shredded", "no1_bundle", "no2_bundle", "turnings"]
    left = {k: int(round(v)) for k, v in mix.items() if v > 0}
    baskets = []
    while sum(left.values()) > 0 and len(baskets) < 3:
        items, mass, vol = [], 0.0, 0.0
        while vol < 39.9:
            moved = False
            for k in order:
                if left.get(k, 0) <= 0:
                    continue
                s = SCRAP_BY_KEY[k]
                cap = 40.0 - vol
                can = min(left[k], int(cap * s["density"]))
                if can < 1:
                    continue
                left[k] -= can
                mass += can
                vol += can / s["density"]
                items.append({"key": k, "name": s["name"], "mass": can,
                              "volume": round(can / s["density"], 1), "form": s["form"]})
                moved = True
                if vol >= 39.9:
                    break
            if not moved:
                break
        if not items:
            break
        # 合并同料
        merged = {}
        for it in items:
            cur = merged.get(it["key"])
            if cur:
                cur["mass"] += it["mass"]
                cur["volume"] = round(cur["volume"] + it["volume"], 1)
            else:
                merged[it["key"]] = dict(it)
        items = list(merged.values())
        mass = sum(x["mass"] for x in items)
        vol = sum(x["volume"] for x in items)
        coarse = sum(x["mass"] for x in items if x["form"] == "CS")
        baskets.append({"index": len(baskets) + 1, "items": items,
                        "mass": round(mass, 1), "volume": round(vol, 1),
                        "coarse_share": round(coarse / mass * 100, 1) if mass else 0})
    return baskets


def plan_baskets(mix):
    """三料斗分配：按体积等分，单斗 ≤40 m³，粗废料质量占比 ≤30%。

    等比例分配可以保证每个料斗的粗废料占比与总混料一致；
    若总粗料占比本身超过 30%，任何分配都无法满足，只给出警告。
    """
    BASKET_VOL = 40.0
    total_mass, total_vol, _ = mix_totals(mix)
    warnings = []
    if total_mass <= 1e-6:
        return {"baskets": [], "warnings": [], "total_volume": 0, "total_mass": 0}

    n = max(1, min(3, int(math.ceil(total_vol / BASKET_VOL - 1e-9))))
    if total_vol > 3 * BASKET_VOL + 1e-6:
        warnings.append(f"总容积 {total_vol:.1f} m³ 超过 3×40 m³，无法装完")
    coarse_total = sum(m for k, m in mix.items() if SCRAP_BY_KEY[k]["form"] == "CS")
    coarse_share = coarse_total / total_mass * 100
    if coarse_share > 30.01:
        warnings.append(f"总粗废料占比 {coarse_share:.1f}% 超过 30%，需减少粗废料")

    # 整吨装料：用整数料斗分配，避免出现 10.5 t 这种模拟器填不进去的数
    if all(abs(float(v) - round(float(v))) < 1e-6 for v in mix.values()):
        return {"baskets": _integer_baskets(mix), "warnings": warnings,
                "total_volume": round(total_vol, 2), "total_mass": round(total_mass, 2)}

    baskets = []
    for i in range(n):
        items = []
        bm = bv = bc = 0.0
        for k, m in sorted(mix.items(), key=lambda kv: -kv[1]):
            if m <= 1e-9:
                continue
            part = m / n
            s = SCRAP_BY_KEY[k]
            items.append({"key": k, "name": s["name"], "mass": round(part, 2),
                          "volume": round(part / s["density"], 2), "form": s["form"]})
            bm += part
            bv += part / s["density"]
            if s["form"] == "CS":
                bc += part
        baskets.append({"index": i + 1, "items": items, "mass": round(bm, 2),
                        "volume": round(bv, 2),
                        "coarse_share": round(bc / bm * 100, 1) if bm else 0})
    return {"baskets": baskets, "warnings": warnings,
            "total_volume": round(total_vol, 2), "total_mass": round(total_mass, 2)}
