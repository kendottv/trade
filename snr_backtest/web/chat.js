/* 浮動交易教練泡泡：可拖曳（滑鼠/觸控）、放開吸附左右邊緣、位置存 localStorage。點一下開關聊天視窗。 */
(function(){
 const KEY='coachBubblePos',S=56,M=12;
 const css=`#cb{position:fixed;width:${S}px;height:${S}px;border-radius:50%;background:#1f6feb;box-shadow:0 4px 14px rgba(0,0,0,.5);z-index:9999;cursor:grab;touch-action:none;display:flex;align-items:center;justify-content:center;transition:left .2s,top .2s;user-select:none}
#cb.drag{transition:none;cursor:grabbing}#cb .dot{position:absolute;top:4px;right:4px;width:12px;height:12px;border-radius:50%;background:#e53935;border:2px solid #0e1117;display:none}
#cb.unread .dot{display:block}#cw{position:fixed;width:min(400px,calc(100vw - 24px));height:min(600px,calc(100vh - 100px));background:#161b22;border:1px solid #30363d;border-radius:14px;z-index:9998;display:none;flex-direction:column;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,.6)}
#cw.open{display:flex}#cw .bar{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-bottom:1px solid #30363d;color:#e6edf3;font-weight:600}
#cw .x{background:none;border:0;color:#8b949e;font-size:22px;cursor:pointer;line-height:1}#cw .x:hover{color:#e6edf3}#cw iframe{flex:1;border:0;width:100%;background:#0e1117}
#cw .off{padding:24px;color:#8b949e;text-align:center}#cw .off code{color:#e6edf3;background:#0e1117;padding:2px 6px;border-radius:4px}#cw .off button{margin-top:12px;background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:6px 14px;cursor:pointer}`;
 const st=document.createElement('style');st.textContent=css;document.head.appendChild(st);
 const b=document.createElement('div');b.id='cb';b.title='交易教練';b.setAttribute('role','button');b.setAttribute('aria-label','開啟交易教練');
 b.innerHTML=`<svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true"><line x1="16" y1="3" x2="16" y2="8" stroke="#e6edf3" stroke-width="2" stroke-linecap="round"/><circle cx="16" cy="3" r="2" fill="#e6edf3"/>
<rect x="5" y="8" width="22" height="18" rx="6" fill="#e6edf3"/><rect x="2" y="14" width="3" height="7" rx="1.5" fill="#e6edf3"/><rect x="27" y="14" width="3" height="7" rx="1.5" fill="#e6edf3"/>
<circle cx="12" cy="16" r="2.6" fill="#1f6feb"/><circle cx="20" cy="16" r="2.6" fill="#1f6feb"/><rect x="11" y="21" width="10" height="2" rx="1" fill="#1f6feb"/></svg><span class="dot"></span>`;
 const w=document.createElement('div');w.id='cw';w.innerHTML='<div class="bar"><span>交易教練</span><button class="x" aria-label="關閉">×</button></div><div class="body"></div>';
 document.body.append(w,b);const body=w.querySelector('.body');body.style.cssText='flex:1;display:flex';
 let pos=JSON.parse(localStorage.getItem(KEY)||'null')||{side:'right',y:0.8};
 const place=()=>{const H=innerHeight;b.style.top=Math.min(Math.max(M,pos.y*H-S/2),H-S-M)+'px';b.style.left=(pos.side==='left'?M:innerWidth-S-M)+'px';if(w.classList.contains('open'))anchor()};
 const anchor=()=>{const r=b.getBoundingClientRect(),ww=w.offsetWidth,wh=w.offsetHeight;let x=pos.side==='left'?r.right+8:r.left-ww-8;
  if(innerWidth<ww+S+40)x=(innerWidth-ww)/2;let y=Math.min(Math.max(M,r.top+S/2-wh/2),innerHeight-wh-M);w.style.left=Math.max(M,x)+'px';w.style.top=y+'px'};
 let loaded=false;
 async function fill(){let s={up:false,hint:'教練未啟動，執行 D:\\trade-coach\\run.ps1'};try{s=await (await fetch('/api/coach/status')).json()}catch(e){}
  if(s.up){if(!loaded){body.innerHTML=`<iframe src="${s.url}/embed" title="trade-coach"></iframe>`;loaded=true}}
  else{loaded=false;body.innerHTML=`<div class="off">教練未啟動，執行 <code>D:\\trade-coach\\run.ps1</code><br><button>重新檢查</button></div>`;body.querySelector('button').onclick=fill}return s.up}
 const toggle=()=>{const o=w.classList.toggle('open');if(o){b.classList.remove('unread');sessionStorage.setItem('coachSeen','1');fill();anchor()}};
 w.querySelector('.x').onclick=()=>w.classList.remove('open');
 let sx,sy,ox,oy,moved=false,down=false;
 b.addEventListener('pointerdown',e=>{down=true;moved=false;sx=e.clientX;sy=e.clientY;const r=b.getBoundingClientRect();ox=sx-r.left;oy=sy-r.top;b.setPointerCapture(e.pointerId)});
 b.addEventListener('pointermove',e=>{if(!down)return;if(!moved&&Math.hypot(e.clientX-sx,e.clientY-sy)<6)return;moved=true;b.classList.add('drag');
  b.style.left=Math.min(Math.max(0,e.clientX-ox),innerWidth-S)+'px';b.style.top=Math.min(Math.max(0,e.clientY-oy),innerHeight-S)+'px';if(w.classList.contains('open'))anchor()});
 const up=e=>{if(!down)return;down=false;b.classList.remove('drag');if(!moved){toggle();return}
  const r=b.getBoundingClientRect();pos={side:(r.left+S/2)<innerWidth/2?'left':'right',y:(r.top+S/2)/innerHeight};localStorage.setItem(KEY,JSON.stringify(pos));place()};
 b.addEventListener('pointerup',up);b.addEventListener('pointercancel',up);
 b.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();toggle()}});b.tabIndex=0;
 addEventListener('resize',place);place();if(location.hash==='#coach')toggle();
 fetch('/api/coach/status').then(r=>r.json()).then(s=>{if(s.up&&!sessionStorage.getItem('coachSeen'))b.classList.add('unread')}).catch(()=>{});
})();