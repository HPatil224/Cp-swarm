"""
Retry / escalation policy decisions, kept separate from pipeline.py so the
"when do we give up or escalate" logic is easy to find, read, and unit test
in isolation (tests/test_pipeline_e2e.py can mock this module entirely).
"""

from agents.adversary import AdversaryReport
from config.settings import settings
from orchestrator.state import RunState


def should_escalate_to_mathematician(report: AdversaryReport, state: RunState) -> bool:
    """
    True if the Adversary flagged the approach itself as wrong AND we
    haven't exhausted mathematician_escalations.

    TODO(phase 4): implement. Note: even if likely_wrong_approach=True,
    should still respect max_mathematician_escalations — if we've already
    escalated twice and it's still failing, that's a "give up and report"
    situation, not infinite escalation.
    """
    raise NotImplementedError


def should_retry_architect(report: AdversaryReport, state: RunState) -> bool:
    """
    True if failure is a code-level bug (not likely_wrong_approach) AND
    architect_retries_used < max_architect_retries.

    TODO(phase 4): implement.
    """
    raise NotImplementedError


def is_solved(report: AdversaryReport) -> bool:
    return report.passed


def should_give_up(state: RunState) -> bool:
    """
    True if we've exhausted both architect retries (for the current
    approach) and mathematician escalations.

    TODO(phase 4): implement. This determines state.final_status =
    "exhausted_retries" vs "exhausted_escalations" for the final report.
    """
    raise NotImplementedError
