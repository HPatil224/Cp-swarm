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
    """
    return report.likely_wrong_approach and state.mathematician_escalations_used < settings.policy.max_mathematician_escalations


def should_retry_architect(report: AdversaryReport, state: RunState) -> bool:
    """
    True if failure is a code-level bug (not likely_wrong_approach) AND
    architect_retries_used < settings.policy.max_architect_retries.
    """
    return not report.likely_wrong_approach and state.architect_retries_used < settings.policy.max_architect_retries


def is_solved(report: AdversaryReport) -> bool:
    return report.passed


def give_up_reason(state: RunState) -> str:
    """
    Determines the final status label when retries are exhausted.
    """
    if state.mathematician_escalations_used >= settings.policy.max_mathematician_escalations:
        return "exhausted_escalations"
    else:
        return "exhausted_retries"
