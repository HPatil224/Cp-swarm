"""
Phase 1-3 tests for individual agents, with the LLM call mocked out so these
run fast/deterministically and don't burn API credits on every test run.

TODO: as each agent's call()/parsing logic is implemented, add a
corresponding test here that mocks BaseAgent.call to return a fixed
response string and asserts the parsed dataclass is correct. Keep one
"real" (unmocked, marked @pytest.mark.live) smoke test per agent for
occasional manual runs against the actual API.
"""

import pytest


def test_mathematician_extracts_approach_from_mocked_response(mocker):
    from agents.mathematician import Mathematician
    from problems.schema import Problem
    from pathlib import Path
    
    math = Mathematician(model="mock-model", prompts_dir=Path("config/prompts"))
    
    mock_response = """
Some thinking or conversational text...
<pattern>binary search on answer</pattern>
<complexity_bound>O(N log max_val)</complexity_bound>
<justification>Since N <= 10^5 and max_val <= 10^9, binary search on the answer fits within 1s limit.</justification>
<pseudocode>
int low = 0, high = 1e9;
while(low <= high) { ... }
</pseudocode>
<edge_case>N = 1</edge_case>
<edge_case>overflow with high + low</edge_case>
"""
    mocker.patch.object(math, "call", return_value=mock_response)
    
    problem = Problem(
        title="Test Problem",
        statement="A simple test statement.",
        samples=[]
    )
    
    approach = math.extract_approach(problem)
    
    assert approach.pattern == "binary search on answer"
    assert approach.complexity_bound == "O(N log max_val)"
    assert approach.justification.startswith("Since N <= 10^5")
    assert "int low = 0" in approach.pseudocode
    assert approach.flagged_edge_cases == ["N = 1", "overflow with high + low"]


def test_architect_produces_code_from_mocked_response(mocker):
    from agents.architect import Architect
    from problems.schema import Problem, Approach
    from pathlib import Path
    
    arch = Architect(model="mock-model", prompts_dir=Path("config/prompts"))
    
    mock_response = """
<cpp_code>
```cpp
#include <iostream>
int main() { return 0; }
```
</cpp_code>
<implementation_notes>
Implemented a basic main function.
</implementation_notes>
"""
    mocker.patch.object(arch, "call", return_value=mock_response)
    
    problem = Problem(
        title="Test Problem",
        statement="A simple test statement.",
        samples=[]
    )
    approach = Approach(
        complexity_bound="O(1)",
        pattern="test-pattern",
        pseudocode="// pseudocode",
        flagged_edge_cases=[]
    )
    
    version = arch.implement(problem, approach)
    
    assert version.source_code == "#include <iostream>\nint main() { return 0; }"
    assert version.implementation_notes == "Implemented a basic main function."
    assert version.version_number == 1
    assert not version.disputes_approach


def test_adversary_generates_tests_from_mocked_response(mocker):
    from agents.adversary import Adversary
    from agents.architect import CodeVersion
    from problems.schema import Problem
    from pathlib import Path
    
    adv = Adversary(model="mock-model", prompts_dir=Path("config/prompts"))
    
    mock_response = """
<reference_source>
```cpp
#include <iostream>
int main() { return 0; }
```
</reference_source>
<test_case>
<input>5 1
1 -100 2 3 -100</input>
<hypothesis>Tests removal behavior with standard array elements</hypothesis>
<expected_output>5</expected_output>
</test_case>
<test_case>
<input>4 0
-1 -2 -3 -4</input>
<hypothesis>Tests all negative elements with no removals</hypothesis>
<expected_output>-1</expected_output>
</test_case>
"""
    mocker.patch.object(adv, "call", return_value=mock_response)
    
    problem = Problem(
        title="Test Problem",
        statement="A simple test statement.",
        samples=[]
    )
    code = CodeVersion(source_code="#include <iostream>\nint main() { return 0; }")
    
    tests = adv.generate_tests(problem, code)
    
    assert adv.reference_source == "#include <iostream>\nint main() { return 0; }"
    assert len(tests) == 2
    assert tests[0].input_data == "5 1\n1 -100 2 3 -100"
    assert tests[0].hypothesis == "Tests removal behavior with standard array elements"
    assert tests[0].expected_output == "5"
    assert tests[1].input_data == "4 0\n-1 -2 -3 -4"
    assert tests[1].expected_output == "-1"
