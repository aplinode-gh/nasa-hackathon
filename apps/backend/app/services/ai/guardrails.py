"""Input/output guardrails ported from the Next.js advisor."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

FARMING_KEYWORDS = [
    "crop", "farm", "plant", "sow", "harvest", "irrigat", "fertiliz", "pesticid",
    "disease", "pest", "weed", "seed", "soil", "water", "rain", "weather",
    "spray", "urea", "dap", "zinc", "rust", "blight", "bollworm", "whitefly",
    "vegetable", "fruit", "orchard", "livestock", "cattle", "buffalo", "goat",
    "poultry", "chicken", "milk", "egg", "feed", "vaccin", "dairy",
    "tractor", "tube well", "canal", "land", "acre", "plot", "field",
    "mandi", "price", "rate", "scheme", "subsidy", "loan", "kissan",
    "organic", "compost", "greenhouse", "tunnel", "drip",
    "wheat", "cotton", "rice", "maize", "sugarcane",
    "gandum", "kapaas", "chawal", "makai", "ganna", "khet", "sinchai",
    "tamatar", "pyaaz", "mirch", "aaloo", "bhindi", "tori", "karela",
    "gobi", "shalgam", "mooli", "baingan", "lauki", "tinda", "kaddu",
    "aam", "kinnow", "malta", "anaar", "angoor", "seeb", "amrood",
    "moong", "mash", "masoor", "chana", "arhar", "lobia",
    "bhains", "gaye", "bakri", "murgi", "murghi", "anda", "doodh",
    "chara", "wanda", "khurak", "farm record", "my farm", "how are my farms",
]

NON_FARMING_KEYWORDS = [
    "politics", "election", "vote", "cricket", "football", "movie", "song",
    "joke", "who won", "stock market", "bitcoin", "crypto", "medical diagnosis",
    "prescription", "love advice", "relationship", "dating", "horoscope",
    "astrology", "lottery", "gambling", "betting", "religion", "prayer",
    "recipe", "cooking", "fashion", "makeup", "travel booking",
]

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?|guidelines?)", re.I),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|above|system)", re.I),
    re.compile(r"forget\s+(everything|all|what)\s+(you|i)\s+(were|have been|are)\s+told", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+(?!farming|crop|weather|agri)", re.I),
    re.compile(r"act\s+as\s+(?:a|an)\s+(?!farming|crop|weather|agri)", re.I),
    re.compile(r"what\s+(?:is|are)\s+your\s+(?:system\s+)?(?:prompt|instructions?|rules?|guidelines?)", re.I),
    re.compile(r"show\s+me\s+your\s+(?:system\s+)?(?:prompt|instructions?|rules?)", re.I),
    re.compile(r"\bbase64\b|\brot13\b|hex\s*decode", re.I),
    re.compile(r"DAN\s+mode|jailbreak|you\s+are\s+unrestricted|no\s+rules\s+apply", re.I),
    re.compile(r"bypass\s+(?:your|the|all)\s+(?:safety|rules?|restrictions?|filters?)", re.I),
]

FABRICATION_PATTERNS = [
    re.compile(r"research\s+shows\s+\d+%", re.I),
    re.compile(r"studies\s+prove", re.I),
    re.compile(r"guaranteed\s+results", re.I),
    re.compile(r"scientifically\s+proven", re.I),
]

DANGEROUS_PATTERNS = [
    re.compile(r"(?:apply|use|inject|give)\s+\d+(\.\d+)?\s*(ml|g|kg|tablet|dose)\s+(?:per|each|every)\s+(?:animal|plant|tree|acre)", re.I),
    re.compile(r"(?:use|apply|give)\s+(?:chlorpyrifos|monocrotophos|phosphamidon|phorate)\s+(?:\d|tablet|dose)", re.I),
    re.compile(r"(?:human|person|you|your)\s+(?:should|must|take|use)\s+(?:medicine|tablet|drug|antibiotic)", re.I),
]


def sanitize_input(text: str) -> str:
    """Strip zero-width characters and collapse abusive repetitions."""
    stripped = re.sub(r"[\u200B-\u200F\u2060-\u2069\uFEFF]", "", text or "")
    return re.sub(r"(.)\1{9,}", r"\1\1\1\1\1", stripped)


def check_input_allowed(text: str) -> tuple[bool, str]:
    """Return (allowed, reason) for topic and prompt-injection guardrails."""
    lower = (text or "").lower()
    if any(pattern.search(text or "") for pattern in INJECTION_PATTERNS):
        return False, "I can only help with farming questions. Please ask about your crops or farm."

    has_farming = any(keyword in lower for keyword in FARMING_KEYWORDS)
    has_non_farming = any(keyword in lower for keyword in NON_FARMING_KEYWORDS)
    if has_non_farming and not has_farming:
        return False, "I'm here to help with farming questions. How can I assist with your crops or farm?"
    if not has_farming and len(text.strip()) >= 200 and has_non_farming:
        return False, "I'm here to help with farming questions. How can I assist with your crops or farm?"
    return True, ""


def finalize_output(text: str) -> str:
    """Apply output guards: log fabrication/safety flags, cap runaway length."""
    if not text:
        return text

    if any(pattern.search(text) for pattern in FABRICATION_PATTERNS):
        logger.warning("[guardrail] response may contain unverified claims")
    if any(pattern.search(text) for pattern in DANGEROUS_PATTERNS):
        logger.warning("[guardrail] response may contain unsafe dosage advice")

    if len(text) > 10000:
        return text[:10000].rstrip() + "…"
    return text
