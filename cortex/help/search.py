"""Fuzzy search for help content."""

import difflib
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .content import HelpEntry, HELP_ENTRIES, HelpCategory


@dataclass
class SearchResult:
    """A search result with relevance score."""

    entry: HelpEntry
    score: float
    match_type: str  # 'exact', 'partial', 'keyword', 'fuzzy'


def calculate_similarity(query: str, text: str) -> float:
    """
    Calculate similarity between query and text.

    Uses difflib's SequenceMatcher for fuzzy matching.

    Args:
        query: Search query
        text: Text to match against

    Returns:
        Similarity score between 0.0 and 1.0
    """
    query = query.lower()
    text = text.lower()

    # Exact match
    if query in text:
        return 1.0

    # Word match
    query_words = set(query.split())
    text_words = set(text.split())
    if query_words and query_words.issubset(text_words):
        return 0.9

    # Fuzzy match
    return difflib.SequenceMatcher(None, query, text).ratio()


def search_entries(
    query: str,
    entries: Optional[List[HelpEntry]] = None,
    category: Optional[HelpCategory] = None,
    min_score: float = 0.3,
    max_results: int = 10,
) -> List[SearchResult]:
    """
    Search help entries for matching content.

    Args:
        query: Search query
        entries: Entries to search (default: all entries)
        category: Filter by category (optional)
        min_score: Minimum relevance score (0.0-1.0)
        max_results: Maximum number of results

    Returns:
        List of SearchResult sorted by relevance
    """
    if entries is None:
        entries = HELP_ENTRIES

    if category:
        entries = [e for e in entries if e.category == category]

    results = []
    query_lower = query.lower()

    for entry in entries:
        best_score = 0.0
        match_type = "fuzzy"

        # Check command (highest weight)
        cmd_score = calculate_similarity(query_lower, entry.command.lower())
        if cmd_score > best_score:
            best_score = cmd_score
            match_type = "exact" if cmd_score == 1.0 else "partial"

        # Check short description
        short_score = calculate_similarity(query_lower, entry.short_desc.lower()) * 0.8
        if short_score > best_score:
            best_score = short_score
            match_type = "partial"

        # Check long description
        long_score = calculate_similarity(query_lower, entry.long_desc.lower()) * 0.6
        if long_score > best_score:
            best_score = long_score
            match_type = "partial"

        # Check keywords
        for keyword in entry.keywords:
            keyword_score = calculate_similarity(query_lower, keyword.lower())
            if keyword_score > best_score:
                best_score = keyword_score * 0.9  # Keywords slightly lower than command
                match_type = "keyword"

        # Check examples
        for example in entry.examples:
            example_score = calculate_similarity(query_lower, example.lower()) * 0.5
            if example_score > best_score:
                best_score = example_score
                match_type = "fuzzy"

        if best_score >= min_score:
            results.append(SearchResult(entry=entry, score=best_score, match_type=match_type))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    return results[:max_results]


def search_by_keyword(keyword: str, entries: Optional[List[HelpEntry]] = None) -> List[HelpEntry]:
    """
    Search entries by keyword.

    Args:
        keyword: Keyword to search for
        entries: Entries to search (default: all entries)

    Returns:
        List of matching entries
    """
    if entries is None:
        entries = HELP_ENTRIES

    keyword = keyword.lower()
    results = []

    for entry in entries:
        if keyword in [k.lower() for k in entry.keywords]:
            results.append(entry)

    return results


def suggest_commands(partial: str, max_suggestions: int = 5) -> List[str]:
    """
    Suggest commands based on partial input.

    Args:
        partial: Partial command input
        max_suggestions: Maximum number of suggestions

    Returns:
        List of suggested commands
    """
    partial = partial.lower().strip()
    if partial.startswith("/"):
        partial = partial[1:]

    suggestions = []
    for entry in HELP_ENTRIES:
        cmd = entry.command.lower()
        if cmd.startswith("/"):
            cmd = cmd[1:]

        if cmd.startswith(partial):
            suggestions.append(entry.command)

    # Sort by length (shorter = more likely intended)
    suggestions.sort(key=len)

    return suggestions[:max_suggestions]


def get_related_entries(entry: HelpEntry) -> List[HelpEntry]:
    """
    Get related help entries.

    Args:
        entry: The entry to find related entries for

    Returns:
        List of related entries
    """
    related = []
    related_commands = [r.lower() for r in entry.related]

    for e in HELP_ENTRIES:
        cmd = e.command.lower()
        if cmd.startswith("/"):
            cmd = cmd[1:]

        for r in related_commands:
            if r.startswith("/"):
                r = r[1:]
            if cmd == r:
                related.append(e)
                break

    return related
