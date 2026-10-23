"""Routing between the Urdu XLM-R, Roman Urdu XLM-R and long-article TF-IDF models.

The XLM-R models are replaced by small stand-ins so these tests run without torch or the
~1 GB model folders; the TF-IDF model is a tiny real pipeline saved the way the notebook
saves it (a bare scikit-learn pipeline, classes 0 = real, 1 = fake).
"""
import joblib
import pytest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline, make_union

from app.ai.text import long_articles, xlmr
from app.ai.text.preprocess import clean_urdu_notebook
from app.ai.text.explain import explain_text
from app.ai.text.predict import LONG_TEXT_WORDS, predict_text

SHORT_URDU = "حکومت نے نئی پالیسی کا اعلان کیا"
LONG_URDU = " ".join(["حکومت نے نئی پالیسی کا اعلان کیا"] * (LONG_TEXT_WORDS // 6 + 2))
LONG_FAKE_URDU = " ".join(["جھوٹی افواہ وائرل سازش"] * (LONG_TEXT_WORDS // 4 + 2))
ROMAN = "viral jhoot khabar hai"


class FakeXlmr:
    """Stand-in: probability of Fake rises with the number of 'jhoot'/'جھوٹ' words."""

    def __init__(self, version, max_len):
        self.model_version, self.max_len, self.calls = version, max_len, 0

    def _p_fake(self, text):
        return min(0.95, 0.2 + 0.6 * (text.count("jhoot") + text.count("جھوٹ")))

    def predict(self, text):
        self.calls += 1
        tokens = len(text.split()) + 2
        p = self._p_fake(text)
        return {"prediction": "Fake" if p >= 0.5 else "Real", "confidence": round(max(p, 1 - p), 4),
                "fake_probability": round(p, 4), "model_version": self.model_version, "is_stub": False,
                "status": "completed", "input_truncated": tokens > self.max_len,
                "input_token_count": tokens, "max_input_tokens": self.max_len}

    def explain(self, text, top_k=8, max_words=8, base_fake_probability=None):
        return [{"word": "jhoot", "contribution": 0.6, "direction": "supports_prediction"}] if "jhoot" in text else []


@pytest.fixture
def models(tmp_path, monkeypatch):
    urdu, roman = FakeXlmr("xlmr-urdu", 64), FakeXlmr("xlmr-roman-urdu", 512)
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: ({"urdu": urdu, "roman": roman}[script], None))

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
    result = predict_text(SHORT_URDU)
    assert result["model_version"] == "xlmr-urdu"
    assert result["prediction"] == "Real" and result["fake_probability"] == pytest.approx(0.2)
    assert result["confidence"] == pytest.approx(0.8)


def test_long_urdu_uses_tfidf_and_reads_the_whole_article(models):
    urdu, _ = models
    result = predict_text(LONG_URDU)
    assert result["model_version"] == long_articles.MODEL_VERSION
    assert result["is_stub"] is False and result["input_truncated"] is False
    assert result["prediction"] == "Real"
    assert predict_text(LONG_FAKE_URDU)["prediction"] == "Fake"   # label order 0 = real, 1 = fake
    assert urdu.calls == 0


def test_roman_urdu_uses_roman_xlmr_even_when_long(models):
    result = predict_text(" ".join([ROMAN] * (LONG_TEXT_WORDS // 4 + 2)))
    assert result["model_version"] == "xlmr-roman-urdu"
    assert result["prediction"] == "Fake"


def test_xlmr_explanation_by_occlusion(models):
    explanation = explain_text(ROMAN)
    assert explanation["is_stub"] is False
    top = explanation["highlighted_words"][0]
    assert top["word"] == "jhoot" and top["direction"] == "supports_prediction"


def test_long_urdu_explanation_uses_tfidf_weights(models):
    explanation = explain_text(LONG_FAKE_URDU)
    assert explanation["is_stub"] is False
    assert "long-article Urdu model" in explanation["summary"]
    assert explanation["highlighted_words"][0]["direction"] == "supports_prediction"


def test_long_urdu_falls_back_to_truncated_xlmr_without_tfidf(models, monkeypatch, tmp_path):
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(tmp_path / "missing.joblib"))
    result = predict_text(LONG_URDU)
    assert result["model_version"] == "xlmr-urdu"
    assert "truncated" in result["summary"]


def test_short_urdu_is_not_sent_to_the_long_article_model(models, monkeypatch):
    # The TF-IDF model was trained on full articles; it is not a stand-in for headlines.
    monkeypatch.setattr(xlmr, "get_classifier", lambda script: (None, "broken"))
    result = predict_text(SHORT_URDU)
    assert result["prediction"] == "Uncertain" and result["is_stub"] is True


def test_corrupt_long_article_model_falls_back(models, monkeypatch, tmp_path):
    broken = tmp_path / "broken.joblib"
    broken.write_bytes(b"not a model")
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(broken))
    assert predict_text(LONG_URDU)["model_version"] == "xlmr-urdu"


def test_cleaning_matches_the_training_notebook():
    assert clean_urdu_notebook("يہ خبر كے مطابق https://x.com  <b>ہے</b> a@b.com") == "یہ خبر کے مطابق ہے"
    assert clean_urdu_notebook("کَیا؟") == "کیا؟"   # diacritics go, punctuation stays


def test_no_models_gives_uncertain(monkeypatch, tmp_path):
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(tmp_path / "missing.joblib"))
    result = predict_text(ROMAN)
    assert result["prediction"] == "Uncertain" and result["is_stub"] is True
