"""Optional confinement for the commands the agent runs, and an honest account of it.

By default there is no isolation: a shell command runs with the same permissions as the user who
started Cortex. The command blocklist (core/security.py) and the approval prompts reduce the
chance of a destructive command, but they are a filter, not a boundary: a script the model writes
and then runs is not inspected.

``mode: bubblewrap`` adds a real boundary on Linux. Commands run in a new namespace where:

- the whole filesystem is visible but read-only,
- the project directory (and any ``writable`` extras) is writable,
- ``/tmp`` is a private empty directory,
- processes are in their own PID namespace and die with Cortex.

It does NOT hide files from the command unless ``private_home`` is set, and it does not restrict
the network unless ``network`` is false. If the mode is requested and cannot be provided (not
Linux, ``bwrap`` missing), the command is refused: a sandbox that quietly turns itself off is
worse than none.
"""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

MODES = ("none", "bubblewrap")


class SandboxUnavailable(RuntimeError):
    """The configured sandbox cannot be provided on this machine."""


@dataclass(frozen=True)
class SandboxConfig:
    mode: str = "none"
    network: bool = True  # False cuts the command off from the network
    private_home: bool = False  # True hides the home directory (and the secrets in it)
    writable: Tuple[str, ...] = ()  # extra directories the command may write to

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> "SandboxConfig":
        data = data or {}
        mode = str(data.get("mode", "none")).strip().lower()
        if mode not in MODES:
            raise ValueError(
                f"Unknown command_sandbox mode '{data.get('mode')}'. Valid modes: {', '.join(MODES)}"
            )
        return cls(
            mode=mode,
            network=bool(data.get("network", True)),
            private_home=bool(data.get("private_home", False)),
            writable=tuple(str(p) for p in (data.get("writable") or ())),
        )


def _find_bwrap() -> str:
    if not sys.platform.startswith("linux"):
        raise SandboxUnavailable(
            "command_sandbox mode 'bubblewrap' only works on Linux. "
            "Set command_sandbox.mode to 'none' or run Cortex inside a container or VM."
        )
    path = shutil.which("bwrap")
    if not path:
        raise SandboxUnavailable(
            "command_sandbox mode 'bubblewrap' is configured but 'bwrap' (bubblewrap) is not "
            "installed. Install it (for example: apt install bubblewrap) or set "
            "command_sandbox.mode to 'none'. The command was not run."
        )
    return path


def confine(
    argv: Sequence[str],
    project_dir: Path,
    config: Optional[SandboxConfig],
    bwrap: Optional[str] = None,
) -> Optional[List[str]]:
    """The command line that runs ``argv`` inside the sandbox, or None for mode 'none'.

    Raises SandboxUnavailable when the mode is on but cannot be provided.
    """
    if config is None or config.mode == "none":
        return None

    project = str(Path(project_dir).resolve())
    command: List[str] = [
        bwrap or _find_bwrap(),
        "--die-with-parent",
        "--new-session",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
    ]
    if not config.network:
        command.append("--unshare-net")

    # Order matters: later mounts are laid over earlier ones.
    command += [
        "--ro-bind",
        "/",
        "/",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--tmpfs",
        "/tmp",
    ]  # nosec B108
    if config.private_home:
        home = os.environ.get("HOME")
        if home and Path(home).is_dir():
            command += ["--tmpfs", home]
    # The project (which may live under /tmp or under home) is bound after both are masked
    command += ["--bind", project, project]
    for extra in config.writable:
        extra_path = Path(extra).expanduser()
        if extra_path.is_dir():
            command += ["--bind", str(extra_path.resolve()), str(extra_path.resolve())]
    command += ["--chdir", project, "--", *argv]
    return command


def shell_argv(command: str) -> List[str]:
    """How a shell command line is run when it has to be passed as an argument vector."""
    return ["/bin/sh", "-c", command]


def describe(config: Optional[SandboxConfig]) -> str:
    """What the current setting does and does not stop, in plain words."""
    if config is None or config.mode == "none":
        return (
            "Commands are not isolated: they run with the same permissions as the user who "
            "started Cortex and can read or change anything that user can. A blocklist refuses "
            "some destructive commands, but it cannot catch everything (for example a script that "
            "is written and then run). Set command_sandbox.mode to 'bubblewrap' (Linux), or run "
            "Cortex in a container or VM, for a real boundary."
        )
    parts = [
        "Commands run in a bubblewrap sandbox: they can write only inside the project "
        "directory (plus any configured writable paths) and a private /tmp, and the rest of the "
        "filesystem is read-only."
    ]
    parts.append(
        "The home directory is hidden."
        if config.private_home
        else "They can still READ everything else the user can read, including files in the home "
        "directory."
    )
    parts.append(
        "The network is disabled."
        if not config.network
        else "The network is NOT restricted, so a command can still send data out."
    )
    return " ".join(parts)
