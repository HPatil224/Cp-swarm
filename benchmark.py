import os
import sys
import argparse
import logging
import re
import datetime
from pathlib import Path
from rich.console import Console
from rich.table import Table

# Add project root to python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from problems.schema import Problem, SampleIO
from orchestrator import pipeline

console = Console()


def parse_problem_file(filepath: Path) -> Problem:
    """
    Parses a competitive programming problem statement text file.
    """
    content = filepath.read_text(encoding="utf-8")
    
    title_match = re.search(r"Title:\s*(.*)", content)
    title = title_match.group(1).strip() if title_match else filepath.stem.replace("_", " ").title()
    
    statement_match = re.search(
        r"Statement:\s*(.*?)(?=\nConstraints:|\nInput format:|\nOutput format:|\nSample Input 1:|\Z)",
        content,
        re.DOTALL
    )
    statement = statement_match.group(1).strip() if statement_match else ""
    
    n_max = None
    time_limit = 2.0
    memory_limit = 256
    
    constraints_match = re.search(
        r"Constraints:\s*(.*?)(?=\nInput format:|\nOutput format:|\nSample Input 1:|\Z)",
        content,
        re.DOTALL
    )
    if constraints_match:
        constraints_text = constraints_match.group(1)
        time_match = re.search(r"Time limit:\s*([\d\.]+)\s*seconds?", constraints_text, re.IGNORECASE)
        if time_match:
            time_limit = float(time_match.group(1))
        mem_match = re.search(r"Memory limit:\s*(\d+)\s*(?:MB|megabytes)", constraints_text, re.IGNORECASE)
        if mem_match:
            memory_limit = int(mem_match.group(1))
            
        n_match = re.search(r"[1\d\s<=]*N\s*<=\s*([0-9\^\*\t ]+)", constraints_text)
        if n_match:
            try:
                expr = n_match.group(1).replace("^", "**").strip()
                n_max = eval(expr)
            except Exception:
                pass
                
    samples = []
    sample_input_matches = list(re.finditer(r"Sample Input\s*(\d+):\s*(.*?)(?=\nSample Output\s*\1:|\Z)", content, re.DOTALL))
    for m in sample_input_matches:
        num = m.group(1)
        sample_in = m.group(2).strip()
        output_match = re.search(rf"Sample Output\s*{num}:\s*(.*?)(?=\nSample Input|\nSample explanation|\nSample Output|\Z)", content, re.DOTALL)
        if output_match:
            sample_out = output_match.group(1).strip()
            samples.append(SampleIO(input=sample_in + "\n", expected_output=sample_out))
            
    return Problem(
        title=title,
        statement=statement,
        n_max=n_max,
        time_limit_seconds=time_limit,
        memory_limit_mb=memory_limit,
        samples=samples
    )


def run_benchmark():
    parser = argparse.ArgumentParser(description="Swarm Solver Benchmark Runner")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of problems to run")
    args = parser.parse_args()
    
    # Warn if API key is placeholders
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "placeholder_key":
        console.print("[bold red]Warning: ANTHROPIC_API_KEY is not configured. Real LLM calls will fail.[/bold red]")
        
    bench_dir = Path(__file__).resolve().parent / "problems" / "benchmarks"
    if not bench_dir.exists():
        console.print(f"[bold red]Benchmark directory {bench_dir} does not exist.[/bold red]")
        sys.exit(1)
        
    files = sorted(list(bench_dir.glob("*.txt")))
    if args.limit:
        files = files[:args.limit]
        
    if not files:
        console.print("[yellow]No benchmark problems found in problems/benchmarks/[/yellow]")
        sys.exit(0)
        
    console.print(f"[bold green]Starting benchmark run on {len(files)} problems...[/bold green]")
    
    results = []
    
    for f in files:
        console.print(f"\n[bold blue]------------------------------------------------[/bold blue]")
        console.print(f"[bold blue]Processing {f.name}...[/bold blue]")
        
        try:
            problem = parse_problem_file(f)
            console.print(f"Title: [cyan]{problem.title}[/cyan]")
            console.print(f"Samples: {len(problem.samples)}")
            
            # Execute Swarm Solver
            state = pipeline.solve(problem)
            
            results.append({
                "file": f.name,
                "title": problem.title,
                "status": state.final_status,
                "escalations": state.mathematician_escalations_used,
                "retries": state.architect_retries_used,
                "iterations": len(state.iterations),
                "error": None
            })
            
            color = "green" if state.final_status == "solved" else "red"
            console.print(f"Result: [{color}]{state.final_status}[/{color}] (Iterations: {len(state.iterations)}, Escalations: {state.mathematician_escalations_used})")
            
        except Exception as e:
            console.print(f"[bold red]Failed to process {f.name}: {e}[/bold red]")
            results.append({
                "file": f.name,
                "title": f.name,
                "status": "failed_to_run",
                "escalations": 0,
                "retries": 0,
                "iterations": 0,
                "error": str(e)
            })
            
    # Print summary table
    table = Table(title="Swarm Solver Benchmark Summary")
    table.add_column("Problem File", style="cyan")
    table.add_column("Title", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Iterations", justify="right")
    table.add_column("Escalations", justify="right")
    table.add_column("Retries", justify="right")
    
    solved_count = 0
    total_count = len(results)
    
    for r in results:
        status_color = "green" if r["status"] == "solved" else "red"
        status_text = f"[{status_color}]{r['status']}[/{status_color}]"
        
        table.add_row(
            r["file"],
            r["title"],
            status_text,
            str(r["iterations"]),
            str(r["escalations"]),
            str(r["retries"])
        )
        if r["status"] == "solved":
            solved_count += 1
            
    console.print("\n")
    console.print(table)
    
    solve_rate = (solved_count / total_count * 100) if total_count > 0 else 0
    console.print(f"\n[bold green]Solve Rate: {solved_count}/{total_count} ({solve_rate:.1f}%)[/bold green]")
    
    # Save report
    report_dir = Path(__file__).resolve().parent / "logs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "benchmark_report.md"
    
    report_lines = [
        "# Swarm Solver Benchmark Report",
        "",
        f"**Date**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Solve Rate**: {solved_count}/{total_count} ({solve_rate:.1f}%)",
        "",
        "## Summary Table",
        "",
        "| Problem File | Title | Status | Iterations | Escalations | Retries |",
        "| --- | --- | --- | --- | --- | --- |"
    ]
    
    for r in results:
        report_lines.append(f"| {r['file']} | {r['title']} | {r['status']} | {r['iterations']} | {r['escalations']} | {r['retries']} |")
        
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    console.print(f"[bold green]Report written to {report_path}[/bold green]")


if __name__ == "__main__":
    run_benchmark()
