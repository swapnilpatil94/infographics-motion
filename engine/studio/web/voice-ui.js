"use strict";
const voiceViewState = {profiles:[],activeId:null,loaded:false,busy:false,recording:false,recorder:null,stream:null,chunks:[],error:null};
async function viewVoice() {
  const view = document.querySelector("#view");
  view.innerHTML = `<section class="kflow"><div class="khero"><h1>Voice Setup</h1><p>Upload your own voice sample or record it live. Studio cleans the audio and saves a reusable local Chatterbox voice reference.</p></div>
  <div class="card kcard"><div class="row sp"><h2>Voice profiles</h2><button class="btn sm" id="voice-refresh">Refresh</button></div>
  <div class="grid two" style="margin-top:16px;gap:14px">
    <label class="f">Upload a voice sample<input id="voice-file" type="file" accept="audio/*,.wav,.mp3,.m4a,.flac,.ogg,.webm,.mp4" ${voiceViewState.busy || voiceViewState.recording ? "disabled" : ""}></label>
    <div><div class="f" style="margin-bottom:7px">Record live</div><button class="btn ${voiceViewState.recording ? "danger" : ""}" id="voice-record" ${voiceViewState.busy ? "disabled" : ""}>${voiceViewState.recording ? "Stop recording" : "Record voice"}</button><small class="muted" style="display:block;margin-top:7px">10–20 seconds of clear speech is a good start.</small></div>
  </div>
  <div id="voice-error" style="margin-top:12px">${voiceViewState.error ? errBox(voiceViewState.error) : ""}</div>
  ${voiceViewState.busy ? '<p class="muted"><span class="spin"></span> Cleaning and saving audio…</p>' : ""}
  <div class="grid two" style="margin-top:18px;gap:12px">${voiceViewState.profiles.map(p => '<div class="card" style="background:var(--bg2)"><div class="row sp"><div><h3>' + esc(p.name) + '</h3><small class="muted">' + (p.duration_seconds == null ? "duration unknown" : p.duration_seconds + " seconds") + ' · denoised WAV</small></div>' + (voiceViewState.activeId === p.id ? '<span class="pill completed">Active</span>' : '') + '</div><audio controls preload="metadata" style="width:100%;margin-top:12px" src="/api/voice-references/' + esc(p.id) + '/wav"></audio><button class="btn ' + (voiceViewState.activeId === p.id ? 'ghost' : 'primary') + '" data-activate-voice="' + esc(p.id) + '" style="margin-top:12px" ' + (voiceViewState.busy ? 'disabled' : '') + '>' + (voiceViewState.activeId === p.id ? 'Active reference' : 'Use for narration') + '</button></div>').join("")}</div>
  ${voiceViewState.profiles.length ? "" : '<p class="muted" style="margin-top:18px">No saved voices yet. Upload a file or record a sample above.</p>'}
  <div class="note" style="margin-top:18px">Cleaning: rumble removal, conservative FFmpeg noise reduction, speech-band filtering and loudness normalization. The original and cleaned WAV stay on this machine under <code>output/voice/references/</code>. Preview the cleaned result before using it. Only clone voices you own or have permission to use.</div></div></section>`;
  if (!voiceViewState.loaded) await refreshVoiceProfiles();
}
async function refreshVoiceProfiles() {
  try { const r = await api("/voice-references"); voiceViewState.profiles = r.profiles || []; voiceViewState.activeId = r.active_id || null; voiceViewState.loaded = true; voiceViewState.error = null; }
  catch (e) { voiceViewState.loaded = true; voiceViewState.error = e; }
  if ((location.hash || "") === "#/voice") viewVoice();
}
async function uploadVoiceFile(file) {
  if (!file) return;
  voiceViewState.busy = true; voiceViewState.error = null; viewVoice();
  try {
    const r = await fetch("/api/voice-references?name=" + encodeURIComponent(file.name || "recorded-voice.webm"), {method:"POST",headers:{"Content-Type":"application/octet-stream"},body:file});
    const j = await r.json(); if (!r.ok) throw j;
    voiceViewState.loaded = false; await refreshVoiceProfiles();
  } catch (e) { voiceViewState.error = e; }
  voiceViewState.busy = false; if ((location.hash || "") === "#/voice") viewVoice();
}
async function startVoiceCapture() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    voiceViewState.error = {error:{code:"recording_not_supported",message:"Live recording is unavailable in this browser. Use upload instead."}}; return viewVoice();
  }
  try {
    voiceViewState.stream = await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    const mime = ["audio/webm;codecs=opus","audio/webm","audio/mp4"].find(x => MediaRecorder.isTypeSupported(x));
    voiceViewState.recorder = new MediaRecorder(voiceViewState.stream, mime ? {mimeType:mime} : undefined);
    voiceViewState.chunks = [];
    voiceViewState.recorder.ondataavailable = e => { if (e.data?.size) voiceViewState.chunks.push(e.data); };
    voiceViewState.recorder.onstop = async () => {
      const blob = new Blob(voiceViewState.chunks,{type:voiceViewState.recorder ? voiceViewState.recorder.mimeType : "audio/webm"});
      if (voiceViewState.stream) voiceViewState.stream.getTracks().forEach(t => t.stop());
      voiceViewState.stream = null; voiceViewState.recorder = null; voiceViewState.chunks = []; voiceViewState.recording = false;
      if (blob.size) await uploadVoiceFile(new File([blob],"recorded-voice-"+Date.now()+".webm",{type:blob.type || "audio/webm"}));
      else { voiceViewState.error = {error:{code:"empty_voice_audio",message:"The recording was empty. Try again."}}; viewVoice(); }
    };
    voiceViewState.recorder.start(); voiceViewState.recording = true; voiceViewState.error = null; viewVoice();
  } catch (_) {
    if (voiceViewState.stream) voiceViewState.stream.getTracks().forEach(t => t.stop());
    voiceViewState.stream = null; voiceViewState.recording = false;
    voiceViewState.error = {error:{code:"microphone_access_failed",message:"Allow microphone access for localhost, then try again."}}; viewVoice();
  }
}
document.addEventListener("change", e => { if (e.target.id === "voice-file") uploadVoiceFile(e.target.files && e.target.files[0]); });
document.addEventListener("click", async e => {
  const rec = e.target.closest("#voice-record"); if (rec) { if (voiceViewState.recording && voiceViewState.recorder) voiceViewState.recorder.stop(); else startVoiceCapture(); return; }
  if (e.target.closest("#voice-refresh")) { voiceViewState.loaded = false; refreshVoiceProfiles(); return; }
  const activate = e.target.closest("[data-activate-voice]"); if (activate) {
    activate.disabled = true;
    try { await api("/voice-references/" + encodeURIComponent(activate.dataset.activateVoice) + "/activate", {}); voiceViewState.loaded = false; await refreshVoiceProfiles(); toast("Voice reference activated"); }
    catch (err) { voiceViewState.error = err; viewVoice(); }
  }
});
