# -*- coding: utf-8 -*-
"""二次炼钢与 EAF 精炼公式（全部来自两份手册第 5/9 章）。"""

import math


def _num(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def liquidus(comp):
    """液相线温度 °C（SM 手册 式7-1/7-2）。"""
    C = _num(comp.get("C"))
    Mn = _num(comp.get("Mn"))
    Si = _num(comp.get("Si"))
    S = _num(comp.get("S"))
    P = _num(comp.get("P"))
    Cr = _num(comp.get("Cr"))
    Al = _num(comp.get("Al"))
    Ni = _num(comp.get("Ni"))
    V = _num(comp.get("V"))
    Mo = _num(comp.get("Mo"))
    if C < 0.5:
        t = (1537 - 73.1 * C - 4 * Mn - 14 * Si - 45 * S - 30 * P
             - 1.5 * Cr - 2.5 * Al - 3.5 * Ni - 4 * V - 5 * Mo)
        formula = "7-1 (C<0.5%)"
    else:
        t = (1531 - 61.5 * C - 4 * Mn - 14 * Si - 45 * S - 30 * P
             - 1.5 * Cr - 2.5 * Al - 3.5 * Ni - 4 * V - 5 * Mo)
        formula = "7-2 (C>0.5%)"
    return {"liquidus": round(t, 1), "formula": formula}


def deox_al(mass_t, o_ppm, target_al=0.0, al_content=98.0, recovery=60.0):
    """铝脱氧（SM 9.2 / EAF 5.4）。"""
    mass_kg = _num(mass_t) * 1000.0
    o_pct = _num(o_ppm) / 10000.0
    al_deox = 54.0 / 48.0 * o_pct
    al_total = al_deox + _num(target_al)
    m = al_total * mass_kg / (_num(al_content) * _num(recovery) / 100.0)
    reacted = al_deox * mass_kg / (_num(al_content) * _num(recovery) / 100.0)
    return {
        "o_pct": round(o_pct, 6),
        "al_deox_pct": round(al_deox, 5),
        "al_target_pct": round(_num(target_al), 5),
        "al_total_pct": round(al_total, 5),
        "alloy_mass_kg": round(m, 1),
        "al_reacted_kg": round(reacted, 1),
        "heat_C": round(reacted / 100.0 * 12.0, 1),
        "note": "按 2Al+3O→Al2O3，54/48=1.125；每 100 kg Al 反应升温约 12°C",
    }


# 钢包脱氧剂（SM 表 7-2 / 7-3）：元素含量、价格、回收率
DEOX_REAGENTS = {
    "al_pebble": {
        "name": "铝块（98% Al）", "comp": {"Al": 98.0}, "price": 1400,
        "rec": {"Al": 90.0}, "note": "最常用；便宜，适合钢包脱氧",
    },
    "al_wire": {
        "name": "铝线（98% Al）", "comp": {"Al": 98.0}, "price": 2100,
        "rec": {"Al": 90.0}, "note": "喂线，回收率稳定，成本高",
    },
    "sica_powder": {
        "name": "硅钙粉（50% Ca + 50% Si）", "comp": {"Ca": 50.0, "Si": 50.0}, "price": 1218,
        "rec": {"Ca": 15.0, "Si": 98.0}, "note": "脱氧 + 夹杂物变性；会带 Si",
    },
    "sica_wire": {
        "name": "硅钙线（50% Ca + 50% Si）", "comp": {"Ca": 50.0, "Si": 50.0}, "price": 1540,
        "rec": {"Ca": 15.0, "Si": 98.0}, "note": "喂线，成本高；会带 Si",
    },
    "fesi75": {
        "name": "硅铁 75%", "comp": {"Si": 75.0}, "price": 770,
        "rec": {"Si": 98.0}, "note": "只适合对 Si 不敏感的钢种；会明显带 Si",
    },
}

# 每 kg 元素脱氧需要的 O（kg）：Al 48/54、Si 32/28、Ca 16/40
_O_PER_KG_ELEMENT = {"Al": 48.0 / 54.0, "Si": 32.0 / 28.0, "Ca": 16.0 / 40.0}
_OXIDE_PER_KG_O = {"Al": 102.0 / 48.0, "Si": 60.0 / 32.0, "Ca": 56.0 / 16.0}


def deox_ladle(mass_t, o_ppm, target_o_ppm=20.0, reagent="al_pebble"):
    """钢包脱氧：按 O 降量计算脱氧剂加入量（SM 9.2）。

    与 `deox_al` 的区别：
    - deox_al 按“目标残铝”反算，包含脱氧铝 + 合金化残铝；
    - 本函数按“初始 O → 目标 O”反算，只做脱氧，可选铝块/铝线/硅钙/硅铁。
    """
    mass_kg = max(1.0, _num(mass_t, 90.0) * 1000.0)
    o0 = max(0.0, _num(o_ppm, 450.0))
    ot = max(0.0, _num(target_o_ppm, 20.0))
    key = reagent if reagent in DEOX_REAGENTS else "al_pebble"
    rg = DEOX_REAGENTS[key]

    o_remove = max(0.0, o0 - ot) / 1e6 * mass_kg
    capacity = 0.0
    oxide_kg = 0.0
    element_kg = {}
    for e, pct in rg["comp"].items():
        rec = _num(rg["rec"].get(e), 100.0) / 100.0
        stoich = _O_PER_KG_ELEMENT.get(e, 0.0)
        eff = pct / 100.0 * rec * stoich
        capacity += eff
        element_kg[e] = None  # 占位，后面按实际加入量填
    theoretical = o_remove / capacity if capacity > 0 else 0.0

    def eval_amount(amount):
        elems = {}
        oxide = 0.0
        for e, pct in rg["comp"].items():
            rec = _num(rg["rec"].get(e), 100.0) / 100.0
            elems[e] = amount * pct / 100.0 * rec
            o_used = amount * pct / 100.0 * rec * _O_PER_KG_ELEMENT.get(e, 0.0)
            oxide += o_used * _OXIDE_PER_KG_O.get(e, 0.0)
        o_after_v = max(0.0, o0 - amount * capacity / mass_kg * 1e6)
        al_add = elems.get("Al", 0.0)
        al_react = min(al_add, o_remove / _O_PER_KG_ELEMENT["Al"] if _O_PER_KG_ELEMENT["Al"] else 0.0)
        res_al = max(0.0, al_add - al_react) / mass_kg * 100.0
        return {"amount": amount, "elems": elems, "oxide": oxide,
                "o_after": o_after_v, "al_add": al_add, "al_react": al_react,
                "res_al": res_al}

    # 10 kg 档搜索：优先不过量（Al 残余 ≤0.004%），再选最接近目标 O 的档位。
    lo = max(0, int(theoretical // 10) * 10 - 10)
    hi = int(math.ceil(theoretical / 10) * 10 + 10)
    candidates = sorted({a for a in range(lo, hi + 1, 10) if a >= 0})
    if not candidates:
        candidates = [0]
    def cand_score(ev):
        penalty = 0.0
        if ev["elems"].get("Al") and ev["res_al"] > 0.004 + 1e-9:
            penalty += 1e6
        # 目标 O 优先；同分时取加入量小的
        return (penalty, abs(ev["o_after"] - ot), ev["amount"])
    chosen = min((eval_amount(a) for a in candidates), key=cand_score)
    actual = chosen["amount"]
    element_kg = chosen["elems"]
    oxide_kg = chosen["oxide"]
    o_after = chosen["o_after"]
    al_added = chosen["al_add"]
    al_reacted = chosen["al_react"]
    residual_al = chosen["res_al"]
    si_pickup = element_kg.get("Si", 0.0) / mass_kg * 100.0
    ca_pickup = element_kg.get("Ca", 0.0) / mass_kg * 100.0
    heat = al_reacted / 100.0 * 12.0 if al_added else 0.0
    o_removed_actual = actual * capacity

    return {
        "status": "ok",
        "reagent": key,
        "reagent_name": rg["name"],
        "mass_t": round(mass_kg / 1000.0, 2),
        "o_ppm": round(o0, 1),
        "target_o_ppm": round(ot, 1),
        "o_after_ppm": round(o_after, 1),
        "o_remove_kg": round(o_remove, 2),
        "o_removed_kg": round(o_removed_actual, 2),
        "capacity_kg_o_per_kg": round(capacity, 4),
        "reagent_kg": round(theoretical, 1),
        "reagent_round_kg": round(actual, 0),
        "cost": round(actual * rg["price"] / 1000.0, 1),
        "oxide_kg": round(oxide_kg, 1),
        "al_added_kg": round(al_added, 1),
        "al_reacted_kg": round(al_reacted, 1),
        "residual_al_pct": round(residual_al, 4),
        "si_pickup_pct": round(si_pickup, 4),
        "ca_pickup_pct": round(ca_pickup, 4),
        "heat_C": round(heat, 1),
        "note": "按元素与 O 的化学计量和回收率计算；铝脱氧 2Al+3O→Al2O3，硅脱氧 Si+2O→SiO2，钙脱氧 Ca+O→CaO。",
    }


def desulf_slag(mass_t, s0, s_aim, Ls):
    """达到目标硫所需脱硫渣量（SM 式9-18，返回吨）。"""
    s0 = _num(s0)
    s_aim = _num(s_aim)
    Ls = _num(Ls)
    if s_aim <= 0 or Ls <= 0:
        return {"error": "目标硫与 Ls 必须大于 0"}
    ws = _num(mass_t) / Ls * ((s0 - s_aim) / s_aim)
    return {"slag_t": round(max(0.0, ws), 3), "slag_kg": round(max(0.0, ws) * 1000, 1)}


def desulf_time(mass_t, s0, s_t, Ls, slag_t, epsilon):
    """脱硫动力学时间（SM 式9-19~9-21，分钟）。"""
    s0, s_t, Ls, ws, eps = map(_num, (s0, s_t, Ls, slag_t, epsilon))
    if min(s0, s_t, Ls, ws, eps) <= 0:
        return {"error": "参数必须大于 0"}
    ks = 0.031 * eps ** 0.25 if eps < 70 else 8e-6 * eps ** 2.1
    wm = _num(mass_t)
    ratio = wm / ws / Ls
    inner = (s_t / s0) * (1 + ratio) - ratio
    if inner <= 0:
        return {"error": "目标硫低于该渣量/分配比下的平衡极限，需增加渣量"}
    t = math.log(inner) / (-ks * (1 + ratio))
    return {"ks": round(ks, 4), "slag_ratio": round(ratio, 4),
            "time_min": round(t, 1), "equilibrium_s": round(s0 / (1 + ratio), 5)}


def decarb(mass_t, c_i, c_f, c_eq, Q=80000.0, q=18.0, rho=7200.0, kc_override=None):
    """RH 脱碳（SM 9.3，式9-15/9-14）。Q kg/min，q m3/min。"""
    c_i, c_f, c_eq = map(_num, (c_i, c_f, c_eq))
    mass_kg = _num(mass_t) * 1000.0
    Vb = mass_kg / rho
    if kc_override:
        kc = _num(kc_override)
    else:
        kc = (Q / (Vb * rho)) * (q / (Q / rho + q))
    if c_f <= c_eq:
        return {"kc": round(kc, 4), "time_min": None,
                "error": "目标碳低于平衡碳，无法达到"}
    if c_i <= c_f:
        return {"kc": round(kc, 4), "time_min": 0.0}
    t = -1.0 / kc * math.log((c_f - c_eq) / (c_i - c_eq))
    return {"kc": round(kc, 4), "Vb": round(Vb, 2), "time_min": round(t, 1),
            "note": "手册例题 kc=0.164 min⁻¹ 对应 t≈27 min；按公式复算值可能略有差异"}


def h_equilibrium(p_h2_atm):
    """1600°C 氢平衡浓度 ppm（SM 表9-1 / Sieverts）。"""
    p = _num(p_h2_atm)
    if p < 0:
        return {"error": "压力不能为负"}
    return {"h_ppm": round(25.6 * math.sqrt(p), 3)}


def hydrogen_time(h_i, h_f, h_eq, kH):
    """除氢时间（SM 式9-25，分钟）。"""
    hi, hf, he, k = map(_num, (h_i, h_f, h_eq, kH))
    if k <= 0:
        return {"error": "kH 必须大于 0"}
    if hf <= he:
        return {"time_min": None, "error": "目标氢低于平衡氢"}
    if hi <= hf:
        return {"time_min": 0.0}
    return {"time_min": round(-1.0 / k * math.log((hf - he) / (hi - he)), 1)}


def kH_tank(argon_nm3min):
    return {"kH": round(0.0576 * _num(argon_nm3min) + 0.02, 4)}


def stir_power(V_nm3min, temp_C, mass_t, H_m, P0_atm=1.0):
    """钢包搅拌功率密度 W/t（SM 式9-26）。"""
    V, T, M, H, P0 = _num(V_nm3min), _num(temp_C) + 273.15, _num(mass_t), _num(H_m), _num(P0_atm)
    if min(V, T, M, H, P0) <= 0:
        return {"error": "参数必须大于 0"}
    eps = 14.23 * (V * T / M) * math.log10((1 + H) / (1.48 * P0))
    return {"epsilon": round(eps, 2),
            "regime": "强搅拌 (ε>70)" if eps > 70 else "常规搅拌"}


def heat_time(mass_t, dT, power_kw, eta=0.55, cp=0.22):
    """钢包炉电加热时间（SM 式9-33）。"""
    m, dt, P, e, c = map(_num, (mass_t, dT, power_kw, eta, cp))
    if P <= 0 or e <= 0:
        return {"error": "功率与效率必须大于 0"}
    hours = m * c * dt / (e * P)
    return {"hours": round(hours, 4), "minutes": round(hours * 60, 2),
            "energy_kwh": round(P * hours, 1)}


def charge_silica(mass_t, mix, si_retained_pct=0.05):
    """按炉料配比计算进入渣相的 SiO2 来源。

    返回 (si_oxidized_pct, sio2_gangue_kg)：
    - si_oxidized_pct：被氧化进渣的 Si 占钢水质量的百分比（总 Si 输入 - 留在钢中的 Si）
    - sio2_gangue_kg：废钢/DRI 自带脉石 SiO2（DRI 按 4.8%，见 data.py 校准说明）

    实炉校准 实炉校准：90 t（68 t 1号捆包 + 21 t DRI + 1 t 炉尘）
    → Si 氧化约 0.037%，DRI 脉石 SiO2 约 1,008 kg。
    """
    from .data import SCRAP_BY_KEY

    mass = max(_num(mass_t, 90.0), 1.0)
    si_in = 0.0
    gangue = 0.0
    for key, tons in (mix or {}).items():
        scrap = SCRAP_BY_KEY.get(key)
        if not scrap:
            continue
        m_kg = _num(tons) * 1000.0
        si_in += m_kg * _num((scrap.get("comp") or {}).get("Si")) / 100.0
        gangue += m_kg * _num(scrap.get("sio2")) / 100.0
    si_retained = mass * 1000.0 * _num(si_retained_pct, 0.05) / 100.0
    si_ox = max(0.0, si_in - si_retained)
    return si_ox / (mass * 1000.0) * 100.0, gangue


def _slag_state(mass_t, si_pct, lime_kg, dolo_kg, fluo_kg, feo_pct,
                sio2_gangue_kg=0.0, other_pct=9.0):
    """炉渣平衡：CaO/SiO2 碱度、MgO%、FeO%。

    SiO2 三个来源：Si 氧化、炉料脉石（DRI）、渣料本身。
    FeO 由氧枪供氧量决定，这里按目标 FeO% 反算；其余氧化物（MnO/Al2O3/Cr2O3/
    P2O5/CaF2 等）按 9% 计入，这个比例是按 实炉校准 终渣分析的余额校准的。
    """
    mass_kg = _num(mass_t) * 1000.0
    si_kg = mass_kg * _num(si_pct) / 100.0
    sio2_si = si_kg * 60.0 / 28.0
    cao = lime_kg * 0.9488 + dolo_kg * 0.59345 + fluo_kg * 0.20
    sio2_flux = lime_kg * 0.021 + dolo_kg * 0.02 + fluo_kg * 0.20
    sio2 = sio2_si + sio2_flux + _num(sio2_gangue_kg)
    mgo = dolo_kg * 0.385 + fluo_kg * 0.20
    non_feo = cao + sio2 + mgo
    f = min(max(_num(feo_pct), 0.0), 90.0) / 100.0
    q = min(max(_num(other_pct, 9.0), 0.0), 50.0) / 100.0
    total = non_feo / (1 - f - q) if f + q < 1 else 0.0
    feo = total * f
    other = total * q
    return {
        "cao": cao, "sio2": sio2, "mgo": mgo, "feo": feo, "other": other,
        "total": total,
        "basicity": cao / sio2 if sio2 else 0.0,
        "mgo_pct": mgo / total * 100.0 if total else 0.0,
        "feo_pct": feo / total * 100.0 if total else 0.0,
        "sio2_from_si": sio2_si, "sio2_from_flux": sio2_flux,
        "sio2_gangue": _num(sio2_gangue_kg),
    }


def slag_calculator(mass_t, si_oxidized_pct, lime_t=0.0, dolomite_t=0.0, fluorspar_t=0.0,
                    target_basicity=1.70, target_mgo=8.2, target_feo=37.0,
                    sio2_gangue_kg=0.0, other_pct=9.0):
    """EAF 造渣：碱度 / MgO / FeO 核算，并给出一次性加入的石灰+白云石推荐量。

    推荐值按 10 kg 档网格搜索，同时逼近目标碱度与目标 MgO%。
    FeO 由氧枪供氧控制，默认 37%（实炉校准 实炉 37.117%）；其他氧化物按 9% 计。
    """
    target_basicity = _num(target_basicity, 1.70)
    target_mgo = _num(target_mgo, 8.2)
    target_feo = _num(target_feo, 37.0)
    lime = _num(lime_t) * 1000.0
    dolo = _num(dolomite_t) * 1000.0
    fluo = _num(fluorspar_t) * 1000.0
    st = _slag_state(mass_t, si_oxidized_pct, lime, dolo, fluo, target_feo,
                     sio2_gangue_kg, other_pct)

    # 补石灰到目标碱度的解析解（考虑石灰自带 2.1% SiO2）
    denom = 0.9488 - 0.021 * target_basicity
    need = (target_basicity * st["sio2"] - st["cao"]) / denom if abs(denom) > 1e-6 else 0.0

    # 10 kg 档网格：石灰 0–3000 kg，白云石 0–3000 kg，萤石固定
    best = None
    for lk in range(0, 3001, 10):
        for dk in range(0, 3001, 10):
            cand = _slag_state(mass_t, si_oxidized_pct, lk, dk, fluo, target_feo,
                               sio2_gangue_kg, other_pct)
            if cand["total"] <= 1:
                continue
            err = ((cand["basicity"] - target_basicity) / max(target_basicity, 0.2)) ** 2 * 2.0
            err += ((cand["mgo_pct"] - target_mgo) / max(target_mgo, 1.0)) ** 2
            if best is None or err < best[0]:
                best = (err, lk, dk, cand)
    rec = None
    if best:
        _, lk, dk, cand = best
        rec = {
            "lime_kg": round(lk, 0), "dolomite_kg": round(dk, 0),
            "fluorspar_kg": round(fluo, 0),
            "basicity": round(cand["basicity"], 2),
            "mgo_pct": round(cand["mgo_pct"], 2),
            "feo_pct": round(cand["feo_pct"], 2),
            "slag_kg": round(cand["total"], 0),
            "batch": "一次加入",
        }

    mg_curve = []
    for feo in (20, 25, 30, 35, 37, 40, 45):
        c = _slag_state(mass_t, si_oxidized_pct, lime, dolo, fluo, feo,
                        sio2_gangue_kg, other_pct)
        mg_curve.append({"feo": feo, "mgo_pct": round(c["mgo_pct"], 2)})

    return {
        "mg_curve": mg_curve,
        "sio2_from_si_kg": round(st["sio2_from_si"], 1),
        "sio2_from_flux_kg": round(st["sio2_from_flux"], 1),
        "sio2_gangue_kg": round(st["sio2_gangue"], 1),
        "sio2_total_kg": round(st["sio2"], 1),
        "cao_kg": round(st["cao"], 1), "sio2_kg": round(st["sio2"], 1),
        "mgo_kg": round(st["mgo"], 1), "feo_kg": round(st["feo"], 1),
        "other_kg": round(st["other"], 1),
        "slag_kg": round(st["total"], 1),
        "basicity": round(st["basicity"], 2),
        "mgo_pct": round(st["mgo_pct"], 2),
        "feo_pct": round(st["feo_pct"], 2),
        "lime_to_target_kg": round(max(0.0, need), 1),
        "target_basicity": target_basicity,
        "target_mgo": target_mgo,
        "target_feo": target_feo,
        "recommend": rec,
        "note": "FeO 由氧枪控制（10–50%，实炉约 37%）；石灰/白云石/萤石一次加入，不再分两批。",
    }


def temperature_plan(mass_t, tap_temp, steps):
    """温度行程：steps 为 [{type, ...}]，返回逐步温度。

    type: hold(min), alloy(t), stir(min), degas(min), lrf(min,power), al_heat(kg), chem_heat(kg)
    """
    t = _num(tap_temp)
    rows = []
    for s in steps or []:
        typ = s.get("type")
        dt = 0.0
        label = ""
        if typ == "hold":
            mins = _num(s.get("minutes"))
            dt = -0.5 * mins
            label = f"钢包等待/运输 {mins:g} min"
        elif typ == "alloy":
            tons = _num(s.get("tonnes"))
            dt = -6.0 * tons
            label = f"加合金 {tons:g} t"
        elif typ == "stir":
            mins = _num(s.get("minutes"))
            dt = -1.5 * mins
            label = f"氩气搅拌 {mins:g} min"
        elif typ == "degas":
            mins = _num(s.get("minutes"))
            dt = -1.0 * mins
            label = f"真空脱气 {mins:g} min"
        elif typ == "lrf":
            mins = _num(s.get("minutes"))
            pct = _num(s.get("power_pct"), 100) / 100.0
            dt = 3.0 * pct * mins
            label = f"钢包炉加热 {mins:g} min @ {pct*100:.0f}%"
        elif typ == "al_heat":
            kg = _num(s.get("kg"))
            dt = 12.0 * kg / 100.0
            label = f"铝化学升温 {kg:g} kg Al"
        rows.append({"label": label, "delta": round(dt, 1), "temp": round(t + dt, 1)})
        t += dt
    return {"final_temp": round(t, 1), "steps": rows}
