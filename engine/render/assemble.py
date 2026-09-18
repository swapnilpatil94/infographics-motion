"""Assembles a rendered frame sequence + synthesized sound cues into an mp4.

Sound cues are synthesized tones (no licensed assets, so nothing for
assets/licenses.json to gate) — a real production pass would replace these
with licensed/recorded SFX per the asset-ingestion pipeline (Gate 3).
Run: python3 engine/render/assemble.py <frames_dir> <fps> <duration_s> <shot_plan.json> <out.mp4>
"""
import sys, os, json, subprocess, tempfile


def build_notification_ding(out_path):
    # two quick sine blips, short and bright — a placeholder "ding".
    filter_complex = (
        "sine=frequency=1318:duration=0.09[a];"
        "sine=frequency=1760:duration=0.12[b];"
        "[a][b]concat=n=2:v=0:a=1[out]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc",
        "-filter_complex", filter_complex, "-map", "[out]",
        "-t", "0.25", out_path,
    ], check=True, capture_output=True)


def main():
    frames_dir, fps, duration_s, shot_plan_path, out_path = sys.argv[1:6]
    fps = int(fps)
    duration_s = float(duration_s)

    with open(shot_plan_path) as f:
        shot_plan = json.load(f)
    cues = []
    for shot in shot_plan["shots"]:
        for cue in shot.get("sound_cues", []):
            cues.append(cue["at_s"])

    with tempfile.TemporaryDirectory() as tmp:
        video_only = os.path.join(tmp, "video_only.mp4")
        subprocess.run([
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", os.path.join(frames_dir, "frame_%04d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
            video_only,
        ], check=True, capture_output=True)

        base_audio = os.path.join(tmp, "base.wav")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_s), base_audio,
        ], check=True, capture_output=True)

        audio_track = base_audio
        if cues:
            ding = os.path.join(tmp, "ding.wav")
            build_notification_ding(ding)
            inputs = ["-i", base_audio]
            filter_parts = []
            mix_labels = ["[0:a]"]
            for i, at_s in enumerate(cues):
                inputs += ["-i", ding]
                delay_ms = int(at_s * 1000)
                filter_parts.append(f"[{i+1}:a]adelay={delay_ms}|{delay_ms}[d{i}]")
                mix_labels.append(f"[d{i}]")
            filter_complex = ";".join(filter_parts) + ";" + "".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=first[aout]"
            mixed = os.path.join(tmp, "mixed.wav")
            subprocess.run(
                ["ffmpeg", "-y"] + inputs + ["-filter_complex", filter_complex, "-map", "[aout]", mixed],
                check=True, capture_output=True,
            )
            audio_track = mixed

        subprocess.run([
            "ffmpeg", "-y", "-i", video_only, "-i", audio_track,
            "-c:v", "copy", "-c:a", "aac", "-shortest", out_path,
        ], check=True, capture_output=True)

    print("ASSEMBLED", out_path)


if __name__ == "__main__":
    main()
