# -*- coding: utf-8 -*-
"""AI 助手：离线检索问答 + 计算器代理 + 可选 OpenAI 兼容 LLM。"""

import json
import os
import re
import time
import urllib.error
import urllib.request

from .kb import KB, offline_answer, detect_intent, detect_grade
from .charge import optimize_charge
from .refine import deox_al, liquidus, desulf_slag
from .alloys import calculate_additions
from .data import EAF_GRADES, SM_ADDITIVES, EAF_ADDITIVES, RECOVERY
from .dynamics import advise as process_advise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "config.json")


def load_config():
    """读取配置；环境变量优先，便于部署时不把 Key 写进文件。"""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            c = json.load(f)
    except Exception:
        c = {}
    for env, key in (("STEEL_LAB_BASE_URL", "base_url"),
                     ("STEEL_LAB_MODEL", "model"),
                     ("STEEL_LAB_API_KEY", "api_key")):
        v = os.environ.get(env)
        if v:
            c[key] = v.strip()
    return c


def public_config():
    c = load_config()
    return {"base_url": c.get("base_url", "https://api.openai.com/v1"),
            "model": c.get("model", "gpt-4o-mini"),
            "has_key": bool(c.get("api_key")),
            "key_from_env": bool(os.environ.get("STEEL_LAB_API_KEY")),
            "multi_user": bool(c.get("multi_user")) and bool(
                os.environ.get("PORT") or os.environ.get("STEEL_LAB_MULTI_USER") == "1")}


def save_config(data):
    c = load_config()
    for k in ("base_url", "model", "api_key"):
        if k in data and data[k] is not None:
            if k == "api_key" and data[k] == "":
                continue
            c[k] = str(data[k]).strip()
    json.dump(c, open(CONFIG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return public_config()


def _norm_base(base):
    """规范化 Base URL：补协议、去掉尾部斜杠和误填的 /chat/completions。"""
    b = str(base or "").strip().rstrip("/")
    if not b:
        return ""
    if not re.match(r"^https?://", b, re.I):
        b = "https://" + b
    if b.lower().endswith("/chat/completions"):
        b = b[: -len("/chat/completions")].rstrip("/")
    return b


def _error_detail(exc):
    """把 HTTPError / URLError 变成可读的错误码 + 说明。"""
    if isinstance(exc, urllib.error.HTTPError):
        raw = ""
        try:
            raw = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        detail = raw
        try:
            data = json.loads(raw)
            err = data.get("error", data)
            if isinstance(err, dict):
                detail = err.get("message") or err.get("code") or raw
            elif isinstance(err, str):
                detail = err
        except Exception:
            detail = re.sub(r"<[^>]+>", " ", raw)
            detail = re.sub(r"\s+", " ", detail).strip()
        return exc.code, (detail or exc.reason or "")[:400]
    if isinstance(exc, urllib.error.URLError):
        return "network", str(exc.reason)[:300]
    return type(exc).__name__, str(exc)[:300]


def _hint_for(code, detail):
    text = f"{code} {detail}".lower()
    if "model_not_found" in text or "未提供该模型" in detail or "model not found" in text:
        return "模型名不在这个接口的可用列表里。点「获取模型列表」选一个站内模型（例如 deepseek-v4.1-flash / glm-5.3-flash）。"
    if code == 401:
        return "API Key 无效，或这个 Key 不属于当前 Base URL。请确认 Key 与中转站匹配，不要混用官方 Key 和中转 Key。"
    if code == 403:
        return "Key 没有该模型权限，或账户被限制。换模型或联系服务商。"
    if code == 404:
        return "Base URL 路径不对。OpenAI 兼容接口通常以 /v1 结尾，例如 https://api.xxx.com/v1。"
    if code == 429:
        return "请求过快或额度用完。稍后再试，或检查账户余额。"
    if isinstance(code, int) and code >= 500:
        return "服务端错误。先确认模型名正确；仍失败就换一个 Base URL 或稍后重试。"
    if code == "network":
        return "网络连接失败：检查域名拼写、本机代理/VPN、DNS 是否能解析该地址。"
    if code in ("TimeoutError", "timeout"):
        return "连接超时：网络到该接口太慢，或接口无响应。检查代理后重试。"
    if code in ("JSONDecodeError", "ValueError"):
        return "接口返回的不是 JSON。通常是 Base URL 少了 /v1，或地址指向了网页而不是 API。"
    if code == "SSLCertVerificationError":
        return "TLS 证书校验失败：检查系统时间、代理证书，或改用 https 正规域名。"
    return "检查 Base URL、模型名和 API Key 三项；可先点「获取模型列表」确认接口可用。"


def list_models(base_url=None, api_key=None, timeout=20):
    """GET /models，返回可用模型 id 列表。"""
    cfg = load_config()
    base = _norm_base(base_url if base_url is not None else cfg.get("base_url", ""))
    key = (api_key or cfg.get("api_key") or "").strip()
    if not base or not key:
        return {"ok": False, "error": "请先填写 Base URL 和 API Key", "models": []}
    req = urllib.request.Request(base + "/models", headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        items = data.get("data") if isinstance(data, dict) else data
        models = []
        for x in items or []:
            mid = x.get("id") if isinstance(x, dict) else str(x)
            if mid:
                models.append(mid)
        models.sort()
        return {"ok": True, "base_url": base, "models": models}
    except Exception as e:
        code, detail = _error_detail(e)
        return {"ok": False, "base_url": base, "code": code, "error": detail,
                "hint": _hint_for(code, detail), "models": []}


def test_connection(base_url=None, model=None, api_key=None, timeout=30):
    """实际发一次最小 chat/completions，返回可直接展示的诊断结果。"""
    cfg = load_config()
    base = _norm_base(base_url if base_url is not None else cfg.get("base_url", ""))
    model = str(model or cfg.get("model") or "").strip()
    key = str(api_key or cfg.get("api_key") or "").strip()
    if not base:
        return {"ok": False, "error": "Base URL 为空", "hint": "填写以 /v1 结尾的 OpenAI 兼容地址。"}
    if not key:
        return {"ok": False, "error": "API Key 为空", "hint": "填写服务商给的 Key（通常 sk- 开头）。"}
    if not model:
        return {"ok": False, "error": "模型名为空", "hint": "先点「获取模型列表」选一个模型。"}

    # 常见错误：Base URL 少 /v1。404 或返回非 JSON 时自动再试一次 +/v1。
    candidates = [base]
    if not re.search(r"/v\d+$", base, re.I):
        candidates.append(base + "/v1")

    last = None
    for idx, b in enumerate(candidates):
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": "只回复 OK"}],
                           "max_tokens": 8, "stream": False}).encode("utf-8")
        req = urllib.request.Request(b + "/chat/completions", data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
            data = json.loads(raw)
            msg = ((data.get("choices") or [{}])[0].get("message") or {}).get("content", "")
            return {"ok": True, "base_url": b, "model": data.get("model") or model,
                    "latency_ms": int((time.time() - t0) * 1000),
                    "reply": (msg or "")[:80],
                    "auto_fixed": idx > 0, "note": ("Base URL 已自动补全为 " + b) if idx > 0 else ""}
        except Exception as e:
            code, detail = _error_detail(e)
            last = {"ok": False, "base_url": b, "model": model, "code": code,
                    "error": detail, "hint": _hint_for(code, detail)}
            retry = (code == 404) or (idx == 0 and code in ("JSONDecodeError", "ValueError"))
            if not retry:
                break
    return last or {"ok": False, "error": "未知错误"}


def _fmt(x, n=2):
    if not isinstance(x, (int, float)):
        return str(x)
    s = f"{x:,.{n}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def try_calc(message):
    """识别常见问法并直接调用计算引擎，返回 (文本, 动作)。"""
    q = message
    grade = detect_grade(q)
    intent = detect_intent(q)

    # 配比类
    if grade and any(k in q for k in ["配比", "配料", "废钢", "炉料", "用什么料", "怎么配", "成本最低"]):
        m_charge = re.search(r"(\d+(?:\.\d+)?)\s*(?:吨|t)", q, re.I)
        charge_mass = float(m_charge.group(1)) if m_charge else 90.0
        if charge_mass > 90:
            charge_mass = 90.0
        r = optimize_charge(grade, charge_mass)
        if r["status"] == "ok":
            mix = "、".join(f"{i['name']} {_fmt(i['mass'],1)} t" for i in r["items"][:4])
            comp = r["composition"]
            warn = "；".join(r["warnings"][:3]) if r["warnings"] else "无硬性超限"
            text = (f"按 {_fmt(charge_mass, 1)} t 废钢、目标钢种「{EAF_GRADES[grade]['name']}」做最小成本配料：\n"
                    f"- 推荐炉料：{mix}\n"
                    f"- 废钢成本：${_fmt(r['cost'],0)}（${_fmt(r['cost_per_t'],1)}/t），体积 {_fmt(r['volume'],1)} m³\n"
                    f"- 熔炼后预测：C {_fmt(comp.get('C',0),3)}%，Si {_fmt(comp.get('Si',0),3)}%，"
                    f"Mn {_fmt(comp.get('Mn',0),3)}%，P {_fmt(comp.get('P',0),4)}%，S {_fmt(comp.get('S',0),4)}%\n"
                    f"- 风险提示：{warn}\n"
                    f"下一步：在「炉料配比」页调整料源/收得率，再到「合金补加」页补足 Mn、Si 等目标。")
            return text, {"label": "打开炉料配比", "view": "charge"}

    # 合金补加类：例如“250吨钢水，锰从0.12%加到1.4%，用高碳锰铁”
    CN_EL = {"碳": "C", "硅": "Si", "锰": "Mn", "磷": "P", "硫": "S", "铬": "Cr",
             "钼": "Mo", "镍": "Ni", "铜": "Cu", "铝": "Al", "铌": "Nb", "钛": "Ti", "钒": "V"}
    if ("合金" in q or "锰铁" in q or "硅铁" in q or "加到" in q or "提高到" in q) \
            and "脱氧" not in q and "ppm" not in q.lower():
        m_el = re.search(r"(碳|硅|锰|磷|硫|铬|钼|镍|铜|铝|铌|钛|钒)\s*(?:从|由)\s*([0-9.]+)\s*%", q)
        el = CN_EL[m_el.group(1)] if m_el else next((v for k, v in CN_EL.items() if k in q), None)
        m_from = re.search(r"(?:从|由)\s*([0-9.]+)\s*%", q)
        m_to = re.search(r"(?:到|至|加到|提高到)\s*([0-9.]+)\s*%", q)
        m_mass = re.search(r"(\d+(?:\.\d+)?)\s*(?:吨|t)", q, re.I)
        if el and m_to:
            mass = float(m_mass.group(1)) if m_mass else 250.0
            cur = float(m_from.group(1)) if m_from else 0.0
            tgt = float(m_to.group(1))
            preferred = {}
            if "高碳锰铁" in q:
                preferred["Mn"] = "femn_hc_sm"
            elif "低碳锰铁" in q:
                preferred["Mn"] = "femn_lc_sm"
            elif "高纯" in q:
                preferred["Mn"] = "femn_hp"
            prof = {k: v for k, v in RECOVERY["ladle"].items() if k != "label"}
            r = calculate_additions(mass, {el: cur}, {el: tgt}, SM_ADDITIVES, prof,
                                    limits={}, preferred=preferred, max_passes=1)
            if r["additions"]:
                a0 = r["additions"][0]
                pick = "、".join(f"{k} {v:g} kg" for k, v in a0["elements"].items() if k != el)
                return (f"按 {_fmt(mass,1)} t 钢水、{el} {cur}%→{tgt}% 计算：\n"
                        f"- 需 {a0['name']} {_fmt(a0['mass'],1)} kg\n"
                        f"- 带入其他元素：{pick or '无'}\n"
                        f"- 合金成本 ${_fmt(a0['cost'],0)}，温降约 −{_fmt(a0['mass']/1000*6,1)}°C\n"
                        f"提示：低碳/超低碳钢种要避免高碳锰铁的 C 夹带，必要时改用低碳锰铁或高纯锰铁。"), \
                    {"label": "打开合金补加", "view": "alloy"}

    # 脱氧类
    if ("脱氧" in q or "加铝" in q or ("铝" in q and "氧" in q)) and "ppm" in q.lower():
        m_ton = re.search(r"(\d+(?:\.\d+)?)\s*(?:吨|t)", q, re.I)
        m_o = re.search(r"(\d+(?:\.\d+)?)\s*ppm", q, re.I)
        m_al = re.search(r"(?:目标铝|残铝|铝含量)\s*([0-9.]+)\s*%?", q)
        if m_o:
            mass = float(m_ton.group(1)) if m_ton else 250.0
            o = float(m_o.group(1))
            al = float(m_al.group(1)) if m_al else 0.04
            r = deox_al(mass, o, al, 98, 60)
            text = (f"按 {_fmt(mass,1)} t 钢水、氧 {_fmt(o,0)} ppm、目标残铝 {_fmt(al,2)}% 计算：\n"
                    f"- 脱氧需铝 {_fmt(r['al_deox_pct'],4)}%，加目标残铝后共 {_fmt(r['al_total_pct'],4)}%\n"
                    f"- 需 98% 铝块 {_fmt(r['alloy_mass_kg'],1)} kg（回收率 60%）\n"
                    f"- 与氧反应的铝约 {_fmt(r['al_reacted_kg'],1)} kg，化学升温约 +{_fmt(r['heat_C'],1)}°C\n"
                    f"提示：一次性算准可获得夹杂物控制奖励；后续补铝会生成更难去除的细 Al₂O₃。")
            return text, {"label": "打开脱氧计算器", "view": "refine"}

    # 脱硫渣量
    if "脱硫" in q and "渣" in q and q.count("%") >= 2:
        nums = [float(x) for x in re.findall(r"([0-9.]+)\s*%", q)]
        m_ls = re.search(r"(?:Ls|LS|分配比)\s*[=为]?\s*(\d+)", q)
        if len(nums) >= 2:
            s0, sa = nums[0], nums[1]
            Ls = float(m_ls.group(1)) if m_ls else 500
            r = desulf_slag(250, s0, sa, Ls)
            return (f"按 250 t 钢水、S {s0}%→{sa}%、Ls={_fmt(Ls,0)}：需脱硫渣约 "
                    f"{_fmt(r['slag_t'],2)} t（{_fmt(r['slag_kg'],0)} kg）。\n"
                    f"注意：这是平衡值，实际需足够搅拌时间；渣中 CaO/Al₂O₃ 约 1.2 时 Ls 可达 500 以上。"), \
                {"label": "打开脱硫计算器", "view": "refine"}

    # 液相线
    if "液相线" in q:
        grade = grade or "structural"
        spec = {}
        for e, (lo, hi) in EAF_GRADES[grade]["specs"].items():
            spec[e] = hi if hi is not None else (lo or 0)
        r = liquidus(spec)
        return (f"按「{EAF_GRADES[grade]['name']}」目标成分上限估算，液相线温度约 "
                f"{_fmt(r['liquidus'],1)} °C（式 {r['formula']}）。\n"
                f"实际出钢温度建议在液相线以上 20–40 °C，并预留运输/合金温降。"), \
            {"label": "打开温度计算器", "view": "refine"}

    return "", None


def _context_heat(context):
    heat = (context or {}).get("heat") or {}
    comp = heat.get("composition") or (heat.get("charge") or {}).get("composition") or {}
    mix = heat.get("mix") or (heat.get("charge") or {}).get("mix") or {}
    alloy = heat.get("alloy") or {}
    return heat, comp, mix, alloy


def _state_snapshot(context):
    """把当前炉次压缩成一份 Agent 可读的状态快照。"""
    heat, comp, mix, alloy = _context_heat(context)
    plan = (context or {}).get("plan") or {}
    state = (context or {}).get("state") or heat.get("dynamic") or {}
    alloy_sm = heat.get("alloy_sm") or {}
    return {
        "炉次": {
            "钢种": heat.get("grade_name") or heat.get("grade"),
            "装入量_t": heat.get("mass"),
            "精炼钢水量_t": heat.get("sm_mass"),
            "来源": heat.get("source"),
        },
        "炉料_t": mix,
        "熔炼后成分_pct": comp,
        "EAF合金_kg": [{"name": a.get("name"), "mass": a.get("mass")}
                       for a in (alloy.get("additions") if isinstance(alloy, dict) else []) or []],
        "SM合金_kg": [{"name": a.get("name"), "mass": a.get("mass")}
                      for a in (alloy_sm.get("additions") if isinstance(alloy_sm, dict) else []) or []],
        "动态实测": state,
        "规划": {
            "C锚点": plan.get("c_anchors"),
            "C轨迹": plan.get("c_path"),
            "渣料": plan.get("fluxes"),
            "成本": plan.get("cost"),
            "EAF出钢": plan.get("final_eaf"),
            "SM出站": plan.get("final_sm"),
            "检查点": plan.get("checkpoints"),
        },
    }


def context_answer(message, context):
    """基于当前炉次回答；没有上下文时返回 None。"""
    if not context:
        return None
    heat, comp, mix, alloy = _context_heat(context)
    plan = (context or {}).get("plan") or {}
    if not mix and not comp and not plan:
        return None
    q = message or ""
    wants_context = any(k in q for k in ["当前", "现在", "这炉", "本炉", "我的炉", "下一步", "怎么操作", "该做什么", "还要", "多久", "预测"])
    # 有当前炉次时，成本/渣料/MgO/硅偏高这些问题也应该用当前数据回答
    if not wants_context:
        wants_context = (
            ("成本" in q and (plan or mix))
            or (any(k in q for k in ["MgO", "渣料", "碱度", "造渣", "白云石", "石灰"]) and plan)
            or ("硅" in q and any(k in q for k in ["多", "高", "超", "降", "减", "少"]) and (comp or mix))
        )
    if not wants_context:
        return None
    wants_next = any(k in q for k in ["下一步", "现在", "怎么操作", "该做什么", "什么时候", "还要", "多久", "停", "预测"])
    wants_charge = any(k in q for k in ["配比", "炉料", "废钢", "成分", "这炉", "当前"])
    wants_alloy = any(k in q for k in ["合金", "加多少", "补加"])
    wants_cost = any(k in q for k in ["成本", "多少钱", "价格", "吨钢"])
    wants_plan = any(k in q for k in ["规划", "停氧", "停真空", "锚点", "目标 C", "目标C"])
    wants_slag = any(k in q for k in ["MgO", "渣料", "碱度", "造渣", "白云石", "石灰"])
    wants_si = ("硅" in q or "Si" in q) and any(k in q for k in ["多", "高", "超", "降", "减", "少"])

    lines = []
    if mix:
        lines.append("当前炉料：" + "、".join(f"{k} {v} t" for k, v in mix.items()))
    if comp:
        keys = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Al"]
        lines.append("当前成分：" + "、".join(f"{e} {comp[e]:.4f}%" for e in keys if comp.get(e) is not None))
    if alloy and alloy.get("additions"):
        lines.append("当前合金：" + "、".join(f"{a['name']} {a['mass']:g} kg" for a in alloy["additions"][:8]))
    fluxes = plan.get("fluxes") or []
    if fluxes:
        lines.append("EAF 渣料（一次加入）：" + "、".join(f"{x['name']} {x['mass']:g} kg" for x in fluxes))
    anchors = plan.get("c_anchors") or {}
    if anchors:
        names = [("blow", "停氧"), ("tap", "EAF 出钢"), ("casob", "CAS-OB 终点"),
                 ("degas", "脱气终点"), ("final", "精炼终点")]
        lines.append("初始规划 C 锚点：" + "、".join(
            f"{cn} {float(anchors[k]):.3f}%" for k, cn in names if anchors.get(k) is not None))

    if wants_slag and (fluxes or plan):
        lines.append("吹氧时 MgO 下降不是烧掉了：Fe 和 Si 被氧化成 FeO、SiO₂ 进入渣中，渣量变大，白云石带入的 MgO 被稀释。同样渣料下 FeO 20% 时 MgO 约 10.8%，FeO 37% 时约 8.2%，FeO 45% 时约 7.0%。所以规划默认按 FeO=45%、MgO=8.8% 配白云石；实际仍低于 8% 时再补 100–200 kg，不要靠多加石灰。")
        return {"answer": "\n".join(lines), "citations": [],
                "actions": [{"label": "打开 EAF 造渣", "view": "slag"}], "mode": "context"}

    if wants_si:
        lines.append("Si 修正：90 t 钢水 0.01% Si = 9 kg Si。高纯硅铁 75.6%：减 10 kg 约降 0.008%，减 20 kg 约降 0.017%。如果是对上限 0.32% 多了 0.01（0.33%），直接减 20 kg 高纯硅铁，约到 0.313%；不要用吹氧降硅，会连带降 C/Mn。")
        return {"answer": "\n".join(lines), "citations": [],
                "actions": [{"label": "打开合金补加", "view": "alloy"}], "mode": "context"}

    if wants_cost:
        plan_cost = plan.get("cost") or {}
        if plan_cost.get("total") is not None:
            material = (float(plan_cost.get('scrap', 0)) + float(plan_cost.get('eaf_alloy', 0))
                        + float(plan_cost.get('flux', 0)) + float(plan_cost.get('oxygen', 0)))
            energy = float(plan_cost.get('energy', 0) or 0)
            other = float(plan_cost.get('other', 0) or 0)
            lines.append("整炉成本：材料 $%s（废钢/EAF合金/渣料/氧）+ 电 $%s + 其他 $%s + 二次精炼合金 $%s；合计 $%s（$%s/t）。" % (
                f"{material:,.0f}", f"{energy:,.0f}", f"{other:,.0f}",
                f"{float(plan_cost.get('sm_total', 0)):,.0f}",
                f"{float(plan_cost.get('total', 0)):,.0f}",
                f"{float(plan_cost.get('per_t', 0)):,.1f}"))
        else:
            lines.append("当前还没有整炉成本；先生成「初始规划」。")
        return {"answer": "\n".join(lines), "citations": [],
                "actions": [{"label": "打开初始规划", "view": "plan"}], "mode": "context"}

    if wants_plan and anchors:
        return {"answer": "\n".join(lines), "citations": [],
                "actions": [{"label": "打开初始规划", "view": "plan"}], "mode": "context"}

    state = (context or {}).get("state") or heat.get("state")
    if wants_next and state:
        r = process_advise({"track": state.get("track", "eaf"), "state": state})
        if r.get("status") == "ok":
            lines.append("动态建议：" + r.get("summary", ""))
            if r.get("sample"):
                lines.append(f"下一次取样：{r['sample']['in_min']} min 后，预计 C≈{r['sample']['expected']:.3f}%。")
            if r.get("actions"):
                lines.append("下一步：")
                for a in r["actions"][:3]:
                    lines.append(f"- {a['label']}：{a['why']}")
            return {"answer": "\n".join(lines), "citations": [],
                    "actions": [{"label": "打开动态操作", "view": "dynamic"}], "mode": "context"}

    if wants_charge or wants_alloy or wants_next:
        if not lines:
            return None
        lines.append("以上是当前页面正在使用的炉次；如果要按它重新排操作流程，点「操作流程」或结果卡上的「生成/更新操作流程」。")
        return {"answer": "\n".join(lines), "citations": [],
                "actions": [{"label": "打开操作流程", "view": "wizard"}], "mode": "context"}
    return None


def offline_chat(message, context=None):
    ctx = context_answer(message, context)
    if ctx:
        return ctx
    calc_text, action = try_calc(message)
    if calc_text:
        return {"answer": calc_text, "citations": [], "actions": [action] if action else [],
                "mode": "calculator"}
    r = offline_answer(message)
    r["mode"] = "kb"
    return r


def _context(message, k=6):
    rows = KB.search(message, k=k)
    parts = []
    for r in rows:
        parts.append(f"[{r['doc_title']} 第{r['page']}页] {r['text']}")
    return "\n\n".join(parts), rows


def llm_chat(message, history=None, context=None):
    cfg = load_config()
    key = cfg.get("api_key")
    if not key:
        out = offline_chat(message, context)
        out["note"] = "未配置 API Key，使用本地检索模式"
        return out
    base = cfg.get("base_url", "https://api.openai.com/v1").rstrip("/")
    model = cfg.get("model", "gpt-4o-mini")
    ctx, rows = _context(message)
    calc_text, action = try_calc(message)
    system = (
        "你是 steel-lab 的炼钢工艺 Agent，服务对象是参加 steeluniversity steelChallenge 的学生。"
        "你不只是问答检索：先读 state_snapshot（当前炉次、炉料、合金、规划、动态实测、成本），"
        "优先用这些数据回答“这炉/现在/下一步/成本/配比/渣料”类问题。"
        "回答结构：① 当前判断（引用具体数值） ② 下一步动作（给出用量、参数、顺序） ③ 停止/检查条件。"
        "如果 state_snapshot 与手册通用说法冲突，以当前炉次数据为准，并说明假设。"
        "需要原理或公式时再引用手册片段，句末用【《手册名》第N页】标注；不要为了引用而引用。"
        "不要编造状态快照里没有的数字；缺数据时明确说需要补哪个值。"
    )
    user = f"问题：{message}\n\n手册片段（仅在需要原理时使用）：\n{ctx}"
    if context:
        snap = _state_snapshot(context)
        user += "\n\nstate_snapshot（当前炉次，优先使用）：\n" + json.dumps(snap, ensure_ascii=False)
    if calc_text:
        user += f"\n\n计算引擎结果（可信）：\n{calc_text}"
    msgs = [{"role": "system", "content": system}]
    for h in (history or [])[-8:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": h["content"]})
    msgs.append({"role": "user", "content": user})

    body = json.dumps({"model": model, "messages": msgs, "temperature": 0.35,
                       "max_tokens": 2000}).encode("utf-8")
    req = urllib.request.Request(base + "/chat/completions", data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        citations = [{"doc_title": r["doc_title"], "page": r["page"], "text": r["text"][:160]}
                     for r in rows[:4]]
        actions = [action] if action else []
        if not actions:
            it = detect_intent(message)
            if it:
                actions = [{"label": f"打开{it['label']}计算器", "view": it["view"]}]
        return {"answer": text, "citations": citations, "actions": actions, "mode": "llm"}
    except Exception as e:
        out = offline_chat(message, context)
        out["note"] = f"LLM 调用失败（{type(e).__name__}），已回退到本地检索：{str(e)[:120]}"
        return out
