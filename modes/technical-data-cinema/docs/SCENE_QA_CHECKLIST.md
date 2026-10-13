# Scene and Render QA Checklist

Use this after each model generation. A successful file write is not a successful video.

## A. Story / explanation
- [ ] The first second creates a clear question, event or visual anomaly.
- [ ] Each major animation represents a real entity or a clearly stated metaphor.
- [ ] Movement makes a causal mechanism visible.
- [ ] The viewer can explain what changed and why after watching.
- [ ] Every scene has a distinct explanatory objective; no repeated layouts just for uniformity.
- [ ] The payoff answers the opening question.
- [ ] Statistics are sourced or labelled illustrative.

## B. Animation
- [ ] All motion is derived from absolute time.
- [ ] Re-seeking to a timestamp reproduces the same frame.
- [ ] Particle motion, branching and queues show meaningful behavior.
- [ ] Graphs have legible labels, units and progressive drawing.
- [ ] Camera movement supports comprehension and leaves text readable.
- [ ] No unmotivated random particles, glows, transitions or decorative dashboards.
- [ ] Motion pauses or simplifies when the viewer needs to read.

## C. Technical
- [ ] One self-contained HTML file.
- [ ] `window.renderAt(seconds)` exists.
- [ ] `window.getDuration()` returns a finite positive duration.
- [ ] No external network requests.
- [ ] No fatal page errors or console errors.
- [ ] No clipped key text at 1080×1920.
- [ ] Same-time deterministic test passes.
- [ ] Output folder and frame disk usage are reasonable.

## D. Narration / captions
- [ ] Narration WAV is the approved Chatterbox output.
- [ ] Pronunciation and code-switching sound natural in Hindi/Hinglish.
- [ ] Visual events follow meaning, not just sentence boundaries.
- [ ] Captions match the approved final narration and are timed to speech.
- [ ] Audio duration and video duration are intentionally aligned.

## E. Export
- [ ] H.264 video, yuv420p, 1080×1920, target frame rate.
- [ ] AAC audio when narration is included.
- [ ] No silent tail, clipped first word, or unintended audio gap.
- [ ] Inspect the beginning, middle, end and every major transition.
- [ ] Watch the complete video at normal speed before release.
- [ ] Verify the final file with `ffprobe` and play it in a normal video player.

## Decision
- **Pass:** all technical checks pass and the explanation is clear.
- **Needs repair:** technical checks pass but a causal beat, pacing, readability or visual quality is weak.
- **Fail:** missing renderer contract, external dependencies, fatal errors, nondeterministic frames, broken audio, or invalid output.
