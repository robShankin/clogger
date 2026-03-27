#!/usr/bin/env python3
"""clogger control plane and hook handlers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATE_VERSION = 2
LOG_DIRNAME = "clogger-files"
STATE_DIRNAME = ".clogger-sessions"
ACTIVE_CURRENT_FILENAME = ".active-current"
TRANSCRIPT_TAIL_LINES = 1500
STOP_RETRY_COUNT = 6
STOP_RETRY_DELAY_SECONDS = 0.15

HOME = Path.home()
TRANSCRIPT_ROOTS = (
    HOME / ".codex" / "sessions",
    HOME / ".Codex" / "sessions",
    HOME / ".claude" / "projects",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def today_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def random_suffix(length: int = 6) -> str:
    alphabet = string.ascii_lowercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


def load_json_file(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        return default


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def state_dir(cwd: Path) -> Path:
    return cwd / LOG_DIRNAME / STATE_DIRNAME


def state_path(cwd: Path, session_id: str) -> Path:
    return state_dir(cwd) / f"{session_id}.json"


def active_current_path(cwd: Path) -> Path:
    return cwd / LOG_DIRNAME / ACTIVE_CURRENT_FILENAME


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.replace("\r\n", "\n").replace("\r", "\n")
    return text.rstrip("\n")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}
    if isinstance(loaded, dict):
        return loaded
    return {"payload": loaded}


def walk_values(node: Any):
    yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from walk_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_values(value)


def find_first_string(node: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(node, dict):
        for key in keys:
            value = node.get(key)
            if isinstance(value, str) and value:
                return value
        for value in node.values():
            result = find_first_string(value, keys)
            if result:
                return result
    elif isinstance(node, list):
        for value in node:
            result = find_first_string(value, keys)
            if result:
                return result
    return None


def find_all_named_items(node: Any) -> list[str]:
    names: list[str] = []
    for value in walk_values(node):
        if not isinstance(value, dict):
            continue
        item_type = str(value.get("type", "")).lower()
        if item_type in {"input_image", "input_file", "image", "file", "local_image", "attachment"}:
            for key in ("filename", "name", "path"):
                raw = value.get(key)
                if isinstance(raw, str) and raw:
                    names.append(Path(raw).name)
                    break
    return names


def flatten_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "")).lower()
            if item_type in {"input_text", "text", "output_text"}:
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
                    continue
            if item_type in {"input_image", "input_file", "image", "file", "local_image", "attachment"}:
                for key in ("filename", "name", "path"):
                    raw = item.get(key)
                    if isinstance(raw, str) and raw:
                        parts.append(f"[file: {Path(raw).name}]")
                        break
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        return flatten_content(content.get("content"))
    return ""


def extract_payload_timestamp(payload: dict[str, Any]) -> str:
    for key in ("timestamp", "ts", "created_at", "createdAt", "event_time"):
        value = find_first_string(payload, (key,))
        if value:
            return value
    return now_iso()


def extract_session_id(payload: dict[str, Any]) -> str | None:
    return find_first_string(payload, ("session_id", "sessionId", "id"))


def extract_cwd(payload: dict[str, Any]) -> Path | None:
    raw = find_first_string(payload, ("cwd", "workspace", "workspace_path", "project_path"))
    if not raw:
        return None
    return Path(raw).expanduser()


def extract_user_text_from_hook_payload(payload: dict[str, Any]) -> str:
    for key in ("prompt", "text", "message"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)

    content = payload.get("content")
    text = flatten_content(content)
    if text:
        return normalize_text(text)

    for key in ("message", "prompt", "payload"):
        value = payload.get(key)
        text = flatten_content(value)
        if text:
            return normalize_text(text)

    names = find_all_named_items(payload)
    if names:
        return "\n".join(f"[file: {name}]" for name in names)

    return ""


def stringify_simple_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return ""
    return json.dumps(value, sort_keys=True)


def extract_tag_text(text: str, tag: str) -> str | None:
    start_marker = f"<{tag}>"
    end_marker = f"</{tag}>"
    start = text.find(start_marker)
    end = text.find(end_marker)
    if start == -1 or end == -1 or end < start:
        return None
    value = text[start + len(start_marker) : end].strip()
    return value or None


def parse_command_markup(text: str) -> dict[str, str] | None:
    normalized = normalize_text(text)
    if "<command-message>" not in normalized or "<command-name>" not in normalized:
        return None

    command_name = extract_tag_text(normalized, "command-name")
    if not command_name:
        return None

    command_args = extract_tag_text(normalized, "command-args") or ""
    return {
        "name": command_name,
        "args": command_args,
    }


def extract_elicitation_prompt(payload: dict[str, Any]) -> str:
    for key in ("prompt", "message", "question", "description"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_text(value)
    return ""


def extract_elicitation_titles(payload: dict[str, Any]) -> dict[str, str]:
    schema = payload.get("requested_schema")
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    titles: dict[str, str] = {}
    for key, spec in properties.items():
        if not isinstance(spec, dict):
            continue
        title = spec.get("title")
        if isinstance(title, str) and title.strip():
            titles[key] = normalize_text(title)
    return titles


def format_elicitation_selection(payload: dict[str, Any], state: dict[str, Any]) -> str:
    action = payload.get("action")
    if isinstance(action, str) and action != "accept":
        return action

    content = payload.get("content")
    titles = state.get("pending_elicitation", {}).get("titles", {})
    if isinstance(content, dict) and content:
        parts: list[str] = []
        for key, value in content.items():
            label = titles.get(key) or key
            rendered = stringify_simple_value(value)
            if rendered:
                parts.append(f"{label} -> {rendered}")
        return "\n".join(parts)

    rendered = stringify_simple_value(content)
    if rendered:
        question = state.get("pending_elicitation", {}).get("prompt") or "response"
        return f"{question} -> {rendered}"

    return ""


def parse_session_identity(path: Path) -> dict[str, Any] | None:
    try:
        with path.open() as handle:
            for _ in range(20):
                line = handle.readline()
                if not line:
                    break
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if entry.get("type") == "session_meta":
                    payload = entry.get("payload", {})
                    session_id = payload.get("id")
                    cwd = payload.get("cwd")
                    if isinstance(session_id, str) and isinstance(cwd, str):
                        label = "CODEX"
                        origin = str(payload.get("originator", "")).lower()
                        if "claude" in origin or ".claude" in str(path):
                            label = "CLAUDE"
                        return {
                            "session_id": session_id,
                            "cwd": str(Path(cwd).expanduser()),
                            "transcript_path": str(path),
                            "agent_label": label,
                        }

                cwd = entry.get("cwd")
                session_id = entry.get("sessionId") or entry.get("session_id")
                if isinstance(cwd, str) and isinstance(session_id, str):
                    label = "CLAUDE" if ".claude" in str(path) else "CODEX"
                    return {
                        "session_id": session_id,
                        "cwd": str(Path(cwd).expanduser()),
                        "transcript_path": str(path),
                        "agent_label": label,
                    }
    except FileNotFoundError:
        return None

    return None


def candidate_transcript_paths() -> list[Path]:
    candidates: list[Path] = []
    for root in TRANSCRIPT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            candidates.append((stat.st_mtime, path))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [path for _, path in candidates]


def discover_session_for_cwd(cwd: Path) -> dict[str, Any] | None:
    cwd = cwd.resolve()
    for path in candidate_transcript_paths():
        identity = parse_session_identity(path)
        if not identity:
            continue
        if Path(identity["cwd"]).resolve() == cwd:
            return identity
    return None


def find_transcript_by_session_id(session_id: str) -> Path | None:
    for root in TRANSCRIPT_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob(f"*{session_id}*.jsonl"):
            return path
    return None


def read_jsonl_tail(path: Path, max_lines: int = TRANSCRIPT_TAIL_LINES) -> list[dict[str, Any]]:
    lines: deque[str] = deque(maxlen=max_lines)
    with path.open() as handle:
        for line in handle:
            if line.strip():
                lines.append(line)

    parsed: list[dict[str, Any]] = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            parsed.append(entry)
    return parsed


def parse_user_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry.get("isMeta") is True:
        return None

    if entry.get("type") == "response_item":
        payload = entry.get("payload", {})
        if payload.get("type") == "message" and payload.get("role") == "user":
            text = flatten_content(payload.get("content"))
            if text:
                return {"text": normalize_text(text), "timestamp": entry.get("timestamp") or now_iso()}

    if entry.get("type") == "user":
        message = entry.get("message", {})
        if message.get("role") == "user":
            text = flatten_content(message.get("content"))
            if text:
                if is_internal_skill_text(text) or is_clogger_command_text(text):
                    return None
                return {"text": normalize_text(text), "timestamp": entry.get("timestamp") or now_iso()}

    return None


def is_internal_skill_text(text: str) -> bool:
    normalized = normalize_text(text)
    return normalized.startswith("Base directory for this skill:")


def is_clogger_command_text(text: str) -> bool:
    parsed = parse_command_markup(text)
    return parsed is not None and parsed.get("name") == "/clogger"


def parse_assistant_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    if entry.get("type") == "response_item":
        payload = entry.get("payload", {})
        if payload.get("type") == "message" and payload.get("role") == "assistant":
            if payload.get("phase") not in {None, "final_answer"}:
                return None
            text = flatten_content(payload.get("content"))
            if text:
                return {
                    "turn_id": None,
                    "assistant_text": normalize_text(text),
                    "assistant_timestamp": entry.get("timestamp") or now_iso(),
                }

    if entry.get("type") == "assistant":
        message = entry.get("message", {})
        if message.get("role") != "assistant":
            return None
        stop_reason = message.get("stop_reason")
        if stop_reason not in {"end_turn", None}:
            return None
        text = flatten_content(message.get("content"))
        if text:
            return {
                "turn_id": None,
                "assistant_text": normalize_text(text),
                "assistant_timestamp": entry.get("timestamp") or now_iso(),
            }

    return None


def extract_ask_user_question_prompt(entry: dict[str, Any]) -> str | None:
    if entry.get("type") != "assistant":
        return None
    message = entry.get("message", {})
    if message.get("role") != "assistant":
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    prompts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "tool_use" or item.get("name") != "AskUserQuestion":
            continue
        questions = item.get("input", {}).get("questions", [])
        if not isinstance(questions, list):
            continue
        for question in questions:
            if isinstance(question, dict):
                text = question.get("question")
                if isinstance(text, str) and text.strip():
                    prompts.append(normalize_text(text))
    if prompts:
        return "\n".join(prompts)
    return None


def extract_ask_user_question_selection(entry: dict[str, Any]) -> str | None:
    if entry.get("type") != "user":
        return None

    tool_result = entry.get("toolUseResult")
    if not isinstance(tool_result, dict):
        return None

    questions = tool_result.get("questions", [])
    answers = tool_result.get("answers", {})
    if not isinstance(questions, list) or not isinstance(answers, dict):
        return None

    parts: list[str] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_text = question.get("question")
        if not isinstance(question_text, str) or not question_text.strip():
            continue
        answer = answers.get(question_text)
        rendered = stringify_simple_value(answer)
        if rendered:
            parts.append(f"{normalize_text(question_text)} -> {rendered}")

    if parts:
        return "\n".join(parts)
    return None


def timestamp_in_window(value: str | None, min_timestamp: str | None = None, max_timestamp: str | None = None) -> bool:
    parsed_value = parse_timestamp(value)
    if parsed_value is None:
        return True

    parsed_min = parse_timestamp(min_timestamp)
    if parsed_min is not None and parsed_value < parsed_min:
        return False

    parsed_max = parse_timestamp(max_timestamp)
    if parsed_max is not None and parsed_value > parsed_max:
        return False

    return True


def extract_recent_ask_user_question_details(
    entries: list[dict[str, Any]],
    min_timestamp: str | None = None,
    max_timestamp: str | None = None,
) -> dict[str, Any]:
    prompt: str | None = None
    prompt_timestamp: str | None = None
    selection: str | None = None
    selection_timestamp: str | None = None

    for index in range(len(entries) - 1, -1, -1):
        entry = entries[index]
        entry_timestamp = entry.get("timestamp")
        if not timestamp_in_window(entry_timestamp, min_timestamp=min_timestamp, max_timestamp=max_timestamp):
            continue
        if selection is None:
            parsed_selection = extract_ask_user_question_selection(entry)
            if parsed_selection:
                selection = parsed_selection
                selection_timestamp = entry_timestamp or now_iso()
                continue
        if prompt is None:
            parsed_prompt = extract_ask_user_question_prompt(entry)
            if parsed_prompt:
                prompt = parsed_prompt
                prompt_timestamp = entry_timestamp or now_iso()
                if selection is not None:
                    break

    result: dict[str, Any] = {}
    if prompt:
        result["elicitation_prompt"] = prompt
        result["elicitation_timestamp"] = prompt_timestamp
    if selection:
        result["elicitation_selection"] = selection
        result["elicitation_selection_timestamp"] = selection_timestamp
    return result


def parse_latest_turn(entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    latest_task_index: int | None = None
    latest_task: dict[str, Any] | None = None

    for index in range(len(entries) - 1, -1, -1):
        entry = entries[index]
        if entry.get("type") != "event_msg":
            continue
        payload = entry.get("payload", {})
        if payload.get("type") != "task_complete":
            continue
        message = payload.get("last_agent_message")
        if not isinstance(message, str) or not message.strip():
            continue
        latest_task_index = index
        latest_task = {
            "turn_id": payload.get("turn_id"),
            "assistant_text": normalize_text(message),
            "assistant_timestamp": entry.get("timestamp") or now_iso(),
        }
        break

    if latest_task and latest_task_index is not None:
        for index in range(latest_task_index - 1, -1, -1):
            user_entry = parse_user_entry(entries[index])
            if user_entry:
                latest_task.update(
                    {
                        "user_text": user_entry["text"],
                        "user_timestamp": user_entry["timestamp"],
                    }
                )
                return latest_task
        return latest_task

    latest_assistant: dict[str, Any] | None = None
    latest_assistant_index: int | None = None
    for index in range(len(entries) - 1, -1, -1):
        parsed = parse_assistant_entry(entries[index])
        if parsed:
            latest_assistant = parsed
            latest_assistant_index = index
            break

    if latest_assistant and latest_assistant_index is not None:
        elicitation_prompt: str | None = None
        elicitation_selection: str | None = None
        elicitation_prompt_timestamp: str | None = None
        elicitation_selection_timestamp: str | None = None
        for index in range(latest_assistant_index - 1, -1, -1):
            if elicitation_selection is None:
                selection = extract_ask_user_question_selection(entries[index])
                if selection:
                    elicitation_selection = selection
                    elicitation_selection_timestamp = entries[index].get("timestamp") or now_iso()
                    continue
            if elicitation_prompt is None:
                prompt = extract_ask_user_question_prompt(entries[index])
                if prompt:
                    elicitation_prompt = prompt
                    elicitation_prompt_timestamp = entries[index].get("timestamp") or now_iso()
                    continue
            user_entry = parse_user_entry(entries[index])
            if user_entry:
                latest_assistant.update(
                    {
                        "user_text": user_entry["text"],
                        "user_timestamp": user_entry["timestamp"],
                    }
                )
                break
        if elicitation_prompt:
            latest_assistant["elicitation_prompt"] = elicitation_prompt
            latest_assistant["elicitation_timestamp"] = elicitation_prompt_timestamp
        if elicitation_selection:
            latest_assistant["elicitation_selection"] = elicitation_selection
            latest_assistant["elicitation_selection_timestamp"] = elicitation_selection_timestamp
        return latest_assistant

    return None


def load_session_state(cwd: Path, session_id: str) -> dict[str, Any] | None:
    state = load_json_file(state_path(cwd, session_id), default=None)
    if not isinstance(state, dict):
        return None
    return state


def save_session_state(cwd: Path, session_id: str, state: dict[str, Any]) -> None:
    write_json_file(state_path(cwd, session_id), state)


def write_active_current(cwd: Path, log_file: Path) -> None:
    active_current_path(cwd).parent.mkdir(parents=True, exist_ok=True)
    active_current_path(cwd).write_text(str(log_file) + "\n")


def clear_active_current_if_matches(cwd: Path, log_file: Path) -> None:
    path = active_current_path(cwd)
    try:
        current = path.read_text().strip()
    except FileNotFoundError:
        return
    if current == str(log_file):
        path.write_text("")


def write_labeled_entry(handle, timestamp: str, label: str, text: str) -> None:
    lines = normalize_text(text).split("\n")
    if not lines:
        lines = [""]
    handle.write(f"[{timestamp}] {label}: {lines[0]}\n")
    for line in lines[1:]:
        handle.write(f"{line}\n")


def append_exchange(log_file: Path, user_timestamp: str, user_text: str, assistant_timestamp: str, assistant_label: str, assistant_text: str) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as handle:
        write_labeled_entry(handle, user_timestamp, "USER", user_text)
        write_labeled_entry(handle, assistant_timestamp, assistant_label, assistant_text)
        handle.write("---\n")


def append_exchange_with_elicitation(
    log_file: Path,
    user_timestamp: str,
    user_text: str,
    assistant_timestamp: str,
    assistant_label: str,
    assistant_text: str,
    elicitation_prompt: str | None = None,
    elicitation_timestamp: str | None = None,
    selected_text: str | None = None,
    selected_timestamp: str | None = None,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as handle:
        write_labeled_entry(handle, user_timestamp, "USER", user_text)
        if elicitation_prompt:
            write_labeled_entry(
                handle,
                elicitation_timestamp or assistant_timestamp,
                assistant_label,
                elicitation_prompt,
            )
        if selected_text:
            write_labeled_entry(
                handle,
                selected_timestamp or assistant_timestamp,
                "SELECTED",
                selected_text,
            )
        write_labeled_entry(handle, assistant_timestamp, assistant_label, assistant_text)
        handle.write("---\n")


def start_session(cwd: Path) -> str:
    identity = discover_session_for_cwd(cwd)
    if not identity:
        return "clogger could not detect the current session"

    log_dir = cwd / LOG_DIRNAME
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"clogger_{today_stamp()}_{random_suffix()}.txt"

    activation_reply = f"clogger on -> {log_file.name}"

    state = {
        "version": STATE_VERSION,
        "enabled": True,
        "session_id": identity["session_id"],
        "cwd": str(cwd),
        "transcript_path": identity["transcript_path"],
        "log_file": str(log_file),
        "agent_label": identity["agent_label"],
        "pending_user": None,
        "pending_elicitation": None,
        "pending_elicitation_result": None,
        "last_logged_turn_id": None,
        "last_logged_exchange_hash": sha256_text(f"/clogger\n---\n{activation_reply}"),
    }
    save_session_state(cwd, identity["session_id"], state)
    write_active_current(cwd, log_file)

    append_exchange(
        log_file=log_file,
        user_timestamp=now_iso(),
        user_text="/clogger",
        assistant_timestamp=now_iso(),
        assistant_label=identity["agent_label"],
        assistant_text=activation_reply,
    )

    return activation_reply


def resume_session(cwd: Path) -> str:
    identity = discover_session_for_cwd(cwd)
    if not identity:
        return "clogger could not detect the current session"

    try:
        active_log = active_current_path(cwd).read_text().strip()
    except FileNotFoundError:
        active_log = ""

    if not active_log:
        return "no active session to resume - use /clogger to start one"

    log_file = Path(active_log)
    state = {
        "version": STATE_VERSION,
        "enabled": True,
        "session_id": identity["session_id"],
        "cwd": str(cwd),
        "transcript_path": identity["transcript_path"],
        "log_file": str(log_file),
        "agent_label": identity["agent_label"],
        "pending_user": None,
        "pending_elicitation": None,
        "pending_elicitation_result": None,
        "last_logged_turn_id": None,
        "last_logged_exchange_hash": None,
    }
    save_session_state(cwd, identity["session_id"], state)
    write_active_current(cwd, log_file)
    return f"clogger resumed -> {log_file.name}"


def stop_session(cwd: Path) -> str:
    identity = discover_session_for_cwd(cwd)
    if not identity:
        return "clogger off"

    state = load_session_state(cwd, identity["session_id"])
    if state:
        log_file = Path(state.get("log_file", ""))
        if log_file:
            clear_active_current_if_matches(cwd, log_file)
        try:
            state_path(cwd, identity["session_id"]).unlink()
        except FileNotFoundError:
            pass

    return "clogger off"


def status_session(cwd: Path) -> str:
    identity = discover_session_for_cwd(cwd)
    if identity:
        state = load_session_state(cwd, identity["session_id"])
        if state and state.get("enabled") and state.get("log_file"):
            return f"clogger on -> {Path(state['log_file']).name}"

    try:
        active_log = active_current_path(cwd).read_text().strip()
    except FileNotFoundError:
        active_log = ""

    if active_log:
        return f"clogger paused -> {Path(active_log).name} (run /clogger resume to reattach)"
    return "clogger off"


def load_state_from_hook_payload(payload: dict[str, Any]) -> tuple[Path, str, dict[str, Any]] | None:
    cwd = extract_cwd(payload)
    session_id = extract_session_id(payload)
    if cwd is None or session_id is None:
        return None
    state = load_session_state(cwd, session_id)
    if not state or not state.get("enabled"):
        return None
    return cwd, session_id, state


def hook_user_prompt_submit(payload: dict[str, Any]) -> int:
    loaded = load_state_from_hook_payload(payload)
    if not loaded:
        return 0

    cwd, session_id, state = loaded
    text = extract_user_text_from_hook_payload(payload)
    if not text:
        return 0
    if is_internal_skill_text(text) or is_clogger_command_text(text):
        return 0

    state["pending_user"] = {
        "timestamp": extract_payload_timestamp(payload),
        "text": text,
    }
    save_session_state(cwd, session_id, state)
    return 0


def hook_elicitation(payload: dict[str, Any]) -> int:
    loaded = load_state_from_hook_payload(payload)
    if not loaded:
        return 0

    cwd, session_id, state = loaded
    prompt = extract_elicitation_prompt(payload)
    if not prompt:
        prompt = "[Asked user a question]"

    state["pending_elicitation"] = {
        "timestamp": extract_payload_timestamp(payload),
        "prompt": prompt,
        "titles": extract_elicitation_titles(payload),
        "elicitation_id": payload.get("elicitation_id"),
    }
    save_session_state(cwd, session_id, state)
    return 0


def hook_elicitation_result(payload: dict[str, Any]) -> int:
    loaded = load_state_from_hook_payload(payload)
    if not loaded:
        return 0

    cwd, session_id, state = loaded
    selection = format_elicitation_selection(payload, state)
    if selection:
        state["pending_elicitation_result"] = {
            "timestamp": extract_payload_timestamp(payload),
            "text": selection,
            "elicitation_id": payload.get("elicitation_id"),
            "action": payload.get("action"),
        }
        save_session_state(cwd, session_id, state)
    return 0


def hook_stop(payload: dict[str, Any]) -> int:
    loaded = load_state_from_hook_payload(payload)
    if not loaded:
        return 0

    cwd, session_id, state = loaded
    transcript_path = Path(state.get("transcript_path", "")) if state.get("transcript_path") else None
    if transcript_path is None or not transcript_path.exists():
        discovered = find_transcript_by_session_id(session_id)
        if discovered is None:
            return 0
        transcript_path = discovered
        state["transcript_path"] = str(transcript_path)

    pending_user = state.get("pending_user") or {}
    pending_elicitation = state.get("pending_elicitation") or {}
    pending_elicitation_result = state.get("pending_elicitation_result") or {}
    assistant_text_from_payload = isinstance(payload.get("last_assistant_message"), str)
    assistant_text = normalize_text(payload.get("last_assistant_message") if assistant_text_from_payload else "")
    current_user_timestamp = pending_user.get("timestamp")
    latest_turn: dict[str, Any] | None = None
    transcript_entries: list[dict[str, Any]] = []

    for _ in range(STOP_RETRY_COUNT):
        transcript_entries = read_jsonl_tail(transcript_path)
        latest_turn = parse_latest_turn(transcript_entries)
        if latest_turn:
            if not assistant_text and latest_turn.get("assistant_text"):
                assistant_text = normalize_text(latest_turn["assistant_text"])
            has_elicitation_details = bool(
                latest_turn.get("elicitation_prompt") or latest_turn.get("elicitation_selection")
            )
            if assistant_text and (has_elicitation_details or not pending_elicitation and not pending_elicitation_result):
                break
            if assistant_text and not has_elicitation_details:
                # For normal turns there may be no elicitation metadata to wait for.
                break
        elif assistant_text:
            break
        time.sleep(STOP_RETRY_DELAY_SECONDS)

    if not assistant_text:
        save_session_state(cwd, session_id, state)
        return 0

    latest_turn_is_current = bool(
        latest_turn
        and timestamp_in_window(
            latest_turn.get("user_timestamp"),
            min_timestamp=current_user_timestamp,
            max_timestamp=extract_payload_timestamp(payload),
        )
    )

    if latest_turn and latest_turn_is_current:
        if latest_turn.get("elicitation_prompt"):
            pending_elicitation = {
                "prompt": latest_turn.get("elicitation_prompt"),
                "timestamp": latest_turn.get("elicitation_timestamp"),
            }
        if latest_turn.get("elicitation_selection"):
            pending_elicitation_result = {
                "text": latest_turn.get("elicitation_selection"),
                "timestamp": latest_turn.get("elicitation_selection_timestamp"),
            }

    fallback_min_timestamp = current_user_timestamp or (latest_turn or {}).get("user_timestamp")
    fallback_max_timestamp = extract_payload_timestamp(payload)
    if transcript_entries and not pending_elicitation and not pending_elicitation_result and fallback_min_timestamp:
        extracted = extract_recent_ask_user_question_details(
            transcript_entries,
            min_timestamp=fallback_min_timestamp,
            max_timestamp=fallback_max_timestamp,
        )
        if extracted.get("elicitation_prompt"):
            pending_elicitation = {
                "prompt": extracted.get("elicitation_prompt"),
                "timestamp": extracted.get("elicitation_timestamp"),
            }
        if extracted.get("elicitation_selection"):
            pending_elicitation_result = {
                "text": extracted.get("elicitation_selection"),
                "timestamp": extracted.get("elicitation_selection_timestamp"),
            }

    user_text = normalize_text(pending_user.get("text") or (latest_turn or {}).get("user_text") or "")
    if not user_text:
        save_session_state(cwd, session_id, state)
        return 0

    exchange_hash = sha256_text(f"{user_text}\n---\n{assistant_text}")
    turn_id = (latest_turn or {}).get("turn_id")
    if turn_id and turn_id == state.get("last_logged_turn_id"):
        return 0
    if exchange_hash == state.get("last_logged_exchange_hash"):
        return 0

    append_exchange_with_elicitation(
        log_file=Path(state["log_file"]),
        user_timestamp=pending_user.get("timestamp") or (latest_turn or {}).get("user_timestamp") or now_iso(),
        user_text=user_text,
        assistant_timestamp=extract_payload_timestamp(payload)
        if assistant_text_from_payload
        else (latest_turn or {}).get("assistant_timestamp") or extract_payload_timestamp(payload),
        assistant_label=state.get("agent_label", "CODEX"),
        assistant_text=assistant_text,
        elicitation_prompt=pending_elicitation.get("prompt"),
        elicitation_timestamp=pending_elicitation.get("timestamp"),
        selected_text=pending_elicitation_result.get("text"),
        selected_timestamp=pending_elicitation_result.get("timestamp"),
    )

    state["pending_user"] = None
    state["pending_elicitation"] = None
    state["pending_elicitation_result"] = None
    state["last_logged_turn_id"] = turn_id
    state["last_logged_exchange_hash"] = exchange_hash
    save_session_state(cwd, session_id, state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control clogger and run hook handlers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("start")
    subparsers.add_parser("resume")
    subparsers.add_parser("stop")
    subparsers.add_parser("status")
    subparsers.add_parser("hook-user-prompt-submit")
    subparsers.add_parser("hook-elicitation")
    subparsers.add_parser("hook-elicitation-result")
    subparsers.add_parser("hook-stop")
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cwd = Path.cwd().resolve()

    if args.command == "start":
        print(start_session(cwd))
        return 0
    if args.command == "resume":
        print(resume_session(cwd))
        return 0
    if args.command == "stop":
        print(stop_session(cwd))
        return 0
    if args.command == "status":
        print(status_session(cwd))
        return 0
    if args.command == "hook-user-prompt-submit":
        return hook_user_prompt_submit(read_stdin_json())
    if args.command == "hook-elicitation":
        return hook_elicitation(read_stdin_json())
    if args.command == "hook-elicitation-result":
        return hook_elicitation_result(read_stdin_json())
    if args.command == "hook-stop":
        return hook_stop(read_stdin_json())

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
