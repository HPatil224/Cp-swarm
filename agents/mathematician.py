"""
Agent 1: The Mathematician.

See config/prompts/mathematician.md for the full role/behavior spec —
keep that file and this implementation in sync.
"""


import re
from agents.base_agent import BaseAgent
from problems.schema import Approach, Problem


def _parse_xml_tag(text: str, tag: str) -> str:
    pattern = f"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1).strip() if match else ""


def _parse_xml_list(text: str, tag: str) -> list[str]:
    pattern = f"<{tag}>(.*?)</{tag}>"
    return [m.strip() for m in re.findall(pattern, text, re.DOTALL)]


class Mathematician(BaseAgent):
    agent_name = "mathematician"

    def system_prompt_filename(self) -> str:
        return "mathematician.md"

    def extract_approach(self, problem: Problem, run_id: str = "default") -> Approach:
        """
        First call for a fresh problem: no prior failure context.
        Generates prompt, calls Claude, and parses the response.
        """
        user_message = f"""
Analyze the following competitive programming problem:

Title: {problem.title}

Statement:
{problem.statement}

Please extract the approach and structure it using these XML tags:
1. Enclose the name of the algorithmic pattern in <pattern>...</pattern> (e.g., <pattern>segment tree</pattern>).
2. Enclose the derived worst-case complexity bound in <complexity_bound>...</complexity_bound> (e.g., <complexity_bound>O(N log N)</complexity_bound>).
3. Enclose a brief mathematical/logical justification matching the constraints to the pattern and complexity in <justification>...</justification>.
4. Enclose the language-agnostic pseudocode of the algorithm in <pseudocode>...</pseudocode>.
5. For each critical edge case to watch out for, enclose it in a separate <edge_case>...</edge_case> tag (e.g., <edge_case>N = 1</edge_case>).

Make sure you wrap all your responses inside the requested XML tags so they can be parsed programmatically.
"""
        raw_response = self.call(user_message, run_id=run_id)
        
        complexity_bound = _parse_xml_tag(raw_response, "complexity_bound")
        pattern = _parse_xml_tag(raw_response, "pattern")
        pseudocode = _parse_xml_tag(raw_response, "pseudocode")
        justification = _parse_xml_tag(raw_response, "justification")
        edge_cases = _parse_xml_list(raw_response, "edge_case")
        
        # Fallback to <edge_cases> tag containing bulleted items
        if not edge_cases:
            edge_cases_block = _parse_xml_tag(raw_response, "edge_cases")
            if edge_cases_block:
                edge_cases = [line.strip("- ").strip() for line in edge_cases_block.split("\n") if line.strip()]
                
        return Approach(
            complexity_bound=complexity_bound or "O(N)",
            pattern=pattern or "unknown",
            pseudocode=pseudocode or "",
            justification=justification,
            flagged_edge_cases=edge_cases
        )

    def revise_approach(
        self,
        problem: Problem,
        previous_approach: Approach,
        adversary_failure_report: "AdversaryReport",  # noqa: F821
        run_id: str = "default",
    ) -> Approach:
        """
        Escalation call: Adversary flagged likely_wrong_approach=True.
        """
        user_message = f"""
We attempted to solve the following problem:

Title: {problem.title}
Statement:
{problem.statement}

The previous approach proposed was:
Algorithmic Pattern: {previous_approach.pattern}
Complexity Bound: {previous_approach.complexity_bound}
Pseudocode:
{previous_approach.pseudocode}

However, it failed against the adversary's stress tests. Here is the failure report:
{adversary_failure_report}

Please decide:
1. Is this a CODE bug (the math/approach was correct, but the implementation was wrong)?
2. Or is it an APPROACH bug (the math/approach itself is wrong or does not meet the complexity/correctness requirements)?

If it is an APPROACH bug, please formulate a new correct approach.
Represent your decision and the revised approach using these XML tags:
- Enclose whether you are revising the approach (true/false) in <revises_previous>...</revises_previous>.
- Enclose the reason for the revision (or why the previous approach failed) in <revision_reason>...</revision_reason>.
- Enclose the new algorithmic pattern in <pattern>...</pattern>.
- Enclose the new complexity bound in <complexity_bound>...</complexity_bound>.
- Enclose the justification in <justification>...</justification>.
- Enclose the new pseudocode in <pseudocode>...</pseudocode>.
- Enclose any new edge cases in separate <edge_case>...</edge_case> tags.
"""
        raw_response = self.call(user_message, run_id=run_id)
        
        revises_prev_str = _parse_xml_tag(raw_response, "revises_previous").lower()
        revises_previous = "true" in revises_prev_str
        revision_reason = _parse_xml_tag(raw_response, "revision_reason")
        
        complexity_bound = _parse_xml_tag(raw_response, "complexity_bound")
        pattern = _parse_xml_tag(raw_response, "pattern")
        pseudocode = _parse_xml_tag(raw_response, "pseudocode")
        justification = _parse_xml_tag(raw_response, "justification")
        edge_cases = _parse_xml_list(raw_response, "edge_case")
        
        if not edge_cases:
            edge_cases_block = _parse_xml_tag(raw_response, "edge_cases")
            if edge_cases_block:
                edge_cases = [line.strip("- ").strip() for line in edge_cases_block.split("\n") if line.strip()]
                
        return Approach(
            complexity_bound=complexity_bound or previous_approach.complexity_bound,
            pattern=pattern or previous_approach.pattern,
            pseudocode=pseudocode or previous_approach.pseudocode,
            justification=justification or previous_approach.justification,
            flagged_edge_cases=edge_cases or previous_approach.flagged_edge_cases,
            revises_previous=revises_previous,
            revision_reason=revision_reason if revises_previous else None
        )
