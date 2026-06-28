"""
Shared mutable "case file" passed through the Mathematician -> Architect ->
Adversary loop. Agents read from / append to this rather than calling each
other directly — keeps each agent's interface narrow and makes the full
history inspectable for logging (logs/runs/<run_id>/).
"""

from dataclasses import dataclass, field
from datetime import datetime

from agents.adversary import AdversaryReport
from agents.architect import CodeVersion
from problems.schema import Approach, Problem


@dataclass
class IterationRecord:
    """One trip around the loop: a code version and what the Adversary did to it."""

    code_version: CodeVersion
    adversary_report: AdversaryReport | None = None  # None until Adversary has run
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class RunState:
    run_id: str
    problem: Problem

    current_approach: Approach | None = None
    approach_history: list[Approach] = field(default_factory=list)  # populated on each escalation

    iterations: list[IterationRecord] = field(default_factory=list)

    mathematician_escalations_used: int = 0
    architect_retries_used: int = 0  # resets to 0 each time we escalate to a new approach

    final_status: str | None = None  # "solved" | "exhausted_retries" | "exhausted_escalations"

    def latest_code(self) -> CodeVersion | None:
        return self.iterations[-1].code_version if self.iterations else None

    def latest_report(self) -> AdversaryReport | None:
        return self.iterations[-1].adversary_report if self.iterations else None

    # TODO(phase 4): add a to_transcript() method that renders this whole
    # object as a readable markdown log for logs/runs/<run_id>/transcript.md —
    # this is the artifact that makes watching the swarm work interesting.
