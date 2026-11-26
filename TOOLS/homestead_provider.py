import json
import os
import re
from urllib.parse import urlsplit

import homestead as core
from homestead_knowledge import canonical_url, request


def destinations(home, names):
    source = core.read_config(home).get("providers", {})
    core.require(isinstance(source, dict) and 1 <= len(names) <= 3 and len(set(names)) == len(names),
                 "Choose one to three distinct configured providers in priority order.")
    result = []
    for name in names:
        core.require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,19}", name), "Use a valid provider name.")
        provider = source.get(name)
        core.require(isinstance(provider, dict), "A selected provider is not configured.")
        endpoint = canonical_url(provider.get("endpoint"))
        parsed = urlsplit(endpoint)
        core.require(parsed.scheme == "https" and parsed.path.endswith("/chat/completions") and not parsed.query,
                     "Set an exact HTTPS chat completions endpoint.")
        model = provider.get("model")
        core.require(isinstance(model, str) and 1 <= len(model) <= 80 and model.isascii() and model.isprintable(),
                     "Set the exact model ID.")
        key_var = provider.get("key_env")
        core.require(key_var is None or isinstance(key_var, str) and re.fullmatch(r"HOMESTEAD_[A-Z0-9_]{1,50}", key_var),
                     "Use a dedicated HOMESTEAD_ key environment variable.")
        effort = provider.get("reasoning_effort")
        core.require(effort is None or effort in ("low", "medium", "high"), "Use low, medium or high effort.")
        effort_note = f" ({effort} effort)" if effort else ""
        purpose = f"Send to {name} at {endpoint} with {model}{effort_note}"
        core.require(len(purpose) <= 160, "Use a shorter provider name or endpoint.")
        result.append({"name": name, "endpoint": endpoint, "model": model, "purpose": purpose,
                       "reasoning_effort": effort, "key_env": key_var})
    return result


def plan(home, raw, names):
    relative, path = core.guardian_path(home, raw)
    core.require(relative.parts[:2] == ("MEMORY", "OUTBOX") and relative.suffix.lower() == ".json",
                 "Use an exact JSON request within MEMORY/OUTBOX.")
    return {"path": relative.as_posix(), "destinations": [
        {key: dest[key] for key in ("name", "endpoint", "model", "purpose", "reasoning_effort")} for dest in destinations(home, names)
    ]}


def get_messages(raw):
    payload = json.loads(raw, object_pairs_hook=core.unique_json_object, parse_constant=core.reject_json_constant)
    core.require(isinstance(payload, dict) and payload.keys() == {"messages"},
                 "Use a JSON object with only a messages list.")
    messages = payload["messages"]
    core.require(isinstance(messages, list) and 1 <= len(messages) <= 40,
                 "Include one to 40 messages.")
    for message in messages:
        core.require(isinstance(message, dict) and message.keys() == {"role", "content"}
                     and message["role"] in {"system", "user", "assistant"}
                     and isinstance(message["content"], str) and bool(message["content"].strip()),
                     "Use role and plain text content for each message.")
    return messages


def send(home, raw, names, *, fetch=request):
    plan(home, raw, names)
    attempts = []
    initial_sha = None
    for dest in destinations(home, names):
        data, sha = core.guardian_bytes(home, raw, dest["purpose"], 64 * 1024)
        if initial_sha is None:
            initial_sha = sha
        core.require(sha == initial_sha, "The request changed during provider routing.")
        messages = get_messages(data)
        headers = {"Content-Type": "application/json", "User-Agent": "Project-Homestead/1.0"}
        if dest["key_env"]:
            token = os.environ.get(dest["key_env"])
            core.require(token and token.isascii() and token.isprintable() and not any(ch.isspace() for ch in token),
                         "The selected provider's key is missing or invalid.")
            headers["Authorization"] = "Bearer " + token
        payload = {"model": dest["model"], "messages": messages, "stream": False}
        if dest["reasoning_effort"]:
            payload["reasoning_effort"] = dest["reasoning_effort"]
        body = core.packed(payload)
        status, reply, mime = fetch(dest["endpoint"], method="POST", body=body, headers=headers, max_bytes=128 * 1024)
        attempts.append({"provider": dest["name"], "http_status": status})
        if status == 503:
            continue
        if status != 200:
            return {"failed": 1, "attempts": attempts, "reason": "The provider declined or delivery was uncertain."}
        core.require(mime == "application/json", "The provider did not return JSON.")
        answer = json.loads(reply)
        choices = answer.get("choices") if isinstance(answer, dict) else None
        core.require(isinstance(choices, list) and bool(choices) and isinstance(choices[0], dict),
                     "The provider response has no message.")
        message = choices[0].get("message")
        core.require(isinstance(message, dict) and isinstance(message.get("content"), str),
                     "The provider result is not a text reply.")
        return {"failed": 0, "provider": dest["name"], "attempts": attempts, "input_sha256": sha,
                "reply": message["content"]}
    return {"failed": 1, "attempts": attempts, "reason": "Every permitted provider was unavailable."}
