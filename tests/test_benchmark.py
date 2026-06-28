from pathlib import Path
from benchmark import parse_problem_file


def test_benchmark_parser_two_sum():
    filepath = Path("problems/benchmarks/two_sum.txt")
    problem = parse_problem_file(filepath)
    
    assert problem.title == "Two Sum"
    assert "You are given an array of N integers" in problem.statement
    assert problem.n_max == 100000
    assert problem.time_limit_seconds == 2.0
    assert problem.memory_limit_mb == 256
    
    assert len(problem.samples) == 3
    assert problem.samples[0].input == "4 9\n2 7 11 15\n"
    assert problem.samples[0].expected_output == "1 2"
    assert problem.samples[1].input == "3 6\n3 2 4\n"
    assert problem.samples[1].expected_output == "2 3"
    assert problem.samples[2].input == "3 6\n3 3 5\n"
    assert problem.samples[2].expected_output == "-1"


def test_benchmark_parser_prefix_sum():
    filepath = Path("problems/benchmarks/prefix_sum.txt")
    problem = parse_problem_file(filepath)
    
    assert problem.title == "Range Sum Queries"
    assert problem.n_max == 100000
    assert len(problem.samples) == 1
    assert problem.samples[0].input == "5 3\n1 -2 3 -4 5\n1 3\n2 4\n1 5\n"
    assert problem.samples[0].expected_output == "2\n-3\n3"
