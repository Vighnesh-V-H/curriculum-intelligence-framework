"""Deterministic text and graph helpers used by curriculum verification.

The helpers in this module are intentionally dependency-free so verification
stays reproducible and testable without an external NLP or graph service.
"""

from __future__ import annotations

import re
import uuid
from collections import deque
from difflib import SequenceMatcher

STOPWORDS = frozenset(
    {
        "about",
        "above",
        "after",
        "again",
        "against",
        "also",
        "among",
        "analysis",
        "analyze",
        "and",
        "apply",
        "applies",
        "application",
        "are",
        "basic",
        "because",
        "been",
        "before",
        "being",
        "between",
        "both",
        "can",
        "concept",
        "concepts",
        "course",
        "courses",
        "demonstrate",
        "describe",
        "design",
        "develop",
        "different",
        "does",
        "each",
        "explain",
        "for",
        "from",
        "fundamental",
        "fundamentals",
        "has",
        "have",
        "how",
        "identify",
        "include",
        "including",
        "into",
        "introduce",
        "introduction",
        "its",
        "knowledge",
        "more",
        "most",
        "other",
        "outcome",
        "outcomes",
        "over",
        "principle",
        "principles",
        "student",
        "students",
        "such",
        "technique",
        "techniques",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "through",
        "understand",
        "using",
        "various",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "within",
        "would",
    }
)

PROGRESSION_MARKERS = (
    "advanced",
    "advance",
    "capstone",
    "project",
    "seminar",
    "internship",
    "special topics",
    "ii",
    "iii",
    "iv",
)

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ies"):
        token = f"{token[:-3]}y"
    elif len(token) > 5 and token.endswith("ing"):
        token = token[:-3]
    elif len(token) > 4 and token.endswith("ed"):
        token = token[:-2]
    elif len(token) > 4 and token.endswith("es"):
        token = token[:-2]
    elif len(token) > 3 and token.endswith("s"):
        token = token[:-1]
    if len(token) > 4 and token[-1] == token[-2]:
        token = token[:-1]
    if len(token) > 4 and token.endswith("e"):
        token = token[:-1]
    return token


def tokenize(text: str | None) -> set[str]:
    if not text:
        return set()
    tokens: set[str] = set()
    for raw in _WORD_PATTERN.findall(text.lower()):
        if len(raw) < 3 or raw in STOPWORDS:
            continue
        token = _stem(raw)
        if len(token) >= 3 and token not in STOPWORDS:
            tokens.add(token)
    return tokens


def course_topic_tokens(
    course_name: str,
    description: str | None,
    syllabus: str | None,
    outcome_descriptions: list[str],
) -> set[str]:
    """Build a topic profile from the curriculum evidence for one course."""

    tokens = tokenize(course_name)
    tokens.update(tokenize(description))
    tokens.update(tokenize(syllabus))
    for description_text in outcome_descriptions:
        tokens.update(tokenize(description_text))
    return tokens


def topic_similarity(
    left: set[str],
    right: set[str],
) -> tuple[float, list[str]]:
    if not left or not right:
        return 0.0, []
    shared = sorted(left & right)
    if not shared:
        return 0.0, []
    jaccard = len(shared) / len(left | right)
    containment = len(shared) / min(len(left), len(right))
    score = round((0.6 * jaccard) + (0.4 * containment), 3)
    return score, shared


def title_similarity(left: str, right: str) -> float:
    left_normalized = " ".join(_WORD_PATTERN.findall(left.lower()))
    right_normalized = " ".join(_WORD_PATTERN.findall(right.lower()))
    if not left_normalized or not right_normalized:
        return 0.0
    return round(
        SequenceMatcher(None, left_normalized, right_normalized).ratio(),
        3,
    )


def course_number(course_code: str) -> int | None:
    digits = "".join(character for character in course_code if character.isdigit())
    return int(digits) if digits else None


def has_progression_marker(course_name: str, course_code: str) -> bool:
    lowered = course_name.lower()
    if any(marker in lowered for marker in PROGRESSION_MARKERS):
        return True
    return False


def build_upstream_reachability(
    edges: list[tuple[uuid.UUID, uuid.UUID]],
) -> dict[uuid.UUID, set[uuid.UUID]]:
    """Return every transitive prerequisite for each course.

    Edges point from a prerequisite to its target. Cycles are tolerated by
    stopping recursion when a node is already on the current path.
    """

    reverse: dict[uuid.UUID, list[uuid.UUID]] = {}
    for prerequisite, target in edges:
        reverse.setdefault(target, []).append(prerequisite)
    for parents in reverse.values():
        parents.sort(key=str)

    memo: dict[uuid.UUID, set[uuid.UUID]] = {}

    def visit(node: uuid.UUID, visiting: frozenset[uuid.UUID]) -> set[uuid.UUID]:
        if node in memo:
            return memo[node]
        if node in visiting:
            return set()
        upstream: set[uuid.UUID] = set()
        next_visiting = visiting | {node}
        for parent in reverse.get(node, []):
            upstream.add(parent)
            upstream.update(visit(parent, next_visiting))
        memo[node] = upstream
        return upstream

    for node in {node for edge in edges for node in edge}:
        visit(node, frozenset())
    return memo


def longest_prerequisite_chain(
    edges: list[tuple[uuid.UUID, uuid.UUID]],
) -> list[uuid.UUID]:
    """Return a longest prerequisite path, ignoring cycle-closing edges."""

    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {}
    nodes: set[uuid.UUID] = set()
    for prerequisite, target in edges:
        adjacency.setdefault(prerequisite, []).append(target)
        nodes.update((prerequisite, target))
    for targets in adjacency.values():
        targets.sort(key=str)

    memo: dict[uuid.UUID, list[uuid.UUID]] = {}
    visiting: set[uuid.UUID] = set()

    def visit(node: uuid.UUID) -> list[uuid.UUID]:
        if node in memo:
            return memo[node]
        if node in visiting:
            return [node]
        visiting.add(node)
        best: list[uuid.UUID] = [node]
        for target in adjacency.get(node, []):
            candidate = [node, *visit(target)]
            if len(candidate) > len(best):
                best = candidate
        visiting.discard(node)
        memo[node] = best
        return best

    longest: list[uuid.UUID] = []
    for node in sorted(nodes, key=str):
        candidate = visit(node)
        if len(candidate) > len(longest):
            longest = candidate
    return longest


def transitive_redundant_edges(
    edges: list[tuple[uuid.UUID, uuid.UUID]],
) -> list[tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]]:
    """Find direct edges already implied by a longer prerequisite path."""

    adjacency: dict[uuid.UUID, list[uuid.UUID]] = {}
    for prerequisite, target in edges:
        adjacency.setdefault(prerequisite, []).append(target)
    for targets in adjacency.values():
        targets.sort(key=str)

    redundant: list[tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]] = []
    for prerequisite, target in sorted(edges, key=lambda edge: (str(edge[0]), str(edge[1]))):
        parent: dict[uuid.UUID, uuid.UUID | None] = {prerequisite: None}
        queue: deque[uuid.UUID] = deque([prerequisite])
        found: uuid.UUID | None = None
        while queue and found is None:
            node = queue.popleft()
            for neighbour in adjacency.get(node, []):
                if (node, neighbour) == (prerequisite, target):
                    continue
                if neighbour in parent:
                    continue
                parent[neighbour] = node
                if neighbour == target:
                    found = node
                    break
                queue.append(neighbour)
        if found is None:
            continue
        path: list[uuid.UUID] = []
        cursor: uuid.UUID | None = found
        while cursor is not None:
            path.append(cursor)
            cursor = parent[cursor]
        path.reverse()
        path.append(target)
        redundant.append((prerequisite, target, path))
    return redundant


def keyword_present(text: str, keyword: str) -> bool:
    """Match a keyword as a word/phrase, tolerating simple plural forms."""

    normalized_text = " ".join(text.lower().split())
    normalized_keyword = " ".join(keyword.lower().split())
    if not normalized_keyword:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?:s|es)?(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None
