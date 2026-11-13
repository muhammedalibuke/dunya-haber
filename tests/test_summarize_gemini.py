import json
from datetime import timedelta

from pipeline.summarize import GEMINI_MODEL, gemini_summary
from tests.test_run_e2e import CFG, EMB, GAZ, GB, JP, TR, pages_run1
from tests.fakes import NOW, FakeTranslator
from pipeline.run import run


class Resp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


def ok_body(tr, en):
    return {"candidates": [{"content": {"parts": [{"text": json.dumps({"tr": tr, "en": en})}]}}]}


def test_success_returns_both_strings():
    seen = {}

    def post(url, **kw):
        seen["url"], seen["kw"] = url, kw
        return Resp(200, ok_body("Özet.", "Summary."))

    assert gemini_summary(["Quake hits Kobe"], ["Strong quake."], "KEY", post=post) == ("Özet.", "Summary.")
    assert GEMINI_MODEL in seen["url"]
    assert seen["kw"]["headers"]["x-goog-api-key"] == "KEY"
    assert seen["kw"]["timeout"] == 20


def test_quota_returns_none():
    assert gemini_summary(["t"], ["d"], "KEY", post=lambda u, **k: Resp(429, {})) is None


def test_malformed_json_returns_none():
    bad = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    assert gemini_summary(["t"], ["d"], "KEY", post=lambda u, **k: Resp(200, bad)) is None
    assert gemini_summary(["t"], ["d"], "KEY", post=lambda u, **k: Resp(200, ValueError("x"))) is None


def test_timeout_returns_none():
    def post(u, **k):
        raise TimeoutError("slow")
    assert gemini_summary(["t"], ["d"], "KEY", post=post) is None


def test_run_never_calls_post_without_key(tmp_path):
    calls = []
    run(tmp_path / "s", tmp_path / "o", NOW, [GB, TR, JP], pages_run1().__getitem__, EMB, FakeTranslator(),
        GAZ, CFG, gemini_key=None, post=lambda *a, **k: calls.append(1))
    assert calls == []


def test_run_uses_ai_summary_for_today_events(tmp_path):
    run(tmp_path / "s", tmp_path / "o", NOW, [GB, TR, JP], pages_run1().__getitem__, EMB, FakeTranslator(),
        GAZ, CFG, gemini_key="KEY", post=lambda u, **k: Resp(200, ok_body("YZ özeti.", "AI summary.")))
    today = json.loads((tmp_path / "o" / "today.json").read_text())
    detail = json.loads((tmp_path / "o" / "events" / f"{today['events'][0]['id']}.json").read_text())
    assert detail["summary"] == {"tr": "YZ özeti.", "en": "AI summary.", "ai": True}
