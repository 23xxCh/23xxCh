"""Action execution for LLM controller.

This module provides functions for executing actions:
- console_action: Simulation control (start, stop, refresh, export)
- shell_command: Safe shell command execution
- code_evolve: Git worktree-based code evolution
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from typing import Any
import uuid


FORBIDDEN_COMMAND_PATTERNS = [
    "rm -rf",
    "git reset --hard",
    "git checkout --",
    "mkfs",
    "shutdown",
    "reboot",
    ":(){",
]

# Shell metacharacters that enable command chaining and injection
DANGEROUS_SHELL_METACHARACTERS = [
    ";",      # Command separator
    "&&",     # Conditional AND
    "||",     # Conditional OR
    "|",      # Pipe
    "`",      # Command substitution (backtick)
    "$(",     # Command substitution (modern)
    ">",      # Output redirection
    "<",      # Input redirection
    "$(",     # Command substitution
    "${",     # Variable expansion
]

ALLOWED_COMMAND_PREFIXES = [
    "ros2 ",
    "colcon ",
    "pytest ",
    "python3 -m pytest",
    "python3 ",
    "git ",
    "ls",
    "cat ",
    "rg ",
    "grep ",
    "sed ",
    "awk ",
    "head ",
    "tail ",
    "echo ",
    "timeout ",
    "cd ",
]


def command_allowed(command: str) -> tuple[bool, str]:
    """Check if a command is allowed by policy.

    Args:
        command: The command to check.

    Returns:
        Tuple of (allowed, reason).
    """
    text = str(command or "").strip()
    if not text:
        return False, "empty command"
    lowered = text.lower()
    for token in FORBIDDEN_COMMAND_PATTERNS:
        if token in lowered:
            return False, f"forbidden pattern: {token}"
    if not any(lowered.startswith(prefix) for prefix in ALLOWED_COMMAND_PREFIXES):
        return False, "command not allowed by policy"
    return True, ""


def has_dangerous_metacharacters(command: str) -> tuple[bool, str]:
    """Check if a command contains dangerous shell metacharacters.

    These characters enable command chaining and injection attacks.
    Commands with these characters must be rejected or use shell=True with caution.

    Args:
        command: The command to check.

    Returns:
        Tuple of (has_dangerous_chars, found_char).
    """
    for char in DANGEROUS_SHELL_METACHARACTERS:
        if char in command:
            return True, char
    return False, ""


def execute_console_action(
    payload: dict[str, Any],
    *,
    sim: Any,
) -> dict[str, Any]:
    """Execute a console action.

    Args:
        payload: Action payload with action type and parameters.
        sim: SimulationController instance.

    Returns:
        Dictionary with ok and message or result.
    """
    action = str(payload.get("action") or "").strip().lower()
    if action == "start_simulation":
        ok, msg = sim.start_with_profile(payload.get("launch_profile"))
        return {"ok": ok, "message": msg}
    if action == "stop_simulation":
        ok, msg = sim.stop()
        return {"ok": ok, "message": msg}
    if action == "refresh_status":
        return {"ok": True, "status": sim.status()}
    if action == "export_diagnostics":
        scene = str(payload.get("scene") or sim.status().get("launch_profile", {}).get("scene", "warehouse"))
        path = sim.export_diagnostics(scene=scene)
        return {"ok": True, "path": path}
    if action == "export_run_report":
        scene = str(payload.get("scene") or sim.status().get("launch_profile", {}).get("scene", "warehouse"))
        artifact = sim.export_run_report(scene=scene)
        return {"ok": True, **artifact}
    return {"ok": False, "message": f"unsupported console action: {action}"}


def _coerce_profile_token(value: Any, *, default: str) -> str:
    """Coerce a profile token value.

    Args:
        value: The value to coerce.
        default: Default value if not recognized.

    Returns:
        Coerced string value.
    """
    text = str(value or "").strip().lower()
    if text in {"true", "1", "yes", "on"}:
        return "true"
    if text in {"false", "0", "no", "off"}:
        return "false"
    if text in {"warehouse", "baseline"}:
        return text
    return default


def translate_legacy_launch_script(
    command: str,
    *,
    sim: Any,
) -> dict[str, Any] | None:
    """Translate a legacy launch_sim.sh command to console action.

    Args:
        command: The shell command to translate.
        sim: SimulationController instance for default profile.

    Returns:
        Translated action payload, or None if not a launch script command.
    """
    if "launch_sim.sh" not in command:
        return None
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    launch_idx = -1
    for idx, token in enumerate(tokens):
        if token.endswith("launch_sim.sh"):
            launch_idx = idx
            break
    if launch_idx < 0:
        return None

    default_profile = {
        "scene": "warehouse",
        "use_gaden": "true",
        "use_slam": "true",
        "use_rviz": "true",
        "headless": "false",
    }
    try:
        status = sim.status()
        launch_profile = status.get("launch_profile") if isinstance(status, dict) else None
        if isinstance(launch_profile, dict):
            default_profile["scene"] = _coerce_profile_token(launch_profile.get("scene"), default="warehouse")
            default_profile["use_gaden"] = _coerce_profile_token(launch_profile.get("use_gaden"), default="true")
            default_profile["use_slam"] = _coerce_profile_token(launch_profile.get("use_slam"), default="true")
            default_profile["use_rviz"] = _coerce_profile_token(launch_profile.get("use_rviz"), default="true")
            default_profile["headless"] = _coerce_profile_token(launch_profile.get("headless"), default="false")
    except Exception:
        pass

    args = tokens[launch_idx + 1 :]
    profile = dict(default_profile)
    i = 0
    while i < len(args):
        arg = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else ""
        if arg == "--scene" and nxt:
            profile["scene"] = _coerce_profile_token(nxt, default=profile["scene"])
            i += 2
            continue
        if arg == "--gaden":
            profile["use_gaden"] = "true"
        elif arg == "--no-gaden":
            profile["use_gaden"] = "false"
        elif arg == "--slam":
            profile["use_slam"] = "true"
        elif arg == "--no-slam":
            profile["use_slam"] = "false"
        elif arg == "--rviz":
            profile["use_rviz"] = "true"
        elif arg == "--no-rviz":
            profile["use_rviz"] = "false"
        elif arg == "--headless":
            profile["headless"] = "true"
        elif arg == "--no-headless":
            profile["headless"] = "false"
        i += 1

    return {"action": "start_simulation", "launch_profile": profile}


def execute_shell_command(
    payload: dict[str, Any],
    *,
    sim: Any,
) -> dict[str, Any]:
    """Execute a shell command.

    Args:
        payload: Command payload with command string.
        sim: SimulationController instance for launch script translation.

    Returns:
        Dictionary with ok, returncode, stdout, stderr, and message.
    """
    command = str(payload.get("command") or "").strip()
    translated_payload = translate_legacy_launch_script(command, sim=sim)
    if translated_payload is not None:
        translated_result = dict(execute_console_action(translated_payload, sim=sim))
        translated_result["translated_from_shell_command"] = True
        translated_result["original_command"] = command
        if translated_result.get("ok"):
            translated_result["message"] = (
                f"translated shell_command -> console_action start_simulation: "
                f"{translated_result.get('message') or 'started'}"
            )
        return translated_result

    allowed, reason = command_allowed(command)
    if not allowed:
        return {"ok": False, "message": reason}

    # Check for dangerous shell metacharacters to prevent command injection
    has_dangerous, dangerous_char = has_dangerous_metacharacters(command)
    if has_dangerous:
        return {"ok": False, "message": f"command contains dangerous metacharacter: {dangerous_char}"}

    timeout_sec = float(payload.get("timeout_sec") or 120.0)

    # Use shlex.split to safely parse the command into arguments
    try:
        args = shlex.split(command)
    except ValueError as exc:
        return {"ok": False, "message": f"invalid command syntax: {exc}"}

    # Execute without shell to prevent injection
    proc = subprocess.run(
        args,
        cwd=str(Path.cwd()),
        check=False,
        capture_output=True,
        text=True,
        timeout=max(1.0, timeout_sec),
    )
    stderr_tail = (proc.stderr or "").strip().splitlines()
    stdout_tail = (proc.stdout or "").strip().splitlines()
    detail = ""
    if stderr_tail:
        detail = stderr_tail[-1]
    elif stdout_tail:
        detail = stdout_tail[-1]
    if not detail:
        detail = "no output"
    summary = (
        f"command succeeded (exit 0): {detail}"
        if proc.returncode == 0
        else f"command failed (exit {proc.returncode}): {detail}"
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-6000:],
        "stderr": (proc.stderr or "")[-6000:],
        "message": summary[:400],
    }


def run_shell(cmd: str, *, cwd: Path, timeout_sec: float) -> dict[str, Any]:
    """Run a shell command and return the result.

    Args:
        cmd: The command to run.
        cwd: Working directory.
        timeout_sec: Timeout in seconds.

    Returns:
        Dictionary with ok, returncode, stdout, stderr, and cmd.
    """
    proc = subprocess.run(
        ["bash", "-lc", cmd],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        timeout=max(1.0, timeout_sec),
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-12000:],
        "stderr": (proc.stderr or "")[-12000:],
        "cmd": cmd,
    }


def execute_code_evolve(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute a code evolution action.

    Creates a git worktree, applies patches or runs commands,
    verifies the changes, and optionally commits and pushes.

    Args:
        payload: Code evolution payload with:
            - topic: Topic name for the branch.
            - branch: Optional branch name.
            - patch: Optional git patch to apply.
            - commands: Optional list of commands to run.
            - verify_commands: Commands to verify changes.
            - commit_message: Commit message.
            - auto_push: Whether to push automatically.
            - timeout_sec: Timeout for operations.

    Returns:
        Dictionary with ok, branch, commit, worktree, and logs.
    """
    repo_root = Path.cwd()
    git_root_cmd = run_shell("git rev-parse --show-toplevel", cwd=repo_root, timeout_sec=20)
    if not git_root_cmd["ok"]:
        return {"ok": False, "message": "not a git repository", "detail": git_root_cmd}
    git_root = Path(str(git_root_cmd["stdout"]).strip())

    topic = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(payload.get("topic") or "auto-evolve")).strip("-").lower()
    if not topic:
        topic = "auto-evolve"
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = str(payload.get("branch") or f"ai/{stamp}-{topic}")

    temp_root = Path("/tmp") / f"h2track_ai_evolve_{stamp}_{uuid.uuid4().hex[:8]}"
    worktree = temp_root
    timeout_sec = float(payload.get("timeout_sec") or 600.0)
    patch_text = str(payload.get("patch") or "")
    commands = payload.get("commands")
    if commands is None:
        commands = []
    if not isinstance(commands, list):
        return {"ok": False, "message": "commands must be a list"}
    commands = [str(c).strip() for c in commands if str(c).strip()]
    if not patch_text and not commands:
        return {"ok": False, "message": "code_evolve requires patch or commands"}

    for cmd in commands:
        allowed, reason = command_allowed(cmd)
        if not allowed:
            return {"ok": False, "message": f"code_evolve command denied: {reason}", "command": cmd}

    verify_commands = payload.get("verify_commands")
    if verify_commands is None:
        verify_commands = [
            "source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && "
            "PYTHONPATH=$PWD/src/h2track_tracking:$PYTHONPATH python3 -m pytest -q src/h2track_tracking/test src/h2track_sim/test",
            "source /opt/ros/humble/setup.bash && source /home/user/gaden_ws/install/setup.bash && "
            "colcon build --packages-select h2track_tracking h2track_sim",
        ]
    if not isinstance(verify_commands, list):
        return {"ok": False, "message": "verify_commands must be a list"}
    verify_commands = [str(c).strip() for c in verify_commands if str(c).strip()]

    commit_message = str(payload.get("commit_message") or f"chore(ai): evolve {topic}")
    auto_push = bool(payload.get("auto_push", False))
    logs: list[dict[str, Any]] = []

    try:
        add_out = run_shell(
            f"git worktree add -b {shlex.quote(branch)} {shlex.quote(str(worktree))} HEAD",
            cwd=git_root,
            timeout_sec=60.0,
        )
        logs.append({"step": "worktree_add", **add_out})
        if not add_out["ok"]:
            return {"ok": False, "message": "failed to create worktree", "logs": logs}

        if patch_text:
            apply_proc = subprocess.run(
                ["bash", "-lc", "git apply --whitespace=fix -"],
                cwd=str(worktree),
                check=False,
                capture_output=True,
                text=True,
                input=patch_text,
                timeout=max(1.0, timeout_sec),
            )
            patch_out = {
                "ok": apply_proc.returncode == 0,
                "returncode": apply_proc.returncode,
                "stdout": (apply_proc.stdout or "")[-12000:],
                "stderr": (apply_proc.stderr or "")[-12000:],
                "cmd": "git apply --whitespace=fix -",
            }
            logs.append({"step": "apply_patch", **patch_out})
            if not patch_out["ok"]:
                return {"ok": False, "message": "failed to apply patch", "logs": logs}

        for cmd in commands:
            out = run_shell(cmd, cwd=worktree, timeout_sec=timeout_sec)
            logs.append({"step": "user_command", **out})
            if not out["ok"]:
                return {"ok": False, "message": "code_evolve command failed", "logs": logs}

        for cmd in verify_commands:
            out = run_shell(cmd, cwd=worktree, timeout_sec=timeout_sec)
            logs.append({"step": "verify", **out})
            if not out["ok"]:
                return {"ok": False, "message": "verification failed", "logs": logs}

        status_out = run_shell("git status --porcelain", cwd=worktree, timeout_sec=20.0)
        logs.append({"step": "git_status", **status_out})
        if not status_out["ok"]:
            return {"ok": False, "message": "git status failed", "logs": logs}
        if not str(status_out["stdout"]).strip():
            return {"ok": False, "message": "no code changes to commit", "logs": logs}

        add_all = run_shell("git add -A", cwd=worktree, timeout_sec=30.0)
        logs.append({"step": "git_add", **add_all})
        if not add_all["ok"]:
            return {"ok": False, "message": "git add failed", "logs": logs}

        commit_out = run_shell(f"git commit -m {shlex.quote(commit_message)}", cwd=worktree, timeout_sec=60.0)
        logs.append({"step": "git_commit", **commit_out})
        if not commit_out["ok"]:
            return {"ok": False, "message": "git commit failed", "logs": logs}

        rev_out = run_shell("git rev-parse --short HEAD", cwd=worktree, timeout_sec=20.0)
        logs.append({"step": "git_rev_parse", **rev_out})
        commit = str(rev_out["stdout"]).strip() if rev_out["ok"] else ""

        if auto_push:
            push_out = run_shell(f"git push -u origin {shlex.quote(branch)}", cwd=worktree, timeout_sec=120.0)
            logs.append({"step": "git_push", **push_out})
            if not push_out["ok"]:
                return {"ok": False, "message": "git push failed", "logs": logs, "branch": branch, "commit": commit}

        return {
            "ok": True,
            "branch": branch,
            "commit": commit,
            "worktree": str(worktree),
            "logs": logs,
        }
    finally:
        try:
            run_shell(f"git -C {shlex.quote(str(git_root))} worktree remove --force {shlex.quote(str(worktree))}", cwd=git_root, timeout_sec=30.0)
        except Exception:
            pass
        if worktree.exists():
            try:
                shutil.rmtree(worktree, ignore_errors=True)
            except Exception:
                pass
