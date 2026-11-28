"""OCR post-processing: reading order of word boxes and the Urdu-script confidence cutoff."""

from app.ai.image.ocr import _reading_order, has_usable_text


def _box(x0, y0, x1, y1, text, conf=0.5):
    return ([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, conf)


def _lines(detections):
    return [" ".join(text for text, _ in line) for line in _reading_order(detections)]


def test_urdu_words_on_one_line_read_right_to_left():
    # EasyOCR order: left to right. The rightmost box holds the first words of the sentence.
    detections = [
        _box(55, 231, 202, 308, "انٹرنیٹ"),
        _box(328, 236, 498, 310, "سات دن"),
        _box(776, 208, 1152, 320, "حکومت نے اعلان کیا"),
    ]
    assert _lines(detections) == ["حکومت نے اعلان کیا سات دن انٹرنیٹ"]


def test_tall_overlapping_nastaliq_lines_are_not_interleaved():
    # Boxes of two lines overlap vertically and arrive interleaved.
    detections = [
        _box(450, 290, 795, 405, "ب"),
        _box(1048, 313, 1132, 441, "الف"),
        _box(488, 367, 867, 455, "د"),
        _box(919, 383, 1077, 449, "ج"),
        _box(467, 171, 1128, 258, "پہلی سطر"),
    ]
    assert _lines(detections) == ["پہلی سطر", "الف ب", "ج د"]


def test_latin_lines_read_left_to_right():
    detections = [_box(400, 10, 600, 50, "world"), _box(10, 12, 200, 48, "Hello"), _box(10, 80, 300, 120, "second line")]
    assert _lines(detections) == ["Hello world", "second line"]


def test_empty_and_blank_detections():
    assert _reading_order([]) == []
    assert _reading_order([_box(0, 0, 10, 10, "  ")]) == []


def _ocr(text, confidence, language):
    return {"text": text, "confidence": confidence, "language": language}


URDU = "حکومت نے اعلان کیا ہے کہ ملک بھر میں"


def test_urdu_text_uses_its_own_lower_cutoff():
    assert has_usable_text(_ocr(URDU, 0.28, "urdu"), 10, 0.3, 0.2)
    assert not has_usable_text(_ocr(URDU, 0.06, "urdu"), 10, 0.3, 0.2)


def test_other_languages_keep_the_main_cutoff():
    assert not has_usable_text(_ocr("The government has announced", 0.28, "english"), 10, 0.3, 0.2)
    assert not has_usable_text(_ocr("IBIB آST UPBISSSTIOJI", 0.28, "mixed"), 10, 0.3, 0.2)


def test_without_urdu_cutoff_behaviour_is_unchanged():
    assert not has_usable_text(_ocr(URDU, 0.28, "urdu"), 10, 0.3)
