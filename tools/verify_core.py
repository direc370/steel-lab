# -*- coding: utf-8 -*-
"""核心算法自检脚本：校验 LP / 10kg 取整 / 联合优化 / 动态建议。

用法：py -X utf8 tools/verify_core.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.data import EAF_GRADES, SM_GRADES, SCRAPS, EAF_ADDITIVES, SM_ADDITIVES
from engine.plan import initial_plan
from engine.wizard import round_plan
from engine.optimizer import optimize_total
from engine.alloy_lp import optimize_alloy_lp
from engine.dynamics import advise


def check(cond, msg):
    print(("  [OK] " if cond else "  [!!] ") + msg)
    return bool(cond)


def main():
    ok = True
    print("=== 1. initial_plan 全流程（82 t 工程钢）===")
    p = initial_plan("sc21_engineering", 82, other_cost_per_t=0.0, alloy_pos=0.15)
    ok &= check(p.get("status") == "ok", f"status={p.get('status')}")
    if p.get("status") == "ok":
        s = p["summary"]
        print(f"  total ${s['cost']['total']}  = ${s['cost']['per_t']}/t  time {s['time_target_min']} min")
        print("  mix:", s["mix_keys"])
        print("  EAF 合金:", s["alloy_eaf_map"])
        print("  SM  合金:", s["alloy_sm_map"])
        ok &= check(all(float(v).is_integer() for v in s["mix_keys"].values()), "炉料全部整吨")
        ok &= check(all(float(v) % 10 == 0 for v in s["alloy_eaf_map"].values()), "EAF 合金全部 10 kg 整数倍")
        ok &= check(all(float(v) % 10 == 0 for v in s["alloy_sm_map"].values()), "SM 合金全部 10 kg 整数倍")
        ok &= check(not s["out_of_spec_eaf"], "EAF 成分全在窗口")
        ok &= check(not s["out_of_spec_sm"], "SM 成分全在窗口")

    print("\n=== 2. optimize_total 联合寻优（整吨 + 10 kg）===")
    limits = {k: {"enabled": True} for k in ("no1_heavy", "shredded", "no1_bundle", "eaf_dust")}
    tot = optimize_total("sc21_engineering", 82.0, limits=limits,
                         round_tons=True, alloy_step=10, alloy_margin=0.02)
    ok &= check(tot.get("status") == "ok", f"status={tot.get('status')}")
    if tot.get("status") == "ok":
        b = tot["best"]
        e = tot.get("exec") or {}
        print(f"  LP best ${b['total_per_t']}/t @ c_pre={b['c_pre']}")
        if e:
            print(f"  exec  ${e['total_per_t']}/t @ c_pre={e['c_pre']}  Δ={e.get('delta_vs_lp')}")
            print("  exec 炉料:", e["charge"]["mix"])
            print("  exec 合金:", [(a["key"], a["mass"]) for a in e["alloy"]["additions"]])
            ok &= check(all(float(v).is_integer() for v in e["charge"]["mix"].values()), "exec 炉料整吨")
            ok &= check(all(float(a["mass"]) % 10 == 0 for a in e["alloy"]["additions"]), "exec 合金 10 kg 档")
            ok &= check(not e["out_of_spec"], "exec 无越限")

    print("\n=== 3. SM 全局 LP + round_plan ===")
    g_sm = SM_GRADES["sc21_refining"]
    init_sm = {"C": 0.335, "Si": 0.01, "Mn": 0.52, "P": 0.008, "S": 0.018, "Cr": 1.48,
               "Mo": 0.023, "Ni": 0.077, "Cu": 0.065, "Al": 0.003, "O": 0.048,
               "H": 0.0007, "N": 0.009}
    lp = optimize_alloy_lp(82.0, init_sm, g_sm["specs"], catalog=SM_ADDITIVES,
                           profile="ladle", margin=0.02)
    ok &= check(lp.get("status") == "ok", f"LP status={lp.get('status')}")
    if lp.get("status") == "ok":
        rp = round_plan(82.0, init_sm, {a["key"]: a["mass"] for a in lp["additions"]},
                        g_sm["specs"], track="sm", profile="ladle", step=10.0,
                        repair=True, margin=0.02)
        print(f"  LP ${lp['cost']:.1f} -> 10kg ${rp['cost']:.1f}  out_of_spec={rp['out_of_spec']}")
        print("  adds:", [(a["key"], a["mass"]) for a in rp["additions"]])
        only_oh = [w for w in rp["out_of_spec"] if not w.startswith(("H ", "O "))]
        ok &= check(not only_oh, "10 kg 取整后无合金可修正的越限（H/O 由脱气脱氧处理）")
        ok &= check(all(float(a["mass"]) % 10 == 0 for a in rp["additions"]), "全部 10 kg 档")

    print("\n=== 4. dynamics.advise（CAS-OB 全元素实时定量）===")
    comp = {"C": 0.42, "Si": 0.01, "Mn": 0.50, "Cr": 1.48, "Mo": 0.023, "Ni": 0.077,
            "P": 0.009, "S": 0.022, "O": 0.055, "H": 0.0008, "N": 0.0095, "Al": 0.004,
            "Cu": 0.065, "Nb": 0.002, "Ti": 0.001, "V": 0.002, "Sn": 0.008}
    adv = advise({"track": "sm", "state": {
        "grade": "sc21_refining", "mass": 82.0, "temp": 1620.0, "stage": "casob",
        "comp": comp, "target_c": 0.335, "alloy_margin": 0.02, "horizon": 20.0,
    }})
    pred = adv.get("prediction") or {}
    print("  c_stop_target:", pred.get("c_stop_target"), " c_pickup:", pred.get("c_pickup"))
    da = adv.get("alloy_plan") or pred.get("dynamic_alloy") or {}
    print("  dyn_alloy:", [(a.get("key"), a.get("kg", a.get("mass"))) for a in da.get("additions", [])])
    print("  cost $:", da.get("total_cost_usd", da.get("cost")), " out_of_spec:", da.get("out_of_spec"))
    print("  stop.elements:", [(o.get("element"), o.get("status")) for o in (adv.get("stop") or {}).get("elements", [])][:8])
    for act in adv.get("actions", [])[:14]:
        print("   -", act.get("key"), "|", str(act.get("label"))[:110])
    ok &= check(bool(adv.get("actions")), "有动态操作建议")
    ok &= check(all(float(a.get("kg", a.get("mass", 0))) % 10 == 0 for a in da.get("additions", [])), "动态合金 10 kg 档")
    temp_acts = [a for a in adv.get("actions", [])
                 if a.get("key") in ("heat", "sample") or "降温" in str(a.get("label", ""))]
    ok &= check(not temp_acts, "CAS-OB 1620°C 不再误报 LF 出站温度/降温分钟数")

    print("\n=== 5. P1-2 回归：多钢种 SM 目标（AISI 4140）===")
    p4140 = initial_plan("engineering", 82, other_cost_per_t=0.0)
    ok &= check(p4140.get("status") == "ok", f"status={p4140.get('status')} {p4140.get('message', '')}")
    if p4140.get("status") == "ok":
        s4140 = p4140["summary"]
        sm_cps = [c for c in p4140.get("checkpoints", []) if c["track"] == "sm"]
        print("  sm_grade:", p4140.get("sm_grade"), " SM 检查点:", len(sm_cps))
        print("  final_sm:", {k: s4140["final_sm"].get(k) for k in ("C", "Si", "Mn", "Cr", "Mo")})
        ok &= check(p4140.get("sm_grade") == "engineering" and len(sm_cps) >= 7,
                    "按钢种映射到 SM engineering 并生成 7 个检查点")
        main_oos = [w for w in (s4140.get("out_of_spec_sm") or [])
                    if str(w).split()[0] in ("C", "Si", "Mn", "Cr", "Mo")]
        ok &= check(not main_oos, "C/Si/Mn/Cr/Mo 全部在 SM 窗口")

    print("\n=== 6. 初始规划沿用用户手工炉料/合金 ===")
    manual_mix = {"no1_bundle": 66, "dri": 20, "eaf_dust": 1, "turnings": 1}
    manual_alloy = {"cr_ore": 1600, "femn_hc": 400, "fesi75hp": 120, "sic": 50}
    p_manual = initial_plan("sc21_engineering", 88, mix=manual_mix, alloy=manual_alloy,
                            other_cost_per_t=0.0, alloy_pos=0.15)
    ok &= check(p_manual.get("status") == "ok",
                f"status={p_manual.get('status')} {p_manual.get('message', '')}")
    if p_manual.get("status") == "ok":
        got_mix = {k: float(v) for k, v in p_manual["summary"]["mix_keys"].items()}
        got_alloy = {k: float(v) for k, v in p_manual["summary"]["alloy_eaf_map"].items()}
        print("  requested mix:", manual_mix, "->", got_mix)
        print("  requested alloy:", manual_alloy, "->", got_alloy)
        ok &= check(got_mix == {k: float(v) for k, v in manual_mix.items()},
                    "初始规划原样保留用户炉料（不再被成本优化替换）")
        ok &= check(got_alloy == {k: float(v) for k, v in manual_alloy.items()},
                    "初始规划原样保留用户 EAF 合金")

    print("\n=== 7. 白云石 FeO 稀释补偿 ===")
    p37 = initial_plan("sc21_engineering", 82, other_cost_per_t=0.0, flux_feo=37)
    p50 = initial_plan("sc21_engineering", 82, other_cost_per_t=0.0, flux_feo=50)
    d37 = next((x["mass"] for x in p37["summary"]["fluxes"] if x["key"] == "dolomite"), 0)
    d50 = next((x["mass"] for x in p50["summary"]["fluxes"] if x["key"] == "dolomite"), 0)
    print(f"  FeO 37% -> 白云石 {d37} kg；FeO 50% -> 白云石 {d50} kg")
    ok &= check(d50 > d37 + 200, "FeO 越高白云石越多，且至少多 200 kg")

    print("\n=== 8. 工序顺序校验：先满足 EAF，再满足二次精炼 ===")
    # EAF 出钢必须满足 EAF 自己的规格；SM 只负责在自己的窗口里收口。
    # 合金成本前移（Mn/Cr/Mo 在 EAF 加）只能影响"往哪个方向加"，不能放松 EAF 的合规。
    for gkey, skey in (("sc21_engineering", "sc21_refining"), ("engineering", "engineering")):
        pg = initial_plan(gkey, 82, other_cost_per_t=0.0)
        if pg.get("status") != "ok":
            ok &= check(False, f"{gkey} status={pg.get('status')}")
            continue
        sg = pg["summary"]
        fe, fs = sg["final_eaf"] or {}, sg["final_sm"] or {}
        eaf_spec, sm_spec = EAF_GRADES[gkey]["specs"], SM_GRADES[skey]["specs"]
        bad_eaf = [e for e, (lo, hi) in eaf_spec.items() if e in fe and (
            (lo is not None and float(fe[e]) < float(lo) - 1e-4) or
            (hi is not None and float(fe[e]) > float(hi) + 1e-4))]
        # SM 只校验合金能控制的元素；C 由 CAS-OB、S 由 LF、O/N/H 由脱气负责
        ctrl = ("C", "Si", "Mn", "Cr", "Mo")
        bad_sm = [e for e in ctrl if e in fs and sm_spec.get(e) and (
            (sm_spec[e][0] is not None and float(fs[e]) < float(sm_spec[e][0]) - 1e-4) or
            (sm_spec[e][1] is not None and float(fs[e]) > float(sm_spec[e][1]) + 1e-4))]
        print(f"  {gkey}: EAF 出钢 {({k: round(float(v), 4) for k, v in fe.items() if k in ctrl})}")
        ok &= check(not bad_eaf, f"{gkey} EAF 出钢满足 EAF 规格" + (f"：{bad_eaf}" if bad_eaf else ""))
        ok &= check(not bad_sm, f"{gkey} SM 出站满足 SM 窗口" + (f"：{bad_sm}" if bad_sm else ""))

    print("\n==== 结论:", "全部通过" if ok else "存在未通过项", "====")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
