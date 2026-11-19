/* STEEL/LAB — 单页应用 */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const S = {
  boot: null, view: "dashboard", grade: "structural",
  lastCharge: null, lastAlloy: null, chat: [], tab: "alloy",
  chargeMass: 90, runs: [], runsLoaded: false, lastEafRunId: null, lastEafName: null, busy: false,
  heat: { track: null, grade: null, mass: null, mix: null, charge: null, alloy: null,
          initial: null, pre_c: 0.37, pre_si: 0.05, skip_decarb: false, dirty: false,
          rev: 0, source: null, updatedAt: null, dynamic: null },
  dyn: { track: "eaf", state: null, data: null, rev: 0, nodes: [], edges: [], seq: 1,
         pan: { x: 0, y: 0 }, zoom: 1, drag: null, panning: null },
  alloyPos: null,
  slag: { lime: null, dol: null, flu: null, b: 1.70, mgo: 8.8, feo: 45, manual: false },
  plan: { data: null, rev: 0, dataSig: null, busy: false, mass: 82, grade: null, safe: true, useHeat: null, pre_c: 0.37, pre_cGrade: null, power_kwh: 34200, other_per_t: 0 },
  smcalc: { route: [], additions: {}, mass: null, initial: null, temp: 1565, result: null, eafRunId: null, sim: null },
  wizard: { track: "eaf", eaf: null, sm: null, rev: 0, step: 0, smInitial: null, eafRunId: null,
            forced: null, forcedAlloy: null, skipDecarb: false, pendingStep: 0,
            eafMass: null, smMass: null },
};

const ICONS = {
  dash: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>',
  charge: '<svg viewBox="0 0 24 24"><path d="M4 7h16l-1.4 12.2a2 2 0 0 1-2 1.8H7.4a2 2 0 0 1-2-1.8L4 7z"/><path d="M8 7V5a4 4 0 0 1 8 0v2"/><path d="M8 12h8"/></svg>',
  alloy: '<svg viewBox="0 0 24 24"><path d="M12 3l7 4v10l-7 4-7-4V7l7-4z"/><path d="M12 12l7-5M12 12v9M12 12L5 7"/></svg>',
  refine: '<svg viewBox="0 0 24 24"><path d="M5 21V8l7-5 7 5v13"/><path d="M9 21v-6h6v6"/><path d="M9 8h.01M15 8h.01"/></svg>',
  kb: '<svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v18H6.5A2.5 2.5 0 0 1 4 18.5v-13z"/><path d="M4 17.5A2.5 2.5 0 0 1 6.5 15H20"/><path d="M8 7h8M8 11h5"/></svg>',
  agent: '<svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="13" rx="3"/><path d="M8 3v3M16 3v3M8 11h.01M16 11h.01M9 15h6"/></svg>',
  runs: '<svg viewBox="0 0 24 24"><path d="M12 8v5l3 2"/><circle cx="12" cy="12" r="9"/></svg>',
  route: '<svg viewBox="0 0 24 24"><circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h6a4 4 0 0 0 0-8H10a4 4 0 0 1 0-8h6"/></svg>',
  plan: '<svg viewBox="0 0 24 24"><path d="M8 4h8v3H8z"/><path d="M9 4H6a1 1 0 0 0-1 1v15a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1h-3"/><path d="M8 11h8M8 15h5"/><circle cx="16.5" cy="17.5" r="2.5"/><path d="M16.5 16.5v1.3l.9.6"/></svg>',
  canvas: '<svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 8h10M7 12h6M7 16h4"/></svg>',
};

const EAF_GRADE_BY_SM = {
  sc21_refining: "sc21_engineering",
  sc21_engineering: "sc21_engineering",
  engineering: "engineering",
  structural: "structural",
  tinb_ulc: "tinb_ulc",
  pipeline: "pipeline",
};

const NAV = [
  { key: "dashboard", label: "总览", icon: "dash", crumb: "总览" },
  { key: "plan", label: "初始规划", icon: "plan", crumb: "初始规划" },
  { key: "reference", label: "2024 参考", icon: "kb", crumb: "2024 参考炉次" },
  { key: "wizard", label: "操作流程", icon: "route", crumb: "操作流程" },
  { key: "dynamic", label: "动态操作", icon: "canvas", crumb: "动态操作" },
  { key: "charge", label: "炉料配比", icon: "charge", crumb: "炉料配比" },
  { key: "slag", label: "EAF 造渣", icon: "refine", crumb: "EAF 造渣" },
  { key: "alloy", label: "合金补加", icon: "alloy", crumb: "合金补加" },
  { key: "refine", label: "二次精炼", icon: "refine", crumb: "二次精炼" },
  { key: "kb", label: "知识库", icon: "kb", crumb: "手册知识库" },
  { key: "agent", label: "AI 助手", icon: "agent", crumb: "AI 助手" },
  { key: "runs", label: "炉次记录", icon: "runs", crumb: "炉次记录" },
];

const TABS = [
  { key: "alloy", label: "9.1 合金添加量" },
  { key: "deox_ladle", label: "9.2 钢包脱氧" },
  { key: "deox", label: "9.2 铝脱氧" },
  { key: "decarb", label: "9.3 脱碳" },
  { key: "desulf", label: "9.4 脱硫" },
  { key: "hydrogen", label: "9.5 除氢" },
  { key: "stir", label: "9.6 钢包搅拌" },
  { key: "heat", label: "9.7 电加热" },
  { key: "clean", label: "9.8 钢材洁净度" },
];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]));
}
function f(x, d = 1) {
  if (x === null || x === undefined || isNaN(x)) return "—";
  return Number(x).toFixed(d);
}
function money(x) { return "$" + Math.round(x || 0).toLocaleString("en-US"); }
function gradeName(k) { const g = S.boot.grades_eaf[k] || S.boot.grades_sm[k]; return g ? g.name : k; }
function gradeShort(k) { const g = S.boot.grades_eaf[k] || S.boot.grades_sm[k]; return g ? g.short : k; }
function heatSilica() {
  const hasHeatMix = !!(S.heat?.mix && Object.keys(S.heat.mix).length);
  const mix = hasHeatMix ? S.heat.mix
    : (S.plan?.data?.summary?.mix_keys && Object.keys(S.plan.data.summary.mix_keys).length
        ? S.plan.data.summary.mix_keys : { no1_bundle: 68, dri: 21, eaf_dust: 1 });
  let siIn = 0, gangue = 0, mixMass = 0;
  for (const [k, t] of Object.entries(mix)) {
    const sc = (S.boot.scraps || []).find((x) => x.key === k);
    if (!sc) continue;
    mixMass += Number(t || 0);
    siIn += Number(t || 0) * 1000 * Number(sc.comp?.Si || 0) / 100;
    gangue += Number(t || 0) * 1000 * Number(sc.sio2 || 0) / 100;
  }
  // 用“当前 mix × 熔炼收得率”重算，不再读 S.heat.charge.composition.Si：
  // 那个值可能是上一炉保存下来的，会把 Si 氧化量算成 0，白云石随之偏少。
  const mass = mixMass || Number(S.heat?.mass || S.plan?.data?.mass || 90);
  const siRetFrac = Number(S.boot.retention?.Si ?? 0.60);
  const siRet = siIn / (mass * 1000) * 100 * siRetFrac;
  const siOxPct = Math.max(0, siIn * (1 - siRetFrac)) / (mass * 1000) * 100;
  return {
    siOxPct, gangue, siRet, mix, fallback: !hasHeatMix,
  };
}


/* ---------------- heat context / linkage ---------------- */
function heatRev() { return Number(S.heat?.rev || 0); }
function heatHasCharge() { return !!(S.heat?.mix && Object.keys(S.heat.mix).length); }
function heatHasAlloy() { return !!(S.heat?.alloy && (S.heat.alloy.additions || []).length); }
function planSettingsSig() {
  return [S.plan?.grade, S.plan?.mass, S.plan?.safe, S.plan?.pre_c,
          S.plan?.power_kwh, S.plan?.other_per_t, S.slag?.feo].join("|");
}
function planFresh() {
  const p = S.plan?.data;
  if (!p) return false;
  if (Number(S.plan.rev || 0) !== heatRev()) return false;
  // 规划参数（钢种/装入量/模式/停氧C/电耗/其他成本/设计FeO）改过，旧结果即失效
  if (S.plan.dataSig != null && S.plan.dataSig !== planSettingsSig()) return false;
  return true;
}
function dynFresh() { return !!S.dyn?.data && Number(S.dyn.rev || 0) === heatRev(); }

function bumpHeat(source) {
  S.heat.rev = heatRev() + 1;
  S.heat.source = source || "manual";
  S.heat.updatedAt = Date.now();
  S.heat.dirty = true;
  S.heat.dynamic = null;
  S.heat.sm_mass = null;
  S.heat.alloy_sm = null;
  S.plan.grade = S.heat.grade || S.plan.grade;
  S.plan.mass = S.heat.mass || S.plan.mass;
  S.grade = S.plan.grade || S.grade;
  // 炉料/合金一变，默认就按“当前炉次”生成规划；用户仍可在页面上取消勾选
  if (["charge", "manual-mix", "alloy", "run", "wizard"].includes(source)) S.plan.useHeat = true;
  // 下游缓存失效；旧规划保留但标记为过期，方便对照
  S.wizard.eaf = null;
  S.wizard.sm = null;
  S.wizard.rev = 0;
  S.dyn.data = null;
  S.dyn.rev = 0;
  refreshHeatFlow();
  updateTop();
  persistPlanSettings();
}

// 把“当前炉次”的规划参数写回本地设置。每次改炉料/重量/钢种都调用，
// 避免下次打开页面读到很早以前保存的旧值。
function newHeat() {
  if (!confirm("清空当前炉次的临时结果，开始新一炉？已保存的炉次记录不会删除。")) return;
  const keep = {
    mass: S.plan.mass, grade: S.plan.grade, safe: S.plan.safe,
    pre_c: S.plan.pre_c, power_kwh: S.plan.power_kwh, other_per_t: S.plan.other_per_t,
  };
  S.heat = { track: null, grade: null, mass: null, mix: null, charge: null, alloy: null,
             initial: null, pre_c: 0.37, pre_si: 0.05, skip_decarb: false, dirty: false,
             rev: 0, source: null, updatedAt: null, dynamic: null };
  S.plan = { ...S.plan, ...keep, data: null, rev: 0, dataSig: null, useHeat: false };
  S.lastCharge = null; S.lastAlloy = null; S.alloy = null;
  S.dyn.data = null; S.dyn.rev = 0; S.dyn.state = null;
  S.wizard.eaf = null; S.wizard.sm = null; S.wizard.rev = 0;
  resetSlagForNewHeat();
  persistPlanSettings();
  updateTop();
  go("plan");
  toast("已清空当前炉次，开始新一炉");
}

function resetSlagForNewHeat() {
  S.slag = { lime: null, dol: null, flu: null, b: 1.70, mgo: 8.8, feo: 45, manual: false };
}

function persistPlanSettings() {
  try {
    localStorage.setItem("steel-lab-plan-settings", JSON.stringify({
      mass: S.plan.mass,
      grade: S.plan.grade,
      safe: S.plan.safe,
      pre_c: S.plan.pre_c,
      pre_c_grade: S.plan.pre_cGrade,
      power_kwh: S.plan.power_kwh,
      other_per_t: S.plan.other_per_t,
      alloy_pos: S.alloyPos,
      flux_feo: S.slag.feo,
      use_heat: S.plan.useHeat,
    }));
  } catch (e) {}
}

function alloySummaryFromRows(rows, massAfter) {
  const additions = rows || [];
  return {
    additions,
    added_total: additions.reduce((a, x) => a + Number(x.mass || 0), 0),
    cost: additions.reduce((a, x) => a + Number(x.cost || 0), 0),
    mass_after: massAfter,
    temperature_drop: Math.round(additions.reduce((a, x) => a + Number(x.mass || 0), 0) / 1000 * 6 * 10) / 10,
  };
}

function syncHeatFromPlan(p) {
  if (!p) return;
  const rev = heatRev();
  const eafPlan = p.plans?.eaf || null;
  const eafSum = eafPlan?.summary || {};
  const alloyRows = p.summary?.alloy_eaf || eafSum.alloy || [];
  S.heat = {
    ...S.heat, track: "eaf", grade: p.grade, mass: p.mass,
    mix: p.summary?.mix_keys || eafSum.mix_keys || S.heat.mix,
    charge: eafSum.charge_result || S.heat.charge,
    alloy: alloySummaryFromRows(alloyRows, p.summary?.tap_mass),
    initial: null, pre_c: p.summary?.c_path?.find((x) => x.key === "blow")?.c ?? S.heat.pre_c,
    pre_si: 0.05, skip_decarb: false, dirty: false, dynamic: null, source: "plan",
    sm_mass: p.summary?.sm_mass,
    alloy_sm: alloySummaryFromRows(p.summary?.alloy_sm || [], p.summary?.sm_mass),
    rev, updatedAt: Date.now(),
  };
  S.plan.rev = rev;
  S.wizard.eaf = eafPlan;
  S.wizard.sm = p.plans?.sm || null;
  S.wizard.eafMass = p.mass;
  S.wizard.smMass = p.summary?.sm_mass;
  S.wizard.rev = rev;
  S.lastCharge = eafSum.charge_result || S.lastCharge;
  S.chargeMass = p.mass;
  S.lastAlloy = null;
  S.alloy = null;
  S.dyn.data = null;
  S.dyn.rev = 0;
  refreshHeatFlow("plan");
  updateTop();
}

function syncHeatFromEaf(r) {
  const s = r?.summary || {};
  const rev = heatRev() + 1;
  S.heat = {
    ...S.heat, track: "eaf", grade: r.grade, mass: r.mass,
    mix: s.mix_keys || S.heat.mix, charge: s.charge_result || S.heat.charge,
    alloy: alloySummaryFromRows(s.alloy || [], s.tap_mass),
    initial: null, pre_c: s.pre?.C ?? S.heat.pre_c, pre_si: s.pre?.Si ?? 0.05,
    skip_decarb: false, dirty: false, dynamic: null, source: "wizard", rev,
    sm_mass: null, alloy_sm: null, updatedAt: Date.now(),
  };
  S.wizard.rev = rev;
  S.wizard.eaf = r;
  S.lastCharge = s.charge_result || S.lastCharge;
  S.chargeMass = r.mass;
  S.lastAlloy = null;
  S.alloy = null;
  S.dyn.data = null; S.dyn.rev = 0;
  refreshHeatFlow("wizard");
  updateTop();
}

function syncHeatFromSm(r) {
  const s = r?.summary || {};
  const rev = heatRev() + 1;
  S.heat = {
    ...S.heat, track: "sm",
    initial: s.initial || S.heat.initial,
    sm_mass: r.mass,
    alloy_sm: alloySummaryFromRows(s.alloy || [], s.tap_mass),
    skip_decarb: true, dirty: false, dynamic: null, source: "wizard", rev, updatedAt: Date.now(),
  };
  S.wizard.rev = rev;
  S.wizard.sm = r;
  S.dyn.data = null; S.dyn.rev = 0;
  refreshHeatFlow("wizard");
  updateTop();
}

function refreshHeatFlow(active) {
  const el = $("#heatflow");
  if (!el) return;
  const wrap = document.createElement("div");
  wrap.innerHTML = renderHeatFlow(active || S.view);
  if (wrap.firstElementChild) el.replaceWith(wrap.firstElementChild);
}

function renderHeatFlow(active) {
  const h = S.heat || {};
  const p = S.plan?.data;
  const pReady = !!p;
  const pStale = pReady && !planFresh();
  const dReady = dynFresh() || S.heat?.dynamic?.comp?.C != null;
  const dynC = S.dyn?.data?.prediction?.points?.[0]?.C ?? S.heat?.dynamic?.comp?.C ?? S.dyn?.state?.comp?.C;
  const planC = p?.summary?.final_eaf?.C;
  const planC2 = p?.summary?.final_sm?.C;
  const alloyKg = (h.alloy?.additions || []).reduce((a, x) => a + Number(x.mass || 0), 0);
  const alloySmKg = (h.alloy_sm?.additions || []).reduce((a, x) => a + Number(x.mass || 0), 0);
  const alloyText = alloyKg && alloySmKg ? f(alloyKg, 0) + "+" + f(alloySmKg, 0) + " kg" : alloyKg ? f(alloyKg, 0) + " kg" : alloySmKg ? f(alloySmKg, 0) + " kg" : "未补";
  const step = (key, no, title, val, cls) => `<button class="hf-step ${cls} ${active === key ? "active" : ""}" onclick="go('${key}')"><i>${no}</i><span>${title}</span><b>${val}</b></button>`;
  let nextKey = "plan", nextLabel = "初始规划";
  if (pReady && !pStale) {
    if (!heatHasCharge()) { nextKey = "charge"; nextLabel = "炉料配比"; }
    else if (!alloyKg && !alloySmKg) { nextKey = "alloy"; nextLabel = "合金补加"; }
    else { nextKey = "dynamic"; nextLabel = "动态操作"; }
  } else if (pStale) { nextLabel = "更新规划"; }
  return `<div class="heatflow" id="heatflow">
    <div class="hf-brand"><span class="hf-dot ${pStale ? "warn" : ""}"></span><div><b>当前炉次</b><span>${esc(gradeName(h.grade || S.grade))}${h.mass ? " · " + f(h.mass, 0) + " t" : ""}</span></div></div>
    <div class="hf-track">
      ${step("plan", "1", "初始规划", pStale ? "需更新" : pReady ? `C ${f(planC, 2)}→${f(planC2, 2)}` : "未生成", pStale ? "stale" : pReady ? "done" : "")}
      <span class="hf-arrow">→</span>
      ${step("charge", "2", "炉料", heatHasCharge() ? f(h.mass, 0) + " t" : "未定", heatHasCharge() ? "done" : "")}
      <span class="hf-arrow">→</span>
      ${step("alloy", "3", "合金", alloyText, (alloyKg || alloySmKg) ? "done" : "")}
      <span class="hf-arrow">→</span>
      ${step("dynamic", "4", "动态实测", dReady ? `C ${f(dynC, 3)}%` : "未开始", dReady ? "done" : "")}
    </div>
    <div class="hf-end">${pStale ? '<span class="badge risk">下游需同步</span>' : ""}<button class="btn sm primary" onclick="go('${nextKey}')">下一步：${nextLabel} →</button><button class="btn sm ghost" onclick="newHeat()">新炉次</button><button class="btn sm" id="hf-save" onclick="saveWholeHeat()">保存整炉</button></div>
  </div>`;
}

function namedMix(mix) {
  const out = {};
  for (const [k, v] of Object.entries(mix || {})) {
    const s = (S.boot?.scraps || []).find((x) => x.key === k);
    out[s ? s.name : k] = v;
  }
  return out;
}

function saveWholeHeat() {
  const payload = {
    kind: "heat",
    heat: { ...S.heat, charge: S.heat.charge || null },
    plan: S.plan?.data || null,
    summary: S.plan?.data ? {
      ...S.plan.data.summary,
      total_mass: S.plan.data.summary?.tap_mass,
      cost: S.plan.data.summary?.cost?.total,
      cost_per_t: S.plan.data.summary?.cost?.per_t,
    } : (S.heat?.charge ? {
      total_mass: S.heat.charge.total_mass, cost: S.heat.charge.cost,
      cost_per_t: S.heat.charge.cost_per_t,
    } : null),
  };
  saveRun("整炉方案 · " + gradeShort(S.heat?.grade || S.grade), payload);
}

function authToken() {
  try { return localStorage.getItem("steel-lab-token") || ""; } catch (e) { return ""; }
}

function sharecode() {
  try { return new URLSearchParams(location.search).get("sharecode") || ""; } catch (e) { return ""; }
}

function withSharecode(path) {
  const sc = sharecode();
  if (!sc) return path;
  return path + (path.includes("?") ? "&" : "?") + "sharecode=" + encodeURIComponent(sc);
}

function currentUser() {
  try { return localStorage.getItem("steel-lab-user") || ""; } catch (e) { return ""; }
}

function setUser(name) {
  try { localStorage.setItem("steel-lab-user", name || ""); } catch (e) {}
  const el = $("#top-user-text");
  if (el) el.textContent = name || "未设置";
}

async function api(path, method = "GET", body) {
  const doFetch = (token) => {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["X-Steel-Token"] = token;
    const user = currentUser();
    if (user) headers["X-Steel-User"] = encodeURIComponent(user);
    const opt = { method, headers };
    if (body !== undefined) opt.body = JSON.stringify(body);
    return fetch(withSharecode(path), opt);
  };
  let token = authToken();
  let res = await doFetch(token);
  let data = null;
  if (res.status === 401) {
    data = await res.json().catch(() => ({}));
    if (data.auth_required) {
      const v = window.prompt("请输入访问口令（部署时设置的 STEEL_LAB_TOKEN）");
      if (v && v.trim()) {
        token = v.trim();
        try { localStorage.setItem("steel-lab-token", token); } catch (e) {}
        res = await doFetch(token);
        data = await res.json().catch(() => ({}));
      } else {
        throw new Error("需要访问口令才能使用");
      }
    }
  } else {
    data = await res.json().catch(() => ({}));
  }
  if (!res.ok) {
    if (res.status === 401) {
      try { localStorage.removeItem("steel-lab-token"); } catch (e) {}
    }
    throw new Error(data.error || ("HTTP " + res.status));
  }
  return data;
}

function toast(msg, err = false) {
  const d = document.createElement("div");
  d.className = "toast" + (err ? " err" : "");
  d.textContent = msg;
  $("#toast").appendChild(d);
  setTimeout(() => d.remove(), 3200);
}

function setBusy(btn, on) {
  if (!btn) return;
  if (on) { btn.dataset.html = btn.innerHTML; btn.innerHTML = '<span class="spin"></span>计算中'; btn.disabled = true; }
  else { btn.innerHTML = btn.dataset.html || btn.innerHTML; btn.disabled = false; }
}

/* ---------------- boot ---------------- */
async function boot() {
  S.boot = await api("/api/bootstrap");
  if (S.boot.config?.multi_user && !currentUser()) {
    let name = "";
    while (!name) {
      name = (window.prompt("输入你的名字（多人共用时用来区分各自的炉次记录，随便填）") || "").trim().slice(0, 24);
      if (!name && !window.confirm("不填名字就看不到自己的炉次记录。确定跳过？")) break;
    }
    if (name) setUser(name);
  }
  setUser(currentUser());
  const qpGrade = new URLSearchParams(location.search).get("grade");
  const saved = qpGrade || localStorage.getItem("steel-lab-grade");
  if (saved && S.boot.grades_eaf[saved]) S.grade = saved;
  const qpTrack = new URLSearchParams(location.search).get("track");
  if (qpTrack === "eaf" || qpTrack === "sm") S.wizard.track = qpTrack;
  const qpStep = parseInt(new URLSearchParams(location.search).get("step") || "", 10);
  if (!isNaN(qpStep)) S.wizard.pendingStep = qpStep;
  try {
    const savedChat = JSON.parse(localStorage.getItem("steel-lab-chat") || "[]");
    if (Array.isArray(savedChat)) S.chat = savedChat.filter((m) => m && !m.pending).slice(-20);
  } catch (e) {}
  try {
    const ps = JSON.parse(localStorage.getItem("steel-lab-plan-settings") || "{}");
    if (ps.mass) S.plan.mass = ps.mass;
    if (ps.grade && S.boot.grades_eaf[ps.grade]) S.plan.grade = ps.grade;
    if (typeof ps.safe === "boolean") S.plan.safe = ps.safe;
    if (ps.pre_c) S.plan.pre_c = ps.pre_c;
    if (ps.pre_c_grade) S.plan.pre_cGrade = ps.pre_c_grade;
    if (ps.power_kwh) S.plan.power_kwh = ps.power_kwh;
    if (ps.other_per_t != null) S.plan.other_per_t = ps.other_per_t;
    if (typeof ps.use_heat === "boolean") S.plan.useHeat = ps.use_heat;
    if (ps.alloy_pos != null) S.alloyPos = ps.alloy_pos;
    if (ps.flux_feo != null) S.slag.feo = ps.flux_feo;
  } catch (e) {}
  try {
    const ap = localStorage.getItem("steel-lab-alloy-pos");
    if (ap != null && !isNaN(parseFloat(ap))) S.alloyPos = parseFloat(ap);
  } catch (e) {}
  renderNav();
  updateTop();
  const now = new Date();
  $("#top-date").textContent = now.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" }) + " " + now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  const initial = (location.hash || "").replace("#", "");
  go(NAV.some((n) => n.key === initial) ? initial : "plan");
  $("#btn-settings").onclick = openSettings;
  window.addEventListener("hashchange", () => {
    const view = (location.hash || "").replace("#", "");
    if (view && view !== S.view && NAV.some((n) => n.key === view)) go(view);
  });
}

function renderNav() {
  $("#nav").innerHTML = '<div class="nav-label">工作区</div>' + NAV.map((n) =>
    `<button data-view="${n.key}" class="${S.view === n.key ? "active" : ""}">${ICONS[n.icon]}<span>${n.label}</span></button>`
  ).join("");
  $$("#nav button").forEach((b) => b.onclick = () => go(b.dataset.view));
}

function updateTop() {
  $("#top-grade").textContent = gradeName(S.grade);
  const tu = $("#top-user-text");
  if (tu) tu.textContent = currentUser() || "未设置";
  const h = S.heat || {};
  const th = $("#top-heat-text");
  if (th) {
    if (!h.mass && !heatHasCharge()) th.textContent = "炉次未建立";
    else {
      const alloyKg = (h.alloy?.additions || []).reduce((a, x) => a + Number(x.mass || 0), 0);
      const massText = h.sm_mass && h.mass ? `${f(h.mass, 0)}→${f(h.sm_mass, 0)} t` : `${f(h.mass, 0)} t`;
      const cText = h.dynamic?.comp?.C != null ? ` · C ${f(h.dynamic.comp.C, 3)}%` : "";
      th.textContent = `${gradeShort(h.grade || S.grade)} · ${massText} · ${alloyKg ? f(alloyKg, 0) + " kg 合金" : "未补合金"}${cText}`;
    }
  }
  $("#crumb").innerHTML = "工作台 / <b>" + (NAV.find((n) => n.key === S.view)?.crumb || "") + "</b>";
  $$("#nav button[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === S.view));
}

function go(view) {
  S.view = view;
  if (location.hash !== "#" + view) history.replaceState(null, "", "#" + view);
  updateTop();
  const fn = { dashboard: viewDashboard, plan: viewPlan, reference: viewReference, wizard: viewWizard, dynamic: viewDynamic, charge: viewCharge, slag: viewSlag, alloy: viewAlloy, refine: viewRefine, kb: viewKB, agent: viewAgent, runs: viewRuns }[view];
  if (fn) fn();
  window.scrollTo({ top: 0, behavior: "instant" });
}

/* ---------------- dashboard ---------------- */
function daysToChallenge() {
  const target = new Date("2026-11-17T12:00:00Z");
  const diff = Math.ceil((target - new Date()) / 86400000);
  return diff > 0 ? diff : 0;
}

async function viewDashboard() {
  const g = S.boot.grades_eaf[S.grade];
  const runs = await api("/api/runs").catch(() => ({ runs: [] }));
  S.runs = runs.runs || [];
  const spec = g.specs;
  const rows = Object.entries(S.boot.grades_eaf).map(([k, x]) => {
    const s = x.specs;
    return `<tr><td>${x.short}</td>
      <td>${fmtSpec(s.C)}</td><td>${fmtSpec(s.Mn)}</td><td>${fmtSpec(s.P)}</td><td>${fmtSpec(s.S)}</td>
      <td>${s.Cr?.[1] != null ? "≤" + s.Cr[1] : "—"}</td><td>${s.Ni?.[1] != null ? "≤" + s.Ni[1] : "—"}</td></tr>`;
  }).join("");

  $("#view").innerHTML = `
  <div class="hero">
    <div>
      <div class="tag">steelChallenge-21 · Regional</div>
      <h2>把炉料算准，把成本打下来。</h2>
      <p>基于 steeluniversity 两份操作手册的配比与精炼计算工作台。目标钢种：${g.name}。${g.note}</p>
      <div class="actions">
        <button class="btn primary" onclick="go('plan')">先做初始规划</button>
        <button class="btn" onclick="go('wizard')">打开操作流程</button>
        <button class="btn" onclick="go('charge')">只算配料</button>
        <button class="btn" onclick="go('reference')">看 2024 参考炉次</button>
        <button class="btn" onclick="go('agent')">问 AI 助手</button>
      </div>
    </div>
    <div class="right">
      <div class="days">${daysToChallenge()}<small>DAYS TO REGIONAL</small></div>
      <div class="small" style="color:#8d949b;margin-top:6px">2026-11-17 · 12:00 UTC</div>
    </div>
  </div>

  ${renderHeatFlow("dashboard")}

  <div class="grid g4 mt16">
    <div class="card kpi"><div class="label">当前钢种</div><div class="value" style="font-size:19px">${g.short}</div><div class="note">${g.standard}</div></div>
    <div class="card kpi accent"><div class="label">废钢装入上限</div><div class="value">90<small>t</small></div><div class="note">总容积约 100 m³ / 3 料斗</div></div>
    <div class="card kpi"><div class="label">目标出钢量</div><div class="value">100<small>t</small></div><div class="note">余量由合金/添加剂补足</div></div>
    <div class="card kpi"><div class="label">赛事倒计时</div><div class="value">${daysToChallenge()}<small>天</small></div><div class="note">区域赛 11 月 17 日</div></div>
  </div>

  <div class="grid mt16" style="grid-template-columns:1.35fr .9fr">
    <div class="card">
      <div class="card-h"><h3>钢种成分窗口</h3><span class="sub">EAF 出钢目标 · wt%</span><div class="spacer"></div><span class="badge neutral">表 2.2.1 + 赛题</span></div>
      <div class="table-wrap"><table class="tbl grade-table">
        <thead><tr><th>钢种</th><th class="num">C</th><th class="num">Mn</th><th class="num">P</th><th class="num">S</th><th class="num">Cr</th><th class="num">Ni</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
    </div>
    <div class="card">
      <div class="card-h"><h3>快捷入口</h3><span class="sub">常用工作流</span></div>
      <div class="card-b quick-grid" style="grid-template-columns:1fr 1fr">
        ${quick("plan", "初始规划", "先定停氧/停真空锚点", "plan")}
        ${quick("wizard", "操作流程", "EAF / 二次精炼分开走", "route")}
        ${quick("charge", "配比优化", "LP 最小成本", "charge")}
        ${quick("slag", "EAF 造渣", "碱度 / 石灰 / 白云石", "refine")}
        ${quick("alloy", "合金补加", "回收率 / 夹带", "alloy")}
        ${quick("refine", "精炼计算", "脱氧 / 脱硫 / 脱碳", "refine")}
      </div>
    </div>
  </div>

  <div class="grid mt16" style="grid-template-columns:1fr 1fr">
    <div class="card">
      <div class="card-h"><h3>最近炉次</h3><div class="spacer"></div><button class="btn sm ghost" onclick="go('runs')">全部记录 →</button></div>
      <div>${S.runs.length ? S.runs.slice(0, 4).map((r) => `<div class="run-row"><div><div class="nm">${esc(r.name)}</div><div class="meta">${r.ts}</div></div><div class="badge neutral">${gradeShort(r.grade)}</div><div class="mono">${r.payload?.cost_per_t ? "$" + f(r.payload.cost_per_t, 1) + "/t" : "—"}</div><div></div><div></div></div>`).join("") : '<div class="empty">还没有保存的炉次。完成一次配料后保存。</div>'}</div>
    </div>
    <div class="card">
      <div class="card-h"><h3>使用顺序</h3><span class="sub">建议的备赛工作流</span></div>
      <div class="card-b" style="display:flex;flex-direction:column;gap:10px">
        ${step("01", "先做初始规划", "定装料、合金与每个检查点的元素停点；时间只作参考。")}
        ${step("02", "按流程执行", "EAF 与二次精炼分开走，一步接一步；停氧/停真空只看 C。")}
        ${step("03", "动态修正", "实测偏离计划时，用动态操作按当前成分重算下一步。")}
        ${step("04", "复盘校准", "用实际炉次结果修正收得率与回收率，越用越准。")}
      </div>
    </div>
  </div>`;
}

function step(n, t, d) {
  return `<div style="display:flex;gap:11px"><div class="mono" style="color:var(--accent);font-size:11px;padding-top:2px">${n}</div><div><b style="font-size:12.5px">${t}</b><div class="note">${d}</div></div></div>`;
}
function quick(view, title, sub, icon) {
  return `<button class="quick" onclick="go('${view}')"><div class="ico">${ICONS[icon]}</div><b>${title}</b><span>${sub}</span></button>`;
}
function fmtSpec(arr) {
  if (!arr) return "—";
  const [lo, hi] = arr;
  if (lo != null && hi != null) return lo + "–" + hi;
  if (hi != null) return "≤" + hi;
  return "—";
}

/* ---------------- initial plan ---------------- */
function planDefaultGrade() {
  const g = S.wizard.eaf?.grade || S.heat?.grade || S.grade;
  return S.boot?.grades_eaf?.[g] ? g : "sc21_engineering";
}

function planHeatReady() {
  const h = S.heat || {};
  if (h.track === "sm") return !!(h.initial || h.mix);
  return !!h.mix && (!h.grade || h.grade === S.plan.grade);
}

function viewReference() {
  $("#view").innerHTML = `
  <div class="page-head">
    <div><h1>2024 参考炉次</h1><p>从 2024 年培训录像 <code>meeting_01.mp4</code> 整理的 AISI 4140 实战炉次：装入 85.58 t → 出站 85.28 t，1 h 20 min，终点 1560°C，吨钢成本 $454.19。只作为操作节奏和参数参考，不是 2026 赛题的官方答案。</p></div>
    <div class="spacer"></div><span class="badge neutral">录像整理 · 2024</span>
  </div>
  <div class="grid g3">
    <div class="card"><div class="card-b"><div class="sub">炉次 / 钢种</div><div class="big" style="font-size:22px">AISI 4140</div><div class="hint">工程钢 · 2024 参考</div></div></div>
    <div class="card"><div class="card-b"><div class="sub">装入 → 出站</div><div class="big" style="font-size:22px">85.58 → 85.28 t</div><div class="hint">全程约 1 h 20 min</div></div></div>
    <div class="card"><div class="card-b"><div class="sub">终点温度 / 成本</div><div class="big" style="font-size:22px">1560°C · $454.19/t</div><div class="hint">录像最终结果</div></div></div>
  </div>

  <div class="card mt16">
    <div class="card-h"><h3>时间轴与关键参数</h3><span class="sub">按录像画面和语音整理</span></div>
    <div class="card-b">
      <div class="table-wrap"><table class="tbl">
        <thead><tr><th>阶段</th><th>画面读数 / 操作</th><th>参考值</th><th>要点</th></tr></thead>
        <tbody>
          <tr><td class="strong">EAF 熔化</td><td>功率 120%，氧 10 Nm³/min，碳 0 kg/min；渣门 / 氧枪 / 流打开</td><td>前两批料熔清</td><td>熔化期用高功率；电极下降可按住下箭头快速右滑，反复几次加快（模拟器 UI 技巧）</td></tr>
          <tr><td class="strong">EAF 吹氧 / 调温</td><td>功率降到 75%，继续吹氧；温度到 1628°C 左右加 EAF 合金</td><td>氧 10 Nm³/min</td><td>不要让温度长时间顶在上限；到 1632°C 过零点几秒立即断电、升氧枪</td></tr>
          <tr><td class="strong">出钢</td><td>1631°C 出钢；出钢后约降 1°C</td><td>~1632°C 停</td><td>出钢前确认 C/Si/Mn/Cr 窗口；出钢后进 CAS-OB</td></tr>
          <tr><td class="strong">CAS-OB</td><td>1566°C，$440/t；加 280 kg 硅锰 + 50 kg 高碳铬铁</td><td>按 C 停氧</td><td>CAS-OB 先吹氧脱碳；合金在停氧后加，避免氧化损失</td></tr>
          <tr><td class="strong">钢包脱气</td><td>1543°C，$452/t；目标真空 1.000 atm，氩气先 0</td><td>保持真空</td><td>脱气主要脱 H/N，不靠它大幅降 C</td></tr>
          <tr><td class="strong">LF / 连铸</td><td>1541°C，$455/t；最终 1560°C，$454.19/t</td><td>1 h 20 min</td><td>温度低再加热很贵；时间越长电耗和成本越高</td></tr>
        </tbody>
      </table></div>
    </div>
  </div>

  <div class="grid g2 mt16">
    <div class="card"><div class="card-h"><h3>可借鉴的 6 条</h3></div><div class="card-b">
      <ol class="ref-list">
        <li><b>功率前高后低</b>：熔化 120%，熔清/吹氧 75%，不要在吹氧阶段长时间满功率。</li>
        <li><b>氧枪 10 Nm³/min、碳粉 0</b>：靠供氧控制 FeO；渣门、氧枪、流打开，保证反应和温度均匀。</li>
        <li><b>出钢按 1632°C 控</b>：到温后零点几秒就断电压枪，出钢过程约降 1°C；后续温度留给 LF 精调。</li>
        <li><b>合金别全留到精炼</b>：这炉 CAS-OB 只补 280 kg 硅锰 + 50 kg 高碳铬铁，说明炉料阶段已把 Mn/Cr 配到接近目标。</li>
        <li><b>时间就是成本</b>：1 h 20 min、$454/t；多吹几分钟、温度低了再加热，都会直接推高电耗和吨钢成本。</li>
        <li><b>顺序固定</b>：CAS-OB → 钢包脱气 → LF → 连铸；先脱碳，再脱气，最后调温/成分。</li>
      </ol>
    </div></div>
    <div class="card"><div class="card-h"><h3>模拟器操作技巧</h3><span class="sub">只影响操作速度，不影响工艺</span></div><div class="card-b">
      <ul class="ref-list">
        <li><b>电极快速下降</b>：按住向下的按钮，快速向右滑动再松开，反复重复；比等电极自动下降快很多。</li>
        <li><b>等待时加速</b>：炉料熔化等待期可用 4x / 8x / 16x；接近停氧、取样、出钢时降回 1x，避免错过窗口。</li>
        <li><b>及时开炉盖/加料</b>：第一批料熔清后按录像节奏加第二批，别让炉子空等。</li>
        <li><b>温度与时间同步</b>：到小方坯前约 2 min、温降约 2–3°C，提前把时间算进去。</li>
      </ul>
      <div class="hint mt12">录像里的 280 kg 硅锰 + 50 kg 高碳铬铁是 AISI 4140 的现场补加量，不能直接套到 2026 的 sc21_engineering；当前钢种仍以「初始规划 / 合金补加」按 17 元素窗口实算为准。</div>
    </div></div>
  </div>

  <div class="card mt16"><div class="card-h"><h3>和 2026 赛题的区别</h3></div><div class="card-b">
    <p class="note">2024 录像的钢种是 <b>AISI 4140</b>（C 0.41–0.42、Cr 1.04–1.06、Mo 0.22–0.23），2026 赛题是 <b>工程用钢 sc21_engineering</b>（C 0.50–0.56、Cr 1.50–1.60、Mo ≤0.024），两者成分窗口不同。可借鉴的是节奏、功率/氧枪设定、出钢温度和“别把合金全留到精炼”的思路；炉料配比、合金量和成本必须用当前钢种重新计算。</p>
  </div></div>`;
}

async function viewPlan() {
  await ensureRuns();
  if (!S.plan.grade || !S.boot.grades_eaf[S.plan.grade]) S.plan.grade = planDefaultGrade();
  if (!S.plan.mass) S.plan.mass = S.heat?.mass || S.wizard.eaf?.mass || 82;
  // 不同钢种的停氧 C 不同（结构钢 0.10、TiNb 0.03、管线 0.05、工程钢 0.37），
  // 不能让低 C 钢种继承 0.37 的旧值，否则规划直接报“初始 C 高于上限”。
  if (S.plan.pre_cGrade !== S.plan.grade) {
    S.plan.pre_c = S.boot.default_pre_c?.[S.plan.grade] ?? 0.37;
    S.plan.pre_cGrade = S.plan.grade;
  }
  // 只做“默认值”初始化，不在每次进入页面时把用户手动勾选/取消的状态改回去
  if (S.plan.useHeat == null) S.plan.useHeat = planHeatReady();
  if (!planHeatReady()) S.plan.useHeat = false;
  $("#view").innerHTML = `
  <div class="page-head">
    <div><h1>初始规划</h1><p>开炉前先把整炉路线定下来：每一站只看指定元素/温度，到什么值停、偏离了怎么处理。分钟数只是参考节拍，执行时交给「动态操作」按实测成分滚动修正。</p></div>
    <div class="spacer"></div>
    <div class="badge neutral">EAF → CAS-OB → 脱气 → LF</div>
  </div>
  ${renderHeatFlow("plan")}
  <div id="plan-setup">${renderPlanSetup()}</div>
  <div id="plan-result" class="mt14">${S.plan.data ? renderPlanResult(S.plan.data) : '<div class="card"><div class="empty">正在生成初始规划…</div></div>'}</div>`;
  bindPlanSetup();
  if (S.plan.data) bindPlanResult();
  else setTimeout(runInitialPlan, 60);
}

function renderPlanSetup() {
  const p = S.plan;
  const heatReady = planHeatReady();
  const mismatch = S.heat?.track === "eaf" && S.heat?.mix && S.heat?.grade && S.heat.grade !== p.grade;
  const heatText = S.heat?.track === "sm"
    ? `当前二次精炼装入成分${S.heat?.mass ? ` · ${S.heat.mass} t` : ""}`
    : `当前炉料${S.heat?.alloy ? " + 合金" : ""}方案${S.heat?.mass ? ` · ${S.heat.mass} t` : ""}`;
  return `<div class="card plan-setup">
    <div class="card-h"><h3>炉次参数</h3><span class="sub">先规划 · 再执行</span><div class="spacer"></div><span class="badge neutral">整吨装料 · 10 kg 添加剂</span></div>
    <div class="card-b">
      <div class="form-grid plan-form">
        <label class="field full"><span>基准炉次（用它的实际装入量 / 电耗 / 炉料方案）</span>
          <select id="plan-base">
            <option value="">— 不指定，按下面参数 —</option>
            ${(S.runs || []).filter((r) => !!runEafRef(r)).map((r) => `<option value="${r.id}" ${S.plan.baseRunId === r.id ? "selected" : ""}>${esc(r.name)}</option>`).join("")}
          </select>
        </label>
        <label class="field"><span>目标钢种</span>
          <select id="plan-grade">${Object.entries(S.boot.grades_eaf).map(([k, x]) => `<option value="${k}" ${k === p.grade ? "selected" : ""}>${x.name}</option>`).join("")}</select>
        </label>
        <label class="field"><span>废钢装入量 t（整吨）</span><input id="plan-mass" class="mono" type="number" min="80" max="110" step="1" value="${p.mass}"></label>
        <label class="field"><span>模式</span><select id="plan-safe"><option value="1" ${p.safe ? "selected" : ""}>稳健（推荐）</option><option value="0" ${!p.safe ? "selected" : ""}>成本优先</option></select></label>
        <label class="field"><span>停氧目标 C %</span><input id="plan-prec" class="mono" type="number" step="0.01" min="0.01" max="0.60" value="${p.pre_c ?? 0.37}"></label>
        <label class="field"><span>电耗 kWh（90 t 基准，按装入量折算）</span><input id="plan-kwh" class="mono" type="number" step="10" value="${p.power_kwh ?? 34200}"></label>
        <label class="field"><span>其他成本 $/t（模拟器口径填 0；全成本可填 37）</span><input id="plan-other" class="mono" type="number" step="1" value="${p.other_per_t ?? 0}"></label>
        <label class="field"><span>白云石设计 FeO %（FeO 会稀释 MgO，45 较稳妥）</span><input id="plan-feo" class="mono" type="number" step="1" min="20" max="60" value="${S.slag.feo ?? 45}"></label>
        <label class="field plan-form-action"><span>&nbsp;</span><button class="btn primary" id="plan-run">生成整炉初始规划</button></label>
      </div>
      <label class="plan-heat-check ${heatReady ? "" : "disabled"}">
        <input type="checkbox" id="plan-use-heat" ${heatReady && p.useHeat ? "checked" : ""} ${heatReady ? "" : "disabled"}>
        <span>${mismatch ? `当前炉料方案是「${esc(gradeName(S.heat.grade))}」，与目标钢种不一致` : `沿用${heatText}，不重新优化炉料/合金`}</span>
        ${heatReady ? "" : `<i>${mismatch ? "先按目标钢种重新算炉料，再回来生成规划" : "先到「炉料配比」或「合金补加」生成方案，勾选后可直接沿用"}</i>`}
      </label>
      <div class="hint">规划给出两段：EAF 与二次精炼分别按当前所选钢种的成分窗口判定（各检查点会列出实际窗口）；两段是同一炉钢的前后工序，不是两炉钢。</div>
    </div>
  </div>`;
}

function bindPlanSetup() {
  $("#plan-run").onclick = runInitialPlan;
  $("#plan-grade").onchange = () => {
    S.plan.grade = $("#plan-grade").value;
    // 钢种是炉料/合金/规划的共同基准：这里改了，炉料页也要跟着改，
    // 否则会出现“规划按新钢种、炉料还按旧钢种”的错配。
    S.grade = S.plan.grade;
    try { localStorage.setItem("steel-lab-grade", S.grade); } catch (e) {}
    S.lastCharge = null;
    S.plan.data = null;
    persistPlanSettings();
    viewPlan();
  };
  $("#plan-mass").onchange = () => {
    S.plan.mass = Math.max(80, Math.min(110, parseInt($("#plan-mass").value || "82", 10)));
    S.chargeMass = S.plan.mass;
    S.slag.lime = S.slag.dol = S.slag.flu = null;
    S.slag.manual = false;
    persistPlanSettings();
    refreshPlanResult();
  };
  const baseSel = $("#plan-base");
  if (baseSel) baseSel.onchange = () => {
    const run = (S.runs || []).find((x) => x.id === baseSel.value);
    if (!run) { S.plan.baseRunId = null; viewPlan(); return; }
    const ref = runEafRef(run) || {};
    const p = run.payload || {};
    const eaf = p.eaf || p.plan?.plans?.eaf || {};
    const ss = eaf.summary || p.summary || {};
    // 历史炉次的“炉料”在 summary.mix_keys（dict），不是 eaf.mix；两者都兼容。
    const baseMix = eaf.mix || ss.mix_keys || p.summary?.mix_keys || null;
    const mixMass = baseMix ? Object.values(baseMix).reduce((a, b) => a + Number(b || 0), 0) : 0;
    const baseMass = Number(ss.mass || eaf.mass || mixMass || ref.tap_mass || S.plan.mass);
    S.plan.baseRunId = run.id;
    S.plan.mass = Math.round(baseMass);
    S.plan.grade = ref.grade || p.grade || S.plan.grade;
    if (ss.energy_kwh) {
      S.plan.power_kwh = Number(ss.energy_kwh) * 90 / Number(ss.mass || baseMass);
    }
    if (baseMix) {
      S.heat = { ...S.heat, track: "eaf", grade: S.plan.grade, mass: S.plan.mass,
                 mix: baseMix, charge: ss.charge_result || null, alloy: null, initial: null };
    }
    S.plan.useHeat = !!baseMix;
    S.grade = S.plan.grade;
    try { localStorage.setItem("steel-lab-grade", S.grade); } catch (e) {}
    persistPlanSettings();
    toast("已按历史炉次填入参数：" + run.name);
    viewPlan();
  };
  $("#plan-prec").onchange = () => { S.plan.pre_c = parseFloat($("#plan-prec").value) || S.plan.pre_c; S.plan.pre_cGrade = S.plan.grade; persistPlanSettings(); refreshPlanResult(); };
  $("#plan-kwh").onchange = () => { S.plan.power_kwh = Math.max(0, parseFloat($("#plan-kwh").value) || 0); persistPlanSettings(); refreshPlanResult(); };
  $("#plan-other").onchange = () => { S.plan.other_per_t = Math.max(0, parseFloat($("#plan-other").value) || 0); persistPlanSettings(); refreshPlanResult(); };
  $("#plan-feo").onchange = () => {
    S.slag.feo = Math.max(20, Math.min(60, parseFloat($("#plan-feo").value) || 45));
    S.slag.lime = S.slag.dol = S.slag.flu = null;
    S.slag.manual = false;
    persistPlanSettings();
    refreshPlanResult();
  };
  $("#plan-safe").onchange = () => { S.plan.safe = $("#plan-safe").value !== "0"; persistPlanSettings(); refreshPlanResult(); };
  $("#plan-use-heat").onchange = (e) => { S.plan.useHeat = e.target.checked; persistPlanSettings(); };
}

async function runInitialPlan() {
  const btn = $("#plan-run");
  if (btn) setBusy(btn, true);
  S.plan.busy = true;
  try {
    const grade = $("#plan-grade")?.value || S.plan.grade || "sc21_engineering";
    S.plan.grade = grade;
    S.grade = grade;
    try { localStorage.setItem("steel-lab-grade", grade); } catch (e) {}
    const mass = Math.max(80, Math.min(110, parseInt($("#plan-mass")?.value || String(S.plan.mass || 82), 10)));
    const safe = ($("#plan-safe")?.value || (S.plan.safe ? "1" : "0")) !== "0";
    const pre_c = parseFloat($("#plan-prec")?.value || String(S.plan.pre_c || 0.37));
    S.plan.pre_c = pre_c;
    S.plan.pre_cGrade = grade;
    const useHeat = $("#plan-use-heat") ? $("#plan-use-heat").checked : S.plan.useHeat;
    const powerBase = parseFloat($("#plan-kwh")?.value || String(S.plan.power_kwh || 34200)) || 34200;
    const power_kwh = powerBase * mass / 90;
    const other_per_t = parseFloat($("#plan-other")?.value || String(S.plan.other_per_t ?? 0));
    const flux_feo = Math.max(20, Math.min(60, parseFloat($("#plan-feo")?.value || String(S.slag.feo ?? 45)) || 45));
    S.slag.feo = flux_feo;
    S.plan.power_kwh = powerBase;
    S.plan.other_per_t = other_per_t;
    S.plan.mass = mass;
    S.plan.safe = safe;
    S.plan.useHeat = useHeat;
    persistPlanSettings();
    const body = { grade, mass, safe, pre_c, pre_si: 0.05, power_kwh, other_per_t, flux_feo };
    if (S.alloyPos != null) body.alloy_pos = S.alloyPos;
    if (useHeat && planHeatReady()) {
      if (S.heat.mix) body.mix = S.heat.mix;
      if (S.heat.charge?.retention) body.retention = S.heat.charge.retention;
      if (S.heat.alloy) {
        body.alloy_plan = Object.fromEntries((S.heat.alloy.additions || []).map((a) => [a.key, a.mass]));
      }
      if (S.heat.track === "sm") {
        if (S.heat.sm_mass || S.heat.mass) body.sm_mass = S.heat.sm_mass || S.heat.mass;
        if (S.heat.initial) body.sm_initial = S.heat.initial;
        const smAlloy = S.heat.alloy_sm?.additions || S.heat.alloy?.additions || [];
        if (smAlloy.length) body.sm_alloy = Object.fromEntries(smAlloy.map((a) => [a.key, a.mass]));
      }
    }
    const r = await api("/api/plan/initial", "POST", body);
    if (r.status !== "ok") throw new Error(r.message || "无可行规划");
    S.plan.data = r;
    S.plan.grade = r.grade;
    S.plan.mass = r.mass;
    S.plan.safe = safe;
    S.plan.dataSig = planSettingsSig();
    syncHeatFromPlan(r);
    S.plan.useHeat = useHeat;
    S.grade = r.grade;
    localStorage.setItem("steel-lab-grade", S.grade);
    persistPlanSettings();
    updateTop();
    const setup = $("#plan-setup");
    if (setup) { setup.innerHTML = renderPlanSetup(); bindPlanSetup(); }
    $("#plan-result").innerHTML = renderPlanResult(r);
    bindPlanResult();
    toast("初始规划已生成：EAF 出钢 C " + f(r.summary.final_eaf?.C, 3) + "% → 精炼终点 C " + f(r.summary.final_sm?.C, 3) + "%");
  } catch (e) {
    toast("生成失败：" + e.message, true);
    // 失败时不要继续显示上一份旧规划，否则看起来像是“设置又被旧结果覆盖了”
    S.plan.data = null;
    S.plan.dataSig = null;
    const box = $("#plan-result");
    if (box) box.innerHTML = `<div class="card"><div class="empty">${esc(e.message)}</div></div>`;
  }
  S.plan.busy = false;
  if (btn) setBusy(btn, false);
}

function refreshPlanResult() {
  const box = $("#plan-result");
  if (!box || !S.plan.data) return;
  box.innerHTML = renderPlanResult(S.plan.data);
  bindPlanResult();
}

function renderPlanResult(p) {
  const s = p.summary;
  const c = s.cost;
  const bad = (s.out_of_spec_eaf || []).length + (s.out_of_spec_sm || []).length;
  const stale = !planFresh();
  return `${stale ? `<div class="plan-stale"><div><b>当前炉料/合金已变更</b><span>这份初始规划是旧版本；下面的炉料、合金和检查点可能和当前炉次不一致。</span></div><button class="btn sm primary" id="plan-regen">按当前炉次重新生成</button></div>` : ""}
  <div class="card plan-hero">
    <div class="card-h"><h3>${esc(p.grade_name)} · 整炉初始规划</h3><span class="sub">装入 ${f(p.mass, 0)} t → 二次精炼 ${f(s.sm_mass, 0)} t${s.time_target_min ? " · 参考节拍约 " + f(s.time_target_min, 0) + " min" : ""}</span><div class="spacer"></div>
      <span class="badge ${bad ? "risk" : "pass"}">${bad ? bad + " 项需注意" : "两段全部达标"}</span>
      <button class="btn sm" id="plan-to-charge">看炉料</button>
      <button class="btn sm" id="plan-to-alloy">看合金</button>
      <button class="btn sm" id="plan-save-eaf">保存 EAF</button>
      <button class="btn sm" id="plan-save-sm">保存二次精炼</button>
      <button class="btn sm" id="plan-print">打印规划</button>
      <button class="btn sm" id="plan-to-wizard">打开分步向导</button>
      <button class="btn sm primary" id="plan-to-dyn">载入动态操作 →</button>
    </div>
    <div class="card-b">
      <div class="plan-kpis">
        <div><span>废钢装入</span><b>${f(p.mass, 0)} t</b><i>整吨装料</i></div>
        <div><span>EAF 出钢</span><b>${f(s.tap_mass, 1)} t</b><i>C ${f(s.final_eaf?.C, 3)}%</i></div>
        <div><span>精炼出站</span><b>${f(s.sm_mass, 1)} t</b><i>C ${f(s.final_sm?.C, 3)}%</i></div>
        <div><span>全程成本（含电）</span><b>${money(c.total)}</b><i>材料 ${money((c.scrap || 0) + (c.eaf_alloy || 0) + (c.flux || 0) + (c.oxygen || 0))} + 电 ${money(c.energy || 0)} + 其他 ${money(c.other || 0)}</i></div>
        <div><span>吨钢成本</span><b>$${f(c.per_t, 1)}<small>/t</small></b><i>${p.safe ? "稳健模式" : "成本优先"}${(c.other || 0) > 0 ? ` · 不含其他 $${f((c.total - (c.other || 0)) / (s.sm_mass || p.mass), 1)}/t` : ""}</i></div>
      </div>
      <div class="plan-path-title"><b>关键 C 轨迹</b><span>从炉料带入到精炼终点；中间两个是停点，不是时间点</span></div>
      ${renderPlanPath(s.c_path)}
      <div class="plan-path-note"><span class="dot eaf"></span>EAF 段 <span class="dot sm"></span>二次精炼段 · 停氧/停真空都按 C 判断，时间只作参考</div>
    </div>
  </div>
  <div class="card mt12 plan-elements">
    <div class="card-h"><h3>元素要求对照</h3><span class="sub">EAF 出钢 13 元素 · 二次精炼出站 17 元素</span><div class="spacer"></div><span class="badge neutral">按目标窗口逐项核对</span></div>
    <div class="card-b el-req-wrap">
      ${renderElementChecks("EAF 出钢（13 元素）", s.checks_eaf, "eaf")}
      ${renderElementChecks("二次精炼出站（17 元素）", s.checks_sm, "sm")}
    </div>
  </div>
  <div class="plan-track-grid mt12">
    ${renderPlanTrack("eaf", p)}
    ${renderPlanTrack("sm", p)}
  </div>
  <div class="grid g2 mt12 plan-tables">
    ${renderPlanChargeCard(p)}
    ${renderPlanAlloyCard(p)}
  </div>
  <div class="card mt12 plan-notes">
    <div class="card-h"><h3>执行红线</h3><span class="sub">照这条走，别靠感觉</span></div>
    <div class="card-b"><div class="plan-note-grid">${(p.notes || []).map((n, i) => `<div><b>${String(i + 1).padStart(2, "0")}</b><span>${esc(n)}</span></div>`).join("")}</div></div>
  </div>
  <div class="print-only">${renderPlanPrint(p)}</div>`;
}

function renderPlanPath(path) {
  return `<div class="plan-path">${(path || []).map((x, i) => `${i ? '<span class="plan-path-arrow">→</span>' : ""}<div class="plan-path-node ${x.track}"><span>${esc(x.label)}</span><b>${f(x.c, 3)}<small>%</small></b><i>${esc(x.note)}</i></div>`).join("")}</div>`;
}

function renderPlanTrack(track, p) {
  const isEaf = track === "eaf";
  const cps = (p.checkpoints || []).filter((c) => c.track === track);
  const s = p.summary;
  const final = isEaf ? s.final_eaf : s.final_sm;
  const bad = isEaf ? (s.out_of_spec_eaf || []).length : (s.out_of_spec_sm || []).length;
  const cost = isEaf ? (s.cost.eaf_total ?? (s.cost.scrap + s.cost.eaf_alloy + s.cost.flux + s.cost.oxygen)) : s.cost.sm_total;
  if (!cps.length) {
    return `<section class="card plan-track ${track}"><div class="plan-track-head"><div class="plan-track-badge">${isEaf ? "EAF" : "SM"}</div><div><h3>${isEaf ? "电弧炉段" : "二次精炼段"}</h3><p>二次精炼规划未生成</p></div></div><div class="card-b"><div class="empty">检查装入成分或合金方案后重试。</div></div></section>`;
  }
  return `<section class="card plan-track ${track}">
    <div class="plan-track-head">
      <div class="plan-track-badge">${isEaf ? "EAF" : "SM"}</div>
      <div class="plan-track-title"><h3>${isEaf ? "电弧炉段" : "二次精炼段"} · ${cps.length} 个检查点</h3><p>${isEaf ? "装料 → 熔清 → 造渣 → 吹氧 → 取样 → 合金化 → 调温 → 出钢" : "到站 → CAS-OB → 脱气 → 脱氧 → 合金化 → 调温 → 连铸"}</p></div>
      <div class="spacer"></div>
      <div class="plan-track-meta"><b>C ${f(final?.C, 3)}%</b><span>${isEaf ? "出钢" : "出站"} · ${money(cost)}${isEaf && s.tap_mass ? ` · $${f(cost / s.tap_mass, 1)}/t` : ""}</span></div>
      <div class="plan-track-actions"><button class="btn sm" data-plan-wizard="${track}">分步向导</button><button class="btn sm" data-plan-dyn="${track}">载入动态</button></div>
    </div>
    <div class="plan-track-body">${cps.map((cp) => renderPlanCheckpoint(cp)).join("")}</div>
    <div class="plan-track-foot"><span class="badge ${bad ? "risk" : "pass"}">${bad ? bad + " 项需注意" : "成分窗口全部达标"}</span><span>${isEaf ? "EAF 判定按 0.50–0.56% C 等 13 元素 · 氧枪 150 Nm³/min，碳枪 0" : "二次精炼判定按 0.35–0.40% C 等 17 元素 · CAS-OB“吹氧”开关必须打开"}</span></div>
  </section>`;
}

function renderPlanCheckpoint(cp) {
  const hasC = cp.c != null;
  const win = cp.c_window ? `${f(cp.c_window[0], 2)}–${f(cp.c_window[1], 2)}%` : "";
  const t = cp.probe && cp.probe.T;
  const tLine = t ? `<span class="plan-cp-temp">计划温度 <b>${t[0]}–${t[1]}°C</b></span>` : "";
  return `<div class="plan-cp kind-${esc(cp.kind || "state")}">
    <div class="plan-cp-no">${String(cp.no).padStart(2, "0")}</div>
    <div class="plan-cp-main">
      <div class="plan-cp-head"><b>${esc(cp.stage)}</b><span>${esc(cp.title)}</span><em>${cp.ref_min != null ? "参考 " + f(cp.ref_min, 0) + " min" : "按元素"}</em></div>
      <div class="plan-cp-trigger"><i>判断</i>${esc(cp.trigger)}</div>
      ${hasC || t ? `<div class="plan-cp-values">${hasC ? `<span>计划 C <b>${f(cp.c, 3)}%</b>${win ? `<i>窗口 ${win}</i>` : ""}</span>` : ""}${tLine}</div>` : ""}
      <div class="plan-cp-action">${esc(cp.action)}</div>
      ${(cp.checks || []).length ? `<div class="plan-cp-checks">${cp.checks.map((x) => `<span>${esc(x)}</span>`).join("")}</div>` : ""}
      ${cp.high || cp.low ? `<div class="plan-cp-branch">${cp.high ? `<p><b>偏高/超上</b>${esc(cp.high)}</p>` : ""}${cp.low ? `<p><b>偏低/超下</b>${esc(cp.low)}</p>` : ""}</div>` : ""}
    </div>
  </div>`;
}

function renderElementChecks(title, checks, track) {
  const rows = checks || [];
  return `<div class="el-req-block ${track}">
    <div class="el-req-head"><b>${title}</b><span>${rows.filter((x) => x.status === "ok").length}/${rows.length} 合格</span></div>
    <div class="el-req-grid">${rows.map((c) => {
      const st = c.status === "ok" ? "pass" : (c.status === "low" ? "adjust" : "risk");
      const label = c.status === "ok" ? "合格" : (c.status === "low" ? "偏低" : "偏高");
      return `<div class="el-req ${st}"><span>${c.element}</span><b>${f(c.value, 4)}</b><i>${esc(fmtSpec([c.min, c.max]))}</i><em class="badge ${st}">${label}</em></div>`;
    }).join("")}</div>
  </div>`;
}

function renderPlanChargeCard(p) {
  const s = p.summary;
  const rows = (s.mix || []).map((x) => `<tr><td>${esc(x.name)}</td><td class="mono">${f(x.mass, 0)} t</td><td class="mono">${f(x.volume, 1)} m³</td><td class="mono">${money(x.cost)}</td></tr>`).join("");
  return `<div class="card"><div class="card-h"><h3>装料单（整吨）</h3><span class="sub">${f(p.mass, 0)} t · ${(s.baskets || []).length} 斗</span></div>
    <div class="table-wrap"><table class="tbl"><thead><tr><th>炉料</th><th>用量</th><th>体积</th><th>成本</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="card-b plan-sub"><span>总装入 ${f(p.mass, 0)} t</span><span>${(s.baskets || []).map((b) => "第" + b.index + "斗 " + f(b.mass, 0) + " t").join(" · ")}</span></div></div>`;
}

function renderPlanAlloyCard(p) {
  const s = p.summary;
  const list = (arr, label) => arr && arr.length ? `<div class="plan-alloy-group"><b>${label}</b>${arr.map((a) => `<div class="plan-alloy-row"><span>${esc(a.name)}</span><b class="mono">${f(a.mass, 0)} kg</b><i>${money(a.cost)}</i></div>`).join("")}</div>` : "";
  return `<div class="card"><div class="card-h"><h3>合金单（10 kg 档）</h3><span class="sub">EAF + 二次精炼</span></div>
    <div class="card-b plan-alloys">${list(s.alloy_eaf, "EAF 合金化")}${list(s.alloy_sm, "二次精炼合金化")}${(!s.alloy_eaf?.length && !s.alloy_sm?.length) ? '<div class="empty">无合金添加</div>' : ""}</div></div>`;
}

function bindPlanResult() {
  const dyn = $("#plan-to-dyn"); if (dyn) dyn.onclick = () => planToDynamic("eaf");
  const wz = $("#plan-to-wizard"); if (wz) wz.onclick = () => planOpenWizard("eaf");
  const pr = $("#plan-print"); if (pr) pr.onclick = () => window.print();
  const se = $("#plan-save-eaf"); if (se) se.onclick = async () => { await saveEafRun(S.plan.data?.plans?.eaf); };
  const ss = $("#plan-save-sm"); if (ss) ss.onclick = () => saveSmRun(S.plan.data?.plans?.sm, S.lastEafRunId || "");
  const regen = $("#plan-regen"); if (regen) regen.onclick = () => runInitialPlan();
  const ch = $("#plan-to-charge"); if (ch) ch.onclick = () => {
    const p = S.plan.data;
    if (!p) return;
    S.grade = p.grade;
    S.chargeMass = p.mass;
    S.lastCharge = p.plans?.eaf?.summary?.charge_result || S.lastCharge;
    go("charge");
  };
  const al = $("#plan-to-alloy"); if (al) al.onclick = () => {
    const p = S.plan.data;
    if (!p) return;
    S.lastCharge = p.plans?.eaf?.summary?.charge_result || S.lastCharge;
    S.lastAlloy = null; S.alloy = null;
    go("alloy");
  };
  $$("[data-plan-dyn]").forEach((b) => b.onclick = () => planToDynamic(b.dataset.planDyn));
  $$("[data-plan-wizard]").forEach((b) => b.onclick = () => planOpenWizard(b.dataset.planWizard));
}

function planAlloyResult(p) {
  const rows = p?.summary?.alloy_eaf || [];
  const kg = rows.reduce((a, x) => a + Number(x.mass || 0), 0);
  return {
    status: "ok", additions: rows, added_total: kg,
    cost: rows.reduce((a, x) => a + Number(x.cost || 0), 0),
    mass_after: p?.summary?.tap_mass, temperature_drop: Math.round(kg / 1000 * 6 * 10) / 10,
    final: p?.summary?.final_eaf || {}, warnings: p?.summary?.out_of_spec_eaf || [], unmet: [],
  };
}

function planOpenWizard(track) {
  const p = S.plan.data;
  if (!p || !p.plans || !p.plans[track]) { toast("该段还没有规划", true); return; }
  S.wizard[track] = p.plans[track];
  S.wizard.track = track;
  S.wizard.step = 0;
  if (track === "eaf") {
    S.wizard.eafMass = p.mass;
    S.wizard.smInitial = null;
  } else {
    S.wizard.smMass = p.summary.sm_mass;
  }
  go("wizard");
}

function planToDynamic(track) {
  const p = S.plan.data;
  if (!p || !p.plans || !p.plans[track]) { toast("该段还没有规划", true); return; }
  dynResetState(track);
  const s = S.dyn.state;
  s.mass = track === "eaf" ? p.mass : p.summary.sm_mass;
  if (track === "eaf") {
    const comp = p.summary.charge_composition || {};
    for (const e of ["C", "Si", "Mn", "Cr", "P", "S"]) if (comp[e] != null) s.comp[e] = comp[e];
    s.comp.C = p.summary.c_path?.[0]?.c ?? s.comp.C;
    s.temp = 1600;
    s.stage = "blow";
    s.target_c = p.summary.c_anchors?.blow ?? 0.37;
    s.o2 = 150; s.carbon = 0; s.power = 90;
  } else {
    const comp = p.summary.final_eaf || {};
    for (const e of ["C", "Si", "Mn", "Cr", "P", "S"]) if (comp[e] != null) s.comp[e] = comp[e];
    s.comp.O = 0.05;
    s.temp = 1565;
    s.stage = "casob";
    s.target_c = p.summary.c_anchors?.degas ?? 0.335;
    s.power = 20; s.o2_on = true;
  }
  go("dynamic");
  setTimeout(() => {
    dynLoadPlanNodes(track);
    runDynAdvice();
  }, 60);
}

function renderPlanPrint(p) {
  const s = p.summary;
  return `<h1>${esc(p.grade_name)} · 整炉初始规划</h1>
  <p>装入 ${f(p.mass, 0)} t · EAF 出钢 ${f(s.tap_mass, 1)} t（C ${f(s.final_eaf?.C, 3)}%）· 精炼出站 ${f(s.sm_mass, 1)} t（C ${f(s.final_sm?.C, 3)}%）· 全程 ${money(s.cost.total)}（$${f(s.cost.per_t, 1)}/t）</p>
  <p><b>关键 C 轨迹：</b>${(s.c_path || []).map((x) => x.label + " " + f(x.c, 3) + "%").join(" → ")}</p>
  ${(p.checkpoints || []).map((cp) => `<div class="print-step"><h3>${cp.track === "eaf" ? "EAF" : "SM"}-${String(cp.no).padStart(2, "0")} ${esc(cp.stage)} · ${esc(cp.title)}</h3><p><b>判断：</b>${esc(cp.trigger)}</p>${cp.c != null ? `<p><b>计划 C：</b>${f(cp.c, 3)}%${cp.c_window ? "（窗口 " + f(cp.c_window[0], 2) + "–" + f(cp.c_window[1], 2) + "%）" : ""}</p>` : ""}<p><b>操作：</b>${esc(cp.action)}</p><p><b>检查：</b>${(cp.checks || []).map((x) => esc(x)).join("；")}</p></div>`).join("")}
  <p><b>红线：</b>${(p.notes || []).map((x) => esc(x)).join("；")}</p>`;
}



/* ---------------- dynamic process ---------------- */
function dynDefaultState(track) {
  const h = S.heat || {};
  const sm = track === "sm";
  const src = {
    ...((h.charge && h.charge.composition) || {}),
    ...(h.initial || {}),
    ...(S.plan?.data?.summary?.final_sm || {}),
    ...(S.plan?.data?.summary?.final_eaf || {}),
  };
  const comp = {};
  for (const e of DYN_ELEMENTS) if (src[e] != null) comp[e] = Number(src[e]);
  return {
    track,
    mass: h.sm_mass || h.mass || S.plan?.data?.summary?.sm_mass || S.plan?.data?.mass || 0,
    time: 0,
    temp: sm ? 1565 : 1600,
    stage: sm ? "casob" : "blow",
    o2: sm ? 0 : 150,
    carbon: 0,
    power: sm ? 20 : 90,
    o2_on: true,
    vacuum: true,
    sm_grade: sm ? (S.plan?.data?.sm_grade || S.wizard?.sm?.grade || "sc21_refining") : undefined,
    target_c: sm ? 0.335 : (S.plan?.data?.summary?.c_anchors?.blow ?? 0.37),
    comp,
  };
}

function dynResetState(track) {
  S.dyn.track = track || "eaf";
  S.dyn.state = dynDefaultState(S.dyn.track);
  S.dyn.data = null;
  S.dyn.nodes = [];
  S.dyn.edges = [];
  S.dyn.seq = 1;
  S.dyn.pan = { x: 40, y: 40 };
  S.dyn.zoom = 1;
}

function viewDynamic() {
  if (!S.dyn.state) dynResetState(S.dyn.track);
  const st = S.dyn.state;
  if (st.track !== S.dyn.track) dynResetState(S.dyn.track);
  const s = S.dyn.state;
  const sm = S.dyn.track === "sm";
  $("#view").innerHTML = `
  <div class="page-head">
    <div><h1>动态操作</h1><p>不按固定时间轴：输入当前成分和工艺参数，按元素含量预测下一步；画布上可以自由拖拽、添加取样/吹氧/合金/调温等节点。</p></div>
    <div class="spacer"></div>
    <div class="dyn-tabs"><button data-dtrack="eaf" class="${!sm ? "active" : ""}">EAF 电弧炉</button><button data-dtrack="sm" class="${sm ? "active" : ""}">二次精炼</button></div>
    <button class="btn" id="dyn-from-heat">读取当前炉次</button>
    <button class="btn" id="dyn-writeback">回写实测到炉次</button>
  </div>
  ${renderHeatFlow("dynamic")}

  <div class="dyn-layout">
    <aside class="card dyn-state">
      <div class="card-h"><h3>当前状态</h3><span class="sub">${sm ? "CAS-OB → 脱气 → LF" : "EAF"}</span></div>
      <div class="card-b">
        <div class="dyn-fields">
          ${dynField("质量 t", "dyn-mass", s.mass || "", "number", 1)}
          ${dynField("已用时间 min", "dyn-time", s.time, "number", 1)}
          ${dynField("温度 °C", "dyn-temp", s.temp, "number", 1)}
          <label class="field"><span>阶段</span><select id="dyn-stage">${(sm ? [["casob", "CAS-OB 吹氧"], ["degas", "钢包脱气"], ["lf", "LF 精炼"], ["cast", "连铸"]] : [["melt", "熔化"], ["blow", "吹氧"], ["sample", "取样"], ["alloy", "合金化"], ["tap", "出钢"]]).map(([k, v]) => `<option value="${k}" ${s.stage === k ? "selected" : ""}>${v}</option>`).join("")}</select></label>
        </div>
        <div class="dyn-comp">
          ${DYN_ELEMENTS.map((k) => `<label><span>${k} %</span><input id="dyn-${k.toLowerCase()}" class="mono" type="number" step="0.0001" value="${s.comp[k] ?? ""}" placeholder="实测"></label>`).join("")}
        </div>
        <div class="dyn-params">
          ${!sm ? dynField("氧气 Nm³/min", "dyn-o2", s.o2, "number", 1) : ""}
          ${!sm ? dynField("碳枪 kg/min", "dyn-carbon", s.carbon, "number", 1) : ""}
          ${dynField(sm ? "LF 功率 MW" : "电弧功率 MW", "dyn-power", s.power, "number", 1)}
          ${dynField(sm ? "目标 C（脱气后）%" : "停氧目标 C %", "dyn-target", s.target_c, "number", 0.001)}
        </div>
        ${sm ? `<label class="dyn-check"><input type="checkbox" id="dyn-o2on" ${s.o2_on ? "checked" : ""}> CAS-OB “吹氧”开关已打开</label>` : ""}
        <button class="btn primary mt12" id="dyn-run" style="width:100%">预测并给下一步建议</button>
        <div class="hint mt8">输入的是“此刻实测值”。系统按经验速率外推，不替代模拟器分析。</div>
      </div>
    </aside>

    <section class="dyn-center">
      <div class="card dyn-toolbar">
        <b>流程画布</b><span class="sub">拖动节点 · 空白处拖动平移 · 滚轮缩放</span><div class="spacer"></div>
        <button class="btn sm" id="dyn-zoom-out">−</button><span class="mono small" id="dyn-zoom-label">100%</span><button class="btn sm" id="dyn-zoom-in">+</button>
        <button class="btn sm" id="dyn-plan">初始规划</button>
        <button class="btn sm" id="dyn-auto">智能规划</button>
        <button class="btn sm" id="dyn-clear">清空</button>
      </div>
      <div class="dyn-canvas" id="dyn-canvas">
        <div class="dyn-world" id="dyn-world"></div>
      </div>
      <div class="card dyn-palette" id="dyn-palette">
        ${(sm ? [["sample", "取样"], ["casob", "CAS-OB 吹氧"], ["degas", "钢包脱气"], ["deox", "铝脱氧"], ["alloy", "合金化"], ["heat", "调温"], ["cast", "送连铸"]] : [["sample", "取样"], ["blow", "吹氧"], ["slag", "加渣料/沉淀"], ["alloy", "加合金"], ["heat", "调温"], ["tap", "出钢"]]).map(([k, label]) => `<button data-dyn-action="${k}">${label}</button>`).join("")}
      </div>
    </section>

    <aside class="card dyn-advice" id="dyn-advice">${S.dyn.data ? renderDynAdvice(S.dyn.data) : '<div class="empty">点击「预测并给下一步建议」</div>'}</aside>
  </div>`;
  bindDynamic();
  renderDynCanvas();
  if (!S.dyn.data && s.mass && Object.keys(s.comp || {}).length) setTimeout(runDynAdvice, 80);
}

function dynField(label, id, value, type = "number", step = 1) {
  return `<label class="field"><span>${label}</span><input id="${id}" class="mono" type="${type}" step="${step}" value="${value}"></label>`;
}

function bindDynamic() {
  $$(".dyn-tabs button").forEach((b) => b.onclick = () => { dynResetState(b.dataset.dtrack); viewDynamic(); });
  $("#dyn-from-heat").onclick = () => {
    dynResetState(S.heat?.track === "sm" ? "sm" : "eaf");
    if (S.heat?.mass) S.dyn.state.mass = S.heat.mass;
    if (S.heat?.dynamic) {
      const d = S.heat.dynamic;
      for (const e of DYN_ELEMENTS) if (d.comp?.[e] != null) S.dyn.state.comp[e] = d.comp[e];
      if (d.temp != null) S.dyn.state.temp = d.temp;
      if (d.stage) S.dyn.state.stage = d.stage;
    }
    const srcs = [S.heat?.charge?.composition, S.heat?.initial,
                  S.plan?.data?.summary?.final_eaf, S.plan?.data?.summary?.final_sm].filter(Boolean);
    for (const src of srcs) {
      for (const e of DYN_ELEMENTS) if (src[e] != null) S.dyn.state.comp[e] = src[e];
    }
    if (!S.dyn.state.mass) S.dyn.state.mass = S.plan?.data?.summary?.sm_mass || S.plan?.data?.mass || 0;
    viewDynamic();
  };
  $("#dyn-run").onclick = runDynAdvice;
  $("#dyn-writeback").onclick = () => {
    dynReadState();
    S.heat.dynamic = JSON.parse(JSON.stringify(S.dyn.state));
    S.heat.state = S.heat.dynamic;
    S.dyn.rev = heatRev();
    updateTop();
    refreshHeatFlow("dynamic");
    toast("已把当前实测成分回写到炉次，AI 助手会按它回答");
  };
  $("#dyn-plan").onclick = () => go("plan");
  $("#dyn-zoom-in").onclick = () => { S.dyn.zoom = Math.min(1.8, S.dyn.zoom + 0.1); applyDynTransform(); };
  $("#dyn-zoom-out").onclick = () => { S.dyn.zoom = Math.max(0.5, S.dyn.zoom - 0.1); applyDynTransform(); };
  $("#dyn-auto").onclick = dynAutoPlan;
  $("#dyn-clear").onclick = () => { S.dyn.nodes = []; S.dyn.edges = []; S.dyn.seq = 1; renderDynCanvas(); };
  $$("[data-dyn-action]").forEach((b) => b.onclick = () => dynAddAction(b.dataset.dynAction));
  const canvas = $("#dyn-canvas");
  if (canvas) bindDynCanvas(canvas);
}

function dynReadState() {
  const s = S.dyn.state;
  s.mass = parseFloat($("#dyn-mass")?.value) || s.mass;
  s.time = parseFloat($("#dyn-time")?.value) || 0;
  s.temp = parseFloat($("#dyn-temp")?.value) || s.temp;
  s.stage = $("#dyn-stage")?.value || s.stage;
  s.o2 = parseFloat($("#dyn-o2")?.value) || 0;
  s.carbon = parseFloat($("#dyn-carbon")?.value) || 0;
  s.power = parseFloat($("#dyn-power")?.value) || 0;
  s.target_c = parseFloat($("#dyn-target")?.value) || s.target_c;
  s.o2_on = $("#dyn-o2on") ? $("#dyn-o2on").checked : s.o2_on;
  for (const e of DYN_ELEMENTS) {
    const el = $("#dyn-" + e.toLowerCase());
    if (!el) continue;
    const v = parseFloat(el.value);
    if (isNaN(v)) delete s.comp[e];
    else s.comp[e] = v;
  }
  return s;
}

async function runDynAdvice() {
  const s = dynReadState();
  if (!s.mass) { toast("先填钢水质量（t）", true); return; }
  if (!Object.keys(s.comp || {}).length) { toast("先填至少一个元素实测值", true); return; }
  const btn = $("#dyn-run"); setBusy(btn, true);
  try {
    const r = await api("/api/process/advise", "POST", { track: S.dyn.track, state: s });
    S.dyn.data = r;
    S.dyn.rev = heatRev();
    refreshHeatFlow("dynamic");
    const advBox = $("#dyn-advice");
    if (advBox) {
      advBox.innerHTML = renderDynAdvice(r);
      bindDynActions();
      if (!S.dyn.nodes.length) dynAddInitialNode();
    }
  } catch (e) { toast("预测失败：" + e.message, true); }
  setBusy(btn, false);
}

function renderDynAdvice(r) {
  if (!r || r.status !== "ok") return `<div class="empty">${esc(r?.message || "无法预测")}</div>`;
  const samp = r.sample || {};
  const stop = r.stop || {};
  const pts = (r.prediction && r.prediction.points) || [];
  return `
    <div class="dyn-advice-head"><span class="badge pass">动态建议</span><span class="mono small">${r.track === "sm" ? "二次精炼" : "EAF"}</span>${(() => { const off = (stop.elements || []).filter((e) => e.status === "high" || e.status === "low"); return `<span class="badge ${off.length ? "risk" : "pass"}">${off.length ? off.length + " 项不合格" : "元素全合格"}</span>`; })()}</div>
    <p class="dyn-summary">${esc(r.summary)}</p>
    <div class="dyn-kpis">
      <div><span>下次取样</span><b>${f(samp.in_min, 1)} min</b></div>
      <div><span>预计 C</span><b>${f(samp.expected, 3)}%</b></div>
      <div><span>到目标</span><b>${samp.to_target_min != null ? f(samp.to_target_min, 1) + " min" : "—"}</b></div>
    </div>
    ${dynChart(pts)}
    <div class="dyn-stop">
      <div class="dyn-stop-title">停止/判断阈值</div>
      ${(stop.elements || []).map((e) => {
        const tgt = Array.isArray(e.target) ? `${e.target[0] != null ? f(e.target[0], 3) : "—"}–${e.target[1] != null ? f(e.target[1], 3) : "—"}` : (e.target != null ? f(e.target, 3) : "—");
        return `<div class="dyn-stop-row"><span>${e.element}</span><b>${f(e.value, 4)}%</b><em class="small muted">${tgt}</em><span class="badge ${e.status === "ok" ? "pass" : e.status === "low" ? "adjust" : e.status === "high" ? "fail" : "neutral"}">${e.status === "ok" ? "合格" : e.status === "low" ? "偏低" : e.status === "high" ? "偏高" : "吹到目标"}</span></div>`;
      }).join("")}
    </div>
    <div class="dyn-actions-title">下一步建议</div>
    ${(r.actions || []).map((a) => `<div class="dyn-action-card"><div><b>${esc(a.label)}</b><p>${esc(a.why)}</p></div><button class="btn sm primary" data-dyn-action="${esc(a.key)}">加入画布</button></div>`).join("")}
    ${renderDynPlanRef(r.track)}
  `;
}

function renderDynPlanRef(track) {
  const p = S.plan.data;
  if (!p) {
    return `<div class="dyn-planref"><div class="dyn-planref-head"><b>初始规划</b><span>还没做</span></div><p>先定停氧 / 停真空的 C 锚点，再进动态操作；否则只能凭感觉走。</p><button class="btn sm" onclick="go('plan')">去生成初始规划 →</button></div>`;
  }
  const a = p.summary.c_anchors || {};
  const cur = Number(S.dyn.state?.comp?.C ?? 0);
  const stage = S.dyn.state?.stage || "";
  const stageCn = { melt: "熔化", blow: "吹氧", sample: "取样", alloy: "合金化", tap: "出钢", casob: "CAS-OB", degas: "脱气", lf: "LF", cast: "连铸" }[stage] || stage;
  let rows;
  if (track === "sm") {
    rows = stage === "casob" ? [["CAS-OB 终点", a.casob]]
      : stage === "degas" ? [["脱气终点", a.degas]]
      : [["精炼终点", a.final]];
  } else {
    rows = ["melt", "blow", "sample"].includes(stage) ? [["停氧", a.blow]] : [["EAF 出钢", a.tap]];
  }
  return `<div class="dyn-planref">
    <div class="dyn-planref-head"><b>初始规划对照</b><span>${esc(p.grade_name || "")}</span></div>
    <div class="dyn-planref-cur">当前实测 C <b>${f(cur, 3)}%</b> · ${esc(stageCn)}</div>
    ${rows.filter(([, v]) => v != null).map(([label, v]) => {
      const d = cur - Number(v);
      const st = Math.abs(d) <= 0.01 ? ["pass", "到位"] : d > 0 ? ["neutral", "待降 " + f(d, 3)] : ["risk", "低于 " + f(Math.abs(d), 3)];
      return `<div class="dyn-plan-row"><span>${label}</span><b>${f(v, 3)}%</b><em class="badge ${st[0]}">${st[1]}</em></div>`;
    }).join("")}
    <button class="btn sm ghost" onclick="go('plan')">查看完整初始规划 →</button>
  </div>`;
}

function dynChart(points) {
  if (!points || points.length < 2) return "";
  const w = 320, h = 130, pad = 24;
  const cs = points.map((p) => p.C);
  const lo = Math.min(...cs) * 0.96, hi = Math.max(...cs) * 1.04;
  const tMax = points[points.length - 1].t || 1;
  const xy = points.map((p) => {
    const x = pad + (p.t / tMax) * (w - pad - 8);
    const y = h - pad - ((p.C - lo) / Math.max(1e-6, hi - lo)) * (h - pad - 12);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<div class="dyn-chart"><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <line x1="${pad}" y1="${h-pad}" x2="${w-8}" y2="${h-pad}" class="axis"/>
    <line x1="${pad}" y1="8" x2="${pad}" y2="${h-pad}" class="axis"/>
    <polyline points="${xy}" class="curve"/>
    <text x="${pad}" y="${h-6}" class="lbl">0</text><text x="${w-28}" y="${h-6}" class="lbl">${f(tMax,0)} min</text>
    <text x="2" y="14" class="lbl">${f(hi,2)}</text><text x="2" y="${h-pad}" class="lbl">${f(lo,2)}</text>
  </svg><div class="sub">C 预测曲线（%/min）</div></div>`;
}

function bindDynActions() {
  $$("#dyn-advice [data-dyn-action], #dyn-palette [data-dyn-action]").forEach((b) => {
    if (b.dataset.bound) return;
    b.dataset.bound = "1";
    b.onclick = () => dynAddAction(b.dataset.dynAction);
  });
}

function dynNodePosition() {
  const n = S.dyn.nodes[S.dyn.nodes.length - 1];
  if (!n) return { x: 80, y: 80 };
  let x = n.x + 280, y = n.y + (S.dyn.seq % 2 ? 10 : -10);
  if (x > 1500) { x = 80; y = n.y + 180; }
  return { x, y };
}

function dynAddNode(type, title, body, meta) {
  const pos = dynNodePosition();
  const id = "n" + S.dyn.seq++;
  const n = { id, type, title, body, meta: meta || "", x: pos.x, y: pos.y };
  S.dyn.nodes.push(n);
  const prev = S.dyn.nodes[S.dyn.nodes.length - 2];
  if (prev) S.dyn.edges.push({ from: prev.id, to: id });
  renderDynCanvas();
  return n;
}

function dynAddInitialNode() {
  if (S.dyn.nodes.length) return;
  const s = S.dyn.state;
  dynAddNode("state", "当前状态", `C ${f(s.comp.C,3)}% · ${f(s.temp,0)}°C`, `${f(s.mass,0)} t · ${s.stage}`);
}

function dynAddAction(key) {
  const r = S.dyn.data;
  const a = (r && r.actions || []).find((x) => x.key === key) || { label: key, why: "", params: {} };
  const s = S.dyn.state;
  const ap = r?.alloy_plan;
  const alloyStr = ap && (ap.additions || []).length
    ? ap.additions.map((x) => `${x.name} ${Math.round(x.mass)}kg`).join(" + ")
    : "按 10 kg 档全局优化方案加入";
  const map = {
    sample: ["取样", `建议 ${f(r?.sample?.in_min,1)} min 后取样，预计 C ${f(r?.sample?.expected,3)}%`],
    blow: ["吹氧", `O₂ ${f(s.o2,0)} Nm³/min · 碳枪 ${f(s.carbon,0)} kg/min · 停氧 C ${f(s.target_c,3)}%`],
    slag: ["造渣/脱氧", a.why || "按 10 kg 档加入造渣/脱氧剂"],
    alloy: ["加合金", alloyStr],
    heat: ["调温", `目标 ${s.track === "sm" ? "1573–1576" : "1630–1660"}°C · 功率 ${f(s.power,0)} MW`],
    tap: ["出钢", "出钢送二次精炼；先停氧 1–2 min"],
    casob: ["CAS-OB 吹氧", `打开“吹氧”开关 · 氩气 1.0 Nm³/min · 目标 C ${f(s.target_c,3)}%`],
    degas: ["钢包脱气", `最大真空 + 氩气 1.5–2.0 Nm³/min · 脱 H/N（C≈${f(s.target_c,3)}%）`],
    deox: ["铝脱氧", a.why || "先看 O；O≤20 ppm 不加铝，否则按 10 kg 档补铝"],
    cast: ["送连铸", "确认 17 元素与温度后送小方坯铸机"],
  };
  const [title, body] = map[key] || [a.label, a.why];
  dynAddNode(key, title, body, a.why);
}

function dynAutoPlan() {
  const r = S.dyn.data;
  if (!r) { toast("先预测并获取建议", true); return; }
  S.dyn.nodes = []; S.dyn.edges = []; S.dyn.seq = 1;
  dynAddInitialNode();
  if (r.sample) dynAddNode("sample", "取样确认", `建议 ${f(r.sample.in_min,1)} min 后，预计 C ${f(r.sample.expected,3)}%`, "按元素含量");
  (r.actions || []).slice(0, 4).forEach((a) => {
    const map = { blow: "吹氧", alloy: "加合金", heat: "调温", tap: "出钢", casob: "CAS-OB 吹氧", degas: "钢包脱气", deox: "铝脱氧", cast: "送连铸", sample: "取样" };
    dynAddNode(a.key, map[a.key] || a.label, a.why, "智能规划");
  });
}

function dynLoadPlanNodes(track) {
  const p = S.plan.data;
  if (!p) return;
  const cps = (p.checkpoints || []).filter((c) => c.track === track);
  if (!cps.length) return;
  S.dyn.nodes = []; S.dyn.edges = []; S.dyn.seq = 1;
  cps.forEach((cp, i) => {
    const id = "n" + S.dyn.seq++;
    const node = {
      id,
      type: cp.kind || "state",
      title: `${cp.stage} · ${cp.title}`,
      body: cp.c != null ? `${cp.trigger}｜计划 C ${f(cp.c, 3)}%` : cp.trigger,
      meta: `初始规划 · ${cp.ref_min != null ? "参考 " + f(cp.ref_min, 0) + " min" : "按元素判断"}`,
      x: 80 + (i % 4) * 270,
      y: 70 + Math.floor(i / 4) * 150,
    };
    S.dyn.nodes.push(node);
    if (i) S.dyn.edges.push({ from: S.dyn.nodes[i - 1].id, to: id });
  });
  S.dyn.pan = { x: 16, y: 16 };
  S.dyn.zoom = 0.82;
  renderDynCanvas();
}

function renderDynCanvas() {
  const world = $("#dyn-world");
  if (!world) return;
  const w = 2200, h = 1400;
  const edges = S.dyn.edges.map((e) => {
    const a = S.dyn.nodes.find((n) => n.id === e.from), b = S.dyn.nodes.find((n) => n.id === e.to);
    if (!a || !b) return "";
    const x1 = a.x + 220, y1 = a.y + 45, x2 = b.x, y2 = b.y + 45;
    const mx = (x1 + x2) / 2;
    return `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" class="dyn-edge"/>`;
  }).join("");
  world.innerHTML = `<svg class="dyn-edges" width="${w}" height="${h}">${edges}</svg>` +
    S.dyn.nodes.map((n) => `<div class="dyn-node dyn-${n.type}" data-node="${n.id}" style="left:${n.x}px;top:${n.y}px">
      <div class="dyn-node-head"><span class="dyn-node-dot"></span><b>${esc(n.title)}</b><span class="dyn-node-tag">${esc(n.type)}</span></div>
      <div class="dyn-node-body">${esc(n.body)}</div>
      <div class="dyn-node-foot">${esc(n.meta || "")}</div>
    </div>`).join("");
  applyDynTransform();
  bindDynCanvas($("#dyn-canvas"));
}

function applyDynTransform() {
  const world = $("#dyn-world");
  if (world) world.style.transform = `translate(${S.dyn.pan.x}px, ${S.dyn.pan.y}px) scale(${S.dyn.zoom})`;
  const z = $("#dyn-zoom-label"); if (z) z.textContent = Math.round(S.dyn.zoom * 100) + "%";
}

function bindDynCanvas(canvas) {
  if (!canvas || canvas.dataset.bound) return;
  canvas.dataset.bound = "1";
  canvas.addEventListener("pointerdown", (ev) => {
    const nodeEl = ev.target.closest(".dyn-node");
    if (nodeEl) {
      const n = S.dyn.nodes.find((x) => x.id === nodeEl.dataset.node);
      if (!n) return;
      ev.preventDefault(); ev.stopPropagation();
      S.dyn.drag = { id: n.id, sx: ev.clientX, sy: ev.clientY, nx: n.x, ny: n.y };
      nodeEl.setPointerCapture?.(ev.pointerId);
      return;
    }
    S.dyn.panning = { sx: ev.clientX, sy: ev.clientY, px: S.dyn.pan.x, py: S.dyn.pan.y };
  });
  canvas.addEventListener("pointermove", (ev) => {
    if (S.dyn.drag) {
      const d = S.dyn.drag;
      const n = S.dyn.nodes.find((x) => x.id === d.id);
      if (!n) return;
      n.x = d.nx + (ev.clientX - d.sx) / S.dyn.zoom;
      n.y = d.ny + (ev.clientY - d.sy) / S.dyn.zoom;
      const el = canvas.querySelector(`[data-node="${n.id}"]`);
      if (el) { el.style.left = n.x + "px"; el.style.top = n.y + "px"; }
      renderDynCanvasEdgesOnly();
    } else if (S.dyn.panning) {
      const p = S.dyn.panning;
      S.dyn.pan.x = p.px + (ev.clientX - p.sx);
      S.dyn.pan.y = p.py + (ev.clientY - p.sy);
      applyDynTransform();
    }
  });
  const end = () => { S.dyn.drag = null; S.dyn.panning = null; };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const cx = ev.clientX - rect.left, cy = ev.clientY - rect.top;
    const old = S.dyn.zoom;
    const next = Math.max(0.5, Math.min(1.8, old * (ev.deltaY > 0 ? 0.92 : 1.08)));
    S.dyn.pan.x = cx - (cx - S.dyn.pan.x) * (next / old);
    S.dyn.pan.y = cy - (cy - S.dyn.pan.y) * (next / old);
    S.dyn.zoom = next;
    applyDynTransform();
  }, { passive: false });
}

function renderDynCanvasEdgesOnly() {
  const svg = $("#dyn-world .dyn-edges");
  if (!svg) return;
  const edges = S.dyn.edges.map((e) => {
    const a = S.dyn.nodes.find((n) => n.id === e.from), b = S.dyn.nodes.find((n) => n.id === e.to);
    if (!a || !b) return "";
    const x1 = a.x + 220, y1 = a.y + 45, x2 = b.x, y2 = b.y + 45;
    const mx = (x1 + x2) / 2;
    return `<path d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}" class="dyn-edge"/>`;
  }).join("");
  svg.innerHTML = edges;
}

/* ---------------- heat -> wizard ---------------- */
function applyHeatToWizard(track) {
  const h = S.heat || {};
  S.wizard.track = track;
  S.wizard.eaf = null;
  S.wizard.sm = null;
  S.wizard.step = 0;
  if (track === "eaf") {
    S.wizard.eafMass = h.mass || null;
    S.wizard.forced = {
      mix: h.mix || null,
      retention: h.charge?.retention || null,
      alloy_plan: h.alloy ? Object.fromEntries((h.alloy.additions || []).map((a) => [a.key, a.mass])) : null,
      pre_c: h.pre_c != null ? h.pre_c : 0.37,
      pre_si: h.pre_si != null ? h.pre_si : 0.05,
    };
    S.wizard.forcedAlloy = null;
  } else {
    S.wizard.smMass = h.mass || null;
    S.wizard.smInitial = h.initial || (h.charge?.composition ? { ...WIZ_DEFAULT_SM, ...h.charge.composition } : WIZ_DEFAULT_SM);
    S.wizard.forcedAlloy = h.alloy ? Object.fromEntries((h.alloy.additions || []).map((a) => [a.key, a.mass])) : null;
    S.wizard.skipDecarb = !!h.skip_decarb;
    S.wizard.forced = null;
  }
  h.dirty = false;
}

function goWizardFromHeat(track = "eaf") {
  applyHeatToWizard(track);
  go("wizard");
}

function goWizardFromAlloy() {
  const tr = S.heat?.track || (S.alloy?.catalog === "eaf" ? "eaf" : "sm");
  goWizardFromHeat(tr);
}

/* ---------------- wizard ---------------- */
const WIZ_DEFAULT_SM = {
  C: 0.52, Si: 0.28, Mn: 1.00, P: 0.010, S: 0.010,
  Cr: 1.55, Mo: 0.02, Ni: 0.04, Al: 0.005,
  O: 0.0500, N: 0.0080, H: 0.0002,
  Cu: 0.06, Nb: 0.0, Ti: 0.0, V: 0.0, B: 0.0,
};

function wizData() { return S.wizard[S.wizard.track]; }

async function viewWizard() {
  await ensureRuns();
  const w = S.wizard;
  if (S.heat?.dirty && S.heat.track === w.track) {
    applyHeatToWizard(w.track);
  }
  // 初始规划是最新的时候，向导直接复用同一套方案，不重复算
  if (planFresh() && S.plan.data?.plans) {
    if (!w.eaf && w.track === "eaf" && S.plan.data.plans.eaf) {
      w.eaf = S.plan.data.plans.eaf;
      w.eafMass = S.plan.data.mass;
    }
    if (!w.sm && w.track === "sm" && S.plan.data.plans.sm && !w.smInitial) {
      w.sm = S.plan.data.plans.sm;
      w.smMass = S.plan.data.summary?.sm_mass;
    }
  }
  $("#view").innerHTML = `
  <div class="page-head">
    <div><h1>操作流程</h1><p>按模拟器输入粒度做的分步向导：装料只按整吨，所有添加剂只按 10 kg；EAF 与二次精炼分开，一步接一步，不用自己拼。</p></div>
    <div class="spacer"></div>
    <button class="btn sm ghost" onclick="go('reference')" style="margin-right:8px">2024 参考</button>
    <div class="wiz-tabs">
      <button data-track="eaf" class="${w.track === "eaf" ? "active" : ""}">EAF 电弧炉</button>
      <button data-track="sm" class="${w.track === "sm" ? "active" : ""}">二次精炼</button>
    </div>
  </div>
  ${S.plan?.data?.summary?.time_target_min ? `<div class="hint" style="margin-bottom:10px">按 ${f(S.plan.data.mass, 0)} t 校准：整炉参考节拍约 ${f(S.plan.data.summary.time_target_min, 0)} min（EAF + 二次精炼）。下面每一步的“时间”是工艺参考，不是硬性时钟。</div>` : ""}
  ${renderHeatFlow("wizard")}
  <div id="wiz-setup">${renderWizardSetup()}</div>
  <div id="wiz-result" class="mt16">${w[w.track] ? renderWizardFlow(w[w.track], w.step) : ""}</div>`;
  bindWizardSetup();
  const topGrade = $("#top-grade");
  if (topGrade) topGrade.textContent = w[w.track]?.grade_name || gradeName(S.grade);
  if (w[w.track]) bindWizardFlow(w[w.track]);
  else if (w.track === "eaf") setTimeout(runWizardEaf, 40);
  else setTimeout(runWizardSm, 40);
}

function renderWizardSetup() {
  const w = S.wizard;
  if (w.track === "eaf") {
    const d = w.eaf;
    const defaultGrade = d?.grade || (S.boot.grades_eaf["sc21_engineering"] ? "sc21_engineering" : S.grade);
    return `<div class="card wiz-setup">
      <div class="card-h"><h3>EAF 电弧炉 · 参数</h3><span class="sub">装料整吨 · 合金/渣料 10 kg</span><div class="spacer"></div><span class="badge neutral">8 步</span></div>
      <div class="card-b">
        <div class="form-grid wiz-form">
          <label class="field"><span>目标钢种</span>
            <select id="wz-grade">${Object.entries(S.boot.grades_eaf).filter(([k]) => ["sc21_engineering", "engineering"].includes(k)).map(([k, x]) => `<option value="${k}" ${k === defaultGrade ? "selected" : ""}>${x.name}</option>`).join("")}</select>
          </label>
          <label class="field"><span>废钢装入量 t（整吨）</span><input id="wz-mass" class="mono" type="number" min="10" max="90" step="1" value="${d?.mass || w.eafMass || 90}"></label>
          <label class="field"><span>模式</span><select id="wz-safe"><option value="1" ${!d || d.safe ? "selected" : ""}>稳健（推荐）</option><option value="0" ${d && !d.safe ? "selected" : ""}>成本优先</option></select></label>
          <label class="field"><span>&nbsp;</span><button class="btn primary" id="wz-eaf-run">生成 EAF 操作流程</button></label>
        </div>
        <div class="hint">流程：装料 → 熔化 → 造渣 → 吹氧 → 停氧取样 → 合金化 → 调温 → 出钢。开炉前先用「初始规划」定整炉停点；时间是建议节拍，执行时以元素含量和「动态操作」的取样建议为准。向导当前覆盖工程钢；其他钢种请用「炉料配比 / 合金补加」页。</div>
      </div>
    </div>`;
  }
  const eaf = w.eaf;
  const eafRuns = (S.runs || []).filter((r) => runEafRef(r));
  const picked = w.eafRunId ? eafRuns.find((r) => r.id === w.eafRunId) : null;
  const pickedRef = picked ? runEafRef(picked) : null;
  const init = w.smInitial || (eaf ? { ...WIZ_DEFAULT_SM, ...(eaf.summary.final || {}) } : WIZ_DEFAULT_SM);
  const fields = [
    ["C", "C %"], ["Si", "Si %"], ["Mn", "Mn %"], ["Cr", "Cr %"],
    ["P", "P %"], ["S", "S %"], ["Mo", "Mo %"], ["Ni", "Ni %"],
    ["Al", "Al %"], ["O", "O %（0.05=500ppm）"], ["N", "N %"], ["H", "H %"],
  ];
  return `<div class="card wiz-setup">
    <div class="card-h"><h3>二次精炼 · 参数</h3><span class="sub">CAS-OB → 钢包脱气 → 钢包炉</span><div class="spacer"></div><span class="badge neutral">7 步</span></div>
    <div class="card-b">
      <div class="form-grid wiz-form">
        <label class="field"><span>选择 EAF 炉次</span>
          <select id="wz-eaf-pick">
            <option value="">— 手动输入成分 —</option>
            ${eafRuns.map((r) => `<option value="${r.id}" ${r.id === w.eafRunId ? "selected" : ""}>${esc(r.name)} · ${gradeShort(r.grade)}</option>`).join("")}
          </select>
        </label>
        <label class="field"><span>钢水质量 t（整吨）</span><input id="wz-sm-mass" class="mono" type="number" min="40" max="120" step="1" value="${w.sm?.mass || w.smMass || (eaf ? Math.round(eaf.summary.tap_mass) : 88)}"></label>
        <label class="field"><span>进站温度 °C</span><input id="wz-sm-temp" class="mono" type="number" min="1500" max="1700" step="1" value="${w.sm ? 1565 : 1565}"></label>
        <label class="field"><span>&nbsp;</span><button class="btn primary" id="wz-sm-run">生成二次精炼流程</button></label>
        <label class="field"><span>&nbsp;</span><button class="btn" id="wz-from-eaf" ${eaf ? "" : "disabled"}>从当前 EAF 结果带入</button></label>
      </div>
      ${pickedRef ? `<div class="hint">已关联 EAF：${esc(picked.name)} · 出钢 ${f(pickedRef.tap_mass, 0)} t · C ${f(pickedRef.final.C, 3)}% · Si ${f(pickedRef.final.Si, 3)}%</div>` : (eafRuns.length ? '<div class="hint">从上面选一个已保存的 EAF 炉次，会自动带入它的出钢成分和钢水量。</div>' : '<div class="hint">还没有保存过 EAF 炉次。先在 EAF 向导里点「保存 EAF 炉次」，这里就能选。</div>')}
      <div class="hr"></div>
      <div class="small muted" style="margin-bottom:6px">装入成分（以 EAF 出钢或上一炉实测为准）</div>
      <div class="wiz-init-grid">
        ${fields.map(([k, label]) => `<label><span>${label}</span><input class="mono wz-init" data-el="${k}" type="number" step="0.0001" value="${init[k] ?? 0}"></label>`).join("")}
      </div>
      <div class="hint">目标成分按所选钢种的窗口执行（C/Si/Mn/Cr/Mo 等见 EAF 出钢钢种对应的 SM 目标）；合金按 10 kg 档。</div>
    </div>
  </div>`;
}

function bindWizardSetup() {
  $$(".wiz-tabs button").forEach((b) => b.onclick = () => {
    S.wizard.track = b.dataset.track;
    S.wizard.step = 0;
    if (b.dataset.track === "sm" && S.wizard.eaf && !S.wizard.smInitial) {
      S.wizard.smInitial = { ...WIZ_DEFAULT_SM, ...(S.wizard.eaf.summary.final || {}) };
    }
    viewWizard();
  });
  const pick = $("#wz-eaf-pick");
  if (pick) pick.onchange = () => {
    const run = (S.runs || []).find((x) => x.id === pick.value);
    S.wizard.eafRunId = run ? run.id : null;
    if (run) {
      const ref = runEafRef(run);
      S.wizard.smInitial = { ...WIZ_DEFAULT_SM, ...(ref.final || {}) };
      if (ref.tap_mass) S.wizard.smMass = Math.round(ref.tap_mass);
      S.wizard.sm = null;
    }
    viewWizard();
  };
  const eafRun = $("#wz-eaf-run");
  if (eafRun) eafRun.onclick = runWizardEaf;
  const smRun = $("#wz-sm-run");
  if (smRun) smRun.onclick = runWizardSm;
  const from = $("#wz-from-eaf");
  if (from) from.onclick = () => {
    const d = S.wizard.eaf;
    if (!d) return;
    const f = d.summary.final || {};
    $$(".wz-init").forEach((i) => {
      const e = i.dataset.el;
      if (f[e] != null) i.value = f[e];
      else if (["B", "Ca", "Nb", "Ti", "V"].includes(e)) i.value = 0;
    });
    const m = $("#wz-sm-mass");
    if (m) m.value = Math.round(d.summary.tap_mass);
    toast("已带入 EAF 最终成分，可直接生成");
  };
}

async function runWizardEaf() {
  const btn = $("#wz-eaf-run");
  setBusy(btn, true);
  try {
    const grade = $("#wz-grade")?.value || (S.boot.grades_eaf["sc21_engineering"] ? "sc21_engineering" : S.grade);
    const mass = Math.max(10, Math.min(90, parseInt($("#wz-mass")?.value || "90", 10)));
    const safe = $("#wz-safe")?.value !== "0";
    const forced = S.wizard.forced && (S.heat.mass == null || S.heat.mass === mass) ? S.wizard.forced : null;
    const body = { grade, mass, safe };
    if (S.alloyPos != null) body.alloy_pos = S.alloyPos;
    if (S.plan?.other_per_t != null) body.other_per_t = S.plan.other_per_t;
    if (S.plan?.power_kwh != null) body.power_kwh = Math.round(S.plan.power_kwh * mass / 90);
    if (forced) {
      body.mix = forced.mix;
      body.retention = forced.retention;
      body.alloy_plan = forced.alloy_plan;
      body.pre_c = forced.pre_c;
      body.pre_si = forced.pre_si;
    }
    const r = await api("/api/wizard/eaf", "POST", body);
    if (r.status !== "ok") throw new Error(r.message || "无可行方案");
    S.grade = grade;
    localStorage.setItem("steel-lab-grade", S.grade);
    updateTop();
    S.wizard.eaf = r;
    S.wizard.sm = null;
    S.wizard.eafMass = mass;
    S.wizard.forced = null;
    S.wizard.track = "eaf";
    const topE = $("#top-grade"); if (topE) topE.textContent = r.grade_name;
    S.wizard.step = Math.max(0, Math.min(r.steps.length - 1, S.wizard.pendingStep ?? 0));
    S.wizard.pendingStep = null;
    S.wizard.smInitial = null;
    syncHeatFromEaf(r);
    $("#wiz-result").innerHTML = renderWizardFlow(r, S.wizard.step);
    bindWizardFlow(r);
  } catch (e) { toast("生成失败：" + e.message, true); }
  setBusy(btn, false);
}

async function runWizardSm() {
  const btn = $("#wz-sm-run");
  setBusy(btn, true);
  try {
    const mass = Math.max(40, Math.min(120, parseInt($("#wz-sm-mass")?.value || "88", 10)));
    const temp_start = parseFloat($("#wz-sm-temp")?.value || "1565");
    const initial = {};
    $$(".wz-init").forEach((i) => { initial[i.dataset.el] = parseFloat(i.value) || 0; });
    const body = { mass, temp_start, initial, safe: true };
    const eafGrade = S.wizard.eaf?.grade || S.plan?.grade || S.heat?.grade;
    if (eafGrade) body.eaf_grade = eafGrade;
    if (S.alloyPos != null) body.alloy_pos = S.alloyPos;
    const forcedAlloy = S.wizard.forcedAlloy && (S.heat.mass == null || S.heat.mass === mass)
      ? S.wizard.forcedAlloy : null;
    if (forcedAlloy) body.alloy_plan = forcedAlloy;
    if (S.wizard.skipDecarb) body.skip_decarb = true;
    const r = await api("/api/wizard/sm", "POST", body);
    if (r.status !== "ok") throw new Error(r.message || "无可行方案");
    syncHeatFromSm(r);
    S.wizard.sm = r;
    S.wizard.smMass = mass;
    S.wizard.forcedAlloy = null;
    S.wizard.skipDecarb = false;
    S.wizard.track = "sm";
    const topS = $("#top-grade"); if (topS) topS.textContent = r.grade_name;
    S.wizard.step = Math.max(0, Math.min(r.steps.length - 1, S.wizard.pendingStep ?? 0));
    S.wizard.pendingStep = null;
    $("#wiz-result").innerHTML = renderWizardFlow(r, S.wizard.step);
    bindWizardFlow(r);
  } catch (e) { toast("生成失败：" + e.message, true); }
  setBusy(btn, false);
}

function renderWizardFlow(data, step) {
  const total = data.steps.length;
  const idx = Math.max(0, Math.min(total - 1, step || 0));
  const s = data.summary;
  const kpis = data.track === "eaf" ? [
    ["钢种", data.grade_name], ["装入量", f(data.mass, 0) + " t"],
    ["废钢", money(s.scrap_cost)], ["合金", money(s.alloy_cost)],
    ["合计", money(s.total_cost)], ["吨钢", "$" + f(s.total_per_t, 1) + "/t"],
  ] : [
    ["钢种", data.grade_name], ["钢水量", f(data.mass, 0) + " t"],
    ["合金", money(s.alloy_cost)], ["合计", money(s.total_cost)],
    ["吨钢", "$" + f(s.total_per_t, 1) + "/t"], ["脱碳目标", f(s.c_pre, 3) + "%"],
  ];
  const finalKeys = data.track === "eaf" ? ["C", "Si", "Mn", "Cr", "P", "S"]
    : ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "Al", "Nb", "Ti", "V", "B", "N", "H", "O"];
  const rail = data.steps.map((x, i) => `<button class="wiz-rail-item ${i === idx ? "active" : ""} ${i < idx ? "done" : ""}" data-wstep="${i}">
      <span class="wz-i">${String(i + 1).padStart(2, "0")}</span>
      <span class="wz-t"><b>${esc(x.title)}</b><i>${esc(x.time)}</i></span>
    </button>`).join("");
  return `
  <div class="card wiz-summary">
    <div class="card-h"><h3>${data.track === "eaf" ? "EAF 电弧炉" : "二次精炼"} · ${esc(data.grade_name)}</h3><span class="sub">${data.track === "eaf" ? "整吨装料 · 10 kg 合金" : "CAS-OB → 钢包脱气 → LF"}</span>${data.source === "manual" ? '<span class="badge neutral">按当前炉次</span>' : ""}<div class="spacer"></div>
      <span class="badge ${s.out_of_spec.length ? "risk" : "pass"}">${s.out_of_spec.length ? s.out_of_spec.length + " 项需注意" : "全部达标"}</span>
      <button class="btn sm" id="wiz-to-plan">初始规划</button>
      <button class="btn sm" id="wiz-to-dyn">动态调整</button>
      ${data.track === "eaf" ? `<button class="btn sm primary" id="wiz-to-sm">去二次精炼 →</button>` : ""}
      <button class="btn sm primary" id="wiz-save-record">${data.track === "eaf" ? "保存 EAF 炉次" : "保存二次精炼"}</button>
      <button class="btn sm" id="wiz-print">打印清单</button>
    </div>
    <div class="card-b">
      <div class="wiz-kpis">${kpis.map(([k, v]) => `<div class="wiz-kpi"><span>${k}</span><b>${v}</b></div>`).join("")}</div>
      <div class="wiz-final-chips">${finalKeys.map((e) => {
        const c = (s.checks || []).find((x) => x.element === e);
        const st = c ? c.status : "ok";
        return `<span class="wiz-chip ${st}">${e} <b>${f(s.final[e], 4)}</b></span>`;
      }).join("")}</div>
    </div>
  </div>

  <div class="wiz-progress card mt12">
    <div class="wiz-progress-inner">
      <div class="wiz-progress-text">步骤 <b>${idx + 1}</b> / ${total}</div>
      <div class="wiz-bar"><i style="width:${(idx + 1) / total * 100}%"></i></div>
      <div class="wiz-progress-text">${esc(data.steps[idx].time)}</div>
    </div>
  </div>

  <div class="wiz-layout mt12">
    <aside class="card wiz-rail">${rail}</aside>
    <div class="wiz-main">
      ${renderWizardStep(data.steps[idx], idx, total)}
      <div class="wiz-nav">
        <button class="btn" id="wiz-prev" ${idx === 0 ? "disabled" : ""}>← 上一步</button>
        <button class="btn" id="wiz-save">${data.track === "eaf" ? "保存 EAF 炉次" : "保存二次精炼"}</button>
        <div class="spacer"></div>
        <button class="btn primary" id="wiz-next">${idx === total - 1 ? "完成" : "下一步 →"}</button>
      </div>
    </div>
  </div>
  ${renderWizardPrint(data)}`;
}

function renderWizardStep(st, idx, total) {
  const adds = st.adds || [];
  return `<div class="card wiz-step">
    <div class="wiz-step-head">
      <div class="wiz-step-no">${String(idx + 1).padStart(2, "0")}</div>
      <div class="wiz-step-title"><div class="wiz-time">${esc(st.time)}</div><h2>${esc(st.title)}</h2><p>${esc(st.lead)}</p></div>
      <div class="wiz-step-frac">${idx + 1}/${total}</div>
    </div>
    <div class="card-b">
      <div class="wiz-metrics">${(st.metrics || []).map((m) => `<div class="wiz-metric"><span>${esc(m.k)}</span><b>${esc(m.v)}</b></div>`).join("")}</div>
      ${adds.length ? `<div class="table-wrap mt14 wiz-adds"><table class="tbl">
        <thead><tr><th>加入物</th><th>用量</th><th>备注</th></tr></thead>
        <tbody>${adds.map((a) => `<tr><td class="strong">${esc(a.name)}</td><td class="mono">${esc(a.qty)}</td><td class="muted">${esc(a.note || "")}</td></tr>`).join("")}</tbody>
      </table></div>` : ""}
      <div class="wiz-two mt14">
        <div class="wiz-block"><h4><span class="wiz-dot"></span>现在做什么</h4><ol>${(st.actions || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ol></div>
        <div class="wiz-block wiz-check-block"><h4><span class="wiz-dot ok"></span>看什么 / 什么时候停</h4><ul>${(st.checks || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>
      </div>
      ${st.warn ? `<div class="wiz-warn"><b>红线</b><span>${esc(st.warn)}</span></div>` : ""}
      ${st.tip ? `<div class="wiz-tip"><b>提示</b><span>${esc(st.tip)}</span></div>` : ""}
    </div>
  </div>`;
}

function renderWizardPrint(data) {
  const s = data.summary;
  return `<div class="print-only">
    <h1>${esc(data.grade_name)} · ${data.track === "eaf" ? "EAF 操作流程" : "二次精炼操作流程"}</h1>
    <p>钢水/装入量 ${f(data.mass, 0)} t · 废钢 ${money(s.scrap_cost || 0)} · 合金 ${money(s.alloy_cost)} · 合计 ${money(s.total_cost)} · ${f(s.total_per_t, 1)} $/t</p>
    ${data.steps.map((st, i) => `<div class="print-step">
      <h3>${i + 1}. ${esc(st.time)} · ${esc(st.title)}</h3>
      <p>${esc(st.lead)}</p>
      ${(st.metrics || []).length ? `<p><b>参数：</b>${st.metrics.map((m) => esc(m.k) + " " + esc(m.v)).join("；")}</p>` : ""}
      ${(st.adds || []).length ? `<table border="1" cellpadding="3" style="border-collapse:collapse;width:100%"><tr><th>加入物</th><th>用量</th><th>备注</th></tr>${st.adds.map((a) => `<tr><td>${esc(a.name)}</td><td>${esc(a.qty)}</td><td>${esc(a.note || "")}</td></tr>`).join("")}</table>` : ""}
      <p><b>操作：</b>${(st.actions || []).map((x) => esc(x)).join("；")}</p>
      <p><b>检查：</b>${(st.checks || []).map((x) => esc(x)).join("；")}</p>
      ${st.warn ? `<p><b>红线：</b>${esc(st.warn)}</p>` : ""}
    </div>`).join("")}
    <div class="print-final"><b>最终成分：</b>${Object.entries(s.final).filter(([e]) => ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Al", "O", "N", "H"].includes(e)).map(([e, v]) => e + " " + f(v, 4)).join(" · ")}</div>
  </div>`;
}

function bindWizardFlow(data) {
  $$("[data-wstep]").forEach((b) => b.onclick = () => {
    S.wizard.step = parseInt(b.dataset.wstep, 10) || 0;
    $("#wiz-result").innerHTML = renderWizardFlow(data, S.wizard.step);
    bindWizardFlow(data);
  });
  const prev = $("#wiz-prev");
  if (prev) prev.onclick = () => { S.wizard.step = Math.max(0, S.wizard.step - 1); $("#wiz-result").innerHTML = renderWizardFlow(data, S.wizard.step); bindWizardFlow(data); };
  const next = $("#wiz-next");
  if (next) next.onclick = () => {
    if (S.wizard.step >= data.steps.length - 1) { toast("流程已完成，可保存或打印"); return; }
    S.wizard.step += 1;
    $("#wiz-result").innerHTML = renderWizardFlow(data, S.wizard.step);
    bindWizardFlow(data);
  };
  const pr = $("#wiz-print");
  if (pr) pr.onclick = () => window.print();
  const toPlan = $("#wiz-to-plan");
  if (toPlan) toPlan.onclick = () => go("plan");
  const toDyn = $("#wiz-to-dyn");
  if (toDyn) toDyn.onclick = () => {
    S.dyn.track = data.track;
    dynResetState(data.track);
    if (data.summary.final) {
      for (const e of ["C", "Si", "Mn", "Cr", "P", "S", "O"]) {
        if (data.summary.final[e] != null) S.dyn.state.comp[e] = data.summary.final[e];
      }
    }
    go("dynamic");
  };
  const toSm = $("#wiz-to-sm");
  if (toSm) toSm.onclick = () => {
    S.smcalc.initial = smPreFromEaf({ final: data.summary.final || {} });
    S.smcalc.mass = Math.round(data.summary.tap_mass || S.heat?.sm_mass || 90);
    S.smcalc.eafRunId = S.lastEafRunId || null;
    S.smcalc.result = null;
    S.smcalc.route = [];
    S.smcalc.additions = {};
    toast("已把 EAF 出钢成分带入二次精炼");
    go("refine");
  };
  const saveRecord = () => data.track === "eaf" ? saveEafRun(data) : saveSmRun(data);
  const sv = $("#wiz-save");
  if (sv) sv.onclick = saveRecord;
  const svRec = $("#wiz-save-record");
  if (svRec) svRec.onclick = saveRecord;
}

/* ---------------- charge ---------------- */
function viewCharge() {
  const g = S.boot.grades_eaf[S.grade];
  $("#view").innerHTML = `
  <div class="page-head">
    <div><h1>炉料配比</h1><p>以熔炼后成分为约束，最小化废钢成本。C / Si / Mn 可在熔化与精炼阶段调整，P / S / Cr / Mo / Ni / Cu 等残余元素主要靠选料控制。</p></div>
    <div class="spacer"></div>
    <span class="badge neutral">约束：${g.standard}</span>
  </div>
  ${renderHeatFlow("charge")}
  <div class="workbench">
    <div class="panel card">
      <div class="card-h"><h3>配料参数</h3><span class="sub">${g.short}</span></div>
      <div class="card-b">
        <div class="form-grid">
          <label class="field full"><span>目标钢种</span>
            <select id="c-grade">${Object.entries(S.boot.grades_eaf).map(([k, x]) => `<option value="${k}" ${k === S.grade ? "selected" : ""}>${x.name}</option>`).join("")}</select>
          </label>
          <label class="field"><span>废钢装入量 t</span><input id="c-mass" class="mono" type="number" value="${S.chargeMass || 90}" step="1" min="10" max="90"></label>
          <label class="field"><span>体积上限 m³</span><input id="c-vol" class="mono" type="number" value="100" step="1" min="20"></label>
          <label class="field full"><span>熔炼后碳上限 %（可选）</span><input id="c-carbon" class="mono" type="number" placeholder="留空 = 不限制" step="0.01"></label>
          <label class="field full" style="flex-direction:row;align-items:center;gap:8px;font-size:11.5px;color:var(--ink-2)">
            <input type="checkbox" id="c-margin" checked style="width:14px;height:14px;accent-color:var(--accent)">
            稳健模式：配料留 6%、合金留 40% 窗口余量（推荐）
          </label>
          <label class="field full" style="flex-direction:row;align-items:center;gap:8px;font-size:11.5px;color:var(--ink-2)">
            <input type="checkbox" id="c-round" checked style="width:14px;height:14px;accent-color:var(--accent)">
            装料按整吨取整（模拟器只接受整吨）
          </label>
        </div>
        <div class="hr"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span class="small muted">可用废钢（勾选 / 限量）</span>
          <span class="small mono muted">$/t</span>
        </div>
        <div class="material-list">
          ${S.boot.scraps.map((s) => `<div class="material-row" data-key="${s.key}">
            <input type="checkbox" class="m-en" checked>
            <span class="nm" title="${s.name}">${s.name} <span class="badge form">${s.form}</span></span>
            <span class="pr">$${s.price}</span>
            <input type="number" class="m-max mono" value="90" min="0" max="90" step="1" title="最大用量 t">
          </div>`).join("")}
        </div>
        <details class="adv">
          <summary>熔炼收得率（高级，默认按强精炼）</summary>
          <div class="ret-grid">
            ${["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "Nb"].map((e) => `<label>${e}<input type="number" data-el="${e}" class="mono" value="${Math.round((S.boot.retention[e] || 0) * 100)}" min="0" max="100" step="1">%</label>`).join("")}
          </div>
          <div class="hint" style="margin-top:9px">收得率 = 元素从废钢进入钢液的比例。实际模拟会随渣碱度、吹氧、温度变化；建议用 2–3 炉实测结果校准。</div>
        </details>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:14px">
          <button class="btn primary" id="c-run">优化配料</button>
          <button class="btn" id="c-total">总成本优化</button>
          <button class="btn" id="c-manual">手工配料</button>
          <button class="btn" id="c-reset">重置</button>
        </div>
      </div>
    </div>
    <div id="c-result">${S.lastCharge ? renderChargeResult(S.lastCharge) : '<div class="card"><div class="empty">点击「优化配料」开始计算。</div></div>'}</div>
  </div>`;

  $("#c-grade").onchange = (e) => {
    S.grade = e.target.value;
    S.plan.grade = S.grade;
    S.plan.pre_c = S.boot.default_pre_c?.[S.grade] ?? 0.37;
    S.plan.pre_cGrade = S.grade;
    S.plan.data = null;
    localStorage.setItem("steel-lab-grade", S.grade);
    S.lastCharge = null;
    persistPlanSettings();
    updateTop();
    viewCharge();
  };
  $("#c-run").onclick = runCharge;
  $("#c-total").onclick = runTotal;
  $("#c-manual").onclick = openManualMix;
  $("#c-reset").onclick = () => { S.lastCharge = null; resetSlagForNewHeat(); viewCharge(); };
  // 任何配料参数改动都让旧结果失效，避免页面还显示上一炉的配比/成本
  const invalidateCharge = () => {
    if (!S.lastCharge) return;
    S.lastCharge = null;
    const box = $("#c-result");
    if (box) box.innerHTML = '<div class="card"><div class="empty">配料参数已修改，点击「优化配料」重新计算。</div></div>';
  };
  ["c-mass", "c-vol", "c-carbon"].forEach((id) => { const el = $("#" + id); if (el) el.onchange = invalidateCharge; });
  $$(".material-row .m-en, .material-row .m-max, .ret-grid input").forEach((el) => el.onchange = invalidateCharge);
  if (new URLSearchParams(location.search).get("total") === "1") setTimeout(runTotal, 50);
  else if (!S.lastCharge) runCharge();
}


function openManualMix() {
  const cur = S.lastCharge?.mix || {};
  $("#modal-root").innerHTML = `<div class="modal-mask" id="mm"><div class="modal" style="max-width:560px">
    <div class="card-h"><h3>手工配料</h3><span class="sub">输入各料质量（t），系统按当前收得率核算</span><div class="spacer"></div><button class="icon-btn" id="mm-close">×</button></div>
    <div class="card-b" style="max-height:60vh;overflow:auto">
      <div class="table-wrap"><table class="tbl"><thead><tr><th>炉料</th><th class="num">质量 t</th><th class="num">单价</th></tr></thead><tbody>
      ${S.boot.scraps.map((x) => `<tr><td>${x.name} <span class="badge form">${x.form}</span></td>
        <td class="num"><input class="mono mm-mass" data-key="${x.key}" type="number" min="0" step="1" value="${Math.round(cur[x.key] || 0)}" style="width:90px;height:26px;text-align:right;padding:0 6px"></td>
        <td class="num">$${x.price}</td></tr>`).join("")}
      </tbody></table></div>
      <div class="hint mt12">提示：EAF 废钢装入量上限 90 t，总体积 ≤100 m³；可先生成推荐方案，再在这里微调。</div>
    </div>
    <div class="foot"><button class="btn" id="mm-cancel">取消</button><button class="btn primary" id="mm-run">核算这个配比</button></div>
  </div></div>`;
  const close = () => $("#modal-root").innerHTML = "";
  $("#mm-close").onclick = close; $("#mm-cancel").onclick = close;
  $("#mm").onclick = (e) => { if (e.target.id === "mm") close(); };
  $("#mm-run").onclick = async () => {
    const mix = {};
    $$(".mm-mass").forEach((i) => { const v = parseFloat(i.value) || 0; if (v > 0) mix[i.dataset.key] = v; });
    if (!Object.keys(mix).length) { toast("至少输入一种炉料", true); return; }
    const retention = {};
    $$(".ret-grid input").forEach((i) => retention[i.dataset.el] = (parseFloat(i.value) || 0) / 100);
    try {
      const r = await api("/api/charge/evaluate", "POST", {
        mix, grade: S.grade, volume_limit: parseFloat($("#c-vol").value) || 100, retention,
      });
      S.lastCharge = r;
      S.chargeMass = r.total_mass;
      S.heat = { ...S.heat, track: "eaf", grade: S.grade, mass: r.total_mass,
                 mix: r.mix, charge: r, alloy: null, initial: null,
                 pre_c: 0.37, pre_si: 0.05, skip_decarb: false };
      resetSlagForNewHeat();
      bumpHeat("manual-mix");
      updateTop();
      $("#c-result").innerHTML = renderChargeResult(r);
      close();
    } catch (e) { toast(e.message, true); }
  };
}

async function runCharge() {
  const btn = $("#c-run");
  setBusy(btn, true);
  try {
    const limits = {};
    $$(".material-row").forEach((row) => {
      const k = row.dataset.key;
      limits[k] = { enabled: row.querySelector(".m-en").checked, max: parseFloat(row.querySelector(".m-max").value) || 90 };
    });
    const retention = {};
    $$(".ret-grid input").forEach((inp) => retention[inp.dataset.el] = (parseFloat(inp.value) || 0) / 100);
    const carbon = $("#c-carbon").value;
    const massInput = Math.min(90, Math.max(10, parseFloat($("#c-mass").value) || 90));
    S.chargeMass = massInput;
    const body = {
      grade: S.grade, mass: massInput,
      volume_limit: parseFloat($("#c-vol").value) || 100,
      limits, retention, soft: true, margin: $("#c-margin")?.checked ? 0.06 : 0,
      round_tons: $("#c-round")?.checked !== false,
    };
    if (carbon !== "") body.carbon_cap = parseFloat(carbon);
    const r = await api("/api/charge/optimize", "POST", body);
    S.lastCharge = r;
    if (r.status === "ok") {
      S.heat = { ...S.heat, track: "eaf", grade: S.grade, mass: massInput, mix: r.mix,
                 charge: r, alloy: null, initial: null, pre_c: 0.37, pre_si: 0.05, skip_decarb: false };
      S.lastAlloy = null; S.alloy = null;
      resetSlagForNewHeat();
      bumpHeat("charge");
      updateTop();
    }
    $("#c-result").innerHTML = renderChargeResult(r);
  } catch (e) { toast("配料失败：" + e.message, true); }
  setBusy(btn, false);
}

async function runTotal() {
  const btn = $("#c-total");
  setBusy(btn, true);
  try {
    const massInput = Math.min(90, Math.max(10, parseFloat($("#c-mass").value) || 90));
    S.chargeMass = massInput;
    const limits = {};
    $$(".material-row").forEach((row) => {
      const k = row.dataset.key;
      limits[k] = { enabled: row.querySelector(".m-en").checked, max: parseFloat(row.querySelector(".m-max").value) || 90 };
    });
    if (!Object.values(limits).some((x) => x.enabled)) throw new Error("至少勾选一种废钢");
    const safe = !!$("#c-margin")?.checked;
    const body = {
      grade: S.grade,
      mass: massInput,
      volume_limit: parseFloat($("#c-vol").value) || 100,
      limits,
      charge_margin: safe ? 0.06 : 0.03,
      alloy_margin: safe ? 0.4 : 0.2,
      c_pre: 0.37,
      si_pre: 0.05,
      ni_cal: safe ? 0.45 : 0.42,
      power_kwh: 34200 * massInput / 90,
      power_price: 0.57,
      // 用页面上的「其他成本」设置，默认 0（模拟器口径）；不要写死 37，否则每吨凭空高约 $37
      other_cost: (Number(S.plan?.other_per_t) || 0) * massInput,
      round_tons: $("#c-round")?.checked !== false,
      alloy_step: 10,
    };
    const r = await api("/api/optimize/total", "POST", body);
    S.lastTotal = r;
    if (r.status === "ok") {
      const use = r.exec || r.best;
      S.heat = { ...S.heat, track: "eaf", grade: r.grade || S.grade, mass: massInput,
                 mix: use.charge.mix, charge: use.charge, alloy: use.alloy,
                 initial: null, pre_c: r.c_pre || 0.37, pre_si: r.si_pre || 0.05,
                 skip_decarb: false };
      resetSlagForNewHeat();
      bumpHeat("charge");
      updateTop();
    }
    $("#c-result").innerHTML = renderTotalResult(r);
    setTimeout(() => {
      const to = $("#c-toalloy");
      if (to) to.onclick = () => {
        const use = r.exec || r.best;
        S.lastAlloy = null;
        S.alloy = null;
        S.lastCharge = { ...use.charge, composition: { ...use.charge.composition, C: r.c_pre, Si: r.si_pre } };
        go("alloy");
      };
    }, 30);
  } catch (e) { toast("总成本优化失败：" + e.message, true); }
  setBusy(btn, false);
}

function renderTotalResult(r) {
  if (!r || r.status !== "ok") {
    return `<div class="card"><div class="card-b">
      <div class="badge fail">总成本优化无解</div>
      <p class="note mt8">${esc(r?.message || "约束过紧")}</p>
    </div></div>`;
  }
  const b = r.best, ex = r.exec, use = ex || b, alloy = use.alloy, base = r.baseline || {};
  return renderChargeResult(use.charge) + `
  <div class="card mt16">
    <div class="card-h"><h3>总成本优化 · 合金方案</h3><span class="sub">${ex ? "整吨装料 · 10 kg 档（可直接填报）" : "LP 联合优化（配料 + 合金）"}</span><div class="spacer"></div>
      ${r.saving != null ? `<span class="badge pass">省 $${f(r.saving, 0)} / ${f(r.saving_pct, 1)}%</span>` : ""}</div>
    <div class="card-b">
      <div class="result-head">
        <div><div class="big">$${f(r.power?.total_with_power ?? use.total_cost, 0)}<small> ${r.power ? "含电合计" : "合计"}</small></div><div class="sub">材料 $${f(use.total_cost, 0)}（废钢 $${f(use.scrap_cost, 0)} + 合金 $${f(use.alloy_cost, 0)}）${r.power ? ` · 电 $${f(r.power.cost, 0)}` : ""}${r.power && (r.power.total_with_power - use.total_cost - r.power.cost) > 1 ? ` · 其他 $${f(r.power.total_with_power - use.total_cost - r.power.cost, 0)}` : ""}</div></div>
        <div style="margin-left:auto;text-align:right"><div class="mono" style="font-size:18px">${f(alloy.mass_after, 1)} t</div><div class="sub">出钢量 · 温降 ${f(alloy.temperature_drop, 1)}°C</div></div>
      </div>
      <div class="table-wrap mt12"><table class="tbl">
        <thead><tr><th>添加剂</th><th class="num">加入量 kg</th><th class="num">成本</th></tr></thead>
        <tbody>${alloy.additions.map((a) => `<tr><td class="strong">${a.name}</td><td class="num">${f(a.mass, 0)}</td><td class="num">${money(a.cost)}</td></tr>`).join("")}
        <tr><td class="strong">合计</td><td class="num strong">${f(alloy.added_total, 0)}</td><td class="num strong">${money(alloy.cost)}</td></tr></tbody>
      </table></div>
      <div class="hint mt12">对照旧版贪心：废钢 $${f(base.scrap_cost, 0)} + 合金 $${f(base.alloy_cost, 0)} = $${f(base.total_cost, 0)}；本方案 $${f(use.total_cost, 0)}，省 $${f(r.saving, 0)}。${r.power ? ` 电能另计：${f(r.power.kwh, 0)} kWh ≈ $${f(r.power.cost, 0)}，含电总成本 ≈ $${f(r.power.total_with_power, 0)}。` : ""}</div>
      ${ex ? `<div class="hint">连续 LP 结果 $${f(b.total_cost, 0)}；按整吨装料 + 10 kg 合金取整后 $${f(ex.total_cost, 0)}（${ex.delta_vs_lp >= 0 ? "高" : "低"} $${f(Math.abs(ex.delta_vs_lp), 0)}）。表内已是取整后可填报的数。</div>` : `<div class="hint">本卡是连续 LP 结果；勾选「装料按整吨取整」后会给出可填报的整吨 + 10 kg 方案。</div>`}
      <div class="hint">合金方案按 C ${f(r.c_pre, 2)}% / Si ${f(r.si_pre, 2)}%（吹氧后）计算；实际以停氧取样为准。出钢前请把实测 C/Si 回填合金页复核。</div>
      <div class="hint">节电：75 MW 保温每减少 1 分钟约省 $713、1,250 kWh、CO₂ 约 626 kg；120 MW 每分钟约省 $1,140。算法只能省 scrap+alloy，电耗要靠缩短通电时间。</div>
    </div>
  </div>`;
}

function renderChargeResult(r) {
  if (!r || r.status !== "ok") {
    const d = (r && r.diagnosis) || [];
    return `<div class="card"><div class="card-b">
      <div class="badge fail">无可行解</div>
      <p class="note mt8">${esc(r?.message || "约束过紧")}</p>
      ${d.length ? `<div class="warn-list mt12">${d.map((x) => `<div class="warn-item bad"><span class="ico">!</span><span>${esc(x.message)}</span></div>`).join("")}</div>` : ""}
    </div></div>`;
  }
  const comp = r.composition, checks = r.checks.filter((c) => ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "N", "Nb", "Ti", "Al", "V"].includes(c.element));
  const fromPlan = planFresh() && S.plan?.data?.plans?.eaf?.summary?.charge_result === r;
  const html = `<div class="card">
    <div class="card-h"><h3>推荐配料</h3><span class="sub">${gradeName(r.grade)} · 熔炼后预测</span>${fromPlan ? '<span class="badge neutral">来自初始规划</span>' : ""}<div class="spacer"></div>
      <button class="btn sm" id="c-towizard">生成操作流程</button>
      <button class="btn sm" id="c-toplan">生成初始规划</button>
      <button class="btn sm" id="c-save">保存炉次</button>
      <button class="btn sm primary" id="c-toalloy">去补合金 →</button></div>
    <div class="card-b">
      <div class="result-head">
        <div><div class="big">$${f(r.cost_per_t, 1)}<small> /t</small></div><div class="sub">废钢成本 · 合计 ${money(r.cost)}（不含电耗/电极/其他）</div></div>
        <div style="margin-left:auto;text-align:right"><div class="mono" style="font-size:18px">${f(r.total_mass, 1)} t</div><div class="sub">装入量 · ${f(r.volume, 1)} m³</div>${S.boot.grades_eaf[r.grade]?.process ? `<div class="sub">工艺窗口：${S.boot.grades_eaf[r.grade].process.temp[0]}–${S.boot.grades_eaf[r.grade].process.temp[1]}°C · ≤${S.boot.grades_eaf[r.grade].process.time_max_min} min · ${S.boot.grades_eaf[r.grade].process.weight[0]}–${S.boot.grades_eaf[r.grade].process.weight[1]} t</div>` : ""}</div>
      </div>
      <div class="table-wrap mt12"><table class="tbl">
        <thead><tr><th>炉料</th><th>形态</th><th class="num">质量 t</th><th class="num">占比</th><th class="num">体积 m³</th><th class="num">单价</th><th class="num">成本</th></tr></thead>
        <tbody>${r.items.map((i) => `<tr><td class="strong">${i.name}</td><td><span class="badge form">${i.form}</span></td><td class="num">${f(i.mass, 1)}</td><td class="num">${f(i.share, 1)}%</td><td class="num">${f(i.volume, 1)}</td><td class="num">$${i.price}</td><td class="num">${money(i.cost)}</td></tr>`).join("")}
        <tr><td class="strong">合计</td><td></td><td class="num strong">${f(r.total_mass, 1)}</td><td class="num">100%</td><td class="num">${f(r.volume, 1)}</td><td></td><td class="num strong">${money(r.cost)}</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <div class="grid g2 mt16">
    <div class="card">
      <div class="card-h"><h3>成分校验</h3><span class="sub">熔炼后 / 目标区间</span></div>
      <div class="card-b spec-list">${checks.map(specRow).join("")}</div>
    </div>
    <div class="card">
      <div class="card-h"><h3>风险与提示</h3><span class="sub">${r.warnings.length ? r.warnings.length + " 条" : "无超限"}</span></div>
      <div class="card-b warn-list">
        ${r.warnings.length ? r.warnings.map((w) => `<div class="warn-item ${w.includes("超上限") || w.includes("超限") ? "bad" : ""}"><span class="ico">!</span><span>${esc(w)}</span></div>`).join("") : '<div class="warn-item ok"><span class="ico">✓</span><span>所有受控元素均在限值内。</span></div>'}
        ${r.need_alloy.length ? `<div class="hint">需在合金补加阶段补足：${r.need_alloy.map((n) => n.element + " +" + f(n.gap, 3) + "%").join("、")}</div>` : ""}
      </div>
    </div>
  </div>

  <div class="card mt16">
    <div class="card-h"><h3>料斗分配</h3><span class="sub">单斗 40 m³ · 粗废料 ≤30%</span><div class="spacer"></div><span class="mono small">总容积 ${f(r.baskets.total_volume, 1)} m³</span></div>
    <div class="card-b basket-grid">
      ${r.baskets.baskets.map((b) => `<div class="basket">
        <h4>料斗 ${b.index}<span>${f(b.mass, 1)} t</span></h4>
        <div class="volbar"><i style="width:${Math.min(100, b.volume / 40 * 100)}%"></i></div>
        <div class="meta"><span>${f(b.volume, 1)} / 40 m³</span><span>粗料 ${f(b.coarse_share, 0)}%</span></div>
        <div class="mt8">${b.items.map((it) => `<div class="line"><span>${it.name}</span><b>${f(it.mass, it.mass < 0.1 ? 2 : 1)} t</b></div>`).join("")}</div>
      </div>`).join("")}
    </div>
    ${r.baskets.warnings.length ? `<div class="card-b" style="padding-top:0"><div class="warn-list">${r.baskets.warnings.map((w) => `<div class="warn-item"><span class="ico">!</span><span>${esc(w)}</span></div>`).join("")}</div></div>` : ""}
  </div>`;

  setTimeout(() => {
    const save = $("#c-save"); if (save) save.onclick = () => saveRun("配料方案", r);
    const tw = $("#c-towizard"); if (tw) tw.onclick = () => goWizardFromHeat("eaf");
    const tp = $("#c-toplan"); if (tp) tp.onclick = () => {
      S.plan.grade = S.heat?.grade || S.grade;
      S.plan.mass = Math.round(S.heat?.mass || r.total_mass || 90);
      S.plan.useHeat = true;
      S.plan.data = null;
      go("plan");
    };
    const to = $("#c-toalloy"); if (to) to.onclick = () => { S.lastAlloy = null; S.alloy = null; go("alloy"); };
  }, 0);
  return html;
}

function specRow(c) {
  const dom = Math.max(c.max ?? 0, c.high ?? 0, c.value ?? 0) * 1.22 || 0.01;
  const lo = c.min ?? 0, hi = c.max ?? dom;
  const left = Math.max(0, lo / dom * 100), width = Math.max(2, (hi - lo) / dom * 100);
  const mark = Math.min(99, Math.max(0, (c.value || 0) / dom * 100));
  const cls = { pass: "pass", risk: "risk", fail: "fail", adjust: "adjust", low: "adjust" }[c.status] || "neutral";
  const txt = { pass: "合格", risk: "波动", fail: "超限", adjust: "需调整", low: "需补加" }[c.status] || "—";
  return `<div class="spec-row">
    <span class="el">${c.element}</span>
    <div class="spec-track"><div class="spec-band" style="left:${left}%;width:${width}%"></div><div class="spec-mark" style="left:${mark}%"></div></div>
    <span class="spec-val">${f(c.value, 4)}</span>
    <span class="spec-lim">${c.min != null ? f(c.min, 3) + "–" : "≤"}${c.max != null ? f(c.max, 3) : "—"}</span>
    <span class="spec-status"><span class="badge ${cls}">${txt}</span></span>
  </div>`;
}

function saveRun(name, payload) {
  const n = prompt("炉次名称", name + " · " + new Date().toLocaleDateString("zh-CN"));
  if (!n) return;
  api("/api/runs", "POST", { name: n, grade: S.heat?.grade || S.grade, payload }).then(() => {
    S.runsLoaded = false;
    toast("已保存炉次");
  }).catch((e) => toast(e.message, true));
}

/* ---------------- EAF / SM separate records ---------------- */
async function ensureRuns(force = false) {
  if (S.runsLoaded && !force) return S.runs || [];
  try {
    const r = await api("/api/runs");
    S.runs = r.runs || [];
  } catch (e) {
    S.runs = S.runs || [];
  }
  S.runsLoaded = true;
  return S.runs;
}

function runEafRef(run) {
  const p = run?.payload || {};
  if (p.kind === "eaf" && p.eaf) {
    const s = p.eaf.summary || p.summary || {};
    return { final: s.final || {}, tap_mass: s.tap_mass, grade: p.eaf.grade, name: run.name };
  }
  if (p.plan?.plans?.eaf) {
    const e = p.plan.plans.eaf;
    return { final: e.summary?.final || {}, tap_mass: e.summary?.tap_mass, grade: e.grade, name: run.name };
  }
  if (p.track === "eaf" && p.summary) {
    return { final: p.summary.final || {}, tap_mass: p.summary.tap_mass, grade: p.grade, name: run.name };
  }
  return null;
}

function saveEafRun(data) {
  if (!data) return;
  const name = prompt("EAF 炉次名称", "EAF · " + (data.grade_name || "") + " · " + new Date().toLocaleDateString("zh-CN"));
  if (!name) return;
  const s = data.summary || {};
  const payload = {
    kind: "eaf",
    eaf: data,
    summary: {
      mass: s.mass, tap_mass: s.tap_mass, final: s.final,
      total_cost: s.total_cost, total_per_t: s.total_per_t,
      scrap_cost: s.scrap_cost, alloy_cost: s.alloy_cost,
      energy_kwh: s.energy_kwh, energy_cost: s.energy_cost, other_cost: s.other_cost,
    },
  };
  return api("/api/runs", "POST", { name, grade: data.grade || S.grade, payload })
    .then((r) => {
      S.lastEafRunId = r.run?.id || null;
      S.lastEafName = name;
      S.runsLoaded = false;
      toast("已保存 EAF 炉次；二次精炼可直接选它");
    })
    .catch((e) => toast(e.message, true));
}

function saveSmRun(data, eafIdOverride) {
  if (!data) return;
  const eafId = eafIdOverride !== undefined ? eafIdOverride : (S.wizard.eafRunId || S.lastEafRunId || "");
  const eaf = (S.runs || []).find((x) => x.id === eafId)
    || (eafId && eafId === S.lastEafRunId ? { name: S.lastEafName } : null);
  const name = prompt("二次精炼记录名称", "SM · " + (data.grade_name || "") + " · " + new Date().toLocaleDateString("zh-CN"));
  if (!name) return;
  const s = data.summary || {};
  const payload = {
    kind: "sm",
    eaf_run_id: eafId,
    eaf_name: eaf?.name || "",
    sm: data,
    summary: {
      mass: data.mass, initial: s.initial, final: s.final,
      total_cost: s.total_cost, total_per_t: s.total_per_t, alloy_cost: s.alloy_cost,
    },
  };
  return api("/api/runs", "POST", { name, grade: data.grade || S.grade, payload })
    .then(() => {
      S.runsLoaded = false;
      toast(eafId ? "已保存二次精炼记录，并关联 EAF 炉次" : "已保存二次精炼记录（未关联 EAF）");
    })
    .catch((e) => toast(e.message, true));
}

function startSmFromRun(id) {
  const run = (S.runs || []).find((x) => x.id === id);
  const ref = run ? runEafRef(run) : null;
  if (!ref) { toast("这条记录里没有 EAF 出钢成分", true); return; }
  S.smcalc.eafRunId = id;
  S.smcalc.initial = smPreFromEaf({ final: ref.final || {} });
  S.smcalc.mass = Math.round(ref.tap_mass || S.heat?.sm_mass || 90);
  S.smcalc.result = null;
  S.smcalc.route = [];
  S.smcalc.additions = {};
  toast("已带入 EAF 炉次：" + (ref.name || id));
  go("refine");
}

/* ---------------- alloy ---------------- */
const ALLOY_ELEMENTS = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "Al", "Nb", "Ti", "V"];
const DYN_ELEMENTS = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "Al", "Nb", "Ti", "V", "B", "N", "H", "O"];

function viewAlloy() {
  if (!S.alloy && planFresh() && S.plan.data?.summary?.alloy_eaf?.length) {
    const p = S.plan.data;
    const pre = p.plans?.eaf?.summary?.pre || { C: S.heat?.pre_c ?? 0.37, Si: S.heat?.pre_si ?? 0.05 };
    S.alloy = {
      grade: p.grade, catalog: "eaf", profile: "eaf_cal", mass: p.mass, pos: S.alloyPos ?? 0.5,
      initial: { ...(p.summary.charge_composition || {}), C: pre.C, Si: pre.Si },
      targets: targetsFromSpec(S.boot.grades_sm[p.grade]?.specs || S.boot.grades_sm.sc21_refining.specs, S.alloyPos ?? 0.5),
      fromPlan: true,
    };
    S.lastAlloy = planAlloyResult(p);
  }
  if (!S.alloy) {
    const last = S.lastCharge;
    S.alloy = {
      grade: S.grade,
      catalog: last ? "eaf" : "sm",
      profile: last ? (S.grade === "sc21_engineering" ? "eaf_cal" : "eaf_tap") : "ladle",
      mass: last ? Math.round(last.mass || last.total_mass || 90) : 100,
      pos: S.alloyPos ?? 0.5,
    };
    const g = S.boot.grades_sm[S.alloy.grade] || S.boot.grades_sm["sc21_refining"];
    S.alloy.targets = targetsFromSpec(g.specs, S.alloy.pos);
    S.alloy.initial = last ? { ...last.composition, C: S.heat?.pre_c ?? 0.37, Si: S.heat?.pre_si ?? 0.05 } : { C: 0.05, Si: 0.01, Mn: 0.1 };
  }
  const a = S.alloy;
  const g = S.boot.grades_sm[a.grade];
  $("#view").innerHTML = `
  <div class="page-head"><div><h1>合金补加</h1><p>按母合金成分与回收率计算添加量。先加大宗合金，再用增碳剂微调 C；注意 FeMn 会带入 C、Si、P。</p></div><div class="spacer"></div>
    <span class="badge neutral">SM 表 7-2 / 7-3</span></div>
  ${renderHeatFlow("alloy")}
  <div class="workbench">
    <div class="panel card">
      <div class="card-h"><h3>计算参数</h3><span class="sub">${g.short}</span></div>
      <div class="card-b">
        <div class="form-grid">
          <label class="field full"><span>目标钢种</span><select id="a-grade">${Object.entries(S.boot.grades_sm).map(([k, x]) => `<option value="${k}" ${k === a.grade ? "selected" : ""}>${x.name}</option>`).join("")}</select></label>
          <label class="field"><span>钢水质量 t</span><input id="a-mass" class="mono" type="number" value="${a.mass}" step="1"></label>
          <label class="field"><span>添加剂表</span><select id="a-cat"><option value="sm" ${a.catalog === "sm" ? "selected" : ""}>二次炼钢（SM）</option><option value="eaf" ${a.catalog === "eaf" ? "selected" : ""}>电弧炉（EAF）</option></select></label>
          <label class="field full"><span>添加位置 / 回收率</span><select id="a-prof"><option value="ladle" ${a.profile === "ladle" ? "selected" : ""}>LF / RH / CAS-OB（保护气氛）</option><option value="eaf_cal" ${a.profile === "eaf_cal" ? "selected" : ""}>EAF 模拟器实测（Cr/Mn≈98%，Si≈95%）</option><option value="eaf_tap" ${a.profile === "eaf_tap" ? "selected" : ""}>EAF 出钢（手册 BOF 列，较低）</option></select></label>
          <label class="field full"><span>目标位置（想省成本就往左挪）</span><select id="a-pos">
            <option value="0.5" ${(a.pos ?? 0.5) === 0.5 ? "selected" : ""}>中值 · 稳妥（默认）</option>
            <option value="0.3" ${(a.pos ?? 0.5) === 0.3 ? "selected" : ""}>偏下限 · 省合金</option>
            <option value="0.15" ${(a.pos ?? 0.5) === 0.15 ? "selected" : ""}>贴近下限 · 最省</option>
          </select></label>
        </div>
        <div class="hint mt12">初始成分填吹氧/精炼后的实测值，或先用「炉料配比」计算后自动带入。若初始 C 高于目标 C，说明还需吹氧脱碳，合金计算不会降 C。目标留空表示不配该元素。</div>
        <div class="table-wrap mt12" style="max-height:560px;border:1px solid var(--line);border-radius:8px">
          <table class="tbl"><thead><tr><th>元素</th><th class="num">初始 %</th><th class="num">目标 %</th></tr></thead>
          <tbody>${ALLOY_ELEMENTS.map((e) => `<tr><td class="strong">${e}</td>
            <td class="num"><input class="mono a-init" data-el="${e}" type="number" step="0.001" value="${a.initial[e] != null ? +Number(a.initial[e]).toFixed(4) : ""}"></td>
            <td class="num"><input class="mono a-target" data-el="${e}" type="number" step="0.001" value="${a.targets[e] != null ? a.targets[e] : ""}"></td></tr>`).join("")}</tbody></table>
        </div>
        <label style="display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--ink-2);margin-top:10px">
          <input type="checkbox" id="a-round" checked style="width:14px;height:14px;accent-color:var(--accent)">
          加入量按 10 kg 档取整（模拟器只能按 10 kg 加）
        </label>
        <button class="btn primary mt12" id="a-run" style="width:100%">计算补加</button>
      </div>
    </div>
    <div id="a-result">${S.lastAlloy ? renderAlloyResult(S.lastAlloy) : '<div class="card"><div class="empty">填写初始/目标成分后点击「计算补加」。</div></div>'}</div>
  </div>`;
  $("#a-grade").onchange = (e) => {
    a.grade = e.target.value; a.targets = targetsFromSpec(S.boot.grades_sm[a.grade].specs, a.pos ?? 0.5);
    a.initial = S.lastCharge ? { ...S.lastCharge.composition } : a.initial;
    viewAlloy();
  };
  $("#a-cat").onchange = (e) => { a.catalog = e.target.value; };
  $("#a-prof").onchange = (e) => { a.profile = e.target.value; };
  $("#a-pos").onchange = (e) => {
    a.pos = parseFloat(e.target.value);
    S.alloyPos = a.pos;
    try { localStorage.setItem("steel-lab-alloy-pos", String(a.pos)); } catch (err) {}
    a.targets = targetsFromSpec(S.boot.grades_sm[a.grade].specs, a.pos);
    S.lastAlloy = null;
    viewAlloy();
    setTimeout(runAlloy, 40);
  };
  $("#a-run").onclick = runAlloy;
  if (!S.lastAlloy) setTimeout(runAlloy, 30);
}

function targetsFromSpec(specs, pos = 0.5) {
  const out = {};
  for (const e of ALLOY_ELEMENTS) {
    if (e === "N" || e === "O" || e === "H") continue;
    const s = specs[e];
    if (!s) continue;
    if (s[0] != null && s[0] > 0 && s[1] != null) out[e] = +((s[0] + (s[1] - s[0]) * pos).toFixed(4));
    else if (s[0] != null && s[0] > 0) out[e] = s[0];
  }
  return out;
}

async function runAlloy() {
  const btn = $("#a-run"); setBusy(btn, true);
  try {
    S.alloy.fromPlan = false;
    const initial = {}, targets = {};
    $$(".a-init").forEach((i) => { if (i.value !== "") initial[i.dataset.el] = parseFloat(i.value); });
    $$(".a-target").forEach((i) => { if (i.value !== "") targets[i.dataset.el] = parseFloat(i.value); });
    S.alloy.mass = parseFloat($("#a-mass").value) || 100;
    const specs = S.boot.grades_sm[S.alloy.grade].specs;
    const r = await api("/api/alloy/calculate", "POST", {
      mass: S.alloy.mass, initial, targets, catalog: S.alloy.catalog,
      profile: S.alloy.profile, limits: specs, max_passes: 2,
      round_step: $("#a-round")?.checked ? 10 : 0,
      pos: S.alloy.pos ?? S.alloyPos ?? 0.5,
    });
    S.lastAlloy = r;
    const tr = S.alloy.catalog === "eaf" ? "eaf" : "sm";
    const mappedGrade = EAF_GRADE_BY_SM[S.alloy.grade] || S.heat.grade || S.grade;
    S.heat = { ...S.heat, track: tr, grade: mappedGrade, mass: S.alloy.mass,
               alloy: r, initial: initial,
               pre_c: initial.C != null ? initial.C : (S.heat.pre_c || 0.37),
               pre_si: initial.Si != null ? initial.Si : (S.heat.pre_si || 0.05),
               skip_decarb: tr === "sm" };
    bumpHeat("alloy");
    updateTop();
    $("#a-result").innerHTML = renderAlloyResult(r);
    const sv = $("#a-save"); if (sv) sv.onclick = () => saveRun("合金方案", { kind: "alloy", grade: S.heat?.grade || S.grade, alloy: r, heat: { ...S.heat, charge: undefined, dynamic: undefined } });
    const tp = $("#a-toplan"); if (tp) tp.onclick = () => {
      S.plan.grade = S.heat?.grade || (S.grade === "sc21_refining" ? "sc21_engineering" : S.grade);
      S.plan.mass = Math.round(S.heat?.mass || 90);
      S.plan.useHeat = true;
      S.plan.data = null;
      go("plan");
    };
  } catch (e) { toast(e.message, true); }
  setBusy(btn, false);
}

function renderAlloyResult(r) {
  const specs = S.boot.grades_sm[S.alloy.grade].specs;
  const keys = ALLOY_ELEMENTS.filter((e) => r.final[e] != null && specs[e]);
  return `<div class="card">
    <div class="card-h"><h3>补加方案</h3><span class="sub">${gradeName(S.alloy.grade)}</span>${S.alloy.fromPlan ? '<span class="badge neutral">来自初始规划</span>' : ""}<div class="spacer"></div><button class="btn sm" id="a-towizard" onclick="goWizardFromAlloy()">更新操作流程</button><button class="btn sm" id="a-toplan">生成初始规划</button><button class="btn sm" id="a-save">保存</button></div>
    <div class="card-b">
      <div class="result-head">
        <div><div class="big">${f(r.added_total, 1)}<small> kg</small></div><div class="sub">添加剂总量 · ${money(r.cost)}</div></div>
        <div style="margin-left:auto;text-align:right"><div class="mono" style="font-size:17px">${f(r.mass_after, 2)} t</div><div class="sub">出钢量 · 温降 −${f(r.temperature_drop, 1)}°C</div></div>
      </div>
      <div class="table-wrap mt12"><table class="tbl"><thead><tr><th>添加剂</th><th class="num">加入量 kg</th><th class="num">成本</th><th>带入元素 kg</th></tr></thead>
      <tbody>${r.additions.map((a) => `<tr><td class="strong">${a.name}</td><td class="num">${f(a.mass, 1)}</td><td class="num">${money(a.cost)}</td><td class="small muted">${Object.entries(a.elements).map(([e, v]) => e + " " + f(v, 1)).join(" · ")}</td></tr>`).join("") || '<tr><td colspan="4" class="empty">无需添加</td></tr>'}</tbody></table></div>
    </div>
  </div>
  <div class="card mt16"><div class="card-h"><h3>最终成分</h3><span class="sub">与 SM 表 6-1 对比</span></div>
    <div class="card-b spec-list">${keys.map((e) => {
      const s = specs[e] || [null, null]; const v = r.final[e] || 0;
      let st = "pass";
      if (s[1] != null && v > s[1] + 0.002) st = "fail";
      else if (s[0] != null && v < s[0] - 0.002) st = "risk";
      return specRow({ element: e, min: s[0], max: s[1], value: v, low: v, high: v, status: st });
    }).join("")}</div>
  </div>
  ${r.warnings.length || r.unmet.length ? `<div class="card mt16"><div class="card-h"><h3>提示</h3></div><div class="card-b warn-list">
    ${r.warnings.map((w) => `<div class="warn-item"><span class="ico">!</span><span>${esc(w)}</span></div>`).join("")}
    ${r.unmet.map((u) => `<div class="warn-item bad"><span class="ico">!</span><span>${u.element}：${esc(u.reason)}</span></div>`).join("")}
  </div></div>` : ""}`;
}

/* ---------------- refine ---------------- */
function renderSmSpecStrip() {
  const specs = S.boot.grades_sm.sc21_refining?.specs || {};
  const final = S.plan?.data?.summary?.final_sm || {};
  return `<div class="card sm-specs">
    <div class="card-h"><h3>二次精炼元素要求</h3><span class="sub">17 元素 · 目标窗口来自 SM 表 6-1 / #1552955</span><div class="spacer"></div><span class="badge neutral">${Object.keys(specs).length} 元素</span></div>
    <div class="card-b"><div class="el-req-grid">${Object.entries(specs).map(([e, sp]) => {
      const v = final[e];
      let st = "neutral", label = "目标";
      if (v != null) {
        if (sp[0] != null && v < sp[0] - 1e-6) { st = "adjust"; label = "偏低"; }
        else if (sp[1] != null && v > sp[1] + 1e-6) { st = "risk"; label = "偏高"; }
        else { st = "pass"; label = "合格"; }
      }
      return `<div class="el-req ${st}"><span>${e}</span><b>${v != null ? f(v, 4) : "—"}</b><i>${esc(fmtSpec(sp))}</i><em class="badge ${st}">${label}</em></div>`;
    }).join("")}</div></div>
  </div>`;
}

function viewSlag() {
  S.tab = "slag";
  $("#view").innerHTML = `
  <div class="page-head"><div><h1>EAF 造渣</h1><p>造渣和碱度属于电弧炉（EAF 手册 5.5 发泡炉渣 / 5.6 脱硫）。这里核算 CaO/SiO₂ 碱度、MgO、FeO 和推荐石灰/白云石用量；二次精炼页不再放造渣计算。</p></div>
    <div class="spacer"></div><span class="badge neutral">EAF 5.5–5.6</span></div>
  ${renderHeatFlow("slag")}
  <div id="tab-body"></div>`;
  renderTab();
  // 只在用户没有手工改过渣料时自动给推荐值；手工改过就保留，避免“又被算回去”
  if (!S.slag.manual) setTimeout(autoSlagRecalc, 0);
}

async function autoSlagRecalc() {
  const massEl = $("#g-mass");
  if (!massEl || S.slag.manual) return;
  const hs = heatSilica();
  const mass = parseFloat(massEl.value) || 90;
  const basicity = parseFloat($("#g-b")?.value) || S.slag.b || 1.70;
  const mgo = parseFloat($("#g-mgo")?.value) || S.slag.mgo || 8.8;
  const feo = parseFloat($("#g-feo")?.value) || S.slag.feo || 45;
  try {
    const r = await api("/api/refine/slag", "POST", {
      mass, si: hs.siOxPct, sio2_gangue: hs.gangue, mix: hs.mix, si_retained: hs.siRet,
      lime: 0, dolomite: 0, fluorspar: 0.05,
      basicity, mgo, feo,
    });
    if (!r.recommend || !$("#g-lime") || S.slag.manual) return;
    S.slag.lime = +(r.recommend.lime_kg / 1000).toFixed(2);
    S.slag.dol = +(r.recommend.dolomite_kg / 1000).toFixed(2);
    S.slag.flu = +(r.recommend.fluorspar_kg / 1000).toFixed(2);
    S.slag.b = basicity; S.slag.mgo = mgo; S.slag.feo = feo;
    $("#g-lime").value = S.slag.lime.toFixed(2);
    $("#g-dol").value = S.slag.dol.toFixed(2);
    $("#g-flu").value = S.slag.flu.toFixed(2);
    $("#r-run")?.click();
  } catch (e) { /* 静默：保留手动输入 */ }
}

const SM_DESTS = [
  { key: "argon", name: "氩站", time: 5, temp: 5, note: "氩气搅拌，均匀成分和温度",
    actions: ["氩气 1–3 Nm³/min，钢液面轻微翻动即可", "搅拌 3–5 min 后取样"], checks: ["成分均匀", "温度 ≥1550°C"] },
  { key: "tank", name: "德环脱气装置", time: 15, temp: 15, note: "真空脱气，主要降 H / N / O",
    actions: ["抽真空到 ≤1 mbar", "保持 10–15 min，氩气小流量"], checks: ["H ≤2 ppm", "N ≤80 ppm", "O ≤20 ppm"] },
  { key: "casob", name: "CAS-OB", time: 8, temp: 5, note: "吹氧脱碳 + 铝升温",
    actions: ["先确认 C 高于目标再开吹氧", "氩气 1.0 Nm³/min，按 C 停氧", "需要升温时加铝粒"], checks: ["C 到 0.44–0.46% 关吹氧", "温度 1573–1576°C"] },
  { key: "lf", name: "钢包炉", time: 10, temp: -3, note: "电弧加热、调温、造渣",
    actions: ["20 MW 加热，每次 2–3 min 复测", "到 1573–1576°C 停"], checks: ["温度 1573–1576°C", "渣况正常"] },
  { key: "vd", name: "钢包脱气", time: 15, temp: 15, note: "真空脱气，降 H / N",
    actions: ["真空保持 10–20 min", "脱气后软搅 3 min"], checks: ["H ≤2 ppm", "N ≤80 ppm"] },
  { key: "slab", name: "板坯铸机", time: 0, temp: 0, note: "板坯连铸终点",
    actions: ["确认目标温度与钢种匹配", "选板坯铸机后直接出站"], checks: ["温度 1558–1578°C", "成分全部在窗口"] },
  { key: "bloom", name: "大方坯铸机", time: 0, temp: 0, note: "大方坯连铸终点",
    actions: ["确认目标温度与钢种匹配", "选大方坯铸机后直接出站"], checks: ["温度 1558–1578°C", "成分全部在窗口"] },
  { key: "billet", name: "小方坯铸机", time: 0, temp: 0, note: "小方坯连铸终点",
    actions: ["确认目标温度与钢种匹配", "选小方坯铸机后直接出站"], checks: ["温度 1558–1578°C", "成分全部在窗口"] },
];

function smInitialFields() {
  return [["C", "C %"], ["Si", "Si %"], ["Mn", "Mn %"], ["Cr", "Cr %"],
          ["P", "P %"], ["S", "S %"], ["Mo", "Mo %"], ["Ni", "Ni %"],
          ["Cu", "Cu %"], ["Al", "Al %"], ["Nb", "Nb %"], ["Ti", "Ti %"],
          ["V", "V %"], ["B", "B %"], ["O", "O %（0.05=500ppm）"], ["N", "N %"], ["H", "H %"]];
}

function smRouteChips() {
  const sc = S.smcalc;
  if (!sc.route.length) return '<span class="muted small">还没选去向。用上面的下拉加一个工位，或点「常用路线」。</span>';
  return sc.route.map((k, i) => {
    const d = SM_DESTS.find((x) => x.key === k);
    return `<span class="sm-route-chip"><b>${i + 1}</b>${esc(d?.name || k)}<button data-rm="${k}" title="移除">×</button></span>`;
  }).join('<span class="sm-route-arrow">→</span>');
}

function renderSmAlloyTable() {
  const sc = S.smcalc;
  const adds = S.boot.additives_sm || [];
  const rows = adds.map((a) => {
    const qty = Number(sc.additions[a.key] || 0);
    return `<tr><td class="strong">${esc(a.name)}</td><td class="mono muted">$${a.price}/t</td>
      <td><input class="mono sm-add" data-key="${a.key}" type="number" min="0" step="10" value="${qty || ""}" placeholder="0"></td>
      <td class="mono sm-cost" data-key="${a.key}">$${f(qty * a.price / 1000, 1)}</td></tr>`;
  }).join("");
  return `<div class="table-wrap sm-alloy-wrap"><table class="tbl sm-alloy-tbl">
    <thead><tr><th>合金元素</th><th>单价</th><th>数量 kg</th><th>成本</th></tr></thead>
    <tbody>${rows}</tbody>
    <tfoot><tr><td class="strong">合计</td><td></td><td class="mono" id="sm-add-total-kg">0 kg</td><td class="mono" id="sm-add-total-cost">$0</td></tr></tfoot>
  </table></div>`;
}

function renderSmResult() {
  const sc = S.smcalc;
  const r = sc.result;
  if (!r) return '<div class="empty">填好合金量后点「计算成分与成本」。</div>';
  const specs = S.boot.grades_sm.sc21_refining?.specs || {};
  const keys = ["C", "Si", "Mn", "P", "S", "Cr", "Mo", "Ni", "Cu", "Al", "Nb", "Ti", "V", "B", "N", "H", "O"];
  const chips = keys.map((e) => {
    const sp = specs[e] || [null, null];
    const v = r.final?.[e];
    let st = "neutral";
    if (v != null) {
      if (sp[0] != null && v < sp[0] - 1e-6) st = "adjust";
      else if (sp[1] != null && v > sp[1] + 1e-6) st = "risk";
      else st = "pass";
    }
    return `<div class="el-req ${st}"><span>${e}</span><b>${v != null ? f(v, 4) : "—"}</b><i>${esc(fmtSpec(sp))}</i><em class="badge ${st}">${st === "pass" ? "合格" : st === "adjust" ? "偏低" : st === "risk" ? "偏高" : "—"}</em></div>`;
  }).join("");
  const out = r.out_of_spec || [];
  const siAdd = ["fesi75_sm", "fesi75hp_sm", "fesi45", "simn"]
    .reduce((a, k) => a + Number(sc.additions[k] || 0), 0);
  const siAlready = Number(sc.initial?.Si || 0) >= 0.24;
  const sim = sc.sim || {};
  const simTime = sim.time_min ? Math.floor(sim.time_min / 60) + "h" + String(sim.time_min % 60).padStart(2, "0") + "m" : "";
  return `<div class="sm-result-kpis">
      <div><span>合金总重</span><b>${f(r.added_total, 0)} kg</b></div>
      <div><span>合金成本</span><b>${money(r.cost)}</b></div>
      <div><span>出站量</span><b>${f(r.mass_after, 1)} t</b></div>
      <div><span>吨钢合金</span><b>$${f(r.cost / (r.mass_after || 1), 1)}/t</b></div>
    </div>
    ${simTime || sim.cost_per_t ? `<div class="hint mt8">模拟器实测：${[simTime, sim.mass ? f(sim.mass, 2) + " t" : "", sim.cost_per_t ? "$" + f(sim.cost_per_t, 2) + "/t" : ""].filter(Boolean).join(" · ")}。这是整炉总成本；本页只算二次精炼合金。</div>` : ""}
    <div class="el-req-grid mt12">${chips}</div>
    ${out.length ? `<div class="warn-item bad mt12"><span class="ico">!</span><span>${out.map(esc).join("；")}</span></div>` : '<div class="warn-item mt12"><span class="ico">✓</span><span>17 元素全部在窗口内。</span></div>'}
    ${siAlready && siAdd > 0 ? `<div class="warn-item bad mt12"><span class="ico">!</span><span>Si 已经在 0.24–0.32% 合格区间，这里又加了 ${f(siAdd, 0)} kg 含硅合金（硅铁/硅锰）。补 Mn 请用高碳/低碳锰铁，不要用硅锰把 Si 顶高。</span></div>` : ""}
    <div class="hint mt8">以上是二次精炼合金成本，不含 EAF；整炉成本 = EAF 成本 + 这部分，看「初始规划」的全程成本。温降估算：合金加入约 −${f(r.temperature_drop, 1)}°C，实际还要叠加路线工位温降。</div>`;
}

function renderSmStationNotes() {
  const sc = S.smcalc;
  if (!sc.route.length) return '<div class="empty">先选择精炼去向。</div>';
  return sc.route.map((k, i) => {
    const d = SM_DESTS.find((x) => x.key === k);
    if (!d) return "";
    return `<div class="sm-station">
      <div class="sm-station-head"><b>${i + 1}. ${esc(d.name)}</b><span>${d.time ? "约 " + d.time + " min" : ""}${d.temp ? " · 温降约 " + Math.abs(d.temp) + "°C" : ""}</span></div>
      <p>${esc(d.note)}</p>
      <ul>${d.actions.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      <div class="sm-checks">${d.checks.map((x) => `<span>${esc(x)}</span>`).join("")}</div>
    </div>`;
  }).join("");
}

function smPreFromEaf(ref) {
  const src = ref?.final || {};
  const base = { ...WIZ_DEFAULT_SM, ...src };
  const anchors = S.plan?.data?.summary?.c_anchors || {};
  return {
    ...base,
    // 合金是在脱碳/脱气之后加的：C 用脱气终点，Si/Mn/Cr 扣掉吹氧损失
    C: anchors.degas ?? 0.335,
    Si: Math.max(0, (base.Si || 0) - 0.015),
    Mn: Math.max(0, (base.Mn || 0) - 0.010),
    Cr: Math.max(0, (base.Cr || 0) - 0.010),
    Al: Math.min(base.Al || 0.002, 0.002),
    O: 0.0016,
  };
}

function parseSimulatorText(text) {
  const out = {};
  const t = String(text || "").trim();
  if (!t) return out;
  try {
    const j = JSON.parse(t);
    const walk = (obj) => {
      for (const [k, v] of Object.entries(obj || {})) {
        if (v && typeof v === "object") { walk(v); continue; }
        const key = String(k).replace(/[^A-Za-z]/g, "");
        if (/^(C|Si|Mn|P|S|Cr|Mo|Ni|Cu|Al|Nb|Ti|V|B|N|H|O)$/.test(key) && isFinite(Number(v))) out[key] = Number(v);
        if (/mass|weight|钢水|质量/i.test(k) && isFinite(Number(v))) out.mass = Number(v);
        if (/temp|温度/i.test(k) && isFinite(Number(v))) out.temp = Number(v);
      }
    };
    walk(j);
    if (Object.keys(out).length) return out;
  } catch (e) {}
  const elRe = /\b(C|Si|Mn|P|S|Cr|Mo|Ni|Cu|Al|Nb|Ti|V|B|N|H|O)\b\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)/g;
  let m;
  while ((m = elRe.exec(t))) out[m[1]] = Number(m[2]);
  const mass = t.match(/(?:钢水|钢液|质量|装入量|重量)\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:t|吨)?/i);
  if (mass) out.mass = Number(mass[1]);
  const temp = t.match(/(?:温度|进站温度)\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)/);
  if (temp) out.temp = Number(temp[1]);
  // 模拟器总结页：初始/最终质量、运行时间、总成本
  const fin = t.match(/(?:最终的?钢铁质量|成品质量|出钢量|final[_ ]?mass)\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)/i);
  if (fin) out.mass_final = Number(fin[1]);
  const ini = t.match(/(?:initial[_ ]?mass|初始质量|装入量)\s*[:：=]?\s*([0-9]+(?:\.[0-9]+)?)/i);
  if (ini) out.mass_initial = Number(ini[1]);
  const tm = t.match(/(?:时间|time)\s*[:：=]?\s*(\d{1,2})\s*[Hh时:：]\s*[:：]?\s*(\d{2})/);
  if (tm) out.time_min = Number(tm[1]) * 60 + Number(tm[2]);
  const ct = t.match(/(?:总成本|成本|cost)\s*[:：=]?\s*\$?\s*([0-9]+(?:\.[0-9]+)?)/i);
  if (ct) out.cost_per_t = Number(ct[1]);
  return out;
}

function openSmImport() {
  $("#modal-root").innerHTML = `<div class="modal-mask" id="mask"><div class="modal">
    <div class="card-h"><h3>导入模拟器数据</h3><div class="spacer"></div><button class="icon-btn" id="m-close">×</button></div>
    <div class="card-b">
      <div class="hint">把模拟器摘要里的成分、钢水质量、温度粘贴进来。支持 <code>C 0.38 Si 0.28 Mn 1.40</code> 这种格式，也支持 JSON；只填能识别的项，其余保留当前值。</div>
      <textarea id="sm-import-text" rows="10" placeholder="C 0.38&#10;Si 0.28&#10;Mn 1.40&#10;Cr 1.90&#10;Mo 0.16&#10;钢水 93 t&#10;温度 1582"></textarea>
      <div id="sm-import-msg" class="hint"></div>
    </div>
    <div class="foot"><button class="btn" id="sm-import-cancel">取消</button><button class="btn primary" id="sm-import-run">解析并填入</button></div>
  </div></div>`;
  const close = () => $("#modal-root").innerHTML = "";
  $("#m-close").onclick = close; $("#sm-import-cancel").onclick = close;
  $("#mask").onclick = (e) => { if (e.target.id === "mask") close(); };
  $("#sm-import-run").onclick = () => {
    const parsed = parseSimulatorText($("#sm-import-text").value);
    const EL_KEYS = ["C","Si","Mn","P","S","Cr","Mo","Ni","Cu","Al","Nb","Ti","V","B","N","H","O"];
    const keys = Object.keys(parsed).filter((k) => EL_KEYS.includes(k));
    if (!keys.length && parsed.mass == null && parsed.temp == null) {
      $("#sm-import-msg").textContent = "没识别到成分。至少写一行，例如 C 0.38。";
      return;
    }
    const sc = S.smcalc;
    keys.forEach((k) => { if (parsed[k] != null) sc.initial[k] = parsed[k]; });
    if (parsed.mass_final != null) sc.mass = Math.round(parsed.mass_final);
    else if (parsed.mass != null) sc.mass = Math.round(parsed.mass);
    if (parsed.temp != null) sc.temp = parsed.temp;
    sc.sim = {
      time_min: parsed.time_min ?? null,
      cost_per_t: parsed.cost_per_t ?? null,
      mass: parsed.mass_final ?? parsed.mass ?? null,
    };
    sc.result = null;
    close();
    viewRefine();
    toast("已导入 " + keys.length + " 个元素" + (parsed.mass != null ? " + 钢水量" : "") + (parsed.temp != null ? " + 温度" : ""));
  };
}

async function viewRefine() {
  await ensureRuns();
  const sc = S.smcalc;
  if (!sc.initial) {
    const pe = S.plan?.data?.summary?.final_eaf || S.wizard.eaf?.summary?.final;
    sc.initial = smPreFromEaf({ final: pe || {} });
  }
  if (!sc.mass) sc.mass = Math.round(S.heat?.sm_mass || S.heat?.mass || 90);
  const eafRuns = (S.runs || []).filter((r) => runEafRef(r));
  const fields = smInitialFields();
  const scInit = sc.initial || {};
  $("#view").innerHTML = `
  <div class="page-head"><div><h1>二次精炼</h1><p>按模拟器实际界面组织：先选“去”的工位，再按模拟器合金清单加料，实时核算 17 元素和成本。不再按手册章节分页。</p></div>
    <div class="spacer"></div><button class="btn sm" id="sm-import">导入模拟器数据</button><span class="badge neutral">模拟器工位 · 21 种合金</span></div>
  ${renderHeatFlow("refine")}
  ${renderSmSpecStrip()}
  <div class="card">
    <div class="card-h"><h3>炉次与精炼路线</h3><span class="sub">选择 EAF 炉次 → 选择去向 → 加合金</span><div class="spacer"></div><span class="badge neutral">${sc.route.length} 个工位</span></div>
    <div class="card-b">
      <div class="form-grid wiz-form">
        <label class="field"><span>EAF 炉次</span>
          <select id="sm-eaf-pick"><option value="">— 手动输入成分 —</option>
            ${eafRuns.map((r) => `<option value="${r.id}" ${r.id === sc.eafRunId ? "selected" : ""}>${esc(r.name)} · ${gradeShort(r.grade)}</option>`).join("")}
          </select>
        </label>
        <label class="field"><span>钢水质量 t（整吨）</span><input id="sm-mass" class="mono" type="number" min="40" max="120" step="1" value="${sc.mass}"></label>
        <label class="field"><span>进站温度 °C</span><input id="sm-temp" class="mono" type="number" min="1500" max="1700" step="1" value="${sc.temp}"></label>
      </div>
      <div class="sm-dest-row">
        <label class="field"><span>去</span>
          <select id="sm-dest">${SM_DESTS.map((d) => `<option value="${d.key}">${d.name}</option>`).join("")}</select>
        </label>
        <button class="btn primary" id="sm-add-dest">加入路线</button>
        <button class="btn" id="sm-quick-route">常用路线：氩站 → 脱气 → CAS-OB → 钢包炉 → 小方坯</button>
      </div>
      <div class="sm-route">${smRouteChips()}</div>
      <div class="hr"></div>
      <div class="small muted" style="margin-bottom:6px">脱碳/脱气后装入成分（选 EAF 炉次自动折算；C 按脱气终点，Si/Mn/Cr 已扣吹氧损失，可手动改）</div>
      <div class="wiz-init-grid">${fields.map(([k, label]) => `<label><span>${label}</span><input class="mono sm-init" data-el="${k}" type="number" step="0.0001" value="${Number(scInit[k] ?? 0).toFixed(4)}"></label>`).join("")}</div>
    </div>
  </div>

  <div class="sm-layout mt12">
    <div class="card">
      <div class="card-h"><h3>合金添加</h3><span class="sub">模拟器清单 · 按 10 kg 档</span><div class="spacer"></div><span class="badge neutral">${(S.boot.additives_sm || []).length} 种</span></div>
      <div class="card-b" style="padding:0">${renderSmAlloyTable()}</div>
    </div>
    <div>
      <div class="card">
        <div class="card-h"><h3>成分与成本</h3><span class="sub">17 元素判定</span><div class="spacer"></div><button class="btn sm primary" id="sm-calc">计算成分与成本</button></div>
        <div class="card-b" id="sm-result">${renderSmResult()}</div>
      </div>
      <div class="card mt12">
        <div class="card-h"><h3>工位操作提示</h3><span class="sub">按路线顺序</span></div>
        <div class="card-b" id="sm-stations">${renderSmStationNotes()}</div>
      </div>
    </div>
  </div>`;
  bindSmCalc();
  updateSmTotals();
}

function updateSmTotals() {
  const sc = S.smcalc;
  const adds = S.boot.additives_sm || [];
  let kg = 0, cost = 0;
  adds.forEach((a) => {
    const q = Number(sc.additions[a.key] || 0);
    kg += q; cost += q * a.price / 1000;
    const cell = document.querySelector(`.sm-cost[data-key="${a.key}"]`);
    if (cell) cell.textContent = "$" + f(q * a.price / 1000, 1);
  });
  const k = $("#sm-add-total-kg"); if (k) k.textContent = f(kg, 0) + " kg";
  const c = $("#sm-add-total-cost"); if (c) c.textContent = money(cost);
}

function bindSmCalc() {
  const sc = S.smcalc;
  const pick = $("#sm-eaf-pick");
  if (pick) pick.onchange = () => {
    const run = (S.runs || []).find((x) => x.id === pick.value);
    sc.eafRunId = run ? run.id : null;
    if (run) {
      const ref = runEafRef(run);
      sc.initial = smPreFromEaf(ref);
      if (ref.tap_mass) sc.mass = Math.round(ref.tap_mass);
    }
    sc.result = null;
    sc.sim = null;
    viewRefine();
  };
  const add = $("#sm-add-dest");
  if (add) add.onclick = () => {
    const k = $("#sm-dest").value;
    if (k && !sc.route.includes(k)) sc.route.push(k);
    viewRefine();
  };
  const quick = $("#sm-quick-route");
  if (quick) quick.onclick = () => {
    sc.route = ["argon", "tank", "casob", "lf", "billet"];
    viewRefine();
  };
  document.querySelectorAll("[data-rm]").forEach((b) => b.onclick = () => {
    sc.route = sc.route.filter((k) => k !== b.dataset.rm);
    viewRefine();
  });
  document.querySelectorAll(".sm-add").forEach((input) => input.oninput = () => {
    const v = Math.max(0, Math.round((parseFloat(input.value) || 0) / 10) * 10);
    const k = input.dataset.key;
    if (v > 0) sc.additions[k] = v; else delete sc.additions[k];
    updateSmTotals();
  });
  const imp = $("#sm-import");
  if (imp) imp.onclick = openSmImport;
  const calc = $("#sm-calc");
  if (calc) calc.onclick = async () => {
    sc.mass = Math.max(40, Math.min(120, parseFloat($("#sm-mass")?.value || "90")));
    sc.temp = parseFloat($("#sm-temp")?.value || "1565");
    document.querySelectorAll(".sm-init").forEach((i) => { sc.initial[i.dataset.el] = parseFloat(i.value) || 0; });
    const additions = {};
    document.querySelectorAll(".sm-add").forEach((i) => {
      const v = parseFloat(i.value) || 0;
      if (v > 0) additions[i.dataset.key] = v;
    });
    setBusy(calc, true);
    try {
      const r = await api("/api/sm/evaluate", "POST", { mass: sc.mass, initial: sc.initial, additions });
      sc.result = r;
      $("#sm-result").innerHTML = renderSmResult();
    } catch (e) { toast(e.message, true); }
    setBusy(calc, false);
  };
}

function tabForm(title, sub, fields, btn, resultInit) {
  return `<div class="calc-layout">
    <div class="card"><div class="card-h"><h3>${title}</h3><span class="sub">${sub}</span></div>
      <div class="card-b calc-form">${fields}<button class="btn primary" id="r-run">${btn}</button></div></div>
    <div id="r-result">${resultInit || '<div class="card"><div class="empty">填写参数后计算。</div></div>'}</div>
  </div>`;
}

function renderTab() {
  const t = S.tab;
  const h = S.heat || {};
  const dyn = h.dynamic || S.dyn?.state || {};
  const comp = dyn.comp || h.charge?.composition || h.initial || {};
  const mass = Math.round(h.mass || dyn.mass || (t === "slag" ? 90 : 250));
  const p = S.plan?.data?.summary || {};
  const flux = p.fluxes || [];
  const sil = heatSilica();
  const planFluxOk = planFresh() && Number(S.plan.data?.mass) === mass;
  const fluxVal = (name, def) => {
    if (!planFluxOk) return +(def * mass / 90).toFixed(2);
    const x = flux.find((f) => String(f.name || "").includes(name));
    return x ? +(Number(x.mass || 0) / 1000).toFixed(2) : def;
  };
  let html = "";
  if (t === "alloy") {
    html = tabForm("合金添加量（9.1）", "式 9-1 ~ 9-3 · 中间合金 / 回收率", `
      ${field("钢水质量 t", "y-mass", mass)}
      <label class="field"><span>元素符号</span><input class="mono" id="y-el" type="text" value="Mn"></label>
      ${field("当前含量 %", "y-cur", comp.Mn != null ? +Number(comp.Mn).toFixed(4) : 0.12)}
      ${field("目标含量 %", "y-tgt", comp.Mn != null ? Math.max(Number(comp.Mn), 1.4) : 1.4)}
      ${field("中间合金中元素含量 %", "y-cont", 76.5)}
      ${field("回收率 %", "y-rec", 95)}`, "计算中间合金添加量");
  } else if (t === "deox_ladle") {
    const reagents = S.boot.deox_reagents || {};
    html = tabForm("钢包脱氧", "9.2 · 按 O 降量选脱氧剂", `
      ${field("钢水质量 t", "dl-mass", mass)}
      ${field("初始氧 ppm", "dl-o", comp.O != null ? Math.round(comp.O * 10000) : 450)}
      ${field("目标氧 ppm", "dl-ot", 20)}
      <label class="field"><span>脱氧剂</span><select id="dl-reagent">${Object.entries(reagents).map(([k, x]) => `<option value="${k}">${esc(x.name)} · $${x.price}/t</option>`).join("")}</select></label>
      <div class="hint" id="dl-info"></div>`, "计算脱氧剂加入量");
  } else if (t === "deox") {
    html = tabForm("铝脱氧", "式 9-4 ~ 9-8", `
      ${field("钢水质量 t", "d-mass", mass)}
      ${field("初始氧 ppm", "d-o", comp.O != null ? Math.round(comp.O * 10000) : 450)}
      ${field("目标残铝 %", "d-al", 0.04)}
      ${field("铝含量 %", "d-alc", 98)}
      ${field("铝回收率 %", "d-rec", 60)}`, "计算加铝量");
  } else if (t === "desulf") {
    html = tabForm("脱硫渣量与时间", "式 9-18 ~ 9-21", `
      ${field("钢水质量 t", "s-mass", mass)}
      ${field("初始硫 %", "s-s0", comp.S != null ? +Number(comp.S).toFixed(4) : 0.008)}
      ${field("目标硫 %", "s-sa", 0.002)}
      ${field("硫分配比 Ls", "s-ls", 500)}
      ${field("渣量 t（算时间用）", "s-ws", 2)}
      ${field("搅拌功率 ε W/t", "s-eps", 100)}`, "计算");
  } else if (t === "decarb") {
    html = tabForm("RH 脱碳", "式 9-13 ~ 9-15", `
      ${field("钢水质量 t", "k-mass", mass)}
      ${field("初始碳 %", "k-ci", comp.C != null ? +Number(comp.C).toFixed(4) : 0.045)}
      ${field("目标碳 %", "k-cf", p.c_anchors?.degas ?? 0.002)}
      ${field("平衡碳 %", "k-ceq", 0.0015)}
      ${field("循环流量 Q kg/min", "k-q", 80000)}
      ${field("传质系数 q m³/min", "k-q2", 18)}`, "计算脱碳时间");
  } else if (t === "hydrogen") {
    html = tabForm("除氢", "式 9-23 ~ 9-25", `
      ${field("初始氢 ppm", "h-hi", 5)}
      ${field("目标氢 ppm", "h-hf", 1)}
      ${field("炉气氢分压 atm", "h-p", 0.1)}
      ${field("kH min⁻¹（RH=0.13）", "h-k", 0.13)}
      ${field("氩气流量 Nm³/min", "h-ar", 3)}`, "计算除氢时间");
  } else if (t === "stir") {
    html = tabForm("钢包搅拌功率", "式 9-26", `
      ${field("氩气流量 Nm³/min", "t-v", 1)}
      ${field("钢水温度 °C", "t-temp", dyn.temp || 1600)}
      ${field("钢水质量 t", "t-mass", mass)}
      ${field("透气砖深度 H m", "t-h", 2.5)}
      ${field("液面压力 atm", "t-p", 1)}`, "计算功率密度");
  } else if (t === "heat") {
    html = tabForm("钢包炉电加热", "式 9-27 ~ 9-33", `
      ${field("钢水质量 t", "e-mass", mass)}
      ${field("升温 ΔT °C", "e-dt", 15)}
      ${field("功率 kW", "e-p", 20000)}
      ${field("电极效率 %", "e-eta", 55)}`, "计算加热时间");
  } else if (t === "slag") {
    html = tabForm("EAF 造渣 / 碱度", "EAF 5.5–5.6 · CaO / SiO₂", `
      ${field("钢水质量 t", "g-mass", mass)}
      <div class="hint" style="margin:-2px 0 2px">${sil.fallback ? "未载入炉次，先按默认 90 t 参考炉料（68 t 捆包 + 21 t DRI + 1 t 炉尘）算。" : ""}当前炉料 SiO₂ 来源：Si 氧化 ${f(sil.siOxPct / 100 * mass * 1000 * 60 / 28, 0)} kg + DRI 脉石 ${f(sil.gangue, 0)} kg。换炉料请先回「炉料配比」，这里会自动跟着变。</div>
      ${field("石灰 t", "g-lime", S.slag.lime ?? fluxVal("石灰", 1.15))}
      ${field("白云石 t", "g-dol", S.slag.dol ?? fluxVal("白云石", 1.41))}
      ${field("萤石 t", "g-flu", S.slag.flu ?? fluxVal("氟石", 0.05))}
      ${field("目标碱度", "g-b", S.slag.b ?? 1.70)}
      ${field("目标 MgO %", "g-mgo", S.slag.mgo ?? 8.8)}
      ${field("目标 FeO %", "g-feo", S.slag.feo ?? 45)}`, "计算碱度 / MgO / FeO");
  } else if (t === "clean") {
    html = tabForm("钢材洁净度（9.8）", "表 9-2 · Al₂O₃ 上浮时间", `
      ${field("初始溶解氧 ppm", "cl-o", comp.O != null ? Math.max(30, Math.round(comp.O * 10000)) : 100)}
      <label class="field"><span>搅拌</span><select id="cl-stir"><option value="1">搅拌</option><option value="0">不搅拌</option></select></label>
      <label class="field"><span>目标洁净度</span><select id="cl-level"><option value="very">非常低</option><option value="low">低（−20%）</option><option value="medium">中等（−40%）</option></select></label>`, "估算夹杂物上浮时间");
  }
  $("#tab-body").innerHTML = html;
  $("#r-run").onclick = () => runTab(t);
  if (t === "slag") {
    // 用户一改渣料，就标记为“手工值”，之后进出页面不再被自动推荐覆盖
    const bindSlag = (id, key) => {
      const el = $("#" + id);
      if (!el) return;
      el.oninput = () => {
        S.slag[key] = parseFloat(el.value);
        S.slag.manual = true;
      };
    };
    bindSlag("g-lime", "lime"); bindSlag("g-dol", "dol"); bindSlag("g-flu", "flu");
    bindSlag("g-b", "b"); bindSlag("g-mgo", "mgo"); bindSlag("g-feo", "feo");
  }
  if (t === "deox_ladle") setTimeout(bindDeoxLadleInfo, 0);
  // 造渣页由 autoSlagRecalc 先按当前炉料算推荐渣料，再触发计算，避免与默认值竞争
  if (t !== "slag") setTimeout(() => runTab(t), 30);
}

function field(label, id, val) {
  return `<label class="field"><span>${label}</span><input class="mono" id="${id}" type="number" step="any" value="${val}"></label>`;
}

function val(id) { return parseFloat($("#" + id).value); }

function bindDeoxLadleInfo() {
  const sel = $("#dl-reagent");
  if (!sel) return;
  const update = () => {
    const r = (S.boot.deox_reagents || {})[sel.value];
    const box = $("#dl-info");
    if (!r || !box) return;
    const comp = Object.entries(r.comp).map(([e, v]) => `${e} ${v}%`).join(" + ");
    const rec = Object.entries(r.rec).map(([e, v]) => `${e} ${v}%`).join("，");
    box.innerHTML = `<b>${esc(r.name)}</b>：${esc(comp)}；回收率 ${esc(rec)}。${esc(r.note || "")}`;
  };
  sel.onchange = update;
  update();
}

async function runTab(t) {
  const btn = $("#r-run"); setBusy(btn, true);
  try {
    let r, body;
    if (t === "alloy") {
      const w = val("y-mass"), cur = val("y-cur"), tgt = val("y-tgt");
      const cont = val("y-cont"), rec = val("y-rec");
      const el = ($("#y-el")?.value || "X").trim();
      const delta = tgt - cur;
      const need = delta > 0 && cont > 0 && rec > 0 ? (delta / 100 * w * 1000) / (cont / 100 * rec / 100) : 0;
      const rounded = need > 0 ? Math.ceil(need / 10) * 10 : 0;
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>合金添加量（9.1）</h3><span class="sub">中间合金 ${cont}% ${el} · 回收率 ${rec}%</span></div><div class="card-b">
        <div class="grid g2"><div class="result-box"><div class="big">${f(need, 1)}<small> kg</small></div><div class="note">理论加入量</div></div>
        <div class="result-box"><div class="big">${rounded ? f(rounded, 0) : "—"}<small> kg</small></div><div class="note">按 10 kg 档取整</div></div></div>
        <div class="mt12">${kv("目标增量", f(Math.max(delta, 0), 4) + " % " + el)}${kv("钢水质量", f(w, 0) + " t")}${kv("中间合金含量", cont + " %")}${kv("回收率", rec + " %")}</div>
        <div class="formula">m = Δ%${el} × W / (%${el} × 回收率)</div>
        ${delta <= 0 ? '<div class="warn-item bad mt12"><span class="ico">!</span><span>目标含量不高于当前含量：合金只能增加元素，不能降低；请先吹氧/换料或调整目标。</span></div>' : ""}
        <div class="hint mt12">手册例：250 t 钢水 Mn 0.12% → 1.4%，HCFeMn 含 Mn 76.5%、回收率 95%，理论约 4.4 t。实际还要看 C 夹带和温降。</div>
      </div></div>`;
    } else if (t === "clean") {
      const o = Math.max(1, val("cl-o"));
      const table = [[600, 14, 5], [100, 47, 15], [30, 108, 36]];
      let base = table[2];
      if (o >= 600) base = table[0];
      else if (o > 30) {
        for (let i = 0; i < table.length - 1; i++) {
          const a = table[i], b = table[i + 1];
          if (o <= a[0] && o >= b[0]) {
            const k = (o - b[0]) / (a[0] - b[0]);
            base = [o, b[1] + (a[1] - b[1]) * k, b[2] + (a[2] - b[2]) * k];
            break;
          }
        }
      }
      const stir = $("#cl-stir")?.value === "1";
      const level = $("#cl-level")?.value || "very";
      const factor = level === "low" ? 0.8 : level === "medium" ? 0.6 : 1.0;
      const mins = base[stir ? 2 : 1] * factor;
      const levelCn = level === "low" ? "低" : level === "medium" ? "中等" : "非常低";
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>钢材洁净度（9.8）</h3><span class="sub">Al₂O₃ 上浮时间估算</span></div><div class="card-b">
        <div class="result-box"><div class="big">≈${f(mins, 0)}<small> min</small></div><div class="note">初始 O ${f(o, 0)} ppm · ${stir ? "搅拌" : "不搅拌"} · 目标${levelCn}夹杂物</div></div>
        <div class="mt12">${kv("初始溶解氧", f(o, 0) + " ppm")}${kv("搅拌", stir ? "是（可缩短约 60–65%）" : "否")}${kv("目标级别", levelCn)}</div>
        <div class="formula">表 9-2：O 600 ppm → 14 / 5 min；100 ppm → 47 / 15 min；30 ppm → 108 / 36 min（不搅拌 / 搅拌）</div>
        <div class="hint mt12">洁净度不是独立加入量：铝脱氧时一次算准，避免后续补铝；补铝越晚，生成的 Al₂O₃ 越细、越难上浮。目标“低”约减 20% 时间，“中等”约减 40%。</div>
      </div></div>`;
    } else if (t === "deox_ladle") {
      body = { mass: val("dl-mass"), o_ppm: val("dl-o"), target_o: val("dl-ot"), reagent: $("#dl-reagent").value };
      r = await api("/api/refine/deox_ladle", "POST", body);
      const siHigh = r.si_pickup_pct >= 0.005;
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>钢包脱氧</h3><span class="sub">${esc(r.reagent_name)} · 9.2</span></div><div class="card-b">
        <div class="grid g3"><div class="result-box"><div class="big">${f(r.reagent_round_kg, 0)}<small> kg</small></div><div class="note">按 10 kg 档加入</div></div>
        <div class="result-box"><div class="big">${f(r.o_after_ppm, 1)}<small> ppm</small></div><div class="note">脱氧后 O（目标 ${body.target_o} ppm）</div></div>
        <div class="result-box"><div class="big">${money(r.cost)}</div><div class="note">脱氧剂成本</div></div></div>
        <div class="mt12">${kv("理论加入量", f(r.reagent_kg, 1) + " kg")}${kv("脱除氧", f(r.o_remove_kg, 2) + " kg")}${kv("生成氧化物", f(r.oxide_kg, 1) + " kg")}${kv("化学升温", "+" + f(r.heat_C, 1) + " °C")}${kv("残余 Al", f(r.residual_al_pct, 4) + " %")}${kv("带入 Si", f(r.si_pickup_pct, 4) + " %")}${r.ca_pickup_pct ? kv("带入 Ca", f(r.ca_pickup_pct, 4) + " %") : ""}</div>
        <div class="formula">Al：2Al + 3O → Al₂O₃（54/48=1.125）；Si：Si + 2O → SiO₂；Ca：Ca + O → CaO</div>
        ${siHigh ? `<div class="warn-item mt12"><span class="ico">!</span><span>这种脱氧剂会带入约 ${f(r.si_pickup_pct, 4)}% Si；对 Si 敏感的钢种改用铝块/铝线。</span></div>` : ""}
        <div class="hint mt12">${esc(r.note)}</div>
      </div></div>`;
    } else if (t === "deox") {
      body = { mass: val("d-mass"), o_ppm: val("d-o"), target_al: val("d-al"), al_content: val("d-alc"), recovery: val("d-rec") };
      r = await api("/api/refine/deox", "POST", body);
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>加铝量</h3><span class="sub">98% Al 块</span></div><div class="card-b">
        <div class="result-box"><div class="big">${f(r.alloy_mass_kg, 1)}<small> kg</small></div><div class="note">需 98% 铝块（回收率 ${body.recovery}%）</div></div>
        <div class="mt12">${kv("脱氧需铝", f(r.al_deox_pct, 4) + " %")}${kv("目标残铝", f(r.al_target_pct, 3) + " %")}${kv("总铝需求", f(r.al_total_pct, 4) + " %")}${kv("与氧反应铝", f(r.al_reacted_kg, 1) + " kg")}${kv("化学升温", "+" + f(r.heat_C, 1) + " °C")}</div>
        <div class="formula">m = (54/48 × [%O] + [%Al]目标) × W / (%Al × 回收率)</div></div></div>`;
    } else if (t === "desulf") {
      body = { mass: val("s-mass"), s0: val("s-s0"), s_aim: val("s-sa"), Ls: val("s-ls"), slag_t: val("s-ws"), epsilon: val("s-eps") };
      r = await api("/api/refine/desulf", "POST", body);
      const slag = r.slag, kin = r.kinetics;
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>脱硫方案</h3><span class="sub">平衡渣量 + 动力学时间</span></div><div class="card-b">
        <div class="grid g2"><div class="result-box"><div class="big">${f(slag.slag_t, 2)}<small> t 渣</small></div><div class="note">达到 ${body.s_aim}% S 的最低渣量</div></div>
        <div class="result-box"><div class="big">${kin.time_min != null ? f(kin.time_min, 1) : "—"}<small> min</small></div><div class="note">ε=${body.epsilon} W/t，kS=${kin.ks ?? "—"} min⁻¹</div></div></div>
        <div class="mt12">${kv("平衡硫", (kin.equilibrium_s ?? "—") + " %")}${kv("渣/钢比 Ws/Wm", f((body.slag_t || 0) / body.mass, 4))}${kv("目标硫", body.s_aim + " %")}</div>
        <div class="formula">Ws = (Wm / Ls) × ([%S]0 − [%S]aim) / [%S]aim</div>
        ${kin.error ? `<div class="warn-item bad mt12"><span class="ico">!</span><span>${kin.error}</span></div>` : ""}
      </div></div>`;
    } else if (t === "decarb") {
      body = { mass: val("k-mass"), c_i: val("k-ci"), c_f: val("k-cf"), c_eq: val("k-ceq"), Q: val("k-q"), q: val("k-q2") };
      r = await api("/api/refine/decarb", "POST", body);
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>脱碳时间</h3><span class="sub">RH 循环脱气</span></div><div class="card-b">
        <div class="result-box"><div class="big">${r.time_min != null ? f(r.time_min, 1) : "—"}<small> min</small></div><div class="note">kc = ${r.kc} min⁻¹ · Vb = ${r.Vb ?? "—"} m³</div></div>
        <div class="mt12">${kv("初始碳", body.c_i + " %")}${kv("目标碳", body.c_f + " %")}${kv("平衡碳", body.c_eq + " %")}</div>
        <div class="formula">[%C]f = [%C]eq + ([%C]i − [%C]eq) · exp(−kc·t)</div>
        ${r.error ? `<div class="warn-item bad mt12"><span class="ico">!</span><span>${r.error}</span></div>` : ""}
        <div class="hint mt12">手册例题给出 kc = 0.164 min⁻¹、t ≈ 27 min；按公式 9-15 复算可能略有差异，可用 kc 覆盖值校准模拟器。</div>
      </div></div>`;
    } else if (t === "hydrogen") {
      body = { hi: val("h-hi"), hf: val("h-hf"), p: val("h-p"), kH: val("h-k"), argon: val("h-ar") };
      const eq = await api("/api/refine/hydrogen", "POST", body);
      const heq = eq.equilibrium.h_ppm;
      const kin = await api("/api/refine/hydrogen", "POST", { ...body, heq });
      r = kin;
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>除氢</h3><span class="sub">Sieverts + 传质动力学</span></div><div class="card-b">
        <div class="grid g2"><div class="result-box"><div class="big">${f(heq, 2)}<small> ppm</small></div><div class="note">p(H₂)=${body.p} atm 的平衡氢</div></div>
        <div class="result-box"><div class="big">${kin.kinetics.time_min != null ? f(kin.kinetics.time_min, 1) : "—"}<small> min</small></div><div class="note">kH=${body.kH} min⁻¹</div></div></div>
        <div class="mt12">${kv("罐式脱气 kH（按氩流量）", f(eq.kH_tank.kH, 4) + " min⁻¹")}${kv("目标氢", body.hf + " ppm")}</div>
        <div class="formula">[H]eq = 25.6 × √p(H₂)　|　t = −(1/kH)·ln((Hf−Heq)/(Hi−Heq))</div>
      </div></div>`;
    } else if (t === "stir") {
      body = { V: val("t-v"), temp: val("t-temp"), mass: val("t-mass"), H: val("t-h"), P0: val("t-p") };
      r = await api("/api/refine/stir", "POST", body);
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>搅拌功率密度</h3><span class="sub">${r.regime}</span></div><div class="card-b">
        <div class="result-box"><div class="big">${f(r.epsilon, 1)}<small> W/t</small></div><div class="note">ε > 70 W/t 时脱硫速率常数快速上升</div></div>
        <div class="formula">ε = 14.23 × (V·T / M) × log₁₀((1+H) / (1.48·P₀))</div>
      </div></div>`;
    } else if (t === "heat") {
      body = { mass: val("e-mass"), dT: val("e-dt"), power: val("e-p"), eta: val("e-eta") / 100 };
      r = await api("/api/refine/heat", "POST", body);
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>电加热时间</h3><span class="sub">LF 满功率约 3°C/min</span></div><div class="card-b">
        <div class="result-box"><div class="big">${f(r.minutes, 1)}<small> min</small></div><div class="note">耗电约 ${Math.round(r.energy_kwh).toLocaleString()} kWh</div></div>
        <div class="formula">Δt = m·Cp·ΔT / (η·P)　Cp = 0.22 kWh/(t·°C)</div>
      </div></div>`;
    } else if (t === "slag") {
      const hs = heatSilica();
      body = { mass: val("g-mass"), si: hs.siOxPct, sio2_gangue: hs.gangue,
               mix: hs.mix, si_retained: hs.siRet,
               lime: val("g-lime"), dolomite: val("g-dol"), fluorspar: val("g-flu"),
               basicity: val("g-b"), mgo: val("g-mgo"), feo: val("g-feo") };
      r = await api("/api/refine/slag", "POST", body);
      const over = r.basicity > body.basicity + 0.01;
      const near = Math.abs(r.basicity - body.basicity) <= 0.01;
      const mgBad = r.mgo_pct < 8 || r.mgo_pct > 12;
      $("#r-result").innerHTML = `<div class="card"><div class="card-h"><h3>渣碱度 / MgO / FeO</h3><span class="sub">CaO / SiO₂ · EAF 5.5–5.6</span></div><div class="card-b">
        <div class="grid g4"><div class="result-box"><div class="big">${f(r.basicity, 2)}</div><div class="note">碱度（目标 ${body.basicity}）${near ? " · 已达标" : over ? " · 偏高" : ""}</div></div>
        <div class="result-box"><div class="big ${mgBad ? "text-bad" : ""}">${f(r.mgo_pct, 1)}<small>%</small></div><div class="note">MgO（8–12%）${mgBad ? " · 不合格" : " · 合格"}</div></div>
        <div class="result-box"><div class="big">${f(r.feo_pct, 1)}<small>%</small></div><div class="note">FeO（10–50%，按目标）</div></div>
        <div class="result-box"><div class="big">${f(r.slag_kg / 1000, 2)}<small> t</small></div><div class="note">渣量</div></div></div>
        <div class="mt12">
          ${kv("SiO₂：Si 氧化", f(r.sio2_from_si_kg, 1) + " kg")}
          ${kv("SiO₂：DRI 脉石", f(r.sio2_gangue_kg, 1) + " kg")}
          ${kv("SiO₂：渣料带入", f(r.sio2_from_flux_kg, 1) + " kg")}
          ${kv("SiO₂ 总量", f(r.sio2_total_kg, 1) + " kg")}
          ${kv("CaO 总量", f(r.cao_kg, 1) + " kg")}
          ${kv("MgO / FeO 质量", f(r.mgo_kg, 0) + " / " + f(r.feo_kg, 0) + " kg")}
        </div>
        <div class="formula">碱度 = %CaO / %SiO₂（1.5–2.5）；MgO 8–12%；FeO 10–50%</div>
        ${Array.isArray(r.mg_curve) && r.mg_curve.length ? `<div class="hint mt8"><b>为什么吹氧时 MgO 会降：</b>氧把 Fe/Si 氧化成 FeO、SiO₂ 进入渣中，渣量变大，白云石带来的 MgO 被稀释。同样渣料下：${r.mg_curve.filter(x => [20, 30, 37, 45].includes(x.feo)).map(x => `FeO ${x.feo}% → MgO ${f(x.mgo_pct, 1)}%`).join("；")}。MgO 低于 8% 就补白云石，不要靠多加石灰。</div>` : ""}
        ${r.recommend ? `<div class="hint mt12"><b>推荐渣料（一次加入）：</b>石灰 ${f(r.recommend.lime_kg, 0)} kg + 白云石 ${f(r.recommend.dolomite_kg, 0)} kg + 萤石 ${f(r.recommend.fluorspar_kg, 0)} kg；预测碱度 ${f(r.recommend.basicity, 2)}、MgO ${f(r.recommend.mgo_pct, 1)}%、FeO ${f(r.recommend.feo_pct, 1)}%、渣量 ${f(r.recommend.slag_kg, 0)} kg。</div>` : ""}
        <div class="hint mt8">实炉校准 实炉校准：石灰 1160 + 白云石 1410 + 萤石 50 kg（当时分两批加入），终渣碱度 1.698、MgO 8.186%、FeO 37.117%。按本模型一次加入复算，推荐值与实炉相差 <1%。</div>
      </div></div>`;
    }
  } catch (e) { toast(e.message, true); }
  setBusy(btn, false);
}

function kv(k, v) { return `<div class="kv"><span>${k}</span><b>${v}</b></div>`; }

/* ---------------- knowledge base ---------------- */
async function viewKB() {
  const sec = await api("/api/kb/sections").catch(() => ({ sections: [] }));
  const groups = {};
  (sec.sections || []).forEach((s) => { (groups[s.doc] = groups[s.doc] || []).push(s); });
  $("#view").innerHTML = `
  <div class="page-head"><div><h1>手册知识库</h1><p>两份 steeluniversity 操作手册的全文分块，带页码引用。BM25 检索，中文按字二元组切分。</p></div><div class="spacer"></div>
    <span class="badge neutral">122 块 · 120 页</span></div>
  ${renderHeatFlow("kb")}
  <div class="grid" style="grid-template-columns:minmax(0,1fr) 300px">
    <div class="card">
      <div class="card-b">
        <div class="kb-search"><input id="kb-q" type="text" placeholder="例如：铝脱氧  脱硫渣量  料斗体积  液相线温度"><button class="btn primary" id="kb-go">检索</button></div>
        <div class="tag-line mt8"><span class="badge neutral">EAF 手册</span><span class="badge neutral">SM 手册</span><span class="small muted">支持元素符号与中文互查</span></div>
      </div>
      <div id="kb-results"><div class="empty">输入关键词检索手册原文。</div></div>
    </div>
    <div class="card">
      <div class="card-h"><h3>按章节浏览</h3><span class="sub">点击填入检索</span></div>
      <div class="card-b section-list">
        ${Object.entries(groups).map(([doc, arr]) => `<div class="small muted" style="padding:7px 8px 3px;letter-spacing:.08em">${doc === "eaf" ? "EAF 电弧炉" : "SM 二次炼钢"}</div>` + arr.map((s) => `<button data-sec="${esc(s.section)}"><span>${s.pages[0]}–${s.pages[s.pages.length - 1]}p</span>${esc(s.section)}</button>`).join("")).join("")}
      </div>
    </div>
  </div>`;
  const search = async () => {
    const q = $("#kb-q").value.trim();
    if (!q) return;
    $("#kb-results").innerHTML = '<div class="empty">检索中…</div>';
    const r = await api("/api/kb/search?q=" + encodeURIComponent(q) + "&k=8");
    $("#kb-results").innerHTML = r.results.length ? r.results.map((x) => `<div class="kb-hit">
      <div class="meta"><span class="badge form">${x.doc === "eaf" ? "EAF" : "SM"}</span><span>${x.doc_title}</span><span>第 ${x.page} 页</span>${x.section ? `<span>${esc(x.section)}</span>` : ""}<span class="mono" style="margin-left:auto">${x.score}</span></div>
      <div class="text">${highlight(x.text, q)}</div></div>`).join("") : '<div class="empty">没有匹配内容。</div>';
  };
  $("#kb-go").onclick = search;
  $("#kb-q").onkeydown = (e) => { if (e.key === "Enter") search(); };
  $$("#view .section-list button").forEach((b) => b.onclick = () => { $("#kb-q").value = b.dataset.sec; search(); });
}

function highlight(text, q) {
  const words = q.split(/\s+/).filter((w) => w.length >= 2).slice(0, 4);
  let out = esc(text);
  words.forEach((w) => {
    try { out = out.replace(new RegExp(esc(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"), (m) => `<mark>${m}</mark>`); } catch (e) {}
  });
  return out;
}

/* ---------------- agent ---------------- */
async function viewAgent() {
  const cfg = S.boot.config || {};
  $("#view").innerHTML = `
  <div class="page-head"><div><h1>AI 助手</h1><p>基于两份手册回答工艺问题，可直接调用配比、合金、脱氧、脱硫计算器。已接入当前炉次上下文，能按你现在的配比和状态回答。</p></div><div class="spacer"></div>
    <label class="chat-heat-toggle"><input type="checkbox" id="chat-use-heat" checked> 结合当前炉次</label>
    <span class="badge ${cfg.has_key ? "pass" : "neutral"}">${cfg.has_key ? "LLM Agent" : "本地检索"}</span>
    ${cfg.has_key ? "" : '<button class="btn sm" id="chat-config">配置 API →</button>'}</div>
  ${renderHeatFlow("agent")}
  <div class="chat-wrap">
    <div class="card chat-card">
      <div class="card-h"><h3>对话</h3><span class="sub">手册 + 计算引擎</span><div class="spacer"></div><button class="btn sm ghost" id="chat-clear">清空</button></div>
      <div class="chat-body" id="chat-body"></div>
      <div class="suggest">${["当前炉次下一步做什么？", "这炉总成本多少？", "这炉初始规划停氧多少？", "当前成分还要吹多久？", "铝脱氧要加多少铝？", "脱硫渣量怎么算？"].map((q) => `<button data-q="${q}">${q}</button>`).join("")}</div>
      <div class="chat-input"><textarea id="chat-in" placeholder="问一个工艺问题，例如：250 吨钢水 450ppm 氧，要加多少铝？"></textarea><button class="btn primary" id="chat-send">发送</button></div>
    </div>
    <div class="card">
      <div class="card-h"><h3>可调用的计算器</h3><span class="sub">Agent tools</span></div>
      <div class="card-b" style="display:flex;flex-direction:column;gap:9px">
        ${["炉料配比优化（LP）", "合金补加（回收率/夹带）", "铝脱氧", "脱硫渣量", "液相线温度", "脱碳/除氢/搅拌/加热"].map((x) => `<div class="kv"><span>${x}</span><b style="color:var(--ok)">✓</b></div>`).join("")}
      </div>
      <div class="card-b" style="padding-top:0"><div class="hint">配置 LLM 后，助手会先检索手册片段，再结合计算结果作答，并给页码引用。点击右上角齿轮配置。</div></div>
    </div>
  </div>`;
  renderChat();
  $("#chat-send").onclick = sendChat;
  $("#chat-in").onkeydown = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); } };
  $("#chat-clear").onclick = () => { S.chat = []; localStorage.removeItem("steel-lab-chat"); renderChat(); };
  const cfgBtn = $("#chat-config"); if (cfgBtn) cfgBtn.onclick = openSettings;
  $$(".suggest button").forEach((b) => b.onclick = () => { $("#chat-in").value = b.dataset.q; sendChat(); });
}

function renderChat() {
  const body = $("#chat-body");
  if (!body) return;
  if (!S.chat.length) {
    S.chat.push({ role: "assistant", content: "我是 steel-lab 工艺 Agent，能直接读取当前炉次：炉料、EAF/SM 合金、初始规划、动态实测和成本。问我“这炉下一步/成本/渣料/MgO/硅偏高”会按当前数据回答；需要算新方案时也可以直接调用计算器。", citations: [], actions: [] });
  }
  body.innerHTML = S.chat.map((m) => `<div class="msg ${m.role}">
    <div class="avatar">${m.role === "user" ? "我" : "SL"}</div>
    <div><div class="bubble">${esc(m.content).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>")}</div>
    ${m.note ? `<div class="msg-note">${esc(m.note)}</div>` : ""}
    ${m.citations && m.citations.length ? `<div class="cite">${m.citations.map((c) => `<span>${esc(c.doc_title)} 第${c.page}页</span>`).join("")}</div>` : ""}
    ${m.actions && m.actions.length ? `<div class="actions">${m.actions.map((a) => `<button class="btn sm" onclick="go('${a.view}')">${a.label} →</button>`).join("")}</div>` : ""}
    </div></div>`).join("");
  body.scrollTop = body.scrollHeight;
}

async function sendChat() {
  const inp = $("#chat-in");
  const q = inp.value.trim();
  if (!q || S.busy) return;
  inp.value = "";
  S.chat.push({ role: "user", content: q });
  S.chat.push({ role: "assistant", content: "检索中…", pending: true });
  S.busy = true;
  renderChat();
  try {
    const history = S.chat.filter((m) => !m.pending).slice(-8).map((m) => ({ role: m.role, content: m.content }));
    let context = null;
    const useHeat = $("#chat-use-heat")?.checked !== false;
    const dynState = S.dyn?.state || null;
    if (useHeat && (S.heat?.mix || S.heat?.charge || S.heat?.initial || dynState || S.plan?.data)) {
      context = {
        heat: {
          grade: S.heat?.grade, grade_name: gradeName(S.heat?.grade || S.grade),
          mass: S.heat?.mass || (dynState ? dynState.mass : null),
          sm_mass: S.heat?.sm_mass,
          mix: namedMix(S.heat?.mix),
          composition: (dynState ? dynState.comp : null) || S.heat?.charge?.composition || S.heat?.initial,
          initial: S.heat?.initial, alloy: S.heat?.alloy, alloy_sm: S.heat?.alloy_sm,
          dynamic: S.heat?.dynamic, source: S.heat?.source,
        },
        state: dynState,
        plan: S.plan?.data ? {
          grade: S.plan.data.grade_name, mass: S.plan.data.mass,
          sm_mass: S.plan.data.summary?.sm_mass,
          c_anchors: S.plan.data.summary?.c_anchors,
          c_path: S.plan.data.summary?.c_path,
          fluxes: S.plan.data.summary?.fluxes,
          cost: S.plan.data.summary?.cost,
          final_eaf: S.plan.data.summary?.final_eaf,
          final_sm: S.plan.data.summary?.final_sm,
          checkpoints: (S.plan.data.checkpoints || []).map((c) => ({ track: c.track, no: c.no, stage: c.stage, title: c.title, trigger: c.trigger })),
        } : null,
      };
    }
    const r = await api("/api/chat", "POST", { message: q, history, context });
    S.chat.pop();
    S.chat.push({ role: "assistant", content: r.answer, citations: r.citations || [], actions: r.actions || [], note: r.note });
    try { localStorage.setItem("steel-lab-chat", JSON.stringify(S.chat.slice(-20))); } catch (e) {}
  } catch (e) {
    S.chat.pop();
    S.chat.push({ role: "assistant", content: "出错了：" + e.message });
  }
  S.busy = false;
  renderChat();
}

/* ---------------- runs ---------------- */
async function viewRuns() {
  const r = await api("/api/runs").catch(() => ({ runs: [] }));
  S.runs = r.runs || [];
  S.runsLoaded = true;
  const eafRows = S.runs.filter((x) => !!runEafRef(x));
  const smRows = S.runs.filter((x) => x.payload?.kind === "sm");
  const eafIds = new Set(eafRows.map((x) => x.id));
  const smIds = new Set(smRows.map((x) => x.id));
  const otherRows = S.runs.filter((x) => !eafIds.has(x.id) && !smIds.has(x.id));
  const byId = Object.fromEntries(S.runs.map((x) => [x.id, x]));

  const row = (x, meta, cost, actions) => `<div class="run-row">
      <div><div class="nm">${esc(x.name)}</div><div class="meta">${meta || ""}</div></div>
      <div><span class="badge neutral">${gradeShort(x.grade)}</span></div>
      <div class="mono">${cost || "—"}</div>
      <div class="meta">${x.ts}</div>
      <div style="display:flex;gap:5px;flex-wrap:wrap">${actions}</div>
    </div>`;
  const head = `<div class="run-row" style="background:#fbfaf7;font-size:10.5px;color:var(--muted)"><div>名称</div><div>钢种</div><div>成本</div><div>时间</div><div></div></div>`;

  const eafHtml = eafRows.length ? head + eafRows.map((x) => {
    const ref = runEafRef(x);
    const sm = x.payload?.summary || {};
    const cpt = sm.total_per_t ?? sm.cost_per_t ?? x.payload?.cost_per_t;
    const cost = cpt ? "$" + f(cpt, 1) + "/t" : "—";
    const meta = `${ref?.tap_mass ? f(ref.tap_mass, 0) + " t" : ""}${ref?.final?.C != null ? " · 出钢 C " + f(ref.final.C, 3) + "%" : ""}`;
    return row(x, meta, cost,
      `<button class="btn sm" onclick="loadRun('${x.id}')">载入 EAF</button>
       <button class="btn sm primary" onclick="startSmFromRun('${x.id}')">做二次精炼 →</button>
       <button class="btn sm ghost" onclick="delRun('${x.id}')">删除</button>`);
  }).join("") : '<div class="empty">还没有保存 EAF 炉次。在 EAF 向导里点「保存 EAF 炉次」。</div>';

  const smHtml = smRows.length ? head + smRows.map((x) => {
    const sm = x.payload?.summary || {};
    const cost = sm.total_per_t ? "$" + f(sm.total_per_t, 1) + "/t" : "—";
    const linked = x.payload?.eaf_name || (x.payload?.eaf_run_id ? (byId[x.payload.eaf_run_id]?.name || "已关联") : "未关联");
    const meta = `${sm.mass ? f(sm.mass, 0) + " t" : ""} · EAF：${linked}`;
    return row(x, meta, cost,
      `<button class="btn sm" onclick="loadRun('${x.id}')">载入二次精炼</button>
       ${x.payload?.eaf_run_id ? `<button class="btn sm" onclick="loadRun('${x.payload.eaf_run_id}')">看 EAF</button>` : ""}
       <button class="btn sm ghost" onclick="delRun('${x.id}')">删除</button>`);
  }).join("") : '<div class="empty">还没有保存二次精炼记录。生成 SM 流程后点「保存二次精炼」。</div>';

  const otherHtml = otherRows.length ? `<div class="card mt12">
    <div class="card-h"><h3>配料 / 合金方案</h3><span class="sub">${otherRows.length} 条</span></div>
    <div class="card-b" style="padding:0 16px">${head}${otherRows.map((x) => {
      const cost = (x.payload?.cost_per_t || x.payload?.summary?.cost_per_t) ? "$" + f(x.payload?.cost_per_t || x.payload?.summary?.cost_per_t, 1) + "/t" : "—";
      const meta = x.payload?.total_mass ? f(x.payload.total_mass, 1) + " t" : "";
      return row(x, meta, cost, `<button class="btn sm" onclick="loadRun('${x.id}')">载入</button><button class="btn sm ghost" onclick="delRun('${x.id}')">删除</button>`);
    }).join("")}</div>
  </div>` : "";

  $("#view").innerHTML = `
  <div class="page-head"><div><h1>炉次记录</h1><p>EAF 炉次和二次精炼分开保存；二次精炼可以选一个 EAF 炉次，自动带入它的出钢成分和钢水量。</p></div><div class="spacer"></div><button class="btn sm" id="runs-export">导出 Excel</button><span class="badge neutral">${S.runs.length} 条</span></div>
  ${renderHeatFlow("runs")}
  <div class="card">
    <div class="card-h"><h3>EAF 炉次</h3><span class="sub">装料 + 合金 + 出钢成分</span><div class="spacer"></div><span class="badge neutral">${eafRows.length} 条</span></div>
    <div class="card-b" style="padding:0 16px">${eafHtml}</div>
  </div>
  <div class="card mt12">
    <div class="card-h"><h3>二次精炼记录</h3><span class="sub">CAS-OB → 脱气 → LF</span><div class="spacer"></div><span class="badge neutral">${smRows.length} 条</span></div>
    <div class="card-b" style="padding:0 16px">${smHtml}</div>
  </div>
  ${otherHtml}`;
  const ex = $("#runs-export");
  if (ex) ex.onclick = exportRuns;
}

async function exportRuns() {
  try {
    const res = await fetch(withSharecode("/api/runs/export"), {
      headers: { "X-Steel-Token": authToken(), "X-Steel-User": encodeURIComponent(currentUser()) },
    });
    if (!res.ok) throw new Error("导出失败：HTTP " + res.status);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "steel-lab-炉次-" + new Date().toISOString().slice(0, 10) + ".csv";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    toast("已导出，Excel 可直接打开");
  } catch (e) { toast(e.message, true); }
}

function loadRun(id) {
  const run = (S.runs || []).find((x) => x.id === id);
  if (!run) return;
  const p = run.payload || {};
  if (p.kind === "eaf" && p.eaf) {
    S.wizard.eaf = p.eaf;
    S.wizard.eafMass = p.eaf.mass;
    S.wizard.eafRunId = run.id;
    S.lastEafRunId = run.id;
    S.wizard.track = "eaf";
    S.wizard.step = 0;
    syncHeatFromEaf(p.eaf);
    resetSlagForNewHeat();
    const ss = p.summary || p.eaf.summary || {};
    S.plan.mass = Math.round(ss.tap_mass || p.eaf.mass || S.plan.mass);
    S.plan.grade = p.eaf.grade || S.plan.grade;
    if (ss.energy_kwh && p.eaf.mass) S.plan.power_kwh = ss.energy_kwh * 90 / Number(p.eaf.mass);
    toast("已载入 EAF 炉次");
    go("wizard");
    return;
  }
  if (p.kind === "sm" && p.sm) {
    S.wizard.sm = p.sm;
    S.wizard.smMass = p.sm.mass;
    S.wizard.smInitial = p.sm.summary?.initial || null;
    S.wizard.eafRunId = p.eaf_run_id || null;
    S.wizard.track = "sm";
    S.wizard.step = 0;
    syncHeatFromSm(p.sm);
    toast("已载入二次精炼记录");
    go("wizard");
    return;
  }
  if (p.kind === "heat" && p.heat) {
    const restoredCharge = p.heat.charge || p.plan?.plans?.eaf?.summary?.charge_result || null;
    S.heat = { ...S.heat, ...p.heat, charge: restoredCharge, rev: heatRev() + 1 };
    resetSlagForNewHeat();
    S.plan.data = p.plan || null;
    // 历史炉次的渣料按当时保存值显示，不用当前模型自动覆盖
    S.slag.lime = S.slag.dol = S.slag.flu = null;
    S.slag.manual = true;
    S.plan.rev = S.heat.rev;
    S.plan.grade = p.plan?.grade || S.heat.grade || S.grade;
    S.plan.mass = p.plan?.mass || S.heat.mass || 82;
    S.plan.dataSig = planSettingsSig();
    const hs = p.summary || p.plan?.summary || {};
    if (hs.energy_kwh && (p.plan?.mass || hs.mass)) {
      S.plan.power_kwh = Number(hs.energy_kwh) * 90 / Number(p.plan?.mass || hs.mass);
    }
    // 旧方案可能带 37 $/t 的“其他成本”（电极/耐材/人工估算）。
    // 不再自动恢复，避免载入旧炉次后成本又凭空高出约 $37/t；统一按当前页面的其他成本设置重算。
    const oldOtherPerT = hs.cost?.other != null && hs.sm_mass
      ? Number(hs.cost.other) / Number(hs.sm_mass) : 0;
    S.wizard.eaf = p.plan?.plans?.eaf || null;
    S.wizard.sm = p.plan?.plans?.sm || null;
    S.wizard.rev = S.heat.rev;
    S.lastCharge = p.plan?.plans?.eaf?.summary?.charge_result || S.lastCharge;
    S.lastAlloy = null; S.alloy = null; S.dyn.data = null; S.dyn.rev = 0;
    if (oldOtherPerT > 1) {
      toast(`已载入整炉方案；旧方案含其他成本 $${f(oldOtherPerT, 0)}/t，当前按 $${f(S.plan.other_per_t || 0, 0)}/t 口径，重新生成后对比更准`);
    } else {
      toast("已载入整炉方案");
    }
    go("plan");
    return;
  }
  if (p.track && p.summary) {
    const fake = { status: "ok", track: p.track, grade: p.grade || run.grade, mass: p.mass || p.summary.mass || 90, grade_name: p.grade_name, summary: p.summary, steps: p.steps || [] };
    if (p.track === "sm") { syncHeatFromSm(fake); S.wizard.sm = fake; S.wizard.track = "sm"; }
    else { syncHeatFromEaf(fake); S.wizard.eaf = fake; S.wizard.track = "eaf"; }
    toast("已载入操作流程");
    go("wizard");
    return;
  }
  if (p.kind === "alloy" && p.alloy && p.heat) {
    S.heat = { ...S.heat, ...p.heat, rev: heatRev() + 1 };
    S.lastAlloy = p.alloy;
    S.alloy = {
      grade: S.heat.grade || S.grade, catalog: "eaf", profile: "eaf_cal",
      mass: Math.round(S.heat.mass || 90), initial: S.heat.initial || {},
      targets: targetsFromSpec(S.boot.grades_sm[S.heat.grade || S.grade]?.specs || S.boot.grades_sm.sc21_refining.specs),
    };
    toast("已载入合金方案");
    go("alloy");
    return;
  }
  if (p.mix && p.total_mass) {
    S.grade = run.grade || S.grade;
    S.chargeMass = p.total_mass;
    S.lastCharge = p;
    S.heat = { ...S.heat, track: "eaf", grade: S.grade, mass: p.total_mass, mix: p.mix, charge: p,
               alloy: null, initial: null, pre_c: 0.37, pre_si: 0.05, skip_decarb: false };
    resetSlagForNewHeat();
    bumpHeat("run");
    toast("已载入配料方案");
    go("charge");
    return;
  }
  toast("这条记录没有可载入的完整方案", true);
}

async function delRun(id) {
  if (!confirm("删除这条记录？")) return;
  await api("/api/runs?id=" + id, "DELETE");
  toast("已删除");
  viewRuns();
}

/* ---------------- settings ---------------- */
function openSettings() {
  const c = S.boot.config || {};
  $("#modal-root").innerHTML = `<div class="modal-mask" id="mask"><div class="modal">
    <div class="card-h"><h3>AI 接口设置</h3><div class="spacer"></div><button class="icon-btn" id="m-close">×</button></div>
    <div class="card-b">
      <div class="hint">本地引擎不需要任何配置。启用 LLM Agent 时填写 OpenAI 兼容接口。Key 只保存在本机 data/config.json；也可以用环境变量 STEEL_LAB_API_KEY 覆盖，部署时更安全。</div>
      ${c.multi_user ? `<label class="field"><span>我的名字（多人共用时隔离炉次记录）</span><input id="cfg-user" value="${esc(currentUser())}" maxlength="24" placeholder="例如：张三"></label>` : ""}
      ${c.key_from_env ? '<div class="warn-item mt8"><span class="ico">!</span><span>当前 Key 来自环境变量 STEEL_LAB_API_KEY，页面里改 Key 不会生效。</span></div>' : ""}
      <label class="field"><span>Base URL（通常以 /v1 结尾）</span><input id="cfg-base" value="${esc(c.base_url || "https://api.openai.com/v1")}" placeholder="https://api.example.com/v1"></label>
      <label class="field"><span>模型</span><input id="cfg-model" list="cfg-model-list" value="${esc(c.model || "gpt-4o-mini")}" placeholder="点下面「获取模型列表」"><datalist id="cfg-model-list"></datalist></label>
      <label class="field"><span>API Key ${c.has_key ? "（已保存，留空不修改）" : ""}</span><input id="cfg-key" type="password" placeholder="sk-..."></label>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
        <button class="btn sm" id="cfg-models">获取模型列表</button>
        <button class="btn sm primary" id="cfg-test">测试连接</button>
        <span class="small muted" id="cfg-msg"></span>
      </div>
      <div id="cfg-detail" class="cfg-detail"></div>
    </div>
    <div class="foot"><button class="btn" id="m-cancel">取消</button><button class="btn primary" id="m-save">保存</button></div>
  </div></div>`;
  const close = () => $("#modal-root").innerHTML = "";
  const payload = () => {
    const body = { base_url: $("#cfg-base").value.trim(), model: $("#cfg-model").value.trim() };
    const key = $("#cfg-key").value.trim();
    if (key) body.api_key = key;
    return body;
  };
  const show = (ok, text, hint) => {
    $("#cfg-msg").textContent = text;
    $("#cfg-msg").style.color = ok ? "var(--ok)" : "var(--bad)";
    $("#cfg-detail").innerHTML = hint ? `<div class="hint">${esc(hint)}</div>` : "";
  };
  $("#m-close").onclick = close; $("#m-cancel").onclick = close;
  $("#mask").onclick = (e) => { if (e.target.id === "mask") close(); };
  $("#m-save").onclick = async () => {
    try {
      const u = $("#cfg-user");
      if (u) setUser(u.value.trim().slice(0, 24));
      S.boot.config = await api("/api/config", "POST", payload());
      toast("设置已保存"); close();
    } catch (e) { show(false, "保存失败：" + e.message); }
  };
  $("#cfg-models").onclick = async () => {
    show(true, "获取中…");
    try {
      const r = await api("/api/config/models", "POST", payload());
      if (!r.ok) return show(false, "获取失败：" + (r.code ? "[" + r.code + "] " : "") + (r.error || ""), r.hint || "");
      const dl = $("#cfg-model-list");
      dl.innerHTML = (r.models || []).map((m) => `<option value="${esc(m)}"></option>`).join("");
      const cur = $("#cfg-model").value.trim();
      const hit = (r.models || []).includes(cur);
      show(true, `接口可用，共 ${r.models.length} 个模型`, hit ? "当前模型在列表中。" : "当前模型不在列表中，点模型框从下拉里选一个。");
    } catch (e) { show(false, "获取失败：" + e.message); }
  };
  $("#cfg-test").onclick = async () => {
    show(true, "测试中…");
    try {
      const r = await api("/api/config/test", "POST", payload());
      if (r.ok) {
        if (r.auto_fixed) $("#cfg-base").value = r.base_url;
        show(true, `连接成功 · ${r.model} · ${r.latency_ms} ms`,
             (r.note ? r.note + "。" : "") + "现在可以保存，AI 页会切换为 LLM Agent。");
      } else {
        show(false, `失败${r.code ? " [" + r.code + "]" : ""}：${r.error || ""}`, r.hint || "");
      }
    } catch (e) { show(false, "测试失败：" + e.message); }
  };
}

/* ---------------- start ---------------- */
boot().catch((e) => {
  document.body.innerHTML = `<div style="padding:40px;font-family:sans-serif"><h2>steel-lab 启动失败</h2><p>${esc(e.message)}</p><p>请确认已运行 <code>python app.py</code>。</p></div>`;
});
