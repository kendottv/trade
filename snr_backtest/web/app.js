const $ = (id) => document.getElementById(id);
let state = null;
let twiiChart, candleSeries, smaSeries, eqChart, eqSeries, txfChart, txfSeries;
let twiiN = 132;
let lastAlertKey = "";

function fmt(n, d = 0) {
  if (n === null || n === undefined || n === "") return "—";
  return Number(n).toLocaleString("zh-TW", { maximumFractionDigits: d, minimumFractionDigits: d });
}
function signed(n, d = 0) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  return (v > 0 ? "+" : "") + fmt(v, d);
}

document.querySelectorAll(".tabs button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll(".tabs button").forEach((x) => x.classList.remove("on"));
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    $("tab-" + b.dataset.tab).classList.add("on");
    if (b.dataset.tab === "over" || b.dataset.tab === "pnl" || b.dataset.tab === "bt" || b.dataset.tab === "curves") resizeCharts();
    if (b.dataset.tab === "bt") loadBacktest();
    if (b.dataset.tab === "curves") loadCurves();
  };
});
document.querySelectorAll("#periods button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#periods button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    twiiN = Number(b.dataset.n);
    if (state) drawTwii(state.twii);
  };
});

function metric(k, v, d, cls) {
  return `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div><div class="d ${cls || ""}">${d || ""}</div></div>`;
}

function render(s) {
  const prevKey = lastAlertKey;
  $("clock").textContent = s.clock + (s.live ? " 盤中" : " 盤後");
  const pnlCls = s.pnl >= 0 ? "up" : "dn";
  let sizeLabel = s.lock_new ? "硬關" : (s.size_weight != null ? (Number(s.size_weight) * 100).toFixed(0) + "%" : (s.allow ? "開" : "關"));
  $("metrics").innerHTML =
    metric("權益", fmt(s.equity, 0), signed(s.pnl, 0) + "（" + signed(s.pnl_pct, 1) + "%）", pnlCls) +
    metric("現金", fmt(s.cash, 0), "") +
    metric("持股", s.n_pos + " 檔", s.live ? "盤中估價" : ("收盤確認 " + s.session)) +
    metric("新聞熱度", s.heat == null ? "—" : s.heat, s.trend) +
    metric("新倉檔位", sizeLabel, s.lock_new ? "戰爭／盤崩／無資料" : "關稅減碼");

  const alerts = s.alerts || [];
  lastAlertKey = alerts.map((a) => a.time + a.ticker).join("|");
  if (!alerts.length) {
    $("alerts").innerHTML = '<p class="empty">今天還沒有破高預警。</p>';
  } else {
    $("alerts").innerHTML = alerts.map((a) => {
      const t = String(a.time || "");
      const hh = t.length >= 16 ? t.slice(11, 16) : t;
      const neu = lastAlertKey !== prevKey && prevKey !== "" && !prevKey.includes(a.ticker);
      return `<div class="item${neu ? " new" : ""}">${hh} ${a.name || ""} (${a.ticker}) 現價 ${fmt(a.last, 2)} &gt; ${fmt(a.prior_high_20, 2)}</div>`;
    }).join("");
  }
  const pend = s.pending || [];
  $("pending").innerHTML = pend.length
    ? pend.map((p) => `<div class="item">${p.side} ${p.name || p.ticker} ${p.reason || ""} ${p.target_weight != null ? "權重 " + (p.target_weight * 100).toFixed(0) + "%" : ""}</div>`).join("")
    : '<p class="empty">沒有 pending。</p>';

  const pos = s.positions || [];
  if (!pos.length) {
    $("positions").innerHTML = '<p class="empty">目前空手。</p>';
  } else {
    const pxLab = s.live ? "現價" : "收盤";
    $("positions").innerHTML = `<table><thead><tr><th>代號</th><th>名稱</th><th>股數</th><th>成本</th><th>${pxLab}</th><th>市值</th><th>未實現</th><th>報酬%</th><th>進場</th></tr></thead><tbody>` +
      pos.map((p) => `<tr><td>${p.ticker}</td><td>${p.name}</td><td>${p.shares}</td><td>${fmt(p.avg, 2)}</td><td>${fmt(p.last, 2)}${p.asof ? `<div class="cap">${p.asof}</div>` : ""}</td><td>${fmt(p.mv, 0)}</td><td class="${p.upnl>=0?"up":"dn"}">${signed(p.upnl,0)}</td><td class="${p.upct>=0?"up":"dn"}">${signed(p.upct,1)}</td><td>${p.entry_date}</td></tr>`).join("") +
      `</tbody></table>`;
    $("posCap").textContent = s.live
      ? "盤中現價。成本是今天開盤成交價，不是昨天收盤。"
      : "用最近收盤估；今天開盤買的，盤中請看現價。";
  }
  const st = s.stamps || {};
  $("stamps").innerHTML = `<p class="cap">收盤單 ${st.live || "—"}　預警 ${st.alert || "—"}　新聞 08:30 ${st.n0830 || "—"}　21:30 ${st.n2130 || "—"}</p>`;
  $("reason").textContent = s.reason || "";

  const tw = s.twii || {};
  const chgCls = (tw.chg || 0) >= 0 ? "up" : "dn";
  const closeLab = tw.status === "盤中" ? "現價" : "收盤";
  $("twiiCap").innerHTML = `<span class="${chgCls}">${signed(tw.chg, 2)}（${signed(tw.chg_pct, 2)}%）</span>　${tw.asof || ""}　${tw.status || ""}　SMA${tw.sma_n} ${tw.above ? "之上" : "之下"}`;
  $("twiiOhlc").innerHTML =
    `<div class="cell"><span>開盤</span><b>${fmt(tw.open, 2)}</b></div>` +
    `<div class="cell"><span>最高</span><b class="up">${fmt(tw.high, 2)}</b></div>` +
    `<div class="cell"><span>最低</span><b class="dn">${fmt(tw.low, 2)}</b></div>` +
    `<div class="cell"><span>${closeLab}</span><b>${fmt(tw.close != null ? tw.close : tw.last, 2)}</b></div>`;
  const tx = s.txf_night || {};
  $("txfCode").textContent = [tx.name, tx.month].filter(Boolean).join(" ");
  const txChg = (tx.chg || 0) >= 0 ? "up" : "dn";
  $("txfCap").innerHTML = tx.ok
    ? `<span class="${txChg}">${signed(tx.chg, 0)}（${signed(tx.chg_pct, 2)}%）</span>　昨收 ${fmt(tx.ref, 0)}　${tx.asof || ""}　${tx.status || ""}`
    : (tx.note || "沒有盤後報價");
  $("txfOhlc").innerHTML = tx.ok
    ? `<div class="cell"><span>開盤</span><b>${fmt(tx.open, 0)}</b></div>` +
      `<div class="cell"><span>最高</span><b class="up">${fmt(tx.high, 0)}</b></div>` +
      `<div class="cell"><span>最低</span><b class="dn">${fmt(tx.low, 0)}</b></div>` +
      `<div class="cell"><span>現價</span><b>${fmt(tx.last != null ? tx.last : tx.close, 0)}</b></div>`
    : "";
  drawTwii(tw);
  drawTxf(s.txf_night || {});
  drawEq(s.equity_curve || []);

  $("newsHead").textContent = `熱度 ${s.heat ?? "—"}　趨勢 ${s.trend}　${s.lock_new ? "硬關" : "檔位 " + sizeLabel}`;
  $("newsOff").innerHTML = (s.off_headlines || []).map((h) => `<li>${h}</li>`).join("") || "<li class='empty'>沒有</li>";
  $("newsOn").innerHTML = (s.on_headlines || []).map((h) => `<li>${h}</li>`).join("") || "<li class='empty'>沒有</li>";
  $("snapHead").textContent = `熱度 ${s.snap?.score ?? "—"}　${s.snap?.session || ""} ${s.snap?.note || ""}`;
  $("snapOff").innerHTML = (s.snap?.off || []).map((h) => `<li>${h}</li>`).join("");

  const led = s.ledger || [];
  $("ledger").innerHTML = led.length
    ? `<table><thead><tr>${Object.keys(led[0]).map((k) => `<th>${k}</th>`).join("")}</tr></thead><tbody>` +
      led.map((r) => `<tr>${Object.keys(led[0]).map((k) => `<td>${r[k] ?? ""}</td>`).join("")}</tr>`).join("") +
      `</tbody></table>`
    : '<p class="empty">還沒有 ledger。</p>';

  const jou = s.journal || [];
  $("journal").innerHTML = jou.length
    ? `<table><thead><tr>${Object.keys(jou[0]).map((k) => `<th>${k}</th>`).join("")}</tr></thead><tbody>` +
      jou.map((r) => `<tr>${Object.keys(jou[0]).map((k) => `<td>${r[k] ?? ""}</td>`).join("")}</tr>`).join("") +
      `</tbody></table>`
    : '<p class="empty">還沒有新聞日誌。</p>';

  renderWatch(s.watch || []);
  if (s.held_banks && s.held_banks.length) $("heldBanks").textContent = "帳上舊倉（只作出場）：" + s.held_banks.join("、");
  else $("heldBanks").textContent = "";
  fillStrat(s.strategy || {}, s.news_th || {});
}

function drawTwii(tw) {
  const el = $("twiiChart");
  if (!window.LightweightCharts) return;
  if (!twiiChart) {
    twiiChart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
      grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
      rightPriceScale: { borderColor: "#30363d" },
      timeScale: { borderColor: "#30363d" },
      width: el.clientWidth,
      height: 360,
    });
    candleSeries = twiiChart.addCandlestickSeries({
      upColor: "#e53935", downColor: "#43a047",
      borderUpColor: "#e53935", borderDownColor: "#43a047",
      wickUpColor: "#e53935", wickDownColor: "#43a047",
    });
    smaSeries = twiiChart.addLineSeries({ color: "#f9a825", lineWidth: 1 });
  }
  let c = tw.candles || [];
  if (twiiN) c = c.slice(-twiiN);
  candleSeries.setData(c.map((x) => ({ time: x.time, open: x.open, high: x.high, low: x.low, close: x.close })));
  smaSeries.setData(c.filter((x) => x.sma != null).map((x) => ({ time: x.time, value: x.sma })));
}

function drawTxf(tx) {
  const el = $("txfChart");
  if (!el || !window.LightweightCharts) return;
  if (!txfChart) {
    txfChart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
      grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "#30363d" },
      width: el.clientWidth,
      height: 220,
    });
    txfSeries = txfChart.addLineSeries({ color: "#f9a825", lineWidth: 2 });
  }
  const line = (tx.line || []).filter((p) => p.time && p.value != null);
  txfSeries.setData(line);
}

function drawEq(rows) {
  const el = $("eqChart");
  if (!window.LightweightCharts || !rows.length) return;
  if (!eqChart) {
    eqChart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
      grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
      width: el.clientWidth,
      height: 220,
    });
    eqSeries = eqChart.addLineSeries({ color: "#58a6ff", lineWidth: 2 });
  }
  eqSeries.setData(rows.filter((r) => r.date && r.equity != null).map((r) => ({ time: String(r.date).slice(0, 10), value: Number(r.equity) })));
}

function resizeCharts() {
  if (twiiChart) twiiChart.applyOptions({ width: $("twiiChart").clientWidth });
  if (txfChart) txfChart.applyOptions({ width: $("txfChart").clientWidth });
  if (btChart) btChart.applyOptions({ width: $("btChart").clientWidth });
  if (cPrice) cPrice.applyOptions({ width: $("curvePrice").clientWidth });
  if (cMacd) cMacd.applyOptions({ width: $("curveMacd").clientWidth });
  if (cRsi) cRsi.applyOptions({ width: $("curveRsi").clientWidth });
  if (cKd) cKd.applyOptions({ width: $("curveKd").clientWidth });
  if (eqChart) eqChart.applyOptions({ width: $("eqChart").clientWidth });
}
window.addEventListener("resize", resizeCharts);

function renderWatch(rows) {
  if ($("watchTable").dataset.lock === "1") return;
  $("watchTable").innerHTML = `<table><thead><tr><th>監看</th><th>代號</th><th>名稱</th><th>持有</th></tr></thead><tbody>` +
    rows.map((r) => `<tr><td><input type="checkbox" data-t="${r.ticker}" ${r.on ? "checked" : ""}></td><td>${r.ticker}</td><td>${r.name}</td><td>${r.held ? "是" : ""}</td></tr>`).join("") +
    `</tbody></table>`;
  $("watchTable").onchange = () => { $("watchTable").dataset.lock = "1"; };
}

function collectWatch() {
  return [...document.querySelectorAll("#watchTable input[type=checkbox]")].map((cb) => {
    const tr = cb.closest("tr");
    return { ticker: cb.dataset.t, name: tr.children[2].textContent, on: cb.checked };
  });
}

$("btnSaveWatch").onclick = async () => {
  const r = await fetch("/api/watch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: collectWatch() }) });
  const j = await r.json();
  $("watchTable").dataset.lock = "0";
  $("watchMsg").textContent = j.ok ? "已存 " + j.n + " 檔。" : (j.error || "失敗");
};
$("btnResetWatch").onclick = async () => {
  await fetch("/api/watch/reset", { method: "POST" });
  $("watchTable").dataset.lock = "0";
  $("watchMsg").textContent = "已恢復內建名單（不含銀行）。";
};
$("btnAdd").onclick = async () => {
  const r = await fetch("/api/watch/add", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker: $("addTicker").value, name: $("addName").value }),
  });
  const j = await r.json();
  $("watchMsg").textContent = j.ok ? "已加入 " + j.ticker : (j.error || "失敗");
};

function fillStrat(st, news) {
  if ($("stratForm").dataset.filled === "1" && document.activeElement && $("stratForm").contains(document.activeElement)) return;
  const fields = [
    ["BREAKOUT_V2_SNR_MIN", "SNR 下限", st.BREAKOUT_V2_SNR_MIN, 0.01],
    ["BREAKOUT_LOOKBACK", "突破回看天數", st.BREAKOUT_LOOKBACK, 1],
    ["TWII_SMA", "大盤 SMA", st.TWII_SMA, 1],
    ["BREAKOUT_TP", "停利", st.BREAKOUT_TP, 0.01],
    ["BREAKOUT_SL", "停損", st.BREAKOUT_SL, 0.01],
    ["BREAKOUT_TIME_STOP_DAYS", "時間停損日數", st.BREAKOUT_TIME_STOP_DAYS, 1],
    ["BREAKOUT_V2_TRAIL_ARM", "移動停利啟動", st.BREAKOUT_V2_TRAIL_ARM, 0.01],
    ["BREAKOUT_V2_TRAIL_LOOKBACK", "移動停利回看", st.BREAKOUT_V2_TRAIL_LOOKBACK, 1],
    ["PAPER_MAX_WEIGHT", "單檔權重上限", st.PAPER_MAX_WEIGHT, 0.01],
    ["PAPER_LOT_SIZE", "零股單位", st.PAPER_LOT_SIZE, 1],
    ["MAX_POSITIONS", "最多持股檔數", st.MAX_POSITIONS, 1],
    ["HOT", "HOT", news.HOT, 1],
    ["SEVERE", "SEVERE", news.SEVERE, 1],
    ["COOLING_DROP", "COOLING_DROP", news.COOLING_DROP, 1],
  ];
  $("stratForm").innerHTML = fields.map(([k, lab, v, step]) =>
    `<label>${lab}<input id="f_${k}" type="number" step="${step}" value="${v}"></label>`
  ).join("") + `<label>移動停利<input id="f_TRAIL" type="checkbox" ${st.BREAKOUT_V2_TRAIL ? "checked" : ""}></label>` +
    `<label>大盤均線濾網<input id="f_TWII_F" type="checkbox" ${st.BREAKOUT_V2_TWII_FILTER ? "checked" : ""}></label>`;
  $("stratForm").dataset.filled = "1";
}
$("btnSaveStrat").onclick = async () => {
  const num = (id) => Number($(id).value);
  const body = {
    strategy: {
      BREAKOUT_V2_SNR_MIN: num("f_BREAKOUT_V2_SNR_MIN"),
      BREAKOUT_LOOKBACK: num("f_BREAKOUT_LOOKBACK"),
      TWII_SMA: num("f_TWII_SMA"),
      BREAKOUT_TP: num("f_BREAKOUT_TP"),
      BREAKOUT_SL: num("f_BREAKOUT_SL"),
      BREAKOUT_TIME_STOP_DAYS: num("f_BREAKOUT_TIME_STOP_DAYS"),
      BREAKOUT_V2_TRAIL: $("f_TRAIL").checked,
      BREAKOUT_V2_TRAIL_ARM: num("f_BREAKOUT_V2_TRAIL_ARM"),
      BREAKOUT_V2_TRAIL_LOOKBACK: num("f_BREAKOUT_V2_TRAIL_LOOKBACK"),
      BREAKOUT_V2_TWII_FILTER: $("f_TWII_F").checked,
      PAPER_MAX_WEIGHT: num("f_PAPER_MAX_WEIGHT"),
      PAPER_LOT_SIZE: num("f_PAPER_LOT_SIZE"),
      MAX_POSITIONS: num("f_MAX_POSITIONS"),
    },
    news: { HOT: num("f_HOT"), SEVERE: num("f_SEVERE"), COOLING_DROP: num("f_COOLING_DROP") },
  };
  await fetch("/api/strategy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  $("stratForm").dataset.filled = "0";
  $("stratMsg").textContent = "已寫入 ui_settings.json。下次 16:00／09:00／08:30 才生效。";
};
$("btnResetStrat").onclick = async () => {
  await fetch("/api/strategy/reset", { method: "POST" });
  $("stratForm").dataset.filled = "0";
  $("stratMsg").textContent = "已恢復程式預設。";
};

let btChart, btSeries, btId = "breakout_v2";
let btKind = "breakout";

const BT_HINT = {
  breakout: "收盤突破前 N 日高，可加 SNR／大盤濾網。出場：停利停損、時間停損、移動停利。",
  pullback: "站上趨勢均線後回檔到短均線附近才買。SNR 上限用來避開太乾淨的趨勢。",
  macd: "MACD 黃金交叉買、死亡交叉賣。停利停損仍有效。",
  rsi: "RSI 從超賣往上穿越買，碰到超買區賣。",
  kd: "K 在超賣區黃金交叉買；死亡交叉或 K 到超買賣。",
  sma: "短均線上穿長均線買、下穿賣。",
  bb: "回歸：收盤碰到下軌買、上軌賣。突破：收上軌買、跌回中軌賣。",
};
const BT_DEFAULTS = {
  breakout: { tp: 0.25, sl: 0.20, time_stop_days: 3 },
  pullback: { tp: 0.08, sl: 0.04, time_stop_days: 0 },
  macd: { tp: 0.15, sl: 0.10, time_stop_days: 0 },
  rsi: { tp: 0.12, sl: 0.08, time_stop_days: 0 },
  kd: { tp: 0.12, sl: 0.08, time_stop_days: 0 },
  sma: { tp: 0.15, sl: 0.10, time_stop_days: 0 },
  bb: { tp: 0.10, sl: 0.06, time_stop_days: 0 },
};

function fillBtForm() {
  const el = $("btForm");
  if (!el) return;
  if ($("btKindHint")) $("btKindHint").textContent = BT_HINT[btKind] || "";
  const d = BT_DEFAULTS[btKind] || BT_DEFAULTS.breakout;
  const num = (id, lab, v, step) =>
    `<label>${lab}<input id="bt_${id}" type="number" step="${step}" value="${v}"></label>`;
  const chk = (id, lab, on) =>
    `<label>${lab}<input id="bt_${id}" type="checkbox"${on ? " checked" : ""}></label>`;
  let extra = [
    num("tp", "停利（例如 0.25=25%）", d.tp, 0.01),
    num("sl", "停損", d.sl, 0.01),
    num("time_stop_days", "時間停損日數（0=關）", d.time_stop_days, 1),
  ];
  if (btKind === "breakout") {
    extra = extra.concat([
      num("lookback", "突破回看天數", 20, 1),
      num("snr_min", "SNR 下限", 0.40, 0.01),
      num("trail_arm", "移動停利啟動（12%=0.12）", 0.12, 0.01),
      num("trail_lookback", "移動停利回看低點", 15, 1),
      chk("use_snr", "用 SNR 濾網", true),
      chk("twii", "大盤 > SMA60", true),
      chk("trail", "移動停利", true),
    ]);
  } else if (btKind === "pullback") {
    extra = extra.concat([
      num("sma_fast", "短均線", 20, 1),
      num("sma_trend", "趨勢均線", 60, 1),
      num("band_lo", "回檔下限（×短均）", 0.97, 0.01),
      num("band_hi", "回檔上限（×短均）", 1.01, 0.01),
      num("snr_max", "SNR 上限（雜訊）", 0.25, 0.01),
      chk("use_snr", "用 SNR 濾網", true),
    ]);
  } else if (btKind === "macd") {
    extra = extra.concat([
      num("macd_fast", "MACD 快線", 12, 1),
      num("macd_slow", "MACD 慢線", 26, 1),
      num("macd_signal", "MACD 訊號", 9, 1),
    ]);
  } else if (btKind === "rsi") {
    extra = extra.concat([
      num("rsi_n", "RSI 天數", 14, 1),
      num("rsi_os", "超賣（進場穿越）", 30, 1),
      num("rsi_ob", "超買（出場）", 70, 1),
    ]);
  } else if (btKind === "kd") {
    extra = extra.concat([
      num("kd_n", "KD 週期", 9, 1),
      num("kd_k", "K 平滑", 3, 1),
      num("kd_d", "D 平滑", 3, 1),
      num("kd_os", "超賣（K 要低於此才買）", 20, 1),
      num("kd_ob", "超買（K 到此賣）", 80, 1),
    ]);
  } else if (btKind === "sma") {
    extra = extra.concat([
      num("sma_fast", "短均線", 20, 1),
      num("sma_trend", "長均線", 60, 1),
    ]);
  } else if (btKind === "bb") {
    extra = extra.concat([
      num("bb_n", "布林天數", 20, 1),
      num("bb_k", "帶寬（標準差倍數）", 2, 0.1),
      `<label>模式<select id="bt_bb_mode"><option value="revert" selected>回歸（下軌買）</option><option value="break">突破（上軌買）</option></select></label>`,
    ]);
  }
  el.innerHTML = extra.join("");
}

document.querySelectorAll("#btKinds button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#btKinds button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    btKind = b.dataset.kind;
    fillBtForm();
  };
});
if ($("btnRunBt")) {
  $("btnRunBt").onclick = async () => {
    const num = (id, d) => {
      const el = $(id);
      return el ? Number(el.value) : d;
    };
    const chk = (id, d) => ($(id) ? $(id).checked : d);
    const sel = (id, d) => ($(id) ? $(id).value : d);
    const body = {
      kind: btKind,
      start: $("btStart").value,
      end: $("btEnd").value,
      tp: num("bt_tp", 0.25),
      sl: num("bt_sl", 0.20),
      time_stop_days: num("bt_time_stop_days", 0),
      snr_min: num("bt_snr_min", 0.4),
      snr_max: num("bt_snr_max", 0.25),
      twii_filter: chk("bt_twii", true),
      trail: chk("bt_trail", true),
      trail_arm: num("bt_trail_arm", 0.12),
      trail_lookback: num("bt_trail_lookback", 15),
      use_snr: chk("bt_use_snr", true),
      lookback: num("bt_lookback", 20),
      sma_fast: num("bt_sma_fast", 20),
      sma_trend: num("bt_sma_trend", 60),
      band_lo: num("bt_band_lo", 0.97),
      band_hi: num("bt_band_hi", 1.01),
      macd_fast: num("bt_macd_fast", 12),
      macd_slow: num("bt_macd_slow", 26),
      macd_signal: num("bt_macd_signal", 9),
      rsi_n: num("bt_rsi_n", 14),
      rsi_os: num("bt_rsi_os", 30),
      rsi_ob: num("bt_rsi_ob", 70),
      kd_n: num("bt_kd_n", 9),
      kd_k: num("bt_kd_k", 3),
      kd_d: num("bt_kd_d", 3),
      kd_os: num("bt_kd_os", 20),
      kd_ob: num("bt_kd_ob", 80),
      bb_n: num("bt_bb_n", 20),
      bb_k: num("bt_bb_k", 2),
      bb_mode: sel("bt_bb_mode", "revert"),
    };
    $("btCap").textContent = "計算中（讀本機日 K）…";
    try {
      const r = await fetch("/api/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const j = await r.json();
      if (!j.ok && j.error) {
        $("btCap").textContent = j.error;
        return;
      }
      $("btCap").textContent = j.note || "完成";
      const sm = (j.summary || [])[0] || {};
      $("btMetrics").innerHTML = [
        ["期末權益", fmt(sm.final_equity, 0), ""],
        ["報酬", signed((Number(sm.total_return) || 0) * 100, 1) + "%", Number(sm.total_return) >= 0 ? "up" : "dn"],
        ["CAGR", ((Number(sm.cagr) || 0) * 100).toFixed(1) + "%", ""],
        ["勝率", ((Number(sm.win_rate) || 0) * 100).toFixed(1) + "%", ""],
        ["最大回撤", ((Number(sm.max_drawdown) || 0) * 100).toFixed(1) + "%", "dn"],
      ].map(([k, v, cls]) => metric(k, v, "", cls)).join("");
      drawBt(j.curve || []);
      const tr = j.trades || [];
      $("btTrades").innerHTML = tr.length
        ? `<table><thead><tr>${Object.keys(tr[0]).slice(0, 9).map((k) => `<th>${k}</th>`).join("")}</tr></thead><tbody>` +
          tr.map((row) => `<tr>${Object.keys(tr[0]).slice(0, 9).map((k) => `<td>${row[k] ?? ""}</td>`).join("")}</tr>`).join("") +
          `</tbody></table>`
        : '<p class="empty">這次沒有成交。</p>';
    } catch (e) {
      $("btCap").textContent = "回測失敗。";
    }
  };
}
fillBtForm();

let cPrice, cCandle, cSma20, cSma60, cMacd, cMacdLine, cMacdSig, cHist, cRsi, cRsiLine, cKd, cK, cD;
let curveN = 132;

function loadBacktest(id) {
  if (id) btId = id;
  fetch("/api/backtest").then((r) => r.json()).then((j) => {
    const items = j.items || [];
    $("btStrats").innerHTML = items.map((x) =>
      `<button data-id="${x.id}" class="${x.id === btId ? "on" : ""}">${x.label}</button>`
    ).join("");
    $("btStrats").querySelectorAll("button").forEach((b) => {
      b.onclick = () => loadBacktest(b.dataset.id);
    });
  }).catch(() => {});
  fetch("/api/backtest/" + encodeURIComponent(btId)).then((r) => r.json()).then((j) => {
    $("btCap").textContent = (j.label || btId) + "　" + (j.note || "");
    const sm = (j.summary || [])[0] || {};
    const cells = [
      ["期末權益", fmt(sm.final_equity, 0), ""],
      ["報酬", signed((Number(sm.total_return) || 0) * 100, 1) + "%", Number(sm.total_return) >= 0 ? "up" : "dn"],
      ["CAGR", ((Number(sm.cagr) || 0) * 100).toFixed(1) + "%", ""],
      ["勝率", ((Number(sm.win_rate) || 0) * 100).toFixed(1) + "%", ""],
      ["最大回撤", ((Number(sm.max_drawdown) || 0) * 100).toFixed(1) + "%", "dn"],
    ];
    $("btMetrics").innerHTML = cells.map(([k, v, cls]) => metric(k, v, "", cls)).join("");
    drawBt(j.curve || []);
    const tr = j.trades || [];
    $("btTrades").innerHTML = tr.length
      ? `<table><thead><tr>${Object.keys(tr[0]).slice(0, 9).map((k) => `<th>${k}</th>`).join("")}</tr></thead><tbody>` +
        tr.map((r) => `<tr>${Object.keys(tr[0]).slice(0, 9).map((k) => `<td>${r[k] ?? ""}</td>`).join("")}</tr>`).join("") +
        `</tbody></table>`
      : '<p class="empty">沒有回測成交檔。</p>';
  }).catch(() => { $("btCap").textContent = "讀不到 reports。"; });
}

function drawBt(rows) {
  const el = $("btChart");
  if (!el || !window.LightweightCharts) return;
  if (!btChart) {
    btChart = LightweightCharts.createChart(el, {
      layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
      grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
      width: el.clientWidth,
      height: 360,
    });
    btSeries = btChart.addLineSeries({ color: "#58a6ff", lineWidth: 2 });
  }
  btSeries.setData((rows || []).filter((r) => r.time && r.value != null).map((r) => ({ time: r.time, value: Number(r.value) })));
}

function fillCurveTickers() {
  const sel = $("curveTicker");
  if (!sel || sel.dataset.ready === "1") return;
  const opts = [{ t: "^TWII", n: "台灣加權" }];
  (state && state.watch ? state.watch : []).forEach((w) => {
    if (w.on) opts.push({ t: w.ticker, n: w.name || w.ticker });
  });
  sel.innerHTML = opts.map((o) => `<option value="${o.t}">${o.n} ${o.t}</option>`).join("");
  sel.dataset.ready = "1";
  sel.onchange = () => loadCurves();
}

function loadCurves() {
  fillCurveTickers();
  const t = ($("curveTicker") && $("curveTicker").value) || "^TWII";
  fetch("/api/curves?ticker=" + encodeURIComponent(t) + "&n=" + curveN).then((r) => r.json()).then(drawCurves).catch(() => {});
}

function mkChart(el, h) {
  return LightweightCharts.createChart(el, {
    layout: { background: { color: "#161b22" }, textColor: "#8b949e" },
    grid: { vertLines: { color: "#222" }, horzLines: { color: "#222" } },
    width: el.clientWidth,
    height: h,
  });
}

function drawCurves(j) {
  if (!window.LightweightCharts) return;
  const pe = $("curvePrice"), me = $("curveMacd"), re = $("curveRsi"), ke = $("curveKd");
  if (!pe) return;
  if (!cPrice) {
    cPrice = mkChart(pe, 360);
    cCandle = cPrice.addCandlestickSeries({
      upColor: "#e53935", downColor: "#43a047",
      borderUpColor: "#e53935", borderDownColor: "#43a047",
      wickUpColor: "#e53935", wickDownColor: "#43a047",
    });
    cSma20 = cPrice.addLineSeries({ color: "#58a6ff", lineWidth: 1 });
    cSma60 = cPrice.addLineSeries({ color: "#f9a825", lineWidth: 1 });
    cMacd = mkChart(me, 220);
    cMacdLine = cMacd.addLineSeries({ color: "#58a6ff", lineWidth: 1 });
    cMacdSig = cMacd.addLineSeries({ color: "#f9a825", lineWidth: 1 });
    cHist = cMacd.addHistogramSeries();
    cRsi = mkChart(re, 220);
    cRsiLine = cRsi.addLineSeries({ color: "#d2a8ff", lineWidth: 2 });
    cKd = mkChart(ke, 220);
    cK = cKd.addLineSeries({ color: "#58a6ff", lineWidth: 1 });
    cD = cKd.addLineSeries({ color: "#e53935", lineWidth: 1 });
  }
  cCandle.setData(j.bars || []);
  cSma20.setData(j.sma20 || []);
  cSma60.setData(j.sma60 || []);
  cMacdLine.setData(j.macd || []);
  cMacdSig.setData(j.macd_sig || []);
  cHist.setData((j.macd_hist || []).map((p) => ({ time: p.time, value: p.value, color: p.value >= 0 ? "#e53935" : "#43a047" })));
  cRsiLine.setData(j.rsi || []);
  cK.setData(j.k || []);
  cD.setData(j.d || []);
}

document.querySelectorAll("#curveN button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("#curveN button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    curveN = Number(b.dataset.n);
    loadCurves();
  };
});

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(proto + "://" + location.host + "/ws");
  ws.onopen = () => { $("wsDot").classList.add("on"); $("wsDot").classList.remove("off"); };
  ws.onclose = () => { $("wsDot").classList.remove("on"); setTimeout(connect, 1500); };
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "state") { state = msg.data; render(state); }
    } catch (e) {}
  };
}
connect();
fetch("/api/state").then((r) => r.json()).then((s) => { state = s; render(s); }).catch(() => {});
