const GRAMMARS = ["network", "particle_flow", "split_comparison", "timeline", "scale", "layered_system", "transformation"];
const ALIASES = {
  dot_silhouette: "network",
  hand_drawn_sketch: "timeline",
  "2d_diagram": "particle_flow",
  three_d_mechanism: "transformation",
  chart: "scale",
  comparison: "split_comparison",
  split_comparison: "split_comparison"
};

function inferGrammar(beat, index) {
  const text = [
    beat?.narration_idea, beat?.viewer_takeaway, beat?.dominant_subject,
    beat?.action_and_causal_proof, beat?.implementation_notes
  ].filter(Boolean).join(" ").toLowerCase();
  if (/before.?after|compare|contrast|versus|trade.?off|alternative/.test(text)) return "split_comparison";
  if (/timeline|history|delay|sequence|escalat|then |later |earlier |phase/.test(text)) return "timeline";
  if (/scale|leverage|amplif|concentrat|imbalance|disproportion|majority|minority/.test(text)) return "scale";
  if (/network|connect|relationship|ecosystem|account|branch|link/.test(text)) return "network";
  if (/flow|queue|pipeline|bottleneck|request|traffic|transfer|transaction|process/.test(text)) return "particle_flow";
  if (/incentive|hidden|root cause|dependency|layer|underlying|mechanism/.test(text)) return "layered_system";
  return GRAMMARS[index % GRAMMARS.length];
}

export function normalizeVisualPlan(plan) {
  if (!plan || !Array.isArray(plan.beats) || plan.beats.length < 4) {
    throw new Error("Visual plan must contain at least four beats.");
  }
  const normalized = { ...plan, beats: plan.beats.map(beat => ({ ...beat })) };
  normalized.beats.forEach((beat, index, beats) => {
    const original = String(beat.visual_grammar || "").toLowerCase().trim();
    let grammar = ALIASES[original] || (GRAMMARS.includes(original) ? original : inferGrammar(beat, index));
    const previous = index ? beats[index - 1].visual_grammar : null;
    const beforePrevious = index > 1 ? beats[index - 2].visual_grammar : null;
    if (grammar === previous) {
      const inferred = inferGrammar(beat, index);
      grammar = inferred !== previous && inferred !== beforePrevious
        ? inferred
        : GRAMMARS.find(candidate => candidate !== previous && candidate !== beforePrevious) || grammar;
    }
    beat.visual_grammar = grammar;
  });
  if (normalized.beats.length >= 5) {
    const unique = new Set(normalized.beats.map(beat => beat.visual_grammar));
    for (let index = 1; unique.size < 3 && index < normalized.beats.length; index++) {
      const beat = normalized.beats[index];
      const previous = normalized.beats[index - 1].visual_grammar;
      const candidate = GRAMMARS.find(grammar => grammar !== previous && !unique.has(grammar));
      if (candidate) {
        beat.visual_grammar = candidate;
        unique.add(candidate);
      }
    }
  }
  return normalized;
}
