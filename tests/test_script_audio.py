"""Tests for standalone script-to-production-Chatterbox audio export."""
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from engine.studio.server import create_app


def test_script_audio_rejects_empty_script():
    client = TestClient(create_app(test_mode=True))
    r = client.post("/api/audio", json={"text": "  "})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "empty_script"


def test_script_audio_accepts_hinglish_and_english_terms(tmp_path):
    import engine.studio.server as server
    fake = {
        "samples": np.zeros(22050, dtype=np.float32),
        "voice": "chatterbox-hi + whisperx alignment",
        "duration": 1.0,
        "beats": [{"id": "n001", "text": "Detector ये निशान देखेगा।", "start": 0.0, "end": 0.9,
                   "words": [{"word": "Detector", "start": 0.0, "end": 0.4},
                             {"word": "ये", "start": 0.4, "end": 0.6},
                             {"word": "निशान", "start": 0.6, "end": 0.9}]}],
        "placeholder": False,
    }
    with patch.object(server.production_voice, "synthesize", return_value=fake), patch.object(server, "ROOT", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        r = client.post("/api/audio", json={"text": "Detector ये निशान देखेगा।"})
        assert r.status_code == 200, r.text


def test_script_audio_calls_production_voice_and_writes_downloads(tmp_path):
    import engine.studio.server as server
    fake = {
        "samples": np.zeros(22050, dtype=np.float32),
        "voice": "chatterbox-hi (voice-cloned reference) + whisperx alignment",
        "duration": 1.0,
        "beats": [{"id": "n001", "text": "यह एक परीक्षण है।", "start": 0.0, "end": 0.9,
                   "words": [{"word": "यह", "start": 0.0, "end": 0.2}, {"word": "परीक्षण", "start": 0.2, "end": 0.9}]}],
        "placeholder": False,
    }
    with patch.object(server.production_voice, "synthesize", return_value=fake) as synth, patch.object(server, "ROOT", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        r = client.post("/api/audio", json={"text": "यह एक परीक्षण है।"})
        assert r.status_code == 200, r.text
        result = r.json()
        assert result["segments"] == 1
        synth.assert_called_once()
        wav = client.get(f"/api/audio/{result['id']}/download")
        assert wav.status_code == 200 and wav.headers["content-type"] == "audio/wav"
        data = client.get(f"/api/audio/{result['id']}/segments")
        assert data.status_code == 200
        assert data.json()["segments"][0]["text"] == "यह एक परीक्षण है।"


def test_script_audio_refuses_placeholder_fallback(tmp_path):
    import engine.studio.server as server
    fake = {"samples": np.zeros(22050, dtype=np.float32), "voice": "macOS say (Lekha) PLACEHOLDER",
            "duration": 1.0, "beats": [], "placeholder": True}
    with patch.object(server.production_voice, "synthesize", return_value=fake), patch.object(server, "ROOT", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        r = client.post("/api/audio", json={"text": "यह एक परीक्षण है।"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "chatterbox_unavailable"


def test_script_audio_rejects_unsupported_symbols():
    client = TestClient(create_app(test_mode=True))
    r = client.post("/api/audio", json={"text": "हैलो 🚀 दुनिया"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "script_not_supported"


def test_hindi_pronunciation_hints_preserve_original_script():
    from engine.shorts.voice import _tts_text
    original = "AI से लिखा? OpenAI का Watermark।"
    spoken = _tts_text(original, "hindi_mixed")
    assert spoken == "एआई से लिखा? ओपनएआई का वॉटरमार्क।"
    assert _tts_text(original, "original") == original



def test_voice_reference_list_is_available_without_profiles(tmp_path):
    import engine.studio.server as server
    with patch.object(server, "VOICE_REFERENCE_DIR", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        r = client.get("/api/voice-references")
        assert r.status_code == 200
        assert r.json()["profiles"] == []


def test_voice_reference_can_be_activated_locally(tmp_path):
    import json
    import os
    import engine.studio.server as server
    ref_id = "abcdef123456"
    folder = tmp_path / ref_id
    folder.mkdir()
    (folder / "cleaned.wav").write_bytes(b"placeholder wav")
    (folder / "profile.json").write_text(json.dumps({"id": ref_id, "name": "Test voice"}), encoding="utf-8")
    with patch.object(server, "VOICE_REFERENCE_DIR", str(tmp_path)), patch.object(server, "ROOT", str(tmp_path / "root")):
        client = TestClient(create_app(test_mode=True))
        r = client.post(f"/api/voice-references/{ref_id}/activate")
        assert r.status_code == 200, r.text
        active = json.loads((tmp_path / "root/output/voice/active_reference.json").read_text(encoding="utf-8"))
        assert active["id"] == ref_id
        assert active["name"] == "Test voice"


def test_voice_reference_activation_rejects_unknown_profile(tmp_path):
    import engine.studio.server as server
    with patch.object(server, "VOICE_REFERENCE_DIR", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        r = client.post("/api/voice-references/000000000000/activate")
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "voice_reference_not_found"



def test_script_audio_expanded_delivery_cues_are_stripped_and_mapped(tmp_path):
    import engine.studio.server as server
    fake = {
        "samples": np.zeros(22050, dtype=np.float32),
        "voice": "chatterbox-hi + whisperx alignment",
        "duration": 1.0,
        "beats": [{"id": "n001", "text": "यह शुरुआत है।", "start": 0.0, "end": 0.9, "words": []}],
        "placeholder": False,
    }
    script = "[HOOK]\nयह शुरुआत है।\n[EMPHASIS]\nयही सबसे बड़ा कारण है।\n[REFLECTIVE]\nअब सोचिए।\n[DEFAULT]\nआगे बढ़ते हैं।"
    with patch.object(server.production_voice, "synthesize", return_value=fake) as synth, patch.object(server, "ROOT", str(tmp_path)):
        client = TestClient(create_app(test_mode=True))
        response = client.post("/api/audio", json={"text": script, "performance_mode": "directed"})
        assert response.status_code == 200, response.text
        beats = synth.call_args.args[0]
        assert [b["performance"] for b in beats] == ["hook", "hook", "emphasis", "emphasis", "reflective", "reflective", "default", "default"]
        assert all("[" not in b["text"] and "]" not in b["text"] for b in beats)
        assert synth.call_args.kwargs["performance_mode"] is True
