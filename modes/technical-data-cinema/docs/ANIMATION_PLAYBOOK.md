# Animation Playbook: Story-Driven Technical Explainers

This is the primary reference for the Visual Director and local coding model. The target is not “particles plus color”; it is a visual explanation in which motion demonstrates a mechanism. Use the technique that makes the causal relationship easiest to understand, then change technique when the explanatory task changes.

## The governing rule

Every animated element must answer four questions:

1. **What does it represent?** A request, person, packet, queue item, transaction, server, unit of capacity, signal, or another explicit entity.
2. **What changes?** Position, state, count, rate, route, load, visibility, relationship, or outcome.
3. **What causes the change?** A tap, event, threshold, dependency, delay, failure, intervention, or feedback loop.
4. **What can the viewer infer from watching?** The intended lesson should be visible before it is stated in text.

If an element cannot answer these questions, remove it or give it a clear explanatory job.

## Technique catalogue

| Technique | Best explanatory job | Useful implementation | Common failure |
|---|---|---|---|
| Semantic particle flow | Show many instances moving through a system: people, requests, packets, payments | Canvas 2D paths, precomputed particle paths, deterministic timestamps | Random dots that look attractive but explain nothing |
| Directed network / graph | Show relationships, dependencies, fan-out, bottlenecks and routing | SVG nodes/edges or Canvas paths; animate a highlighted route | Too many nodes/edges; viewer cannot see the active path |
| Branching / fan-out | One action creating multiple downstream jobs | Spawn deterministic child events from a source event | Lines branch but the consequence is never shown |
| Queue / backlog | Work arriving faster than it is processed | Arrivals and departures change queue length; show queue depth and wait time | Queue is represented only by a label or an arbitrary pile |
| Capacity vs demand | Explain overload and headroom | Progressive chart, threshold line, demand/capacity gap, state transition | Chart appears instantly or has unlabeled axes |
| Time-series / area chart | Show growth, spikes, lag, recovery and intervention effects | Draw path from timestamp; synchronize cursor with the narration | Decorative graph without units or an explicit takeaway |
| State machine | Explain workflow states, retries, approval, failure, recovery | Nodes change state in sequence; active transition has cause and result | Diagram is static, or all states light up together |
| Feedback loop | Explain retries, amplification, recommendations, control systems | Closed causal path with visible repeated effect | Circular arrows are shown without demonstrating feedback |
| Particle collision / convergence | Show aggregation, competition, merging or congestion | Paths converge at a bottleneck; density maps to load | Density has no relation to actual quantities |
| Diffusion / spread | Show information or an event spreading through a population | Deterministic wavefront or graph propagation with fixed seed | Spread looks like a generic explosion instead of a network |
| Field / heat map | Show concentration, pressure, risk or demand by region | Binned cells or sampled field with labeled legend | Color-only encoding; no scale or labels |
| Sorting / clustering | Explain categories, segmentation, search or grouping | Items move into meaningful bins; preserve item identity | Items teleport without showing the grouping rule |
| Before / after intervention | Prove why caching, prescaling, batching or backoff changes behavior | Keep initial conditions fixed; change one variable and replay | Before/after uses different conditions so comparison is invalid |
| Split-screen experiment | Compare two strategies under the same load | Share time axis, demand input and scale; label both conditions | Different scales or mismatched start times |
| Camera push / pull | Direct attention to the causal mechanism or reveal system context | Camera target/distance derived from timeline | Constant zooming adds motion but harms comprehension |
| Pan / tracking camera | Follow a request or trace a causal path through a large system | Camera position is a deterministic function of time | Camera moves faster than labels can be read |
| Parallax / depth layers | Separate foreground entities, system structure and context | Layered 2D planes with small controlled offsets | Depth is ornamental or causes confusing motion |
| Cutaway / exploded view | Reveal hidden components or internal stages | Transition from complete object to separated labeled layers | Layers separate without showing their function |
| Progressive build / draw-on | Explain a graph, route, diagram or process step-by-step | Compute line progress from normalized time | Every element builds at the same speed regardless of meaning |
| Trail / motion history | Reveal direction, path, latency or accumulated movement | Draw a short deterministic history window | Trails obscure objects or make the scene muddy |
| Pulse / signal propagation | Show an event moving through a system or latency between stages | Propagate a pulse along a known path with timestamp-based delay | Pulses are purely decorative |
| Morph / transform | Show one concept becoming another or a system changing state | Interpolate geometry and labels between explicit states | Unrelated shapes morph only for spectacle |
| Reveal / mask / wipe | Control information release or shift attention | Deterministic clip path or canvas mask | Repeated transitions become a template |
| Freeze / annotation | Give the viewer time to understand a dense mechanism | Briefly hold motion; add one concise annotation or callout | Text overload replaces the animation |
| Physical metaphor | Make an invisible concept tangible (queue as waiting line, cache as nearby shelf) | One coherent metaphor whose behavior maps to the system | Metaphor is visually clever but technically misleading |
| 2.5D / WebGL scene | Show spatial systems, layered machinery or 3D relationships | CSS/SVG/Canvas first; WebGL/Three.js only when depth helps | 3D increases complexity without improving understanding |

## Choose the simplest technique that preserves the explanation

- Use **Canvas 2D** for many particles, trails, custom drawing and lightweight simulations.
- Use **SVG** for crisp labeled diagrams, node-edge networks, chart paths and shapes that need precise styling.
- Use **DOM/CSS** for typography, captions, cards and interface-like objects. Avoid CSS-driven animation for rendered scenes because seeking becomes difficult to reproduce.
- Use **WebGL / Three.js** when the story genuinely needs 3D geometry, camera perspective, volumetric layering or many GPU-driven elements. Do not add it to every page. If using Three.js, vendor the required library locally and pin its version; never load from a CDN.
- Use **FFmpeg** for encoding, audio muxing, format checks and final delivery, not for inventing scene logic.
- Use **Playwright + Chromium** for deterministic browser frame capture and regression checks.

## A good explanatory sequence

This is a thinking tool, not a fixed visual template:

1. Establish the entity and stakes.
2. Show the normal mechanism working.
3. Introduce the change or pressure.
4. Let the viewer see the mechanism fail or change state.
5. Reveal the hidden bottleneck / causal relationship.
6. Apply one intervention while keeping other conditions stable.
7. Show the resulting behavior and summarize the insight.

Reorder, merge, or replace these beats when the story calls for it. A scene may continue across multiple narration lines; a line may need multiple visual states.

## Timing and readability

- Tie visual events to narration meaning, not equal-duration scene blocks.
- Leave reading time for labels and charts; reduce motion during dense explanation.
- Animate only the element relevant to the current causal claim; de-emphasize context rather than removing it arbitrarily.
- Use a small number of legible labels with units; never depend on color alone.
- Treat every statistic as sourced data or visibly illustrative.
- Hold the payoff long enough to register. Avoid arbitrary black fades and repetitive transitions.

## Deterministic animation contract

Every generated scene must expose:

```js
window.renderAt = function (seconds) {
  // Set every visible property from seconds.
};
window.getDuration = function () {
  return 45; // scene duration in seconds
};
```

Rules:
- Derive state directly from absolute time; do not integrate motion from the previous frame.
- Precompute particle positions, paths, seeds and event times.
- Avoid `Math.random()`, `Date.now()`, elapsed-time deltas and independent CSS keyframes for rendered state.
- For a particle moving from A to B during [t0, t1], calculate normalized progress `u = clamp((t - t0) / (t1 - t0), 0, 1)`, then derive its position from A and B.
- Use easing functions of normalized progress; never use a frame counter.
- Render the same timestamp twice and compare pixels. Different output indicates a determinism bug.
- The preview loop may use requestAnimationFrame to ask for a timestamp, but it must call the same `renderAt(t)` function used by the offline renderer.

## Local model instruction

The coding model must choose a visual technique based on the story's explanatory need. It must not simply use the same particle system, camera movement, palette, or shot sequence for every story. It should write a short scene plan first for internal reasoning, then output one complete HTML file that satisfies the renderer contract. After generation, run static validation, render samples, inspect the frames, and revise the code based on observed failures.

## References

- MDN requestAnimationFrame: https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame
- MDN Canvas filter: https://developer.mozilla.org/en-US/docs/Web/API/CanvasRenderingContext2D/filter
- Three.js WebGLRenderer: https://threejs.org/docs/pages/WebGLRenderer.html
- Playwright browser management: https://playwright.dev/docs/browsers
