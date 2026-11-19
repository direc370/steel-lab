# -*- coding: utf-8 -*-
"""自检脚本：python tools/selftest.py"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine.simplex import minimize
from engine.charge import optimize_charge
from engine.alloys import calculate_additions
from engine.refine import deox_al, deox_ladle, desulf_slag, desulf_time, heat_time, liquidus, slag_calculator, charge_silica
from engine.kb import KB, offline_answer
from engine.agent import offline_chat
from engine.optimizer import optimize_total
from engine.alloy_lp import optimize_alloy_lp
from engine.wizard import eaf_plan, sm_plan
from engine.plan import initial_plan
from engine.dynamics import advise as process_advise
from engine.data import SM_ADDITIVES, RECOVERY, SM_GRADES

ok = 0
fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✓ {name}")
    else:
        fail += 1
        print(f"  ✗ {name}  {detail}")


print("== 单纯形 ==")
r = minimize([160, 140], [[1, 1]], [90], [[1, 1]], [90], [(0, 60), (0, 80)])
check("两料 LP", r.status == "optimal" and abs(r.x[0] - 10) < 1e-6 and abs(r.value - 12800) < 1e-6,
      f"{r.status} {r.x} {r.value}")

print("== 手册例题 ==")
prof = {k: v for k, v in RECOVERY["ladle"].items() if k != "label"}
a = calculate_additions(250, {"Mn": 0.12, "C": 0.05}, {"Mn": 1.4}, SM_ADDITIVES, prof, limits={})
m = a["additions"][0]["mass"] if a["additions"] else 0
check("HCFeMn 4403 kg", abs(m - 4403) < 15, f"{m} kg")
d = deox_al(250, 450, 0.04, 98, 60)
check("铝脱氧 385 kg / 0.0906%", abs(d["alloy_mass_kg"] - 386) < 3 and abs(d["al_total_pct"] - 0.0906) < 0.001,
      f"{d['alloy_mass_kg']} {d['al_total_pct']}")
s = desulf_slag(250, 0.008, 0.002, 500)
check("脱硫渣 1.5 t", abs(s["slag_t"] - 1.5) < 1e-6, str(s))
k = desulf_time(250, 0.01, 0.003, 500, 2, 100)
check("脱硫时间 ~13 min", abs(k["time_min"] - 13.1) < 1.0, str(k))
h = heat_time(250, 15, 20000, 0.55)
check("电加热 4.5 min", abs(h["minutes"] - 4.5) < 0.1, str(h))
liq = liquidus({"C": 0.145, "Si": 0.2, "Mn": 1.4, "P": 0.02, "S": 0.01, "Cr": 0.1, "Al": 0.035, "Ni": 0.1})
check("液相线 1500–1530", 1500 < liq["liquidus"] < 1530, str(liq))

# EAF 造渣：目标碱度 1.8 时，推荐渣料复算必须回到目标附近
slag_r = slag_calculator(90, 0.0559, 0.16, 0.10, 0.05, 1.8, 10, 20)
check("EAF 造渣碱度复算", abs(slag_r["basicity"] - 1.8) < 0.03, str(slag_r["basicity"]))

# 实炉校准：90 t（68 捆包 + 21 DRI + 1 炉尘），石灰 1160 + 白云石 1410 + 萤石 50
si_ox, gangue = charge_silica(90, {"no1_bundle": 68, "dri": 21, "eaf_dust": 1}, 0.0559)
slag_real = slag_calculator(90, si_ox, 1.16, 1.41, 0.05, 1.70, 8.2, 37.0, gangue)
check("实炉渣量 SiO2 来源", abs(slag_real["sio2_gangue_kg"] - 1008) < 2 and 60 < slag_real["sio2_from_si_kg"] < 80,
      f"gangue={slag_real['sio2_gangue_kg']} si={slag_real['sio2_from_si_kg']}")
check("实炉终渣碱度复算 1.70", abs(slag_real["basicity"] - 1.70) < 0.02, str(slag_real["basicity"]))
check("实炉终渣 MgO 复算 8.2", abs(slag_real["mgo_pct"] - 8.2) < 0.1, str(slag_real["mgo_pct"]))
check("实炉终渣 FeO 复算 37", abs(slag_real["feo_pct"] - 37.0) < 0.3, str(slag_real["feo_pct"]))
check("推荐渣料与实炉一致", slag_real["recommend"]["lime_kg"] == 1150 and slag_real["recommend"]["dolomite_kg"] == 1410,
      str(slag_real["recommend"]))

# 钢包脱氧 / 铝脱氧
dl = deox_ladle(90, 450, 20, "al_pebble")
check("钢包脱氧铝块加入量", dl["reagent_round_kg"] == 50 and dl["o_after_ppm"] <= 20,
      f"{dl['reagent_round_kg']} kg, O={dl['o_after_ppm']}")
check("钢包脱氧 Al 残余 ≤0.004", dl["residual_al_pct"] <= 0.004, str(dl["residual_al_pct"]))
sica = deox_ladle(90, 450, 20, "sica_powder")
check("钢包脱氧硅钙带 Si", sica["si_pickup_pct"] > 0.01, str(sica["si_pickup_pct"]))

print("== 配料（四钢种） ==")
for g in ["structural", "tinb_ulc", "pipeline", "engineering", "sc21_engineering"]:
    res = optimize_charge(g, 90)
    check(f"{g} 返回方案", res["status"] == "ok", res.get("message", ""))
    if res["status"] == "ok":
        check(f"{g} 体积 ≤100", res["volume"] <= 100.01, f"{res['volume']}")
        check(f"{g} 料斗总和≈90", abs(res["baskets"]["total_mass"] - 90) < 0.2, str(res["baskets"]["total_mass"]))

print("== 总成本优化 ==")
ot = optimize_total("sc21_engineering", 90)
check("联合优化返回方案", ot["status"] == "ok", ot.get("message", ""))
if ot["status"] == "ok":
    best = ot["best"]
    check("联合优化省成本", ot.get("saving") is not None and ot["saving"] > 200, str(ot.get("saving")))
    check("合金最终成分全部达标", not best["alloy"].get("out_of_spec"), str(best["alloy"].get("out_of_spec")))
    check("合金 LP 成本 < 贪心基准", best["alloy_cost"] < ot["baseline"]["alloy_cost"],
          f"{best['alloy_cost']} vs {ot['baseline']['alloy_cost']}")
    check("联合优化有成本分解", best["scrap_cost"] > 0 and best["alloy_cost"] > 0 and best["total_cost"] > 0, str(best))

print("== 操作流程 ==")
wp = eaf_plan("sc21_engineering", 90, True, other_cost_per_t=37)
check("EAF 向导返回", wp["status"] == "ok", wp.get("message", ""))
if wp["status"] == "ok":
    ws = wp["summary"]
    check("EAF 装料全为整吨", all(abs(x["mass"] - round(x["mass"])) < 1e-6 for x in ws["mix"]),
          str([(x["name"], x["mass"]) for x in ws["mix"]]))
    check("EAF 合金全为 10 kg 档", all(a["mass"] % 10 == 0 for a in ws["alloy"]),
          str([(a["name"], a["mass"]) for a in ws["alloy"]]))
    check("EAF 最终成分达标", not ws["out_of_spec"], str(ws["out_of_spec"]))
    check("EAF 料斗合计=装入量", abs(sum(b["mass"] for b in ws["baskets"]) - 90) < 1e-6,
          str([b["mass"] for b in ws["baskets"]]))
    check("EAF 步骤数 8", len(wp["steps"]) == 8, str(len(wp["steps"])))
    check("EAF 摘要带联动字段", bool(ws.get("mix_keys")) and bool(ws.get("charge_result")) and bool(ws.get("alloy_map")))
    flux_mass = [x["mass"] for x in ws["fluxes"]]
    # 新渣料模型按 FeO=45%、MgO=8.8% 设计（补偿 FeO 对 MgO 的稀释），
    # 石灰会相应减少、白云石增加；不再用实炉 FeO=37% 时的 1150/1410 旧值卡死。
    # 萤石改为 0：模拟器里萤石对碱度/MgO/FeO 均无作用，加了只增加成本（2026-11-17 用户实测）。
    check("EAF 渣料按实炉校准（含 FeO 稀释补偿）", 700 <= flux_mass[0] <= 1000 and
          1650 <= flux_mass[1] <= 2000 and flux_mass[2] == 0,
          str([(x["name"], x["mass"]) for x in ws["fluxes"]]))
    check("EAF 渣料一次加入", "一次加完全部渣料" in wp["steps"][2]["title"], wp["steps"][2]["title"])
    si_fe = next((a["mass"] for a in ws["alloy"] if a["key"] == "fesi75hp"), 0)
    check("EAF 硅铁按 95% 回收率", 230 <= si_fe <= 270, f"SiFe={si_fe} kg")
    check("EAF 预测 Si 在窗口", 0.24 <= float(ws["final"].get("Si", 0)) <= 0.32, str(ws["final"].get("Si")))
    check("EAF 成本含电耗", float(ws.get("energy_cost") or 0) > 19000, str(ws.get("energy_cost")))
    # 规格改为 20MnB4（EAF C 0.42–0.45、Cr 0.20–0.30、S ≤0.05、Ni ≤0.080）后，
    # 该基线由 $452 降到约 $444（铬铁/锰铁用量与废钢结构都变了）。
    check("EAF 总成本约 $444/t", abs(float(ws.get("total_per_t") or 0) - 444) < 6, str(ws.get("total_per_t")))

sp = sm_plan(88, safe=True)
check("SM 向导返回", sp["status"] == "ok", sp.get("message", ""))
check("SM 目标覆盖 17 元素", len(SM_GRADES["sc21_refining"]["specs"]) == 17,
      str(list(SM_GRADES["sc21_refining"]["specs"])))
if sp["status"] == "ok":
    ss = sp["summary"]
    check("SM 合金全为 10 kg 档", all(a["mass"] % 10 == 0 for a in ss["alloy"]),
          str([(a["name"], a["mass"]) for a in ss["alloy"]]))
    check("SM 最终成分达标", not ss["out_of_spec"], str(ss["out_of_spec"]))
    check("SM 步骤含脱碳/脱气/合金", len(sp["steps"]) >= 6, str(len(sp["steps"])))
    check("SM 摘要带合金映射", bool(ss.get("alloy_map")))
    check("SM 钢包脱氧 + LF 精调", float(ss.get("ladle_al_kg") or 0) > 0 and float(ss.get("al_kg") or 0) >= 0,
          f"ladle={ss.get('ladle_al_kg')} lf={ss.get('al_kg')}")

# Si 已经合格时，不能再用硅锰把 Si 顶到上限
sm_base = sm_plan(90, None, True, 1565)["summary"]["initial"]
init_si28 = dict(sm_base); init_si28["Si"] = 0.28
sm_si28 = sm_plan(90, init_si28, True, 1565)
si_simn = next((a["mass"] for a in sm_si28["summary"]["alloy"] if a["key"] == "simn"), 0)
check("SM Si 合格时硅锰受限", si_simn <= 40, f"SiMn={si_simn} kg")
check("SM Si 不被顶到上限", float(sm_si28["summary"]["final"].get("Si", 0)) <= 0.30,
      str(sm_si28["summary"]["final"].get("Si")))
check("SM Si 合格时 Mn 仍达标", 1.30 <= float(sm_si28["summary"]["final"].get("Mn", 0)) <= 1.60,
      str(sm_si28["summary"]["final"].get("Mn")))

# 炉料/合金调整后重新生成流程：必须保留用户方案
wo = eaf_plan("sc21_engineering", 90, True,
              mix_override={"no1_bundle": 68, "dri": 21, "eaf_dust": 1},
              alloy_override={"cr_ore": 2030, "femn_lc": 640, "fesi75hp": 320})
check("EAF 按当前炉次生成", wo["status"] == "ok" and wo.get("source") == "manual", wo.get("source"))
if wo["status"] == "ok":
    check("EAF 保留用户合金量", any(a["key"] == "cr_ore" and a["mass"] == 2030 for a in wo["summary"]["alloy"]),
          str([(a["name"], a["mass"]) for a in wo["summary"]["alloy"]]))
    check("EAF 当前炉次成分达标", not wo["summary"]["out_of_spec"], str(wo["summary"]["out_of_spec"]))

so = sm_plan(88, {"C": 0.335, "Si": 0.289, "Mn": 1.053, "Cr": 1.588, "P": 0.0096,
                  "S": 0.0104, "Mo": 0.0227, "Ni": 0.0379, "Al": 0.002,
                  "O": 0.0016, "N": 0.0079, "H": 0.0001},
             alloy_override={"fecr": 480, "femn_hc_sm": 180, "femn_lc_sm": 180, "femo_sm": 180},
             skip_decarb=True)
check("SM 按当前炉次生成", so["status"] == "ok" and so.get("source") == "manual", so.get("source"))
if so["status"] == "ok":
    check("SM 保留用户合金量", any(a["key"] == "fecr" and a["mass"] == 480 for a in so["summary"]["alloy"]),
          str([(a["name"], a["mass"]) for a in so["summary"]["alloy"]]))
    check("SM 跳过重复脱碳", not any("CAS-OB" in x["title"] for x in so["steps"]),
          str([x["title"] for x in so["steps"]]))

print("== 初始规划 ==")
plan = initial_plan("sc21_engineering", 90, True)
check("整炉初始规划返回", plan["status"] == "ok", plan.get("message", ""))
if plan["status"] == "ok":
    ps = plan["summary"]
    check("规划含 EAF + SM 两段", len([x for x in plan["checkpoints"] if x["track"] == "eaf"]) == 8 and
          len([x for x in plan["checkpoints"] if x["track"] == "sm"]) >= 7,
          str([(x["track"], x["no"]) for x in plan["checkpoints"]]))
    # 停氧锚点不再写死 0.37：合金带碳多时规划会自动提前停氧，
    # 这里校验的是「页面显示的停氧窗口 = C 轨迹里的停氧锚点」这条不变式。
    _blows = [x for x in plan["checkpoints"] if x.get("kind") == "blow"]
    _anchor = ps["c_path"][1]["c"]
    check("规划 C 轨迹完整", len(ps["c_path"]) == 6 and bool(_blows)
          and _blows[0]["c_window"][0] == _anchor,
          str(ps["c_path"]))
    check("EAF 出钢成分达标", not ps["out_of_spec_eaf"], str(ps["out_of_spec_eaf"]))
    check("SM 出站成分达标", not ps["out_of_spec_sm"], str(ps["out_of_spec_sm"]))
    check("SM 出站核对 17 元素", len(ps["checks_sm"]) == 17, str(len(ps["checks_sm"])))
    check("停氧是元素停点", bool(_blows) and _blows[0]["c_window"] == [_anchor, round(_anchor + 0.01, 3)],
          str(_blows))
    check("规划带可执行向导数据", plan["plans"]["eaf"]["status"] == "ok" and plan["plans"]["sm"]["status"] == "ok")
    check("规划带联动映射", bool(ps.get("mix_keys")) and bool(ps.get("alloy_eaf_map")) and bool(ps.get("alloy_sm_map")))

print("== 动态预测 ==")
adv = process_advise({"track": "eaf", "state": {
    "mass": 90, "temp": 1600, "o2": 150, "carbon": 0, "power": 90,
    "target_c": 0.37,
    "comp": {"C": 0.51, "Si": 0.08, "Mn": 0.5, "Cr": 0.1, "P": 0.012, "S": 0.01},
}})
check("EAF 动态建议返回", adv["status"] == "ok", adv.get("message", ""))
if adv["status"] == "ok":
    check("C0.51 取样建议 2–5 min", 2 <= adv["sample"]["in_min"] <= 5, str(adv["sample"]))
    check("C0.51 预计 C 0.40–0.43", 0.40 <= adv["sample"]["expected"] <= 0.43, str(adv["sample"]))
    check("EAF 建议继续吹氧", any(a["key"] == "blow" for a in adv["actions"]), str([a["key"] for a in adv["actions"]]))
advs = process_advise({"track": "sm", "state": {
    "mass": 88, "temp": 1565, "stage": "casob", "o2_on": True, "target_c": 0.335,
    "comp": {"C": 0.56, "O": 0.0016},
}})
check("SM CAS-OB 目标 0.335", advs["status"] == "ok" and "0.335" in advs["summary"], advs.get("summary", ""))
ctx_r = offline_chat("当前炉次下一步做什么", {"heat": {"mass": 90, "mix": {"no1_bundle": 68},
    "composition": {"C": 0.51, "Si": 0.08}}, "state": {"track": "eaf", "mass": 90,
    "temp": 1600, "o2": 150, "carbon": 0, "power": 90, "target_c": 0.37,
    "comp": {"C": 0.51, "Si": 0.08}}})
check("AI 按当前炉次回答", ctx_r.get("mode") == "context" and "当前炉料" in ctx_r.get("answer", ""),
      ctx_r.get("answer", "")[:80])

print("== 知识库 ==")
if not KB.chunks:
    print("  … 跳过（未放置手册，知识库为空；功能等价于未安装）")
else:
    for q, page in [("脱硫渣量", 56), ("料斗体积", 18), ("铝脱氧", 45)]:
        hits = KB.search(q, 5)
        check(f"检索 {q}", any(abs(h["page"] - page) <= 3 for h in hits), str([(h["page"], h["score"]) for h in hits]))
    ans = offline_answer("脱硫渣量怎么算")
    check("离线回答有引用", len(ans["citations"]) >= 2, str(ans["citations"]))

print("== Agent 计算代理 ==")
r = offline_chat("250吨钢水450ppm氧，目标铝0.04%，要加多少铝")
check("脱氧意图", r["mode"] == "calculator" and "385" in r["answer"], r["answer"][:80])
r = offline_chat("管线钢废钢怎么配")
check("配料意图", r["mode"] == "calculator" and "推荐炉料" in r["answer"], r["answer"][:80])

print(f"\n结果：{ok} 通过，{fail} 失败")
sys.exit(0 if fail == 0 else 1)
