# -*- coding: utf-8 -*-
"""合金补加计算：母合金、回收率、元素夹带、迭代收敛。"""

from .data import ELEMENT_CN

# 先加合金元素，最后用增碳剂微调 C（避免碳被反复抬升）
ORDER = ["Cr", "Mn", "Mo", "Ni", "Nb", "Ti", "V", "Al", "B", "Ca", "Si", "C", "S", "P"]

# 现场加料先后：难熔/大宗先，脱氧剂最后（加早了会被氧烧掉）
_ADD_ORDER = (
    ("铬铁", 0), ("钼铁", 1), ("镍铁", 1), ("铌铁", 1), ("钒铁", 1), ("钛铁", 1),
    ("锰铁", 2), ("硅锰", 3), ("硅铁", 4), ("硅钙", 4), ("硅碳", 4),
    ("增碳剂", 5), ("硼铁", 6), ("铝", 7),
)


def add_sequence(rows):
    """按现场加料顺序返回合金名列表（输入 alloy_rows，含 name 字段）。"""
    def key(row):
        name = str(row.get("name", ""))
        for pat, rank in _ADD_ORDER:
            if pat in name:
                return rank
        return 8
    return [r.get("name", "") for r in sorted(rows, key=key) if r.get("name")]


def _rec(profile, e):
    return float(profile.get(e, 100.0)) / 100.0


def _candidates(catalog, element, forbidden, preferred):
    out = []
    for a in catalog:
        if a.get("flux"):
            continue
        if a["key"] in forbidden:
            continue
        if a["comp"].get(element, 0.0) <= 0:
            continue
        out.append(a)
    if preferred:
        picked = [a for a in out if a["key"] == preferred]
        if picked:
            return picked
    return out


def _score(a, element, profile):
    c = a["comp"].get(element, 0.0)
    r = _rec(profile, element)
    return a["price"] / (10.0 * c * r)  # $/kg 元素


def _apply(comp, mass, m, a, profile, elements):
    """向 mass kg 钢液加入 m kg 添加剂，返回新 (comp, mass)。"""
    new_mass = mass + m
    new = {}
    for e in elements:
        old_kg = comp.get(e, 0.0) / 100.0 * mass
        added_kg = m * a["comp"].get(e, 0.0) / 100.0 * _rec(profile, e)
        new[e] = (old_kg + added_kg) / new_mass * 100.0
    return new, new_mass


def _trial(comp, mass, m, a, profile, elements):
    new_mass = mass + m
    out = {}
    for e in elements:
        old_kg = comp.get(e, 0.0) / 100.0 * mass
        add_kg = m * a["comp"].get(e, 0.0) / 100.0 * _rec(profile, e)
        out[e] = (old_kg + add_kg) / new_mass * 100.0
    return out


def calculate_additions(mass_t, initial, targets, catalog, profile,
                        limits=None, forbidden=None, preferred=None,
                        max_kg=None, max_passes=1):
    """迭代计算合金补加量。

    mass_t: 钢水质量（吨）
    initial: 初始成分 {元素: wt%}
    targets: 目标成分 {元素: wt%}
    catalog: 添加剂列表
    profile: 回收率表（元素 -> %）
    limits: 成分上下限 {元素: [min,max]}，用于拒绝会超限的添加剂
    preferred: {元素: additive_key} 指定使用某种添加剂
    max_kg: {additive_key: 最大添加量 kg}
    """
    forbidden = set(forbidden or [])
    preferred = preferred or {}
    limits = limits or {}
    max_kg = max_kg or {}
    elements = set(initial) | set(targets)
    for a in catalog:
        elements |= set(a["comp"].keys())
    elements = [e for e in elements if e in ELEMENT_CN]

    comp = {e: float(initial.get(e, 0.0)) for e in elements}
    mass = float(mass_t) * 1000.0
    totals = {}
    warnings, unmet = [], []

    for _pass in range(max_passes):
        changed = False
        for e in ORDER:
            if e not in targets or targets[e] is None:
                continue
            target = float(targets[e])
            delta = target - comp.get(e, 0.0)
            if delta <= max(0.0005, abs(target) * 0.01):
                continue
            cands = _candidates(catalog, e, forbidden, preferred.get(e))
            if not cands:
                unmet.append({"element": e, "reason": "无可用添加剂"})
                continue
            cands.sort(key=lambda a: _score(a, e, profile))

            chosen, chosen_m, best_over = None, 0.0, None
            for a in cands:
                c_e = a["comp"].get(e, 0.0)
                rec = _rec(profile, e)
                m = delta * mass / (c_e * rec)
                if a["key"] in max_kg:
                    remain = max_kg[a["key"]] - totals.get(a["key"], {}).get("mass", 0.0)
                    if remain <= 1e-6:
                        continue
                    m = min(m, remain)
                if m <= 1e-9:
                    continue
                trial_comp = _trial(comp, mass, m, a, profile, elements)
                over = 0.0
                for ee, (lo, hi) in limits.items():
                    if hi is not None and trial_comp.get(ee, 0.0) > hi:
                        over += (trial_comp[ee] - hi) / max(hi, 1e-6)
                if over <= 0:
                    chosen, chosen_m, best_over = a, m, 0.0
                    break
                if best_over is None or over < best_over:
                    best_over, chosen, chosen_m = over, a, m
            if chosen is None:
                unmet.append({"element": e, "reason": "无可用的不超限添加剂"})
                continue
            if best_over is not None and best_over > 0:
                warnings.append(f"{e} 目标 {target}% 无法在不超限条件下达到，已按最小超标方案添加")

            m = chosen_m
            comp, mass = _apply(comp, mass, m, chosen, profile, elements)
            t = totals.setdefault(chosen["key"], {"key": chosen["key"], "name": chosen["name"],
                                                  "mass": 0.0, "cost": 0.0, "elements": {}})
            t["mass"] += m
            t["cost"] += m / 1000.0 * chosen["price"]
            for ee, cv in chosen["comp"].items():
                t["elements"][ee] = round(t["elements"].get(ee, 0.0)
                                          + m * cv / 100.0 * _rec(profile, ee), 2)
            changed = True
        if not changed:
            break

    additions = [{"key": t["key"], "name": t["name"], "mass": round(t["mass"], 1),
                  "cost": round(t["cost"], 1), "elements": t["elements"]}
                 for t in totals.values()]
    additions.sort(key=lambda x: -x["mass"])
    final = {e: round(v, 4) for e, v in comp.items() if v > 0.00001}
    total_added = sum(a["mass"] for a in additions)
    cost = sum(a["cost"] for a in additions)

    warn = list(warnings)
    for e, (lo, hi) in limits.items():
        v = final.get(e, 0.0)
        if hi is not None and v > hi + 0.002:
            warn.append(f"最终 {e} = {v:.4f}% 超上限 {hi}%")
    for e, tv in targets.items():
        if tv is None:
            continue
        if abs(final.get(e, 0.0) - float(tv)) > max(0.004, abs(float(tv)) * 0.05):
            if not any(u["element"] == e for u in unmet):
                unmet.append({"element": e,
                              "reason": f"实际 {final.get(e, 0):.4f}% / 目标 {tv}%"})

    return {
        "status": "ok",
        "mass_before": round(mass_t, 2),
        "mass_after": round(mass / 1000.0, 3),
        "additions": additions,
        "added_total": round(total_added, 1),
        "cost": round(cost, 1),
        "cost_per_t": round(cost / (mass / 1000.0), 2) if mass else 0,
        "temperature_drop": round(total_added / 1000.0 * 6.0, 1),
        "final": final,
        "unmet": unmet,
        "warnings": warn,
    }
