const $ = (id) => document.getElementById(id);
let state = null;
let twiiChart, candleSeries, smaSeries, eqChart, eqSeries;
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
    if (b.dataset.tab === "over") resizeCharts();
    if (b.dataset.tab === "pnl") resizeCharts();
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
  drawTwii(tw);
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
