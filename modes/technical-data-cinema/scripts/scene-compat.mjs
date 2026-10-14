/**
 * Applies a narrowly-scoped compatibility layer to otherwise complete model-generated scenes.
 * It does not invent a scene or bypass browser/visual QA: it only makes random calls repeatable
 * for each absolute timestamp and supplies the render-only presentation contract.
 */
export function applySceneCompatibility(source) {
  let html = String(source || "");
  const changes = [];
  if (!/^\s*<!doctype html>/i.test(html)) return { html, changes };

  let randomCalls = 0;
  html = html.replace(/(<script\b[^>]*>)([\s\S]*?)(<\/script\s*>)/gi, (whole, open, body, close) => {
    if (/\bsrc\s*=/.test(open)) return whole;
    const patched = body.replace(/\bMath\s*\.\s*random\s*\(\s*\)/g, () => {
      randomCalls += 1;
      return "window.__tdcRandom()";
    });
    return open + patched + close;
  });
  if (randomCalls) changes.push(`made ${randomCalls} Math.random() call(s) timestamp-deterministic`);

  const hasRenderOnly = /new\s+URLSearchParams\s*\(\s*(?:window\.)?location\.search\s*\)/.test(html) &&
    /\.get\s*\(\s*["']render["']\s*\)/.test(html);
  if (!hasRenderOnly) changes.push("added render-only query handling");

  if (randomCalls || !hasRenderOnly) {
    const runtime = String.raw`<script id="tdc-compat-runtime">
(() => {
  const renderOnly = new URLSearchParams(window.location.search).get("render") === "1";
  let seed = 0x59414e54;
  const random = () => {
    seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
    return seed / 4294967296;
  };
  window.__tdcRandom = random;
  Math.random = random;
  let wrappedRenderAt;
  Object.defineProperty(window, "renderAt", {
    configurable: true,
    enumerable: true,
    get() { return wrappedRenderAt; },
    set(fn) {
      if (typeof fn !== "function") { wrappedRenderAt = fn; return; }
      wrappedRenderAt = function(seconds) {
        const t = Number(seconds) || 0;
        seed = (0x59414e54 ^ (Math.round(t * 1000) >>> 0)) >>> 0;
        return fn.call(this, seconds);
      };
    }
  });
  if (renderOnly) {
    const style = document.createElement("style");
    style.id = "tdc-compat-render-only-style";
    style.textContent = `
      html,body{margin:0!important;width:100%!important;height:100%!important;overflow:hidden!important;background:#050607!important}
      button,input,select,textarea,nav,[role="toolbar"],[role="navigation"],.controls,.toolbar,.editor,.transport,.playback-controls,.timeline,.preview-ui,.cursor,.helper,.watermark{display:none!important;visibility:hidden!important;opacity:0!important}
      body{cursor:none!important}
    `;
    document.head.appendChild(style);
  }
})();
</script>`;
    if (/<\/head\s*>/i.test(html)) html = html.replace(/<\/head\s*>/i, runtime + "\n</head>");
    else html = html.replace(/<body\b/i, runtime + "\n<body");
  }
  return { html, changes };
}
