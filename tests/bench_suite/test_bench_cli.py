import json

from bench.__main__ import main


def test_list_shows_every_task(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "bug-sum-to-off-by-one" in out and "20 tasks" in out


def test_verify_accepts_the_shipped_tasks(capsys):
    assert (
        main(["verify", "--task", "bug-sum-to-off-by-one", "--task", "refactor-move-function"]) == 0
    )
    assert "all tasks check out" in capsys.readouterr().out


def test_run_with_the_oracle_writes_a_report(tmp_path, capsys):
    code = main(
        [
            "run",
            "--solver",
            "oracle",
            "--task",
            "bug-sum-to-off-by-one",
            "--out",
            str(tmp_path),
            "--label",
            "t",
        ]
    )

    assert code == 0
    files = sorted(p.name for p in tmp_path.iterdir())
    assert files[0].endswith("-t.json") and files[1].endswith("-t.md")
    saved = json.loads((tmp_path / files[0]).read_text())
    assert saved["summary"]["solver=oracle"]["pass_rate"] == 1.0


def test_run_with_a_failing_stand_in_reports_the_failure(tmp_path, capsys):
    main(["run", "--solver", "noop", "--kind", "refactor", "--out", str(tmp_path)])

    out = capsys.readouterr().out
    assert "0/5" in out and "FAIL" in out


def test_an_agent_run_needs_a_model(capsys):
    assert main(["run", "--solver", "agent"]) == 2


def test_report_command_prints_a_saved_report(tmp_path, capsys):
    main(["run", "--solver", "oracle", "--task", "bug-sum-to-off-by-one", "--out", str(tmp_path)])
    saved = next(tmp_path.glob("*.json"))
    capsys.readouterr()

    assert main(["report", str(saved)]) == 0
    assert "solver=oracle" in capsys.readouterr().out
