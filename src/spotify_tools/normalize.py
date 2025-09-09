from __future__ import annotations
import re
import unicodedata
from typing import Iterable, List, Set


_WHITESPACE_RE = re.compile(r"\s+")
# Common suffixes/markers we want to ignore in relaxed mode
_MARKER_PATTERNS = [
    r"\s*-\s*remaster(?:ed)?\s*(?:\d{2,4})?",
    r"\s*-\s*(?:mono|stereo)\s*version",
    r"\s*-\s*(?:radio|clean|explicit)\s*edit",
    r"\s*\((?:feat\.?|featuring) [^)]*\)",
    r"\s*\[(?:feat\.?|featuring) [^]]*\]",
    r"\s*\((?:version|edit|remaster[^)]*)\)",
]
_MARKER_RE = re.compile("|".join(_MARKER_PATTERNS), re.IGNORECASE)
_PUNCT_RE = re.compile(r"[\u2018\u2019\u201C\u201D\u2014\-—–:,.;!?'\"]")

# Chinese, Japanese, Korean characters get destroyed by NFKD handling (Normalization Form Compatibility Decomposition) for default ascii handling of latin characters
def _has_cjk(s: str) -> bool:
    for ch in s:
        o = ord(ch)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) or (0x3400 <= o <= 0x4DBF):
            return True
    return False

# default accent strip logic destroyed non-latin characters, avoid this
def _strip_accents_latin_only(s: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKD", s):
        name = unicodedata.name(ch, "")
        if "LATIN" in name and unicodedata.combining(ch):
            # drop combining mark on Latin letters
            continue
        out.append(ch)
    # recompose
    return unicodedata.normalize("NFC", "".join(out))

# Strip accents, 
# if strict is true, "Notion remaster" and "Notion" would be different songs. strict==true only removes accents.
# if strict is false, "Notion remaster" and "Notion" would be the same song. strict==false normalizes: accents, "feat", "remaster", "&", and whitespace
def normalize_title(title: str, *, strict: bool = False) -> str:
    s = unicodedata.normalize("NFKC", title or "").strip()
    if not s: 
        return ""
    
    has_cjk = _has_cjk(s)

    # lowercase but unicode-normalized aware
    s = s.casefold()

    if not strict:
        s = _MARKER_RE.sub("", s)

    if has_cjk: 
        s = _PUNCT_RE.sub(" ", s)
    else: 
        s = _strip_accents_latin_only(s)
        s = _PUNCT_RE.sub(" ", s)
        s = s.replace("&", " and ")
    
    s = _WHITESPACE_RE.sub(" ", s).strip()

    return s


def normalize_artists(artists: Iterable[str]) -> List[str]:
    # Treat artists as a set for dedupe; sort for them to appear in same order if different songs ordered them differently for some reason
    norm: Set[str] = set()
    for a in artists:
        s = normalize_title(a, strict=True)
        if s:
            norm.add(s)
    return sorted(norm)
