"""Routing between the Urdu XLM-R, Roman Urdu XLM-R and long-article TF-IDF models.

The XLM-R models are replaced by small stand-ins so these tests run without
torch or the ~1 GB model folders; the TF-IDF model is a tiny real pipeline.
"""
import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

from app.ai.text import xlmr
from app.ai.text.explain import explain_text
from app.ai.text.predict import LONG_TEXT_WORDS, predict_text

SHORT_URDU = "حکومت نے نئی پالیسی کا اعلان کیا"
LONG_URDU = " ".join(["حکومت نے نئی پالیسی کا اعلان کیا"] * (LONG_TEXT_WORDS // 6 + 2))
ROMAN = "viral jhoot khabar hai"


class FakeXlmr:
    """Stand-in: probability of Fake rises with the number of 'jhoot'/'جھوٹ' words."""

    def __init__(self, version):
        self.model_version = version
        self.calls = 0

    def fake_probabilities(self, texts, batch_size=16):
        self.calls += 1
        return [min(0.95, 0.2 + 0.6 * (t.count("jhoot") + t.count("جھوٹ"))) for t in texts]


@pytest.fixture
def models(tmp_path, monkeypatch):
    urdu, roman = FakeXlmr("xlmr-urdu"), FakeXlmr("xlmr-roman-urdu")
    monkeypatch.setattr(xlmr, "is_configured", lambda script: True)
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: ({"urdu": urdu, "roman": roman}[script], None))

    # Long-article model saved as a bare pipeline, the way the notebook saves it.
    texts = ["حکومت اعلان پالیسی رپورٹ"] * 10 + ["جھوٹی افواہ وائرل سازش"] * 10
    pipeline = make_pipeline(
        make_union(TfidfVectorizer(analyzer="word"), TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4))),
        LogisticRegression(max_iter=1000),
    ).fit(texts, [0] * 10 + [1] * 10)
    path = tmp_path / "long.joblib"
    joblib.dump(pipeline, path)
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(path))
    return urdu, roman


def test_short_urdu_uses_urdu_xlmr(models):
    result = predict_text(SHORT_URDU, language="urdu")
    assert result["model_version"] == "xlmr-urdu"
    assert result["prediction"] == "Real" and result["fake_probability"] == pytest.approx(0.2)
    assert result["confidence"] == pytest.approx(0.8)


def test_long_urdu_uses_tfidf(models):
    result = predict_text(LONG_URDU, language="urdu")
    assert result["model_version"] == "text-tfidf-logreg"
    assert result["is_stub"] is False


def test_roman_urdu_uses_roman_xlmr(models):
    result = predict_text(ROMAN, language="roman_urdu")
    assert result["model_version"] == "xlmr-roman-urdu"
    assert result["prediction"] == "Fake"


def test_xlmr_explanation_by_occlusion(models):
    explanation = explain_text(ROMAN)
    assert explanation["is_stub"] is False
    top = explanation["highlighted_words"][0]
    assert top["word"] == "jhoot" and top["direction"] == "supports_prediction"


def test_long_urdu_explanation_uses_tfidf_weights(models):
    explanation = explain_text(LONG_URDU)
    assert explanation["is_stub"] is False
    assert explanation["highlighted_words"]


def test_falls_back_to_tfidf_when_xlmr_cannot_load(models, monkeypatch):
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (None, "broken"))
    assert predict_text(SHORT_URDU, language="urdu")["model_version"] == "text-tfidf-logreg"


def test_no_models_gives_uncertain(monkeypatch, tmp_path):
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(tmp_path / "missing.joblib"))
    result = predict_text(ROMAN, language="roman_urdu")
    assert result["prediction"] == "Uncertain" and result["is_stub"] is True
