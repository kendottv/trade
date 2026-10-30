const $=id=>document.getElementById(id);
const nf=(x,d=0)=>x==null?'—':Number(x).toLocaleString('zh-TW',{maximumFractionDigits:d,minimumFractionDigits:d});
const pct=(x,d=2)=>x==null||isNaN(x)?'—':(x*100).toFixed(d)+'%';
const spct=(x,d=2)=>x==null||isNaN(x)?'—':(x>0?'+':x<0?'−':'')+Math.abs(x*100).toFixed(d)+'%';
const snf=(x,d=0)=>x==null?'—':(x>0?'+':x<0?'−':'')+nf(Math.abs(x),d);
const abbr=v=>{const a=Math.abs(v);return a>=1e8?(v/1e8).toFixed(2)+'億':a>=1e4?(v/1e4).toFixed(a>=1e6?0:1)+'萬':nf(v)};
const cls=x=>x>0?'up':x<0?'dn':'';
function line(el,series,opts){const W=640,H=200,P=28;const all=series.flatMap(s=>s.pts.filter(v=>v!=null));
 if(!all.length){el.innerHTML='<div class="cap">尚無資料</div>';return}
 let lo=Math.min(...all),hi=Math.max(...all);if(hi===lo){hi+=Math.abs(hi)*.01||1;lo-=Math.abs(lo)*.01||1}
 const n=Math.max(...series.map(s=>s.pts.length));const X=i=>P+(n<2?(W-2*P)/2:i*(W-2*P)/(n-1)),Y=v=>H-P-(v-lo)/(hi-lo)*(H-2*P);
 let g=`<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><line x1="${P}" x2="${W-P}" y1="${H-P}" y2="${H-P}" class="ax"/>`;
 if(opts&&opts.zero&&lo<0&&hi>0)g+=`<line x1="${P}" x2="${W-P}" y1="${Y(0)}" y2="${Y(0)}" class="zero"/>`;
 series.forEach(s=>{const d=s.pts.map((v,i)=>v==null?null:`${X(i)},${Y(v)}`).filter(Boolean);
  g+=d.length>1?`<polyline points="${d.join(' ')}" class="ln" style="stroke:${s.color}"/>`:d.map(p=>`<circle cx="${p.split(',')[0]}" cy="${p.split(',')[1]}" r="4" fill="${s.color}"/>`).join('')});
 g+=`<text x="${P}" y="14" class="lbl">${opts.fmt(hi)}</text><text x="${P}" y="${H-6}" class="lbl">${opts.fmt(lo)}</text>`;
 if(opts.x)g+=`<text x="${W-P}" y="${H-6}" class="lbl" text-anchor="end">${opts.x}</text>`;
 el.innerHTML=g+'</svg>'+(opts.legend?`<div class="legend">${series.map(s=>`<span><i style="background:${s.color}"></i>${s.name}</span>`).join('')}</div>`:'')}
async function load(){let s;const E=$('err');try{const ac=new AbortController();const to=setTimeout(()=>ac.abort(),15000);const r=await fetch('/api/state',{signal:ac.signal,cache:'no-store'});clearTimeout(to);if(!r.ok)throw new Error('HTTP '+r.status);s=await r.json();E.hidden=true}catch(e){E.hidden=false;E.textContent='資料載入失敗：'+(e.name==='AbortError'?'逾時 15 秒':e.message)+'。請確認面板有在跑（start_dashboard.bat），按 Ctrl+F5 重新整理。';if($('strat').textContent==='載入中…')$('strat').textContent='載入失敗';return}
 try{render(s)}catch(e){E.hidden=false;E.textContent='畫面錯誤：'+e.message;console.error(e)}}
function render(s){const a=s.account;
 $('strat').textContent=`${s.strategy.label} · 目標月份 ${a.target_month||'—'} · 更新 ${a.as_of||'—'}`;
 $('metrics').innerHTML=[['權益',nf(a.equity)],['現金',nf(a.cash)],['損益',`<span class="${cls(a.pnl)}">${snf(a.pnl)}</span>`,`<span class="${cls(a.pnl)}">${spct(a.initial?a.pnl/a.initial:0)}</span>`],['持股',a.positions.length+' 檔'],['初始資金',nf(a.initial)]]
  .map(([k,v,d])=>`<div class="metric"><div class="k">${k}</div><div class="v">${v}</div>${d?`<div class="d">${d}</div>`:''}</div>`).join('');
 EQ.a=a;eqDraw();
 $('pos').innerHTML='<tr><th class="l">股票</th><th>股數</th><th>權重</th><th>成本</th><th>現價</th><th>損益</th><th>報酬</th><th>NN名次</th></tr>'+a.positions.map(p=>
  `<tr><td class="l">${p.name}</td><td>${nf(p.shares)}</td><td>${pct(p.weight)}</td><td>${nf(p.avg,2)}</td><td>${nf(p.last,2)}</td><td class="${cls(p.pnl)}">${snf(p.pnl)}</td><td class="${cls(p.pnl)}">${spct(p.pnl_pct)}</td><td>${p.nn_rank??''}</td></tr>`).join('');
 const w=s.watchlist;$('wlcap').textContent=`${w.mon||''} 月底資料 · ${w.model||''}`;
 $('wl').innerHTML='<tr><th>#</th><th class="l">代號</th><th>預測超額</th><th>全市場</th><th>十分位</th></tr>'+(w.records||[]).map(r=>
  `<tr class="${r.code=='6197'?'hl':''}"><td>${r.watch_rank}</td><td class="l">${r.label||r.code}${r.code=='6197'?' ★':''}</td><td class="${cls(r.pred_excess_ret)}">${spct(r.pred_excess_ret)}</td><td>${r.rank}/${r.n_stocks}</td><td>${r.decile}</td></tr>`).join('');
 const R=s.research;$('rscap').textContent=`⚠ ${R.note}（${R.mon||''}）`;
 $('rs').innerHTML='<tr><th>#</th><th class="l">股票</th><th>預測超額</th></tr>'+R.rows.map(r=>`<tr><td>${r.rank}</td><td class="l">${r.name}</td><td class="${cls(r.pred)}">${pct(r.pred,2)}</td></tr>`).join('');
 const m=s.monitor,L=m.latest||{};$('moncap').innerHTML=`最新 ${L.mon||'—'}：IC ${nf(L.ic,3)} · 12月滾動 IC ${nf(L.ic12,3)} · 12月命中率 ${nf(L.hit12,0)}% · 全期平均 IC ${nf(m.ic_mean_all,3)}（${pct(m.ic_pos_share,0)} 月份為正，共 ${m.n_months} 月）${m.neg_streak>=3?' · <span class="dn">IC 連續轉負 '+m.neg_streak+' 月</span>':''}`;
 const sr=m.series.slice(-60);line($('mon'),[{name:'12月滾動 IC',color:'#58a6ff',pts:sr.map(r=>r.ic12)},{name:'12月命中率 ÷100',color:'#3fb950',pts:sr.map(r=>r.hit12==null?null:r.hit12/100)}],{fmt:v=>v.toFixed(2),zero:true,legend:true,x:sr.length?sr[0].mon.slice(0,7)+' → '+sr.at(-1).mon.slice(0,7):''});
 const N=s.news;$('newscap').textContent=`${N.note} · ${N.as_of?N.as_of.slice(0,16):'尚未抓取'} · ${N.count||0} 則`;
 const lk=h=>`<li><a href="${h.link}" target="_blank" rel="noopener">${h.title}</a>${h.held?` <span class="tag">${h.held.join('、')}</span>`:''}</li>`;
 $('news').innerHTML=`<div class="chips">${N.keywords.map(k=>`<span class="chip">${k.keyword} ${k.count}</span>`).join('')}</div>`+
  (N.held.length?`<h3>提到持股</h3><ul class="nl">${N.held.map(lk).join('')}</ul>`:'')+`<h3>頭條</h3><ul class="nl">${N.headlines.map(lk).join('')}</ul>`;}
function tk(name,q){if(!q||!q.ok)return `<div class="tk"><span class="n">${name}</span><span class="v">—</span><span class="cap">${q?q.reason:'無資料'}</span></div>`;
 const c=q.chg>0?'up':q.chg<0?'dn':'';const sg=q.chg>0?'+':'';
 return `<div class="tk"><span class="n">${name}${q.status?` <em class="st ${q.status==='盤中'?'live':''}">${q.status}</em>`:''}</span><span class="v">${nf(q.last,2)}</span><span class="${c}">${snf(q.chg,2)}（${q.pct==null?'—':spct(q.pct/100)}）</span><span class="cap">${q.ts}${q.delayed?' 延遲':''}</span></div>`}
async function loadTicker(){try{const ac=new AbortController();setTimeout(()=>ac.abort(),8000);const t=await (await fetch('/api/ticker',{signal:ac.signal,cache:'no-store'})).json();
 $('ticker').innerHTML=tk('加權指數',t.taiex)+tk('台指期夜盤',t.txf)+`<span class="cap upd">更新 ${t.updated||'—'}</span>`}catch(e){$('ticker').innerHTML='<span class="cap">行情載入失敗：'+e.message+'</span>'}}
load();setInterval(load,60000);loadTicker();setInterval(loadTicker,30000);
// ---- 權益曲線 ----
const EQ={a:null,bench:[],benchReason:'',range:'ALL'};
async function loadBench(){try{const b=await (await fetch('/api/bench',{cache:'no-store'})).json();EQ.bench=b.data||[];EQ.benchReason=b.reason||'';if(EQ.a)eqDraw()}catch(e){EQ.benchReason='加權指數日線載入失敗'}}
document.querySelectorAll('#eqtabs button').forEach(b=>b.onclick=()=>{EQ.range=b.dataset.r;document.querySelectorAll('#eqtabs button').forEach(x=>x.classList.toggle('on',x===b));eqDraw()});
window.addEventListener('resize',()=>EQ.a&&eqDraw());
function eqRange(c){if(EQ.range==='ALL'||!c.length)return c;const end=new Date(c.at(-1).date);let s;
 if(EQ.range==='YTD')s=new Date(end.getFullYear(),0,1);else{s=new Date(end);s.setMonth(s.getMonth()-(EQ.range==='1M'?1:3))}
 const k=s.toISOString().slice(0,10);return c.filter(r=>r.date>=k)}
function smooth(p){if(p.length<3)return p.map((q,i)=>(i?'L':'M')+q[0]+','+q[1]).join('');let d='M'+p[0];
 for(let i=0;i<p.length-1;i++){const a=p[i-1]||p[i],b=p[i],c=p[i+1],e=p[i+2]||c,t=.18;
  d+=`C${b[0]+(c[0]-a[0])*t},${b[1]+(c[1]-a[1])*t} ${c[0]-(e[0]-b[0])*t},${c[1]-(e[1]-b[1])*t} ${c[0]},${c[1]}`}return d}
function eqDraw(){const a=EQ.a,el=$('curve'),init=a.initial||0,all=a.curve.filter(r=>r.equity!=null);
 if(all.length<3){const pl=a.equity-init;$('eqtabs').style.visibility='hidden';
  el.innerHTML=`<div class="eqsum"><div><div class="k">目前權益</div><div class="big">NT$ ${nf(a.equity)}</div></div>
   <div><div class="k">累積損益</div><div class="mid ${cls(pl)}">${snf(pl)}</div></div>
   <div><div class="k">報酬率</div><div class="mid ${cls(pl)}">${spct(init?pl/init:null)}</div></div>
   <div><div class="k">起始日</div><div class="mid">${all[0]?all[0].date:'—'}</div></div>
   <div class="note">資料累積中 · 目前 ${all.length} 個交易日，滿 3 日後顯示曲線</div></div>`;return}
 $('eqtabs').style.visibility='';const c=eqRange(all).length>=2?eqRange(all):all;
 const W=Math.max(320,el.clientWidth||900),H=Math.round(Math.min(320,Math.max(200,W*.28))),L=64,R=14,T=14,B=26;
 const bm=new Map(EQ.bench.map(r=>[r.date,r.close]));const b0=c.map(r=>bm.get(r.date)).find(v=>v);const base=c[0].equity;
 const bp=b0?c.map(r=>bm.has(r.date)?base*bm.get(r.date)/b0:null):[];
 const vals=c.map(r=>r.equity).concat(bp.filter(v=>v!=null),[init]);let lo=Math.min(...vals),hi=Math.max(...vals);const pad=(hi-lo)*.08||hi*.005;lo-=pad;hi+=pad;
 const X=i=>L+i*(W-L-R)/(c.length-1),Y=v=>T+(hi-v)/(hi-lo)*(H-T-B);const up=c.at(-1).equity>=init,col=up?'#f85149':'#3fb950';
 const pts=c.map((r,i)=>[X(i),Y(r.equity)]);const ln=smooth(pts);
 let g=`<svg width="${W}" height="${H}" class="eq"><defs><linearGradient id="eqg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".35"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>`;
 for(let k=0;k<=4;k++){const v=lo+(hi-lo)*k/4,y=Y(v);g+=`<line x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" class="grid"/><text x="${L-8}" y="${y+4}" class="lbl" text-anchor="end">${abbr(v)}</text>`}
 g+=`<line x1="${L}" x2="${W-R}" y1="${Y(init)}" y2="${Y(init)}" class="base"/>`;
 const nx=Math.min(6,c.length);for(let k=0;k<nx;k++){const i=Math.round(k*(c.length-1)/(nx-1));g+=`<text x="${X(i)}" y="${H-6}" class="lbl" text-anchor="${k==0?'start':k==nx-1?'end':'middle'}">${c[i].date.slice(5)}</text>`}
 g+=`<path d="${ln}L${X(c.length-1)},${H-B}L${L},${H-B}Z" fill="url(#eqg)"/><path d="${ln}" fill="none" stroke="${col}" stroke-width="2"/>`;
 if(b0){const bpts=bp.map((v,i)=>v==null?null:[X(i),Y(v)]).filter(Boolean);g+=`<path d="${smooth(bpts)}" fill="none" stroke="#8b949e" stroke-width="1.4" stroke-dasharray="4 3"/>`}
 g+=`<line id="eqx" y1="${T}" y2="${H-B}" class="cross" visibility="hidden"/><circle id="eqd" r="4" fill="${col}" stroke="#0d1117" stroke-width="2" visibility="hidden"/><rect x="${L}" y="${T}" width="${W-L-R}" height="${H-T-B}" fill="transparent" id="eqhit"/></svg>`;
 const lg=`<div class="legend"><span><i style="background:${col}"></i>權益</span>${b0?'<span><i class="dash"></i>加權指數（同起點）</span>':`<span class="cap">加權指數：${EQ.benchReason||'無同期資料'}</span>`}<span class="cap">虛線基準 = 初始資金 NT$ ${nf(init)}</span></div>`;
 el.innerHTML=g+'<div class="tip" id="eqtip" hidden></div>'+lg;
 const hit=$('eqhit'),tip=$('eqtip');hit.onmouseleave=()=>{tip.hidden=true;$('eqx').setAttribute('visibility','hidden');$('eqd').setAttribute('visibility','hidden')};
 hit.onmousemove=ev=>{const r=hit.getBoundingClientRect(),i=Math.max(0,Math.min(c.length-1,Math.round((ev.clientX-r.left)/(r.width)*(c.length-1)))),x=X(i),y=Y(c[i].equity);
  $('eqx').setAttribute('x1',x);$('eqx').setAttribute('x2',x);$('eqx').setAttribute('visibility','visible');$('eqd').setAttribute('cx',x);$('eqd').setAttribute('cy',y);$('eqd').setAttribute('visibility','visible');
  const dc=i?c[i].equity-c[i-1].equity:null,cu=init?c[i].equity/init-1:null;
  tip.innerHTML=`<b>${c[i].date}</b><div>權益 NT$ ${nf(c[i].equity)}</div><div>當日 <span class="${cls(dc)}">${snf(dc)}</span></div><div>累積 <span class="${cls(cu)}">${spct(cu)}</span></div>${bp[i]!=null?`<div class="cap">加權指數 ${spct(bp[i]/base-1)}</div>`:''}`;
  tip.hidden=false;tip.style.left=Math.min(x+12,W-170)+'px';tip.style.top=Math.max(4,y-70)+'px'}}
loadBench();setInterval(loadBench,3600000);
