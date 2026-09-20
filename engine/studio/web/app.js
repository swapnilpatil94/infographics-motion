"use strict";
/* Kathaaya Studio - a thin client. All logic (analysis, validation, edits, progress folding) lives in the server; this file only renders what the API returns. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const view = $("#view");
const S = { opts: null, level: localStorage.getItem("ks.level") || "simple", draft: null, edit: false, scriptEdits: {}, regen: new Set(), busy: null,
  form: JSON.parse(sessionStorage.getItem("ks.form") || "null") || { mode: "create", topic: "", script_text: "", title: "", segments_text: "", story_md: "", story_json: "", audio_upload: null, audio_name: "", example: null,
    language: "hi", format: "9:16", duration: "auto", voice: "chatterbox_hindi", style: "kathaya_cinematic", character: { protagonist: {}, partner: {}, extras: [{}, {}] }, environment: { mode: "auto", location: "" }, typography: { captions: true },
    director: { pacing: "auto", camera: "auto", audio: { music: 1, sfx: 1, ambience: 1 } }, variation: 0 },
  prod: { id: null, state: null, meta: null, logs: [], es: null, skew: 0, msgAt: 0, tick: null, poll: null }, insp: { plan: null, sel: null, raw: null, tab: "overview", preview: null, busy: false, last: null } };

// ------------------------------------------------------------------------------------------------ helpers
async function api(path, body, method) {
  const r = await fetch("/api" + path, { method: method || (body !== undefined ? "POST" : "GET"), headers: body !== undefined ? { "Content-Type": "application/json" } : {}, body: body !== undefined ? JSON.stringify(body) : undefined });
  let j = null;
  try { j = await r.json(); } catch (e) { /* not json */ }
  if (!r.ok) throw (j && j.error ? j : { error: { code: "http_" + r.status, message: j && j.detail ? "The request was not understood: " + JSON.stringify(j.detail).slice(0, 200) : "The server answered " + r.status, reasons: [], hint: null } });
  return j;
}
function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("on"); clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("on"), 2600); }
const mmss = s => { if (s == null || !isFinite(s)) return "--:--"; s = Math.max(0, Math.round(s)); return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"); };
const fmt1 = v => v == null ? "-" : (Math.round(v * 10) / 10).toString();
function errBox(e) {
  const x = (e && e.error) || e || {};
  return `<div class="err" role="alert"><b>${esc(x.message || "Something went wrong")}</b>${(x.reasons || []).length ? "<ul>" + x.reasons.map(r => `<li>${esc(r)}</li>`).join("") + "</ul>" : ""}${x.hint ? `<div class="hint">${esc(x.hint)}</div>` : ""}<div class="dim mono" style="margin-top:8px">${esc(x.code || "")}</div></div>`;
}
function saveForm() { try { sessionStorage.setItem("ks.form", JSON.stringify(S.form)); } catch (e) { /* quota */ } }
function setPath(o, path, v) { const k = path.split("."); let t = o; for (let i = 0; i < k.length - 1; i++) t = t[k[i]] = t[k[i]] || {}; t[k[k.length - 1]] = v; }
function getPath(o, path) { return path.split(".").reduce((a, k) => (a == null ? a : a[k]), o); }
const opt = (list, cur, get = x => x, label = x => x) => list.map(x => `<option value="${esc(get(x))}" ${String(get(x)) === String(cur) ? "selected" : ""}>${esc(label(x))}</option>`).join("");
const lvl = () => ["simple", "director", "expert"].indexOf(S.level);

// ------------------------------------------------------------------------------------------------ router
window.addEventListener("hashchange", route);
async function route() {
  stopWatch();
  const h = location.hash.replace(/^#/, "") || "/";
  $$("[data-nav]").forEach(a => a.classList.toggle("on", (a.dataset.nav === "create" && (h === "/" || h.startsWith("/review"))) || (a.dataset.nav === "productions" && h.startsWith("/productions"))));
  $$(".levels button").forEach(b => b.classList.toggle("on", b.dataset.level === S.level));
  if (!S.opts) { try { S.opts = await api("/options"); } catch (e) { view.innerHTML = errBox(e); return; } }
  let m;
  if ((m = h.match(/^\/review\/(d_[0-9a-f]+)$/))) return viewReview(m[1]);
  if ((m = h.match(/^\/production\/([\w-]+)$/))) return viewProduction(m[1]);
  if (h.startsWith("/productions")) return viewList();
  return viewCreate();
}
$(".levels").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; S.level = b.dataset.level; localStorage.setItem("ks.level", S.level); route(); });
async function ping() { try { await fetch("/api/options"); $("#conn").className = "conn ok"; } catch (e) { $("#conn").className = "conn bad"; } }
setInterval(ping, 8000);

// ------------------------------------------------------------------------------------------------ CREATE
function viewCreate(err) {
  const o = S.opts, f = S.form, L = lvl();
  const langs = opt(o.languages, f.language, x => x.id, x => x.label + (x.supported ? "" : "  (not supported)"));
  const modeHint = { create: "Describe a topic or idea. The studio writes the story, the script and the narration.", script: "Paste a story or script (Hindi). The studio checks it, then narrates and films it.", production: "Bring your own story and narration segments JSON (with the audio)." };
  const input = f.mode === "create" ? `
      <label class="f">Topic or idea<textarea class="big" data-f="topic" placeholder="e.g. fake WhatsApp investment group" rows="3">${esc(f.topic)}</textarea></label>
      <div class="row" style="margin-top:12px"><small class="muted">Try:</small>${o.sample_topics.map(t => `<span class="chip click" data-topic="${esc(t)}">${esc(t)}</span>`).join("")}</div>`
    : f.mode === "script" ? `
      <div class="grid g2" style="grid-template-columns:2fr 1fr"><label class="f">Title (shown on the end card)<input data-f="title" value="${esc(f.title)}" placeholder="कहानी का नाम"></label>
      <label class="f">Load a file<span class="drop" style="padding:9px 12px"><input type="file" id="file-script" accept=".md,.txt,.json" style="border:0;padding:0"></span></label></div>
      <label class="f" style="margin-top:12px">Story / script (Hindi, one narration line per row)<textarea class="big" data-f="script_text" rows="9" placeholder="रात के ग्यारह बजे। कमरे में अकेला अर्जुन।&#10;तभी फ़ोन बज उठा।&#10;…">${esc(f.script_text)}</textarea></label>
      ${f.story_json ? `<div class="note">story.json loaded (${f.story_json.length} characters). <a href="#" data-clear="story_json">remove</a></div>` : ""}
      <small class="muted">Accepts plain text, story.md (with optional <code>protagonist:</code>, <code>other:</code>, <code>location:</code> notes) or story.json. 8–40 lines. Write numbers and English words in Devanagari.</small>`
    : `
      <div class="row" style="margin-bottom:12px"><small class="muted">Use an accepted example:</small>${o.examples.map(x => `<span class="chip click ${f.example === x.id ? "on" : ""}" data-example="${esc(x.id)}" title="${esc(x.hint)}">${esc(x.label)}</span>`).join("")}${f.example ? `<span class="chip click" data-example="">clear</span>` : ""}</div>
      <div class="${f.example ? "dim" : ""}"><div class="grid g2"><label class="f">Narration segments JSON<textarea data-f="segments_text" rows="8" placeholder='{"segments":[{"id":"n01","text":"…","start":0.3,"end":2.8}], "audio":"path/to/paced.wav"}' ${f.example ? "disabled" : ""}>${esc(f.segments_text)}</textarea></label>
      <div class="grid" style="align-content:start"><label class="f">…or load the JSON file<input type="file" id="file-seg" accept=".json" ${f.example ? "disabled" : ""}></label>
      <label class="f">Narration audio (if the JSON has no valid path)<input type="file" id="file-audio" accept=".wav,.mp3,.m4a,.flac" ${f.example ? "disabled" : ""}></label>${f.audio_name ? `<small class="ok">audio uploaded: ${esc(f.audio_name)}</small>` : ""}</div></div>
      <label class="f" style="margin-top:12px">Story notes (optional story.md: title, protagonist, other, sender, amount)<textarea data-f="story_md" rows="3" ${f.example ? "disabled" : ""}>${esc(f.story_md)}</textarea></label></div>`;
  const dur = opt(o.durations, f.duration, x => x.id, x => x.label);
  const director = L >= 1 ? directorPanel() : "";
  view.innerHTML = `<section class="create">
    <div class="hero"><h1>Make a Kathaaya film</h1><p>One screen from an idea to a finished cinematic Short. Everything is <b>Auto</b> unless you say otherwise.</p></div>
    <div class="seg tabs-mode" role="tablist">${o.modes.map(m => `<button data-mode="${m.id}" class="${f.mode === m.id ? "on" : ""}">${esc(m.label)}<small>${esc(m.hint)}</small></button>`).join("")}</div>
    <div class="card input-card"><div class="muted" style="margin-bottom:14px">${modeHint[f.mode]}</div>${input}
      <hr><div class="grid g5">
        <label class="f">Language<select data-f="language">${langs}</select></label>
        <label class="f">Format<select data-f="format">${opt(o.formats, f.format, x => x.id, x => x.label)}</select></label>
        <label class="f">Duration<select data-f="duration" ${f.mode === "production" ? "disabled" : ""}>${dur}</select></label>
        <label class="f">Voice<select data-f="voice" ${f.mode === "production" ? "disabled" : ""}>${opt(o.voices.filter(v => f.mode === "production" ? v.id === "provided" : v.id !== "provided"), f.mode === "production" ? "provided" : f.voice, x => x.id, x => x.label)}</select></label>
        <label class="f">Visual style<select data-f="style">${opt(o.styles, f.style, x => x.id, x => x.label)}</select></label></div>
      ${f.format === "16:9" ? `<div class="note">${esc(o.formats.find(x => x.id === "16:9").note)}</div>` : ""}
      ${f.mode === "production" ? `<div class="note">Duration and voice come from your narration file.</div>` : ""}
      <div id="create-err">${err ? errBox(err) : ""}</div>
      <div class="cta"><small class="muted">${L === 0 ? "Simple mode: topic → story review → generate." : "Director mode: overrides below apply to the plan; leave anything on Auto to keep the studio's defaults."}</small>
        <button class="btn primary" id="go">Generate Movie</button></div></div>
    ${director}
    ${L === 2 ? `<div class="sect"><h3>Expert · request payload</h3><pre class="json">${esc(JSON.stringify(payload(), null, 1))}</pre></div>` : ""}
  </section>`;
}
function directorPanel() {
  const o = S.opts, f = S.form, c = f.character, a = f.director.audio;
  const slider = (k, lab) => `<label class="f">${lab} <span class="mono" id="av-${k}">${Math.abs(a[k] - 1) < 1e-9 ? "Auto" : Math.round(a[k] * 100) + "%"}</span><input type="range" min="0" max="2" step="0.05" value="${a[k]}" data-audio="${k}"></label>`;
  const arch = (path, cur) => `<select data-f="${path}"><option value="">Auto</option>${opt(o.archetypes, cur)}</select>`;
  return `<div class="sect"><h3>Director controls · optional</h3><div class="director-grid">
    <div class="dcard"><h3>Character</h3><div class="grid g2">
      <label class="f">Protagonist${arch("character.protagonist.archetype", c.protagonist.archetype)}</label>
      <label class="f">Gender<select data-f="character.protagonist.gender"><option value="">Auto</option>${opt(["male", "female"], c.protagonist.gender)}</select></label>
      <label class="f">Name<input data-f="character.protagonist.name" value="${esc(c.protagonist.name || "")}" placeholder="Auto"></label>
      <label class="f">Partner${arch("character.partner.archetype", c.partner.archetype)}</label>
      <label class="f">Partner gender<select data-f="character.partner.gender"><option value="">Auto</option>${opt(["masculine", "feminine", "either"], c.partner.gender)}</select></label>
      <label class="f">Extra 1${arch("character.extras.0.archetype", (c.extras[0] || {}).archetype)}</label>
      <label class="f">Extra 2${arch("character.extras.1.archetype", (c.extras[1] || {}).archetype)}</label>
      <label class="f">Character variation<input type="number" min="0" max="20" data-f="variation" value="${f.variation || 0}"></label></div><small class="dim">0 = Auto. Another number re-draws every character and set, deterministically.</small></div>
    <div class="dcard"><h3>Environment</h3><div class="grid"><div class="seg">${[["auto", "Auto"], ["prefer", "Preferred"], ["force", "Forced"]].map(([k, l]) => `<button data-env="${k}" class="${f.environment.mode === k ? "on" : ""}">${l}</button>`).join("")}</div>
      <label class="f">Location<select data-f="environment.location" ${f.environment.mode === "auto" ? "disabled" : ""}><option value="">—</option>${opt(Object.keys(o.environments), f.environment.location, x => x, x => x.replace(/_/g, " ") + " (" + o.environments[x].times.join("/") + ")")}</select></label></div>
      <small class="dim">Preferred: used where the story names no place. Forced: every scene is staged there (time of day stays plausible, e.g. a bank is never night).</small></div>
    <div class="dcard"><h3>Style</h3><label class="f">Visual style<select data-f="style">${opt(o.styles, f.style, x => x.id, x => x.label)}</select></label><small class="dim">Only styles the production engine renders are listed.</small></div>
    <div class="dcard"><h3>Typography</h3><div class="grid"><label class="f">Caption style<select>${opt(o.typography.styles, "kathaya_bold", x => x.id, x => x.label)}</select></label>
      <label class="f" style="flex-direction:row;align-items:center;gap:10px;text-transform:none;font-size:14px;color:var(--text)"><input type="checkbox" data-check="typography.captions" ${f.typography.captions !== false ? "checked" : ""}> Captions on</label>
      <label class="f">Caption language<input value="${esc(o.typography.caption_language)}" disabled></label></div></div>
    <div class="dcard"><h3>Camera and pacing</h3><div class="grid g2"><label class="f">Pacing<select data-f="director.pacing">${opt(o.pacing, f.director.pacing, x => x.id, x => x.label)}</select></label>
      <label class="f">Camera preference<select data-f="director.camera">${opt(o.camera, f.director.camera, x => x.id, x => x.label)}</select></label></div><small class="dim">Pacing changes how the camera moves, never the cut points or the acting.</small></div>
    <div class="dcard"><h3>Voice</h3><label class="f">Narrator<select data-f="voice" ${f.mode === "production" ? "disabled" : ""}>${opt(o.voices.filter(v => v.id !== "provided"), f.voice, x => x.id, x => x.label)}</select></label><small class="dim">The studio has one narrator voice; Production mode uses your own audio.</small></div>
    <div class="dcard"><h3>Music and audio</h3><div class="grid">${slider("music", "Music")}${slider("sfx", "Sound effects")}${slider("ambience", "Room ambience")}</div><small class="dim">Auto = the Audio Director's levels. Speech ducking and the master limiter always stay on.</small></div>
  </div></div>`;
}
function payload() {
  const f = S.form, p = { mode: f.mode, language: f.language, format: f.format, duration: f.mode === "production" ? "auto" : f.duration, voice: f.mode === "production" ? "provided" : f.voice, style: f.style, level: S.level, variation: Number(f.variation) || 0 };
  const clean = o => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));
  const ch = {}, pr = clean(f.character.protagonist), pa = clean(f.character.partner), ex = f.character.extras.map(clean);
  if (Object.keys(pr).length) ch.protagonist = pr; if (Object.keys(pa).length) ch.partner = pa; if (ex.some(e => Object.keys(e).length)) ch.extras = ex;
  if (Object.keys(ch).length) p.character = ch;
  if (f.environment.mode !== "auto" && f.environment.location) p.environment = { mode: f.environment.mode, location: f.environment.location };
  const d = {}; if (f.director.pacing !== "auto") d.pacing = f.director.pacing; if (f.director.camera !== "auto") d.camera = f.director.camera;
  const au = {}; ["music", "sfx", "ambience"].forEach(k => { if (Math.abs(f.director.audio[k] - 1) > 1e-9) au[k] = f.director.audio[k]; }); if (Object.keys(au).length) d.audio = au;
  if (Object.keys(d).length) p.director = d;
  if (f.typography.captions === false) p.typography = { captions: false };
  if (f.mode === "create") p.topic = f.topic;
  if (f.mode === "script") { p.script_text = (f.title ? "# " + f.title + "\n" : "") + f.script_text; if (f.story_json) { p.story_json = f.story_json; if (!f.script_text.trim()) p.script_text = ""; } }
  if (f.mode === "production") { if (f.example) p.example = f.example; else { p.segments_json = f.segments_text; p.story_md = f.story_md; if (f.audio_upload) p.audio_upload = f.audio_upload; } }
  return p;
}
async function analyze() {
  const btn = $("#go"); btn.disabled = true; btn.innerHTML = '<span class="spin"></span>Analysing the story…';
  try { const d = await api("/story", payload()); S.draft = d; S.edit = false; S.scriptEdits = {}; S.regen = new Set(); location.hash = "#/review/" + d.id; }
  catch (e) { $("#create-err").innerHTML = errBox(e); btn.disabled = false; btn.textContent = "Generate Movie"; $("#create-err").scrollIntoView({ block: "center", behavior: "smooth" }); }
}
view.addEventListener("input", e => {
  const t = e.target;
  if (t.dataset.f) { let v = t.value; if (t.dataset.f === "variation") v = Number(v) || 0; setPath(S.form, t.dataset.f, v); saveForm(); }
  if (t.dataset.audio) { S.form.director.audio[t.dataset.audio] = Number(t.value); $("#av-" + t.dataset.audio).textContent = Math.abs(t.value - 1) < 1e-9 ? "Auto" : Math.round(t.value * 100) + "%"; saveForm(); }
  if (t.dataset.seg) { S.scriptEdits[t.dataset.seg] = t.value; const b = $("#apply-script"); if (b) b.disabled = false; }
});
view.addEventListener("change", async e => {
  const t = e.target;
  if (t.dataset.check) { setPath(S.form, t.dataset.check, t.checked); saveForm(); return; }
  if (t.dataset.f && ["mode", "format", "language"].includes(t.dataset.f)) { viewCreate(); }
  if (t.id === "file-script") return loadFile(t.files[0], "script");
  if (t.id === "file-seg") return loadFile(t.files[0], "seg");
  if (t.id === "file-audio") return uploadAudio(t.files[0]);
  if (t.dataset.f === "format") viewCreate();
});
async function loadFile(file, kind) {
  if (!file) return; const txt = await file.text();
  if (kind === "seg") { S.form.segments_text = txt; }
  else if (/\.json$/i.test(file.name)) { S.form.story_json = txt; }
  else { S.form.script_text = txt; S.form.story_json = ""; }
  saveForm(); viewCreate(); toast(file.name + " loaded");
}
async function uploadAudio(file) {
  if (!file) return;
  try { const r = await fetch(`/api/upload?kind=audio&name=${encodeURIComponent(file.name)}`, { method: "POST", body: file }); const j = await r.json(); if (!r.ok) throw j; S.form.audio_upload = j.upload_id; S.form.audio_name = file.name; saveForm(); viewCreate(); toast("audio uploaded"); }
  catch (e) { $("#create-err").innerHTML = errBox(e); }
}

// ------------------------------------------------------------------------------------------------ REVIEW
async function viewReview(id) {
  if (!S.draft || S.draft.id !== id) { view.innerHTML = '<div class="muted"><span class="spin"></span>Loading…</div>'; try { S.draft = await api("/draft/" + id); } catch (e) { view.innerHTML = errBox(e) + '<p><a href="#/">Back to Create</a></p>'; return; } }
  renderReview();
}
function renderReview(err) {
  const d = S.draft, r = d.review, o = S.opts, L = lvl(), s = d.settings, prov = d.provided_audio;
  const person = p => `<b>${esc(p.name || p.role.replace(/_/g, " "))}</b> <span class="muted">· ${esc(p.archetype)}, ${esc(p.gender)}</span>`;
  const psy = r.psychology.map(p => `<span class="chip" title="${esc(p.why)}">${esc(p.name)}${p.cues.length ? ` <small class="dim">${esc(p.cues.join(", "))}</small>` : ""}</span>`).join(" ");
  const acts = r.acts.map(a => `<span class="a" data-e="${esc(a.emotion)}" title="${esc(a.text)} · ${esc(a.loc)}/${esc(a.time)}">${esc(a.act)}</span>`).join("");
  const scenes = r.scenes.map(x => `<span class="chip">${esc(x.loc.replace(/_/g, " "))} · ${esc(x.time)}</span>`).join(" ");
  const edit = S.edit ? editStoryPanel() : "";
  const rows = d.script.segments.map(g => {
    const ed = S.scriptEdits[g.id] !== undefined;
    return `<div class="seg-row ${S.regen.has(g.id) ? "sel" : ""}" data-row="${esc(g.id)}"><input type="checkbox" title="select to regenerate" data-regen="${esc(g.id)}" ${S.regen.has(g.id) ? "checked" : ""} ${prov ? "disabled" : ""}>
      <div class="ts">${g.start.toFixed(1)}–${g.end.toFixed(1)}s<b>${g.duration.toFixed(1)} s</b></div>
      <div>${ed ? `<textarea data-seg="${esc(g.id)}">${esc(S.scriptEdits[g.id])}</textarea>` : `<div class="tx" ${prov ? "" : `data-edit="${esc(g.id)}" title="click to edit"`}>${esc(g.text)}</div>`}<span class="act">${esc(g.id)} · ${esc(g.act || "")}</span></div></div>`;
  }).join("");
  view.innerHTML = `<section>
    <div class="dash-h"><div><div class="muted">Story review · ${esc(d.mode)}${d.variation ? " · variation " + d.variation : ""}</div><h1>Approve the story</h1></div>
      <div class="row">${[s.format, "Hindi", s.duration ? "about " + s.duration + " s" : "Auto duration", prov ? "provided audio" : "Chatterbox Hindi"].map(x => `<span class="chip">${esc(x)}</span>`).join("")}</div></div>
    <div class="rev"><div>
      <div class="card"><div class="title-big">${esc(r.title)}</div><div class="hook">${esc(r.hook.text)}</div>
        <dl class="kv"><dt>Protagonist</dt><dd>${person(r.protagonist)}</dd>
        <dt>Supporting</dt><dd>${r.supporting.length ? r.supporting.map(person).join("<br>") : '<span class="muted">none</span>'}</dd>
        <dt>Conflict</dt><dd>${esc(r.conflict.text)}</dd>
        <dt>Psychology</dt><dd>${psy}</dd>
        <dt>Ending / lesson</dt><dd>${esc(r.ending.text)}</dd>
        <dt>Scenes</dt><dd>${scenes}</dd>
        <dt>Duration</dt><dd>${r.est_duration_s ? "about " + r.est_duration_s + " s" : "-"} <small class="muted">${r.duration_is_estimate ? "(estimated until the narration is made)" : "(from your narration)"}</small></dd></dl>
        <div class="sect"><h3>Act structure · ${r.acts.length} beats</h3><div class="acts">${acts}</div></div>
        ${(d.warnings || []).length ? `<div class="note">${d.warnings.map(esc).join("<br>")}</div>` : ""}
        ${(r.provenance || []).length && L === 2 ? `<pre class="json">${esc(JSON.stringify(r.provenance, null, 1))}</pre>` : ""}
        <div class="row" style="margin-top:20px"><button class="btn" id="btn-edit">${S.edit ? "Close editor" : "Edit Story"}</button><button class="btn" id="btn-regen" title="${d.mode === "create" ? "write another version of this story (new names, relation and time of night)" : "draw a new cast and sets for the same story (deterministic variation)"}">Regenerate</button><span style="flex:1"></span><button class="btn primary" id="btn-approve">Approve &amp; Generate</button></div>
        <div id="rev-err">${err ? errBox(err) : ""}</div></div>${edit}</div>
      <div class="card"><div class="row sp"><h2>Script</h2><small class="muted">${d.script.segments.length} segments · ${d.script.total} s ${d.script.estimated ? "(estimated)" : ""}</small></div>
        ${prov ? '<div class="note">Narration provided: audio and timings come from your file, so the text is read-only.</div>' : '<div class="muted" style="margin:8px 0 12px;font-size:13px">Click a line to edit it. Tick lines and use <b>Regenerate selected</b> to have them re-written (needs the local LLM; the result is validated or refused).</div>'}
        <div class="seglist">${rows}</div>
        ${prov ? "" : `<div class="row" style="margin-top:14px"><button class="btn sm" id="apply-script" ${Object.keys(S.scriptEdits).length ? "" : "disabled"}>Apply edits</button><button class="btn sm" id="regen-sel" ${S.regen.size ? "" : "disabled"}>Regenerate selected (${S.regen.size})</button>
          ${Object.keys(S.scriptEdits).length ? '<button class="btn sm ghost" id="discard-script">Discard</button>' : ""}</div>`}
        ${d.script.estimated ? '<small class="dim" style="display:block;margin-top:10px">Real timings come from the narration step (Chatterbox Hindi), which runs after you approve.</small>' : ""}</div></div></section>`;
}
function editStoryPanel() {
  const d = S.draft, o = S.opts, L = lvl(), r = d.review;
  const c = d.graph.cast, pr = c.protagonist, pa = c.principal;
  const beats = d.graph.beats.map(b => `<tr><td class="mono">${esc(b.id)}</td><td>${esc(b.text.slice(0, 44))}${b.text.length > 44 ? "…" : ""}</td>
    <td><select data-be="${esc(b.id)}" data-k="act" ${L < 2 ? "disabled" : ""}>${opt(o.acts, b.act)}</select></td><td><select data-be="${esc(b.id)}" data-k="emotion">${opt(o.emotions, b.emotion)}</select></td>
    <td><select data-be="${esc(b.id)}" data-k="loc" ${L < 2 ? "disabled" : ""}>${opt(Object.keys(o.environments), b.loc)}</select></td><td><select data-be="${esc(b.id)}" data-k="time" ${L < 2 ? "disabled" : ""}>${opt(["day", "dusk", "night"], b.time)}</select></td></tr>`).join("");
  return `<div class="card"><h3 style="margin-bottom:12px">Edit story</h3><div class="edit-grid">
      <label class="f">Title<input id="ed-title" value="${esc(d.graph.title)}"></label><span></span>
      <label class="f">Protagonist type<select id="ed-p-arch">${opt(o.archetypes, pr.archetype)}</select></label><label class="f">Protagonist gender<select id="ed-p-gen">${opt(["male", "female"], pr.gender)}</select></label>
      ${pa ? `<label class="f">Partner type<select id="ed-d-arch">${opt(o.archetypes, pa.archetype)}</select></label><label class="f">Partner gender<select id="ed-d-gen">${opt(["masculine", "feminine", "either"], pa.gender)}</select></label>` : ""}</div>
    <div class="sect"><h3>Beats${L < 2 ? " · emotion (switch to Expert to change acts, places and times)" : ""}</h3><div style="max-height:340px;overflow:auto"><table class="t"><tr><th>id</th><th>line</th><th>act</th><th>emotion</th><th>place</th><th>time</th></tr>${beats}</table></div></div>
    <div class="row" style="margin-top:14px"><button class="btn" id="apply-story">Apply story edits</button><small class="dim">Edits are validated by the story-graph constructor (act grammar, supported places). An invalid edit is refused with the reason.</small></div></div>`;
}
const storyEdits = {};
view.addEventListener("click", async e => {
  const t = e.target.closest("[data-mode],[data-topic],[data-example],[data-clear],[data-env],[data-edit],[data-tab],[data-shot],[data-act],button,[data-nav-prod]");
  if (!t) return;
  if (t.dataset.mode) { S.form.mode = t.dataset.mode; saveForm(); return viewCreate(); }
  if (t.dataset.topic) { S.form.topic = t.dataset.topic; saveForm(); return viewCreate(); }
  if (t.dataset.example !== undefined) { S.form.example = t.dataset.example || null; saveForm(); return viewCreate(); }
  if (t.dataset.clear) { e.preventDefault(); S.form[t.dataset.clear] = ""; saveForm(); return viewCreate(); }
  if (t.dataset.env) { S.form.environment.mode = t.dataset.env; saveForm(); return viewCreate(); }
  if (t.id === "go") return analyze();
  if (t.dataset.edit) { S.scriptEdits[t.dataset.edit] = S.draft.script.segments.find(g => g.id === t.dataset.edit).text; renderReview(); const ta = $(`textarea[data-seg="${t.dataset.edit}"]`); ta && ta.focus(); return; }
  if (t.id === "btn-edit") { S.edit = !S.edit; return renderReview(); }
  if (t.id === "btn-regen") return reviewAct("regen", () => api("/story", { draft_id: S.draft.id, regenerate: true }), "Regenerating…");
  if (t.id === "btn-approve") return approve();
  if (t.id === "apply-script") return reviewAct("script", () => api("/script", { draft_id: S.draft.id, segments: Object.entries(S.scriptEdits).map(([id, text]) => ({ id, text })) }), "Applying…", () => { S.scriptEdits = {}; });
  if (t.id === "discard-script") { S.scriptEdits = {}; return renderReview(); }
  if (t.id === "regen-sel") return reviewAct("script", () => api("/script", { draft_id: S.draft.id, regenerate: [...S.regen] }), "Rewriting with the local LLM…", () => { S.regen = new Set(); });
  if (t.id === "apply-story") {
    const ed = { beats: {}, cast: {} };
    $$("[data-be]").forEach(s => { const b = S.draft.graph.beats.find(x => x.id === s.dataset.be); if (b && b[s.dataset.k] !== s.value) (ed.beats[b.id] = ed.beats[b.id] || {})[s.dataset.k] = s.value; });
    const pr = S.draft.graph.cast.protagonist, pa = S.draft.graph.cast.principal;
    const pv = { archetype: $("#ed-p-arch").value, gender: $("#ed-p-gen").value }; if (pv.archetype !== pr.archetype || pv.gender !== pr.gender) ed.cast.protagonist = pv;
    if (pa) { const dv = { archetype: $("#ed-d-arch").value, gender: $("#ed-d-gen").value }; if (dv.archetype !== pa.archetype || dv.gender !== pa.gender) ed.cast.partner = dv; }
    const ti = $("#ed-title").value.trim(); if (ti && ti !== S.draft.graph.title) ed.title = ti;
    if (!Object.keys(ed.beats).length) delete ed.beats; if (!Object.keys(ed.cast).length) delete ed.cast;
    if (!Object.keys(ed).length) return toast("nothing changed");
    return reviewAct("story", () => api("/story", { draft_id: S.draft.id, edits: ed }), "Validating…");
  }
  if (t.dataset.tab) { S.insp.tab = t.dataset.tab; return renderFinal(); }
  if (t.dataset.shot) { S.insp.sel = t.dataset.shot; S.insp.preview = null; return renderFinal(); }
});
view.addEventListener("change", e => { const c = e.target; if (c.dataset && c.dataset.regen) { c.checked ? S.regen.add(c.dataset.regen) : S.regen.delete(c.dataset.regen); renderReview(); } });
async function reviewAct(kind, fn, busyText, after) {
  const b = $("#rev-err"); b.innerHTML = `<div class="note"><span class="spin"></span>${esc(busyText)}</div>`;
  try { const d = await fn(); S.draft = d; if (after) after(); renderReview(); }
  catch (e) { renderReview(e); }
}
async function approve() {
  const b = $("#btn-approve"); b.disabled = true; b.innerHTML = '<span class="spin"></span>Starting…';
  try { const r = await api("/generate", { draft_id: S.draft.id, approve: true }); location.hash = "#/production/" + r.production_id; }
  catch (e) { renderReview(e); }
}

// ------------------------------------------------------------------------------------------------ PRODUCTION (dashboard + final)
function stopWatch() { const P = S.prod; if (P.es) { P.es.close(); P.es = null; } clearInterval(P.tick); clearInterval(P.poll); P.tick = P.poll = null; }
async function viewProduction(pid) {
  const P = S.prod; P.id = pid; P.state = null; P.meta = null; P.logs = []; S.insp = { plan: null, sel: null, raw: null, tab: "overview", preview: null, busy: false, last: null };
  view.innerHTML = '<div class="muted"><span class="spin"></span>Loading production…</div>';
  try { P.meta = await api("/production/" + pid); } catch (e) { view.innerHTML = errBox(e); return; }
  P.state = P.meta.status;
  if (P.state.status === "completed" && P.meta.summary) return renderFinal();
  renderDash();
  if (!["completed", "failed", "cancelled"].includes(P.state.status)) watch(pid);
  else if (P.state.status === "completed") { P.meta = await api("/production/" + pid); renderFinal(); }
}
function watch(pid) {
  const P = S.prod; stopWatch();
  const es = new EventSource(`/api/production/${pid}/events`); P.es = es;
  es.onmessage = ev => {
    const m = JSON.parse(ev.data); P.msgAt = Date.now() / 1000;
    if (m.event.event === "log") { P.logs.push(m.event.message); if (P.logs.length > 200) P.logs.shift(); }
    if (m.state) { P.state = m.state; P.skew = m.state.now - Date.now() / 1000; renderDash(); if (["completed", "failed", "cancelled"].includes(m.state.status)) finishWatch(); }
  };
  es.onerror = () => { $("#conn").className = "conn bad"; };
  es.onopen = () => { $("#conn").className = "conn ok"; };
  P.tick = setInterval(renderDash, 1000);
  P.poll = setInterval(async () => { if (Date.now() / 1000 - P.msgAt > 8) { try { P.state = await api(`/production/${pid}/status`); renderDash(); if (["completed", "failed", "cancelled"].includes(P.state.status)) finishWatch(); } catch (e) { /* server away */ } } }, 4000);
}
async function finishWatch() {
  const P = S.prod; const id = P.id; stopWatch();
  try { P.meta = await api("/production/" + id); } catch (e) { return; }
  if (location.hash.indexOf(id) < 0) return;
  if (P.state.status === "completed" && P.meta.summary) renderFinal(); else renderDash();
}
const ICON = { completed: "✓", running: "▶", pending: "○", skipped: "✓", failed: "✗", cancelled: "■" };
function renderDash() {
  const P = S.prod, st = P.state, m = P.meta || {}; if (!st) return;
  if (location.hash.indexOf(P.id) < 0) return;
  const now = Date.now() / 1000 + (P.skew || 0), running = st.status === "running";
  const elapsed = st.started ? ((st.ended || now) - st.started) : 0;
  const L = lvl();
  const stages = st.stages.map(s => {
    let ms = s.message || "", tm = "";
    if (s.status === "completed" || s.status === "skipped") tm = s.seconds ? s.seconds.toFixed(1) + " s" : "";
    if (s.status === "running") { tm = mmss(st.last && st.last.stage === s.id ? (st.last.elapsed_seconds || 0) + (now - st.now < 0 ? 0 : (now - st.now)) : 0); }
    const bar = s.status === "running" && s.fraction > 0 ? `<div class="bar sm" style="margin-top:6px"><i style="width:${Math.round(s.fraction * 100)}%"></i></div>` : "";
    return `<li class="stage ${s.status}"><span class="ic">${ICON[s.status] || "○"}</span><span class="nm">${esc(s.name)}</span><span class="ms">${esc(ms)}${bar}</span><span class="tm">${esc(tm)}</span></li>`;
  }).join("");
  const pct = Math.round((st.overall || 0) * 1000) / 10;
  const err = st.status === "failed" && st.error ? `<div class="err" role="alert"><b>Failed${st.error.stage ? " in " + esc((st.stages.find(x => x.id === st.error.stage) || {}).name || st.error.stage) : ""}: ${esc(st.error.message || st.error.error || "")}</b>${(st.error.reasons || []).length ? "<ul>" + st.error.reasons.map(r => `<li>${esc(r)}</li>`).join("") + "</ul>" : ""}${st.error.hint ? `<div class="hint">${esc(st.error.hint)}</div>` : ""}
      <div class="row" style="margin-top:12px">${m.settings && m.mode !== undefined ? `<a class="btn sm" href="#/review/${esc((m.draft_id || ""))}" ${m.draft_id ? "" : "hidden"}>Back to review</a>` : ""}<button class="btn sm" id="btn-retry">Try again</button></div></div>` : "";
  const cancelled = st.status === "cancelled" ? `<div class="note">This production was cancelled. Frames that were fully rendered before the cancel are kept in the frame cache only when their render finished; starting again re-uses everything that is cached.</div>` : "";
  view.innerHTML = `<section><div class="dash-h"><div><div class="muted">Production · ${esc(m.mode || "")}${m.kind === "rerender" ? " · re-render of edits" : ""} · <span class="mono">${esc(P.id)}</span></div><h1>${esc(m.title || "Production")}</h1></div>
      <div class="row"><span class="pill ${st.status}">${st.status === "queued" ? "queued" + (st.queue_position ? " #" + st.queue_position : "") : st.status}</span>${["running", "queued"].includes(st.status) ? '<button class="btn danger sm" id="btn-cancel">Cancel</button>' : ""}</div></div>
    <div class="card"><div class="overall"><div class="pct">${pct.toFixed(pct % 1 ? 1 : 0)}%</div><div><div class="bar ${st.status === "completed" ? "done" : ""}"><i style="width:${pct}%"></i></div>
      <small class="dim">Overall = measured progress of every stage, weighted by its typical cost${st.pass_no ? " · QC auto-fix pass " + st.pass_no : ""}</small></div><div class="mono muted">${mmss(elapsed)}</div></div></div>
    ${detail(st, now)}
    <div class="card" style="margin-top:16px"><ul class="stages">${stages}</ul></div>
    ${err}${cancelled}
    ${(L >= 1 || st.status === "failed") && P.logs.length ? `<div class="sect"><h3>Engine log</h3><div class="logbox" id="logbox">${esc(P.logs.slice(-40).join("\n"))}</div></div>` : ""}
  </section>`;
  const lb = $("#logbox"); if (lb) lb.scrollTop = lb.scrollHeight;
}
function detail(st, now) {
  const a = st.active, L = st.last || {}; if (!a || !["running"].includes(st.status)) return "";
  const s = st.stages.find(x => x.id === a); if (!s || s.status !== "running") return "";
  const el = (L.elapsed_seconds || 0) + Math.max(0, now - st.now);
  const M = (l, v, sub) => `<div class="metric"><div class="l">${l}</div><div class="v">${v}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div>`;
  let cells = "";
  if (a === "blender_render" || a === "compositing") {
    cells = M("Shot", L.shot != null ? `${L.shot} / ${L.total_shots}` : "—") + M("Frame", L.frame != null ? `${L.frame} / ${L.total_frames}` : "—", a === "blender_render" && L.rendered != null ? `${L.rendered} of ${L.to_render} rendered now` : "")
      + M("Elapsed", mmss(el)) + M(a === "blender_render" ? "Render FPS" : "Frames per second", L.fps != null ? L.fps : "—") + M("ETA", L.eta_seconds != null ? mmss(Math.max(0, L.eta_seconds - Math.max(0, now - st.now))) : "—")
      + (a === "blender_render" ? M("Cache", L.cache_reused != null ? L.cache_reused : "—", "frames reused, not re-rendered") : "");
  } else cells = M("Elapsed", mmss(el)) + (L.cached != null ? M("Cache", L.cached ? "hit" : "miss") : "");
  return `<div class="card" style="margin-top:16px"><div class="row sp"><h2>${esc(s.name)}</h2><span class="muted">${esc(L.current_operation || s.message || "")}</span></div><div class="detail">${cells}</div></div>`;
}
view.addEventListener("click", async e => {
  const t = e.target.closest("button"); if (!t) return;
  if (t.id === "btn-cancel") { if (!confirm("Cancel this production? Blender and ffmpeg are stopped immediately.")) return; t.disabled = true; try { S.prod.state = await api("/cancel", { production_id: S.prod.id }); finishWatch(); } catch (er) { toast(er.error ? er.error.message : "cancel failed"); } }
  if (t.id === "btn-variation") { t.disabled = true; t.innerHTML = '<span class="spin"></span>Preparing…'; try { S.draft = await api("/story", { draft_id: S.prod.meta.draft_id, regenerate: true }); S.edit = false; S.scriptEdits = {}; S.regen = new Set(); location.hash = "#/review/" + S.draft.id; } catch (er) { toast(er.error ? er.error.message : "could not start a new variation"); t.disabled = false; } }
  if (t.id === "btn-retry") { try { const j = S.prod.meta; const r = await api("/generate", { draft_id: j.draft_id, approve: true }); location.hash = "#/production/" + r.production_id; } catch (er) { toast(er.error ? er.error.message : "could not restart"); } }
});

// ------------------------------------------------------------------------------------------------ FINAL
const stat = (l, val, s) => `<div class="stat"><div class="l">${l}</div><div class="v">${val}</div>${s ? `<div class="s">${s}</div>` : ""}</div>`;
function overviewHtml(sm) {
  const q = sm.qc, T = sm.timings, C = sm.cache, v = sm.video, fx = q.autofix_rounds.filter(r => r.fixes && r.fixes.length);
  const want = (sm.requested || {}).duration;
  return `<div class="grid g3">${stat("Duration", v.duration.toFixed(1) + " s", (want ? "requested about " + want + " s · " : "") + v.frames + " frames @ " + v.fps + " fps")}${stat("Resolution", v.width + "×" + v.height, v.size_mb + " MB")}${stat("Shots", sm.shots, sm.scenes.length + " scene(s)")}
      ${stat("Characters", sm.characters.length, esc(sm.characters.map(c => c.role.replace(/_/g, " ")).join(", ")))}${stat("Environments", new Set(sm.scenes.map(s => s.loc)).size, esc(sm.scenes.map(s => s.loc.replace(/_/g, " ") + " (" + s.time + ")").join(", ")))}
      ${stat("Audio events", (sm.audio.foley_events || 0) + (sm.audio.sfx_events || 0), (sm.audio.foley_events || 0) + " foley + " + (sm.audio.sfx_events || 0) + " sfx · music: " + esc((sm.audio.music_moods || []).join(", ")))}</div>
    <div class="sect"><h3>Time</h3><div class="grid g4">${stat("Total render", mmss(T.total), fmt1(T.total) + " s")}${stat("Blender", mmss(T.blender), fmt1(T.blender) + " s")}${stat("Audio", fmt1(T.audio) + " s", sm.audio.mix_cache_hit ? "mix from cache" : "mix synthesised")}${stat("QC", fmt1(T.qc) + " s", q.passes + " pass(es)")}
      ${stat("Compositing", mmss(T.compositing), fmt1(T.compositing) + " s")}${stat("Scene direction", fmt1(T.scene_direction) + " s", "cast, blocking, camera, critic")}${stat("Narration", T.narration ? fmt1(T.narration) + " s" : "-", C.narration_cached ? "from cache" : (sm.mode === "production" ? "provided" : ""))}${stat("Cache reuse", C.frames ? C.reuse_pct + "%" : "-", C.frames ? `${C.reused} of ${C.frames} frames reused` : "")}</div></div>
    <div class="sect"><h3>QC · ${q.passed_checks.length} passed${q.failed_checks.length ? ` · <span class="bad">${q.failed_checks.length} failed</span>` : ""} of ${q.n_checks}</h3>
      ${q.failed_checks.length ? `<div class="err" style="margin:0 0 12px"><b>Failed checks</b><ul>${q.failed_checks.map(x => `<li>${esc(x.replace(/_/g, " "))}</li>`).join("")}</ul><div class="hint">The engine could not repair this automatically${S.prod.meta && S.prod.meta.draft_id ? ". Another variation re-draws the story details and the cast (deterministically) but is not guaranteed to clear it." : "."}</div>${S.prod.meta && S.prod.meta.draft_id ? `<div class="row" style="margin-top:10px"><button class="btn sm" id="btn-variation">Try another variation</button></div>` : ""}</div>` : ""}
      <div class="qc-list">${q.checks.map(c => `<div class="${c.ok ? "" : "bad-row"}"><span class="${c.ok ? "y" : "x"}">${c.ok ? "✓" : "✗"}</span><span>${esc(c.name.replace(/_/g, " "))}</span></div>`).join("")}</div>
      <div style="margin-top:12px"><small class="muted">Auto-fixes performed: ${q.critic_fixes ? q.critic_fixes + " framing / lighting fix(es) by the critic before rendering" : "none by the critic"}${fx.length ? "; " + fx.map(r => `QC round ${r.round}: ${esc(r.fixes.join("; "))}`).join("; ") : "; no QC auto-fix was needed"}.</small></div></div>
    <div class="sect"><h3>Files</h3><div class="files">${Object.entries(sm.files).filter(([k]) => k !== "absolute_dir").map(([k, p]) => `<div><span class="muted">${esc(k.replace(/_/g, " "))}</span><code>${esc(p)}</code></div>`).join("")}<div><span class="muted">folder</span><code>${esc(sm.files.absolute_dir)}</code></div></div></div>`;
}
function renderFinal() {
  const P = S.prod, m = P.meta, sm = m && m.summary; if (!sm) return renderDash();
  if (location.hash.indexOf(P.id) < 0) return;
  const q = sm.qc, wide = S.insp.wide && sm.files.video_16x9;
  const src = `/api/production/${P.id}/video${wide ? "?variant=16x9" : ""}`;
  const tabs = `<div class="tabs" style="margin-top:0">${[["overview", "Overview"], ["inspector", "Movie inspector"], ["expert", "Plan and graph"]].map(([k, l]) => `<button data-tab="${k}" class="${S.insp.tab === k ? "on" : ""}">${l}</button>`).join("")}</div>`;
  const body = S.insp.tab === "inspector" ? inspectorHtml() : S.insp.tab === "expert" ? expertHtml() : overviewHtml(sm);
  view.innerHTML = `<section><div class="dash-h"><div><div class="muted">Your movie${m.parent ? ` · re-render of <a href="#/production/${esc(m.parent)}">${esc(m.parent)}</a>` : ""} · <span class="mono">${esc(P.id)}</span></div><h1>${esc(sm.title)}</h1></div>
      <div class="row"><span class="pill ${q.passed ? "completed" : "failed"}">QC ${q.passed_checks.length}/${q.n_checks}</span><a class="btn sm" href="/api/production/${esc(P.id)}/download">Download MP4</a>${sm.files.video_16x9 ? `<a class="btn sm" href="/api/production/${esc(P.id)}/download?variant=16x9">Download 16:9</a>` : ""}<a class="btn sm" href="#/">New movie</a></div></div>
    <div class="final"><div><div class="player ${wide ? "wide" : ""}"><video id="vid" controls playsinline preload="metadata" poster="/api/production/${esc(P.id)}/poster" src="${src}"></video></div>
      ${sm.files.video_16x9 ? `<div class="row" style="justify-content:center;margin-top:12px"><div class="seg"><button data-fmt="9x16" class="${wide ? "" : "on"}">9:16</button><button data-fmt="16x9" class="${wide ? "on" : ""}">16:9</button></div></div>` : ""}</div>
      <div><div class="muted" style="margin-bottom:10px">${esc(sm.format)} · ${esc(sm.mode)} mode${sm.director && Object.keys(sm.director).length ? " · director: " + esc(JSON.stringify(sm.director)) : ""}${sm.captions === false ? " · captions off" : ""}</div>${tabs}<div id="tabbody">${body}</div></div></div></section>`;
  if (S.insp.tab === "inspector") loadInspector();
  if (S.insp.tab === "expert") loadExpert();
}
view.addEventListener("click", e => { const b = e.target.closest("[data-fmt]"); if (b) { S.insp.wide = b.dataset.fmt === "16x9"; renderFinal(); } });

// ------------------------------------------------------------------------------------------------ INSPECTOR
async function loadInspector() {
  const I = S.insp; if (I.plan || I.loading) return; I.loading = true;
  try { I.plan = await api(`/production/${S.prod.id}/plan`); if (!I.sel) I.sel = I.plan.shots[0].id; } catch (e) { $("#tabbody").innerHTML = errBox(e); return; } finally { I.loading = false; }
  if (S.insp.tab === "inspector" && $("#tabbody")) $("#tabbody").innerHTML = inspectorHtml();
}
function inspectorHtml() {
  const I = S.insp, P = I.plan; if (!P) return '<div class="muted"><span class="spin"></span>Loading the shot plan…</div>';
  const edited = new Set(((P.edits || {}).impact || {}).shots_affected || []);
  const tl = P.shots.map(s => `<div class="tl ${I.sel === s.id ? "on" : ""} ${edited.has(s.id) ? "edited" : ""}" data-shot="${s.id}" style="width:${Math.max(64, Math.round(s.duration * 22))}px" title="${esc(s.act || "")}"><span class="q ${s.qc.state}"></span>
      <img loading="lazy" alt="" src="/api/production/${S.prod.id}/shot/${s.id}.jpg"><div class="n"><span>${String(s.index).padStart(2, "0")}</span><span>${s.duration.toFixed(1)}s</span></div></div>`).join("");
  const sh = P.shots.find(s => s.id === I.sel), w = (P.working_shots || {})[I.sel];
  return `<div class="muted" style="margin-bottom:8px">${P.shots.length} shots · click a shot · <span class="ok">●</span> QC ok <span class="bad">●</span> flagged ${edited.size ? '· <span style="color:var(--accent)">▬</span> edited' : ""}</div><div class="timeline">${tl}</div>${sh ? shotPanel(sh, w) : ""}${editBanner(P)}`;
}
function shotPanel(sh, w) {
  const I = S.insp, P = I.plan, c = (w && w.camera) || sh.camera || {}, o = P.options, ed = !!w;
  const chars = ((w && w.characters) || sh.characters).map(x => `<span class="tag"><b>${esc(x.id)}</b> ${esc(x.role.replace(/_/g, " "))} · ${esc(x.archetype)} · ${esc(x.skin)} · ${esc(x.palette)} ${esc(x.top)}</span>`).join("");
  const acts = sh.actions.map(a => `${a.t.toFixed(1)}s  ${a.char} ${a.action}${a.detail ? " → " + a.detail : ""}`).join("\n") || "no scripted actions (idle, gaze and breathing continue)";
  const audio = sh.audio_events.length ? sh.audio_events.map(a => `<span class="tag">${a.t.toFixed(1)}s <b>${esc(a.kind)}</b></span>`).join("") : '<span class="muted">none in this shot</span>';
  const camEdit = sh.camera ? `<div class="sect"><h3>Edit camera (this shot only)</h3><div class="grid g4">
      <label class="f">Size<select id="ed-size">${opt(o.sizes, c.size)}</select></label><label class="f">Move<select id="ed-move">${opt(o.moves, c.move)}</select></label>
      <label class="f">Shift x <span class="mono" id="v-dx">${Math.round(c.dx || 0)}</span><input type="range" id="ed-dx" min="-300" max="300" step="10" value="${c.dx || 0}"></label><label class="f">Shift y <span class="mono" id="v-dy">${Math.round(c.dy || 0)}</span><input type="range" id="ed-dy" min="-300" max="300" step="10" value="${c.dy || 0}"></label></div>
      <div class="row" style="margin-top:10px"><button class="btn sm" data-act="cam">Apply camera</button></div></div>` : '<div class="note">This is a procedural insert shot (screen / money flow): it has no camera to edit.</div>';
  const emo = `<div class="sect"><h3>Edit story beat</h3><div class="grid g4"><label class="f">Emotion<select id="ed-emo">${opt(o.emotions, (w && w.emotion) || sh.emotion)}</select></label>
      ${lvl() === 2 ? `<label class="f">Act<select id="ed-act">${opt(o.acts, (w && w.act) || sh.act)}</select></label>` : ""}</div><div class="row" style="margin-top:10px"><button class="btn sm" data-act="beat">Apply to beat ${esc(sh.beats[0] || "")}</button><small class="dim">Re-directs the beat through the story-graph validator; the act grammar still applies.</small></div></div>`;
  const look = sh.characters.length ? `<div class="sect"><h3>Edit character look (every shot they appear in)</h3><div class="grid g4"><label class="f">Character<select id="ed-ch">${sh.characters.map(x => `<option value="${x.id}">${esc(x.id)} · ${esc(x.role.replace(/_/g, " "))}</option>`).join("")}</select></label>
      <label class="f">Skin<select id="ed-skin"><option value="">unchanged</option>${opt(o.skins, "")}</select></label><label class="f">Wardrobe palette<select id="ed-pal"><option value="">unchanged</option>${opt(o.palettes, "")}</select></label><label class="f">Top<select id="ed-top"><option value="">unchanged</option>${opt(o.tops, "")}</select></label></div>
      <div class="row" style="margin-top:10px"><button class="btn sm" data-act="char">Apply look</button></div></div>` : "";
  return `<div class="card" style="margin-top:8px"><div class="shotpanel"><div><img class="pv" alt="shot preview" src="${esc(I.preview || `/api/production/${S.prod.id}/shot/${sh.id}.jpg`)}"><div class="muted" style="margin-top:8px;font-size:12px">${I.preview ? "preview of the edited plan (Blender)" : "frame from the final film"}</div>
      <div class="row" style="margin-top:10px"><button class="btn sm" data-act="preview" ${ed ? "" : "disabled"} title="renders this shot of the edited plan with Blender (frame-cached)">Preview edited shot</button></div></div>
    <div><div class="row sp"><h2>Shot ${String(sh.index).padStart(2, "0")} <small class="muted">${esc(sh.id)} · ${esc(sh.act || "")}</small></h2><span class="pill ${sh.qc.state === "ok" ? "completed" : "failed"}">QC ${sh.qc.state === "ok" ? "ok" : "flagged"}</span></div>
      <p class="hook" style="margin:10px 0;font-size:17px">${esc(sh.text)}</p>
      <div><span class="tag">time <b>${sh.t0}–${sh.t1}s</b> (${sh.duration}s)</span><span class="tag">environment <b>${esc(sh.location.loc.replace(/_/g, " "))} · ${esc(sh.location.time)}</b></span><span class="tag">emotion <b>${esc((w && w.emotion) || sh.emotion || "-")}</b></span><span class="tag">lighting <b>${esc(sh.lighting.mood || "-")}</b></span>
      ${sh.camera ? `<span class="tag">camera <b>${esc(c.target || "")} · ${esc(c.size)} · ${esc(c.move)}${c.dx || c.dy ? ` · shift ${Math.round(c.dx || 0)},${Math.round(c.dy || 0)}` : ""}</b></span>` : ""}${ed ? '<span class="tag" style="border-color:var(--accent)"><b>edited</b></span>' : ""}</div>
      ${sh.qc.flags.length ? `<div class="err" style="margin:10px 0"><b>QC flags</b><ul>${sh.qc.flags.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>` : ""}
      <div class="sect"><h3>Characters</h3>${chars || '<span class="muted">none on the set</span>'}</div>
      <div class="sect"><h3>Action</h3><div class="acts-list">${esc(acts).replace(/\n/g, "<br>")}</div></div>
      <div class="sect"><h3>Audio events · mood ${esc(sh.audio_mood || "-")}</h3>${audio}</div>
      ${camEdit}${emo}${look}</div></div></div>`;
}
function editBanner(P) {
  const e = P.edits; if (!e) return "";
  const i = e.impact || {}, wr = (e.warnings || []).map(x => `<li>shot ${esc(x.shot)}: ${esc(x.problems.join(", ").replace(/_/g, " "))}</li>`).join("");
  return `<div class="pending-edit"><b>Pending edits</b> · ${e.ops.length} change(s)<div class="detail" style="margin-top:10px"><div class="metric"><div class="l">Frames to re-render</div><div class="v">${i.frames_to_render} <small class="muted">/ ${i.frames_total}</small></div><div class="s">${i.frames_reused} reused from the cache</div></div>
    <div class="metric"><div class="l">Shots affected</div><div class="v">${(i.shots_affected || []).length}</div><div class="s">${esc((i.shots_affected || []).join(", ") || "none")}</div></div><div class="metric"><div class="l">Audio</div><div class="v">${i.audio_remixed ? "re-mix" : "unchanged"}</div><div class="s">${i.audio_remixed ? "mix only, no video frames" : "cached mix reused"}</div></div></div>
    ${wr ? `<div class="err" style="margin:12px 0"><b>Framing warnings (measured)</b><ul>${wr}</ul></div>` : ""}<small class="dim" style="display:block;margin-top:8px">${esc(i.note || "")}</small>
    <div class="row" style="margin-top:12px"><button class="btn primary sm" data-act="render">Render changes</button><button class="btn sm ghost" data-act="discard">Discard edits</button></div></div>`;
}
async function inspectorEdit(ops) {
  const I = S.insp; I.busy = true;
  try { const r = await api(`/production/${S.prod.id}/edit`, { ops }); I.plan = await api(`/production/${S.prod.id}/plan`); I.preview = null; toast(r.reset ? "edits discarded" : "edit validated"); }
  catch (e) { toast((e.error && e.error.message) || "edit refused"); const el = $("#tabbody"); if (el) el.insertAdjacentHTML("afterbegin", errBox(e)); I.busy = false; return; }
  I.busy = false; $("#tabbody").innerHTML = inspectorHtml();
}
view.addEventListener("input", e => { const t = e.target; if (t.id === "ed-dx" || t.id === "ed-dy") $("#v-" + t.id.slice(3)).textContent = t.value; });
view.addEventListener("click", async e => {
  const b = e.target.closest("[data-act]"); if (!b || !S.insp.plan) return; const I = S.insp, sid = I.sel, sh = I.plan.shots.find(s => s.id === sid);
  if (b.dataset.act === "cam") return inspectorEdit([{ op: "camera", shot: sid, size: $("#ed-size").value, move: $("#ed-move").value, dx: Number($("#ed-dx").value), dy: Number($("#ed-dy").value) }]);
  if (b.dataset.act === "beat") { const op = { op: "beat", beat: sh.beats[0], emotion: $("#ed-emo").value }; if ($("#ed-act")) op.act = $("#ed-act").value; return inspectorEdit([op]); }
  if (b.dataset.act === "char") { const op = { op: "character", char: $("#ed-ch").value }; ["skin", "pal", "top"].forEach(k => { const v = $("#ed-" + k).value; if (v) op[k === "pal" ? "palette" : k] = v; }); if (Object.keys(op).length < 3) return toast("choose a skin, palette or top"); return inspectorEdit([op]); }
  if (b.dataset.act === "discard") return inspectorEdit([{ op: "reset" }]);
  if (b.dataset.act === "preview") { b.disabled = true; b.innerHTML = '<span class="spin"></span>Rendering…'; try { const r = await api("/preview", { production_id: S.prod.id, shot_id: sid, source: "working" }); I.preview = r.url; } catch (er) { toast((er.error && er.error.message) || "preview failed"); } $("#tabbody").innerHTML = inspectorHtml(); return; }
  if (b.dataset.act === "render") { b.disabled = true; try { const r = await api("/render", { production_id: S.prod.id }); location.hash = "#/production/" + r.production_id; } catch (er) { toast((er.error && er.error.message) || "render refused"); b.disabled = false; } }
});
async function loadExpert() {
  const I = S.insp; if (!I.plan) { try { I.plan = await api(`/production/${S.prod.id}/plan`); } catch (e) { /* shown below */ } }
  if (!I.raw) { try { I.raw = await api(`/production/${S.prod.id}/plan?raw=1`); } catch (e) { return; } }
  if (S.insp.tab === "expert" && $("#tabbody")) $("#tabbody").innerHTML = expertHtml();
}
function expertHtml() {
  const I = S.insp; if (!I.plan || !I.raw) return '<div class="muted"><span class="spin"></span>Loading…</div>';
  const g = I.plan.graph;
  const beats = g.beats.map(b => `<tr><td class="mono">${esc(b.id)}</td><td>${esc(b.act)}</td><td>${esc(b.emotion)}</td><td>${esc(b.loc)} · ${esc(b.time)}</td><td>${esc(b.text)}</td></tr>`).join("");
  const shots = I.plan.shots.map(s => `<tr><td class="mono">${esc(s.id)}</td><td>${s.t0}–${s.t1}</td><td>${esc(s.act || "")}</td><td class="mono">${esc(s.camera ? [s.camera.target, s.camera.size, s.camera.move].join(" / ") : "insert")}</td><td>${s.qc.state}</td></tr>`).join("");
  return `<div class="sect" style="margin-top:0"><h3>Story graph · ${g.beats.length} beats</h3><div style="max-height:300px;overflow:auto"><table class="t"><tr><th>id</th><th>act</th><th>emotion</th><th>place</th><th>line</th></tr>${beats}</table></div></div>
    <div class="sect"><h3>Shot plan · ${I.plan.shots.length} shots</h3><div style="max-height:300px;overflow:auto"><table class="t"><tr><th>shot</th><th>time</th><th>act</th><th>camera</th><th>qc</th></tr>${shots}</table></div></div>
    <div class="sect"><h3>plan.json (as rendered)</h3><pre class="json">${esc(JSON.stringify(I.raw, null, 1).slice(0, 60000))}</pre></div>`;
}

// ------------------------------------------------------------------------------------------------ LIST
async function viewList() {
  view.innerHTML = '<div class="muted"><span class="spin"></span>Loading…</div>';
  let items; try { items = await api("/productions"); } catch (e) { view.innerHTML = errBox(e); return; }
  view.innerHTML = `<section><div class="dash-h"><h1>Productions</h1><a class="btn" href="#/">New movie</a></div>${items.length ? `<div class="plist">${items.map(p => `<div class="pcard" data-go="${esc(p.id)}"><div class="im" style="${p.poster ? `background-image:url(/api/production/${esc(p.id)}/poster)` : ""}"></div>
    <div class="b"><div class="row sp"><b>${esc(p.title || p.id)}</b><span class="pill ${p.status}">${p.status}</span></div><small class="muted">${esc(p.mode)}${p.kind === "rerender" ? " · re-render" : ""} · ${esc(p.id)}</small></div></div>`).join("")}</div>` : '<div class="muted">No productions yet.</div>'}</section>`;
  $$("[data-go]").forEach(c => c.addEventListener("click", () => { location.hash = "#/production/" + c.dataset.go; }));
}

ping(); route();
