"""python -m bench: list, verify, run and report."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import report as reporting
from .runner import FACTORS, RunConfig, SOLVERS, ablation_configs, run_batch
from .suite import TASKS, select
from .task import apply_solution, materialize, verify

DEFAULT_REPORTS = Path(__file__).resolve().parent / "reports"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m bench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show the tasks")

    check = sub.add_parser(
        "verify", help="check the tasks themselves: each must fail as shipped and pass when solved"
    )
    check.add_argument("--task", action="append", help="only this task (repeatable)")

    run = sub.add_parser("run", help="run a solver against the tasks and write a report")
    run.add_argument("--solver", choices=SOLVERS, default="agent")
    run.add_argument("--model", help="model name (agent solver)")
    run.add_argument("--provider", help="provider name (agent solver)")
    run.add_argument("--task", action="append", help="only this task (repeatable)")
    run.add_argument("--kind", choices=("bugfix", "refactor"))
    run.add_argument("--runs", type=int, default=1, help="repetitions per setting")
    run.add_argument("--max-iterations", type=int, default=30)
    for factor in FACTORS:
        run.add_argument(f"--{factor}", action="store_true", help=f"turn {factor} on")
    run.add_argument(
        "--ablate",
        help=f"comma-separated factors to switch on and off in every combination "
        f"({', '.join(FACTORS)})",
    )
    run.add_argument("--share-memory", action="store_true", help="keep memory across tasks")
    run.add_argument("--price-in", type=float, help="USD per million input tokens (for cost)")
    run.add_argument("--price-out", type=float, help="USD per million output tokens (for cost)")
    run.add_argument("--out", type=Path, default=DEFAULT_REPORTS, help="where reports are written")
    run.add_argument("--label", default="", help="a name for this run, used in the file name")

    show = sub.add_parser("report", help="print a saved report as a table")
    show.add_argument("file", type=Path)
    return parser


def cmd_list() -> int:
    width = max(len(t.id) for t in TASKS)
    for task in TASKS:
        print(f"{task.id:<{width}}  {task.kind:<8}  {task.title}")
    print(f"\n{len(TASKS)} tasks")
    return 0


def cmd_verify(ids: Optional[List[str]]) -> int:
    import tempfile

    problems = 0
    for task in select(ids):
        with tempfile.TemporaryDirectory(prefix="bench-verify-") as scratch:
            project = Path(scratch) / "project"
            materialize(task, project)
            before = verify(task, project)
            apply_solution(task, project)
            after = verify(task, project)
        if before.passed:
            print(f"BAD  {task.id}: passes before any change, so it tests nothing")
            problems += 1
        elif not after.passed:
            print(f"BAD  {task.id}: the reference solution does not pass\n{after.output[-500:]}")
            problems += 1
        else:
            print(f"ok   {task.id}")
    print("\nall tasks check out" if not problems else f"\n{problems} task(s) are broken")
    return 1 if problems else 0


def cmd_run(args: argparse.Namespace) -> int:
    if args.solver == "agent" and not args.model:
        print(
            "--model is required for the agent solver (or use --solver oracle|noop)",
            file=sys.stderr,
        )
        return 2
    base = RunConfig(
        solver=args.solver,
        model=args.model,
        provider=args.provider,
        planning=args.planning,
        memory=args.memory,
        metacognition=args.metacognition,
        max_iterations=args.max_iterations,
        price_in=args.price_in,
        price_out=args.price_out,
        share_memory=args.share_memory,
    )
    configs = (
        ablation_configs(base, [f.strip() for f in args.ablate.split(",") if f.strip()])
        if args.ablate
        else [base]
    )
    tasks = select(args.task, args.kind)
    total = len(configs) * args.runs * len(tasks)
    print(f"{len(tasks)} tasks x {len(configs)} setting(s) x {args.runs} run(s) = {total} runs")

    done = 0

    def progress(result) -> None:
        nonlocal done
        done += 1
        print(
            f"[{done}/{total}] {'PASS' if result.passed else 'FAIL'} {result.task_id} ({result.config})"
        )

    results = run_batch(configs, tasks, args.runs, progress=progress)
    report = reporting.build_report(results, configs, args.runs, args.label)
    path = reporting.save(report, args.out, args.label)
    print("\n" + reporting.to_markdown(report))
    print(f"Saved {path}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list":
        return cmd_list()
    if args.command == "verify":
        return cmd_verify(args.task)
    if args.command == "run":
        return cmd_run(args)
    print(reporting.to_markdown(json.loads(args.file.read_text())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
