# -*- coding: utf-8 -*-
"""steel-lab 本地服务（仅标准库）。启动：python app.py"""

import json
import csv
import io
import mimetypes
import os
import sys
import time
import secrets
import threading
import traceback
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from engine import data as D
from engine.charge import optimize_charge, evaluate_mix, MELT_RETENTION
from engine.alloys import calculate_additions
from engine.optimizer import optimize_total
from engine.wizard import eaf_plan, sm_plan, round_plan
from engine.plan import initial_plan
from engine.dynamics import advise as process_advise
from engine import refine as R
from engine.kb import KB
from engine import agent as A
from engine import embed as E

WEB = os.path.join(ROOT, "web")
RUNS = os.path.join(ROOT, "data", "runs.json")
ACCESS_TOKEN = os.environ.get("STEEL_LAB_TOKEN", "").strip()
# 部署平台通常不给自定义环境变量，只注入 PORT；此时允许从 data/config.json 读 access_token。
if not ACCESS_TOKEN and os.environ.get("PORT"):
    try:
        ACCESS_TOKEN = str(A.load_config().get("access_token") or "").strip()
    except Exception:
        ACCESS_TOKEN = ""
RUNS_LOCK = threading.Lock()
MAX_BODY = 8 * 1024 * 1024


def load_runs():
    try:
        with open(RUNS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_runs(rows):
    """原子写：先写临时文件再 os.replace，避免并发/断电把 runs.json 写坏。"""
    with RUNS_LOCK:
        tmp = RUNS + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows[:300], f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, RUNS)


def clean(obj):
    """递归把 NaN/Inf 转为 null，避免 JSON 解析失败。"""
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


def runs_csv(rows):
    """把炉次记录导成 Excel 能直接打开的 CSV（带 BOM）。"""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["炉次名称", "类型", "钢种", "钢水质量(t)", "吨钢成本($/t)",
                "总成本($)", "出钢C(%)", "备注", "保存时间"])
    kind_name = {"eaf": "EAF 炉次", "sm": "二次精炼", "alloy": "合金方案",
                 "charge": "配料方案", "plan": "整炉方案", "heat": "整炉方案"}
    for r in rows:
        p = r.get("payload") or {}
        kind = p.get("kind") or ("plan" if p.get("plan") else "")
        s = p.get("summary") or {}
        eaf_p = p.get("eaf") or {}
        plan_eaf = ((p.get("plan") or {}).get("plans") or {}).get("eaf") or {}
        eaf_s = eaf_p.get("summary") or plan_eaf.get("summary") or (s if p.get("track") == "eaf" else {})
        mass = s.get("mass") or s.get("tap_mass") or eaf_s.get("tap_mass") or p.get("mass") or p.get("total_mass")
        cpt = s.get("total_per_t") or s.get("cost_per_t") or eaf_s.get("total_per_t") or p.get("cost_per_t")
        total = s.get("total_cost") or s.get("cost") or eaf_s.get("cost") or p.get("cost")
        c = (s.get("final") or eaf_s.get("final") or {}).get("C")
        note = p.get("eaf_name") or ""
        if not note and p.get("route"):
            note = " → ".join((p.get("route") or []))
        w.writerow([
            r.get("name") or "", kind_name.get(kind, kind or "记录"),
            r.get("grade") or "",
            round(float(mass), 2) if isinstance(mass, (int, float)) else "",
            round(float(cpt), 2) if isinstance(cpt, (int, float)) else "",
            round(float(total), 0) if isinstance(total, (int, float)) else "",
            round(float(c), 4) if isinstance(c, (int, float)) else "",
            note, r.get("ts") or "",
        ])
    return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    server_version = "SteelLab/1.0"

    def log_message(self, fmt, *args):
        if os.environ.get("STEEL_LAB_DEBUG"):
            super().log_message(fmt, *args)

    def _user(self):
        """轻量用户名：只用于隔离炉次记录，不是安全账号。"""
        raw = self.headers.get("X-Steel-User") or ""
        try:
            name = urllib.parse.unquote(raw)
        except Exception:
            name = raw
        return name.strip()[:24]

    def _multi_user(self):
        if os.environ.get("STEEL_LAB_MULTI_USER") == "1":
            return True
        # 只在部署环境（平台注入 PORT）启用多人隔离，本地单人使用不打扰
        return bool(A.load_config().get("multi_user")) and bool(os.environ.get("PORT"))

    def _visible_runs(self):
        rows = load_runs()
        if not self._multi_user():
            return rows
        user = self._user()
        if not user:
            return []
        return [r for r in rows if (r.get("owner") or "") == user]

    def _auth_ok(self):
        """设置了 STEEL_LAB_TOKEN 时，除健康检查和静态文件外都要口令。"""
        if not ACCESS_TOKEN:
            return True
        if not urllib.parse.urlparse(self.path).path.startswith("/api/"):
            return True
        if urllib.parse.urlparse(self.path).path == "/api/health":
            return True
        got = self.headers.get("X-Steel-Token") or ""
        if not got:
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got = (qs.get("token") or [""])[0]
        return bool(got) and secrets.compare_digest(got, ACCESS_TOKEN)

    def _send(self, code, body, ctype="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(clean(body), ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        if length > MAX_BODY:
            raise ValueError("请求体过大（上限 8 MB）")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)
        if not self._auth_ok():
            return self._send(401, {"error": "访问口令错误", "auth_required": True})
        try:
            if path == "/api/health":
                return self._send(200, {"ok": True, "ts": int(time.time())})
            if path == "/api/bootstrap":
                return self._send(200, {
                    "grades_eaf": D.EAF_GRADES,
                    "grades_sm": D.SM_GRADES,
                    "default_pre_c": D.DEFAULT_PRE_C,
                    "scraps": D.SCRAPS,
                    "additives_eaf": D.EAF_ADDITIVES,
                    "additives_sm": D.SM_ADDITIVES,
                    "recovery": D.RECOVERY,
                    "deox_reagents": R.DEOX_REAGENTS,
                    "retention": MELT_RETENTION,
                    "elements": D.ELEMENTS,
                    "element_cn": D.ELEMENT_CN,
                    "manuals": D.MANUALS,
                    "config": A.public_config(),
                    "runs": len(self._visible_runs()),
                })
            if path == "/api/kb/search":
                q = (qs.get("q") or [""])[0]
                k = int((qs.get("k") or ["6"])[0])
                doc = (qs.get("doc") or [None])[0]
                mode = (qs.get("mode") or ["hybrid"])[0]
                if mode not in ("bm25", "vector", "hybrid"):
                    mode = "hybrid"
                KB.vector_index()
                results = KB.search_hybrid(q, k=k, doc=doc, mode=mode)
                return self._send(200, {"results": results, "mode": mode,
                                        "vector": KB.vector_label()})
            if path == "/api/kb/status":
                KB.vector_index()
                return self._send(200, {"chunks": KB.N,
                                        "vector": KB.vector_label(),
                                        "embed": E.status()})
            if path == "/api/kb/sections":
                return self._send(200, {"sections": KB.sections()})
            if path == "/api/runs/export":
                data = runs_csv(self._visible_runs()).encode("utf-8-sig")
                fn = "steel-lab-runs-" + time.strftime("%Y%m%d-%H%M") + ".csv"
                return self._send(200, data, ctype="text/csv; charset=utf-8",
                                  headers={"Content-Disposition": f'attachment; filename="{fn}"'})
            if path == "/api/runs":
                return self._send(200, {"runs": self._visible_runs()})
            if path == "/api/config":
                return self._send(200, A.public_config())
            if path in ("/", "/index.html"):
                sc = (qs.get("sharecode") or [""])[0]
                return self._static("index.html", sc)
            return self._static(path.lstrip("/"))
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": str(e)})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not self._auth_ok():
            return self._send(401, {"error": "访问口令错误", "auth_required": True})
        try:
            body = self._json_body()
            if path == "/api/charge/optimize":
                grade = body.get("grade", "structural")
                mass = float(body.get("mass", 82))
                vol = float(body.get("volume_limit", 100))
                limits = body.get("limits") or {}
                allowed = {k for k, v in limits.items() if (v or {}).get("enabled", True)} if limits else None
                r = optimize_charge(
                    grade, mass,
                    limits,
                    vol,
                    bool(body.get("enforce_min", False)),
                    body.get("carbon_cap"),
                    body.get("retention") or {},
                    bool(body.get("soft", True)),
                    body.get("specs"),
                    float(body.get("margin", 0) or 0),
                )
                if body.get("round_tons") and r.get("status") == "ok":
                    from engine.wizard import round_charge_mix
                    r = round_charge_mix(r.get("mix") or {}, mass, grade,
                                         body.get("retention") or None, vol,
                                         allowed=allowed, limits=limits)
                return self._send(200, r)
            if path == "/api/plan/initial":
                return self._send(200, initial_plan(
                    body.get("grade", "sc21_engineering"),
                    float(body.get("mass", 82)),
                    bool(body.get("safe", True)),
                    body.get("mix") or None,
                    body.get("alloy_plan") or None,
                    body.get("retention") or None,
                    float(body["pre_c"]) if body.get("pre_c") not in (None, "") else None,
                    float(body.get("pre_si", 0.05)),
                    body.get("sm_mass"),
                    body.get("sm_initial") or None,
                    body.get("sm_alloy") or None,
                    float(body.get("temp_start", 1565)),
                    body.get("power_kwh"),
                    float(body.get("other_per_t", 0.0)),
                    float(body.get("energy_price", 0.57)),
                    body.get("alloy_pos"),
                    body.get("sm_grade") or None,
                    float(body.get("flux_feo", 45)),
                ))
            if path == "/api/process/advise":
                return self._send(200, process_advise(body))
            if path == "/api/wizard/eaf":
                return self._send(200, eaf_plan(
                    body.get("grade", "sc21_engineering"),
                    float(body.get("mass", 82)),
                    bool(body.get("safe", True)),
                    body.get("power_kwh"),
                    body.get("mix") or None,
                    body.get("alloy_plan") or None,
                    body.get("retention") or None,
                    float(body["pre_c"]) if body.get("pre_c") not in (None, "") else None,
                    float(body.get("pre_si", 0.05)),
                    float(body.get("other_per_t", 0.0)),
                    float(body.get("energy_price", 0.57)),
                    body.get("alloy_pos"),
                    flux_feo=float(body.get("flux_feo", 45)),
                ))
            if path == "/api/sm/evaluate":
                sm_key = body.get("sm_grade") or body.get("grade") or "sc21_refining"
                sm_specs = (D.SM_GRADES.get(sm_key) or D.SM_GRADES["sc21_refining"])["specs"]
                return self._send(200, round_plan(
                    float(body.get("mass", 90)),
                    body.get("initial") or {},
                    body.get("additions") or {},
                    sm_specs,
                    track="sm", profile="ladle", repair=False))
            if path == "/api/wizard/sm":
                sm_key = body.get("sm_grade")
                if not sm_key:
                    sm_key = D.sm_grade_for(body.get("eaf_grade") or body.get("grade") or "")
                return self._send(200, sm_plan(
                    float(body.get("mass", 88)),
                    body.get("initial") or {},
                    bool(body.get("safe", True)),
                    float(body.get("temp_start", 1565)),
                    body.get("alloy_plan") or None,
                    bool(body.get("skip_decarb", False)),
                    body.get("alloy_pos"),
                    sm_grade=sm_key,
                ))
            if path == "/api/optimize/total":
                grade = body.get("grade", "sc21_engineering")
                c_pre = body.get("c_pre")
                if c_pre in (None, ""):
                    c_pre = D.default_pre_c(grade)
                return self._send(200, optimize_total(
                    grade,
                    float(body.get("mass", 82)),
                    float(body.get("charge_margin", 0.06)),
                    float(body.get("alloy_margin", 0.2)),
                    float(c_pre),
                    float(body.get("si_pre", 0.05)),
                    float(body.get("ni_cal", 0.42)),
                    body.get("power_kwh"),
                    float(body.get("power_price", 0.57)),
                    float(body.get("other_cost", 0)),
                    body.get("limits") or None,
                    bool(body.get("round_tons", False)),
                    int(body.get("alloy_step", 0) or 0),
                    float(body.get("volume_limit", 100)),
                ))
            if path == "/api/charge/evaluate":
                return self._send(200, evaluate_mix(body.get("mix") or {},
                                                    body.get("grade", "structural"),
                                                    float(body.get("volume_limit", 100)),
                                                    body.get("retention") or {},
                                                    body.get("specs")))
            if path == "/api/alloy/calculate":
                track = "sm" if body.get("catalog", "sm") == "sm" else "eaf"
                cat = D.SM_ADDITIVES if track == "sm" else D.EAF_ADDITIVES
                prof_name = body.get("profile", "ladle")
                prof = D.RECOVERY.get(prof_name, D.RECOVERY["ladle"])
                prof = {k: v for k, v in prof.items() if k != "label"}
                mass_val = float(body.get("mass", 85))
                init_val = body.get("initial") or {}
                targets_val = body.get("targets") or {}
                limits_val = {e: list(v) for e, v in (body.get("limits") or {}).items()}
                step_val = int(body.get("round_step") or 0)

                # 先尝试全局线性规划（LP），把用户填写的 targets 作为有效下限约束（若低于窗口上限）
                lp_specs = {e: list(v) for e, v in limits_val.items()}
                for e, tv in targets_val.items():
                    if tv is None or tv == "":
                        continue
                    tv_f = float(tv)
                    lo, hi = lp_specs.get(e, [None, None])
                    if hi is not None and tv_f <= hi + 1e-6:
                        lp_specs[e] = [max(lo or 0.0, tv_f - 0.002), hi]
                    elif hi is None:
                        lp_specs[e] = [tv_f, None]

                from engine.alloy_lp import optimize_alloy_lp
                drift = {"Si": 0.01} if track == "sm" else None
                lp_out = None
                if lp_specs and not body.get("preferred"):
                    lp_out = optimize_alloy_lp(
                        mass_val, init_val, lp_specs, catalog=cat, profile=prof_name,
                        margin=0.0, max_kg=body.get("max_kg") or None,
                        drift_caps=drift, forbidden=body.get("forbidden") or None,
                    )
                    if lp_out.get("status") != "ok" and limits_val:
                        pos_m = float(body.get("pos") if body.get("pos") is not None else 0.2)
                        lp_out = optimize_alloy_lp(
                            mass_val, init_val, limits_val, catalog=cat, profile=prof_name,
                            margin=max(0.02, min(0.4, pos_m * 0.6)),
                            max_kg=body.get("max_kg") or None,
                            drift_caps=drift, forbidden=body.get("forbidden") or None,
                        )

                if lp_out and lp_out.get("status") == "ok":
                    out = lp_out
                    if step_val > 0 and limits_val:
                        plan = {a["key"]: a["mass"] for a in out.get("additions") or []}
                        rr = round_plan(mass_val, init_val, plan, limits_val, track=track,
                                        profile=prof_name, step=step_val, repair=True,
                                        margin=float(body.get("pos") or 0.15))
                        out["additions"] = rr["additions"]
                        out["added_total"] = rr["added_total"]
                        out["cost"] = rr["cost"]
                        out["cost_per_t"] = round(rr["cost"] / rr["mass_after"], 2) if rr["mass_after"] else 0
                        out["mass_after"] = rr["mass_after"]
                        out["final"] = rr["final"]
                        out["temperature_drop"] = rr["temperature_drop"]
                        out["warnings"] = rr["out_of_spec"]
                        out["unmet"] = []
                    return self._send(200, out)

                # 回退：当用户指定 preferred 添加剂或初始值已超限时，用迭代贪心 + 10 kg 修复
                out = calculate_additions(
                    mass_val, init_val, targets_val,
                    cat, prof, limits_val,
                    body.get("forbidden") or [],
                    body.get("preferred") or {},
                    body.get("max_kg") or {},
                    int(body.get("max_passes", 2)),
                )
                if step_val > 0 and out.get("status") == "ok" and limits_val:
                    plan = {a["key"]: a["mass"] for a in out.get("additions") or []}
                    rr = round_plan(mass_val, init_val, plan, limits_val, track=track,
                                    profile=prof_name, step=step_val, repair=True)
                    out["additions"] = rr["additions"]
                    out["added_total"] = rr["added_total"]
                    out["cost"] = rr["cost"]
                    out["cost_per_t"] = round(rr["cost"] / rr["mass_after"], 2) if rr["mass_after"] else 0
                    out["mass_after"] = rr["mass_after"]
                    out["final"] = rr["final"]
                    out["temperature_drop"] = rr["temperature_drop"]
                    out["warnings"] = rr["out_of_spec"]
                    out["unmet"] = []
                return self._send(200, out)
            if path == "/api/refine/liquidus":
                return self._send(200, R.liquidus(body.get("comp") or {}))
            if path == "/api/refine/deox":
                return self._send(200, R.deox_al(body.get("mass", 250), body.get("o_ppm", 450),
                                                 body.get("target_al", 0.04),
                                                 body.get("al_content", 98),
                                                 body.get("recovery", 60)))
            if path == "/api/refine/deox_ladle":
                return self._send(200, R.deox_ladle(
                    body.get("mass", 90), body.get("o_ppm", 450),
                    body.get("target_o", 20), body.get("reagent", "al_pebble")))
            if path == "/api/refine/desulf":
                return self._send(200, {
                    "slag": R.desulf_slag(body.get("mass", 250), body.get("s0", 0.008),
                                          body.get("s_aim", 0.002), body.get("Ls", 500)),
                    "kinetics": R.desulf_time(body.get("mass", 250), body.get("s0", 0.01),
                                              body.get("s_t", body.get("s_aim", 0.003)), body.get("Ls", 500),
                                              body.get("slag_t", 2), body.get("epsilon", 100)),
                })
            if path == "/api/refine/decarb":
                return self._send(200, R.decarb(body.get("mass", 250), body.get("c_i", 0.045),
                                                body.get("c_f", 0.002), body.get("c_eq", 0.0015),
                                                body.get("Q", 80000), body.get("q", 18),
                                                body.get("rho", 7200), body.get("kc")))
            if path == "/api/refine/hydrogen":
                return self._send(200, {
                    "equilibrium": R.h_equilibrium(body.get("p", 0.1)),
                    "kinetics": R.hydrogen_time(body.get("hi", 5), body.get("hf", 1),
                                                body.get("heq", 0.81), body.get("kH", 0.13)),
                    "kH_tank": R.kH_tank(body.get("argon", 3)),
                })
            if path == "/api/refine/stir":
                return self._send(200, R.stir_power(body.get("V", 1), body.get("temp", 1600),
                                                    body.get("mass", 250), body.get("H", 2.5),
                                                    body.get("P0", 1)))
            if path == "/api/refine/heat":
                return self._send(200, R.heat_time(body.get("mass", 250), body.get("dT", 15),
                                                   body.get("power", 20000), body.get("eta", 0.55)))
            if path == "/api/refine/slag":
                mass = float(body.get("mass", 90) or 90)
                mix = body.get("mix") or {}
                if mix:
                    si_ox_pct, gangue = R.charge_silica(
                        mass, mix, float(body.get("si_retained", 0.05) or 0.05))
                else:
                    si_ox_pct = float(body.get("si", 0.1) or 0.1)
                    gangue = float(body.get("sio2_gangue", 0) or 0)
                return self._send(200, R.slag_calculator(
                    mass, si_ox_pct,
                    body.get("lime", 1.15), body.get("dolomite", 1.41),
                    body.get("fluorspar", 0.05),
                    body.get("basicity", 1.70),
                    body.get("mgo", 8.2),
                    body.get("feo", 37.0),
                    sio2_gangue_kg=gangue))
            if path == "/api/refine/temperature":
                return self._send(200, R.temperature_plan(body.get("mass", 250),
                                                          body.get("tap_temp", 1650),
                                                          body.get("steps") or []))
            if path == "/api/chat":
                msg = (body.get("message") or "").strip()
                if not msg:
                    return self._send(400, {"error": "message 不能为空"})
                return self._send(200, A.llm_chat(msg, body.get("history") or [], body.get("context") or None))
            if path == "/api/runs":
                rows = load_runs()
                row = {
                    "id": str(int(time.time() * 1000)),
                    "ts": time.strftime("%Y-%m-%d %H:%M"),
                    "name": body.get("name") or "未命名炉次",
                    "grade": body.get("grade"),
                    "owner": self._user(),
                    "payload": body.get("payload"),
                }
                rows.insert(0, row)
                save_runs(rows)
                return self._send(200, {"ok": True, "run": row})
            if path == "/api/config":
                return self._send(200, A.save_config(body))
            if path == "/api/config/test":
                tmp_key = body.get("api_key") or None
                return self._send(200, A.test_connection(
                    body.get("base_url") or None,
                    body.get("model") or None,
                    tmp_key))
            if path == "/api/config/models":
                return self._send(200, A.list_models(
                    body.get("base_url") or None,
                    body.get("api_key") or None))
            return self._send(404, {"error": "not found"})
        except json.JSONDecodeError:
            return self._send(400, {"error": "JSON 格式错误"})
        except Exception as e:
            traceback.print_exc()
            return self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if not self._auth_ok():
            return self._send(401, {"error": "访问口令错误", "auth_required": True})
        if parsed.path == "/api/runs":
            rid = (qs.get("id") or [""])[0]
            rows = load_runs()
            target = next((r for r in rows if r.get("id") == rid), None)
            if target is None:
                return self._send(404, {"error": "记录不存在"})
            if self._multi_user() and (target.get("owner") or "") != self._user():
                return self._send(403, {"error": "只能删除自己的炉次记录"})
            rows = [r for r in rows if r.get("id") != rid]
            save_runs(rows)
            return self._send(200, {"ok": True})
        return self._send(404, {"error": "not found"})

    def _static(self, rel, sharecode=""):
        rel = urllib.parse.unquote(rel)
        root = os.path.normpath(WEB)
        path = os.path.normpath(os.path.join(root, rel))
        try:
            inside = os.path.commonpath([root, path]) == root
        except ValueError:
            inside = False
        if not inside:
            return self._send(403, "forbidden")
        if not os.path.isfile(path):
            return self._send(404, "not found")
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as f:
            data = f.read()
        # 平台分享链接用 ?sharecode= 校验；把口令带到静态资源上，否则 JS/CSS 会被 403。
        if sharecode and os.path.basename(path) == "index.html":
            try:
                html = data.decode("utf-8")
                sc = urllib.parse.quote(sharecode, safe="")
                html = html.replace('href="styles.css"', 'href="styles.css?sharecode=%s"' % sc)
                html = html.replace('src="app.js"', 'src="app.js?sharecode=%s"' % sc)
                data = html.encode("utf-8")
            except Exception:
                pass
        return self._send(200, data, ctype)


def main():
    # 本地默认只监听 127.0.0.1；部署平台会注入 PORT，此时监听 0.0.0.0。
    env_port = os.environ.get("PORT") or os.environ.get("STEEL_LAB_PORT")
    host = os.environ.get("STEEL_LAB_HOST") or ("0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    port = int(env_port or "8765")
    srv = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    print(f"\n  steel-lab 已启动：{url}")
    if ACCESS_TOKEN:
        print("  访问口令：已启用（STEEL_LAB_TOKEN）")
    elif os.environ.get("PORT") or host not in ("127.0.0.1", "localhost"):
        print("  [警告] 正在对外监听但未设置 STEEL_LAB_TOKEN —— 任何人都能访问并消耗你的 AI 额度！")
    else:
        print("  访问口令：未启用（仅本机使用，正常）")
    print("  Ctrl+C 停止\n")
    if "--open" in sys.argv:
        import threading
        import webbrowser
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("bye")


if __name__ == "__main__":
    main()
