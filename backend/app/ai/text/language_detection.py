"""Conservative language identification for Urdu, Roman Urdu, and English.

This is a lightweight heuristic, not a trained language-identification model.
Ambiguous Latin-script text is reported as unknown instead of being silently
classified as Roman Urdu.
"""

import re

ARABIC_SCRIPT = ("؀", "ۿ")
LATIN_WORD = re.compile(r"[a-zA-Z]+")

# Frequent Roman Urdu function words / auxiliaries.
ROMAN_URDU_WORDS = {
    "hai", "hain", "ho", "hy", "he", "tha", "thi", "thay", "the", "ka", "ki", "ke", "ko", "ne",
    "se", "mein", "main", "mai", "par", "pe", "aur", "ya", "nahi", "nahin", "nai", "kya", "kyun",
    "kaise", "yeh", "ye", "woh", "wo", "is", "us", "ek", "bhi", "sab", "hum", "ap", "aap", "tum",
    "gaya", "gayi", "raha", "rahi", "rahe", "kar", "kiya", "diya", "liye", "wala", "wali", "khabar",
}
# Frequent English function words. Overlaps with Roman Urdu ("is", "the", "he")
# are removed so they do not count for both languages.
ENGLISH_WORDS = {
    "a", "an", "and", "are", "was", "were", "be", "been", "of", "in", "on", "at", "to", "for",
    "with", "by", "from", "about", "that", "this", "it", "its", "has", "have", "had", "will",
    "would", "not", "but", "or", "as", "they", "their", "said", "news", "which", "who", "after",
    "i", "you", "your", "we", "our", "do", "does", "did", "these", "those",
} - ROMAN_URDU_WORDS


def detect_language(text: str) -> str:
    """Return 'urdu', 'roman_urdu', 'english', 'mixed', or 'unknown'."""
    letters = [character for character in text if character.isalpha()]
    if not letters:
        return "unknown"
    urdu_letters = sum(ARABIC_SCRIPT[0] <= character <= ARABIC_SCRIPT[1] for character in letters)
    ratio = urdu_letters / len(letters)
    if ratio >= 0.7:
        return "urdu"
    # The Urdu-script model was trained on Urdu text, not bilingual samples.
    # Do not route any text containing both scripts to it by a majority vote.
    if ratio > 0:
        return "mixed"

    words = [word.lower() for word in LATIN_WORD.findall(text)]
    roman_hits = sum(word in ROMAN_URDU_WORDS for word in words)
    english_hits = sum(word in ENGLISH_WORDS for word in words)
    # Require a two-marker margin. A single shared or ambiguous function word
    # (for example "is", "the", or "to") is not enough to choose a language.
    if roman_hits >= 2 and roman_hits - english_hits >= 2:
        return "roman_urdu"
    if english_hits >= 2 and english_hits - roman_hits >= 2:
        return "english"
    return "unknown"
