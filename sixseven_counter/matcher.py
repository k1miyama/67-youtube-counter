from __future__ import annotations

import html
import re

from .models import Match, MatchResult, Token, TranscriptSnippet

TOKEN_RE = re.compile(r"[A-Za-z]+|\d+")
POSSIBLE_VALUES = {"six", "6", "seven", "7"}


def find_sixseven_matches(snippets: list[TranscriptSnippet]) -> MatchResult:
    tokens = tokenize_transcript(snippets)
    confirmed: list[Match] = []
    consumed_token_indexes: set[int] = set()

    index = 0
    while index < len(tokens):
        single_pattern = _single_confirmed_pattern(tokens[index])
        if single_pattern:
            confirmed.append(
                _make_match(
                    match_id=f"confirmed_{len(confirmed) + 1:03d}",
                    kind="confirmed",
                    pattern=single_pattern,
                    matched_tokens=[tokens[index]],
                    snippets=snippets,
                )
            )
            consumed_token_indexes.add(tokens[index].token_index)
            index += 1
            continue

        if index + 1 < len(tokens):
            pair_pattern = _pair_confirmed_pattern(tokens[index], tokens[index + 1])
            if pair_pattern:
                pair = [tokens[index], tokens[index + 1]]
                confirmed.append(
                    _make_match(
                        match_id=f"confirmed_{len(confirmed) + 1:03d}",
                        kind="confirmed",
                        pattern=pair_pattern,
                        matched_tokens=pair,
                        snippets=snippets,
                    )
                )
                consumed_token_indexes.update(token.token_index for token in pair)
                index += 2
                continue

        index += 1

    possible: list[Match] = []
    for token in tokens:
        if token.value in POSSIBLE_VALUES and token.token_index not in consumed_token_indexes:
            possible.append(
                _make_match(
                    match_id=f"possible_{len(possible) + 1:03d}",
                    kind="possible",
                    pattern="single_six_or_seven",
                    matched_tokens=[token],
                    snippets=snippets,
                )
            )

    return MatchResult(confirmed=confirmed, possible=possible)


def tokenize_transcript(snippets: list[TranscriptSnippet]) -> list[Token]:
    tokens: list[Token] = []
    for snippet_index, snippet in enumerate(snippets):
        text = html.unescape(snippet.text)
        for raw_match in TOKEN_RE.finditer(text):
            raw = raw_match.group(0)
            tokens.append(
                Token(
                    value=raw.lower(),
                    raw=raw,
                    start=snippet.start,
                    end=snippet.end,
                    snippet_index=snippet_index,
                    token_index=len(tokens),
                )
            )
    return tokens


def _single_confirmed_pattern(token: Token) -> str | None:
    if token.value == "67":
        return "numeric_67"
    return None


def _pair_confirmed_pattern(first: Token, second: Token) -> str | None:
    pair = (first.value, second.value)
    if pair == ("6", "7"):
        return "numeric_6_7"
    if pair == ("six", "seven"):
        return "six_seven"
    if pair == ("sixty", "seven"):
        return "sixty_seven"
    return None


def _make_match(
    match_id: str,
    kind: str,
    pattern: str,
    matched_tokens: list[Token],
    snippets: list[TranscriptSnippet],
) -> Match:
    snippet_start = min(token.snippet_index for token in matched_tokens)
    snippet_end = max(token.snippet_index for token in matched_tokens)
    transcript_text = " ".join(
        snippet.text.strip()
        for snippet in snippets[snippet_start : snippet_end + 1]
        if snippet.text.strip()
    )

    return Match(
        id=match_id,
        kind=kind,
        pattern=pattern,
        text=" ".join(token.raw for token in matched_tokens),
        transcript_text=transcript_text,
        start=min(token.start for token in matched_tokens),
        end=max(token.end for token in matched_tokens),
        token_start_index=matched_tokens[0].token_index,
        token_end_index=matched_tokens[-1].token_index,
        snippet_start_index=snippet_start,
        snippet_end_index=snippet_end,
    )
