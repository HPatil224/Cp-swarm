"""
Shared data schema for a competitive programming problem.

This is intentionally the FIRST thing built after the sandbox (phase 0/1
boundary) because every agent and the orchestrator state object depends on
this shape. Keep it stable; extend via optional fields rather than renaming.
"""

from dataclasses import dataclass, field


@dataclass
class SampleIO:
    input: str
    expected_output: str
    explanation: str | None = None


@dataclass
class Problem:
    """Raw problem as given by the user, parsed into structured form."""

    title: str
    statement: str  # full original text, kept verbatim for agent context

    # Constraints — these may start as None and get filled in by the
    # Mathematician's extraction step rather than requiring the user to
    # pre-parse them.
    n_max: int | None = None
    value_min: int | None = None
    value_max: int | None = None
    time_limit_seconds: float | None = None
    memory_limit_mb: int | None = None

    samples: list[SampleIO] = field(default_factory=list)

    # TODO(phase 1): add a from_text() classmethod that does light parsing
    # (e.g. regex for "1 <= N <= 10^5" style constraint lines) as a fallback/
    # cross-check against what the Mathematician extracts — useful for
    # catching cases where the LLM mis-reads a constraint.


@dataclass
class Approach:
    """Mathematician's structured output."""

    complexity_bound: str          # e.g. "O(N log N)"
    pattern: str                   # e.g. "two-pointer", "binary search on answer"
    pseudocode: str
    flagged_edge_cases: list[str] = field(default_factory=list)
    justification: str = ""        # why this bound/pattern fits the extracted constraints

    # Populated only on escalation re-invocations
    revises_previous: bool = False
    revision_reason: str | None = None
