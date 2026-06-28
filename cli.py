"""
Entry point: `python cli.py solve problems/samples/<file>.txt`

TODO(phase 6): build out with `click` + `rich` for live progress display of
the agent back-and-forth (this is the fun part to watch — show each
iteration's Adversary verdict as it happens, not just the final result).
"""

import click


@click.group()
def cli():
    pass


@cli.command()
@click.argument("problem_file", type=click.Path(exists=True))
def solve(problem_file: str):
    """
    TODO(phase 6, depends on phase 4's orchestrator.pipeline.solve existing):
    1. Parse problem_file into a Problem (TODO phase 1: decide on parsing —
       likely a simple text format matching problems/samples/*.txt, or just
       pass raw text + let the Mathematician do all the constraint
       extraction without pre-parsing).
    2. state = orchestrator.pipeline.solve(problem)
    3. Pretty-print state.final_status + final code version (if solved) or
       failure summary (if not) using rich.
    """
    click.echo("Not implemented yet — see TODOs in cli.py and orchestrator/pipeline.py")


if __name__ == "__main__":
    cli()
