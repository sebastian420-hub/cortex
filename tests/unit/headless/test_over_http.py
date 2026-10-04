"""The whole thing as a person's scheduler would run it: a real `cortex run` process, talking over
HTTP to a server that speaks the OpenAI chat API.

The server is a small stand-in (it replays a script), not vLLM or llama.cpp, but the wire format
is the real one and the client is the real OpenAI SDK, so this exercises what the unit tests with
stand-in clients cannot: the SDK's response objects (`content` is null when a model calls a tool),
the provider's conversion of them, and the command line end to end.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.unit.headless.gitutil import git
from tests.unit.headless.test_runner import CHECK, VERIFY, branches


def tool_reply(name, arguments, call_id="call_1"):
    return {
        "role": "assistant",
        "content": None,  # real servers send null, not "", when the model calls a tool
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        ],
    }


def text_reply(text):
    return {"role": "assistant", "content": text}


class FakeServer:
    """Replays assistant messages over /v1/chat/completions and records what it was sent."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - the name http.server looks for
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(
                    {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
                )
                message = outer.replies.pop(0) if outer.replies else text_reply("done")
                payload = json.dumps(
                    {
                        "id": "chatcmpl-test",
                        "object": "chat.completion",
                        "created": 0,
                        "model": body.get("model"),
                        "choices": [
                            {
                                "index": 0,
                                "message": message,
                                "finish_reason": (
                                    "tool_calls" if message.get("tool_calls") else "stop"
                                ),
                            }
                        ],
                        "usage": {
                            "prompt_tokens": 120,
                            "completion_tokens": 30,
                            "total_tokens": 150,
                        },
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/v1"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def task_repo(repo):
    (repo / "check.py").write_text(CHECK)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "add check")
    return repo


def cortex_run(repo, tmp_path, base_url, *args):
    """`cortex run` as its own process, with an environment that cannot reach anything but the
    stand-in server."""
    env = {k: v for k, v in os.environ.items() if "proxy" not in k.lower()}
    home = tmp_path / "proc-home"
    home.mkdir(exist_ok=True)
    env.update(HOME=str(home), USERPROFILE=str(home), GIT_CONFIG_GLOBAL=os.devnull)
    env.pop("OPENAI_API_KEY", None)
    if base_url:
        env["OPENAI_BASE_URL"] = base_url
    else:
        env.pop("OPENAI_BASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "cortex", "run", "--project-dir", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
        timeout=120,
    )


def test_a_real_run_over_http_passes_and_reports_what_the_server_said(task_repo, tmp_path):
    script = [
        tool_reply("write_file", {"path": "out.txt", "content": "good\n"}),
        text_reply("done"),
    ]

    with FakeServer(script) as server:
        process = cortex_run(
            task_repo, tmp_path, server.url,
            "--task", "Make out.txt say good", "--verify", VERIFY,
            "--provider", "openai", "--model", "my-local-model", "--json",
        )  # fmt: skip

    assert process.returncode == 0, process.stderr[-2000:]
    result = json.loads(process.stdout)  # all of stdout is the result
    assert result["status"] == "passed"
    assert result["provider"] == "openai" and result["model"] == "my-local-model"
    assert result["branch"] in branches(task_repo)
    assert git(task_repo, "show", f"{result['branch']}:out.txt") == "good"

    # the usage is what the server reported, not an estimate
    assert result["usage"]["steps"] == 2
    assert result["usage"]["input_tokens"] == 240 and result["usage"]["output_tokens"] == 60
    assert result["usage"]["estimated"] is False

    # what the server was sent
    first = server.requests[0]
    assert first["path"] == "/v1/chat/completions"
    assert first["body"]["model"] == "my-local-model"
    tools = [t["function"]["name"] for t in first["body"]["tools"]]
    assert "write_file" in tools and "ask_user_question" not in tools
    prompt = [m for m in first["body"]["messages"] if m["role"] == "user"][0]["content"]
    assert "Make out.txt say good" in prompt and "unattended" in prompt
    # the tool result went back to the model, paired with its call
    followup = server.requests[1]["body"]["messages"]
    assert [m["role"] for m in followup][-2:] == ["assistant", "tool"]
    assert followup[-1]["tool_call_id"] == "call_1"


def test_a_real_run_that_does_not_verify_leaves_nothing(task_repo, tmp_path):
    before = branches(task_repo)
    script = [tool_reply("write_file", {"path": "out.txt", "content": "bad\n"}), text_reply("done")]

    with FakeServer(script) as server:
        process = cortex_run(
            task_repo, tmp_path, server.url,
            "--task", "t", "--verify", VERIFY, "--retries", "0",
            "--provider", "openai", "--model", "m", "--json",
        )  # fmt: skip

    result = json.loads(process.stdout)
    assert process.returncode == 1 and result["status"] == "failed"
    assert "bad" in result["attempts"][0]["verification"]["output_tail"]
    assert branches(task_repo) == before
    assert len(git(task_repo, "worktree", "list").splitlines()) == 1


def test_a_server_that_is_not_there_is_an_agent_failure_not_a_hang(task_repo, tmp_path):
    before = branches(task_repo)

    process = cortex_run(
        task_repo, tmp_path, "http://127.0.0.1:9/v1",  # nothing listens on the discard port
        "--task", "t", "--verify", VERIFY, "--provider", "openai", "--model", "m", "--json",
    )  # fmt: skip

    result = json.loads(process.stdout)
    assert process.returncode == 1 and result["status"] == "agent_failed"
    assert branches(task_repo) == before


def test_with_no_server_and_no_key_it_says_what_to_set(task_repo, tmp_path):
    process = cortex_run(
        task_repo, tmp_path, None,
        "--task", "t", "--verify", VERIFY, "--provider", "openai", "--model", "m", "--json",
    )  # fmt: skip

    result = json.loads(process.stdout)
    assert process.returncode == 2 and result["status"] == "setup_error"
    assert "OPENAI_BASE_URL" in process.stderr  # the provider's own explanation
