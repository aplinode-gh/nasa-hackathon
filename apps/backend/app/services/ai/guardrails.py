"""Advisor guardrails: input/output checks and OpenAI Agents SDK guardrail hooks.

Mirrors boilerplate ``lib/advisor/guardrails.ts`` and exposes SDK
``InputGuardrail``/``OutputGuardrail`` objects for attachment to agents.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    TResponseInputItem,
    input_guardrail,
    output_guardrail,
)

logger = logging.getLogger(__name__)

FARMING_KEYWORDS = [
    # English
    "crop", "farm", "plant", "sow", "harvest", "irrigat", "fertiliz", "pesticid",
    "disease", "pest", "weed", "seed", "soil", "water", "rain", "weather",
    "spray", "urea", "dap", "zinc", "rust", "blight", "bollworm", "whitefly",
    "vegetable", "fruit", "orchard", "livestock", "cattle", "buffalo", "goat",
    "poultry", "chicken", "milk", "egg", "feed", "vaccin", "dairy",
    "tractor", "tube well", "canal", "land", "acre", "plot", "field",
    "mandi", "price", "rate", "scheme", "subsidy", "loan", "kissan",
    "organic", "compost", "greenhouse", "tunnel", "drip",
    # Major crops (English + Urdu)
    "wheat", "cotton", "rice", "maize", "sugarcane",
    "gandum", "kapaas", "chawal", "makai", "ganna", "khet", "sinchai",
    # Vegetables (Urdu transliteration)
    "tamatar", "pyaaz", "mirch", "aaloo", "bhindi", "tori", "karela",
    "gobi", "shalgam", "mooli", "baingan", "lauki", "tinda", "kaddu",
    # Fruits (Urdu transliteration)
    "aam", "kinnow", "malta", "anaar", "angoor", "seeb", "amrood",
    # Pulses (Urdu transliteration)
    "moong", "mash", "masoor", "chana", "arhar", "lobia",
    # Livestock (Urdu transliteration)
    "bhains", "gaye", "bakri", "murgi", "murghi", "anda", "doodh",
    "chara", "wanda", "khurak",
    # Farm-related phrases
    "farm record", "my farm", "how are my farms",
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
    re.compile(r"pretend\s+(?:you|to)\s+(?:are|be)\s+(?!farming|crop|weather|agri)", re.I),
    re.compile(r"what\s+(?:is|are)\s+your\s+(?:system\s+)?(?:prompt|instructions?|rules?|guidelines?)", re.I),
    re.compile(r"show\s+me\s+your\s+(?:system\s+)?(?:prompt|instructions?|rules?)", re.I),
    re.compile(r"repeat\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?)", re.I),
    re.compile(r"\bbase64\b", re.I),
    re.compile(r"\brot13\b", re.I),
    re.compile(r"\bhex\s*decode\b", re.I),
    re.compile(r"DAN\s+mode", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"you\s+are\s+unrestricted", re.I),
    re.compile(r"no\s+rules\s+apply", re.I),
    re.compile(r"bypass\s+(?:your|the|all)\s+(?:safety|rules?|restrictions?|filters?)", re.I),
]

FABRICATION_PATTERNS = [
    re.compile(r"research\s+shows\s+\d+%", re.I),
    re.compile(r"studies\s+prove", re.I),
    re.compile(r"according\s+to\s+a\s+(recent\s+)?study\s+by\s+(?!Punjab|Sindh|Pakistan|FAO|ICARDA|PAR)", re.I),
    re.compile(r"\d{2,3}%\s+increase\s+in\s+yield", re.I),
    re.compile(r"guaranteed\s+results", re.I),
    re.compile(r"scientifically\s+proven", re.I),
    re.compile(r"\bexactly\s+\d+(\.\d+)?\s*(kg|ton|maund|acre)", re.I),
    re.compile(r"(?:i|we)\s+(?:personally|can)\s+(?:guarantee|promise|confirm)\s+\d+%", re.I),
    re.compile(r"(?:the\s+)?(?:current|latest)\s+price\s+is\s+Rs\s*\d+", re.I),
]

DANGEROUS_PATTERNS = [
    re.compile(r"(?:apply|use|inject|give)\s+\d+(\.\d+)?\s*(ml|g|kg|tablet|dose)\s+(?:per|each|every)\s+(?:animal|plant|tree|acre)", re.I),
    re.compile(r"(?:use|apply|give)\s+(?:chlorpyrifos|monocrotophos|phosphamidon|phorate)\s+(?:\d|tablet|dose)", re.I),
    re.compile(r"(?:human|person|you|your)\s+(?:should|must|take|use)\s+(?:medicine|tablet|drug|antibiotic)", re.I),
    re.compile(r"(?:connect|wire|install)\s+(?:directly|without)\s+(?:earthing|grounding|breaker)", re.I),
]

URDU_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


def _extract_input_text(input_value: Any) -> str:
    if isinstance(input_value, str):
        return input_value
    if isinstance(input_value, list):
        parts: list[str] = []
        for item in input_value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str):
                    parts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") in ("text", "input_text"):
                            parts.append(str(block.get("text") or ""))
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return " ".join(p for p in parts if p)
    return str(input_value or "")


# ── Utility helpers (kept for route-level prechecks and output post-processing) ──

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


# ── SDK input guardrails ─────────────────────────────────────────────────────

@input_guardrail(name="input_sanitization_guardrail", run_in_parallel=False)
async def input_sanitization_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    text = _extract_input_text(input)
    stripped = re.sub(r"[\u200B-\u200F\u2060-\u2069\uFEFF]", "", text)
    deduplicated = re.sub(r"(.)\1{9,}", r"\1\1\1\1\1", stripped)
    was_modified = stripped != text or deduplicated != stripped
    return GuardrailFunctionOutput(
        tripwire_triggered=False,
        output_info={"sanitized": deduplicated, "wasModified": was_modified},
    )


@input_guardrail(name="farming_only_guardrail")
async def farming_only_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    text = _extract_input_text(input)
    lower = text.lower()
    has_farming = any(keyword in lower for keyword in FARMING_KEYWORDS)
    has_non_farming = any(keyword in lower for keyword in NON_FARMING_KEYWORDS)
    is_on_topic = has_farming or (not has_non_farming and len(text.strip()) < 200)
    tripwire = (not is_on_topic) and has_non_farming
    return GuardrailFunctionOutput(
        tripwire_triggered=tripwire,
        output_info={"isOnTopic": is_on_topic, "reason": "farming-related" if is_on_topic else "non-farming query"},
    )


@input_guardrail(name="prompt_injection_guardrail")
async def prompt_injection_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], input: str | list[TResponseInputItem]
) -> GuardrailFunctionOutput:
    text = _extract_input_text(input)
    is_injection = any(pattern.search(text) for pattern in INJECTION_PATTERNS)
    return GuardrailFunctionOutput(
        tripwire_triggered=is_injection,
        output_info={"isInjection": is_injection, "reason": "potential prompt injection detected" if is_injection else "clean"},
    )


# ── SDK output guardrails ────────────────────────────────────────────────────

@output_guardrail(name="no_fabrication_guardrail")
async def no_fabrication_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], output: Any
) -> GuardrailFunctionOutput:
    text = output if isinstance(output, str) else str(output or "")
    has_fabrication = any(pattern.search(text) for pattern in FABRICATION_PATTERNS)
    if has_fabrication:
        logger.warning("[guardrail] response contains unverified claims")
    return GuardrailFunctionOutput(
        tripwire_triggered=has_fabrication,
        output_info={"hasFabrication": has_fabrication, "reason": "contains unverified claims" if has_fabrication else "clean"},
    )


@output_guardrail(name="safety_boundary_guardrail")
async def safety_boundary_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], output: Any
) -> GuardrailFunctionOutput:
    text = output if isinstance(output, str) else str(output or "")
    is_dangerous = any(pattern.search(text) for pattern in DANGEROUS_PATTERNS)
    if is_dangerous:
        logger.warning("[guardrail] response may contain unsafe advice")
    return GuardrailFunctionOutput(
        tripwire_triggered=is_dangerous,
        output_info={"isDangerous": is_dangerous, "reason": "potentially dangerous advice detected" if is_dangerous else "safe"},
    )


@output_guardrail(name="language_consistency_guardrail")
async def language_consistency_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], output: Any
) -> GuardrailFunctionOutput:
    text = output if isinstance(output, str) else str(output or "")
    if not text or len(text) < 20:
        return GuardrailFunctionOutput(tripwire_triggered=False, output_info={"consistent": True})

    has_urdu = bool(URDU_SCRIPT_RE.search(text))
    if not has_urdu:
        return GuardrailFunctionOutput(tripwire_triggered=False, output_info={"consistent": True, "language": "en"})

    sentences = [s for s in re.split(r"[.!؟\n]+", text) if s.strip()]
    mixed_sentences = 0
    for sentence in sentences:
        trimmed = sentence.strip()
        if len(trimmed) < 5:
            continue
        urdu_chars = len(URDU_SCRIPT_RE.findall(trimmed))
        total_chars = len(re.sub(r"\s", "", trimmed))
        if total_chars == 0:
            continue
        urdu_ratio = urdu_chars / total_chars
        if urdu_ratio < 0.3 and len(trimmed) > 10:
            mixed_sentences += 1

    mixing_detected = mixed_sentences > 0
    return GuardrailFunctionOutput(
        tripwire_triggered=False,  # log/detect only; prompt enforces consistency
        output_info={
            "consistent": not mixing_detected,
            "mixedSentences": mixed_sentences,
            "reason": f"Detected {mixed_sentences} sentences with language mixing" if mixing_detected else "consistent",
        },
    )


@output_guardrail(name="output_length_guardrail")
async def output_length_guardrail(
    ctx: RunContextWrapper[Any], agent: Agent[Any], output: Any
) -> GuardrailFunctionOutput:
    text = output if isinstance(output, str) else str(output or "")
    char_count = len(text)
    is_excessive = char_count > 4000
    is_absurd = char_count > 10000
    reason = "within bounds"
    if is_absurd:
        reason = "response exceeds maximum length"
    elif is_excessive:
        reason = "response is longer than typical"
    return GuardrailFunctionOutput(
        tripwire_triggered=is_absurd,
        output_info={
            "charCount": char_count,
            "isExcessive": is_excessive,
            "isAbsurd": is_absurd,
            "reason": reason,
        },
    )


# Bundles mirroring boilerplate exports
advisor_input_guardrails = [
    input_sanitization_guardrail,
    farming_only_guardrail,
    prompt_injection_guardrail,
]

advisor_output_guardrails = [
    no_fabrication_guardrail,
    safety_boundary_guardrail,
    language_consistency_guardrail,
    output_length_guardrail,
]
