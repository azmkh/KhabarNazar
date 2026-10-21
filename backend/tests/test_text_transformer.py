"""Routing and output format of the Urdu XLM-RoBERTa model, tested with a fake model
(no torch, GPU or 1 GB model folder needed). The fake model only marks texts containing
"جھوٹ" (lie) as fake; it says nothing about real news."""
import pytest

import app.ai.text.predict as predict_module
from app.ai.text.explain import explain_text
from app.ai.text.predict import predict_text
from app.ai.text.preprocess import clean_urdu_for_model
from app.ai.text.transformer_model import load_transformer

URDU_FAKE = "وزیر اعظم نے جھوٹ بولا کہ پیٹرول مفت ہوگا"
URDU_REAL = "حکومت نے پیٹرول کی قیمت میں کمی کا اعلان کر دیا"
ROMAN = "Yeh khabar sach hai ya jhoot, kya aap ko pata hai?"


class FakeTransformer:
    model_version = "test-xlmr"
    remove_punctuation = True

    def clean(self, text):
        return clean_urdu_for_model(text, remove_punctuation=self.remove_punctuation)

    def fake_probabilities(self, texts, batch_size=32):
        return [0.9 if "جھوٹ" in text else 0.2 for text in texts]


@pytest.fixture
def no_tfidf_model(tmp_path, monkeypatch):
    monkeypatch.setenv("KHABARNAZAR_TEXT_MODEL_PATH", str(tmp_path / "missing.joblib"))


@pytest.fixture
def transformer(monkeypatch, no_tfidf_model):
    monkeypatch.setattr(predict_module, "load_transformer", lambda: (FakeTransformer(), None))


def test_cleaning_matches_training_rules():
    cleaned = clean_urdu_for_model("يہ خبر كے مطابق ١٢ بجے https://example.com <b>ہے</b>")
    assert "ي" not in cleaned and "ك" not in cleaned          # Arabic letters -> Urdu letters
    assert "12" in cleaned and "http" not in cleaned and "<b>" not in cleaned
    assert clean_urdu_for_model("کَیا") == "کیا"                 # diacritics removed
    assert clean_urdu_for_model(None) == ""


def test_punctuation_removed_only_when_the_model_was_trained_that_way():
    text = "وزیر اعظم نے کہا: ’یہ خبر غلط ہے‘۔ کیا واقعی؟"
    kept = clean_urdu_for_model(text)
    removed = clean_urdu_for_model(text, remove_punctuation=True)
    assert "۔" in kept and "؟" in kept and ":" in kept
    assert not any(mark in removed for mark in "۔؟:’‘")
    assert removed == "وزیر اعظم نے کہا یہ خبر غلط ہے کیا واقعی"


def test_missing_model_folder_is_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("KHABARNAZAR_TEXT_TRANSFORMER_DIR", str(tmp_path / "nothing"))
    model, reason = load_transformer()
    assert model is None and "not found" in reason


def test_urdu_text_uses_transformer(transformer):
    fake = predict_text(URDU_FAKE)
    assert fake["prediction"] == "Fake" and fake["is_stub"] is False
    assert fake["fake_probability"] == pytest.approx(0.9)
    assert fake["confidence"] == pytest.approx(0.9)
    assert fake["model_version"] == "test-xlmr"

    real = predict_text(URDU_REAL)
    assert real["prediction"] == "Real"
    assert real["confidence"] == pytest.approx(0.8)            # probability of the predicted label
    assert real["fake_probability"] == pytest.approx(0.2)      # risk stays low for a confident Real


def test_roman_urdu_is_not_sent_to_urdu_model(transformer):
    result = predict_text(ROMAN)
    assert result["is_stub"] is True and result["prediction"] == "Uncertain"
    assert "Roman Urdu" in result["summary"]


def test_transformer_explanation_highlights_the_deciding_word(transformer):
    explanation = explain_text(URDU_FAKE)
    assert explanation["is_stub"] is False
    top = explanation["highlighted_words"][0]
    assert top["word"] == "جھوٹ" and top["direction"] == "supports_prediction"
    assert top["contribution"] == pytest.approx(0.7)           # 0.9 with the word, 0.2 without it


def test_broken_transformer_falls_back(monkeypatch, no_tfidf_model):
    class Broken(FakeTransformer):
        def fake_probabilities(self, texts, batch_size=32):
            raise RuntimeError("GPU out of memory")

    monkeypatch.setattr(predict_module, "load_transformer", lambda: (Broken(), None))
    result = predict_text(URDU_FAKE)
    assert result["prediction"] == "Uncertain" and result["is_stub"] is True
