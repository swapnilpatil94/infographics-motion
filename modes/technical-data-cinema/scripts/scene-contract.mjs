import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
export function validateSceneSource(source) {
  const html=String(source||""), errors=[];
  if(!/^\s*<!doctype html>/i.test(html)) errors.push("output is not a complete HTML document");
  if(/\bMath\s*\.\s*random\s*\(/.test(html)) errors.push("uses Math.random(), forbidden for deterministic rendering");
  if(!/window\.renderAt\s*=/.test(html)) errors.push("missing window.renderAt(seconds)");
  if(!/window\.getDuration\s*=/.test(html)) errors.push("missing window.getDuration()");
  if(!/new\s+URLSearchParams\s*\(\s*(?:window\.)?location\.search\s*\)/.test(html)||!/\.get\s*\(\s*["']render["']\s*\)/.test(html)) errors.push("missing native ?render=1 render-only mode");
  // Catch model-generated placeholder renderers before spending another long repair call.
  const commentOnlyFunction = /function\s+((?:draw|render|build|animate|paint|update)[A-Za-z0-9_$]*)\s*\([^)]*\)\s*\{\s*(?:(?:\/\/[^\n]*|\/\*[\s\S]*?\*\/)\s*)*\}/g;
  for (const match of html.matchAll(commentOnlyFunction)) errors.push(`renderer function ${match[1]} is empty/comment-only; implement its actual drawing and timestamp-driven state changes`);
  const commentOnlyArrow = /(?:const|let)\s+((?:draw|render|build|animate|paint|update)[A-Za-z0-9_$]*)\s*=\s*(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>\s*\{\s*(?:(?:\/\/[^\n]*|\/\*[\s\S]*?\*\/)\s*)*\}/g;
  for (const match of html.matchAll(commentOnlyArrow)) errors.push(`renderer function ${match[1]} is empty/comment-only; implement its actual drawing and timestamp-driven state changes`);
  return errors;
}
export async function assertSceneCandidate(source) {
  const staticErrors=validateSceneSource(source); if(staticErrors.length) throw new Error(staticErrors.join("; "));
  const dir=await fs.mkdtemp(path.join(os.tmpdir(),"tdc-scene-contract-")), file=path.join(dir,"candidate.html");
  const browser=await chromium.launch({headless:true,args:["--enable-webgl","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"]});
  try {
    await fs.writeFile(file,source,"utf8");
    const page=await browser.newPage({viewport:{width:540,height:960},deviceScaleFactor:1,reducedMotion:"reduce"});
    const errors=[], external=[];
    page.on("pageerror",e=>errors.push(e.message));
    page.on("console",m=>{if(m.type()==="error")errors.push(m.text())});
    page.on("request",r=>{if(/^https?:/i.test(r.url()))external.push(r.url())});
    const url=pathToFileURL(file);url.searchParams.set("render","1");
    await page.goto(url.href,{waitUntil:"load",timeout:15000});
    const c=await page.evaluate(()=>({renderAt:typeof window.renderAt,getDuration:typeof window.getDuration,duration:typeof window.getDuration==="function"?Number(window.getDuration()):NaN,visibleControls:[...document.querySelectorAll("button,input,select,textarea,nav,[role=toolbar],.controls,.toolbar,.editor,.transport,.playback-controls")].filter(el=>{const r=el.getBoundingClientRect(),s=getComputedStyle(el);return s.display!=="none"&&s.visibility!=="hidden"&&Number(s.opacity)>0&&r.width>0&&r.height>0}).map(el=>el.tagName.toLowerCase()).slice(0,8)}));
    if(c.renderAt!=="function")errors.push("renderAt is not callable in render-only mode");
    if(c.getDuration!=="function"||!Number.isFinite(c.duration)||c.duration<=0||c.duration>600)errors.push("getDuration() must return a finite duration in (0, 600]");
    if(c.visibleControls.length)errors.push("render-only mode leaves controls visible: "+c.visibleControls.join(", "));
    if(external.length)errors.push("external network requests are forbidden: "+[...new Set(external)].slice(0,4).join(", "));
    if(!errors.length){const t=Math.min(Math.max(.25,c.duration*.37),c.duration-.001);await page.evaluate(t=>window.renderAt(t),t);const h=()=>crypto.createHash("sha256");const first=h().update(await page.screenshot({type:"png",animations:"disabled"})).digest("hex");await page.evaluate(t=>window.renderAt(t*.2),t);await page.evaluate(t=>window.renderAt(t),t);const second=h().update(await page.screenshot({type:"png",animations:"disabled"})).digest("hex");if(first!==second)errors.push("seeking away and back did not reproduce identical pixels");}
    if(errors.length)throw new Error(errors.join("; "));return {duration:c.duration,renderOnly:true,deterministic:true};
  }catch(e){throw new Error("browser render-only validation failed: "+e.message)}
  finally{await browser.close();await fs.rm(dir,{recursive:true,force:true})}
}