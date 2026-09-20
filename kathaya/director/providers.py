"""Creative-director PROVIDERS. All return the director's raw JSON object; validation is the same for every provider.
    OllamaProvider    a local LLM with schema-constrained output (default qwen3:14b), temperature 0, fixed seed, replies cached by prompt hash (a plan is then reproducible)
    PasteProvider     the user copies the prompt into ChatGPT and pastes the reply back (no API key needed)
    FileProvider      a saved plan JSON"""
import hashlib
import json
import os
import re
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE = os.path.join(ROOT, "output/kathaya/llm_cache")


class DirectorUnavailable(Exception):
    pass


def extract_json(text):
    """a chat reply: strip ``` fences / lead-in text and parse the first JSON object"""
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    t = m.group(1) if m else text
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j < i:
        raise ValueError("no JSON object in the reply")
    return json.loads(t[i:j + 1])


class OllamaProvider:
    name = "ollama"
    sequential = True                                                                          # written one visual at a time with the renderer's legal-action menu (see director/sequential.py)

    def __init__(self, model="qwen3:14b", host="http://localhost:11434", timeout=1500):
        self.model, self.host, self.timeout = model, host, timeout

    def available(self):
        try:
            tags = json.load(urllib.request.urlopen(self.host + "/api/tags", timeout=3))
            return self.model in [m["name"] for m in tags.get("models", [])]
        except Exception:                                                                      # noqa: BLE001
            return False

    def __call__(self, prompt, schema):
        key = hashlib.sha1((self.model + json.dumps(schema, sort_keys=True) + prompt).encode()).hexdigest()[:20]
        p = os.path.join(CACHE, key + ".json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
        if not self.available():
            raise DirectorUnavailable(f"the local LLM '{self.model}' is not available (is ollama running?)")
        body = {"model": self.model, "stream": False, "think": False, "format": schema, "options": {"temperature": 0, "seed": 7, "num_ctx": 20000, "num_predict": 9000}, "messages": [{"role": "user", "content": prompt}]}
        req = urllib.request.Request(self.host + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
        raw = json.load(urllib.request.urlopen(req, timeout=self.timeout))["message"]["content"]
        out = extract_json(raw)
        os.makedirs(CACHE, exist_ok=True)
        json.dump(out, open(p, "w", encoding="utf-8"), ensure_ascii=False)
        return out


class PasteProvider:
    """the reply comes from the user (ChatGPT); `reply` is set by the caller"""
    name = "chatgpt_paste"

    def __init__(self, reply=None):
        self.reply = reply

    def __call__(self, prompt, schema):
        if not self.reply:
            raise DirectorUnavailable("paste ChatGPT's reply first")
        r, self.reply = self.reply, None
        return extract_json(r) if isinstance(r, str) else r


class FileProvider:
    name = "file"

    def __init__(self, path):
        self.path = path

    def __call__(self, prompt, schema):
        return json.load(open(self.path, encoding="utf-8"))
