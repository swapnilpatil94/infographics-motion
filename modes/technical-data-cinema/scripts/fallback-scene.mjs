export function buildFallbackScene({ title, story, plan }) {
  const beats = (Array.isArray(plan?.beats) ? plan.beats : []).slice(0, 12).map((beat, index) => ({
    start: Number.isFinite(Number(beat.start)) ? Math.max(0, Number(beat.start)) : index * 4,
    end: Number.isFinite(Number(beat.end)) ? Math.max(0.5, Number(beat.end)) : (index + 1) * 4,
    idea: String(beat.narration_idea || beat.viewer_takeaway || beat.dominant_subject || `Visual beat ${index + 1}`).slice(0, 150),
    subject: String(beat.dominant_subject || beat.visual_grammar || "SYSTEM").slice(0, 90),
    action: String(beat.action_and_causal_proof || beat.viewer_takeaway || "Observe how the system changes").slice(0, 180),
    grammar: String(beat.visual_grammar || "transformation"),
    labels: Array.isArray(beat.overlay_text) ? beat.overlay_text.slice(0, 3).map(String) : []
  }));
  if (beats.length < 4) throw new Error("Cannot build safe fallback: visual plan needs at least four beats.");
  const duration = Math.max(8, Math.min(600, ...[beats[beats.length - 1].end].filter(Number.isFinite)));
  const safeJson = value => JSON.stringify(value).replace(/</g, "\\u003c").replace(/>/g, "\\u003e").replace(/&/g, "\\u0026");
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${String(title).replace(/[&<>"]/g, "")}</title>
<style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#07110f;color:#f5f1e8;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;overflow:hidden}
#stage{width:100vw;height:100vh;display:block;background:radial-gradient(ellipse at 50% 44%,#15332b 0%,#0b1c18 48%,#050b0a 100%)}
.kicker{font-size:24px;letter-spacing:5px;fill:#d9a441;font-weight:800}.headline{font-size:54px;fill:#fff8e9;font-weight:850}.sub{font-size:28px;fill:#c6d3ca}.micro{font-size:23px;fill:#e3b44f;font-weight:700;letter-spacing:2px}
#subject{fill:#112d25;stroke:#e0ae47;stroke-width:5}#orbit{fill:none;stroke:#4d8c74;stroke-width:3;stroke-dasharray:12 15}#core{fill:#e5b44e}#flow{stroke:#e5b44e;stroke-width:8;stroke-linecap:round;fill:none}#dot{fill:#fff4d6}
#progress{stroke:#dba83f;stroke-width:8;stroke-linecap:round}#base{stroke:#37574b;stroke-width:8;stroke-linecap:round}
#footer{font-size:22px;fill:#91a99b;letter-spacing:3px}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
</style></head><body><svg id="stage" viewBox="0 0 1080 1920" role="img" aria-label="Animated explainer visual fallback">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#204c3d"/><stop offset="1" stop-color="#0b1915"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="14"/></filter></defs>
<g id="grain" opacity=".35"></g>
<text x="76" y="115" class="kicker">VISUAL EXPLAINER / STORY MODE</text>
<text id="beatNo" x="78" y="220" class="micro">BEAT 01</text>
<text id="headline" x="76" y="305" class="headline">Story mechanism</text>
<text id="description" x="78" y="365" class="sub">Cause → effect → consequence</text>
<g id="mechanism" transform="translate(540 940)">
  <circle id="halo" r="300" fill="#dba83f" opacity=".08" filter="url(#glow)"/>
  <circle id="orbit" r="250"/>
  <circle id="orbit2" r="180" fill="none" stroke="#3c705c" stroke-width="2" stroke-dasharray="4 17"/>
  <path id="flow" d="M-300 0 C-170 -110,-90 120,0 0 S170 -100,300 0"/>
  <rect id="subject" x="-175" y="-175" width="350" height="350" rx="48" fill="url(#g)"/>
  <circle id="core" r="64"/>
  <circle id="dot" cx="-245" cy="0" r="18"/>
  <g id="nodes"></g>
  <text id="subjectText" text-anchor="middle" y="12" font-size="28" font-weight="850" fill="#f9f0da">SYSTEM</text>
</g>
<text id="action" x="76" y="1390" class="headline" style="font-size:38px">Watch the relationship change</text>
<g id="labels"></g>
<line id="base" x1="78" y1="1760" x2="1002" y2="1760"/>
<line id="progress" x1="78" y1="1760" x2="78" y2="1760"/>
<text id="footer" x="78" y="1830">A VISUAL MODEL · NOT A DATA SOURCE</text>
</svg><script>
const BEATS=${safeJson(beats)}, DURATION=${duration};
const $=id=>document.getElementById(id);
const NS="http://www.w3.org/2000/svg";
function el(name,attrs={}){const e=document.createElementNS(NS,name);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);return e}
function drawNodes(index){const group=$("nodes");group.replaceChildren();const count=7+(index%5);for(let i=0;i<count;i++){const a=(Math.PI*2*i/count)+(index*.31),r=218+(i%3)*25,x=Math.cos(a)*r,y=Math.sin(a)*r;group.append(el("circle",{cx:x.toFixed(2),cy:y.toFixed(2),r:i%3===0?13:8,fill:i%2?"#75b89a":"#e5b44e",opacity:.92}));if(i<count-1){const b=a+Math.PI*2/count;group.append(el("line",{x1:x.toFixed(2),y1:y.toFixed(2),x2:(Math.cos(b)*r).toFixed(2),y2:(Math.sin(b)*r).toFixed(2),stroke:"#578c74","stroke-width":2,opacity:.55}))}}}
function setText(id,value){$(id).textContent=String(value||"")}
function renderAt(seconds){const t=Math.max(0,Math.min(DURATION,Number(seconds)||0));let index=BEATS.findIndex((b,i)=>t>=b.start&&(t<b.end||i===BEATS.length-1));if(index<0)index=BEATS.length-1;const b=BEATS[index],local=Math.max(0,Math.min(1,(t-b.start)/Math.max(.01,b.end-b.start)));drawNodes(index);setText("beatNo","BEAT "+String(index+1).padStart(2,"0")+" / "+String(BEATS.length).padStart(2,"0"));setText("headline",b.idea);setText("description",b.grammar.replace(/_/g," ").toUpperCase());setText("action",b.action);setText("subjectText",b.subject.toUpperCase().slice(0,18));$("mechanism").setAttribute("transform","translate(540 940) rotate("+((index%2?1:-1)*local*5).toFixed(2)+") scale("+(0.96+0.04*Math.sin(local*Math.PI)).toFixed(3)+")");$("dot").setAttribute("cx",(-245+490*local).toFixed(2));$("core").setAttribute("r",(52+12*Math.sin(local*Math.PI)).toFixed(2));$("orbit").setAttribute("transform","rotate("+(index*13+local*16)+")");$("progress").setAttribute("x2",(78+924*t/DURATION).toFixed(2));$("labels").replaceChildren();b.labels.forEach((label,i)=>{const g=el("g",{transform:"translate(78 "+(1500+i*62)+")"});g.append(el("circle",{cx:12,cy:-8,r:7,fill:"#e5b44e"}));const tx=el("text",{x:36,y:0,fill:"#e9e2d1","font-size":25});tx.textContent=label.slice(0,48);g.append(tx);$("labels").append(g)});$("halo").setAttribute("opacity",(.05+.06*Math.sin(local*Math.PI)).toFixed(3));}
window.renderAt=renderAt;window.getDuration=()=>DURATION;
if(new URLSearchParams(window.location.search).get("render")!=="1"){document.body.insertAdjacentHTML("beforeend",'<div style="position:fixed;bottom:12px;right:12px;color:#9bb4a7;font:12px system-ui">SAFE FALLBACK · review visuals before publishing</div>')}
renderAt(0);
</script></body></html>`;
}
