"""
Agent 2: The C++ Architect.

See config/prompts/architect.md for the full role/behavior spec.
"""

import re
from dataclasses import dataclass

from agents.base_agent import BaseAgent
from problems.schema import Approach, Problem


@dataclass
class CodeVersion:
    source_code: str
    implementation_notes: str = ""
    version_number: int = 1
    # Set True if the Architect itself pushes back on the approach rather
    # than implementing it — orchestrator should treat this as a signal to
    # escalate to the Mathematician rather than treating it as a normal
    # compile/runtime failure.
    disputes_approach: bool = False
    dispute_reason: str | None = None


def _parse_xml_tag(text: str, tag: str) -> str:
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


class Architect(BaseAgent):
    agent_name = "architect"

    def system_prompt_filename(self) -> str:
        return "architect.md"

    def implement(self, problem: Problem, approach: Approach, run_id: str = "default") -> CodeVersion:
        """
        First implementation attempt for a given Approach.
        """
        edge_cases_str = "\n".join(f"- {ec}" for ec in approach.flagged_edge_cases)
        user_message = f"""
Implement a C++ solution for the following competitive programming problem:

Title: {problem.title}
Statement:
{problem.statement}

The approach you must follow is:
Algorithmic Pattern: {approach.pattern}
Complexity Bound: {approach.complexity_bound}
Pseudocode:
{approach.pseudocode}

Critical Edge Cases to consider:
{edge_cases_str}

If you dispute the approach and believe it is fundamentally incorrect or does not meet complexity/correctness requirements, describe your reasoning within <dispute_reason>...</dispute_reason> tags.

Otherwise, please output your implementation using these XML tags:
1. Enclose your complete, compilable C++ source code in <cpp_code>...</cpp_code>.
2. Enclose any brief implementation notes in <implementation_notes>...</implementation_notes>.

Make sure you wrap all your responses inside the requested XML tags so they can be parsed programmatically.
"""
        raw_response = self.call(user_message, run_id=run_id)
        
        dispute_reason = _parse_xml_tag(raw_response, "dispute_reason")
        if dispute_reason:
            return CodeVersion(
                source_code="",
                disputes_approach=True,
                dispute_reason=dispute_reason
            )
            
        cpp_code = _parse_xml_tag(raw_response, "cpp_code")
        if "```cpp" in cpp_code:
            cpp_code = cpp_code.split("```cpp")[1].split("```")[0].strip()
        elif "```" in cpp_code:
            cpp_code = cpp_code.split("```")[1].split("```")[0].strip()
            
        implementation_notes = _parse_xml_tag(raw_response, "implementation_notes")
        
        return CodeVersion(
            source_code=cpp_code,
            implementation_notes=implementation_notes,
            version_number=1
        )

    def fix(
        self,
        problem: Problem,
        approach: Approach,
        previous_version: CodeVersion,
        failure_report: "AdversaryReport",  # noqa: F821
        run_id: str = "default",
    ) -> CodeVersion:
        """
        Retry call after an Adversary failure (TLE/MLE/RTE/WA/compile error).
        """
        user_message = f"""
We are solving the following problem:
Title: {problem.title}
Statement:
{problem.statement}

Our current C++ source code is:
```cpp
{previous_version.source_code}
```

The code failed during execution against the adversary's stress tests. Here is the failure report:
{failure_report}

Please fix the bug in the code. Maintain the required approach:
Algorithmic Pattern: {approach.pattern}
Complexity Bound: {approach.complexity_bound}

If you believe the approach itself is wrong and needs to be revised by the Mathematician, write your reasoning in <dispute_reason>...</dispute_reason> tags.

Otherwise, please output your updated implementation using these XML tags:
1. Enclose your complete, compilable C++ source code in <cpp_code>...</cpp_code>.
2. Enclose any brief implementation notes explaining the fix in <implementation_notes>...</implementation_notes>.
"""
        raw_response = self.call(user_message, run_id=run_id)
        
        dispute_reason = _parse_xml_tag(raw_response, "dispute_reason")
        if dispute_reason:
            return CodeVersion(
                source_code="",
                disputes_approach=True,
                dispute_reason=dispute_reason,
                version_number=previous_version.version_number + 1
            )
            
        cpp_code = _parse_xml_tag(raw_response, "cpp_code")
        if "```cpp" in cpp_code:
            cpp_code = cpp_code.split("```cpp")[1].split("```")[0].strip()
        elif "```" in cpp_code:
            cpp_code = cpp_code.split("```")[1].split("```")[0].strip()
            
        implementation_notes = _parse_xml_tag(raw_response, "implementation_notes")
        
        return CodeVersion(
            source_code=cpp_code,
            implementation_notes=implementation_notes,
            version_number=previous_version.version_number + 1
        )
