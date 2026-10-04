"""`cortex run`: the command line around an unattended run. What a scheduler sees is the exit code
and one JSON document on stdout, so nothing else may be written there."""

import json
import subprocess
import sys

import pytest

from cortex import cli
from cortex.headless import cli as run_cli
from tests.e2e.scripted import ScriptedProvider, final, tool_call
from tests.unit.headless.gitutil import git
from tests.unit.headless.test_runner import CHECK, GOOD, VERIFY, branches, write

MODEL = ["--model", "llama3.2", "--provider", "ollama"]


@pytest.fixture
def task_repo(repo):
    (repo / "check.py").write_text(CHECK)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "add check")
    return repo


def invoke(repo, *args, script=GOOD, provider=None):
    """Run `cortex run` in-process with a scripted model; returns the exit code."""
    provider = provider or ScriptedProvider(list(script))
    return run_cli.main(
        [*args, "--project-dir", str(repo), *MODEL], provider_factory=lambda: provider
    )


# ---- arguments ----------------------------------------------------------------------------


def test_it_needs_a_task(task_repo, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli.main(["--verify", VERIFY, "--project-dir", str(task_repo)])

    assert exit_info.value.code == 2
    assert "--task" in capsys.readouterr().err


def test_it_needs_to_be_told_how_the_work_is_checked(task_repo, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli.main(["--task", "t", "--project-dir", str(task_repo)])

    assert exit_info.value.code == 2
    err = capsys.readouterr().err
    assert "--verify" in err and "--no-verify" in err


def test_verify_and_no_verify_together_make_no_sense(task_repo, capsys):
    with pytest.raises(SystemExit) as exit_info:
        run_cli.main(["--task", "t", "--verify", "x", "--no-verify"])

    assert exit_info.value.code == 2


def test_a_task_and_a_task_file_together_make_no_sense(task_repo):
    with pytest.raises(SystemExit) as exit_info:
        run_cli.main(["--task", "t", "--task-file", "f", "--no-verify"])

    assert exit_info.value.code == 2


def test_the_defaults_are_safe_for_unattended_use():
    args = run_cli.build_parser().parse_args(["--task", "t", "--no-verify"])

    assert args.retries == 1
    assert args.max_steps == 40 and args.max_tokens == 1_000_000 and args.timeout == 3600
    assert args.keep_failed is False and args.require_sandbox is False
    assert args.protect == []


def test_protect_can_be_repeated():
    args = run_cli.build_parser().parse_args(
        ["--task", "t", "--no-verify", "--protect", "tests/*", "--protect", "*.lock"]
    )

    assert args.protect == ["tests/*", "*.lock"]


# ---- what comes out -----------------------------------------------------------------------


def test_json_mode_prints_one_document_and_nothing_else_on_stdout(task_repo, capfd):
    code = invoke(task_repo, "--task", "write good output", "--verify", VERIFY, "--json")

    out, err = capfd.readouterr()
    data = json.loads(out)  # the whole of stdout, despite the agent narrating its work
    assert code == 0 and data["status"] == "passed"
    assert data["branch"] in branches(task_repo)
    assert "Writing" in err or "out.txt" in err  # the narration went to stderr, not away


def test_quiet_discards_the_narration(task_repo, capfd):
    invoke(task_repo, "--task", "t", "--verify", VERIFY, "--json", "--quiet")

    out, err = capfd.readouterr()
    json.loads(out)
    assert "out.txt" not in err


def test_text_mode_gives_a_summary_a_person_can_read(task_repo, capfd):
    code = invoke(task_repo, "--task", "write good output", "--verify", VERIFY)

    out, _ = capfd.readouterr()
    assert code == 0
    assert "passed" in out.lower()
    assert "cortex/write-good-output-" in out  # the branch
    assert "git diff" in out  # how to look at it
    assert not out.lstrip().startswith("{")


def test_a_failed_run_says_why_and_exits_1(task_repo, capfd):
    bad = [write("out.txt", "bad\n"), final("done")]

    code = invoke(task_repo, "--task", "t", "--verify", VERIFY, "--retries", "0", script=bad)

    out, _ = capfd.readouterr()
    assert code == 1
    assert "failed" in out.lower() and "verification" in out.lower()


def test_output_writes_the_same_document_to_a_file(task_repo, tmp_path, capfd):
    target = tmp_path / "reports" / "run.json"

    invoke(task_repo, "--task", "t", "--verify", VERIFY, "--json", "--output", str(target))

    out, _ = capfd.readouterr()
    assert json.loads(target.read_text()) == json.loads(out)


def test_no_verify_means_unverified_and_exit_0(task_repo, capfd):
    code = invoke(task_repo, "--task", "t", "--no-verify", "--json")

    out, _ = capfd.readouterr()
    assert code == 0 and json.loads(out)["status"] == "unverified"


def test_the_task_can_come_from_a_file(task_repo, tmp_path, capfd):
    task_file = tmp_path / "task.md"
    task_file.write_text("Make out.txt say good.\n\nThe check will tell you.\n")

    invoke(task_repo, "--task-file", str(task_file), "--verify", VERIFY, "--json")

    data = json.loads(capfd.readouterr().out)
    assert data["task"].startswith("Make out.txt say good.")


def test_the_model_and_provider_flags_win(task_repo, capfd):
    invoke(task_repo, "--task", "t", "--verify", VERIFY, "--json")

    data = json.loads(capfd.readouterr().out)
    assert data["model"] == "llama3.2" and data["provider"] == "ollama"


def test_prices_turn_into_a_cost(task_repo, capfd):
    class Counting(ScriptedProvider):
        def chat(self, model, messages, tools=None):
            response = super().chat(model, messages, tools)
            response["usage"] = {"input_tokens": 1_000_000, "output_tokens": 0}
            return response

    invoke(
        task_repo, "--task", "t", "--verify", VERIFY, "--json", "--max-tokens", "0",
        "--price-in", "2", "--price-out", "10", provider=Counting(list(GOOD)),
    )  # fmt: skip

    usage = json.loads(capfd.readouterr().out)["usage"]
    assert usage["cost_usd"] == pytest.approx(4.0)  # two calls of a million input tokens at $2


# ---- could not start ----------------------------------------------------------------------


def test_a_directory_that_is_not_a_repository_exits_2_with_a_json_reason(tmp_path, capfd):
    plain = tmp_path / "plain"
    plain.mkdir()

    code = invoke(plain, "--task", "t", "--verify", "true", "--json")

    data = json.loads(capfd.readouterr().out)
    assert code == 2 and data["status"] == "setup_error"
    assert "git repository" in data["reason"]


def test_a_missing_task_file_exits_2(task_repo, tmp_path, capfd):
    code = invoke(task_repo, "--task-file", str(tmp_path / "nope.md"), "--no-verify", "--json")

    data = json.loads(capfd.readouterr().out)
    assert code == 2 and data["status"] == "setup_error" and "nope.md" in data["reason"]


def test_an_empty_task_exits_2(task_repo, capfd):
    code = invoke(task_repo, "--task", "   ", "--no-verify", "--json")

    assert code == 2
    assert "empty" in json.loads(capfd.readouterr().out)["reason"]


def test_a_missing_config_file_exits_2(task_repo, tmp_path, capfd):
    code = invoke(
        task_repo, "--task", "t", "--no-verify", "--json", "--config", str(tmp_path / "no.yaml")
    )

    data = json.loads(capfd.readouterr().out)
    assert code == 2 and data["status"] == "setup_error"


def test_require_sandbox_refuses_to_run_without_one(task_repo, capfd):
    provider = ScriptedProvider(list(GOOD))

    code = invoke(task_repo, "--task", "t", "--verify", VERIFY, "--json", "--require-sandbox",
                  provider=provider)  # fmt: skip

    data = json.loads(capfd.readouterr().out)
    assert code == 2 and "command_sandbox" in data["reason"]
    assert provider.seen == []


def test_the_config_file_is_used(task_repo, tmp_path, capfd):
    import yaml

    config = tmp_path / "c.yaml"
    config.write_text(yaml.safe_dump({"command_sandbox": {"mode": "magic"}}))

    code = invoke(task_repo, "--task", "t", "--no-verify", "--json", "--config", str(config))

    data = json.loads(capfd.readouterr().out)
    assert code == 2 and "magic" in data["reason"]  # proof the file reached the run


# ---- reaching it from `cortex` ------------------------------------------------------------


def test_cortex_run_dispatches_to_the_headless_command(monkeypatch):
    seen = {}

    def fake_main(argv=None, provider_factory=None):
        seen["argv"] = argv
        return 7

    monkeypatch.setattr(run_cli, "main", fake_main)
    monkeypatch.setattr(sys, "argv", ["cortex", "run", "--task", "t", "--no-verify"])

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 7
    assert seen["argv"] == ["--task", "t", "--no-verify"]


def test_other_commands_are_not_taken_for_run(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["cortex", "--list-providers"])
    monkeypatch.setattr(run_cli, "main", lambda *a, **k: pytest.fail("dispatched"))

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 0


def test_the_real_command_is_reachable_and_documents_itself(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cortex", "run", "--help"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 0
    for flag in ("--task", "--verify", "--no-verify", "--max-steps", "--keep-failed", "--json"):
        assert flag in result.stdout


def test_a_real_process_without_a_verify_decision_exits_2(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cortex", "run", "--task", "t"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert result.returncode == 2 and "--verify" in result.stderr


def test_a_config_file_that_does_not_exist_is_an_error_not_the_defaults(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        cli.load_agent_config(str(tmp_path / "typo.yaml"))


def test_the_interactive_command_refuses_a_missing_config_file_too(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["cortex", "--config", str(tmp_path / "typo.yaml"), "-p", "hello"]
    )

    with pytest.raises(SystemExit) as exit_info:
        cli.main()

    assert exit_info.value.code == 1


def test_no_config_argument_still_means_the_defaults(monkeypatch):
    config, path = cli.load_agent_config(None)

    assert config is not None  # and no error: only an explicit missing file is refused
