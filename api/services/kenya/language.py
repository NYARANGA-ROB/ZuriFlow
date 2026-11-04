"""Turn-level Kenyan language and mix detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from api.services.kenya.config import KenyaLanguage
from api.services.kenyan_intent.patterns import SWAHILI_MARKERS

_SHENG = frozenset(
    {
        "poa",
        "fiti",
        "sasa",
        "mambo",
        "vipi",
        "msee",
        "dem",
        "chapo",
        "doh",
        "fala",
        "sai",
        "cheki",
        "noma",
        "wazi",
        "bro",
        "boss",
        "manze",
        "ukoje",
        "niaje",
        "rada",
        "mbele",
        "isha",
        "dooh",
    }
)

_ENGLISH = frozenset(
    {
        "the",
        "and",
        "you",
        "please",
        "want",
        "need",
        "help",
        "pay",
        "balance",
        "account",
        "appointment",
        "order",
        "delivery",
        "cancel",
        "confirm",
        "where",
        "when",
        "how",
        "my",
        "is",
        "call",
        "hello",
        "thanks",
        "yes",
        "no",
    }
)

# High-confidence language lock: do not flip the session below this.
LANGUAGE_SWITCH_THRESHOLD = 0.72


class ConversationalMix(str, Enum):
    NONE = "none"
    ENGLISH_KISWAHILI = "en_sw"
    ENGLISH_SHENG = "en_sheng"
    KISWAHILI_SHENG = "sw_sheng"
    MULTILINGUAL = "multilingual"


class DetectedStyle(str, Enum):
    FORMAL = "formal"
    NEUTRAL = "neutral"
    CASUAL_KENYAN = "casual_kenyan"
    SHENG_HEAVY = "sheng_heavy"
    KISWAHILI_FIRST = "kiswahili_first"
    ENGLISH_FIRST = "english_first"


@dataclass(frozen=True)
class LanguageGuess:
    language: KenyaLanguage
    primary_language: KenyaLanguage
    secondary_language: KenyaLanguage | None
    confidence: float
    mix: ConversationalMix
    style: DetectedStyle
    swahili_hits: int
    sheng_hits: int
    english_hits: int
    switched: bool = False

    def to_dict(self) -> dict:
        return {
            "language": self.language.value,
            "primary_language": self.primary_language.value,
            "secondary_language": (
                self.secondary_language.value if self.secondary_language else None
            ),
            "confidence": round(self.confidence, 4),
            "mix": self.mix.value,
            "style": self.style.value,
            "swahili_hits": self.swahili_hits,
            "sheng_hits": self.sheng_hits,
            "english_hits": self.english_hits,
            "switched": self.switched,
        }


def identify_kenya_language(text: str) -> LanguageGuess:
    tokens = [t for t in "".join(ch.lower() if ch.isalnum() else " " for ch in text).split() if t]
    if not tokens:
        return LanguageGuess(
            KenyaLanguage.MIXED,
            KenyaLanguage.MIXED,
            None,
            0.0,
            ConversationalMix.NONE,
            DetectedStyle.NEUTRAL,
            0,
            0,
            0,
        )

    sw = sum(1 for t in tokens if t in SWAHILI_MARKERS)
    sh = sum(1 for t in tokens if t in _SHENG)
    en = sum(1 for t in tokens if t in _ENGLISH)
    n = len(tokens)
    mix, primary, secondary, language, style, confidence = _resolve_mix(sw, sh, en, n)
    return LanguageGuess(
        language=language,
        primary_language=primary,
        secondary_language=secondary,
        confidence=confidence,
        mix=mix,
        style=style,
        swahili_hits=sw,
        sheng_hits=sh,
        english_hits=en,
    )


def lock_language(
    guess: LanguageGuess,
    previous: KenyaLanguage | None,
) -> LanguageGuess:
    """Keep the session language unless this turn is confidently different."""
    if previous is None or guess.confidence >= LANGUAGE_SWITCH_THRESHOLD:
        switched = previous is not None and guess.primary_language != previous
        if not switched:
            return guess
        return LanguageGuess(
            language=guess.language,
            primary_language=guess.primary_language,
            secondary_language=guess.secondary_language,
            confidence=guess.confidence,
            mix=guess.mix,
            style=guess.style,
            swahili_hits=guess.swahili_hits,
            sheng_hits=guess.sheng_hits,
            english_hits=guess.english_hits,
            switched=True,
        )
    return LanguageGuess(
        language=previous if previous != KenyaLanguage.MIXED else guess.language,
        primary_language=previous,
        secondary_language=guess.secondary_language or guess.primary_language,
        confidence=guess.confidence,
        mix=guess.mix if guess.mix != ConversationalMix.NONE else ConversationalMix.NONE,
        style=guess.style,
        swahili_hits=guess.swahili_hits,
        sheng_hits=guess.sheng_hits,
        english_hits=guess.english_hits,
        switched=False,
    )


def _resolve_mix(
    sw: int, sh: int, en: int, n: int
) -> tuple[ConversationalMix, KenyaLanguage, KenyaLanguage | None, KenyaLanguage, DetectedStyle, float]:
    present = [
        (KenyaLanguage.KISWAHILI, sw),
        (KenyaLanguage.SHENG, sh),
        (KenyaLanguage.ENGLISH, en),
    ]
    present.sort(key=lambda x: x[1], reverse=True)
    nonzero = [(lang, c) for lang, c in present if c > 0]
    languages_used = len(nonzero)

    if languages_used >= 3:
        mix = ConversationalMix.MULTILINGUAL
        conf = min(0.94, 0.5 + (sw + sh + en) / n)
        return mix, nonzero[0][0], nonzero[1][0], KenyaLanguage.MIXED, DetectedStyle.CASUAL_KENYAN, conf

    if languages_used == 2:
        a, b = nonzero[0][0], nonzero[1][0]
        pair = {a, b}
        if pair == {KenyaLanguage.ENGLISH, KenyaLanguage.KISWAHILI}:
            mix = ConversationalMix.ENGLISH_KISWAHILI
        elif pair == {KenyaLanguage.ENGLISH, KenyaLanguage.SHENG}:
            mix = ConversationalMix.ENGLISH_SHENG
        else:
            mix = ConversationalMix.KISWAHILI_SHENG
        conf = min(0.93, 0.52 + (nonzero[0][1] + nonzero[1][1]) / n)
        style = DetectedStyle.SHENG_HEAVY if KenyaLanguage.SHENG in pair else DetectedStyle.CASUAL_KENYAN
        return mix, a, b, KenyaLanguage.MIXED, style, conf

    if sh >= 2 or (sh and sh >= sw and sh >= en):
        conf = min(0.92, 0.45 + sh / n)
        return ConversationalMix.NONE, KenyaLanguage.SHENG, None, KenyaLanguage.SHENG, DetectedStyle.SHENG_HEAVY, conf
    if sw > en:
        conf = min(0.92, 0.45 + sw / n)
        return ConversationalMix.NONE, KenyaLanguage.KISWAHILI, None, KenyaLanguage.KISWAHILI, DetectedStyle.KISWAHILI_FIRST, conf
    if en > 0:
        conf = min(0.9, 0.4 + en / n)
        style = DetectedStyle.ENGLISH_FIRST if en >= 3 else DetectedStyle.NEUTRAL
        return ConversationalMix.NONE, KenyaLanguage.ENGLISH, None, KenyaLanguage.ENGLISH, style, conf
    if sw or sh:
        lang = KenyaLanguage.SHENG if sh else KenyaLanguage.KISWAHILI
        return ConversationalMix.NONE, lang, None, lang, DetectedStyle.NEUTRAL, 0.55
    return ConversationalMix.NONE, KenyaLanguage.ENGLISH, None, KenyaLanguage.ENGLISH, DetectedStyle.FORMAL, 0.3
