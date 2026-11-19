# -*- coding: utf-8 -*-
"""动态过程预测与全元素定量纠偏建议。

不按固定时间轴、不使用任何预写假数据：
完全按用户输入的当前成分（支持全部 17 元素）、质量、温度、氧气/碳枪/功率实时计算：
- 瞬时多元素氧化/脱除速率与未来轨迹；
- 协同停氧时间（同时满足 C 锚点与偏高 Si/Mn/Cr 氧化到上限以内）；
- 停氧/脱碳时刻全元素预测成分 → 全局线性规划（LP）+ 10 kg 成本感知整数寻优合金方案；
- O（10 kg 档铝脱氧）、S（白渣脱硫渣量与动力学时间）、H/N（真空脱气分钟数）、温度（MW·min）定量建议。
"""

import math
from .data import EAF_ADDITIVES, SM_ADDITIVES, EAF_GRADES, SM_GRADES
from .alloy_lp import optimize_alloy_lp
from .wizard import round_plan
from . import refine as R


def _n(x, default=0.0):
    try:
        v = float(x)
        return v if v == v else default
    except Exception:
        return default


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def eaf_rates(comp, mass_t, o2=150.0, carbon=0.0, power=90.0):
    """当前工况下的瞬时速率（%/min、°C/min）。dC > 0 表示脱碳下降速率，其余负号表示氧化下降。"""
    c = max(0.0, _n(comp.get("C")))
    mass_kg = max(1.0, _n(mass_t, 82.0) * 1000.0)
    o2 = max(0.0, _n(o2, 150.0))
    carbon = max(0.0, _n(carbon, 0.0))
    power = max(0.0, _n(power, 90.0))

    # 脱碳效率随 C 降低而降低：C=0.5 约 30%，C=0.2 约 18%
    eff = _clamp(0.18 + 0.24 * c, 0.12, 0.32)
    c_remove = o2 * 1.429 * (12.0 / 32.0) * eff  # kg C/min
    c_add = carbon * 0.90                         # 碳枪带入 kg C/min
    d_c = (c_remove - c_add) / mass_kg * 100.0

    # 其他元素按氧势伴随氧化；碳枪不阻止 Si/Mn/Cr 氧化
    oxid = o2 * 1.429 * (12.0 / 32.0) * eff / mass_kg * 100.0
    d_si = -0.55 * oxid if _n(comp.get("Si")) > 0.02 else 0.0
    d_mn = -0.10 * oxid if _n(comp.get("Mn")) > 0.02 else 0.0
    d_cr = -0.08 * oxid if _n(comp.get("Cr")) > 0.02 else 0.0
    d_p = -0.03 * oxid if _n(comp.get("P")) > 0.005 else 0.0

    d_t = (power * 0.045 + o2 * 0.022 + carbon * 0.020 - 0.6)
    return {
        "dC": round(d_c, 5), "dSi": round(d_si, 5), "dMn": round(d_mn, 5),
        "dCr": round(d_cr, 5), "dP": round(d_p, 5), "dT": round(d_t, 3),
        "eff": round(eff, 3),
    }


def eaf_predict(state, minutes=12.0):
    comp = dict(state.get("comp") or {})
    mass = _n(state.get("mass"), 82.0)
    temp = _n(state.get("temp"), 1600.0)
    o2 = _n(state.get("o2"), 150.0)
    carbon = _n(state.get("carbon"), 0.0)
    power = _n(state.get("power"), 90.0)
    target_c = _n(state.get("target_c"), 0.37)
    max_temp = _n(state.get("max_temp"), 1680.0)
    specs = state.get("specs") or EAF_GRADES.get("sc21_engineering", {}).get("specs", {})

    points = []
    t = 0.0
    stop_reason = None
    dt = 0.5
    while t <= minutes + 1e-9:
        points.append({
            "t": round(t, 1),
            "C": round(_n(comp.get("C")), 4),
            "Si": round(_n(comp.get("Si")), 4),
            "Mn": round(_n(comp.get("Mn")), 4),
            "Cr": round(_n(comp.get("Cr")), 4),
            "P": round(_n(comp.get("P")), 4),
            "temp": round(temp, 1),
        })
        if stop_reason:
            break
        r = eaf_rates(comp, mass, o2, carbon, power)
        if "C" in comp:
            comp["C"] = max(0.0, _n(comp.get("C")) - r["dC"] * dt)
        for ek in ("Si", "Mn", "Cr", "P"):
            if ek in comp:
                comp[ek] = max(0.0, _n(comp.get(ek)) + r["d" + ek] * dt)
        temp += r["dT"] * dt
        t = round(t + dt, 1)

        # 协同停氧条件：不仅 C 到目标，若有超上限的 Si/Mn/Cr 正在氧化也尽量等到进窗口
        c_ok = ("C" not in comp) or (comp["C"] <= target_c)
        oxid_high = [
            ek for ek in ("Si", "Mn", "Cr")
            if ek in comp and specs.get(ek) and specs[ek][1] is not None
            and comp[ek] > specs[ek][1] + 1e-4 and abs(r.get("d" + ek, 0)) > 1e-6
        ]
        if temp >= max_temp:
            stop_reason = f"温度已到 {temp:.0f}°C ≥ 安全上限 {max_temp:.0f}°C"
        elif c_ok and not oxid_high:
            stop_reason = f"C 已到 {comp.get('C', 0):.3f}% ≤ 目标 {target_c:.3f}%（可氧化超标元素均已达标）"
        elif c_ok and comp.get("C", 0) <= max(0.05, target_c - 0.12):
            stop_reason = f"C 已降到 {comp.get('C', 0):.3f}%（防过吹停氧，剩余 {', '.join(oxid_high)} 需改用稀释/换渣）"

    return {
        "points": points,
        "final": {
            "C": round(_n(comp.get("C")), 4), "Si": round(_n(comp.get("Si")), 4),
            "Mn": round(_n(comp.get("Mn")), 4), "Cr": round(_n(comp.get("Cr")), 4),
            "P": round(_n(comp.get("P")), 4), "temp": round(temp, 1),
        },
        "stop_comp": {k: round(_n(v), 4) for k, v in comp.items()},
        "stop_t": round(t, 1),
        "stop_reason": stop_reason,
        "rates": eaf_rates(state.get("comp") or {}, mass, o2, carbon, power),
    }


def _sample_advice(c0, rate, target, max_step=4.0, extra_min=0.0):
    c0 = _n(c0)
    rate = _n(rate)
    target = _n(target)
    if rate <= 1e-6 and extra_min <= 0:
        return {"in_min": 3.0, "expected": round(c0, 3), "to_target_min": None,
                "note": "当前无有效脱碳速率，请检查氧气/碳枪设置。"}
    to_c = max(0.0, (c0 - target) / rate) if rate > 1e-6 else 0.0
    to_target = max(to_c, float(extra_min or 0.0))
    step = _clamp(to_target * 0.7 if to_target > 0 else 2.0, 1.5, max_step)
    exp_c = max(0.0, c0 - rate * step) if rate > 1e-6 else c0
    return {
        "in_min": round(step, 1),
        "expected": round(exp_c, 3),
        "to_target_min": round(to_target, 1),
        "note": "预计 %.1f min 到达停点；建议 %.1f min 后取样（预计 C≈%.3f%%）。"
                % (to_target, step, exp_c),
    }


def _spec_status(v, lo, hi):
    if hi is not None and v > hi + 1e-9:
        return "high"
    if lo is not None and v < lo - 1e-9:
        return "low"
    return "ok"


def _off_summary(rows):
    bad = [r for r in rows if r.get("status") in ("high", "low")]
    if not bad:
        return "所有已填元素都在目标窗口内。"
    return "不合格项：" + "、".join(
        "%s %.4f%%%s" % (r["element"], r["value"], "偏高" if r["status"] == "high" else "偏低")
        for r in bad) + "。"


def _solve_dynamic_alloy(mass_t, comp_at_stop, specs, track="eaf", margin=0.2):
    """基于停氧/脱碳时刻的全部已填元素，用 LP + 10 kg 成本感知整数规划求最优补加方案。"""
    if mass_t <= 0 or not comp_at_stop:
        return None
    # 只对用户实际填写的元素（加上能被合金带入的受控元素）建约束，不塞入未填假数据
    active_specs = {}
    for e, lim in specs.items():
        if e in comp_at_stop:
            active_specs[e] = list(lim)
        elif lim[1] is not None and e in ("C", "Si", "Mn", "Cr", "Mo", "Al", "P", "S", "V", "Nb", "Ti", "Ni", "Cu"):
            # 用户未填残余元素时，按 0 初值仅保留上限保护，防止合金夹带超标
            active_specs[e] = [None, lim[1]]
    if track == "sm" and "Mo" in active_specs and active_specs["Mo"][0] is not None:
        active_specs["Mo"] = [max(0.16, active_specs["Mo"][0]), active_specs["Mo"][1]]

    cat = SM_ADDITIVES if track == "sm" else EAF_ADDITIVES
    prof = "ladle" if track == "sm" else "eaf_cal"
    drift = {"Si": 0.01} if track == "sm" else None

    # 若仍有元素高于上限（例如还在吹氧前），LP 用截断到上限的虚拟初值算“停氧达标后的合金包”
    init_for_lp = {}
    for e, v in comp_at_stop.items():
        lim = active_specs.get(e)
        if lim and lim[1] is not None and v > lim[1]:
            init_for_lp[e] = lim[1]
        else:
            init_for_lp[e] = v

    lp = optimize_alloy_lp(mass_t, init_for_lp, active_specs, catalog=cat,
                           profile=prof, margin=margin, drift_caps=drift)
    if lp.get("status") != "ok":
        # 放宽余量重试一次（贴近下限求可行解）
        lp = optimize_alloy_lp(mass_t, init_for_lp, active_specs, catalog=cat,
                               profile=prof, margin=0.02, drift_caps=drift)
    if lp.get("status") != "ok":
        return None
    plan0 = {a["key"]: a["mass"] for a in lp.get("additions") or []}
    rr = round_plan(mass_t, init_for_lp, plan0, active_specs, track=track,
                    profile=prof, step=10, repair=True, margin=margin)
    c0 = float(init_for_lp.get("C", 0.0))
    c_final = float(rr["final"].get("C", c0))
    rr["c_pickup"] = round(max(0.0, c_final - c0), 4)
    return rr


def _off_actions(rows, track, mass=0.0, rates=None, comp=None, target_c=0.0,
                 comp_stop=None, t_stop=0.0, alloy_plan=None):
    """对每个不合格元素生成定量可执行动作（吹氧时长/脱氧铝 kg/脱硫渣 kg & min/脱气 min/LP 合金组合）。"""
    acts = []
    comp = comp or {}
    comp_stop = comp_stop or comp
    rates = rates or {}
    alloy_items = (alloy_plan or {}).get("additions") or []

    # 如果有偏低可合金化元素，先给出全局 LP 联合计算的 10 kg 档总配方卡片
    low_alloy_els = [r["element"] for r in rows
                     if r["status"] == "low" and r["element"] in ("Si", "Mn", "Cr", "Mo", "V", "Ni", "Nb", "Ti", "B", "C")]
    if low_alloy_els and alloy_items:
        combo_txt = " + ".join(f"{a['name']} {int(a['mass'])} kg" for a in alloy_items)
        when_txt = f"吹氧约 {t_stop:.1f} min 到停点后，" if t_stop > 0.2 else "当前可直接"
        pred_parts = [f"{e}→{alloy_plan['final'].get(e, 0):.3f}%" for e in ("C", "Si", "Mn", "Cr", "Mo")
                      if e in alloy_plan.get("final", {}) and (e in comp or e in low_alloy_els)]
        acts.append({
            "key": "alloy",
            "label": f"全局最优补合金（修 {', '.join(low_alloy_els)}，10 kg 档）",
            "priority": 2,
            "why": f"{when_txt}一次加入：{combo_txt}（共 {alloy_plan['added_total']:.0f} kg / ${alloy_plan['cost']:.0f}，"
                   f"温降 −{alloy_plan['temperature_drop']:.1f}°C）。加入后预测 {' · '.join(pred_parts)}。",
            "params": {"additions": alloy_items, "cost": alloy_plan["cost"], "low_elements": low_alloy_els},
        })

    for r in rows:
        e, st, v = r["element"], r["status"], r["value"]
        if e == "C" or st not in ("high", "low"):
            continue
        target = r.get("target") or [None, None]
        lo = target[0] if len(target) > 0 else None
        hi = target[1] if len(target) > 1 else None
        v_stop = _n(comp_stop.get(e), v)

        # 1) Si / Mn / Cr 偏高（氧化去除）
        if e in ("Si", "Mn", "Cr") and st == "high" and hi is not None:
            rate = abs(_n(rates.get("d" + e)))
            if rate > 1e-6:
                mins = max(0.0, (v - hi) / rate)
                c_after = max(0.0, _n(comp.get("C")) - abs(_n(rates.get("dC"))) * mins)
                extra_c = ""
                if c_after < max(0.05, target_c - 0.03):
                    recarb_kg = int(round((target_c - c_after) / 100.0 * mass * 1000.0 / 0.90 / 10.0)) * 10
                    extra_c = f" 届时 C 会被连带吹到约 {c_after:.3f}%，停氧后需补增碳剂约 {max(10, recarb_kg)} kg（或改用高碳铁合金把 C 带回）。"
                acts.append({
                    "key": "blow" if track == "eaf" else "casob",
                    "label": f"{e} 偏高（{v:.4f}% > {hi}%）：吹氧约 {mins:.1f} min",
                    "priority": 1,
                    "why": f"按当前氧化速率 {rate:.4f}%/min，继续吹氧约 {mins:.1f} min 可将 {e} 压到上限 {hi}%（届时 C≈{c_after:.3f}%）。{extra_c}",
                    "params": {"element": e, "minutes": round(mins, 1), "expected_c": round(c_after, 4)},
                })
            else:
                acts.append({
                    "key": "blow" if track == "eaf" else "casob",
                    "label": f"{e} 偏高（{v:.4f}% > {hi}%）：需开氧氧化或稀释",
                    "priority": 2,
                    "why": f"当前工况下 {e} 氧化速率接近 0；需开启吹氧将其氧化入渣，若已在 LF 无法吹氧则只能稀释。",
                    "params": {"element": e},
                })
            continue

        # 2) O 偏高（定量算 10 kg 档铝脱氧）
        if e == "O" and st == "high" and hi is not None:
            o_ppm = v * 10000.0
            aim_ppm = min(20.0, hi * 10000.0 * 0.85)
            deox = R.deox_ladle(mass, o_ppm, aim_ppm, "al_pebble")
            al_kg = int(deox.get("reagent_round_kg") or 0)
            if track == "eaf":
                acts.append({
                    "key": "slag",
                    "label": f"O 偏高（{o_ppm:.0f} ppm）：出钢到站加铝块约 {al_kg} kg",
                    "priority": 2,
                    "why": f"当前溶解氧 {o_ppm:.0f} ppm（上限 {hi*10000:.0f} ppm）；电炉吹氧期 O 高属正常，出钢进二次精炼到站按 10 kg 档加铝块 {al_kg} kg 可降到约 {deox['o_after_ppm']:.0f} ppm（残铝 +{deox['residual_al_pct']:.4f}%）。",
                    "params": {"element": "O", "al_kg": al_kg},
                })
            else:
                acts.append({
                    "key": "deox",
                    "label": f"O 偏高（{o_ppm:.0f} ppm）：补铝块 {max(10, al_kg)} kg 脱氧",
                    "priority": 1,
                    "why": f"溶解氧 {o_ppm:.0f} ppm > {hi*10000:.0f} ppm；加入铝块（98% Al）{max(10, al_kg)} kg 并氩气搅拌 3–4 min，预计 O 降至 {deox['o_after_ppm']:.0f} ppm，残铝增加 {deox['residual_al_pct']:.4f}%。",
                    "params": {"element": "O", "al_kg": max(10, al_kg)},
                })
            continue

        # 3) S 偏高（定量算脱硫渣量 + 搅拌时间）
        if e == "S" and st == "high" and hi is not None:
            s_aim = max(0.001, hi * 0.85)
            sl = R.desulf_slag(mass, v, s_aim, Ls=400.0)
            slag_t = max(0.8, min(3.0, _n(sl.get("slag_t"), 1.5)))
            kin = R.desulf_time(mass, v, s_aim, Ls=400.0, slag_t=slag_t, epsilon=90.0)
            t_des = _n(kin.get("time_min"), 8.0)
            lime_kg = int(round(slag_t * 1000.0 * 0.55 / 10.0)) * 10
            fluo_kg = int(round(slag_t * 1000.0 * 0.10 / 10.0)) * 10
            acts.append({
                "key": "slag" if track == "eaf" else "alloy",
                "label": f"S 偏高（{v:.4f}% > {hi}%）：造白渣脱硫约 {t_des:.1f} min",
                "priority": 2,
                "why": f"要把 S 从 {v:.4f}% 降到 {s_aim:.4f}%（上限 {hi}%），需在低氧条件下（O≤20 ppm）补加石灰约 {lime_kg} kg + 氟石 {max(10, fluo_kg)} kg 造高碱度白渣，强氩气搅拌约 {t_des:.1f} min。",
                "params": {"element": "S", "lime_kg": lime_kg, "fluorspar_kg": max(10, fluo_kg), "minutes": round(t_des, 1)},
            })
            continue

        # 4) H / N 偏高（定量算真空脱气时间）
        if e in ("H", "N") and st == "high" and hi is not None:
            if e == "H":
                hi_ppm, hf_ppm = v * 10000.0, max(0.9, hi * 10000.0 * 0.85)
                kh = R.kH_tank(1.8)["kH"]
                ht = R.hydrogen_time(hi_ppm, hf_ppm, 0.80, kh)
                t_deg = max(3.0, _n(ht.get("time_min"), 6.0))
                detail = f"H 当前 {hi_ppm:.1f} ppm（上限 {hi*10000:.1f} ppm）；罐式脱气最大真空 + 氩气 1.8 Nm³/min（kH={kh:.3f} min⁻¹），需保持真空约 {t_deg:.1f} min 降至 {hf_ppm:.1f} ppm。"
            else:
                # 真空脱氮近似一阶速率 kN ≈ 0.045 min⁻¹，平衡 N ≈ 0.0020%
                n_aim = max(0.0025, hi * 0.90)
                t_deg = max(4.0, -1.0 / 0.045 * math.log(max(0.05, (n_aim - 0.002) / max(1e-5, v - 0.002))))
                detail = f"N 当前 {v*10000:.0f} ppm（上限 {hi*10000:.0f} ppm）；需进钢包脱气开最大真空 + 氩气 1.8–2.0 Nm³/min 约 {t_deg:.1f} min，严禁敞开液面吸氮。"
            acts.append({
                "key": "degas" if track == "sm" else "tap",
                "label": f"{e} 偏高（{v:.4f}%）：真空脱气约 {t_deg:.1f} min",
                "priority": 1 if track == "sm" else 2,
                "why": detail,
                "params": {"element": e, "minutes": round(t_deg, 1)},
            })
            continue

        # 5) Al 偏高
        if e == "Al" and st == "high" and hi is not None:
            acts.append({
                "key": "deox" if track == "sm" else "blow",
                "label": f"Al 偏高（{v:.4f}% > {hi}%）：停用含铝合金并吹氩促上浮",
                "priority": 2,
                "why": f"Al 超上限 {(v - hi)*10000:.0f} ppm；严禁再加铝块/铝线/普通硅铁（含 1.23% Al，必须改高纯硅铁），氩气柔和搅拌 4–6 min 让 Al₂O₃ 上浮（或点吹氧 0.5–1 min 氧化降铝）。",
                "params": {"element": "Al"},
            })
            continue

        # 6) P / Ni / Cu / Mo 等残余超上限（计算稀释所需洁净铁源吨数）
        if st == "high" and hi is not None and e in ("P", "Ni", "Cu", "Mo", "Cr", "V", "Nb", "Ti", "B"):
            dilute_t = math.ceil(mass * (v - hi) / max(hi, 1e-4))
            note = "电炉高氧化渣可微弱脱磷，二次精炼无法脱磷；" if e == "P" else f"{e} 无法通过氧化或精炼去除；"
            acts.append({
                "key": "sample",
                "label": f"{e} 超上限（{v:.4f}% > {hi}%）：需洁净料稀释约 {dilute_t} t",
                "priority": 2,
                "why": f"{note}若总炉容允许，需兑入约 {dilute_t} t 不含 {e} 的 DRI/洁净废钢才能把 {e} 稀释到 {hi}% 以下。",
                "params": {"element": e, "dilute_tons": dilute_t},
            })
            continue

        # 7) 单元素偏低明细（若上面已给全局 LP 合金包，只补充该元素在 LP 包中的分配说明；若无 LP 包则单独算 10 kg 量）
        if st == "low" and lo is not None:
            matched = [a for a in alloy_items if e in (a.get("elements") or {})]
            if matched:
                sub = " + ".join(f"{a['name']} {int(a['mass'])} kg（带入 {e} {a['elements'][e]:.1f} kg）" for a in matched)
                acts.append({
                    "key": "alloy",
                    "label": f"{e} 偏低（停点约 {v_stop:.4f}% < {lo}%）：已纳入全局合金方案",
                    "priority": 3,
                    "why": f"由 {sub} 补足，加入后 {e} 预计达到 {alloy_plan['final'].get(e, lo):.4f}%。",
                    "params": {"element": e},
                })
            else:
                need_kg = max(0.0, lo * 1.02 - v_stop) / 100.0 * mass * 1000.0
                cat = SM_ADDITIVES if track == "sm" else EAF_ADDITIVES
                cands = [a for a in cat if not a.get("flux") and a["comp"].get(e, 0) > 0]
                if cands:
                    best_a = min(cands, key=lambda a: a["price"] / max(a["comp"][e], 0.1))
                    kg10 = max(10, int(math.ceil(need_kg / (best_a["comp"][e] / 100.0 * 0.95) / 10.0)) * 10)
                    acts.append({
                        "key": "alloy",
                        "label": f"{e} 偏低（{v:.4f}% < {lo}%）：补 {best_a['name']} 约 {kg10} kg",
                        "priority": 2,
                        "why": f"停氧/脱碳后 {e} 约 {v_stop:.4f}%，距下限缺约 {need_kg:.1f} kg 纯 {e}；按 10 kg 档需加 {best_a['name']} {kg10} kg。",
                        "params": {"element": e, "additive": best_a["key"], "mass_kg": kg10},
                    })
    return acts


def eaf_advice(state):
    comp = {k: _n(v) for k, v in (state.get("comp") or {}).items() if v is not None and v != ""}
    grade_key = state.get("grade") or "sc21_engineering"
    specs = state.get("specs") or EAF_GRADES.get(grade_key, EAF_GRADES["sc21_engineering"]).get("specs", {})
    mass = _n(state.get("mass"), 82.0)
    temp = _n(state.get("temp"), 1600.0)
    target_c = _n(state.get("target_c"), 0.37)
    o2 = _n(state.get("o2"), 150.0)
    carbon = _n(state.get("carbon"), 0.0)
    power = _n(state.get("power"), 90.0)
    tap_lo, tap_hi = state.get("tap_temp") or [1630, 1660]
    margin = _n(state.get("alloy_margin"), 0.2)

    r = eaf_rates(comp, mass, o2, carbon, power)
    # 估算如果有 Si/Mn/Cr 超上限需要额外吹氧的时间
    extra_blow_min = 0.0
    for ek in ("Si", "Mn", "Cr"):
        if ek in comp and specs.get(ek) and specs[ek][1] is not None and comp[ek] > specs[ek][1]:
            rek = abs(_n(r.get("d" + ek)))
            if rek > 1e-6:
                extra_blow_min = max(extra_blow_min, (comp[ek] - specs[ek][1]) / rek)

    horizon = max(_n(state.get("horizon"), 12.0), min(25.0, extra_blow_min + 4.0))
    pred = eaf_predict({**state, "comp": comp, "specs": specs}, minutes=horizon)
    samp = _sample_advice(_n(comp.get("C")), r["dC"], target_c, extra_min=extra_blow_min)

    comp_stop = pred.get("stop_comp") or dict(comp)
    t_stop = _n(pred.get("stop_t"), 0.0) if ("C" in comp and comp["C"] > target_c + 0.01) or extra_blow_min > 0.2 else 0.0

    # 用真实 LP + 10 kg 整数规划计算“现在停氧”与“吹到目标停氧”的合金方案及 C 增量
    alloy_at_stop = _solve_dynamic_alloy(mass, comp_stop if t_stop > 0 else comp, specs, track="eaf", margin=margin)
    alloy_now = _solve_dynamic_alloy(mass, comp, specs, track="eaf", margin=margin) if t_stop > 0 else alloy_at_stop
    alloy_c = alloy_at_stop["c_pickup"] if alloy_at_stop else _n(state.get("alloy_c_pickup"), 0.16)
    stop_now_c = (alloy_now["final"].get("C") if alloy_now and "C" in alloy_now.get("final", {})
                  else _n(comp.get("C")) + alloy_c)
    target_final_c = (alloy_at_stop["final"].get("C") if alloy_at_stop and "C" in alloy_at_stop.get("final", {})
                      else target_c + alloy_c)

    # 停止/判断表：所有用户填写的元素全部进表判定
    stop_rows = []
    for e, (lo, hi) in specs.items():
        if e not in comp:
            continue
        v = _n(comp.get(e))
        if e == "C":
            c_lo_sp, c_hi_sp = lo, hi
            if state.get("stage") in ("alloy", "tap") and c_lo_sp is not None:
                status = _spec_status(v, c_lo_sp, c_hi_sp)
                stop_rows.append({"element": e, "value": round(v, 4), "target": [c_lo_sp, c_hi_sp],
                                  "status": status, "note": "按出钢 C 窗口判定"})
            else:
                status = "blow" if v > target_c + 0.01 else ("ok" if v >= target_c - 0.01 else "low")
                stop_rows.append({"element": e, "value": round(v, 4), "target": [target_c, round(target_c + 0.01, 3)],
                                  "status": status, "note": f"吹到 {target_c:.2f}% 停氧"})
        else:
            stop_rows.append({"element": e, "value": round(v, 4), "target": [lo, hi],
                              "status": _spec_status(v, lo, hi), "note": ""})
    # 若用户填了不在 EAF_GRADES.specs 里但在 SM 17 元素里的项（如 Mo/Al/O/N/H），同样纳入检查！
    sm_specs = SM_GRADES.get("sc21_refining", {}).get("specs", {})
    for e, v in comp.items():
        if any(x["element"] == e for x in stop_rows):
            continue
        lo, hi = sm_specs.get(e, [None, None])
        stop_rows.append({"element": e, "value": round(v, 4), "target": [lo, hi],
                          "status": _spec_status(v, lo, hi), "note": "参考精炼窗口"})

    off_rows = [row for row in stop_rows if row["element"] != "C" and row["status"] in ("high", "low")]

    actions = []
    c_val = comp.get("C")
    if c_val is not None:
        if c_val > target_c + 0.015 and state.get("stage") not in ("alloy", "tap"):
            actions.append({
                "key": "blow", "label": f"继续吹氧脱碳（约 {samp['to_target_min']} min）", "priority": 1,
                "why": f"当前 C {c_val:.4f}% 高于停氧锚点 {target_c:.3f}%；按 O₂ {o2:.0f} Nm³/min（dC≈{r['dC']:.4f}%/min）预计 {samp['to_target_min']} min 到达目标，建议 {samp['in_min']} min 后取样。",
                "params": {"o2": o2, "carbon": carbon, "power": power, "stop_c": target_c, "minutes": samp["to_target_min"]},
            })
        elif c_val < target_c - 0.02 and state.get("stage") in ("melt", "blow", "sample"):
            recarb_kg = max(10, int(round((target_c - c_val) / 100.0 * mass * 1000.0 / 0.90 / 10.0)) * 10)
            actions.append({
                "key": "alloy", "label": f"C 偏低（{c_val:.4f}%）：立停吹氧，用高碳合金/增碳剂约 {recarb_kg} kg 补回", "priority": 1,
                "why": f"当前 C 已低于停氧锚点 {target_c:.3f}%；立即关氧枪，后续优先由高碳铬铁/高碳锰铁补 C（若单靠增碳剂约需 {recarb_kg} kg）。",
                "params": {"recarb_kg": recarb_kg},
            })
        elif abs(c_val - target_c) <= 0.015 and state.get("stage") in ("blow", "sample"):
            actions.append({
                "key": "sample", "label": "C 已到停氧点：停氧并取全元素样", "priority": 1,
                "why": f"C {c_val:.4f}% 已命中停氧目标 {target_c:.3f}%；立即停氧、氩气搅拌 1 min 后取样确认 Si/Mn/Cr，按下方 10 kg 合金单加料。",
                "params": {"stop_c": target_c},
            })

    # 结合合金温降给出定量升温/降温时间
    t_drop = alloy_at_stop["temperature_drop"] if alloy_at_stop and state.get("stage") != "tap" else 0.0
    aim_furnace_lo = tap_lo + t_drop
    aim_furnace_hi = tap_hi + t_drop
    if temp < aim_furnace_lo:
        need_dt = aim_furnace_lo + 5.0 - temp
        use_mw = max(power, 105.0)
        rate_t = max(1.2, use_mw * 0.045 - 0.6)
        heat_min = round(need_dt / rate_t, 1)
        actions.append({
            "key": "heat", "label": f"升温约 {need_dt:.0f}°C（{use_mw:.0f} MW 约 {heat_min} min）", "priority": 3,
            "why": f"当前 {temp:.0f}°C，计入合金温降 {t_drop:.1f}°C 后炉内需到 {aim_furnace_lo:.0f}–{aim_furnace_hi:.0f}°C 才能保证 {tap_lo}–{tap_hi}°C 出钢；按 {use_mw:.0f} MW 约需 {heat_min} min。",
            "params": {"target": round(aim_furnace_lo + 5), "power_mw": use_mw, "minutes": heat_min},
        })
    elif temp > aim_furnace_hi:
        cool_min = round((temp - aim_furnace_hi) / 1.5, 1)
        actions.append({
            "key": "cool", "label": f"停电降温约 {temp - aim_furnace_hi:.0f}°C（约 {cool_min} min）", "priority": 3,
            "why": f"当前 {temp:.0f}°C 高于目标上限 {aim_furnace_hi:.0f}°C；关电弧静置/吹氩约 {cool_min} min，勿加废钢以免引入杂质。",
            "params": {"target": round(aim_furnace_hi), "minutes": cool_min},
        })

    actions.extend(_off_actions(off_rows, "eaf", mass, r, comp, target_c,
                                comp_stop=comp_stop, t_stop=t_stop, alloy_plan=alloy_at_stop))

    all_ok = not off_rows and (c_val is None or (specs.get("C") and specs["C"][0] <= c_val <= specs["C"][1]))
    if all_ok and tap_lo <= temp <= tap_hi + 10:
        actions.append({
            "key": "tap", "label": "成分与温度全部合格：立即出钢送二次精炼", "priority": 1,
            "why": f"已填元素全部在窗口内，温度 {temp:.0f}°C 满足 {tap_lo}–{tap_hi}°C，立即出钢避免额外电耗与氧化。",
            "params": {"tap_temp": [tap_lo, tap_hi]},
        })

    if not actions:
        actions.append({
            "key": "sample", "label": "取样确认", "priority": 1,
            "why": "请补充更多实测元素以生成精确配方。", "params": {},
        })

    c_disp = f"C {c_val:.4f}%、" if c_val is not None else ""
    return {
        "status": "ok", "track": "eaf", "rates": r, "prediction": pred,
        "sample": samp,
        "alloy_plan": alloy_at_stop,
        "stop": {
            "target_c": target_c,
            "stop_now_final_c": round(_n(stop_now_c), 4),
            "target_final_c": round(_n(target_final_c), 4),
            "elements": stop_rows,
        },
        "actions": sorted(actions, key=lambda x: x["priority"]),
        "summary": (
            f"实测 {mass:.0f} t · {c_disp}温度 {temp:.0f}°C。"
            + (f"按 {o2:.0f} Nm³/min 吹氧 dC≈{r['dC']:.4f}%/min，预计 {samp['to_target_min']} min 到停点（建议 {samp['in_min']:.1f} min 后取样）；"
               f"LP 实算合金带入 C +{alloy_c:.3f}%，停氧合金化后最终 C≈{target_final_c:.3f}%。" if c_val is not None else "")
            + _off_summary(stop_rows)
        ),
    }


def sm_rates(state):
    stage = state.get("stage", "casob")
    mass = max(40.0, _n(state.get("mass"), 85.0))
    scale = 88.0 / mass
    power = _n(state.get("power"), 0.0)
    if stage == "casob":
        d_c = (-0.015 * scale) if state.get("o2_on", True) else -0.0008
        d_si = (-0.0018 * scale) if state.get("o2_on", True) else 0.0
        d_mn = (-0.0012 * scale) if state.get("o2_on", True) else 0.0
        d_cr = (-0.0012 * scale) if state.get("o2_on", True) else 0.0
        d_t = (0.8 if state.get("o2_on", True) else -0.6) + power * 0.02
    elif stage == "degas":
        d_c = -0.0015 * scale
        d_si, d_mn, d_cr = 0.0, 0.0, 0.0
        d_t = -1.2 + power * 0.02
    else:
        d_c = -0.0003
        d_si, d_mn, d_cr = 0.0, 0.0, 0.0
        # LF 电加热速率按手册式 9-33：dT/dt = eta * P_kW / (m * cp * 60)
        heat_rate = (0.50 * power * 1000.0) / (mass * 0.22 * 60.0) if power > 0 else 0.0
        d_t = -0.8 + heat_rate
    return {
        "dC": round(d_c, 5),
        "dSi": round(d_si, 5),
        "dMn": round(d_mn, 5),
        "dCr": round(d_cr, 5),
        "dT": round(d_t, 3),
    }


def sm_predict(state, minutes=20.0):
    comp = dict(state.get("comp") or {})
    temp = _n(state.get("temp"), 1565.0)
    stage = state.get("stage", "casob")
    target = _n(state.get("target_c"), 0.335)
    points = []
    t = 0.0
    stop = None
    dt = 0.5
    while t <= minutes + 1e-9:
        points.append({
            "t": round(t, 1),
            "C": round(_n(comp.get("C")), 4),
            "Si": round(_n(comp.get("Si")), 4),
            "Mn": round(_n(comp.get("Mn")), 4),
            "Cr": round(_n(comp.get("Cr")), 4),
            "temp": round(temp, 1),
            "stage": stage,
        })
        if stop:
            break
        r = sm_rates({**state, "comp": comp, "stage": stage})
        if "C" in comp:
            comp["C"] = max(0.0, _n(comp.get("C")) + r["dC"] * dt)
        for ek in ("Si", "Mn", "Cr"):
            if ek in comp:
                comp[ek] = max(0.0, _n(comp.get(ek)) + r["d" + ek] * dt)
        temp += r["dT"] * dt
        t = round(t + dt, 1)
        if stage in ("casob", "degas") and "C" in comp and comp["C"] <= target:
            stop = f"C 已到 {comp['C']:.3f}% ≤ 目标 {target:.3f}%"
    return {
        "points": points,
        "final": {"C": round(_n(comp.get("C")), 4), "temp": round(temp, 1)},
        "stop_comp": {k: round(_n(v), 4) for k, v in comp.items()},
        "stop_t": round(t, 1),
        "stop_reason": stop,
        "rates": sm_rates(state),
    }


def sm_advice(state):
    comp = {k: _n(v) for k, v in (state.get("comp") or {}).items() if v is not None and v != ""}
    sm_grade = state.get("sm_grade") or "sc21_refining"
    specs = state.get("specs") or (SM_GRADES.get(sm_grade) or SM_GRADES["sc21_refining"])["specs"]
    stage = state.get("stage", "casob")
    mass = _n(state.get("mass"), 85.0)
    temp = _n(state.get("temp"), 1565.0)
    c = comp.get("C")
    target = _n(state.get("target_c"), 0.335)
    margin = _n(state.get("alloy_margin"), 0.2)

    stage_target = target
    r = sm_rates(state)
    pred = sm_predict({**state, "comp": comp, "target_c": stage_target}, minutes=_n(state.get("horizon"), 20.0))
    samp = _sample_advice(c if c is not None else target, -r["dC"], stage_target, max_step=3.0)

    t_stop = _n(pred.get("stop_t"), 0.0) if (stage in ("casob", "degas") and c is not None and c > stage_target + 0.008) else 0.0
    comp_stop = pred.get("stop_comp") if t_stop > 0 else dict(comp)
    # 算 LF 合金包时，假定 O 已脱到 ≤20 ppm、C 在脱碳期按 target 计
    comp_for_alloy = dict(comp_stop or comp)
    if stage in ("casob", "degas") and c is not None and c > stage_target:
        comp_for_alloy["C"] = stage_target
    if comp_for_alloy.get("O", 0) > 0.002:
        comp_for_alloy["O"] = 0.0016
    alloy_plan = _solve_dynamic_alloy(mass, comp_for_alloy, specs, track="sm", margin=margin)

    stop_rows = []
    for e, (lo, hi) in specs.items():
        if e not in comp:
            continue
        v = _n(comp.get(e))
        if e == "C":
            if stage in ("lf", "cast"):
                status = _spec_status(v, lo, hi)
                stop_rows.append({"element": e, "value": round(v, 4), "target": [lo, hi],
                                  "status": status, "note": "按终样窗口判定"})
            else:
                status = "blow" if v > target + 0.01 else ("ok" if v >= target - 0.015 else "low")
                stop_rows.append({"element": e, "value": round(v, 4), "target": [target, round(target + 0.015, 3)],
                                  "status": status, "note": "CAS-OB 一步吹到锚点"})
        else:
            stop_rows.append({"element": e, "value": round(v, 4), "target": [lo, hi],
                              "status": _spec_status(v, lo, hi), "note": ""})
    off_rows = [row for row in stop_rows if row["element"] != "C" and row["status"] in ("high", "low")]

    actions = []
    if stage == "casob":
        if c is not None and c > target + 0.012:
            if not state.get("o2_on", True):
                actions.append({
                    "key": "casob", "label": "立即打开 CAS-OB“吹氧”开关！", "priority": 1,
                    "why": f"当前 C {c:.4f}% 仍高于 {target:.3f}%，但“吹氧”开关未开，单靠吹氩无法脱碳。",
                    "params": {"o2_on": True, "target_c": target},
                })
            else:
                actions.append({
                    "key": "casob", "label": f"继续 CAS-OB 吹氧约 {samp['to_target_min']} min 到 {target:.3f}%", "priority": 1,
                    "why": f"C {c:.4f}% → {target:.3f}%（一步吹到位，不再靠脱气站大幅降碳）；预计 {samp['to_target_min']} min 完成，建议 {samp['in_min']} min 后取样。",
                    "params": {"target_c": stage_target, "next_sample_min": samp["in_min"], "minutes": samp["to_target_min"]},
                })
        else:
            need_vac = any(x["element"] in ("H", "N") and x["status"] == "high" for x in off_rows) or ("H" not in comp and "N" not in comp)
            actions.append({
                "key": "degas" if need_vac else "deox",
                "label": "关吹氧 → 转钢包脱气（脱 H/N）" if need_vac else "C/H/N 已达标 → 直接转 LF 精炼",
                "priority": 1,
                "why": f"C 已到 {c if c is not None else target:.4f}% 附近；" + ("进罐式脱气开最大真空 5–6 min 脱除 H/N。" if need_vac else "H/N 已在窗口内，可省去脱气直接去 LF 脱氧与合金化。"),
                "params": {"target_c": target},
            })
    elif stage == "degas":
        if c is not None and c > target + 0.025:
            actions.append({
                "key": "casob", "label": f"C 偏高（{c:.4f}%）：回 CAS-OB 补吹氧约 {round((c - target)/0.015, 1)} min", "priority": 1,
                "why": "罐式真空脱气不吹氧，脱碳极慢；C 明显偏高时回 CAS-OB 点吹氧更快更省时。",
                "params": {"target_c": target},
            })
        elif not any(x["element"] in ("H", "N") and x["status"] == "high" for x in off_rows):
            actions.append({
                "key": "deox", "label": "转 LF 钢包炉（先看 O 脱氧，再加 10 kg 档合金）", "priority": 1,
                "why": "C 与 H/N 已满足进 LF 条件；到 LF 先确认 O≤20 ppm，再一次性加入下方全局优化的合金组合。",
                "params": {"target_o": 20},
            })

    # LF / 连铸阶段温度定量控制（式 9-33）
    # CAS-OB / 脱气阶段的 1600–1650°C 是工艺需要，不能套用 1573–1576°C 出站窗口；
    # 只有进入 LF 或连铸后才做出站温度判断。
    if stage in ("lf", "cast"):
        t_drop = alloy_plan["temperature_drop"] if alloy_plan and stage != "cast" else 0.0
        aim_lo, aim_hi = 1573.0, 1576.0
        pred_after_alloy = temp - t_drop
        if pred_after_alloy < aim_lo:
            d_t_need = (aim_lo + 1.5) - pred_after_alloy
            ht = R.heat_time(mass, d_t_need, 20000.0, eta=0.50)
            h_min = max(1.5, _n(ht.get("minutes"), 3.0))
            actions.append({
                "key": "heat",
                "label": (f"LF 20 MW 补热约 {d_t_need:.0f}°C（约 {h_min:.1f} min）" if stage == "lf"
                          else f"温度低于出站窗口：回 LF 补热约 {d_t_need:.0f}°C（约 {h_min:.1f} min）"),
                "priority": 3,
                "why": f"当前 {temp:.0f}°C，扣除待加合金温降 {t_drop:.1f}°C 后约 {pred_after_alloy:.0f}°C；用 LF 20 MW 加热约 {h_min:.1f} min 精准送到 1574–1575°C 出站。",
                "params": {"target": 1575, "power_mw": 20, "minutes": round(h_min, 1)},
            })
        elif pred_after_alloy > aim_hi:
            cool_min = round((pred_after_alloy - aim_hi + 1.0) / 1.0, 1)
            actions.append({
                "key": "sample", "label": f"温度偏高（{temp:.0f}°C）：停电吹氩降温约 {cool_min} min", "priority": 3,
                "why": f"高于出站上限 {aim_hi:.0f}°C；关闭 LF 加热，柔和吹氩自然降温至 1574–1576°C 再送连铸。",
                "params": {"target": 1575, "minutes": cool_min},
            })

    actions.extend(_off_actions(off_rows, "sm", mass, r, comp, target,
                                comp_stop=comp_stop, t_stop=t_stop, alloy_plan=alloy_plan))

    c_final_ok = c is not None and specs.get("C") and (specs["C"][0] - 1e-4 <= c <= specs["C"][1] + 1e-4)
    if stage in ("lf", "cast") and not off_rows and c_final_ok and aim_lo - 1 <= temp <= aim_hi + 2:
        actions.append({
            "key": "cast", "label": "全部已检元素与温度达标：立即送小方坯连铸！", "priority": 1,
            "why": f"当前已填元素全部合格，温度 {temp:.0f}°C 落在 1573–1576°C 窗口内，立即开浇避免超时与温降。",
            "params": {},
        })

    c_disp = f"C {c:.4f}%、" if c is not None else ""
    alloy_c_pick = alloy_plan["c_pickup"] if alloy_plan else 0.0
    return {
        "status": "ok", "track": "sm", "stage": stage, "rates": r, "prediction": pred,
        "sample": samp,
        "alloy_plan": alloy_plan,
        "stop": {
            "target_c": target,
            "target_final_c": round(target + alloy_c_pick, 4),
            "elements": stop_rows,
        },
        "actions": sorted(actions, key=lambda x: x["priority"]),
        "summary": (
            f"阶段 {stage} · {mass:.0f} t · {c_disp}温度 {temp:.0f}°C。"
            + (f"按 |dC|≈{abs(r['dC']):.4f}%/min，约 {samp['to_target_min'] or 0:.1f} min 到 {stage_target:.3f}%（建议 {samp['in_min']:.1f} min 后取样）；"
               f"LP 实算后续合金带入 C +{alloy_c_pick:.3f}%。" if c is not None and stage in ("casob", "degas") else "")
            + _off_summary(stop_rows)
        ),
    }


def advise(payload):
    track = payload.get("track", "eaf")
    state = payload.get("state") or {}
    if track == "sm":
        return sm_advice(state)
    return eaf_advice(state)
