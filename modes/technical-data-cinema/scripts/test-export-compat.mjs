import assert from "node:assert/strict";
import { assertSceneCandidate, validateSceneSource } from "./scene-contract.mjs";
const good=`<!doctype html><html><head><style>html,body{margin:0;width:100%;height:100%;overflow:hidden}#stage{width:100vw;height:100vh;background:#101510;color:#eadfc0;display:grid;place-items:center}</style></head><body><main id="stage">frame</main><script>const DURATION=4;window.getDuration=function(){return DURATION};window.renderAt=function(t){document.querySelector("#stage").style.transform="scale("+String(1+Math.sin(t)*.03)+")"};if(new URLSearchParams(window.location.search).get("render")!=="1")document.body.insertAdjacentHTML("afterbegin",'<button>Preview</button>');</script></body></html>`;
assert.deepEqual(validateSceneSource(good),[]);
assert.ok(validateSceneSource(good.replace("window.renderAt=function","Math.random();window.renderAt=function")).some(e=>e.includes("Math.random")));
assert.ok(validateSceneSource(good.replace('new URLSearchParams(window.location.search).get("render")!=="1"',"false")).some(e=>e.includes("render-only")));
const result=await assertSceneCandidate(good);assert.equal(result.renderOnly,true);assert.equal(result.deterministic,true);
console.log("Strict scene source validation and browser render-only smoke test passed.");