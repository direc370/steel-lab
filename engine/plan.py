# -*- coding: utf-8 -*-
"""炉次初始规划。

开炉前把 EAF 与二次精炼串成一条完整路线。每个检查点先写“看什么元素、
到什么值停”，时间只作参考节拍；执行时交给「动态操作」按实测成分滚动修正。

这不是另一套计算，而是把 eaf_plan / sm_plan 的结果提炼成可执行的检查点，
保证“初始规划”和“分步向导 / 动态操作”用的是同一套配料与合金数据。
"""

import re

from .data import EAF_GRADES, SM_GRADES, sm_grade_for, default_pre_c
from .wizard import eaf_plan, sm_plan, DEFAULT_SM_INITIAL


def _num(text):
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(text or ""))
    return float(m.group(1)) if m else None


def _metrics(step):
    return {m.get("k"): m.get("v") for m in (step or {}).get("metrics") or []}


def _step_min(steps, step_id, key="预计时间"):
    for st in steps or []:
        if st.get("id") == step_id:
            return _num(_metrics(st).get(key))
    return None


def _ck(track, no, stage, title, trigger, action, checks=None, c=None,
        c_window=None, probe=None, ref_min=None, kind="state", step_id=None,
        high=None, low=None):
    return {
        "track": track, "no": no, "stage": stage, "title": title,
        "trigger": trigger, "action": action, "checks": checks or [],
        "c": None if c is None else round(float(c), 4),
        "c_window": c_window,
        "probe": probe or ({} if c is None else {"C": round(float(c), 4)}),
        "ref_min": None if ref_min is None else round(float(ref_min), 1),
        "kind": kind, "step_id": step_id,
        "high": high or "", "low": low or "",
    }


def _flux_amounts(fluxes):
    """按石灰/白云石/氟石顺序返回 kg。"""
    out = []
    for key in ("石灰", "白云石", "氟石"):
        row = next((x for x in fluxes or [] if x.get("name") == key), None)
        out.append(int(round(float((row or {}).get("mass") or 0))))
    return out


def _fmt_spec(pair, digits=2):
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


def _sm_feed_specs(grade_key, sm_grade_key):
    """EAF 出钢规格 + 二次精炼进站上限。

    SM 只能加合金、吹氧脱碳，不能把 Mn/Cr/Si/Mo 等已经超上限的元素降下来；
    因此整炉规划时把 EAF 规格中这些元素的上限收紧到 SM 目标上限。
    C 由 CAS-OB 脱碳、S 由 LF 脱硫、N/H/O 由脱气脱氧处理，不在此列。
    返回 None 表示无需收紧，保持原基线。

    注意：这里只收上限，**不改下限**。下限是「可以让 SM 去补」的自由度，
    把它抬上来会连累废钢配料（配料阶段也被要求凑 SM 窗口），
    而且会让 EAF 自己的合规校验变成按窄窗口判。
    想让 EAF 多承担 Mn/Cr/Mo 以省合金钱，用 _alloy_target_specs 单独给合金 LP 用。
    """
    base = {e: list(v) for e, v in (EAF_GRADES.get(grade_key) or {}).get("specs", {}).items()}
    sm = (SM_GRADES.get(sm_grade_key) or {}).get("specs") or {}
    changed = False
    for e in ("Si", "Mn", "Cr", "Mo", "P", "Ni", "Cu"):
        if e not in base or e not in sm:
            continue
        hi0, hi1 = base[e][1], sm[e][1]
        if hi0 is not None and hi1 is not None and float(hi1) < float(hi0):
            base[e][1] = float(hi1)
            changed = True
    return base if changed else None


# EAF 合金比 SM 便宜的元素（每 kg 元素成本，见 data.py 两张添加剂表）：
#   Mo  $2.71 vs $24.00（约 9 倍）· Cr $0.84 vs $1.90（2.3 倍）· Mn $0.46 vs $0.64（1.4 倍）
# Si 相反：EAF $1.28 vs SM $1.03，留给 SM 补。
_EAF_CHEAPER_ELEMENTS = ("Mn", "Cr", "Mo")


def _alloy_target_specs(grade_key, sm_grade_key):
    """给 **EAF 合金 LP** 用的目标窗口：能在 EAF 便宜补的，就做到 SM 窗口内。

    这是纯成本优化目标，不是工艺要求，所以：
    - 只在「EAF 窗口 ∩ SM 窗口」非空时才抬下限，保证永远不越过 EAF 自己的规格；
    - 交集为空（如 2026 赛题 Mo：EAF ≤0.024%、SM 要 0.15–0.25）就原样返回该元素；
    - 只作用于合金补加，不参与废钢配料，也不作为 EAF 合规判定依据。

    返回 (specs, 说明文本)；无可优化项时 specs 为 None。
    """
    base = {e: list(v) for e, v in (EAF_GRADES.get(grade_key) or {}).get("specs", {}).items()}
    sm = (SM_GRADES.get(sm_grade_key) or {}).get("specs") or {}
    notes = []
    for e in _EAF_CHEAPER_ELEMENTS:
        if e not in base or e not in sm:
            continue
        lo0, hi0 = base[e][0], base[e][1]
        lo1, hi1 = sm[e][0], sm[e][1]
        if lo1 is None:
            continue
        # 下限：EAF 自己不能低于 SM 要求补到的位置时才抬
        target_lo = max(float(x) for x in (lo0, lo1) if x is not None)
        # 上限：EAF 自己不能超过 SM 上限（SM 降不下来）
        caps = [float(x) for x in (hi0, hi1) if x is not None]
        target_hi = min(caps) if caps else None
        if target_hi is not None and target_lo > target_hi:
            continue  # 交集为空：EAF 做不到，仍交给 SM
        if (lo0 is None or target_lo > float(lo0) + 1e-9) or \
           (hi0 is not None and target_hi is not None and target_hi < float(hi0) - 1e-9):
            base[e] = [target_lo, target_hi]
            notes.append("%s 提到 %.2f–%.2f%%（EAF 加更便宜）"
                         % (e, target_lo, target_hi if target_hi is not None else target_lo))
    return (base if notes else None), notes


def _eaf_checkpoints(eaf, pre_c):
    s = eaf["summary"]
    final = s.get("final") or {}
    specs = EAF_GRADES.get(eaf.get("grade"), {}).get("specs") or {}
    c_spec = specs.get("C") or [0.50, 0.56]
    charge_c = float((s.get("charge_composition") or {}).get("C", pre_c))
    tap_c = float(final.get("C", c_spec[0]))
    tap_lo, tap_hi = s.get("tap_temp") or [1630, 1660]
    furnace_lo, furnace_hi = s.get("furnace_temp") or [tap_lo, tap_hi]
    oxy_min = _step_min(eaf.get("steps"), "eaf-blow")
    stop_lo = round(float(pre_c), 3)
    stop_hi = round(float(pre_c) + 0.01, 3)

    cps = [
        _ck("eaf", 1, "装料", "装第 1 斗（整吨）",
            f"总装入量 = {eaf.get('mass')} t；逐斗称重",
            "按装料单先装 DRI / 炉尘和一部分 1 号捆包，再装剩余 1 号捆包；每斗不超过 40 m³。",
            ["总装入量 = %s t（只能整吨）" % eaf.get("mass"), "总体积 ≤ 100 m³", "粗料质量占比 ≤ 30%"],
            c=charge_c, c_window=None, probe={"C": round(charge_c, 4)},
            ref_min=5, kind="state", step_id="eaf-charge"),
        _ck("eaf", 2, "熔化", "熔清 + 装第 2 斗",
            "炉料全熔、无冷料堆；温度 ≥ 1560°C",
            "第 1 斗熔清后降功率装第 2 斗，恢复 110–120 MW 继续熔清；熔清后测温。",
            ["无结块、电极不埋冷料", "温度 ≥ 1560°C", "第 2 斗重量与装料单一致"],
            c=charge_c, ref_min=25, kind="heat", step_id="eaf-melt"),
        _ck("eaf", 3, "造渣", "一次加完全部渣料",
            "熔清后立即造渣；碱度 1.6–1.9",
            "石灰 %s kg + 白云石 %s kg + 氟石 %s kg 一次全部加入，不再分两批；加完吹氧 1–2 min 化渣。"
            % tuple(_flux_amounts(s.get("fluxes"))),
            ["碱度 1.6–1.9", "MgO 8–10%", "FeO 30–40%"],
            ref_min=6, kind="slag", step_id="eaf-flux"),
        _ck("eaf", 4, "吹氧", "吹氧脱碳（碳枪 0）",
            f"C 高于 {stop_hi:.2f}%、温度 1560–1650°C、渣已造好",
            "氧枪 150 Nm³/min、碳枪 0；每 2 min 点一次成分分析，只盯 C，不按时间停。",
            [f"C 到 {stop_lo:.2f}–{stop_hi:.2f}% 立即停氧", "温度 ≤1680°C", "渣面持续发泡、不喷溅"],
            c=charge_c, c_window=[stop_lo, stop_hi], probe={"C": round(charge_c, 4)},
            ref_min=oxy_min, kind="blow", step_id="eaf-blow",
            high=f"C > {stop_hi + 0.02:.2f}%：继续吹 1–2 min，再取样；不要一次吹过头。",
            low=f"C < {stop_lo - 0.02:.2f}%：停氧，加增碳剂 10–20 kg（10 kg 档）后重新取样。"),
        _ck("eaf", 5, "取样", "停氧取样，确认 C / Si / Mn / Cr",
            f"C 到 {stop_lo:.2f}–{stop_hi:.2f}% 立即停氧，吹氩 1–2 min 后取样",
            "以实测成分为准，不照预测值硬加合金；C 偏离先修正，再进入合金化。",
            [f"C {stop_lo - 0.02:.2f}–{stop_hi + 0.02:.2f}%", "温度 1600–1660°C", "渣子仍然发泡"],
            c=pre_c, c_window=[round(float(pre_c) - 0.02, 3), round(float(pre_c) + 0.03, 3)],
            probe={"C": round(float(pre_c), 4)},
            ref_min=4, kind="sample", step_id="eaf-sample",
            high=f"C > {stop_hi + 0.02:.2f}%：再吹 1–2 min，重新取样。",
            low=f"C < {stop_lo - 0.02:.2f}%：加增碳剂 10–20 kg，搅匀后重新取样。"),
        _ck("eaf", 6, "合金化", "加合金（全部 10 kg 档）",
            "停氧取样完成，按实测 C/Si/Mn/Cr 重算合金",
            "按加料单顺序加：铬铁、锰铁先加（难熔、量大），硅系合金最后加（脱氧剂，加早了会被氧化）；每批搅拌 2–3 min。",
            ["C 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("C")), tap_c),
             "Mn 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("Mn")), float(final.get("Mn", 0))),
             "Cr 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("Cr")), float(final.get("Cr", 0)))],
            c=tap_c, c_window=c_spec, probe={"C": round(tap_c, 4)},
            ref_min=8, kind="alloy", step_id="eaf-alloy",
            high="实测 C 高于计划 0.02% 以上：合金按实测重算，不要照原计划加。",
            low="实测 C 低于计划 0.02% 以上：先补增碳剂 10–20 kg，再加合金。"),
        _ck("eaf", 7, "调温", "调温到出钢温度",
            "合金加完、搅拌 3–5 min 后测温",
            "炉内终点按出钢温度反推：低于下限用 100–120 MW 加热，每次 2–3 min 复测；高了降功率等待，不加废钢。",
            ["炉内终点 %d–%d°C" % (furnace_lo, furnace_hi), "渣子覆盖弧光", "出钢口畅通"],
            probe={"T": [furnace_lo, furnace_hi]}, ref_min=8, kind="heat", step_id="eaf-temp"),
        _ck("eaf", 8, "出钢", "出钢，送二次精炼",
            "C %s、温度 %d–%d°C" % (_fmt_spec(c_spec), tap_lo, tap_hi),
            "出钢前最后测温、取样；记录实际出钢量与成分；钢包送 CAS-OB，不要送错工位。",
            ["出钢量 %.1f t" % float(s.get("tap_mass", 0)), "出钢温度 %d–%d°C" % (tap_lo, tap_hi), "C/Si/Mn/Cr 全部在窗口"],
            c=tap_c, c_window=c_spec, probe={"C": round(tap_c, 4), "T": [tap_lo, tap_hi]},
            ref_min=6, kind="tap", step_id="eaf-tap"),
    ]
    return cps


def _sm_checkpoints(sm):
    s = sm["summary"]
    final = s.get("final") or {}
    specs = SM_GRADES.get(sm.get("grade") or "sc21_refining", {}).get("specs") or {}
    c_spec = specs.get("C") or [0.35, 0.40]
    init_c = float((s.get("initial") or {}).get("C", 0.55))
    c_mid = float(s.get("c_mid", 0.45))
    c_pre = float(s.get("c_pre", 0.335))
    final_c = float(final.get("C", c_spec[0]))
    cas_min = _step_min(sm.get("steps"), "sm-casob")
    degas_min = _step_min(sm.get("steps"), "sm-degas")
    tap_lo, tap_hi = s.get("tap_temp") or [1573, 1576]
    al_kg = float(s.get("al_kg") or 0)
    ladle_al_kg = float(s.get("ladle_al_kg") or 0)
    o0_ppm = float(s.get("o0_ppm") or 500.0)
    o_after_ladle = float(s.get("o_after_ladle_ppm") or 20.0)

    cps = [
        _ck("sm", 1, "到站", "钢包到站 + 钢包脱氧",
            "钢包到站；温度 ≥ 1550°C、重量 80–110 t",
            ("核对钢包号和上一工序成分；到站 O 约 %.0f ppm，先加铝块 %.0f kg 脱氧到 ≤55 ppm，氩气搅拌 3–5 min。"
             % (o0_ppm, ladle_al_kg)) if ladle_al_kg else
            "核对钢包号和上一工序成分；氩气小流量搅拌 2–3 min，确认 CAS-OB 工位空闲。",
            ["重量 80–110 t", "温度 ≥ 1550°C", "钢包无严重粘渣",
             "钢包脱氧后 O ≤55 ppm"],
            c=init_c, probe={"C": round(init_c, 4)}, ref_min=8 if ladle_al_kg else 3,
            kind="state", step_id="sm-arrive"),
        _ck("sm", 2, "CAS-OB", "CAS-OB 吹氧脱碳到 %.2f–%.2f%%" % (c_mid, c_mid + 0.015),
            "C 高于 %.2f%%；电源打开、“吹氧”开关打开、氩气 1.0 Nm³/min" % (c_mid + 0.015),
            "每 2–3 min 点一次成分分析；C 到 %.2f–%.2f%% 立即关“吹氧”，继续氩气搅拌 1–2 min，然后转钢包脱气。"
            % (c_mid, c_mid + 0.015),
            ["C 到 %.2f–%.2f%% 立即关吹氧" % (c_mid, c_mid + 0.015),
             "3 分钟 C 不降 → 检查“吹氧”开关", "Cr/Mn/Si 不被过度氧化"],
            c=c_mid, c_window=[c_mid - 0.01, c_mid + 0.01], probe={"C": round(c_mid, 4)},
            ref_min=cas_min, kind="casob", step_id="sm-casob",
            high="C > %.2f%%：继续吹氧，每 2 min 复测。" % (c_mid + 0.015),
            low="C < %.2f%%：关吹氧，直接转钢包脱气，避免 Cr/Mn 氧化。" % (c_mid - 0.01)),
        _ck("sm", 3, "脱气", "钢包脱气：脱氢 / 脱氮（不再降 C）",
            "C 已到 %.2f–%.2f%%，钢包进罐式脱气器，开最大真空" % (c_mid, c_mid + 0.015),
            "氩气 1.5–2.0 Nm³/min 保持轻微翻动；每 2–3 min 看 C，到 %.3f%% 停真空。" % c_pre,
            ["C 到 %.3f–%.3f%%" % (c_pre, c_pre + 0.015),
             "H ≤%s" % (_fmt_spec(specs.get("H"), 4)),
             "N ≤%s" % (_fmt_spec(specs.get("N"), 4))],
            c=c_pre, c_window=[c_pre, c_pre + 0.015], probe={"C": round(c_pre, 4)},
            ref_min=degas_min, kind="degas", step_id="sm-degas",
            high="8 min 后 C 仍 >%.2f%%：回 CAS-OB 补吹 2–3 min。" % (c_spec[1] - 0.04),
            low="C < %.3f%%：停真空，避免过度脱碳和合金浪费。" % (c_pre - 0.015)),
        _ck("sm", 4, "脱氧", "LF 铝脱氧（精调，先取样再决定）",
            "脱气结束；钢包脱氧后 O 已约 %.0f ppm，先复核" % o_after_ladle,
            "取 O 样：O ≤0.0020% 直接合金化；O 高才按 10 kg 档补铝，搅拌 3–5 min 后复测。",
            ["O ≤0.0020%", "Al ≤0.0040%", "钢包液面覆盖良好"],
            probe={"O_ppm": 20}, ref_min=8, kind="deox", step_id="sm-deox",
            high="O > 20 ppm：按计算量补铝（10 kg 档），再复测。",
            low="O 已 ≤20 ppm：不加铝。LF 精调计划加铝量 %s。" % ("0 kg" if not al_kg else "%.0f kg" % al_kg)),
        _ck("sm", 5, "合金化", "LF 合金化（全部 10 kg 档）",
            "O 合格后；按脱碳后的 C/Si/Mn/Cr 计算",
            "按加料单顺序加：铬铁、锰铁先加（难熔、量大），硼铁/增碳剂最后加；全部加完搅拌 5–8 min 取样。",
            ["C 目标 %s（计划 %.3f%%）" % (_fmt_spec(c_spec), final_c),
             "Mn 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("Mn")), float(final.get("Mn", 0))),
             "Cr 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("Cr")), float(final.get("Cr", 0))),
             "Mo 目标 %s（计划 %.3f%%）" % (_fmt_spec(specs.get("Mo")), float(final.get("Mo", 0))),
             "P/S/Ni/Cu/Nb/Ti/V/B/N/H/O 共 17 元素全部在窗口"],
            c=final_c, c_window=c_spec, probe={"C": round(final_c, 4)},
            ref_min=12, kind="alloy", step_id="sm-alloy",
            high="实测 C 高于计划 0.02% 以上：先查脱碳终点，再按实测重算合金。",
            low="实测 C 低于计划 0.02% 以上：减少增碳类合金，避免 C 冲高。"),
        _ck("sm", 6, "调温", "LF 调温 + 最终取样",
            "合金化完成；目标出站 1573–1576°C",
            "LF 20 MW 少量多次加热，每次 2–3 min 复测；到 1573–1576°C 停，宁低勿高。",
            ["出站温度 1573–1576°C", "17 个元素全部在窗口", "钢包净重 80–110 t"],
            probe={"T": [tap_lo, tap_hi]}, ref_min=10, kind="heat", step_id="sm-temp"),
        _ck("sm", 7, "连铸", "送连铸，结束",
            "17 个元素全部在窗口、温度 1573–1576°C",
            "确认最终成分和温度后送指定铸机；记录实际加料、成分、温度和时间，回填网站校准。",
            ["17 个元素全绿", "温度 1573–1576°C", "时间 ≤1:45", "铸机正确"],
            ref_min=7, kind="cast", step_id="sm-cast"),
    ]

    # 脱硫：EAF 出钢 S 高于 SM 上限时必须专门做，插在脱气之后、脱氧之前
    d = s.get("desulf")
    if d:
        s_hi = (specs.get("S") or [None, None])[1]
        cps.insert(3, _ck(
            "sm", 4, "脱硫", "LF 脱硫（还原渣，S %.4f%% → ≤%.3f%%）" % (d.get("s_in", 0), s_hi or 0),
            "脱气结束、氧化渣扒除；S 约 %.4f%%，成品上限 %.3f%%" % (d.get("s_in", 0), s_hi or 0),
            "加石灰 %d kg + 萤石 %d kg 造还原渣，氩气强搅拌约 %.0f min；S 到 ≤%.3f%% 停。"
            % (d.get("lime_kg", 0), d.get("fluorspar_kg", 0), d.get("time_min", 0), s_hi or 0),
            ["S ≤%.3f%%" % (s_hi or 0), "渣面发亮、流动性好", "搅拌时钢水不裸露"],
            c=init_c, probe={"C": round(init_c, 4)},
            ref_min=d.get("time_min", 10), kind="desulf", step_id="sm-desulf",
            high="S 不降反升：检查是否仍在氧化性气氛，或渣没化开、碱度不够。",
            low="S 已达标：停止加石灰，避免渣量过大带走钢水温度。"))

    for i, cp in enumerate(cps, 1):
        cp["no"] = i
    return cps


def initial_plan(grade_key="sc21_engineering", mass_t=82, safe=True, mix=None,
                 alloy=None, retention=None, pre_c=None, pre_si=0.05,
                 sm_mass=None, sm_initial=None, sm_alloy=None, temp_start=1565.0,
                 power_kwh=None, other_cost_per_t=0.0, energy_price=0.57,
                 alloy_pos=None, sm_grade=None, flux_feo=45.0):
    """生成整炉初始规划（EAF → 二次精炼）。"""
    sm_grade_key = sm_grade or sm_grade_for(grade_key)
    if pre_c is None:
        pre_c = default_pre_c(grade_key)
    feed_specs = _sm_feed_specs(grade_key, sm_grade_key)
    alloy_specs, alloy_notes = _alloy_target_specs(grade_key, sm_grade_key)
    eaf = eaf_plan(grade_key, mass_t, safe, power_kwh, mix, alloy, retention,
                   pre_c, pre_si, other_cost_per_t, energy_price,
                   alloy_pos=alloy_pos, specs_override=feed_specs, flux_feo=flux_feo,
                   alloy_specs_override=alloy_specs)
    if eaf.get("status") != "ok":
        return eaf

    s_eaf = eaf["summary"]
    pre_c = float(pre_c)
    # 以 EAF 段实际选用的停氧锚点为准：合金带碳多时会自动比用户设定更早停氧，
    # 若检查点仍按原设定写，照页面操作会把碳吹过头（例如 4140 预加高碳铬铁后需 0.32 而非 0.37）。
    try:
        chosen_pre = (s_eaf.get("pre") or {}).get("C")
        if chosen_pre is not None:
            pre_c = float(chosen_pre)
    except (TypeError, ValueError):
        pass
    tap_mass = int(round(float(s_eaf.get("tap_mass") or mass_t)))
    sm_mass = int(round(float(sm_mass or tap_mass)))
    base_init = {**DEFAULT_SM_INITIAL, **(s_eaf.get("final") or {})}
    if sm_initial:
        base_init.update({k: v for k, v in sm_initial.items() if v is not None})

    sm = sm_plan(sm_mass, base_init, safe, float(temp_start), sm_alloy,
                 alloy_pos=alloy_pos, sm_grade=sm_grade_key)
    sm_ok = sm.get("status") == "ok"

    checkpoints = _eaf_checkpoints(eaf, float(pre_c))
    if sm_ok:
        checkpoints += _sm_checkpoints(sm)
    # 参考节拍按模拟器实测校准：82 t 约 70 min，每多 1 t 约 +4.4 min
    target_min = 68.0 + 4.4 * (float(mass_t) - 81.4)
    cur_min = sum(float(c.get("ref_min") or 0) for c in checkpoints)
    if cur_min > 0 and target_min > 0:
        k = target_min / cur_min
        for c in checkpoints:
            if c.get("ref_min"):
                c["ref_min"] = round(float(c["ref_min"]) * k, 1)

    c_path = [{
        "key": "charge", "track": "eaf", "label": "装入",
        "c": round(float((s_eaf.get("charge_composition") or {}).get("C", pre_c)), 3),
        "note": "炉料带入 C",
    }, {
        "key": "blow", "track": "eaf", "label": "停氧",
        "c": round(float(pre_c), 3), "note": "目标 %.2f–%.2f" % (float(pre_c), float(pre_c) + 0.01),
    }, {
        "key": "tap", "track": "eaf", "label": "EAF 出钢",
        "c": round(float((s_eaf.get("final") or {}).get("C", pre_c)), 3),
        "note": "合金增碳后",
    }]
    anchors = {
        "blow": round(float(pre_c), 4),
        "tap": round(float((s_eaf.get("final") or {}).get("C", pre_c)), 4),
    }
    if sm_ok:
        s_sm = sm["summary"]
        c_path += [{
            "key": "casob", "track": "sm", "label": "CAS-OB",
            "c": round(float(s_sm.get("c_mid", 0.335)), 3), "note": "吹氧脱碳终点",
        }, {
            "key": "degas", "track": "sm", "label": "脱气",
            "c": round(float(s_sm.get("c_pre", 0.335)), 3), "note": "脱气后（主要脱 H/N）",
        }, {
            "key": "final", "track": "sm", "label": "精炼终点",
            "c": round(float((s_sm.get("final") or {}).get("C", 0.38)), 3),
            "note": "成品 C %s" % _fmt_spec((SM_GRADES.get(sm_grade_key) or {}).get("specs", {}).get("C")),
        }]
        anchors.update({
            "casob": round(float(s_sm.get("c_mid", 0.335)), 4),
            "degas": round(float(s_sm.get("c_pre", 0.335)), 4),
            "final": round(float((s_sm.get("final") or {}).get("C", 0.38)), 4),
        })

    eaf_total = float(s_eaf.get("total_cost") or 0)
    sm_total = float((sm.get("summary") or {}).get("total_cost") or 0) if sm_ok else 0.0
    total = eaf_total + sm_total
    per_t = total / sm_mass if sm_mass else 0.0

    sm_c_pre = float((sm.get("summary") or {}).get("c_pre") or 0.0) if sm_ok else 0.0
    sm_c_mid = float((sm.get("summary") or {}).get("c_mid") or 0.0) if sm_ok else 0.0
    notes = [
        "装料只按整吨，所有添加剂只按 10 kg 档；计划里的时间是参考节拍，不是停点。",
        "EAF 停氧只看 C：到 %.2f–%.2f%% 立即停，碳枪保持 0。" % (pre_c, pre_c + 0.01),
        "停氧后先取样，再按实测成分重算合金；不要照初始计划硬加。",
        "CAS-OB 必须打开“吹氧”开关（只有开/关），只开氩气 C 不会降。",
        ("真空脱气不吹氧，所以 CAS-OB 就要把 C 吹到 %.2f–%.2f%%，脱气只负责脱 H/N。"
         % (sm_c_pre, max(sm_c_pre, sm_c_mid) + 0.01)) if sm_ok else
        "真空脱气不吹氧，脱碳终点按所选钢种的 C 窗口执行。",
        "O ≤20 ppm 不加铝；温度出站宁低勿高，目标 1573–1576°C。",
    ]
    if alloy_notes:
        notes.append(
            "EAF 合金前移：" + "；".join(alloy_notes)
            + "。这几样在 EAF 表比二次精炼表便宜，先在 EAF 加到位，二次精炼只补硅（硅铁在 SM 表更便宜）。"
        )
        if sm_ok:
            notes.append("注意：EAF 加高碳铬铁会带碳（7.82%），所以停氧要比平时更早，"
                         "否则出钢 C 会顶过 EAF 上限。")

    # 二次精炼脱硫提示：EAF 出钢 S 高于 SM 上限时，LF 必须专门脱硫，否则一定超标
    try:
        s_tap = float((s_eaf.get("final") or {}).get("S") or 0.0)
        sm_s_hi = ((SM_GRADES.get(sm_grade_key) or {}).get("specs") or {}).get("S", [None, None])[1]
        if sm_ok and sm_s_hi is not None and s_tap > float(sm_s_hi) + 1e-4:
            from .refine import desulf_slag
            ds = desulf_slag(sm_mass, s_tap, float(sm_s_hi), 80.0)
            notes.append(
                "二次精炼必须脱硫：EAF 出钢 S %.4f%% → 目标 ≤%.3f%%。按 Ls=80 估需脱硫渣约 %.0f kg"
                "（石灰为主 + 萤石调流动性），氩气强搅拌 10–15 min；这一步不做，S 必然超标。"
                % (s_tap, float(sm_s_hi), float(ds.get("slag_kg") or 0))
            )
    except Exception:
        pass
    if not sm_ok:
        notes.insert(0, "二次精炼规划未生成：%s" % (sm.get("message") or "无可行方案"))

    return {
        "status": "ok",
        "track": "full",
        "grade": grade_key,
        "grade_name": eaf.get("grade_name"),
        "sm_grade": sm_grade_key,
        "mass": eaf.get("mass"),
        "safe": bool(safe),
        "source": eaf.get("source") or "optimized",
        "manual_mix": bool(eaf.get("manual_mix")),
        "manual_alloy": bool(eaf.get("manual_alloy")),
        "summary": {
            "mass": eaf.get("mass"),
            "time_target_min": round(target_min, 0),
            "energy_kwh": round(float(s_eaf.get("energy_kwh") or 0), 1),
            "tap_mass": round(float(s_eaf.get("tap_mass") or 0), 1),
            "sm_mass": round(float(sm_mass), 1),
            "sm_grade": sm_grade_key,
            "cost": {
                "scrap": round(float(s_eaf.get("scrap_cost") or 0), 1),
                "eaf_alloy": round(float(s_eaf.get("alloy_cost") or 0), 1),
                "flux": round(float(s_eaf.get("flux_cost") or 0), 1),
                "oxygen": round(float(s_eaf.get("oxygen_cost") or 0), 1),
                "energy": round(float(s_eaf.get("energy_cost") or 0), 1),
                "other": round(float(s_eaf.get("other_cost") or 0), 1),
                "eaf_total": round(eaf_total, 1),
                "sm_alloy": round(float((sm.get("summary") or {}).get("alloy_cost") or 0), 1) if sm_ok else 0.0,
                "sm_total": round(sm_total, 1),
                "total": round(total, 1),
                "per_t": round(per_t, 2),
            },
            "c_path": c_path,
            "c_anchors": anchors,
            "final_eaf": s_eaf.get("final") or {},
            "final_sm": (sm.get("summary") or {}).get("final") or {} if sm_ok else {},
            "checks_eaf": s_eaf.get("checks") or [],
            "checks_sm": (sm.get("summary") or {}).get("checks") or [] if sm_ok else [],
            "out_of_spec_eaf": s_eaf.get("out_of_spec") or [],
            "out_of_spec_sm": (sm.get("summary") or {}).get("out_of_spec") or [] if sm_ok else [],
            "charge_composition": s_eaf.get("charge_composition") or {},
            "mix_keys": s_eaf.get("mix_keys") or {},
            "alloy_eaf_map": s_eaf.get("alloy_map") or {},
            "alloy_sm_map": (sm.get("summary") or {}).get("alloy_map") or {} if sm_ok else {},
            "mix": s_eaf.get("mix") or [],
            "baskets": s_eaf.get("baskets") or [],
            "alloy_eaf": s_eaf.get("alloy") or [],
            "alloy_sm": (sm.get("summary") or {}).get("alloy") or [] if sm_ok else [],
            "fluxes": s_eaf.get("fluxes") or [],
            "tap_temp": s_eaf.get("tap_temp") or [1630, 1660],
            "furnace_temp": s_eaf.get("furnace_temp") or [1630, 1660],
            "sm_temp": (sm.get("summary") or {}).get("tap_temp") or [1573, 1576],
            "oxy_time": _step_min(eaf.get("steps"), "eaf-blow"),
            "cas_time": _step_min((sm.get("steps") or []), "sm-casob"),
            "degas_time": _step_min((sm.get("steps") or []), "sm-degas"),
        },
        "checkpoints": checkpoints,
        "plans": {"eaf": eaf, "sm": sm if sm_ok else None},
        "notes": notes,
    }
