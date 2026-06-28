"""
Phase 4-5 end-to-end test(s). Run the full orchestrator loop against the
sample problem in problems/samples/ and assert it reaches a final_status.

These are real API + real compilation tests — slow and not run on every
commit. Mark accordingly once CI is set up.
"""

import pytest


from problems.schema import Problem, SampleIO
from orchestrator import pipeline


def test_pipeline_solve_mocked_success(mocker):
    """
    Test the full orchestrator loop with mocked agent LLM responses.
    Verifies that the loop compiles code, runs it, evaluations match, and terminates on 'solved'.
    """
    mock_approach = """
<pattern>two-pointer</pattern>
<complexity_bound>O(N)</complexity_bound>
<justification>Fits N <= 10^5</justification>
<pseudocode>// pseudocode</pseudocode>
<edge_case>N = 1</edge_case>
"""
    mock_cpp_code = """
<cpp_code>
```cpp
#include <iostream>
int main() {
    int n, k;
    if (std::cin >> n >> k) {
        std::cout << 5;
    }
    return 0;
}
```
</cpp_code>
<implementation_notes>notes</implementation_notes>
"""
    mock_tests = """
<reference_source>
```cpp
#include <iostream>
int main() {
    int n, k;
    if (std::cin >> n >> k) {
        std::cout << 5;
    }
    return 0;
}
```
</reference_source>
<test_case>
<input>5 1
1 -100 2 3 -100</input>
<hypothesis>test</hypothesis>
<expected_output>5</expected_output>
</test_case>
"""
    from agents.mathematician import Mathematician
    from agents.architect import Architect
    from agents.adversary import Adversary
    
    mocker.patch.object(Mathematician, "call", return_value=mock_approach)
    mocker.patch.object(Architect, "call", return_value=mock_cpp_code)
    mocker.patch.object(Adversary, "call", return_value=mock_tests)
    
    problem = Problem(
        title="Maximum Subarray Sum with At Most K Removals",
        statement="Solve subarray problem.",
        samples=[SampleIO(input="5 1\n1 -100 2 3 -100", expected_output="5")]
    )
    
    state = pipeline.solve(problem)
    assert state.final_status == "solved"
    assert len(state.iterations) == 1
    assert state.mathematician_escalations_used == 0
    assert state.architect_retries_used == 0


# TODO(phase 5): once this passes for one problem, extend into a small
# benchmark runner over problems/samples/ (or a separate benchmark/ dir of
# pulled Codeforces/AtCoder problems) tracking solve rate and
# iterations-to-pass per problem, per the project plan's Phase 5 metrics.
