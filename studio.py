#!/usr/bin/env python3
"""Studio CLI — the single entrypoint for generating a visual test shot.
Runs OUTSIDE Blender (plain Python) and shells out to Blender for the
parts that need bpy, per the project's "deterministic compiler, no manual
Blender editing" rule: this script never opens the Blender GUI or expects
a human to touch the .blend file. Re-running it with the same shot list
regenerates the same structural result.

Usage:
  python studio.py --visual-test [--full-quality]
  python studio.py --shots manifests/gate3_shots.json [--full-quality]
  python studio.py --contact-sheet
"""
import argparse
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
DEFAULT_SHOTS = "manifests/gate3_shots.json"


def run_generator(shot_list, full_quality=False):
    script = os.path.join(ROOT, "engine/render/build_from_shots.py")
    cmd = [BLENDER, "--background", "--python", script, "--", shot_list]
    if not full_quality:
        cmd.append("--preview")
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        sys.exit(result.returncode)


def run_shorts(dsl_path, out_mp4):
    """Vertical Short via the 2D compositor (engine/shorts). Runs in the project venv."""
    py = os.path.join(ROOT, ".venv/bin/python")
    code = (
        "import sys, json; sys.path.insert(0, '.');"
        "from engine.shorts import director, render, qc;"
        f"dsl = json.load(open({dsl_path!r})); show = director.compile_show(dsl);"
        f"res = render.render_video(show, {out_mp4!r});"
        f"rep = qc.run({out_mp4!r}, show, res['stats']);"
        f"json.dump(rep, open({out_mp4!r}.replace('.mp4', '_qc.json'), 'w'), indent=2);"
        "print('frames', res['frames'], 'render_s', round(res['seconds'], 1), 'QC passed:', rep['passed'])"
    )
    subprocess.run([py, "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT))


def run_make(topic=None, plan=None, duration=40, plan_only=False, stills=None, brief=None):
    """Topic (or a saved plan) -> Short. The system plans, voices, compiles and renders."""
    py = os.path.join(ROOT, ".venv/bin/python")
    code = (
        "import sys, json; sys.path.insert(0, '.');"
        "from engine.shorts import pipeline;"
        f"r = pipeline.run(topic={topic!r}, plan_path={plan!r}, brief_path={brief!r}, duration={duration}, plan_only={plan_only!r}, still_times={stills!r});"
        "print('OUT', r['out_dir'])"
    )
    subprocess.run([py, "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT))


def run_factory(story=None, narration=None, project_plan=None, name=None, plan_only=False, stills=None, window=None, allow_fallbacks=False, domain="money_psychology", qc_only=False):
    """Story-driven factory: story.md + narration segments JSON -> analysis -> plan -> film + project folder."""
    py = os.path.join(ROOT, ".venv/bin/python")
    code = (
        "import sys; sys.path.insert(0, '.');"
        "from engine.factory import pipeline;"
        f"pipeline.run(story={story!r}, narration={narration!r}, project_plan={project_plan!r}, name={name!r}, dom_id={domain!r}, plan_only={plan_only!r}, "
        f"stills={stills!r}, window={window!r}, allow_fallbacks={allow_fallbacks!r}, qc_only={qc_only!r})"
    )
    subprocess.run([py, "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))


def _is_skeleton_plan(path):
    try:
        import json
        return json.load(open(path)).get("kind") == "skeleton_short"
    except Exception:
        return False


def run_contact_sheet():
    subprocess.run([sys.executable, os.path.join(ROOT, "asset_pipeline/contact_sheet.py")], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--visual-test", action="store_true", help="Generate the default Gate 3 shot list at preview quality")
    parser.add_argument("--shots", default=None, help="Path to a shot-list JSON (defaults to manifests/gate3_shots.json)")
    parser.add_argument("--full-quality", action="store_true", help="Render at final resolution/samples instead of fast preview")
    parser.add_argument("--shorts", metavar="DSL", help="Render a vertical Short from a v2 shot list (2D compositor)")
    parser.add_argument("--out", default="output/shorts/rahul_short.mp4")
    parser.add_argument("--make", metavar="TOPIC", help="Generate a complete Short from a topic (planner -> voice -> render -> QC)")
    parser.add_argument("--brief", metavar="BRIEF", help="Story brief file (briefs/*.md): premise + beat ladder; the system writes and stages the story")
    parser.add_argument("--from-plan", metavar="PLAN_JSON", help="Re-render a saved plan.json (no LLM calls)")
    parser.add_argument("--plan-only", action="store_true", help="With --make: stop after writing plan.json")
    parser.add_argument("--duration", type=int, default=40, help="Target seconds for --make")
    parser.add_argument("--stills", metavar="T,T,..", help="With --make/--from-plan: render only stills at these times")
    parser.add_argument("--story", metavar="STORY_MD", help="FACTORY: story.md (source of truth)")
    parser.add_argument("--narration", metavar="SEGMENTS_JSON", help="FACTORY: narration segments JSON (audio = same name without .segments.json)")
    parser.add_argument("--project-plan", metavar="SHOT_PLAN_JSON", help="FACTORY: deterministic re-render of a saved project/shot_plan.json (no LLM)")
    parser.add_argument("--name", help="FACTORY: project folder name")
    parser.add_argument("--domain", default="money_psychology", help="FACTORY: domain pack (domains/<id>)")
    parser.add_argument("--window", metavar="T0,T1", help="FACTORY: render only this time window (standalone Short candidate)")
    parser.add_argument("--qc-only", action="store_true", help="FACTORY: re-run QC/reports on an existing render")
    parser.add_argument("--allow-fallbacks", action="store_true", help="FACTORY: continue even if required assets are missing")
    parser.add_argument("--api-request", metavar="REQUEST_JSON", help='FACTORY API: {"story","narration_segments","style","aspect_ratio"} -> film (what a UI would call)')
    parser.add_argument("--production", metavar="STORY_MD", help="PRODUCTION: story.md + --narration-json SEGMENTS_JSON -> finished cinematic Short (parse -> plan -> render -> audio -> QC + auto-fix)")
    parser.add_argument("--narration-json", metavar="SEGMENTS_JSON", help="With --production: narration segments JSON (id,text,start,end[,words] + audio path)")
    parser.add_argument("--production-acceptance", action="store_true", help="ONE command: 3 different stories end to end + determinism + caching + failure modes + 24-situation matrix + original-film regression + unit tests")
    parser.add_argument("--ui", action="store_true", help="STUDIO UI: start Kathaaya Studio (web UI + production API) at http://127.0.0.1:8765 - create movies from one screen")
    parser.add_argument("--port", type=int, default=8765, help="With --ui: port of the studio server")
    parser.add_argument("--skeleton-short", action="store_true", help="SKELETON PROOF: build + render the full-body 2D skeleton short (narration -> plan -> Blender rig -> film)")
    parser.add_argument("--skeleton-short-v2", action="store_true", help="FACTORY V2: render the 'एक गलत कॉल' Short (CharacterDNA v2, 3/4 views, hand poses, gaze targets, hand-over, lighting)")
    parser.add_argument("--skeleton-short-v3", action="store_true", help="CHARACTER ART + ACTING LOCK: the V3 Short (hand library, prop grips, acted entrance, sequences)")
    parser.add_argument("--skeleton-topic", metavar="TOPIC", help="TOPIC -> FILM: the system writes the story, voices it, directs it, CRITIQUES the preview stills and fixes the flaws, then renders the Short")
    parser.add_argument("--story-json", metavar="STORY_JSON", help="With --skeleton-topic: reuse a saved story.json (deterministic re-run: no LLM)")
    parser.add_argument("--critique-rounds", type=int, default=3, help="With --skeleton-topic: max critique->fix->re-render rounds")
    parser.add_argument("--no-llm", action="store_true", help="With --skeleton-topic: deterministic domain packs only")
    parser.add_argument("--draft", action="store_true", help="With --skeleton-topic: estimated narration timing (no TTS) - fast preview")
    parser.add_argument("--out-dir", default=None, help="With --skeleton-short-v2: output folder (default output/shorts/skeleton_factory_v2)")
    parser.add_argument("--tts", default="chatterbox", choices=["chatterbox", "vibevoice"], help="With --skeleton-short: narration engine used to (re)generate the voice")
    parser.add_argument("--tempo", type=float, default=1.16, help="With --skeleton-short: pacing speed-up (1.0 = natural)")
    parser.add_argument("--contact-sheet", action="store_true", help="Regenerate the asset contact sheet from the registry")
    args = parser.parse_args()

    if args.from_plan and _is_skeleton_plan(args.from_plan):
        code = ("import sys, json; sys.path.insert(0, '.'); from engine.skeleton import build;"
                f"build.from_plan({args.from_plan!r})")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))
        return
    if args.ui:
        sys.exit(subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-u", "-m", "engine.studio.server", "--port", str(args.port)], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1")).returncode)
    if args.production_acceptance:
        sys.exit(subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-u", "-m", "engine.skeleton.acceptance"], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1")).returncode)
    if args.production:
        if not args.narration_json:
            parser.error("--production needs --narration-json")
        code = ("import sys; sys.path.insert(0, '.'); from engine.skeleton import production as P, story_semantics as SS, narration_io as NI;"
                "\ntry:\n"
                f"    r = P.make({args.production!r}, {args.narration_json!r}, out_dir={args.out_dir!r}, critique_rounds={args.critique_rounds}); print('FILM', r['mp4'], 'QC passed:', r['qc']['passed'])\n"
                "except (SS.StoryNotSupported, NI.NarrationInvalid) as e:\n    print('REJECTED:', e); sys.exit(2)")
        sys.exit(subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1")).returncode)
    if args.skeleton_topic:
        code = ("import sys, json; sys.path.insert(0, '.'); from engine.skeleton import topic_build as TB;"
                f"st = json.load(open({args.story_json!r})) if {args.story_json!r} else None;"
                f"TB.make({args.skeleton_topic!r}, out_dir={args.out_dir!r}, use_llm={not args.no_llm}, rounds={args.critique_rounds}, draft={args.draft}, story=st)")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))
        return
    if args.skeleton_short_v3 or args.skeleton_short_v2:
        code = ("import sys; sys.path.insert(0, '.'); from engine.skeleton import build_v2;"
                f"build_v2.make(out_dir={args.out_dir!r}, tempo={args.tempo if args.tempo != 1.16 else 1.08}, director={'v3' if args.skeleton_short_v3 else 'v2'!r})")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))
        return
    if args.skeleton_short:
        code = ("import sys; sys.path.insert(0, '.'); from engine.skeleton import build;"
                f"build.make(tts={args.tts!r}, tempo={args.tempo})")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))
        return
    if args.api_request:
        code = ("import sys, json; sys.path.insert(0, '.'); from engine import api;"
                f"r = api.generate(json.load(open({args.api_request!r}))); print(json.dumps(r, ensure_ascii=False, indent=2))")
        subprocess.run([os.path.join(ROOT, ".venv/bin/python"), "-c", code], cwd=ROOT, check=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONUNBUFFERED="1"))
        return
    if args.story or args.project_plan:
        stills = [float(x) for x in args.stills.split(",")] if args.stills else None
        window = tuple(float(x) for x in args.window.split(",")) if args.window else None
        run_factory(story=args.story, narration=args.narration, project_plan=args.project_plan, name=args.name, plan_only=args.plan_only,
                    stills=stills, window=window, allow_fallbacks=args.allow_fallbacks, domain=args.domain, qc_only=args.qc_only)
        return
    if args.make or args.from_plan or args.brief:
        stills = [float(x) for x in args.stills.split(",")] if args.stills else None
        run_make(topic=args.make, plan=args.from_plan, duration=args.duration, plan_only=args.plan_only, stills=stills, brief=args.brief)
        return
    if args.shorts:
        run_shorts(args.shorts, args.out)
        return
    if args.contact_sheet:
        run_contact_sheet()
        return

    shot_list = args.shots or DEFAULT_SHOTS
    if not (args.visual_test or args.shots):
        parser.print_help()
        return
    run_generator(shot_list, full_quality=args.full_quality)


if __name__ == "__main__":
    main()
