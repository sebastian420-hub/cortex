"""``cortex run``: one task, unattended, with a result a scheduler can read.

What a scheduler sees is the exit code and, with ``--json``, one JSON document on stdout. So
nothing else is written to stdout: the agent's running commentary goes to stderr (or nowhere, with
``--quiet``).

Exit codes: 0 the run completed as asked (``passed``, or ``unverified`` because no verify command
was given); 1 it ran and did not succeed; 2 it could not start (bad arguments, not a git
repository, a sandbox that was required but is unavailable...). The ``status`` field says exactly
what happened.
"""

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, List, Optional

from .runner import HeadlessConfig, RunResult, run, setup_error

# Defaults for an unattended run: bounded, because nobody is watching it
DEFAULT_RETRIES = 1
DEFAULT_MAX_STEPS = 40
DEFAULT_MAX_TOKENS = 1_000_000
DEFAULT_TIMEOUT_S = 3600
DEFAULT_VERIFY_TIMEOUT_S = 600


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cortex run",
        description=(
            "Run one task unattended on its own git branch, check it with a command, and report "
            "what happened. Your checkout is never touched; a run that does not verify leaves "
            "nothing behind."
        ),
        epilog=(
            "exit codes: 0 completed as asked (passed, or unverified because --no-verify), "
            "1 ran but did not succeed, 2 could not start. The 'status' field in the JSON result "
            "says exactly what happened."
        ),
    )

    task = parser.add_mutually_exclusive_group(required=True)
    task.add_argument("--task", help="what to do, in words")
    task.add_argument("--task-file", help="read the task from this file")

    verify = parser.add_mutually_exclusive_group()
    verify.add_argument(
        "--verify",
        metavar="COMMAND",
        help="shell command that must exit 0 for the task to count as done, e.g. 'pytest -q'",
    )
    verify.add_argument(
        "--no-verify",
        action="store_true",
        help="run without a check; the result is then 'unverified', never 'passed'",
    )

    budgets = parser.add_argument_group("budgets (0 = no limit)")
    budgets.add_argument("--retries", type=int, default=DEFAULT_RETRIES,
                         help="extra attempts after a failed verification (default %(default)s)")  # fmt: skip
    budgets.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS,
                         help="model calls over the whole run (default %(default)s)")  # fmt: skip
    budgets.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS,
                         help="input plus output tokens over the whole run (default %(default)s)")  # fmt: skip
    budgets.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S,
                         help="wall-clock seconds over the whole run (default %(default)s)")  # fmt: skip
    budgets.add_argument("--verify-timeout", type=float, default=DEFAULT_VERIFY_TIMEOUT_S,
                         help="seconds the verify command may take (default %(default)s)")  # fmt: skip

    where = parser.add_argument_group("where it runs")
    where.add_argument("--project-dir", help="the git repository (default: current directory)")
    where.add_argument("--base", default="HEAD", help="commit to start from (default HEAD)")
    where.add_argument("--branch", help="name for the branch (default cortex/<task>-<id>)")
    where.add_argument("--keep-failed", action="store_true",
                       help="keep the branch of a run that did not succeed, to look at it")  # fmt: skip
    where.add_argument("--protect", action="append", default=[], metavar="GLOB",
                       help="a path the run must not change, e.g. 'tests/*' (repeatable); "
                            "changing one fails the run even if verification passes")  # fmt: skip
    where.add_argument("--require-sandbox", action="store_true",
                       help="refuse to run unless command_sandbox confines commands")  # fmt: skip

    model = parser.add_argument_group("model")
    model.add_argument("--model", "-m", help="model to use")
    model.add_argument("--provider", choices=["ollama", "deepseek", "anthropic", "openrouter", "openai"])  # fmt: skip
    model.add_argument("--config", "-c", help="configuration file (YAML)")
    model.add_argument("--price-in", type=float, metavar="USD",
                       help="dollars per million input tokens, to report a cost")  # fmt: skip
    model.add_argument("--price-out", type=float, metavar="USD",
                       help="dollars per million output tokens, to report a cost")  # fmt: skip

    output = parser.add_argument_group("output")
    output.add_argument("--json", action="store_true", help="print the result as JSON on stdout")
    output.add_argument("--output", metavar="FILE", help="also write the JSON result to this file")
    output.add_argument("--quiet", action="store_true",
                        help="discard the agent's commentary instead of sending it to stderr")  # fmt: skip
    return parser


def summary(result: RunResult) -> str:
    """The result in a few lines a person can read."""
    lines = [f"{result.status.upper()}: {result.reason}", f"run:     {result.run_id}"]
    if result.branch and result.base:
        lines.append(f"branch:  {result.branch} ({len(result.files_changed)} file(s) changed)")
        lines.append(f"review:  git diff {result.base[:12]}..{result.branch}")
    elif result.files_changed:
        lines.append(
            f"changes: {len(result.files_changed)} file(s) were changed and not kept "
            "(--keep-failed keeps the branch of a run that did not succeed)"
        )
    usage = result.usage
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    spent = (
        f"{usage.get('steps', 0)} model calls, {usage.get('tool_calls', 0)} tool calls, "
        f"{tokens:,} tokens{' (estimated)' if usage.get('estimated') else ''}, {result.seconds}s"
    )
    if usage.get("cost_usd") is not None:
        spent += f", ${usage['cost_usd']:.4f}"
    lines.append(f"spent:   {spent}")
    if result.verify_command:
        lines.append(f"checked: {result.verify_command}")
    return "\n".join(lines)


def _emit(result: RunResult, args: argparse.Namespace) -> None:
    document = json.dumps(result.to_dict(), indent=2, default=str)
    if args.output:
        try:
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(document + "\n", encoding="utf-8")
        except OSError as e:
            print(f"cortex run: could not write {args.output}: {e}", file=sys.stderr)
    print(document if args.json else summary(result))


def main(
    argv: Optional[List[str]] = None,
    provider_factory: Optional[Callable[[], Any]] = None,
) -> int:
    """Run the command. ``provider_factory`` replaces the model provider (used by the tests)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.verify is None and not args.no_verify:
        parser.error(
            "say how the work is checked: --verify 'COMMAND' (recommended, e.g. --verify 'pytest "
            "-q') or --no-verify (the result is then 'unverified')"
        )

    project_dir = Path(args.project_dir or os.getcwd())

    def fail(task: str, reason: str) -> int:
        result = setup_error(task, project_dir, reason)
        _emit(result, args)
        return result.exit_code

    try:
        task = (
            args.task if args.task is not None else Path(args.task_file).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError) as e:
        return fail("", f"could not read the task file {args.task_file}: {e}")
    if not task.strip():
        return fail(task, "the task is empty")

    def execute() -> RunResult:
        from ..cli import load_agent_config, validate_provider_setup
        from ..core.feature_flags import FeatureManager

        try:
            agent_config, _ = load_agent_config(args.config)
        except Exception as e:
            return setup_error(task, project_dir, f"could not load the configuration: {e}")
        FeatureManager.get_instance(agent_config.get_feature_flags_config())
        if args.model:
            agent_config.model = args.model
        if args.provider:
            agent_config.provider = args.provider
        if provider_factory is None and not validate_provider_setup(
            agent_config.model, agent_config.provider
        ):
            return setup_error(
                task, project_dir, "the model provider is not set up (see the message above)"
            )

        return run(
            HeadlessConfig(
                task=task,
                project_dir=project_dir,
                verify=None if args.no_verify else args.verify,
                retries=args.retries,
                max_steps=args.max_steps,
                max_tokens=args.max_tokens,
                timeout_s=args.timeout,
                verify_timeout_s=args.verify_timeout,
                base_ref=args.base,
                branch=args.branch,
                keep_failed=args.keep_failed,
                protect=tuple(args.protect),
                require_sandbox=args.require_sandbox,
                price_in=args.price_in,
                price_out=args.price_out,
            ),
            agent_config,
            provider_factory,
        )

    # Everything the run prints (provider checks, the agent's commentary) goes to stderr, so that
    # stdout carries only the result, which is written once the redirect is over
    sink = open(os.devnull, "w") if args.quiet else sys.stderr
    try:
        with contextlib.redirect_stdout(sink):
            result = execute()
    finally:
        if args.quiet:
            sink.close()

    _emit(result, args)
    return result.exit_code
