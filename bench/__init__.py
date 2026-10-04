"""A small benchmark for coding agents: verifiable tasks, a runner, and honest reports.

Each task is a tiny project with a planted bug (or code that needs refactoring) and tests that
decide whether the work is done. The verdict always comes from running those tests, never from
what the agent says about its own work.

    python -m bench list                  # the tasks
    python -m bench verify                # check the tasks themselves (no model needed)
    python -m bench run --model <name>    # run an agent against them
    python -m bench report <report.json>  # show a saved report
"""
