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


def test_script_audio_rejects_mostly_latin_english():
    client = TestClient(create_app(test_mode=True))
    r = client.post("/api/audio", json={"text": "This is an English script."})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "script_not_supported"


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
