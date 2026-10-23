"""Fast unit tests for model-specific XLM-R config and preprocessing."""

import sys
import types

import pytest

from app.ai.text import xlmr
from app.ai.text.preprocess import clean_urdu_for_model
from app.config import Settings, settings


def test_model_max_length_defaults_are_per_checkpoint(monkeypatch):
    monkeypatch.delenv("KHABARNAZAR_XLMR_MAX_LEN", raising=False)
    monkeypatch.delenv("KHABARNAZAR_URDU_XLMR_MAX_LEN", raising=False)
    monkeypatch.delenv("KHABARNAZAR_ROMAN_XLMR_MAX_LEN", raising=False)
    monkeypatch.setattr(settings, "XLMR_MAX_LEN", None)
    monkeypatch.setattr(settings, "URDU_XLMR_MAX_LEN", None)
    monkeypatch.setattr(settings, "ROMAN_XLMR_MAX_LEN", None)
    assert xlmr.configured_max_length("urdu", metadata_max_len=64) == 64
    assert xlmr.configured_max_length("roman") == 512


def test_legacy_and_per_model_max_length_precedence(monkeypatch):
    monkeypatch.setattr(settings, "XLMR_MAX_LEN", None)
    monkeypatch.setattr(settings, "ROMAN_XLMR_MAX_LEN", None)
    monkeypatch.setattr(settings, "URDU_XLMR_MAX_LEN", None)
    monkeypatch.setenv("KHABARNAZAR_XLMR_MAX_LEN", "256")
    assert xlmr.configured_max_length("roman") == 256
    # Legacy setting is a Roman Urdu compatibility alias; Urdu keeps its checkpoint limit.
    assert xlmr.configured_max_length("urdu", metadata_max_len=64) == 64
    monkeypatch.setenv("KHABARNAZAR_ROMAN_XLMR_MAX_LEN", "512")
    assert xlmr.configured_max_length("roman") == 512
    monkeypatch.setenv("KHABARNAZAR_URDU_XLMR_MAX_LEN", "32")
    assert xlmr.configured_max_length("urdu", metadata_max_len=64) == 32


def test_legacy_max_length_is_loaded_from_backend_dotenv(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=sqlite:///:memory:\n"
        f"JWT_SECRET={'x' * 40}\n"
        "KHABARNAZAR_XLMR_MAX_LEN=256\n",
        encoding="utf-8",
    )
    configured = Settings(_env_file=env_file)
    assert configured.XLMR_MAX_LEN == 256


@pytest.mark.parametrize("value", [0, 513, -1])
def test_max_length_override_cannot_exceed_the_trained_limit(monkeypatch, value):
    monkeypatch.setattr(settings, "XLMR_MAX_LEN", value)
    monkeypatch.delenv("KHABARNAZAR_XLMR_MAX_LEN", raising=False)
    with pytest.raises(ValueError, match="trained limit"):
        xlmr.configured_max_length("roman")


def test_model_specific_preprocessing_keeps_roman_text_unchanged():
    assert clean_urdu_for_model("يہ خبر https://example.com <b>ہے</b>", True) == "یہ خبر ہے"
    raw_roman = "  Yeh KHABAR hai!!! https://example.com  "
    roman_model = xlmr.XlmrClassifier.__new__(xlmr.XlmrClassifier)
    roman_model.script = "roman"
    # Roman checkpoint consumes the training `roman_text` representation directly.
    assert roman_model.prepare(raw_roman) == raw_roman


def test_artifact_validator_requires_config_weights_and_tokenizer(tmp_path):
    assert not xlmr.is_configured("roman")
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    assert not xlmr._artifact_files_present(tmp_path)
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    assert xlmr._artifact_files_present(tmp_path)


def test_checkpoint_labels_are_read_from_the_actual_mapping():
    labels, fake_index = xlmr._labels_from_config(
        types.SimpleNamespace(id2label={"0": "REAL", "1": "FAKE"}), "roman"
    )
    assert labels == {0: "real", 1: "fake"} and fake_index == 1
    with pytest.raises(ValueError, match="exactly REAL and FAKE"):
        xlmr._labels_from_config(types.SimpleNamespace(id2label={0: "LABEL_0", 1: "LABEL_1"}), "roman")


def test_model_loader_validates_position_limit_and_keeps_cpu_support(tmp_path, monkeypatch):
    class FakeTorch:
        cuda = types.SimpleNamespace(is_available=lambda: False)

    class FakeTokenizer:
        pad_token_id = 1
        model_max_length = 512

    class FakeModel:
        config = types.SimpleNamespace(
            id2label={0: "REAL", 1: "FAKE"}, model_type="xlm-roberta", max_position_embeddings=514
        )

        def to(self, device):
            assert device == "cpu"
            return self

        def eval(self):
            return self

    auto_tokenizer = types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: FakeTokenizer())
    auto_model = types.SimpleNamespace(from_pretrained=lambda *args, **kwargs: FakeModel())
    monkeypatch.setitem(sys.modules, "torch", FakeTorch)
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(
        AutoTokenizer=auto_tokenizer, AutoModelForSequenceClassification=auto_model
    ))
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    monkeypatch.setattr(settings, "ROMAN_XLMR_MAX_LEN", None)
    monkeypatch.setattr(settings, "XLMR_MAX_LEN", None)
    model = xlmr.XlmrClassifier(tmp_path, "roman")
    assert model.max_len == 512 and model.device == "cpu" and model.fake_index == 1


def test_oversized_override_is_rejected_against_model_positions(tmp_path, monkeypatch):
    class FakeTorch:
        cuda = types.SimpleNamespace(is_available=lambda: False)

    class FakeTokenizer:
        pad_token_id = 1
        model_max_length = 512

    class FakeModel:
        config = types.SimpleNamespace(
            id2label={0: "REAL", 1: "FAKE"}, model_type="xlm-roberta", max_position_embeddings=514
        )

        def to(self, device): return self
        def eval(self): return self

    monkeypatch.setitem(sys.modules, "torch", FakeTorch)
    monkeypatch.setitem(sys.modules, "transformers", types.SimpleNamespace(
        AutoTokenizer=types.SimpleNamespace(from_pretrained=lambda *a, **k: FakeTokenizer()),
        AutoModelForSequenceClassification=types.SimpleNamespace(from_pretrained=lambda *a, **k: FakeModel()),
    ))
    monkeypatch.setattr(xlmr, "configured_max_length", lambda script, metadata_max_len=None: 513)
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "tokenizer.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    with pytest.raises(ValueError, match="exceeds tokenizer/model limit 512"):
        xlmr.XlmrClassifier(tmp_path, "roman")


def test_each_urdu_checkpoint_gets_the_cleaning_it_was_trained_with():
    text = "يہ خبر: کَیا واقعی؟ https://example.com"
    legacy = xlmr.XlmrClassifier.__new__(xlmr.XlmrClassifier)
    legacy.script, legacy.notebook_cleaning, legacy.remove_punctuation = "urdu", False, True
    notebook = xlmr.XlmrClassifier.__new__(xlmr.XlmrClassifier)
    notebook.script, notebook.notebook_cleaning = "urdu", True
    # text-model-v1 (khabarnazar_config.json): urduhack cleaning with punctuation removed.
    assert legacy.prepare(text) == "یہ خبر کیا واقعی"
    # urdu-xlmr-v1 (no metadata file): the notebook's clean_urdu, which keeps punctuation.
    assert notebook.prepare(text) == "یہ خبر: کیا واقعی؟"


def test_notebook_urdu_release_uses_its_training_length(monkeypatch):
    monkeypatch.delenv("KHABARNAZAR_URDU_XLMR_MAX_LEN", raising=False)
    monkeypatch.setattr(settings, "URDU_XLMR_MAX_LEN", None)
    assert xlmr.configured_max_length("urdu", xlmr.URDU_NOTEBOOK_MAX_LEN) == 256
