# -*- coding: utf-8 -*-
"""配料 + 合金的联合成本优化。

思路：
1. 用 `optimize_charge` 生成若干候选废钢配比（基础 / 模拟器 Ni 校准 / 合金替代价值）；
2. 对每个候选，把熔炼后成分作为合金起点（C/Si 按吹氧后目标覆盖）；
3. 用 `optimize_alloy_lp` 求该配比下的最低合金成本；
4. 选“废钢成本 + 合金成本”最低且成分全部达标的方案。

这样能避免旧版“只选最便宜废钢，再花高价补合金”的局部最优。
"""

from .alloy_lp import optimize_alloy_lp
from .alloys import calculate_additions
from .charge import optimize_charge
from .data import EAF_ADDITIVES, EAF_GRADES, RECOVERY


def _mid_targets(specs):
    out = {}
    for e, (lo, hi) in specs.items():
        if lo is None:
            continue
        out[e] = (lo + (hi if hi is not None else lo)) / 2.0
    return out


def _initial_from_charge(charge, c_pre, si_pre):
    comp = dict(charge.get("composition") or {})
    comp["C"] = c_pre
    comp["Si"] = si_pre
    return comp


def _greedy_baseline(mass_t, initial, specs):
    """旧版贪心合金方案，用作“优化前”对照。

    只对 C/Si/Mn/Cr 主动配目标；P/S/Mo/Ni/Cu 等残余元素是上限约束，
    不能作为“目标”去补加，否则会给出荒谬的添加量。
    """
    targets = {}
    for e in ("C", "Si", "Mn", "Cr"):
        if e in specs:
            lo, hi = specs[e]
            targets[e] = (lo + (hi if hi is not None else lo)) / 2.0
    prof = {k: v for k, v in RECOVERY["eaf_cal"].items() if k != "label"}
    return calculate_additions(mass_t, initial, targets, EAF_ADDITIVES, prof,
                               limits=specs, max_passes=2)


def optimize_total(grade_key, mass_t=82.0, charge_margin=0.06, alloy_margin=0.2,
                   c_pre=0.37, si_pre=0.05, ni_cal=1.0,
                   power_kwh=None, power_price=0.57, other_cost=0.0,
                   limits=None, round_tons=False, alloy_step=0, volume_limit=100.0,
                   specs_override=None, alloy_specs_override=None):
    """联合优化配料 + 合金，返回最低 scrap+alloy 成本方案。

    limits：各废钢的启用/上限，与「炉料配比」页的勾选一致；不传则全部可用。
    round_tons / alloy_step：给出可执行方案（整吨装料、合金按 step 取整）。
    specs_override：EAF 出钢规格（可叠加 SM 进站上限），用于**废钢配料**与合规判定。
    alloy_specs_override：仅用于**合金补加**的目标窗口，可把 EAF 补更便宜的元素
        往 SM 窗口里推；不影响废钢配料，也不影响 EAF 合规判定。
        默认与 specs_override 相同（即不做额外前移）。
    power_kwh / power_price / other_cost 只用于附带估算总成本，不参与选优
    （电量由操作时间决定，与配料算法无关）。
    """
    if grade_key not in EAF_GRADES:
        return {"status": "error", "message": f"未知 EAF 钢种：{grade_key}"}
    specs = specs_override or EAF_GRADES[grade_key]["specs"]          # 配料 + 合规
    alloy_specs = alloy_specs_override or specs                        # 仅合金
    limits = limits or EAF_GRADES[grade_key].get("material_limits")
    carbon_cap = EAF_GRADES[grade_key].get("charge_c_max")
    limits = limits or None
    allowed = None
    if limits:
        allowed = {k for k, v in limits.items() if (v or {}).get("enabled", True)}
        if not allowed:
            return {"status": "infeasible", "message": "所有废钢都被取消了，至少勾选一种"}

    candidates = []
    # 停氧碳锚点搜索集合：围绕用户设定 c_pre 的 ±0.02 动态范围（不再写死 0.32–0.41）
    c_grid = sorted({round(float(c_pre), 3),
                     round(max(0.001, float(c_pre) - 0.02), 3),
                     round(max(0.001, float(c_pre) - 0.01), 3),
                     round(float(c_pre) + 0.01, 3)})

    def add_candidate(tag, charge, retention=None, credit=None):
        if not charge or charge.get("status") != "ok":
            return
        for cp in c_grid:
            init = _initial_from_charge(charge, cp, si_pre)
            alloy = optimize_alloy_lp(mass_t, init, alloy_specs, profile="eaf_cal",
                                      margin=alloy_margin)
            if alloy.get("status") != "ok":
                continue
            total = float(charge.get("cost", 0)) + float(alloy.get("cost", 0))
            candidates.append({
                "tag": tag if abs(cp - float(c_pre)) < 1e-6 else f"{tag}@C{cp:.2f}",
                "c_pre": cp,
                "charge": charge,
                "alloy": alloy,
                "retention": retention or {},
                "credit": credit or {},
                "scrap_cost": round(float(charge.get("cost", 0)), 1),
                "alloy_cost": round(float(alloy.get("cost", 0)), 1),
                "total_cost": round(total, 1),
                "total_per_t": round(total / float(alloy.get("mass_after", mass_t)), 2)
                if alloy.get("mass_after") else None,
                "out_of_spec": alloy.get("out_of_spec") or [],
            })

    # 1) 基础：当前默认收得率
    def run_pass(grid):
        c_grid[:] = grid
        candidates.clear()
        # 1) 基础：当前默认收得率
        add_candidate("base", optimize_charge(grade_key, mass_t, material_limits=limits,
                                             volume_limit=volume_limit, margin=charge_margin,
                                             specs_override=specs_override,
                                             carbon_cap=carbon_cap))

        # 2) 模拟器 Ni 校准：允许更多电炉炉尘（负成本、带 Cr/Mn）
        # 2026-11-17：模拟器实测 Ni 在熔化期完全不损失（步骤1 即纯加权值），
        # 因此不再用「Ni 部分进入钢水」的校准候选，直接按 1.0 计。
        ni_ret = {"Ni": ni_cal}
        add_candidate("ni_cal", optimize_charge(
            grade_key, mass_t, material_limits=limits, volume_limit=volume_limit,
            margin=charge_margin, retention=ni_ret, specs_override=specs_override,
            carbon_cap=carbon_cap), ni_ret)

        # 3) Ni 校准 + 合金替代价值（Mn/Cr/Si）
        credit_map = {"Mn": 4.0, "Cr": 7.5, "Si": 3.0}
        add_candidate("ni_cal_credit", optimize_charge(
            grade_key, mass_t, material_limits=limits, volume_limit=volume_limit,
            margin=charge_margin, retention=ni_ret, specs_override=specs_override,
            objective_credit=credit_map, carbon_cap=carbon_cap), ni_ret, credit_map)

    run_pass(c_grid)

    # 合金带碳多时（例如按 SM 窗口在 EAF 预加高碳铬铁 / 钼铁），出钢 C 会被合金顶过上限，
    # 必须比默认锚点更早停氧。此时把锚点向下扩展再排一遍，避免误判「无可行方案」。
    if not candidates:
        ext = sorted(set(c_grid) | {
            round(max(0.001, float(c_pre) - d), 3)
            for d in (0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12)
        })
        run_pass(ext)

    if not candidates:
        return {"status": "infeasible", "message": "没有可行的配料+合金组合"}

    # 优先选成本最低；若成本相同，选偏离用户设定 c_pre 最小的
    candidates.sort(key=lambda c: (len(c["out_of_spec"]), c["total_cost"], abs(c["c_pre"] - float(c_pre))))
    best = candidates[0]

    # 可执行方案：对各候选配料分别做整吨取整 + 10 kg 合金取整，直接选离散总成本最低的方案
    exec_plan = None
    if round_tons or alloy_step:
        from .wizard import round_charge_mix, round_plan
        exec_cands = []
        seen_tags = set()
        for cand in candidates:
            base_tag = cand["tag"].split("@")[0]
            key_sig = (base_tag, cand["c_pre"])
            if key_sig in seen_tags:
                continue
            seen_tags.add(key_sig)
            ch_lp = cand["charge"]
            ch_exec = ch_lp
            if round_tons:
                r_ch = round_charge_mix(
                    ch_lp.get("mix") or {}, mass_t, grade_key,
                    cand.get("retention") or None, volume_limit,
                    allowed=allowed, limits=limits, credit=cand.get("credit") or None)
                if r_ch.get("status") == "ok":
                    ch_exec = r_ch
                else:
                    continue
            cp = cand["c_pre"]
            init_exec = _initial_from_charge(ch_exec, cp, si_pre)
            al_exec = optimize_alloy_lp(mass_t, init_exec, alloy_specs, profile="eaf_cal",
                                        margin=alloy_margin)
            if al_exec.get("status") != "ok":
                continue
            if alloy_step:
                plan = {a["key"]: a["mass"] for a in al_exec["additions"]}
                rr = round_plan(mass_t, init_exec, plan, alloy_specs, track="eaf",
                                profile="eaf_cal", step=int(alloy_step),
                                repair=True, margin=alloy_margin)
                if rr and rr.get("additions") is not None:
                    al_exec = {**al_exec, **{k: rr[k] for k in
                               ("additions", "added_total", "cost", "mass_after",
                                "final", "temperature_drop", "out_of_spec") if k in rr}}
            total_exec = float(ch_exec.get("cost", 0)) + float(al_exec.get("cost", 0))
            exec_cands.append({
                "tag": cand["tag"],
                "c_pre": cp,
                "charge": ch_exec,
                "alloy": al_exec,
                "retention": cand.get("retention") or {},
                "scrap_cost": round(float(ch_exec.get("cost", 0)), 1),
                "alloy_cost": round(float(al_exec.get("cost", 0)), 1),
                "total_cost": round(total_exec, 1),
                "total_per_t": round(total_exec / float(al_exec.get("mass_after") or mass_t), 2),
                "out_of_spec": al_exec.get("out_of_spec") or [],
                "delta_vs_lp": round(total_exec - best["total_cost"], 1),
            })
        if exec_cands:
            exec_cands.sort(key=lambda x: (
                len(x["charge"].get("violations") or []),
                len(x["out_of_spec"]),
                x["total_cost"],
                abs(x["c_pre"] - float(c_pre)),
            ))
            exec_plan = exec_cands[0]

    # 旧版对照：基础配料 + 贪心合金
    base_charge = candidates[0]["charge"]
    for c in candidates:
        if c["tag"] == "base":
            base_charge = c["charge"]
            break
    base_init = _initial_from_charge(base_charge, c_pre, si_pre)
    try:
        greedy = _greedy_baseline(mass_t, base_init, alloy_specs)
        baseline_total = float(base_charge.get("cost", 0)) + float(greedy.get("cost", 0))
        baseline = {
            "scrap_cost": round(float(base_charge.get("cost", 0)), 1),
            "alloy_cost": round(float(greedy.get("cost", 0)), 1),
            "total_cost": round(baseline_total, 1),
            "alloy_plan": greedy.get("additions", []),
        }
    except Exception:
        baseline_total = None
        baseline = None

    saving = round(baseline_total - best["total_cost"], 1) if baseline_total else None
    saving_pct = round(saving / baseline_total * 100.0, 2) if baseline_total else None

    out = {
        "status": "ok",
        "grade": grade_key,
        "mass_t": mass_t,
        "method": "joint_lp",
        "c_pre": c_pre,
        "si_pre": si_pre,
        "alloy_margin": alloy_margin,
        "best": best,
        "exec": exec_plan,
        "candidates": candidates,
        "baseline": baseline,
        "saving": saving,
        "saving_pct": saving_pct,
    }
    if power_kwh:
        power_cost = round(float(power_kwh) * float(power_price), 1)
        base_total = (exec_plan or best)["total_cost"]
        out["power"] = {
            "kwh": float(power_kwh), "price": float(power_price),
            "cost": power_cost,
            "total_with_power": round(base_total + power_cost + float(other_cost), 1),
        }
    return out
