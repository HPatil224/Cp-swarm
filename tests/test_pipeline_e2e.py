"""
Phase 4-5 end-to-end test(s). Run the full orchestrator loop against the
sample problem in problems/samples/ and assert it reaches a final_status.

These are real API + real compilation tests — slow and not run on every
commit. Mark accordingly once CI is set up.
"""

import pytest


@pytest.mark.skip(reason="orchestrator.pipeline.solve not yet implemented (phase 4)")
@pytest.mark.live
def test_solve_sample_problem_end_to_end():
    ...


# TODO(phase 5): once this passes for one problem, extend into a small
# benchmark runner over problems/samples/ (or a separate benchmark/ dir of
# pulled Codeforces/AtCoder problems) tracking solve rate and
# iterations-to-pass per problem, per the project plan's Phase 5 metrics.
