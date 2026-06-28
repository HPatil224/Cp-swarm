"""
Shared mutable "case file" passed through the Mathematician -> Architect ->
Adversary loop. Agents read from / append to this rather than calling each
other directly — keeps each agent's interface narrow and makes the full
history inspectable for logging (logs/runs/<run_id>/).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from agents.adversary import AdversaryReport
from agents.architect import CodeVersion
from problems.schema import Approach, Problem


@dataclass
class IterationRecord:
    """One trip around the loop: a code version and what the Adversary did to it."""

    code_version: CodeVersion
    adversary_report: AdversaryReport | None = None  # None until Adversary has run
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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

    def to_transcript(self) -> str:
        """
        Renders the full state as a markdown transcript.
        """
        lines = []
        lines.append(f"# Swarm Run Transcript - {self.run_id}")
        lines.append(f"**Problem**: {self.problem.title}")
        lines.append(f"**Final Status**: {self.final_status or 'Running'}")
        lines.append(f"**Escalations**: {self.mathematician_escalations_used}")
        lines.append(f"**Retries**: {self.architect_retries_used}")
        lines.append("")
        
        lines.append("## Approach History")
        for idx, approach in enumerate(self.approach_history, 1):
            lines.append(f"### Approach {idx}")
            lines.append(f"- **Complexity Bound**: `{approach.complexity_bound}`")
            lines.append(f"- **Algorithmic Pattern**: `{approach.pattern}`")
            lines.append(f"- **Justification**: {approach.justification}")
            if approach.revises_previous:
                lines.append(f"- **Revises Previous**: Yes (Reason: {approach.revision_reason})")
            lines.append("- **Pseudocode**:")
            lines.append("```")
            lines.append(approach.pseudocode)
            lines.append("```")
            lines.append("")
            
        lines.append("## Execution Iterations")
        for idx, iter_rec in enumerate(self.iterations, 1):
            lines.append(f"### Iteration {idx} ({iter_rec.timestamp.isoformat()})")
            code = iter_rec.code_version
            lines.append(f"- **Version**: {code.version_number}")
            if code.disputes_approach:
                lines.append(f"- **Disputes Approach**: Yes (Reason: {code.dispute_reason})")
            else:
                lines.append("- **Implementation Notes**: " + (code.implementation_notes or "none"))
                lines.append("- **Source Code**:")
                lines.append("```cpp")
                lines.append(code.source_code)
                lines.append("```")
                
            report = iter_rec.adversary_report
            if report:
                lines.append(f"- **Adversary Result**: `{report.failure_type.value}`")
                lines.append(f"- **Notes**: {report.notes or 'none'}")
                if report.failing_test:
                    lines.append("- **Failing Test Case Input**:")
                    lines.append("```")
                    lines.append(report.failing_test.input_data)
                    lines.append("```")
                    lines.append(f"- **Failing Test Case Hypothesis**: {report.failing_test.hypothesis}")
                    if report.actual_output:
                        lines.append("- **Failing Test Case Actual Output**:")
                        lines.append("```")
                        lines.append(report.actual_output)
                        lines.append("```")
            lines.append("")
            
        return "\n".join(lines)
