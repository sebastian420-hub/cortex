"""Summaries of a batch of results, as data and as a table."""

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .runner import RunConfig, TaskResult


def _mean(values: Sequence[float]) -> Optional[float]:
    return round(sum(values) / len(values), 2) if values else None


def summarize(results: List[TaskResult]) -> Dict[str, Any]:
    """Per configuration: how many runs passed, and the average steps, tokens and time."""
    by_config: Dict[str, Dict[str, Any]] = {}
    for label in dict.fromkeys(r.config for r in results):
        rows = [r for r in results if r.config == label]
        tokens = [
            r.input_tokens + (r.output_tokens or 0) for r in rows if r.input_tokens is not None
        ]
        costs = [r.cost_usd for r in rows]
        known_costs = [c for c in costs if c is not None]
        by_config[label] = {
            "runs": len(rows),
            "passed": sum(r.passed for r in rows),
            "pass_rate": round(sum(r.passed for r in rows) / len(rows), 3),
            "pass_rate_by_kind": {
                kind: round(sum(r.passed for r in rows if r.kind == kind) / n, 3)
                for kind in dict.fromkeys(r.kind for r in rows)
                if (n := sum(1 for r in rows if r.kind == kind))
            },
            "mean_steps": _mean([r.steps for r in rows]),
            "mean_tokens": _mean(tokens),
            "tokens_estimated": any(r.tokens_estimated for r in rows),
            "total_cost_usd": (
                round(sum(known_costs), 4) if costs and len(known_costs) == len(costs) else None
            ),
            "mean_seconds": _mean([r.seconds for r in rows]),
            "crashed": sum(r.status == "crashed" for r in rows),
        }
    return by_config


def _git_sha() -> Optional[str]:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=Path(__file__).resolve().parent,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        return None


def build_report(
    results: List[TaskResult], configs: List[RunConfig], runs: int, label: str = ""
) -> Dict[str, Any]:
    base = configs[0] if configs else RunConfig()
    return {
        "meta": {
            "label": label,
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "python": platform.python_version(),
            "model": base.model,
            "provider": base.provider,
            "solver": base.solver,
            "max_iterations": base.max_iterations,
            "runs_per_setting": runs,
            "configs": [c.label for c in configs],
            "prices_usd_per_million": {"input": base.price_in, "output": base.price_out},
        },
        "summary": summarize(results),
        "results": [r.to_dict() for r in results],
    }


def to_markdown(report: Dict[str, Any]) -> str:
    meta = report["meta"]
    lines = [
        f"# Benchmark report{': ' + meta['label'] if meta.get('label') else ''}",
        "",
        f"- Date: {meta['date']}  Commit: {meta.get('git_sha') or 'unknown'}",
        f"- Solver: {meta['solver']}  Model: {meta.get('model') or 'n/a'}  "
        f"Runs per setting: {meta['runs_per_setting']}  Max steps: {meta['max_iterations']}",
        "",
        "| Setting | Passed | Pass rate | Bug fixes | Refactors | Mean steps | Mean tokens | Cost (USD) |",
        "|---|---|---|---|---|---|---|---|",
    ]

    def pct(value: Optional[float]) -> str:
        return "n/a" if value is None else f"{value * 100:.0f}%"

    for label, row in report["summary"].items():
        tokens = "n/a" if row["mean_tokens"] is None else f"{row['mean_tokens']:.0f}"
        if row["mean_tokens"] is not None and row["tokens_estimated"]:
            tokens += " (est.)"
        cost = "n/a" if row["total_cost_usd"] is None else f"{row['total_cost_usd']:.4f}"
        kinds = row["pass_rate_by_kind"]
        lines.append(
            f"| {label} | {row['passed']}/{row['runs']} | {pct(row['pass_rate'])} | "
            f"{pct(kinds.get('bugfix'))} | {pct(kinds.get('refactor'))} | "
            f"{row['mean_steps'] if row['mean_steps'] is not None else 'n/a'} | {tokens} | {cost} |"
        )
    failed = [r for r in report["results"] if not r["passed"]]
    if failed:
        lines += ["", f"{len(failed)} run(s) failed their tests:", ""]
        lines += [
            f"- `{r['task_id']}` ({r['config']}, run {r['run']}): {r['status']}"
            + (f", {r['error']}" if r.get("error") else "")
            for r in failed[:40]
        ]
    lines += [""]
    return "\n".join(lines)


def save(report: Dict[str, Any], directory: Path, label: str = "") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = f"{stamp}-{label}" if label else stamp
    path = directory / f"{stem}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True))
    path.with_suffix(".md").write_text(to_markdown(report))
    return path
