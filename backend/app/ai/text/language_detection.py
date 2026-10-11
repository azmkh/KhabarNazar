"""Rule-based script/language detection for Urdu, Roman Urdu, and English.

This is a lightweight heuristic, not a trained language-identification model:
Urdu is recognized by Arabic-script letters, and Latin-script text is labelled
English or Roman Urdu by counting common function words of each language.
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
    if ratio > 0.3:
        return "mixed"

    words = [word.lower() for word in LATIN_WORD.findall(text)]
    roman_hits = sum(word in ROMAN_URDU_WORDS for word in words)
    english_hits = sum(word in ENGLISH_WORDS for word in words)
    if ratio > 0 and roman_hits == 0 and english_hits == 0:
        return "mixed"
    if english_hits > roman_hits:
        return "english"
    return "roman_urdu"
