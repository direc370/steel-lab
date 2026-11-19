# -*- coding: utf-8 -*-
"""分步操作向导：把配料、合金、精炼串成一条可执行的时间线。

设计原则（按实际模拟器输入粒度）：
- 炉料只按整吨装入（EAF 上限 90 t）；
- 所有添加剂、熔剂只按 10 kg 一档加入；
- 每一步都给出“什么时候、做什么、加多少、看什么、什么时候停”。

EAF 与二次精炼是两条独立流程，但 EAF 的最终成分可以直接带入二次精炼。
"""

from .alloy_lp import optimize_alloy_lp, MAX_KG
from .alloys import add_sequence
from .charge import optimize_charge, evaluate_mix, MELT_RETENTION, plan_baskets
from .refine import slag_calculator
from .data import (
    EAF_ADDITIVES, SM_ADDITIVES, EAF_ADDITIVE_BY_KEY, SM_ADDITIVE_BY_KEY,
    EAF_GRADES, SM_GRADES, RECOVERY, SCRAP_BY_KEY, default_pre_c,
)
from .optimizer import optimize_total
from . import refine as R


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def _profile(name):
    return {k: float(v) / 100.0 for k, v in RECOVERY[name].items() if k != "label"}


def _catalog(track):
    return SM_ADDITIVES if track == "sm" else EAF_ADDITIVES


def _by_key(track):
    return SM_ADDITIVE_BY_KEY if track == "sm" else EAF_ADDITIVE_BY_KEY


def _round_step(x, step=10):
    if x <= 0:
        return 0
    return int(round(float(x) / step)) * step


def _t(minutes):
    """把分钟数格式化成 HH:MM。"""
    m = int(round(float(minutes)))
    return f"{m // 60:02d}:{m % 60:02d}"


def _fmt_range(pair, digits=2):
    """把 [下限, 上限] 规格格式化成可读文本。"""
    if not pair:
        return "—"
    lo, hi = pair
    if lo is None and hi is None:
        return "—"
    if lo is None:
        return f"≤{float(hi):.{digits}f}%"
    if hi is None:
        return f"≥{float(lo):.{digits}f}%"
    return f"{float(lo):.{digits}f}–{float(hi):.{digits}f}%"


def _eval_plan(mass_t, initial, plan, track="eaf", profile=None):
    """按 kg 计划核算最终成分、质量与成本。"""
    cat = _by_key(track)
    rec = _profile(profile or ("ladle" if track == "sm" else "eaf_cal"))
    mass_kg = float(mass_t) * 1000.0
    comp = {}
    for e, v in (initial or {}).items():
        comp[e] = float(v) / 100.0 * mass_kg
    cost = 0.0
    for key, kg in plan.items():
        a = cat.get(key)
        if not a or not kg:
            continue
        cost += kg * float(a["price"]) / 1000.0
        mass_kg += kg
        for e, pct in a["comp"].items():
            comp[e] = comp.get(e, 0.0) + kg * float(pct) / 100.0 * rec.get(e, 1.0)
    final = {e: v / mass_kg * 100.0 for e, v in comp.items()}
    return {
        "mass_after": round(mass_kg / 1000.0, 3),
        "final": {e: round(v, 4) for e, v in final.items()},
        "cost": round(cost, 1),
        "added_total": round(sum(plan.values()), 1),
    }


def _out_of_spec(final, specs):
    out = []
    for e, (lo, hi) in specs.items():
        v = final.get(e)
        if v is None:
            continue
        if lo is not None and v < lo - 1e-4:
            out.append(f"{e} {v:.4f}% 低于下限 {lo}%")
        if hi is not None and v > hi + 1e-4:
            out.append(f"{e} {v:.4f}% 高于上限 {hi}%")
    return out


def _score(final, specs):
    """越小越好：惩罚越限。"""
    s = 0.0
    for e, (lo, hi) in specs.items():
        v = final.get(e)
        if v is None:
            continue
        if lo is not None and v < lo - 1e-6:
            s += (lo - v) / max(abs(lo), 0.002) * 100.0 + 1.0
        if hi is not None and v > hi + 1e-6:
            s += (v - hi) / max(abs(hi), 0.002) * 100.0 + 1.0
    return s


def round_plan(mass_t, initial, plan, specs, track="eaf", profile=None, step=10,
               repair=True, margin=None):
    """把连续 LP 结果取整到 10 kg，并做成本感知的局部搜索（0 越限 + 最低成本）。"""
    m_ratio = 0.10 if margin is None else max(0.0, min(0.35, float(margin) * 0.6))
    score_specs = {}
    for e, (lo, hi) in specs.items():
        if e in ("C", "Si", "Mn", "Cr", "Mo") and lo is not None and hi is not None:
            span = hi - lo
            lo_m = lo + span * m_ratio
            hi_m = hi - span * m_ratio
            v0 = (initial or {}).get(e)
            if v0 is not None and float(lo) - 1e-9 <= float(v0) <= float(hi) + 1e-9:
                lo_m = min(lo_m, float(v0))
            if v0 is not None and float(v0) > hi_m:
                hi_m = float(v0)
            score_specs[e] = [lo_m, hi_m]
        else:
            score_specs[e] = [lo, hi]
    cat = _by_key(track)
    adds = [a for a in _catalog(track) if not a.get("flux")]
    cur = {}
    for a in adds:
        kg = _round_step(plan.get(a["key"], 0.0), step)
        if kg > 0:
            cur[a["key"]] = kg

    def obj(trial):
        ev_t = _eval_plan(mass_t, initial, trial, track, profile)
        hard = _score(ev_t["final"], specs)
        soft = _score(ev_t["final"], score_specs)
        # 严格优先满足 specs 硬窗口，其次满足安全余量窗口，最后最小化合金成本
        return (round(hard, 6), round(soft, 6), round(ev_t["cost"], 2)), ev_t

    best = dict(cur)
    best_key, ev = obj(best)
    limits = {a["key"]: float(MAX_KG.get(a["key"], 5000.0)) for a in adds}
    for _ in range(0 if not repair else 60):
        cand_best = None
        for a in adds:
            k = a["key"]
            base = best.get(k, 0)
            for d in (-2 * step, -step, step, 2 * step):
                nv = base + d
                if nv < 0 or nv > limits.get(k, 5000.0):
                    continue
                trial = dict(best)
                if nv == 0:
                    trial.pop(k, None)
                else:
                    trial[k] = nv
                key_t, _ = obj(trial)
                if key_t < best_key and (cand_best is None or key_t < cand_best[0]):
                    cand_best = (key_t, trial)
        # 尝试等量替换（如用便宜的高碳锰铁替换低碳锰铁，或硅锰替换硅铁+锰铁）
        active_keys = [k for k, v in best.items() if v >= step]
        for k_from in active_keys:
            for a_to in adds:
                k_to = a_to["key"]
                if k_to == k_from:
                    continue
                if best.get(k_to, 0) + step > limits.get(k_to, 5000.0):
                    continue
                trial = dict(best)
                trial[k_from] -= step
                if trial[k_from] <= 0:
                    trial.pop(k_from, None)
                trial[k_to] = trial.get(k_to, 0) + step
                key_t, _ = obj(trial)
                if key_t < best_key and (cand_best is None or key_t < cand_best[0]):
                    cand_best = (key_t, trial)
        if cand_best:
            best_key, best = cand_best
        else:
            break

    ev = _eval_plan(mass_t, initial, best, track, profile)
    out = _out_of_spec(ev["final"], specs)
    return {
        "plan": best,
        "additions": [
            {"key": k, "name": cat[k]["name"], "mass": v,
             "cost": round(v * float(cat[k]["price"]) / 1000.0, 1),
             "elements": {e: round(float(pct) * v / 100.0, 2)
                          for e, pct in cat[k]["comp"].items()}}
            for k, v in sorted(best.items(), key=lambda kv: -kv[1])
        ],
        "mass_after": ev["mass_after"],
        "final": ev["final"],
        "cost": ev["cost"],
        "added_total": ev["added_total"],
        "out_of_spec": out,
        "temperature_drop": round(ev["added_total"] / 1000.0 * 6.0, 1),
    }


# ---------------------------------------------------------------------------
# 炉料取整与料斗
# ---------------------------------------------------------------------------

def round_charge_mix(mix, mass_t, grade_key, retention=None, volume_limit=100.0,
                     allowed=None, limits=None, credit=None, preserve=False):
    """把 LP 的小数配比取整到整吨，并做 1 t 级成本感知局部修正。

    allowed：允许使用的废钢 key 集合；给定时局部修正不会引入被禁用的料。
    limits：各废钢的上下限 {key: {"enabled": bool, "min": float, "max": float}}。
    credit：合金元素替代价值 {元素: $/kg}，用于在满足约束的前提下继续压低总成本。
    preserve：为 True 时只做整吨取整，不再做成本邻域搜索——用户手动设置的炉料
        方案必须原样保留，不能在“生成初始规划”时被优化成另一套料。
    """
    mass = int(round(float(mass_t)))
    items = [(k, float(v)) for k, v in (mix or {}).items() if v and v > 0]
    if not items:
        return {"status": "infeasible", "message": "配料为空"}
    floors = {k: int(v) for k, v in items}
    rem = mass - sum(floors.values())
    if rem > 0:
        order = sorted(items, key=lambda kv: (kv[1] - int(kv[1])), reverse=True)
        for i in range(rem):
            floors[order[i % len(order)][0]] += 1
    elif rem < 0:
        order = sorted(items, key=lambda kv: (kv[1] - int(kv[1])))
        for i in range(-rem):
            k = order[i % len(order)][0]
            if floors[k] > 0:
                floors[k] -= 1
    mix_int = {k: v for k, v in floors.items() if v > 0}
    limits = limits or {}
    credit = credit or {}

    def within_limits(m):
        for k, lim in limits.items():
            if not lim:
                continue
            val = m.get(k, 0)
            if not lim.get("enabled", True) and val > 0:
                return False
            if lim.get("max") is not None and val > float(lim["max"]) + 1e-6:
                return False
            if lim.get("min") is not None and val < float(lim["min"]) - 1e-6:
                return False
        return True

    def ev(m):
        return evaluate_mix(m, grade_key, volume_limit, retention)

    def eff_cost(r):
        cost = float(r.get("cost") or 0.0)
        if credit and r.get("composition"):
            tot_kg = float(r.get("total_mass") or mass) * 1000.0
            for el, val_per_kg in credit.items():
                cost -= float(r["composition"].get(el, 0.0)) / 100.0 * tot_kg * float(val_per_kg)
        return round(cost, 2)

    base = ev(mix_int)
    if preserve:
        # 用户手动指定的炉料：只取整，不再做 1 t 成本邻域搜索，确保初始规划与炉料页一致
        base["mix_int"] = mix_int
        base["integer_repair"] = False
        return base
    best = dict(mix_int)
    best_key = (round(_charge_score(base, volume_limit), 6), eff_cost(base))
    keys = list(best.keys()) + [k for k in SCRAP_BY_KEY if k not in best]
    if allowed is not None:
        keys = [k for k in keys if k in allowed]
    for _ in range(50):
        cand = None
        for donor in list(best.keys()):
            if best[donor] < 1:
                continue
            for recv in keys:
                if recv == donor:
                    continue
                trial = dict(best)
                trial[donor] -= 1
                trial[recv] = trial.get(recv, 0) + 1
                trial = {k: v for k, v in trial.items() if v > 0}
                if not within_limits(trial):
                    continue
                r = ev(trial)
                key_t = (round(_charge_score(r, volume_limit), 6), eff_cost(r))
                if key_t < best_key and (cand is None or key_t < cand[0]):
                    cand = (key_t, trial)
        if cand:
            best_key, best = cand
        else:
            break
    out = ev(best)
    out["mix_int"] = best
    out["integer_repair"] = True
    return out


def _charge_score(r, volume_limit):
    s = 0.0
    for v in r.get("violations") or []:
        s += 1000.0 + abs(float(v.get("excess", 0))) * 1000.0
    vol = float(r.get("volume") or 0)
    if vol > float(volume_limit):
        s += (vol - float(volume_limit)) * 100.0
    return s


def _baskets(mix_int):
    """按“先 DRI/炉尘、再重废/捆包”的顺序装斗，单斗 ≤40 m³。"""
    order = ["dri", "eaf_dust", "no1_heavy", "no2_heavy", "plate_structural",
             "internal_low_alloy", "shredded", "no1_bundle", "no2_bundle", "turnings"]
    left = {k: float(v) for k, v in mix_int.items() if v > 0}
    baskets = []
    for _ in range(3):
        if sum(left.values()) <= 1e-9:
            break
        items, mass, vol = [], 0.0, 0.0
        # 反复扫，直到这一斗装满或没有余料
        while vol < 39.9:
            moved = False
            for k in order:
                if left.get(k, 0) <= 1e-9:
                    continue
                s = SCRAP_BY_KEY[k]
                cap = 40.0 - vol
                can = min(left[k], cap * s["density"])
                if can <= 1e-9:
                    continue
                # 只装整吨；不足 1 t 的余料留到下一斗
                take = float(int(can))
                if take < 0.5:
                    continue
                left[k] -= take
                mass += take
                vol += take / s["density"]
                items.append({"key": k, "name": s["name"], "mass": round(take, 1),
                              "volume": round(take / s["density"], 1),
                              "form": s["form"]})
                moved = True
                if vol >= 39.9:
                    break
            if not moved:
                break
        if not items:
            break
        merged = {}
        for it in items:
            m = merged.get(it["key"])
            if m:
                m["mass"] = round(m["mass"] + it["mass"], 1)
                m["volume"] = round(m["volume"] + it["volume"], 1)
            else:
                merged[it["key"]] = dict(it)
        items = [x for x in merged.values() if x["mass"] >= 0.5]
        mass = sum(x["mass"] for x in items)
        vol = sum(x["volume"] for x in items)
        if not items:
            break
        coarse = sum(i["mass"] for i in items if i["form"] == "CS")
        baskets.append({
            "index": len(baskets) + 1, "items": items,
            "mass": round(mass, 1), "volume": round(vol, 1),
            "coarse_share": round(coarse / mass * 100.0, 1) if mass else 0.0,
        })
    return baskets


def _fluxes(mass_t, charge, target_feo=45.0, target_mgo=8.8):
    """EAF 渣料：按炉料 Si 氧化量 + DRI 脉石 SiO2 反算，一次加入。

    校准依据 实炉校准：90 t 炉料（68 t 1号捆包 + 21 t DRI + 1 t 炉尘）实际加入
    石灰 260+900=1160 kg、白云石 160+1250=1410 kg、萤石 50 kg，终渣碱度 1.698、
    MgO 8.186%、FeO 37.117%，全部合格。

    注意：FeO 会稀释 MgO。实炉出钢后 FeO 37%，但吹氧过程可到 45–50%；
    若仍按 FeO=37%、MgO=8.2% 配白云石，实际 MgO 会掉到 7% 左右。
    因此默认按 FeO=45%、MgO=8.8% 设计，保证 FeO 37–50% 时 MgO 仍在 8–12%。
    """
    mass = float(mass_t)
    mix = charge.get("mix_int") or charge.get("mix") or {}
    si_retained = float((charge.get("composition") or {}).get("Si", 0.05) or 0.05)
    si_ox_pct, gangue = R.charge_silica(mass, mix, si_retained)
    rec = R.slag_calculator(
        mass, si_ox_pct, 0.0, 0.0, 0.0,
        target_basicity=1.70, target_mgo=target_mgo, target_feo=target_feo,
        sio2_gangue_kg=gangue,
    ).get("recommend") or {}
    lime = _round_step(rec.get("lime_kg", 1160.0 * mass / 90.0))
    dolo = _round_step(rec.get("dolomite_kg", 1410.0 * mass / 90.0))
    # 氟石在模拟器里对碱度/MgO/FeO 无影响（实测验证），加了只花钱，默认 0。
    fluo = 0
    return [
        {"key": "lime", "name": "石灰", "mass": lime, "price": 120},
        {"key": "dolomite", "name": "白云石", "mass": dolo, "price": 120},
        {"key": "fluorspar", "name": "氟石", "mass": fluo, "price": 180},
    ]


def _oxygen(c0, c1, mass_t, flow=150.0, eff=0.45):
    dc = max(0.0, float(c0) - float(c1))
    c_kg = dc / 100.0 * float(mass_t) * 1000.0
    o2_kg = c_kg * 32.0 / 12.0
    nm3 = o2_kg / 1.429
    t = nm3 / max(flow, 1.0) / max(eff, 0.1)
    t = max(5.0, min(15.0, t))
    return {
        "c_kg": round(c_kg, 1), "o2_kg": round(o2_kg, 1),
        "nm3": round(nm3, 1), "time_min": round(t, 1),
        "flow": flow, "cost": round(t * flow * 0.10, 1),
    }


def _status_value(v, lo, hi):
    if v is None:
        return "—"
    if lo is not None and v < lo - 1e-4:
        return "low"
    if hi is not None and v > hi + 1e-4:
        return "high"
    return "ok"


def _checks(final, specs):
    rows = []
    for e, (lo, hi) in specs.items():
        if e not in final:
            continue
        rows.append({"element": e, "value": final[e], "min": lo, "max": hi,
                     "status": _status_value(final[e], lo, hi)})
    return rows


# ---------------------------------------------------------------------------
# EAF 流程
# ---------------------------------------------------------------------------

def eaf_plan(grade_key="sc21_engineering", mass_t=82, safe=True, power_kwh=None,
             mix_override=None, alloy_override=None, retention_override=None,
             pre_c=None, pre_si=0.05, other_cost_per_t=0.0, energy_price=0.57,
             alloy_pos=None, specs_override=None, flux_feo=45.0,
             alloy_specs_override=None):
    mass = int(round(float(mass_t)))
    grade = EAF_GRADES.get(grade_key)
    if not grade:
        return {"status": "error", "message": f"未知钢种：{grade_key}"}
    if pre_c is None:
        pre_c = default_pre_c(grade_key)
    # specs：EAF 自己的出钢规格，负责合规判定与页面显示
    # alloy_specs：仅用于合金补加的目标窗口（可把 EAF 便宜的元素往 SM 窗口推）
    specs = {e: list(v) for e, v in (specs_override or grade["specs"]).items()}
    alloy_specs = {e: list(v) for e, v in (alloy_specs_override or specs).items()}
    charge_margin = 0.06 if safe else 0.03
    alloy_margin = float(alloy_pos) if alloy_pos is not None else (0.4 if safe else 0.2)
    if alloy_specs_override:
        # 合金目标是故意收窄的窗口（例如 Mo 0.22–0.23%）。若再按 margin 收缩，
        # 窗口会比 10 kg 一个步长还窄，取整后必然越界、误判成无解。
        # 这里按「收缩后至少保留 1.2 个步长」反算 margin 上限。
        step_pct = 10.0 / max(mass * 1000.0, 1.0) * 100.0
        cap = 1.0
        for _e, (_lo, _hi) in alloy_specs.items():
            if _lo is None or _hi is None:
                continue
            _w = float(_hi) - float(_lo)
            if _w <= 1e-9:
                continue
            cap = min(cap, max(0.0, (_w - 1.2 * step_pct) / (2.0 * _w)))
        alloy_margin = min(alloy_margin, max(0.0, cap))
    ni_cal = 1.0  # 模拟器 Ni 不损失（2026-11-17 实测校准）

    if mix_override:
        # 用“炉料配比”页当前方案，不再重新优化
        retention = retention_override or None
        charge = round_charge_mix(mix_override, mass, grade_key, retention, preserve=True)
        if charge.get("status") != "ok":
            return {"status": "infeasible", "message": charge.get("message", "取整后配料无解")}
    else:
        total = optimize_total(grade_key, mass, charge_margin=charge_margin,
                               alloy_margin=alloy_margin, c_pre=pre_c, si_pre=pre_si,
                               ni_cal=ni_cal, round_tons=True, alloy_step=10,
                               specs_override=specs_override,
                               alloy_specs_override=alloy_specs_override)
        if total.get("status") != "ok":
            return {"status": "infeasible", "message": total.get("message", "联合优化无解")}
        best = total["best"]
        if total.get("exec") and total["exec"].get("charge", {}).get("status") == "ok":
            charge = total["exec"]["charge"]
            if total["exec"].get("c_pre") is not None:
                pre_c = total["exec"]["c_pre"]
        else:
            retention = None
            charge = round_charge_mix(best["charge"]["mix"], mass, grade_key, retention)
        if charge.get("status") != "ok":
            return {"status": "infeasible", "message": charge.get("message", "取整后配料无解")}

    init = dict(charge["composition"])
    init["C"] = float(pre_c)
    init["Si"] = float(pre_si)
    if alloy_override:
        plan0 = {k: float(v) for k, v in alloy_override.items() if float(v) > 0}
        rounded = round_plan(mass, init, plan0, alloy_specs, track="eaf", profile="eaf_cal",
                             repair=False)
    else:
        lp = optimize_alloy_lp(mass, init, alloy_specs, profile="eaf_cal", margin=alloy_margin)
        if lp.get("status") != "ok":
            return {"status": "infeasible", "message": lp.get("message", "合金 LP 无解")}
        plan0 = {a["key"]: a["mass"] for a in lp["additions"]}
        rounded = round_plan(mass, init, plan0, alloy_specs, track="eaf", profile="eaf_cal",
                             repair=True, margin=alloy_margin)

    fluxes = _fluxes(mass, charge, flux_feo)
    flux_cost = sum(x["mass"] * x["price"] / 1000.0 for x in fluxes)
    oxy = _oxygen(charge["composition"].get("C", 0.56), 0.375, mass)
    alloy_cost = rounded["cost"]
    scrap_cost = float(charge["cost"])
    tap_mass = rounded["mass_after"]
    # 模拟器成本口径：电耗 $0.57/kWh（EAF 手册 3.3），再加电极/耐材/人工等。
    # 其他成本取 $37/t：按 实炉校准 模拟器总成本 493.41 $/t 反算（材料+电约 415 $/t，
    # SM 合金约 41.6 $/t → EAF 其他约 37 $/t），避免用 45 $/t 时整体偏高约 $8/t。
    energy_kwh = float(power_kwh) if power_kwh else 380.0 * mass
    energy_cost = energy_kwh * float(energy_price)
    other_cost = float(other_cost_per_t) * tap_mass
    material_cost = scrap_cost + alloy_cost + flux_cost + oxy["cost"]
    subtotal = material_cost + energy_cost + other_cost
    total_per_t = subtotal / tap_mass if tap_mass else 0.0

    baskets = _baskets(charge["mix_int"])
    charge_rows = [{"name": i["name"], "mass": i["mass"], "volume": i["volume"],
                    "price": i["price"], "cost": i["cost"], "form": i["form"]}
                   for i in charge["items"]]
    alloy_rows = rounded["additions"]
    stop_lo, stop_hi = float(pre_c), float(pre_c) + 0.01
    eaf_c_txt = _fmt_range(specs.get("C"))
    eaf_mn_txt = _fmt_range(specs.get("Mn"))
    eaf_cr_txt = _fmt_range(specs.get("Cr"))

    steps = []
    # 1) 装料
    basket_lines = []
    for b in baskets:
        basket_lines.append({
            "name": f"第 {b['index']} 斗（{b['mass']:.0f} t / {b['volume']:.1f} m³）",
            "qty": " + ".join(f"{i['name']} {i['mass']:.0f} t" for i in b["items"]),
            "note": f"粗料 {b['coarse_share']:.0f}%",
        })
    steps.append({
        "id": "eaf-charge", "time": "00:00–00:05",
        "title": "装第 1 斗（按整吨）",
        "lead": f"目标钢种：{grade['name']}。炉料只能按整吨装，下面是取整后的装料单；总装入量 {mass} t。",
        "metrics": [
            {"k": "总装入量", "v": f"{charge['total_mass']:.0f} t"},
            {"k": "总体积", "v": f"{charge['volume']:.1f} m³"},
            {"k": "料斗数", "v": f"{len(baskets)} 斗"},
            {"k": "废钢成本", "v": f"${scrap_cost:,.0f}"},
        ],
        "adds": basket_lines[:1],
        "actions": [
            "第 1 斗先装 DRI、电炉炉尘和一部分 1 号捆包料；装完称重核对。",
            "第 2 斗装剩余 1 号捆包料；单斗体积不要超过 40 m³。",
            "装料期间记录实际装入量；如果某料少了 1 t，用 1 号捆包料补足总吨数。",
        ],
        "checks": [
            f"第 1 斗装入约 {baskets[0]['mass']:.0f} t（第 2 斗剩 {mass - baskets[0]['mass']:.0f} t）",
            f"装入总量必须 = {mass} t（模拟器只接受整吨）",
            f"总体积 ≤ 100 m³（当前 {charge['volume']:.1f} m³）",
            "粗废料质量占比 ≤ 30%",
        ],
        "tip": "不要把合金、石灰、白云石和废钢一起装进去；这些都要等熔清后再加。",
    })
    # 2) 熔化
    steps.append({
        "id": "eaf-melt", "time": "00:05–00:30",
        "title": "熔炼 + 装第 2 斗",
        "lead": "先用电弧把第 1 斗熔清，再装第 2 斗；目标是炉内无冷料堆、成分温度均匀。",
        "metrics": [
            {"k": "电弧功率", "v": "110–120 MW"},
            {"k": "目标熔清温度", "v": "1560–1580°C"},
            {"k": "第 2 斗装入", "v": "约第 25 分钟"},
            {"k": "第 2 斗重量", "v": f"{mass - baskets[0]['mass']:.0f} t"},
        ],
        "adds": basket_lines[1:],
        "actions": [
            "第 1 斗熔清后（约 15–20 min）降功率，装第 2 斗。",
            "第 2 斗装完恢复 110–120 MW，继续熔清。",
            "熔清后测温；低于 1560°C 继续加热 3–5 min。",
        ],
        "checks": ["炉料全部熔化，无结块", "温度 ≥ 1560°C", "电极不埋入冷料"],
        "warn": "合金、渣料都不要在这一步加；提前加会被未熔废钢和氧化渣吃掉。",
    })
    # 3) 造渣
    flux_lines = [{"name": x["name"], "qty": f"{x['mass']} kg", "note": f"${x['price']/1000:.2f}/kg"}
                  for x in fluxes]
    steps.append({
        "id": "eaf-flux", "time": "00:30–00:36",
        "title": f"一次加完全部渣料（石灰 {fluxes[0]['mass']} + 白云石 {fluxes[1]['mass']} + 氟石 {fluxes[2]['mass']} kg）",
        "lead": "熔清后把渣料一次全部加入，不再分两批。目标碱度 1.6–1.9、MgO 8–10%、FeO 30–40%；渣子发泡后电弧更稳定。",
        "metrics": [
            {"k": "目标碱度", "v": "1.6–1.9"},
            {"k": "目标 MgO", "v": "8–10%"},
            {"k": "目标 FeO", "v": "30–40%"},
            {"k": "渣料成本", "v": f"${flux_cost:,.0f}"},
        ],
        "adds": flux_lines,
        "actions": [
            "石灰、白云石、萤石一次全部加入，加完吹氧 1–2 min 让渣料化开。",
            "取渣样：碱度低于 1.5 补石灰 100–200 kg；MgO 低于 8% 补白云石 100–200 kg（10 kg 档）。",
            "渣子发干、弧光外露时开碳枪 10–20 kg/min，最多 1–2 min，不要长期开。",
        ],
        "checks": ["渣样碱度 1.6–1.9", "MgO 8–10%", "FeO 30–40%", "渣面发泡、弧光被埋住"],
        "tip": "渣料量按炉料 Si 氧化量 + DRI 脉石 SiO2 反算；如果换炉料，先回「EAF 造渣」页重算，不要照抄上一炉。",
    })
    # 4) 吹氧
    steps.append({
        "id": "eaf-blow", "time": "00:36–00:46",
        "title": "吹氧脱碳（碳枪 0）",
        "lead": f"把 C 从约 {charge['composition'].get('C', 0.56):.2f}% 吹到 {stop_lo:.2f}–{stop_hi:.2f}%。目标是给后面合金带入的 C 留余量，不是把碳吹得越低越好。",
        "metrics": [
            {"k": "氧气流量", "v": "150 Nm³/min"},
            {"k": "碳枪流量", "v": "0 kg/min"},
            {"k": "电弧功率", "v": "80–100 MW"},
            {"k": "预计时间", "v": f"{oxy['time_min']:.1f} min"},
            {"k": "理论 O₂", "v": f"{oxy['nm3']:.0f} Nm³"},
        ],
        "actions": [
            "确认氧枪已开、流量到 150 Nm³/min；碳枪保持 0。",
            f"每 2 分钟看一次 C；到 {stop_lo:.2f}–{stop_hi:.2f}% 立即停氧。",
            "温度到 1650°C 就把功率降到 60–70 MW，氧枪不停。",
            "停氧后继续吹氩/搅拌 1–2 min，让成分均匀。",
        ],
        "checks": [
            f"C 到 {stop_lo:.2f}–{stop_hi:.2f}% 立即停氧",
            "温度 ≤ 1680°C（避免 Cr 大量氧化）",
            "渣子保持发泡，不喷溅",
        ],
        "warn": f"碳枪不要开：这炉 C 只需要降到 {stop_lo:.2f}，开碳枪会把 C 顶回去，还会增加 CO₂。",
    })
    # 5) 取样
    steps.append({
        "id": "eaf-sample", "time": "00:46–00:50",
        "title": "停氧取样，确认 C / Si / Mn / Cr",
        "lead": "这一步决定后面合金加多少。以实测成分为准，不要直接照下面的预测值硬加。",
        "metrics": [
            {"k": "目标 C", "v": f"{stop_lo:.2f}–{stop_hi:.2f}%"},
            {"k": "目标 Si", "v": "≤0.08%"},
            {"k": "目标 Mn", "v": "0.40–0.55%"},
            {"k": "目标 Cr", "v": "0.08–0.12%"},
        ],
        "actions": [
            "点“化学成分分析”，等结果。",
            f"C >{stop_hi:.2f}%：再吹氧 1–2 min，然后重新取样。",
            f"C <{stop_lo:.2f}%：加增碳剂 10–20 kg（10 kg 档），不要超过 20 kg。",
            "Cr 或 Mn 明显低于预测：合金量按实测重算（合金补加页），不要照计划硬加。",
        ],
        "checks": [f"C 在 {stop_lo:.2f}–{stop_hi:.2f}%", "温度 1600–1660°C", "渣子仍然发泡"],
        "tip": "实测 C 每低 0.01%，最终 C 大约低 0.01%；后面合金还会带入约 0.15–0.18% C，所以不要吹过头。",
    })
    # 6) 合金
    alloy_lines = [{"name": a["name"], "qty": f"{a['mass']} kg", "note": f"${a['cost']:,.1f}"}
                   for a in alloy_rows]
    seq = add_sequence(alloy_rows) or ["按表"]
    seq_txt = " → ".join(seq)
    steps.append({
        "id": "eaf-alloy", "time": "00:50–00:58",
        "title": "加合金（全部按 10 kg 档）",
        "lead": f"以停氧后 C {float(pre_c):.2f}%、Si {float(pre_si):.2f}% 计算；加完合金出钢量约 {tap_mass:.1f} t。顺序：{seq_txt}。",
        "metrics": [
            {"k": "合金总重", "v": f"{rounded['added_total']:.0f} kg"},
            {"k": "合金成本", "v": f"${alloy_cost:,.0f}"},
            {"k": "温降", "v": f"−{rounded['temperature_drop']:.0f}°C"},
            {"k": "出钢量", "v": f"{tap_mass:.1f} t"},
        ],
        "adds": alloy_lines,
        "actions": [
            f"按顺序加：{seq_txt}；每加完一种搅拌/升温 2–3 min 化开，再加下一种。",
            "铬铁、锰铁先加（难熔、用量大）；硅系合金最后加（脱氧剂，加早了会被钢水里的氧烧掉）。",
            "全部加完继续搅拌/升温 3–5 min，取样确认。",
            "不要加铝块，也不要加清单以外的合金（Al 已接近上限，多一种就多一份夹带）。",
        ],
        "checks": [
            f"最终 C 目标 {eaf_c_txt}（预测 {rounded['final'].get('C', 0):.3f}%）",
            f"最终 Mn 目标 {eaf_mn_txt}（预测 {rounded['final'].get('Mn', 0):.3f}%）",
            f"最终 Cr 目标 {eaf_cr_txt}（预测 {rounded['final'].get('Cr', 0):.3f}%）",
        ],
        "warn": "合金必须在停氧、取样之后加；氧枪还开着时加合金，Cr 会进渣、C 会被氧化。",
        "tip": "第一次试跑建议先按保守配方把流程跑通，确认取样和停氧节奏，再切到成本优化版。",
    })
    # 7) 调温
    tap_lo, tap_hi = (grade.get("process") or {}).get("temp", [1630, 1660])
    furnace_lo = int(tap_lo + rounded["temperature_drop"] + 5)
    furnace_hi = int(tap_hi + rounded["temperature_drop"] + 5)
    steps.append({
        "id": "eaf-temp", "time": "00:58–01:06",
        "title": "调温到出钢温度",
        "lead": "合金已经加完，温降约 {:.0f}°C；炉内终点要按出钢温度反推。".format(rounded["temperature_drop"]),
        "metrics": [
            {"k": "出钢目标", "v": f"{tap_lo}–{tap_hi}°C"},
            {"k": "炉内终点", "v": f"{furnace_lo}–{furnace_hi}°C"},
            {"k": "合金温降", "v": f"−{rounded['temperature_drop']:.0f}°C"},
        ],
        "actions": [
            f"测温；低于 {furnace_lo}°C 就用 100–120 MW 加热，每次 2–3 min 复测。",
            f"高于 {furnace_hi}°C 就降功率，等 1–2 min 再测，不要用加废钢降温。",
            "温度到位后不要再长时间保温，避免 CO₂ 和电耗增加。",
        ],
        "checks": [f"炉内终点 {furnace_lo}–{furnace_hi}°C", "渣子仍然覆盖弧光", "出钢口畅通"],
        "tip": "出钢温度按模拟器要求 1630–1660°C；如果合金在钢包加而不是炉内加，炉内终点可以低 15–20°C。",
    })
    # 8) 出钢
    steps.append({
        "id": "eaf-tap", "time": "01:06–01:12",
        "title": "出钢，送二次精炼",
        "lead": "出钢前最后取样；出钢后把钢包送到 CAS-OB，进入二次精炼流程。",
        "metrics": [
            {"k": "出钢量", "v": f"{tap_mass:.1f} t"},
            {"k": "出钢温度", "v": f"{tap_lo}–{tap_hi}°C"},
            {"k": "总成本", "v": f"${subtotal:,.0f}"},
            {"k": "吨钢成本", "v": f"${total_per_t:,.1f}/t"},
        ],
        "actions": [
            "出钢前测温、取样；确认 C/Si/Mn/Cr 在目标窗口。",
            "出钢时钢包加覆盖剂/保温剂（如果有），减少温降。",
            "记录实际出钢量、温度和成分，回填网站用于校准。",
            "把钢包送到 CAS-OB，不要送错工位。",
        ],
        "checks": [
            f"出钢量 {tap_mass:.1f} t（目标 80–110 t）",
            f"出钢温度 {tap_lo}–{tap_hi}°C",
            "成分预测全部在窗口内",
        ],
        "tip": f"下一炉按本炉实测回填：若最终 C 偏高，把停氧目标从 {stop_lo:.2f}% 下调 0.01–0.02%；偏低则上调。",
    })

    final = rounded["final"]
    return {
        "status": "ok", "track": "eaf", "grade": grade_key,
        "grade_name": grade["name"], "source": "manual" if (mix_override or alloy_override) else "optimized",
        "manual_mix": bool(mix_override), "manual_alloy": bool(alloy_override),
        "mass": mass, "safe": safe,
        "summary": {
            "scrap_cost": round(scrap_cost, 1),
            "alloy_cost": round(alloy_cost, 1),
            "flux_cost": round(flux_cost, 1),
            "oxygen_cost": round(oxy["cost"], 1),
            "energy_kwh": round(energy_kwh, 0),
            "energy_price": float(energy_price),
            "energy_cost": round(energy_cost, 1),
            "other_cost": round(other_cost, 1),
            "material_cost": round(material_cost, 1),
            "total_cost": round(subtotal, 1),
            "total_per_t": round(total_per_t, 2),
            "tap_mass": round(tap_mass, 1),
            "tap_temp": [tap_lo, tap_hi],
            "furnace_temp": [furnace_lo, furnace_hi],
            "final": final,
            "checks": _checks(final, specs),
            # 合规判定一律按 EAF 自己的规格，不受合金优化目标影响
            "out_of_spec": _out_of_spec(final, specs),
            # 合金优化目标（把 EAF 便宜的 Mn/Cr/Mo 往 SM 窗口推）没打到的部分，仅作诊断
            "alloy_target_miss": _out_of_spec(final, alloy_specs),
            "charge_composition": {k: round(float(v), 4) for k, v in charge["composition"].items()},
            "charge_result": charge,
            "mix_keys": charge.get("mix_int") or charge.get("mix") or {},
            "alloy_map": {a["key"]: a["mass"] for a in alloy_rows},
            "pre": {"C": float(pre_c), "Si": float(pre_si)},
            "mix": charge_rows,
            "baskets": baskets,
            "alloy": alloy_rows,
            "fluxes": fluxes,
        },
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# 二次精炼流程
# ---------------------------------------------------------------------------

# 二次精炼未传元素时的中性起点（不再写死早期特定炉次数字；实际调用均由 EAF 出钢或用户输入覆盖）
DEFAULT_SM_INITIAL = {
    "C": 0.52, "Si": 0.28, "Mn": 1.00, "P": 0.010, "S": 0.010,
    "Cr": 1.55, "Mo": 0.02, "Ni": 0.04, "Cu": 0.06,
    "Al": 0.005, "Nb": 0.0, "Ti": 0.0, "V": 0.0, "B": 0.0,
    "N": 0.0080, "H": 0.0002, "O": 0.0500,
}


def sm_plan(mass_t=82, initial=None, safe=True, temp_start=1565.0,
            alloy_override=None, skip_decarb=False, alloy_pos=None, sm_grade=None):
    mass = int(round(float(mass_t)))
    grade_key = sm_grade if sm_grade in SM_GRADES else "sc21_refining"
    grade = SM_GRADES[grade_key]
    specs = {e: list(v) for e, v in grade["specs"].items()}
    # 工程钢把 Mo 按窗口安全下限控制，避免冲中值白花钱；其它钢种保持原窗口
    mo_spec = specs.get("Mo")
    if (mo_spec and mo_spec[0] is not None and mo_spec[1] is not None
            and float(mo_spec[0]) < 0.16 <= float(mo_spec[1])
            and (alloy_pos is None or float(alloy_pos) >= 0.2)):
        specs["Mo"] = [0.16, float(mo_spec[1])]
    init = {**DEFAULT_SM_INITIAL, **(initial or {})}
    try:
        c0 = float(init.get("C", 0.52))
        si0 = float(init.get("Si", 0.28))
        mn0 = float(init.get("Mn", 1.00))
        cr0 = float(init.get("Cr", 1.55))
        o0 = float(init.get("O", 0.05))
    except Exception:
        return {"status": "error", "message": "初始成分格式错误"}

    # 目标：最终 C 落在窗口内且优先配高碳合金省钱；反推最佳脱碳终点 c_pre
    c_lo, c_hi = specs.get("C") or [0.35, 0.40]
    margin = float(alloy_pos) if alloy_pos is not None else (0.3 if safe else 0.2)
    c_aim = c_lo + (c_hi - c_lo) * max(0.15, min(0.5, margin))
    # 估算补 Mn/Cr 带入的高碳增量，动态求最优 c_pre（不再固定 0.335）
    mn_lo = (specs.get("Mn") or [None, None])[0]
    cr_lo = (specs.get("Cr") or [None, None])[0]
    mn_gap = max(0.0, ((mn_lo + 0.05) if mn_lo is not None else 0.0) - max(0.0, mn0 - 0.010))
    cr_gap = max(0.0, ((cr_lo + 0.05) if cr_lo is not None else 0.0) - max(0.0, cr0 - 0.010))
    est_c_pickup = mn_gap * (7.0 / 76.5) + cr_gap * (6.0 / 66.5)
    # 脱碳终点按当前钢种的 C 窗口反推：高碳钢保留 0.30 的工艺下限，
    # 低碳钢（结构钢/管线钢等）按目标窗口下沿动态下移，避免误套工程钢 0.30–0.355。
    c_floor = 0.30 if c_lo >= 0.30 else max(0.001, c_lo - 0.03)
    c_cap = min(0.355, c_hi - 0.005)
    c_pre_opt = round(max(c_floor, min(c_cap, c_aim - est_c_pickup)), 4)
    c_pre = c_pre_opt if c0 > c_pre_opt + 0.015 else round(
        max(c_floor, min(c_cap, c0 - 0.005)), 4)
    # CAS-OB 直接吹到脱气终点附近；真空脱气只脱 H/N，不再靠它降 C
    c_mid = c_pre + 0.005
    if c0 <= c_mid + 0.005:
        c_mid = c0

    pre = dict(init)
    if skip_decarb:
        # 已经是脱碳/脱气后的成分，不再扣氧化损失
        pre["C"] = c0
        c_pre = c0
        c_mid = c0
    else:
        pre["C"] = c_pre
        pre["Si"] = max(0.0, si0 - 0.015)
        pre["Mn"] = max(0.0, mn0 - 0.010)
        pre["Cr"] = max(0.0, cr0 - 0.010)
        pre["Al"] = min(float(init.get("Al", 0.0) or 0.0), 0.002)
        pre["O"] = min(o0, 0.0016)

    # LF 脱硫：EAF 出钢 S 通常远高于 SM 上限（2026 赛题 EAF ≤0.1、SM ≤0.025），
    # 二次精炼必须专门造还原渣脱硫，否则 S 一定超标。按手册式9-18/9-19 估算渣量与时间，
    # 并把 S 降到目标值，后续合金 LP 才能在同一份成分上收口。
    desulf = None
    _s0 = float(init.get("S", 0.0) or 0.0)
    _s_hi = (specs.get("S") or [None, None])[1]
    if (not skip_decarb) and _s_hi is not None and _s0 > float(_s_hi) + 1e-4:
        _s_aim = round(float(_s_hi) * 0.85, 4)  # 留 15% 余量，避免刚好卡线
        _ds = R.desulf_slag(mass, _s0, _s_aim, 80.0)
        _slag_kg = float(_ds.get("slag_kg") or 0.0)
        _dt = R.desulf_time(mass, _s0, _s_aim, 80.0, _slag_kg / 1000.0, 60.0) if _slag_kg else {}
        _lime_kg = int(round(_slag_kg * 0.90))
        _flu_kg = int(round(_slag_kg * 0.10))
        desulf = {
            "s_in": round(_s0, 4), "s_aim": _s_aim,
            "slag_kg": int(round(_slag_kg)),
            "lime_kg": _lime_kg, "fluorspar_kg": _flu_kg,
            "time_min": round(float(_dt.get("minutes") or 10.0), 1),
            "cost": round(_lime_kg / 1000.0 * 120.0 + _flu_kg / 1000.0 * 180.0, 1),
        }
        pre["S"] = _s_aim

    if alloy_override:
        plan0 = {k: float(v) for k, v in alloy_override.items() if float(v) > 0}
        rounded = round_plan(mass, pre, plan0, specs, track="sm", profile="ladle",
                             repair=False)
    else:
        lp = optimize_alloy_lp(mass, pre, specs, catalog=SM_ADDITIVES, profile="ladle",
                               margin=margin, drift_caps={"Si": 0.01})
        if lp.get("status") != "ok":
            return {"status": "infeasible", "message": lp.get("message", "二次精炼合金 LP 无解")}
        plan0 = {a["key"]: a["mass"] for a in lp["additions"]}
        rounded = round_plan(mass, pre, plan0, specs, track="sm", profile="ladle",
                             repair=True, margin=margin)
    alloy_rows = rounded["additions"]
    alloy_cost = rounded["cost"]
    tap_mass = rounded["mass_after"]

    # 脱碳时间与氧量
    cas_time = max(4.0, min(15.0, (c0 - c_mid) / 0.015)) if c0 > c_mid + 0.005 else 0.0
    degas_time = max(5.0, min(22.0, (c_mid - c_pre) / 0.006 + 4.0)) if c_mid > c_pre + 0.005 else 0.0
    c_kg = max(0.0, (c0 - c_pre)) / 100.0 * mass * 1000.0
    o2_kg = c_kg * 32.0 / 12.0
    o2_nm3 = o2_kg / 1.429

    # 钢包脱氧（到站/出钢）：把初始 O 降到 20 ppm；铝块 98%、回收率 90%
    o0_ppm = o0 * 10000.0
    ladle_al_kg = 0.0
    ladle_o_after = o0_ppm
    if not skip_decarb and o0_ppm > 20:
        # 钢包脱氧先降到约 55 ppm；剩下的 O 由 LF 铝脱氧精调到 ≤20 ppm。
        # 这样两段都按 10 kg 档加，Al 残余不会超过 0.004%。
        ladle_deox = R.deox_ladle(mass, o0_ppm, 55.0, "al_pebble")
        ladle_al_kg = _round_step(ladle_deox.get("reagent_round_kg") or 0)
        ladle_o_after = float(ladle_deox.get("o_after_ppm") or 55.0)

    # LF 铝脱氧（精调）：按钢包脱氧后的 O 继续降到 20 ppm；目标残铝 0.003%
    al_kg = 0.0
    o_pre_ppm = ladle_o_after if ladle_al_kg else float(pre.get("O", 0.0)) * 10000.0
    if o_pre_ppm > 20:
        al = R.deox_al(mass, o_pre_ppm, 0.003, 98, 90)
        al_kg = _round_step(al.get("alloy_mass_kg") or al.get("mass_kg") or 0)
    # 温降与加热
    drop = rounded["temperature_drop"]
    tap_lo, tap_hi = 1573.0, 1576.0
    heat_dT = max(0.0, tap_lo - (float(temp_start) - drop))
    heat = R.heat_time(mass, heat_dT, 20000, 0.45) if heat_dT > 0 else {"minutes": 0}

    # 当前钢种的窗口文本（供步骤里的检查项使用，不再写死 sc21 的数字）
    c_txt = _fmt_range([c_lo, c_hi])
    si_txt = _fmt_range(specs.get("Si"))
    mn_txt = _fmt_range(specs.get("Mn"))
    cr_txt = _fmt_range(specs.get("Cr"))
    mo_txt = _fmt_range(specs.get("Mo"))
    h_hi = (specs.get("H") or [None, 0.0003])[1] or 0.0003
    n_hi = (specs.get("N") or [None, 0.009])[1] or 0.009

    steps = []
    steps.append({
        "id": "sm-arrive", "time": "00:00–00:03",
        "title": "钢包到站 + 钢包脱氧",
        "lead": f"装入 {mass} t，进站温度约 {temp_start:.0f}°C。先氩气搅拌 2–3 min，再按 O 加铝块脱氧。",
        "metrics": [
            {"k": "钢水质量", "v": f"{mass} t"},
            {"k": "进站温度", "v": f"≈{temp_start:.0f}°C"},
            {"k": "初始 C", "v": f"{c0:.4f}%"},
            {"k": "初始 O", "v": f"{o0_ppm:.0f} ppm"},
            {"k": "钢包脱氧铝", "v": f"{ladle_al_kg:.0f} kg" if ladle_al_kg else "—"},
        ],
        "adds": ([{"name": "铝块（98% Al）", "qty": f"{ladle_al_kg:.0f} kg", "note": "到站脱氧到 20 ppm"}] if ladle_al_kg else []),
        "actions": [
            "核对钢包号、重量和上一工序成分。",
            "取 O 样；O >20 ppm 时按上表加铝块脱氧（10 kg 档），氩气搅拌 3–5 min。",
            "确认 CAS-OB 工位空闲，钢包吊运到位。",
        ],
        "checks": ["重量 80–110 t", "温度 ≥ 1550°C", f"钢包脱氧后 O ≤55 ppm（计划 {ladle_o_after:.0f} ppm）"],
        "tip": "温度低于 1550°C 先 LF 加热 3–5 min，再进 CAS-OB；温度低脱碳会明显变慢。",
    })
    if c0 > c_mid + 0.005:
        steps.append({
            "id": "sm-casob", "time": f"{_t(3)}–{_t(3 + cas_time)}",
            "title": "CAS-OB 吹氧脱碳（一步到位）",
            "lead": f"把 C 从 {c0:.3f}% 吹到 {c_pre:.3f}–{c_mid+0.01:.3f}%。真空脱气只脱 H/N 不再大幅降 C，因此 CAS-OB 直接吹到目标区间。",
            "metrics": [
                {"k": "CAS-OB 电源", "v": "打开"},
                {"k": "“吹氧”开关", "v": "打开（灰色=关）"},
                {"k": "氩气流量", "v": "1.0 Nm³/min"},
                {"k": "预计时间", "v": f"{cas_time:.0f} min"},
            ],
            "actions": [
                "打开绿色电源按钮。",
                "把第二行“吹氧”开关拨到开（只有开/关，没有流量数值）。",
                "氩气流量拉到 1.0 Nm³/min。",
                f"每 2–3 分钟点一次“化学成分分析”；C 到 {c_pre:.3f}–{c_mid+0.01:.3f}% 立即关“吹氧”。",
                "关吹氧后继续氩气搅拌 1–2 min，再取样确认 C、Cr、Mn、Si。",
            ],
            "checks": [
                f"C 到 {c_pre:.3f}–{c_mid+0.01:.3f}% 立即关吹氧",
                "3 分钟内 C 不降 → 检查“吹氧”开关是否真的打开",
                "Cr/Mn/Si 不要被过度氧化",
            ],
            "warn": "只开氩气、不点“吹氧”，C 不会降；切记确认吹氧开关打开。",
        })
    h0 = float(init.get("H", 0.0) or 0.0)
    n0 = float(init.get("N", 0.0) or 0.0)
    need_degas = (c_mid > c_pre + 0.005) or (h0 > h_hi * 0.83) or (n0 > n_hi * 0.83)
    if need_degas and degas_time <= 0:
        degas_time = 6.0
    if need_degas:
        steps.append({
            "id": "sm-degas", "time": f"{_t(3 + cas_time)}–{_t(3 + cas_time + degas_time)}",
            "title": "钢包脱气：真空脱氢/脱氮 + C 微调",
            "lead": f"开真空把 H 降到 ≤{h_hi:.4f}%、N 降到 ≤{n_hi:.4f}%，同时 C 稳定在 {c_pre:.3f}% 左右。",
            "metrics": [
                {"k": "真空度", "v": "最大"},
                {"k": "氩气流量", "v": "1.5–2.0 Nm³/min"},
                {"k": "预计时间", "v": f"{degas_time:.0f} min"},
                {"k": "目标 C", "v": f"{c_pre:.3f}%"},
            ],
            "actions": [
                "钢包吊入罐式脱气器，开最大真空。",
                "氩气 1.5–2.0 Nm³/min，保持钢水轻微翻动。",
                "保持 5–6 min 脱除 H/N，停真空后取样确认 C、Cr、Mn、Si、O、H、N。",
            ],
            "checks": [
                f"C 在 {c_pre:.3f}–{c_pre+0.015:.3f}%",
                f"H ≤{h_hi:.4f}%",
                f"N ≤{n_hi:.4f}%",
                f"若 C 仍高于 {c_hi:.2f}% → 回 CAS-OB 补吹 1–2 min",
            ],
            "tip": "CAS-OB 已把 C 吹到位，脱气站主要负责把 H 和 N 抽到安全上限以下。",
        })
    if desulf:
        steps.append({
            "id": "sm-desulf",
            "time": f"{_t(3 + cas_time + degas_time)}–{_t(3 + cas_time + degas_time + desulf['time_min'])}",
            "title": f"LF 脱硫（S {desulf['s_in']:.4f}% → ≤{desulf['s_aim']:.4f}%）",
            "lead": (f"进站 S 约 {desulf['s_in']:.4f}%，成品要 ≤{_s_hi:.3f}%。"
                     f"必须专门造还原渣脱硫，靠吹氧或加合金都降不下来。"),
            "metrics": [
                {"k": "进站 S", "v": f"{desulf['s_in']:.4f}%"},
                {"k": "目标 S", "v": f"≤{_s_hi:.3f}%"},
                {"k": "脱硫渣量", "v": f"{desulf['slag_kg']} kg"},
                {"k": "石灰 / 萤石", "v": f"{desulf['lime_kg']} / {desulf['fluorspar_kg']} kg"},
                {"k": "预计时间", "v": f"{desulf['time_min']} min"},
            ],
            "adds": [
                {"name": "石灰", "qty": f"{desulf['lime_kg']} kg", "note": "造高碱度还原渣"},
                {"name": "萤石", "qty": f"{desulf['fluorspar_kg']} kg", "note": "调渣流动性"},
            ],
            "actions": [
                f"扒掉氧化渣后，加石灰 {desulf['lime_kg']} kg + 萤石 {desulf['fluorspar_kg']} kg 造还原渣。",
                "氩气强搅拌（≥1.5 Nm³/min），保证钢渣充分接触。",
                f"搅拌约 {desulf['time_min']:.0f} min 后取样；S 到 ≤{_s_hi:.3f}% 即可停止。",
                "S 不降反升 → 检查是否还在氧化性气氛、渣是否没化开。",
            ],
            "checks": [f"S ≤{_s_hi:.3f}%", "渣面发亮、流动性好", "搅拌过程中钢水不裸露"],
            "warn": "脱硫是还原反应：渣必须脱氧充分。边吹氧边加石灰是白做，先停氧再造渣。",
        })
    steps.append({
        "id": "sm-deox", "time": f"{_t(3 + cas_time + degas_time)}–{_t(11 + cas_time + degas_time)}",
        "title": "LF 铝脱氧（精调，先取样再决定加不加）",
        "lead": f"钢包到站已用铝块脱氧到约 {ladle_o_after:.0f} ppm；这里精调到 ≤20 ppm：O 已低就不加铝，O 高才补 10–20 kg。",
        "metrics": [
            {"k": "钢包脱氧后 O", "v": f"约 {ladle_o_after:.0f} ppm"},
            {"k": "LF 精调铝", "v": f"{al_kg} kg" if al_kg else "0 kg（O≤20 ppm）"},
            {"k": "目标 O", "v": "≤0.0020%"},
            {"k": "目标 Al", "v": "≤0.0040%"},
        ],
        "adds": ([{"name": "铝块（98% Al）", "qty": f"{al_kg} kg", "note": "LF 精调，O 高时才加"}] if al_kg else []),
        "actions": [
            "脱气后取 O 样；钢包脱氧后 O ≤0.0020% 时不加铝，直接进入合金化。",
            "O >0.0020% 时按上表补铝（10 kg 档），搅拌 3–5 min；每次补 10–20 kg 后复测。",
            "加铝后复测 O/Al；Al 超 0.004% 就停止加铝，改氩气搅拌让 Al₂O₃ 上浮。",
        ],
        "checks": ["O ≤0.0020%", "Al ≤0.0040%", "钢包液面覆盖良好"],
        "warn": "钢包脱氧已经加过一轮，LF 只做精调；不要重复按 450 ppm 的量补铝，铝超了很难降。",
    })
    alloy_lines = [{"name": a["name"], "qty": f"{a['mass']} kg", "note": f"${a['cost']:,.1f}"}
                   for a in alloy_rows]
    sm_seq = add_sequence(alloy_rows) or ["按表"]
    sm_seq_txt = " → ".join(sm_seq)
    steps.append({
        "id": "sm-alloy", "time": f"{_t(11 + cas_time + degas_time)}–{_t(23 + cas_time + degas_time)}",
        "title": "LF 合金化（全部按 10 kg 档）",
        "lead": f"按脱碳后 C {c_pre:.3f}%、Si {pre['Si']:.3f}%、Mn {pre['Mn']:.3f}%、Cr {pre['Cr']:.3f}% 计算；顺序：{sm_seq_txt}。",
        "metrics": [
            {"k": "合金总重", "v": f"{rounded['added_total']:.0f} kg"},
            {"k": "合金成本", "v": f"${alloy_cost:,.0f}"},
            {"k": "温降", "v": f"−{drop:.0f}°C"},
            {"k": "出站量", "v": f"{tap_mass:.1f} t"},
        ],
        "adds": alloy_lines,
        "actions": [
            f"按顺序加：{sm_seq_txt}；每加完一种搅拌 3–5 min，再加下一种。",
            "铬铁、锰铁先加（难熔、用量大）；硼铁、增碳剂最后加，加完立刻搅拌 5–8 min 保证收得率。",
            "全部加完继续搅拌 5–8 min，取样确认。",
            f"不要额外加硅铁：Si 目标 {si_txt}；表里的硅锰只用于补 Mn，带入的 Si 已计入最终 Si 预测。不要加镍/脱硫渣。",
        ],
        "checks": [
            f"C 目标 {c_txt}（预测 {rounded['final'].get('C', 0):.3f}%）",
            f"Mn 目标 {mn_txt}（预测 {rounded['final'].get('Mn', 0):.3f}%）",
            f"Cr 目标 {cr_txt}（预测 {rounded['final'].get('Cr', 0):.3f}%）",
            f"Mo 目标 {mo_txt}（预测 {rounded['final'].get('Mo', 0):.3f}%）" if mo_txt != "—" else "",
        ],
        "warn": f"钼铁不要冲 {mo_txt} 的上限；按窗口下沿附近控制，每多 0.01% Mo 约多花 $190–200。",
        "tip": "正式比赛建议先用一炉保守配方跑通全部工位，再按本页的成本优化方案压缩合金用量。",
    })
    steps.append({
        "id": "sm-temp", "time": f"{_t(23 + cas_time + degas_time)}–{_t(33 + cas_time + degas_time)}",
        "title": "LF 调温 + 最终取样",
        "lead": f"目标出站 1573–1576°C；当前温降约 {drop:.0f}°C，需要 LF 补热约 {heat_dT:.0f}°C。",
        "metrics": [
            {"k": "目标出站", "v": "1573–1576°C"},
            {"k": "LF 功率", "v": "20 MW"},
            {"k": "加热时间", "v": f"≈{heat.get('minutes', 0):.0f} min"},
            {"k": "温降", "v": f"−{drop:.0f}°C"},
        ],
        "actions": [
            "LF 20 MW 少量多次加热，每次 2–3 min 复测。",
            "到 1573–1576°C 停止加热，避免超温。",
            "取最终样：C/Si/Mn/Cr/Mo/Al/O/N/H 全部确认。",
        ],
        "checks": ["出站温度 1573–1576°C", "17 个元素全部在窗口", "钢包净重 80–110 t"],
        "tip": "出站目标按当前钢种窗口执行，宁低勿高，后面还有运输温降。",
    })
    steps.append({
        "id": "sm-cast", "time": f"{_t(33 + cas_time + degas_time)}–{_t(40 + cas_time + degas_time)}",
        "title": "送连铸，结束",
        "lead": "最终取样合格后送小方坯铸机；记录实际成分、温度、时间和成本。",
        "metrics": [
            {"k": "出站量", "v": f"{tap_mass:.1f} t"},
            {"k": "合金成本", "v": f"${alloy_cost:,.0f}"},
            {"k": "吨钢成本", "v": f"${alloy_cost/tap_mass:,.1f}/t（仅合金）"},
            {"k": "计划总时间", "v": f"{40+cas_time+degas_time:.0f} min"},
        ],
        "actions": [
            "确认最终成分和温度后，把钢包送到指定铸机。",
            "记录实际加料量、取样成分，回填网站。",
            "如果时间还有富余，不要额外保温；CO₂ 会超。",
        ],
        "checks": ["17 个元素全绿", "温度 1573–1576°C", "时间 ≤1:45", "铸机正确"],
        "tip": "下一炉沿用本炉实测数据回填，再按实际偏差微调，不要照抄历史炉次。",
    })

    final = rounded["final"]
    desulf_cost = float((desulf or {}).get("cost") or 0.0)
    sm_extra = (al_kg + ladle_al_kg) * 1.4 + desulf_cost
    return {
        "status": "ok", "track": "sm", "grade": grade_key,
        "grade_name": grade["name"], "source": "manual" if alloy_override else "optimized",
        "manual_alloy": bool(alloy_override),
        "mass": mass, "safe": safe,
        "summary": {
            "alloy_cost": round(alloy_cost, 1),
            "al_cost": round(al_kg * 1.4, 1),
            "ladle_al_kg": round(ladle_al_kg, 0),
            "ladle_al_cost": round(ladle_al_kg * 1.4, 1),
            "desulf_cost": round(desulf_cost, 1),
            "desulf": desulf,
            "total_cost": round(alloy_cost + sm_extra, 1),
            "total_per_t": round((alloy_cost + sm_extra) / tap_mass, 2) if tap_mass else 0,
            "tap_mass": round(tap_mass, 1),
            "tap_temp": [tap_lo, tap_hi],
            "c_pre": round(c_pre, 4), "c_mid": round(c_mid, 4),
            "final": final,
            "checks": _checks(final, specs),
            "out_of_spec": rounded["out_of_spec"],
            "alloy": alloy_rows,
            "alloy_map": {a["key"]: a["mass"] for a in alloy_rows},
            "initial": {k: round(float(v), 4) for k, v in init.items()},
            "al_kg": al_kg,
            "o0_ppm": round(o0_ppm, 1),
            "o_after_ladle_ppm": round(ladle_o_after, 1),
            "heat_min": round(heat.get("minutes", 0), 1),
        },
        "steps": steps,
    }
