"""Compare the two generated Shorts (A: investment group, night bedroom; B: lottery fee, day study) on the nine axes the milestone names, from their plan.json files. -> docs/asset_audit/two_shorts.json / .md
    PYTHONPATH=. .venv/bin/python tools/asset_audit/two_shorts_report.py
"""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from engine.skeleton import lab_dna as LD   # noqa: E402

FILMS = {"A": "output/shorts/topic/fake_whatsapp_investment_group", "B": "output/shorts/topic/lottery_prize_processing_fee_scam"}


def summarise(d):
    p = json.load(open(os.path.join(ROOT, d, "plan.json")))
    st = json.load(open(os.path.join(ROOT, d, "story.json")))
    q = json.load(open(os.path.join(ROOT, d, "qc_report.json")))
    sh = [s for s in p["shots"] if s["treatment"] == "skeleton" and s.get("camera")]
    lights = [s["lighting"] for s in p["shots"]]
    cast = {cid: dict(name=c["name"], role=c["role"], dna=c["dna"]["id"], hair=c["dna"]["hair"]["style"], top=c["dna"]["wardrobe"]["top"], gender=c["dna"]["gender_presentation"], age=c["dna"]["age"],
                      glasses=c["dna"].get("glasses")) for cid, c in p["characters"].items()}
    return dict(
        story=st["title"], domain=st["domain"], style=st.get("style") or "night_bedroom", beats=len(st["beats"]), duration_s=p["duration"], arc=[b["act"] for b in st["beats"]],
        character_selection=cast,
        environment=p["environment"]["family"], blocking=dict(A_origin=p["characters"]["A"]["origin"][0], D_origin=p["characters"]["D"]["origin"][0], A_stop=p["targets"].get("A_STOP"), D_stop=p["targets"].get("D_STOP"),
                                                             handover=p["targets"].get("HANDOVER"), A_start=p["characters"]["A"].get("start")),
        camera=dict(sizes=dict(collections.Counter(s["camera"]["size"] for s in sh)), moves=dict(collections.Counter(s["camera"]["move"] for s in sh)), critic_fixed_shots=sum(1 for s in sh if s.get("fixes", {}).get("camera"))),
        props=dict(phone_location=p["targets"]["PHONE"], furniture={"night_bedroom": "bed + nightstand", "day_study": "chair + table + lamp"}.get(st.get("style") or "night_bedroom")),
        psychology=dict(replacement_faces=sorted({a["name"] for s in p["shots"] for a in s.get("actions", []) if a["action"] == "face_atom"}), acting=sorted({a["action"] for s in p["shots"] for a in s.get("actions", [])})),
        motifs=sorted({g["effect"] for s in p["shots"] for g in s.get("gp", [])}),
        lighting=dict(moods=sorted({l.get("mood") for l in lights}), moon=any(l.get("moon", 0) > 0 for l in lights), sun=any(l.get("sun", 0) > 0 for l in lights), lamp_on_at=p.get("lamp_on")),
        composition=dict(shots=len(p["shots"]), mean_shot_s=round(p["duration"] / len(p["shots"]), 2), insert_at_beat=next((i + 1 for i, s in enumerate(p["shots"]) if s["treatment"] == "insert_ui"), None)),
        qc=dict(passed=q["passed"], n=q["n_checks"], not_applicable=q["evidence"].get("not_applicable_gates")),
        shared_library=dict(rig="26 bones + 4 IK", hand_poses=20, open_peeps_heads_used=sorted({c["hair"] for c in cast.values()})))


def main():
    out = {k: summarise(v) for k, v in FILMS.items()}
    json.dump(out, open(os.path.join(ROOT, "docs/asset_audit/two_shorts.json"), "w"), ensure_ascii=False, indent=1)
    rows = [("story / domain", lambda s: f"{s['story']} / {s['domain']}"), ("art direction (style)", lambda s: s["style"]), ("arc", lambda s: f"{s['beats']} beats: " + " ".join(a[:6] for a in s["arc"])),
            ("character selection", lambda s: "; ".join(f"{c['role']}: {c['gender']} {c['age']}, {c['hair']}, {c['top']}" for c in s["character_selection"].values())),
            ("environment", lambda s: s["environment"]), ("blocking", lambda s: json.dumps(s["blocking"])), ("camera sizes / moves", lambda s: json.dumps(s["camera"]["sizes"]) + " / " + json.dumps(s["camera"]["moves"])),
            ("props / furniture", lambda s: f"phone at {s['props']['phone_location']}, {s['props']['furniture']}"), ("psychology (replacement faces)", lambda s: ", ".join(s["psychology"]["replacement_faces"]) or "procedural only"),
            ("GP motifs", lambda s: ", ".join(s["motifs"])), ("lighting", lambda s: f"moods {s['lighting']['moods']}, moon {s['lighting']['moon']}, sun {s['lighting']['sun']}"),
            ("composition", lambda s: f"{s['composition']['shots']} shots, mean {s['composition']['mean_shot_s']} s, insert at beat {s['composition']['insert_at_beat']}"), ("duration", lambda s: f"{s['duration_s']} s"),
            ("QC", lambda s: f"{s['qc']['passed']} ({s['qc']['n']} gates; n/a: {s['qc']['not_applicable']})")]
    L = ["| axis | Short A | Short B |", "|---|---|---|"] + [f"| {n} | {f(out['A'])} | {f(out['B'])} |" for n, f in rows]
    open(os.path.join(ROOT, "docs/asset_audit/two_shorts.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
