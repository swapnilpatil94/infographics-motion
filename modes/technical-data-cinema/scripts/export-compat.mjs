export function installDeterministicCompatibility(source) {
  if (!/^<!doctype html>/i.test(source)) return source;
  const prelude = '<script>/* TDC deterministic compatibility layer */(function(){let seed=0x6d2b79f5;window.__tdcSeedRandom=function(v){seed=(v>>>0)||1};Math.random=function(){seed=(seed+0x6D2B79F5)|0;let t=seed;t=Math.imul(t^(t>>>15),t|1);t^=t+Math.imul(t^(t>>>7),t|61);return ((t^(t>>>14))>>>0)/4294967296};if(new URLSearchParams(location.search).get("render")==="1")window.requestAnimationFrame=function(){return 0};})();<\/script>';
  const renderShim = '<script>/* TDC export compatibility */(function(){const q=new URLSearchParams(location.search);if(q.get("render")==="1"){document.documentElement.dataset.tdcRenderOnly="1";document.body.dataset.tdcRenderOnly="1";const s=document.createElement("style");s.textContent="html,body{margin:0!important;width:100%!important;height:100%!important;overflow:hidden!important}body[data-tdc-render-only=1] button,body[data-tdc-render-only=1] input,body[data-tdc-render-only=1] select,body[data-tdc-render-only=1] textarea,body[data-tdc-render-only=1] nav,body[data-tdc-render-only=1] [role=toolbar],body[data-tdc-render-only=1] .controls,body[data-tdc-render-only=1] .toolbar,body[data-tdc-render-only=1] .editor,body[data-tdc-render-only=1] .transport,body[data-tdc-render-only=1] .playback-controls{display:none!important}body[data-tdc-render-only=1] canvas,body[data-tdc-render-only=1] svg{max-width:100vw!important;max-height:100vh!important}";document.head.appendChild(s)}const old=window.renderAt;if(typeof old==="function"&&!old.__tdcWrapped){const w=function(seconds){const t=Math.max(0,Number(seconds)||0);window.__tdcSeedRandom((Math.floor(t*1000)^0x51f15e5d)>>>0);return old.call(this,seconds)};w.__tdcWrapped=true;window.renderAt=w}})();<\/script>';
  if (!source.includes("TDC deterministic compatibility layer")) {
    if (/<head([^>]*)>/i.test(source)) source = source.replace(/<head([^>]*)>/i, match => match + prelude);
    else source = source.replace(/<!doctype html>/i, match => match + prelude);
  }
  if (!source.includes("TDC export compatibility")) {
    if (/<\/body>/i.test(source)) source = source.replace(/<\/body>/i, renderShim + "</body>");
    else source += renderShim;
  }
  return source;
}
