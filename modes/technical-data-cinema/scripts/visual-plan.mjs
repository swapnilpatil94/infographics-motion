const GRAMMARS=["network","particle_flow","split_comparison","timeline","scale","layered_system","transformation"];
const ALIASES={dot_silhouette:"network",hand_drawn_sketch:"timeline","2d_diagram":"particle_flow",three_d_mechanism:"transformation",chart:"scale",comparison:"split_comparison"};
const REQUIRED=["narration_idea","viewer_takeaway","dominant_subject","action_and_causal_proof","composition","camera","transition","implementation_notes"];
function inferGrammar(beat,index){
 const t=[beat?.narration_idea,beat?.viewer_takeaway,beat?.dominant_subject,beat?.action_and_causal_proof,beat?.implementation_notes].filter(Boolean).join(" ").toLowerCase();
 if(/before.?after|compare|contrast|versus|trade.?off|alternative/.test(t))return "split_comparison";
 if(/timeline|history|delay|sequence|escalat|then |later |earlier |phase/.test(t))return "timeline";
 if(/scale|leverage|amplif|concentrat|imbalance|disproportion|majority|minority/.test(t))return "scale";
 if(/network|connect|relationship|ecosystem|account|branch|link/.test(t))return "network";
 if(/flow|queue|pipeline|bottleneck|request|traffic|transfer|transaction|process/.test(t))return "particle_flow";
 if(/incentive|hidden|root cause|dependency|layer|underlying|mechanism/.test(t))return "layered_system";
 return GRAMMARS[index%GRAMMARS.length];
}
export function validateVisualPlan(plan,{requireFingerprint=false,expectedDuration=null}={}){
 if(!plan||typeof plan!=="object"||!Array.isArray(plan.beats)||plan.beats.length<4)throw new Error("Visual plan must contain at least four beats.");
 const errors=[];
 if(typeof plan.visual_thesis!=="string"||plan.visual_thesis.trim().length<12)errors.push("visual_thesis must explain the central visual metaphor");
 if(!Array.isArray(plan.visual_signature)||plan.visual_signature.length<3||plan.visual_signature.some(x=>typeof x!=="string"||!x.trim()))errors.push("visual_signature must contain at least three concrete motifs");
 if(typeof plan.ending_image!=="string"||plan.ending_image.trim().length<8)errors.push("ending_image must describe the story resolution");
 if(requireFingerprint&&!/^[a-f0-9]{64}$/i.test(String(plan.story_fingerprint||"")))errors.push("plan is missing story_fingerprint; rerun analysis");
 let previousEnd=0;const signatures=new Set(),grammars=new Set();
 for(let i=0;i<plan.beats.length;i++){
  const b=plan.beats[i];if(!b||typeof b!=="object"){errors.push("beat "+(i+1)+" must be an object");continue}
  for(const field of REQUIRED)if(typeof b[field]!=="string"||b[field].trim().length<5)errors.push("beat "+(i+1)+" is missing meaningful "+field);
  const start=Number(b.start),end=Number(b.end);
  if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start)errors.push("beat "+(i+1)+" has invalid start/end timing");
  else{if(i===0&&start>0.5)errors.push("first visual beat must begin by 0.5 seconds");if(i>0&&start-previousEnd>0.6)errors.push("narration coverage has a gap before beat "+(i+1));if(i>0&&start<previousEnd-0.05)errors.push("beat "+(i+1)+" overlaps the previous beat");previousEnd=Math.max(previousEnd,end)}
  const g=String(b.visual_grammar||inferGrammar(b,i));grammars.add(ALIASES[g]||g);
  signatures.add([g,b.dominant_subject,b.composition].map(x=>String(x||"").trim().toLowerCase()).join("|"));
  if(i>0){const prior=plan.beats[i-1];if(String(prior?.dominant_subject||"").trim().toLowerCase()===String(b.dominant_subject||"").trim().toLowerCase()&&String(prior?.composition||"").trim().toLowerCase()===String(b.composition||"").trim().toLowerCase())errors.push("beats "+i+" and "+(i+1)+" repeat the same dominant subject and composition")}
 }
 if(plan.beats.length>=5&&grammars.size<3)errors.push("five or more beats must select at least three visual grammars");
 if(signatures.size<Math.min(4,plan.beats.length))errors.push("plan repeats too many scene signatures");
 if(expectedDuration!==null&&Number.isFinite(Number(expectedDuration))){const d=Number(expectedDuration),last=Number(plan.beats.at(-1)?.end);if(last<d-1)errors.push("visual plan ends before narration ends");if(last>d+2.5)errors.push("visual plan exceeds narration duration")}
 if(errors.length)throw new Error(errors.join("; "));
 return {beats:plan.beats.length,coverageEnd:Number(plan.beats.at(-1)?.end),grammarCount:grammars.size,sceneSignatureCount:signatures.size};
}
export function normalizeVisualPlan(plan){
 validateVisualPlan(plan);
 return {...plan,beats:plan.beats.map((beat,index)=>({...beat,visual_grammar:ALIASES[String(beat.visual_grammar||"").trim().toLowerCase()]||(GRAMMARS.includes(String(beat.visual_grammar||"").trim().toLowerCase())?String(beat.visual_grammar).trim().toLowerCase():inferGrammar(beat,index))}))};
}
