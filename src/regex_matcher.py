"""
Regex Pattern Matcher Engine.
Detects structured entities in OCR-extracted text:
URLs, IP Addresses, Emails, JSON Blocks, Code Snippets, Hex Colors, UUIDs, Phone Numbers.
"""

import re
from typing import List, Dict, Tuple
from src.config import REGEX_PATTERNS


class MatchResult:
    def __init__(self, pattern_name: str, match_text: str, start: int, end: int):
        self.pattern_name = pattern_name
        self.match_text = match_text
        self.start = start
        self.end = end

    def __repr__(self):
        return f"<Match [{self.pattern_name}] '{self.match_text[:40]}'>"


# Compiled pattern cache
_COMPILED_PATTERNS: Dict[str, re.Pattern] = {}

def _get_pattern(name: str) -> re.Pattern:
    if name not in _COMPILED_PATTERNS:
        _COMPILED_PATTERNS[name] = re.compile(REGEX_PATTERNS[name], re.IGNORECASE | re.MULTILINE)
    return _COMPILED_PATTERNS[name]


class RegexMatcher:
    @staticmethod
    def find_all(text: str, active_patterns: List[str] = None) -> List[MatchResult]:
        """
        Scans text for all enabled regex patterns.
        Returns: sorted list of MatchResult objects by position.
        """
        if not text:
            return []

        if active_patterns is None:
            active_patterns = list(REGEX_PATTERNS.keys())

        results: List[MatchResult] = []
        for name in active_patterns:
            if name not in REGEX_PATTERNS:
                continue
            pattern = _get_pattern(name)
            for m in pattern.finditer(text):
                results.append(MatchResult(name, m.group(), m.start(), m.end()))

        # Sort by position, de-duplicate overlapping matches (keep first/longest)
        results.sort(key=lambda r: (r.start, -len(r.match_text)))
        deduped: List[MatchResult] = []
        last_end = -1
        for r in results:
            if r.start >= last_end:
                deduped.append(r)
                last_end = r.end

        return deduped

    @staticmethod
    def group_by_pattern(results: List[MatchResult]) -> Dict[str, List[str]]:
        """Groups match results by pattern name → list of match strings."""
        groups: Dict[str, List[str]] = {}
        for r in results:
            groups.setdefault(r.pattern_name, []).append(r.match_text)
        return groups

    @staticmethod
    def summary_string(results: List[MatchResult]) -> str:
        """Returns human-readable summary of all matches."""
        if not results:
            return "No patterns detected."
        groups = RegexMatcher.group_by_pattern(results)
        lines = []
        for pattern_name, matches in groups.items():
            lines.append(f"[{pattern_name}] ({len(matches)} match{'es' if len(matches) != 1 else ''}):")
            for m in matches[:10]:  # cap at 10 per pattern in display
                lines.append(f"  • {m[:120]}")
            if len(matches) > 10:
                lines.append(f"  … and {len(matches) - 10} more")
        return "\n".join(lines)
