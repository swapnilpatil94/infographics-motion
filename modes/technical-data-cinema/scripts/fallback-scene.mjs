const clean = value => String(value ?? "").replace(/\s+/g, " ").trim().slice(0, 220);
const clamp = (v,a,b)=>Math.max(a,Math.min(b,v));
export function buildFallbackScene({title,story,plan}) {
 const source=Array.isArray(plan?.beats)?plan.beats:[];
 const beats=source.slice(0,18).map((b,i)=>({start:Number.isFinite(Number(b.start))?Math.max(0,Number(b.start)):i*4,end:Number.isFinite(Number(b.end))?Math.max(.5,Number(b.end)):(i+1)*4,idea:clean(b.narration_idea||b.viewer_takeaway||b.dominant_subject||("Visual beat "+(i+1))),subject:clean(b.dominant_subject||"SYSTEM"),action:clean(b.action_and_causal_proof||b.viewer_takeaway||"Follow the cause and its consequence"),grammar:String(b.visual_grammar||"transformation").toLowerCase().replace(/[^a-z0-9_-]/g,""),labels:Array.isArray(b.overlay_text)?b.overlay_text.slice(0,3).map(clean).filter(Boolean):[]}));
 if(beats.length<4)throw new Error("Cannot build safe fallback: visual plan needs at least four beats.");
 beats.forEach((b,i)=>{if(b.end<=b.start)b.end=b.start+1;if(i&&b.start<beats[i-1].start)b.start=beats[i-1].start;});
 const duration=clamp(Math.max(...beats.map(b=>b.end)),4,600);
 const json=JSON.stringify(beats).replace(/</g,"\\u003c").replace(/>/g,"\\u003e").replace(/&/g,"\\u0026");
 const safeTitle=clean(title).replace(/[&<>"]/g,"");
 const mythology=/mytholog|epic|ramayana|mahabharat|draupadi|yudhishthir|krishna|pandava|dharma|arjuna|bhima|karna|rama|sita|hanuman|shiva|parvati|durga|vishnu|lakshmi|saraswati|ravana|ganesha|पुराण|महाभारत|रामायण|द्रौपदी|युधिष्ठिर|कृष्ण|धर्म|अर्जुन|भीम|कर्ण|राम|सीता|हनुमान|शिव|पार्वती|दुर्गा|विष्णु|लक्ष्मी|सरस्वती|रावण|गणेश|देवता|देवी/i.test([title,story,...beats.map(b=>b.subject+" "+b.idea+" "+b.action)].join(" "));
 const theme=mythology?"mythology":"technical";
 return String.raw`<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
*{box-sizing:border-box}html,body{margin:0;width:100%;height:100%;background:#050607;font-family:Inter,ui-sans-serif,system-ui,sans-serif;overflow:hidden}
#stage{width:100vw;height:100vh;display:block;background:radial-gradient(ellipse at 50% 47%,#11171b 0%,#07090b 48%,#030405 100%)}
#stage[data-theme="mythology"]{background:radial-gradient(ellipse at 50% 43%,#30251b 0%,#100e0d 42%,#030303 100%)}
#stage[data-theme="mythology"] .panel{fill:#17120e!important;stroke:#b88a43!important}
#stage[data-theme="mythology"] .rule{stroke:#8d6a37!important}
#stage[data-theme="mythology"] .green{stroke:#e6c477!important}
#stage[data-theme="mythology"] .gold{stroke:#f0c56c!important}
#stage[data-theme="mythology"] .node{fill:#df493b!important;stroke:#1b130e!important}
#stage[data-theme="mythology"] text{fill:#f5e8c8!important}
#stage[data-theme="mythology"] .micro,#stage[data-theme="mythology"] .kicker{fill:#e34b3d!important}
#stage[data-theme="mythology"] #dotGrid circle{fill:#d6a84e!important;opacity:.34}
.kicker{font-size:22px;letter-spacing:4px;fill:#e64b36;font-weight:800}.micro{font-size:22px;fill:#e64b36;font-weight:750;letter-spacing:2px}.headline{font-size:54px;fill:#fff8e9;font-weight:850}.sub{font-size:25px;fill:#c4cbd0}.action{font-size:31px;fill:#f5f7f8;font-weight:700}.label{font-size:24px;fill:#d9e3d8}.footer{font-size:19px;fill:#858d95;letter-spacing:2px}.rule{stroke:#3b4249;stroke-width:3;fill:none}.gold{stroke:#e64b36;fill:none;stroke-width:6;stroke-linecap:round;stroke-linejoin:round}.green{stroke:#f5f7f8;fill:none;stroke-width:4;stroke-linecap:round;stroke-linejoin:round}.panel{fill:#0b0d10;stroke:#3e725b;stroke-width:3}.node{fill:#e64b36;stroke:#0b0d10;stroke-width:3}
</style></head><body><svg id="stage" data-theme="__THEME_ATTR__" viewBox="0 0 1080 1920" role="img" aria-label="Story-driven animated explainer">
<defs><pattern id="dotGrid" width="24" height="24" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.2" fill="#f5f7f8" opacity=".22"/></pattern><linearGradient id="panelFill" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#171c21"/><stop offset="1" stop-color="#080a0d"/></linearGradient><filter id="glow"><feGaussianBlur stdDeviation="15"/></filter></defs>
<rect width="1080" height="1920" fill="url(#dotGrid)" opacity=".42"/>
<text x="76" y="108" class="kicker">VISUAL EXPLAINER / STORY MODE</text><text id="beatNo" x="78" y="192" class="micro"></text><text id="headline" x="76" y="280" class="headline"></text><text id="description" x="78" y="400" class="sub"></text><line x1="78" y1="445" x2="1002" y2="445" class="rule" opacity=".55"/>
<g id="sceneArt"></g><text id="action" x="78" y="1378" class="action"></text><g id="labels"></g>
<line x1="78" y1="1760" x2="1002" y2="1760" class="rule" opacity=".65"/><line id="progress" x1="78" y1="1760" x2="78" y2="1760" stroke="#dba83f" stroke-width="8" stroke-linecap="round"/><text x="78" y="1830" class="footer">ILLUSTRATIVE VISUAL MODEL · NOT A DATA SOURCE</text></svg>
<script>
const BEATS=__BEATS__,DURATION=__DURATION__,THEME=__THEME__, $=id=>document.getElementById(id),NS="http://www.w3.org/2000/svg",clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function el(n,a){const e=document.createElementNS(NS,n);Object.entries(a||{}).forEach(([k,v])=>e.setAttribute(k,String(v)));return e}
function add(p,n,a,t){const e=el(n,a);if(t!==undefined)e.textContent=t;p.append(e);return e}
function wrap(p,text,x,y,max,lineHeight,cls,limit){const words=String(text||"").split(/\s+/).filter(Boolean),lines=[];let line="";words.forEach(w=>{const c=line?line+" "+w:w;if(c.length>max&&line){lines.push(line);line=w}else line=c});if(line)lines.push(line);const shown=lines.slice(0,limit);if(lines.length>limit)shown[limit-1]=shown[limit-1].slice(0,max-1).trimEnd()+"…";const t=add(p,"text",{x,y,class:cls});shown.forEach((s,i)=>add(t,"tspan",{x,dy:i?lineHeight:0},s));return t}
function network(g,i,l){const cx=540,cy=850,n=7+i%3,pts=[];for(let k=0;k<n;k++){const a=2*Math.PI*k/n-Math.PI/2,r=185+k%3*25;pts.push([cx+Math.cos(a)*r,cy+Math.sin(a)*r])}pts.forEach((p,k)=>{const q=pts[(k+2)%n];add(g,"line",{x1:p[0],y1:p[1],x2:q[0],y2:q[1],class:"rule",opacity:.75})});pts.forEach((p,k)=>add(g,"circle",{cx:p[0],cy:p[1],r:k===i%n?23:13,class:"node"}));add(g,"circle",{cx,cy,r:78,fill:"url(#panelFill)",stroke:"#e64b36","stroke-width":5});const a=pts[i%n],b=pts[(i+2)%n],p=l;add(g,"circle",{cx:a[0]+(b[0]-a[0])*p,cy:a[1]+(b[1]-a[1])*p,r:12,fill:"#fff4d6",filter:"url(#glow)"});add(g,"text",{x:cx,y:cy+8,"text-anchor":"middle",fill:"#fff4d6","font-size":24,"font-weight":800},["SOURCE","NETWORK","TARGET"][i%3])}
function flow(g,i,l){const x0=92,y=820,gap=226,labels=["INPUT","QUEUE","PROCESS","OUTPUT"];labels.forEach((s,k)=>{const x=x0+k*gap;add(g,"rect",{x,y:y-75,width:166,height:150,rx:20,class:"panel"});add(g,"text",{x:x+83,y:y+8,"text-anchor":"middle",fill:"#f5f7f8","font-size":22,"font-weight":750},s);if(k<3)add(g,"path",{d:"M "+(x+170)+" "+y+" h 42 l -13 -13 m 13 13 l -13 13",class:k===i%4?"gold":"green",opacity:k===i%4?1:.6})});for(let k=0;k<12;k++)add(g,"circle",{cx:180+(k%6)*145,cy:1040+Math.floor(k/6)*48,r:9,fill:k<i%12?"#e64b36":"#436d59"})}
function compare(g,i,l){[[130,"BEFORE",0],[585,"AFTER",1]].forEach(([x,s,side])=>{add(g,"rect",{x,y:680,width:360,height:370,rx:26,class:"panel"});add(g,"text",{x:x+180,y:725,"text-anchor":"middle",class:"micro"},s);for(let k=0;k<5;k++)add(g,"rect",{x:x+35,y:770+k*48,width:side?95+((k+i)%4)*48+28*Math.sin(l*Math.PI):55+((k*2+i)%3)*22+18*Math.sin(l*Math.PI),height:17,rx:8,fill:side?"#e64b36":"#646d76"})});add(g,"path",{d:"M 510 855 h 55 l -16 -16 m 16 16 l -16 16",class:"gold"});add(g,"text",{x:540,y:1120,"text-anchor":"middle",fill:"#d9e3d8","font-size":23},["CHANGE","CONTRAST","RESULT"][i%3])}
function timeline(g,i,l){const y=850,x0=130,x1=950;add(g,"line",{x1:x0,y1:y,x2:x1,y2:y,class:"green"});["TRIGGER","REACTION","ESCALATION","OUTCOME"].forEach((s,k)=>{const x=x0+k*(x1-x0)/3;add(g,"circle",{cx:x,cy:y,r:k===i%4?24:15,fill:k===i%4?"#e64b36":"#f5f7f8"});add(g,"text",{x,y:y+66,"text-anchor":"middle",fill:"#e9e2d1","font-size":20,"font-weight":700},s);add(g,"line",{x1:x,y1:y+28,x2:x,y2:y+48,class:"rule"})});const x=x0+(x1-x0)*((i%4+l)/4);add(g,"circle",{cx:x,cy:y,r:10,fill:"#fff4d6"});add(g,"path",{d:"M 130 1000 Q 540 1110 950 1000",class:"gold",opacity:.65})}
function scale(g,i,l){const cx=540,cy=820;add(g,"line",{x1:cx,y1:cy-170,x2:cx,y2:cy+120,class:"gold"});add(g,"line",{x1:cx-230,y1:cy-90+10*Math.sin(l*Math.PI),x2:cx+230,y2:cy-90-10*Math.sin(l*Math.PI),class:"gold"});[cx-230,cx+230].forEach((x,side)=>{add(g,"path",{d:"M "+(x-110)+" "+(cy-35)+" L "+(x+110)+" "+(cy-35)+" L "+(x+75)+" "+(cy+140)+" Q "+x+" "+(cy+185)+" "+(x-75)+" "+(cy+140)+" Z",class:"panel"});const n=side?8+i%4:2+i%3;for(let k=0;k<n;k++)add(g,"circle",{cx:x-65+k%5*32,cy:cy+10+Math.floor(k/5)*32,r:8,fill:side?"#e64b36":"#f5f7f8"})});add(g,"circle",{cx,cy:cy-170,r:24,class:"node"});add(g,"text",{x:cx,y:cy+240,"text-anchor":"middle",fill:"#d9e3d8","font-size":23},["IMBALANCE","LEVERAGE","AMPLIFICATION"][i%3])}
function stack(g,i,l){const x=285,y=600,w=510,h=88;["VISIBLE EVENT","HIDDEN INCENTIVE","SYSTEM PRESSURE","ROOT CAUSE"].forEach((s,k)=>{const yy=y+k*126,offset=k===i%4?18*Math.sin(l*Math.PI):0;add(g,"rect",{x:x+offset,y:yy,width:w,height:h,rx:18,fill:k===i%4?"#171c21":"#0b0d10",stroke:k===i%4?"#e64b36":"#3b4249","stroke-width":k===i%4?5:3});add(g,"text",{x:x+w/2+offset,y:yy+54,"text-anchor":"middle",fill:"#f5f7f8","font-size":24,"font-weight":750},s);if(k<3)add(g,"path",{d:"M 540 "+(yy+h+8)+" v 25 m -11 -11 l 11 11 l 11 -11",class:"gold"})})}
function transform(g,i,l){const cx=540,cy=850;for(let k=0;k<4;k++){const r=70+k*68;add(g,"circle",{cx,cy,r,fill:"none",stroke:k===i%4?"#e64b36":"#3b4249","stroke-width":k===i%4?6:3,"stroke-dasharray":k%2?"8 18":"none"})}for(let k=0;k<12;k++){const a=k*Math.PI/6+l*.6,r=100+k%3*68;add(g,"circle",{cx:cx+Math.cos(a)*r,cy:cy+Math.sin(a)*r,r:k%4===0?14:8,fill:k%3===0?"#e64b36":"#f5f7f8"})}add(g,"rect",{x:420,y:780,width:240,height:140,rx:24,fill:"url(#panelFill)",stroke:"#e64b36","stroke-width":4});add(g,"text",{x:540,y:858,"text-anchor":"middle",fill:"#fff4d6","font-size":23,"font-weight":800},["INPUT","SHIFT","NEW STATE"][i%3])}
function drawDraupadiConstruction(g,i,l){
 const cx=540,top=570,spacing=18;
 add(g,"circle",{cx,cy:760,r:220,fill:"none",stroke:"#e34b3d","stroke-width":3,"stroke-dasharray":"3 18",opacity:.65});
 // A recognizable person is constructed progressively from deterministic ink dots.
 for(let row=0;row<34;row++){
  const y=top+row*spacing,dy=row;
  let half;
  if(dy<5)half=35;
  else if(dy<9)half=52;
  else if(dy<14)half=88;
  else if(dy<20)half=115;
  else half=175-(dy-20)*2.2;
  half=Math.max(55,half);
  for(let col=-Math.floor(half/spacing);col<=Math.floor(half/spacing);col++){
   const x=cx+col*spacing;
   const reveal=clamp((l*34+2)-row,0,1);
   if(reveal>0)add(g,"circle",{cx:x,cy:y,r:(row<5?5.5:4.2),fill:(row<5||Math.abs(col)<2)?"#fff0ad":"#e7c16f",opacity:.22+.78*reveal,filter:"url(#glow)"});
  }
 }
 add(g,"path",{d:"M 540 570 C 480 610 475 700 500 760 L 465 1040 Q 540 1115 615 1040 L 580 760 C 605 700 600 610 540 570 Z",fill:"none",stroke:"#e7c16f","stroke-width":5,filter:"url(#glow)","stroke-linejoin":"round"});
 add(g,"path",{d:"M 500 655 Q 540 700 580 655 M 500 760 Q 540 800 580 760 M 475 960 Q 540 1015 605 960",fill:"none",stroke:"#e34b3d","stroke-width":5});
 add(g,"path",{d:"M 585 700 Q 680 665 725 735 L 690 770",fill:"none",stroke:"#e34b3d","stroke-width":8,"stroke-linecap":"round"});
 add(g,"text",{x:540,y:1180,"text-anchor":"middle","font-size":23,"font-weight":800,fill:"#e34b3d"},"THE QUESTION BECOMES VISIBLE");
}
function drawDiceGame(g,i,l){
 add(g,"path",{d:"M 190 650 L 890 650 L 980 1050 L 100 1050 Z",fill:"#E9D8C4",stroke:"#e7c16f","stroke-width":5});
 for(let row=0;row<5;row++)for(let col=0;col<7;col++)add(g,"circle",{cx:205+col*112,cy:710+row*68,r:3,fill:"#e7c16f",opacity:.3});
 add(g,"path",{d:"M 190 850 L 540 650 L 890 850 L 540 1050 Z",fill:"none",stroke:"#e34b3d","stroke-width":5});
 const rotation=(i*31+l*220)%360;
 for(let d=0;d<2;d++){
  const x=405+d*190+(d?1:-1)*Math.sin(l*Math.PI)*42,y=830+(d?45:-30)*Math.sin(l*Math.PI);
  const gdie=add(g,"g",{transform:"translate("+x+" "+y+") rotate("+(rotation*(d?-.7:1)) +")"});
  add(gdie,"rect",{x:-62,y:-62,width:124,height:124,rx:15,fill:"#21170f",stroke:"#e7c16f","stroke-width":5});
  const dots=[[ -25,-25],[25,-25],[0,0],[-25,25],[25,25]];
  const count=2+((i+d)%4);
  dots.slice(0,count).forEach(([dx,dy])=>add(gdie,"circle",{cx:dx,cy:dy,r:8,fill:"#e34b3d"}));
 }
 add(g,"path",{d:"M 255 1130 H 825 M 255 1130 l 25 -18 M 255 1130 l 25 18 M 825 1130 l -25 -18 M 825 1130 l -25 18",fill:"none",stroke:"#e7c16f","stroke-width":4});
 add(g,"text",{x:540,y:1200,"text-anchor":"middle","font-size":24,"font-weight":800,fill:"#e34b3d"},"A GAME CHANGES THE BALANCE");
}
function drawAssembly(g,i,l){
 // Pillars and a row of distinct silhouettes make the royal court legible rather than abstract.
 for(let k=0;k<5;k++){
  const x=145+k*198;
  add(g,"path",{d:"M "+(x-58)+" 670 L "+x+" 610 L "+(x+58)+" 670 Z",fill:"#21170f",stroke:"#e7c16f","stroke-width":4});
  add(g,"rect",{x:x-40,y:670,width:80,height:400,fill:"#21170f",stroke:"#e7c16f","stroke-width":4});
  add(g,"path",{d:"M "+(x-54)+" 1070 H "+(x+54),fill:"none",stroke:"#e34b3d","stroke-width":5});
 }
 for(let k=0;k<5;k++){
  const x=190+k*175,alpha=clamp(1-l*1.2-(k%2)*.12,0,1);
  add(g,"circle",{cx:x,cy:900,r:35,fill:"#e7c16f",opacity:alpha});
  add(g,"path",{d:"M "+(x-50)+" 970 Q "+x+" 910 "+(x+50)+" 970 L "+(x+68)+" 1100 L "+(x-68)+" 1100 Z",fill:"#e7c16f",opacity:alpha});
  add(g,"path",{d:"M "+(x-20)+" 880 L 540 820 L "+(x+20)+" 880",fill:"none",stroke:"#e34b3d","stroke-width":3,opacity:alpha*.8});
 }
 add(g,"ellipse",{cx:540,cy:1100,rx:255,ry:60,fill:"none",stroke:"#e34b3d","stroke-width":4,"stroke-dasharray":"8 12"});
 add(g,"text",{x:540,y:1200,"text-anchor":"middle","font-size":24,"font-weight":800,fill:"#e34b3d"},"THE COURT FALLS SILENT");
}
function drawBalance(g,i,l){
 const cx=540,cy=790,tilt=Math.sin(l*Math.PI)*22;
 add(g,"path",{d:"M 540 650 L 540 1110 M 410 1110 H 670",fill:"none",stroke:"#e7c16f","stroke-width":8,"stroke-linecap":"round"});
 add(g,"circle",{cx,cy:650,r:28,fill:"#e34b3d",stroke:"#e7c16f","stroke-width":4});
 add(g,"path",{d:"M 300 "+(760+tilt)+" L 780 "+(760-tilt),fill:"none",stroke:"#e34b3d","stroke-width":9,"stroke-linecap":"round"});
 for(const side of [-1,1]){
  const x=540+side*235,y=760-side*tilt;
  add(g,"path",{d:"M "+(x-105)+" "+(y+5)+" L "+(x+105)+" "+(y+5)+" L "+(x+65)+" "+(y+160)+" Q "+x+" "+(y+205)+" "+(x-65)+" "+(y+160)+" Z",fill:"#17120e",stroke:"#e7c16f","stroke-width":5});
  for(let k=0;k<5+(side>0?i%4:1);k++)add(g,"circle",{cx:x-45+(k%4)*30,cy:y+45+Math.floor(k/4)*30,r:7,fill:side>0?"#e34b3d":"#e7c16f"});
  add(g,"text",{x,y:y+235,"text-anchor":"middle","font-size":22,"font-weight":800,fill:"#e7c16f"},side<0?"AUTHORITY":"JUSTICE");
 }
 add(g,"text",{x:540,y:1190,"text-anchor":"middle","font-size":24,"font-weight":800,fill:"#e34b3d"},"WHO HAS THE RIGHT TO DECIDE?");
}
function draw(b,i,l){const g=$("sceneArt");g.replaceChildren();const semantic=(b.subject+" "+b.idea).toLowerCase(),s=(b.grammar+" "+semantic+" "+b.action).toLowerCase();let type;
 if(THEME==="mythology"&&/draupadi|queen|woman|silhouette|raised hand|question/.test(s)){type="draupadi-construction";drawDraupadiConstruction(g,i,l)}
 else if(THEME==="mythology"&&/dice|game|board|gambl|roll/.test(s)){type="dice-game";drawDiceGame(g,i,l)}
 else if(THEME==="mythology"&&/elder|assembly|court|silence|throne|king/.test(s)){type="royal-assembly";drawAssembly(g,i,l)}
 else if(THEME==="mythology"&&/justice|authority|balance|dharma|rule|right to decide/.test(s)){type="authority-justice";drawBalance(g,i,l)}
 else if(b.grammar==="split_comparison"||/compar|contrast|before.?after|versus|trade.?off|distribution/.test(semantic)){type="comparison";compare(g,i,l)}
 else if(b.grammar==="timeline"||/timeline|sequence|history|escalat|causal_chain/.test(semantic)){type="timeline";timeline(g,i,l)}
 else if(b.grammar==="scale"||/scale|leverage|amplif|inequal|concentration|imbalance/.test(semantic)){type="scale";scale(g,i,l)}
 else if(b.grammar==="particle_flow"||/flow|queue|pipeline|bottleneck|process|traffic|particle/.test(semantic)){type="flow";flow(g,i,l)}
 else if(b.grammar==="network"||/network|graph|ecosystem|connection|relationship/.test(semantic)){type="network";network(g,i,l)}
 else if(b.grammar==="layered_system"||/stack|layer|incentive|root_cause|hierarch/.test(semantic)){type="layered-system";stack(g,i,l)}
 else{type="transformation";transform(g,i,l)}
 g.setAttribute("data-scene",type);
 const glow=add(g,"circle",{cx:540,cy:850,r:340,fill:THEME==="mythology"?"#f0bd58":"#dba83f",opacity:.025+.025*Math.sin(l*Math.PI),filter:"url(#glow)"});g.insertBefore(glow,g.firstChild)}

function renderAt(seconds){const t=clamp(Number(seconds)||0,0,DURATION);let i=BEATS.findIndex((b,k)=>t>=b.start&&(t<b.end||k===BEATS.length-1));if(i<0)i=BEATS.length-1;const b=BEATS[i],l=clamp((t-b.start)/Math.max(.01,b.end-b.start),0,1);$("beatNo").textContent="BEAT "+String(i+1).padStart(2,"0")+" / "+String(BEATS.length).padStart(2,"0");const h=$("headline");h.replaceChildren();wrap(h,b.idea,76,265,22,64,"headline",2);$("description").textContent=b.subject.toUpperCase().slice(0,60);$("action").replaceChildren();wrap($("action"),b.action,78,1370,42,42,"action",2);$("labels").replaceChildren();b.labels.forEach((s,k)=>{const y=1480+k*66;add($("labels"),"circle",{cx:88,cy:y-8,r:7,fill:"#e64b36"});wrap($("labels"),s,112,y,48,30,"label",1)});draw(b,i,l);$("progress").setAttribute("x2",(78+924*t/DURATION).toFixed(2));$("stage").setAttribute("aria-label","Visual beat "+(i+1)+": "+b.idea)}
window.renderAt=renderAt;window.getDuration=()=>DURATION;
if(new URLSearchParams(window.location.search).get("render")!=="1")document.body.insertAdjacentHTML("beforeend",'<div style="position:fixed;bottom:12px;right:12px;color:#9bb4a7;font:12px system-ui">PLAN-COMPILED SCENE · preview before publishing</div>');
renderAt(0);
</script></body></html>`.replace("__TITLE__",()=>safeTitle).replace("__BEATS__",()=>json).replace("__DURATION__",()=>String(duration)).replace("__THEME_ATTR__",theme).replaceAll("__THEME__",()=>JSON.stringify(theme));
}
