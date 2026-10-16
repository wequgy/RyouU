"""Text helpers for comparing spoken answers with ID details."""
import re
from datetime import date
from typing import Optional

from rapidfuzz import fuzz

_DIGIT_WORDS = {
    "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9",
}


def spoken_to_digits(text: str) -> str:
    """'four two double seven 1' -> '42771'. Ignores everything that is not a digit word or digit."""
    tokens = re.findall(r"[a-zA-Z]+|\d", (text or "").lower())
    out, repeat = [], 1
    for t in tokens:
        if t in ("double", "triple"):
            repeat = 2 if t == "double" else 3
            continue
        d = _DIGIT_WORDS.get(t, t if t.isdigit() else None)
        if d is not None:
            out.append(d * repeat)
        repeat = 1
    return "".join(out)


def normalize_name(s: str) -> str:
    s = re.sub(r"[^\w\s]", " ", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip()


def name_ratio(expected: str, spoken: str) -> int:
    """Fuzzy score 0-100. token_set_ratio ignores filler like 'my name is'."""
    e, s = normalize_name(expected), normalize_name(spoken)
    if not e or not s:
        return 0
    return int(fuzz.token_set_ratio(e, s))


def parse_date(text: str) -> Optional[date]:
    """Parse '12 April 1999', 'April 12th, 1999', '1999-04-12'. Day-first for ambiguous numeric dates."""
    import dateparser
    if not text:
        return None
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):   # ISO: dateparser's DMY setting would misread it
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    dt = dateparser.parse(text, settings={"DATE_ORDER": "DMY", "PREFER_DAY_OF_MONTH": "first"})
    return dt.date() if dt else None
