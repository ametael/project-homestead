import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import secrets
import stat
import sys
from urllib.parse import unquote
import uuid

VERSION = "0.3.1"
LIMIT_FILES = 10000
LIMIT_BYTES = 512 * 1024 * 1024
TEXT_LIMIT = 256 * 1024
PAGE_LIMIT = 4096
DATA_ROOTS = {"PERSONA", "MEMORY", "PROJECTS", "ASSETS"}
CORE_ROOTS = {"TOOLS", "OPERATIONS", "TEMPLATES", "KNOWLEDGE"}
CORE_FILES = {"AGENTS.md", "START_HERE.md", "CONTEXT_MAP.md", "README.md", "LICENSE", ".gitignore"}
EVENT_HOOK = None


class SafetyError(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def event(name):
    if EVENT_HOOK is not None:
        EVENT_HOOK(name)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def packed(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def clean_relative(raw):
    require(isinstance(raw, str) and raw.strip() == raw and bool(raw), "Use a nonempty exact relative path.")
    raw = raw.replace("\\", "/")
    require(not raw.startswith("/") and not ntpath.splitdrive(raw)[0], "Absolute and drive-relative paths are refused.")
    parts = raw.split("/")
    require(all(p and p not in {".", ".."} for p in parts), "Empty, dot, and parent path components are refused.")
    for part in parts:
        require(not any(ord(c) < 32 or c in ':*?<>|"'
                        for c in part), "Reserved path characters are refused.")
        require(not part.endswith((".", " ")) and not ntpath.isreserved(part), "Reserved path names are refused.")
    return Path(*parts)


def check_node(path):
    s = path.lstat()
    require(not stat.S_ISLNK(s.st_mode) and not (getattr(s, "st_file_attributes", 0) & 0x400),
            "Links, junctions, and reparse points are refused.")
    require(stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode), "Special files are refused.")
    if stat.S_ISREG(s.st_mode):
        require(s.st_nlink == 1, "Multiply linked files are refused.")
    return s


def check_chain(path):
    for p in reversed((path, *path.parents)):
        if os.path.lexists(p):
            check_node(p)


def no_replace(source, destination):
    require(os.name == "nt", "File mutation is currently supported on Windows only.")
    check_chain(source)
    check_chain(destination.parent)
    require(not os.path.lexists(destination), "Destination already exists; nothing overwritten.")
    require(source.stat().st_dev == destination.parent.stat().st_dev, "Cross-filesystem moves are refused.")
    os.rename(source, destination)


def write_json_new(path, value):
    check_chain(path.parent)
    with path.open("xb") as f:
        f.write(packed(value) + b"\n")
        f.flush()
        os.fsync(f.fileno())


def record_state(path, value):
    check_chain(path)
    tmp = path.parent / ("record-" + uuid.uuid4().hex + ".tmp")
    write_json_new(tmp, value)
    os.replace(tmp, path)


def hash_file(path):
    before = check_node(path)
    require(stat.S_ISREG(before.st_mode), "A regular file is required.")
    require(before.st_size <= LIMIT_BYTES, "File exceeds the safety size limit.")
    h = hashlib.sha256()
    with path.open("rb") as f:
        opened = os.fstat(f.fileno())
        require((opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino), "File changed while opening.")
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
        after = os.fstat(f.fileno())
    latest = check_node(path)
    key = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_nlink)
    require(key(before) == key(opened) == key(after) == key(latest), "File changed while reading.")
    require(before.st_ctime_ns == latest.st_ctime_ns and opened.st_ctime_ns == after.st_ctime_ns,
            "File metadata changed while reading.")
    return h.hexdigest()


def inventory(path):
    entries = []
    total = 0
    device = check_node(path).st_dev

    def visit(p, relative):
        nonlocal total
        s = check_node(p)
        require(s.st_dev == device, "Filesystem boundary inside target is refused.")
        require(p.name.casefold() != ".git", "Git metadata inside a target is protected.")
        item = {"path": relative, "kind": "dir" if stat.S_ISDIR(s.st_mode) else "file"}
        if item["kind"] == "file":
            total += s.st_size
            require(total <= LIMIT_BYTES, "Target exceeds the safety size limit.")
            item.update(bytes=s.st_size, sha256=hash_file(p))
        item["identity"] = [s.st_dev, s.st_ino, s.st_mtime_ns, s.st_ctime_ns]
        entries.append(item)
        require(len(entries) <= LIMIT_FILES, "Target exceeds the safety entry limit.")
        if item["kind"] == "dir":
            for child in sorted(p.iterdir(), key=lambda x: x.name):
                visit(child, child.relative_to(path).as_posix())

    visit(path, ".")
    return entries


def content_key(entries):
    return [{k: v for k, v in e.items() if k != "identity"} for e in entries]


def copy_checked(source, destination, expected):
    require(not os.path.lexists(destination), "Copy destination already exists.")
    require(inventory(source) == expected, "Source changed after preview.")
    for item in expected:
        src = source if item["path"] == "." else source / item["path"]
        dst = destination if item["path"] == "." else destination / item["path"]
        check_chain(src)
        check_chain(dst.parent)
        if item["kind"] == "dir":
            dst.mkdir(exist_ok=False)
        else:
            with src.open("rb") as f, dst.open("xb") as g:
                opened = os.fstat(f.fileno())
                require([opened.st_dev, opened.st_ino] == item["identity"][:2], "Source identity changed.")
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    g.write(chunk)
                    h.update(chunk)
                g.flush()
                os.fsync(g.fileno())
            require(h.hexdigest() == item["sha256"], "Copy differs from the preview.")
    require(content_key(inventory(destination)) == content_key(expected), "Retained copy verification failed.")
    require(inventory(source) == expected, "Source changed during capture.")


class Home:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        require(not str(absolute).startswith("\\\\"), "Network homes are not supported.")
        check_chain(absolute)
        self.root = absolute.resolve(strict=True)
        require(self.root != Path(self.root.anchor), "A filesystem root cannot be a VHD home.")
        for name in ("START_HERE.md", "CONTEXT_MAP.md", "TEMPLATES/IDENTITY.md"):
            require(self.path(name).is_file(), "Not a complete VHD home.")

    def path(self, raw, exists=False):
        relative = clean_relative(raw)
        require(all(p.casefold() != ".git" for p in relative.parts), "Git metadata is protected.")
        target = self.root / relative
        check_chain(target)
        require(target.resolve(strict=False).is_relative_to(self.root), "Path is outside the VHD home.")
        if exists:
            require(target.exists(), "Selected path does not exist.")
        return target

    def target(self, raw, action, allow_core=False):
        relative = clean_relative(raw)
        p = self.path(raw, exists=True)
        first = relative.parts[0]
        if first in DATA_ROOTS:
            require(len(relative.parts) > 1, "Local data roots are protected.")
        else:
            is_core_file = (len(relative.parts) == 1 and first in CORE_FILES) or (
                first in CORE_ROOTS and len(relative.parts) > 1 and p.is_file())
            require(action in {"snapshot", "update", "restore"} and allow_core and is_core_file,
                    "Target is protected or outside the permitted data areas.")
        return p

    def store(self, area):
        p = self.path(area)
        p.mkdir(exist_ok=True)
        check_chain(p)
        return p

    @contextmanager
    def lock(self):
        require(os.name == "nt", "File mutation is currently supported on Windows only.")
        base = self.store(".recycle")
        lock = base / "operation.lock"
        try:
            write_json_new(lock, {"pid": os.getpid(), "created": stamp()})
        except FileExistsError:
            raise SafetyError("Another operation or stale lock exists. Inspect it; do not automatically remove it.")
        try:
            yield
        finally:
            check_node(lock)
            lock.unlink()

    def setup(self):
        with self.lock():
            for name in sorted(DATA_ROOTS | {"ARCHIVE"}):
                self.store(name)
            pairs = {
                "PERSONA/IDENTITY.md": "TEMPLATES/IDENTITY.md",
                "MEMORY/INDEX.md": "TEMPLATES/MEMORY_INDEX.md",
                "MEMORY/HANDOFF.md": "TEMPLATES/HOME_HANDOFF.md",
                "PERSONA/HANDOFF.md": "TEMPLATES/OWNER_HANDOFF.md",
                "PERSONA/PROGRESSION/EXP.md": "TEMPLATES/EXP.md",
            }
            created = []
            for target, template in pairs.items():
                dst = self.path(target)
                if not dst.exists():
                    data = self.path(template, exists=True).read_bytes()
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    with dst.open("xb") as f:
                        f.write(data)
                    created.append(target)
                else:
                    require(dst.is_file(), "An existing local identity/memory target is not a file.")
            return {"created": created, "existing_files": "preserved"}

    def transaction(self, identifier):
        require(bool(re.fullmatch(r"[0-9a-f]{32}", identifier)), "Invalid operation ID.")
        found = []
        for area in ("ARCHIVE", ".recycle/items"):
            file = self.path(f"{area}/{identifier}/record.json")
            if file.exists():
                require(file.stat().st_size <= 4 * 1024 * 1024, "Oversized recovery record.")
                data = json.loads(file.read_text(encoding="utf-8"))
                require(data.get("id") == identifier and data.get("home") == str(self.root), "Recovery record mismatch.")
                require(data.get("action") in {"snapshot", "update", "archive", "recycle", "restore"}, "Invalid recovery action.")
                found.append((file.parent, data))
        require(len(found) == 1, "Recovery record missing or ambiguous.")
        return found[0]

    def plan(self, action, target=None, source=None, identifier=None, reason="", allow_core=False):
        require(reason.strip() and len(reason) <= 500, "Provide a reason of 1 to 500 characters.")
        with self.lock():
            plan = {"schema": 1, "id": uuid.uuid4().hex, "home": str(self.root),
                    "action": action, "reason": reason, "created": stamp(), "allow_core": bool(allow_core)}
            if action == "restore":
                folder, previous = self.transaction(identifier)
                require(previous["action"] != "restore", "Restore from the original retained operation.")
                target = previous["target"]
                dst = self.path(target)
                relative = clean_relative(target)
                if relative.parts[0] not in DATA_ROOTS:
                    require(allow_core, "Core restore requires --allow-core.")
                require(len(relative.parts) > 1 or relative.parts[0] in CORE_FILES, "Root restore is refused.")
                require(not dst.exists(), "Restore target exists. Archive/recycle the active version first.")
                require(dst.parent.is_dir(), "Restore parent is missing; restore it explicitly first.")
                payload = folder / "payload"
                require(payload.exists(), "Retained payload is missing; inspect the operation state.")
                actual = inventory(payload)
                require(content_key(actual) == previous["content"], "Retained payload differs from its record.")
                plan.update(target=target, restore_id=identifier, fingerprint=actual)
            else:
                p = self.target(target, action, allow_core)
                plan.update(target=clean_relative(target).as_posix(), fingerprint=inventory(p))
                if action == "update":
                    q = self.target(source, "update", allow_core)
                    require(p != q and not q.is_relative_to(p) and not p.is_relative_to(q),
                            "Replacement source and target overlap.")
                    require(p.is_dir() == q.is_dir(), "Replacement must have the same file/directory kind.")
                    plan.update(source=clean_relative(source).as_posix(), replacement=inventory(q))
            plans = self.store(".recycle") / "plans"
            check_chain(plans)
            plans.mkdir(exist_ok=True)
            write_json_new(plans / (plan["id"] + ".json"), plan)
            return {"plan_id": plan["id"], "action": action, "target": plan["target"],
                    "source": plan.get("source"), "entries": len(plan["fingerprint"]),
                    "reason": reason, "notice": "Preview only. Apply only within user authorization."}

    def apply(self, identifier):
        require(bool(re.fullmatch(r"[0-9a-f]{32}", identifier)), "Invalid plan ID.")
        with self.lock():
            pfile = self.path(f".recycle/plans/{identifier}.json", exists=True)
            require(pfile.stat().st_size <= 8 * 1024 * 1024, "Oversized plan.")
            plan = json.loads(pfile.read_text(encoding="utf-8"))
            require(plan.get("id") == identifier and plan.get("home") == str(self.root), "Plan mismatch.")
            action = plan.get("action")
            require(action in {"snapshot", "update", "archive", "recycle", "restore"}, "Invalid plan action.")
            target = plan["target"]
            if action == "restore":
                source_folder, record = self.transaction(plan["restore_id"])
                require(record["target"] == target and record["action"] != "restore", "Restore record changed.")
                source = source_folder / "payload"
                require(content_key(inventory(source)) == record["content"], "Retained payload changed.")
                require(inventory(source) == plan["fingerprint"], "Restore plan is stale.")
                destination = self.path(target)
                require(not destination.exists() and destination.parent.is_dir(), "Restore destination is unavailable.")
                relative = clean_relative(target)
                if relative.parts[0] not in DATA_ROOTS:
                    allowed = (len(relative.parts) == 1 and relative.parts[0] in CORE_FILES) or (
                        relative.parts[0] in CORE_ROOTS and len(relative.parts) > 1 and source.is_file())
                    require(allowed and plan.get("allow_core"), "Core restore is not authorized.")
                else:
                    require(len(relative.parts) > 1, "Data root restore is refused.")
            else:
                source = self.target(target, action, plan.get("allow_core", False))
                require(inventory(source) == plan["fingerprint"], "Source changed after preview; make a new plan.")
            replacement = None
            if action == "update":
                replacement = self.target(plan["source"], "update", plan.get("allow_core", False))
                require(source != replacement and not replacement.is_relative_to(source) and not source.is_relative_to(replacement),
                        "Overlapping replacement is refused.")
                require(inventory(replacement) == plan["replacement"], "Replacement changed after preview.")
            area = ".recycle/items" if action == "recycle" else "ARCHIVE"
            base = self.store(".recycle") if action == "recycle" else self.store("ARCHIVE")
            if action == "recycle":
                base = base / "items"
                check_chain(base)
                base.mkdir(exist_ok=True)
            folder = base / identifier
            require(not folder.exists(), "This plan was already applied or interrupted; inspect its record.")
            folder.mkdir()
            payload = folder / "payload"
            require(source.stat().st_dev == folder.stat().st_dev, "Cross-filesystem operation refused.")
            record = {"id": identifier, "schema": 1, "home": str(self.root), "target": target,
                      "action": action, "reason": plan["reason"], "created": stamp(),
                      "state": "prepared", "content": content_key(plan["fingerprint"])}
            rfile = folder / "record.json"
            write_json_new(rfile, record)
            event("prepared")
            if action in {"recycle", "archive"}:
                require(inventory(source) == plan["fingerprint"], "Source changed immediately before move.")
                no_replace(source, payload)
                event("after_move")
                require(content_key(inventory(payload)) == record["content"], "Moved content verification failed.")
            elif action == "restore":
                copy_checked(source, payload, plan["fingerprint"])
                record["state"] = "captured"
                record_state(rfile, record)
                event("captured")
                no_replace(payload, self.path(target))
                event("after_restore")
            else:
                copy_checked(source, payload, plan["fingerprint"])
                record["state"] = "captured"
                record_state(rfile, record)
                event("captured")
                if action == "update":
                    new = folder / "replacement"
                    copy_checked(replacement, new, plan["replacement"])
                    require(inventory(source) == plan["fingerprint"], "Target changed before update.")
                    require(inventory(replacement) == plan["replacement"], "Replacement changed before update.")
                    record["state"] = "ready"
                    record_state(rfile, record)
                    no_replace(source, folder / "displaced")
                    event("old_retained")
                    no_replace(new, self.path(target))
                    event("after_install")
                    require(content_key(inventory(self.path(target))) == content_key(plan["replacement"]),
                            "Installed content verification failed.")
            record["state"] = "complete"
            record["completed"] = stamp()
            record_state(rfile, record)
            return {"operation_id": identifier, "action": action, "target": target,
                    "state": "complete", "record": rfile.relative_to(self.root).as_posix()}

    def records(self, limit=20, identifier=None):
        require(1 <= limit <= 100, "Limit must be between 1 and 100.")
        if identifier:
            folder, record = self.transaction(identifier)
            return {"record": record, "payload_present": (folder / "payload").exists(),
                    "target_present": self.path(record["target"]).exists(),
                    "displaced_present": (folder / "displaced").exists()}
        rows = []
        for area in ("ARCHIVE", ".recycle/items"):
            base = self.path(area)
            if base.exists():
                for folder in base.iterdir():
                    check_node(folder)
                    if re.fullmatch(r"[0-9a-f]{32}", folder.name):
                        _, record = self.transaction(folder.name)
                        rows.append({k: record.get(k) for k in ("id", "action", "target", "state", "created")})
                    require(len(rows) <= LIMIT_FILES, "Too many records; inspect specific operation IDs.")
        return {"records": sorted(rows, key=lambda r: r["created"], reverse=True)[:limit]}


def inspect(home, raw, sha=False, links=False):
    path = home.path(raw, exists=True)
    s = check_node(path)
    result = {"path": clean_relative(raw).as_posix(), "kind": "directory" if path.is_dir() else "file",
              "bytes": s.st_size if path.is_file() else None}
    if sha:
        result["sha256"] = hash_file(path)
    if links:
        require(path.is_file() and path.suffix.lower() == ".md" and s.st_size <= 1024 * 1024,
                "Link inspection needs a Markdown file of at most 1 MiB.")
        text = path.read_text(encoding="utf-8")
        found = []
        for link in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            link = link.strip("<>").split("#", 1)[0]
            if not link or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", link):
                continue
            candidate = path.parent / unquote(link)
            try:
                relative = candidate.relative_to(home.root).as_posix()
                checked = home.path(relative)
                found.append({"link": link, "exists": checked.exists()})
            except (ValueError, SafetyError):
                found.append({"link": link, "exists": False, "error": "outside scope or unsafe path"})
            require(len(found) <= 1000, "Too many links.")
        result["links"] = found
    return result


def read_text_source(home, raw):
    path = home.path(raw, exists=True)
    require(path.is_file(), "Select a regular text file.")
    with path.open("rb") as source:
        data = source.read(TEXT_LIMIT + 1)
    require(len(data) <= TEXT_LIMIT, "Text files must be at most 256 KiB.")
    return data.decode("utf-8-sig"), digest(data)


def read_page(home, raw, offset, length, expected_sha):
    require(1 <= length <= PAGE_LIMIT, "Page length must be 1 to 4096 characters.")
    text, sha = read_text_source(home, raw)
    require(0 <= offset <= len(text), "Offset is outside the source.")
    require(offset == 0 or expected_sha is not None, "A resumed page needs the previous SHA-256.")
    require(expected_sha is None or expected_sha == sha, "Source changed. Start again at offset 0.")
    end = min(offset + length, len(text))
    return {"path": clean_relative(raw).as_posix(), "sha256": sha, "offset": offset,
            "text": text[offset:end], "next_offset": end if end < len(text) else None}


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key.")
        result[key] = value
    return result


def reject_json_constant(value):
    raise SafetyError(f"Invalid JSON constant: {value}.")


def validate_text(home, raw, kind):
    text, sha = read_text_source(home, raw)
    if kind == "json":
        json.loads(text, object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
    return {"path": clean_relative(raw).as_posix(), "sha256": sha, "check": kind, "validation": "PASS"}


def write_text_source(home, raw, expected_sha, data):
    require(os.name == "nt", "File mutation is currently supported on Windows only.")
    relative = clean_relative(raw)
    require(len(relative.parts) > 1 and relative.parts[0] in DATA_ROOTS,
            "Write only to an exact file under PERSONA, MEMORY, PROJECTS, or ASSETS.")
    require(expected_sha == "absent" or re.fullmatch(r"[a-f0-9]{64}", expected_sha),
            "Provide the current SHA-256 or absent for creation.")
    require(len(data) <= TEXT_LIMIT, "Replacement text must be at most 256 KiB.")
    target = home.path(raw)
    replacement_sha = digest(data)
    snapshot_id = None
    if expected_sha != "absent":
        _, current_sha = read_text_source(home, raw)
        require(current_sha == expected_sha, "Source changed. Read the current file and rework the edit.")
        if current_sha == replacement_sha:
            return {"path": relative.as_posix(), "sha256": current_sha, "changed": False}
        plan = home.plan("snapshot", target=raw, reason="Before Swiss Knife text edit")
        snapshot_id = home.apply(plan["plan_id"])["operation_id"]
        payload = home.path(f"ARCHIVE/{snapshot_id}/payload", exists=True)
        require(hash_file(payload) == expected_sha, "Source changed before snapshot. No edit installed.")

    with home.lock():
        target = home.path(raw)
        if snapshot_id:
            require(hash_file(target) == expected_sha, "Source changed after snapshot. No edit installed.")
        else:
            require(not os.path.lexists(target), "Creation target exists. No edit installed.")
            target.parent.mkdir(parents=True, exist_ok=True)
            check_chain(target.parent)
        staged = target.parent / (".vhd-write-" + uuid.uuid4().hex + ".tmp")
        created_stage = False
        try:
            with staged.open("xb") as output:
                created_stage = True
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            require(hash_file(staged) == replacement_sha, "Staged edit verification failed.")
            if snapshot_id:
                require(hash_file(target) == expected_sha, "Source changed during staging. No edit installed.")
                os.replace(staged, target)
            else:
                no_replace(staged, target)
            require(hash_file(target) == replacement_sha, "Installed edit verification failed.")
        finally:
            if created_stage and staged.exists():
                staged.unlink()
    return {"path": relative.as_posix(), "sha256": replacement_sha, "changed": True,
            "snapshot_id": snapshot_id}


def read_write_request():
    max_request_bytes = TEXT_LIMIT * 6 + 32
    body = sys.stdin.buffer.read(max_request_bytes + 1)
    require(len(body) <= max_request_bytes, "Write request exceeds the input limit.")
    request = json.loads(body.decode("utf-8-sig"), object_pairs_hook=unique_json_object)
    require(isinstance(request, dict) and request.keys() == {"text"} and isinstance(request["text"], str),
            'Send one UTF-8 JSON object with only a string field named "text".')
    return request["text"].encode("utf-8")


def table_rows(text, header):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if table_cells(line) == header:
            require(index + 1 < len(lines), "Missing Markdown table separator.")
            separator = table_cells(lines[index + 1])
            require(len(separator) == len(header) and
                    all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator),
                    "Invalid Markdown table separator.")
            for row in lines[index + 2:]:
                if not row.lstrip().startswith("|"):
                    break
                fields = table_cells(row)
                require(len(fields) == len(header), "Invalid Markdown table row.")
                yield fields
            return
    raise SafetyError("Expected Markdown table header not found.")


def table_cells(line):
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.replace(r"\|", "|").strip() for cell in re.split(r"(?<!\\)\|", line[1:-1])]


def level_card(xp):
    level = sum(xp >= threshold for threshold in (0, 5, 12, 22))
    if xp >= 22:
        level = min(255, 4 + (xp - 22) // 10)
    next_xp = (5, 12, 22)[level - 1] if level < 4 else 22 + 10 * (level - 3)
    return {"xp": xp, "level": level, "next_level_xp": next_xp if level < 255 else None}


def progression(home, raw, contribution_id=None, award=None):
    parts = clean_relative(raw).parts
    require(parts[-2:] == ("PROGRESSION", "EXP.md") and
            ((parts[0] == "PERSONA" and len(parts) in (3, 4)) or parts == ("MEMORY", "USER", *parts[-2:])),
            "Select the requested owner's PROGRESSION/EXP.md.")
    text, sha = read_text_source(home, raw)
    ledger = {}
    for row in table_rows(text, ["Contribution ID", "Project", "Primary skill", "Title",
                                 "Earned date", "Verification", "Evidence", "Awarded EXP"]):
        identifier, _, skill, _, _, _, _, points = row
        require(all(row) and points in {"0", "1", "2", "3"}, "Ledger row is incomplete or has invalid EXP.")
        require(identifier not in ledger, "Duplicate contribution ID in ledger.")
        ledger[identifier] = (skill, int(points))
    xp = sum(points for _, points in ledger.values())
    result = {"ledger": clean_relative(raw).as_posix(), "sha256": sha, **level_card(xp)}
    if contribution_id is not None:
        require(bool(contribution_id.strip()) and len(contribution_id) <= 128 and "|" not in contribution_id,
                "Provide the stable contribution ID from the Markdown ledger.")
        previous = ledger.get(contribution_id, ("", 0))[1]
        delta = max(0, award - previous)
        return {**result, "id": contribution_id, "previous_award": previous, "delta": delta,
                "projected": level_card(xp + delta), "recorded": False}

    catalog = "MEMORY/KNOWLEDGE/CLASSES.md"
    if not home.path(catalog).exists():
        catalog = "KNOWLEDGE/CLASSES.md"
    class_text, catalog_sha = read_text_source(home, catalog)
    classes = {}
    skill_classes = {}
    for identifier, skills, *titles in table_rows(class_text, ["Class ID", "Skills", "Tier 1", "Tier 2", "Tier 3"]):
        require(identifier and identifier not in classes and all(titles), "Invalid class or duplicate class ID.")
        classes[identifier] = titles
        for skill in map(str.strip, skills.split(",")):
            require(skill and skill not in skill_classes, "Invalid skill or duplicate skill mapping.")
            skill_classes[skill] = identifier

    skill_totals = {skill: 0 for skill in skill_classes}
    class_totals = {identifier: [0, 0] for identifier in classes}
    for skill, points in ledger.values():
        skill_totals[skill] = skill_totals.get(skill, 0) + points
        if points and skill in skill_classes:
            totals = class_totals[skill_classes[skill]]
            totals[0] += points
            totals[1] += 1

    titles = []
    for identifier, (points, count) in class_totals.items():
        if count:
            tier = 1 + (points >= 4 and count >= 2) + (points >= 9 and count >= 3)
            titles.append({"class_id": identifier, "title": classes[identifier][tier - 1],
                           "tier": tier, "xp": points, "milestones": count})
    titles.sort(key=lambda title: (-title["xp"], -title["milestones"], title["class_id"]))
    skills = {skill: {"xp": points, "status": "verified" if points else "unassessed"}
              for skill, points in sorted(skill_totals.items())}
    return {**result, "catalog": catalog, "catalog_sha256": catalog_sha, "skills": skills,
            "title": titles[0] if titles else None, "titles": titles}


def rng(args, home):
    require(1 <= args.count <= 1000, "Count must be between 1 and 1000.")
    random = secrets.SystemRandom()
    if args.mode in {"int", "sample"}:
        require(args.low is not None and args.high is not None and args.low <= args.high, "Provide valid inclusive bounds.")
        require(abs(args.low) <= 10**18 and abs(args.high) <= 10**18, "Bounds exceed the supported range.")
        if args.mode == "int":
            values = [args.low + secrets.randbelow(args.high - args.low + 1) for _ in range(args.count)]
        else:
            require(args.count <= args.high - args.low + 1, "Sample exceeds the population.")
            values = random.sample(range(args.low, args.high + 1), args.count)
    else:
        require(args.pool is not None, "Provide --pool with a relative JSON file.")
        file = home.path(args.pool, exists=True)
        require(file.is_file() and file.stat().st_size <= 1024 * 1024, "Pool must be a file of at most 1 MiB.")
        pool = json.loads(file.read_text(encoding="utf-8"))
        require(isinstance(pool, list) and 1 <= len(pool) <= 10000, "Pool must contain 1 to 10000 entries.")
        if args.mode == "choose":
            values = [{"index": (index := secrets.randbelow(len(pool))) + 1, "value": pool[index]} for _ in range(args.count)]
        else:
            require(args.count == 1, "Shuffle accepts one complete pool, without --count.")
            values = list(pool)
            random.shuffle(values)
    require(len(packed(values)) <= 1024 * 1024, "Output exceeds 1 MiB.")
    return {"source": "os-csprng", "mode": args.mode, "values": values}


def main(argv=None):
    parser = argparse.ArgumentParser(description="VHD local helpers. No network, purge, or automatic cleanup.")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--version", action="version", version=VERSION)
    subs = parser.add_subparsers(dest="command", required=True)
    subs.add_parser("init", help="Create missing starter files on Windows")
    subs.add_parser("now", help="Read the host clock")
    r = subs.add_parser("rng", help="Draw random values")
    r.add_argument("mode", choices=["int", "sample", "choose", "shuffle"])
    r.add_argument("--low", type=int)
    r.add_argument("--high", type=int)
    r.add_argument("--count", type=int, default=1)
    r.add_argument("--pool")
    i = subs.add_parser("inspect", help="Inspect exact file metadata")
    i.add_argument("path")
    i.add_argument("--sha256", action="store_true")
    i.add_argument("--links", action="store_true")
    read = subs.add_parser("read", help="Read one bounded UTF-8 page")
    read.add_argument("path")
    read.add_argument("--offset", type=int, default=0)
    read.add_argument("--length", type=int, default=PAGE_LIMIT)
    read.add_argument("--sha256")
    validate = subs.add_parser("validate", help="Check an exact UTF-8 or JSON file")
    validate.add_argument("path")
    validate.add_argument("--kind", choices=["utf8", "json"], default="utf8")
    write = subs.add_parser("write", help="Create or update one UTF-8 file from JSON on stdin (Windows)")
    write.add_argument("path")
    write.add_argument("--sha256", required=True, help="Current file hash, or absent to create")
    stats = subs.add_parser("stats", help="Derive stats from an owner's Markdown EXP ledger")
    stats.add_argument("ledger")
    preview = subs.add_parser("xp-preview", help="Project one award without writing the ledger")
    preview.add_argument("ledger")
    preview.add_argument("--id", required=True)
    preview.add_argument("--award", type=int, choices=range(4), required=True)
    p = subs.add_parser("plan", help="Preview a guarded recovery operation")
    p.add_argument("action", choices=["snapshot", "update", "archive", "recycle", "restore"])
    p.add_argument("--path")
    p.add_argument("--from", dest="source")
    p.add_argument("--id")
    p.add_argument("--reason", required=True)
    p.add_argument("--allow-core", action="store_true")
    a = subs.add_parser("apply", help="Apply an authorized recovery plan")
    a.add_argument("id")
    l = subs.add_parser("records", help="Inspect recovery records")
    l.add_argument("--limit", type=int, default=20)
    l.add_argument("--id")
    args = parser.parse_args(argv)
    try:
        require(sys.version_info >= (3, 13), "Python 3.13 or newer is required.")
        if args.command == "now":
            now = datetime.now(timezone.utc)
            result = {"utc": now.isoformat(), "local": now.astimezone().isoformat(),
                      "zone": now.astimezone().tzname(), "note": "Host clock and zone; not an inferred user location."}
        elif args.command == "rng" and args.mode in {"int", "sample"}:
            result = rng(args, None)
        else:
            home = Home(args.home)
            if args.command == "init":
                result = home.setup()
            elif args.command == "rng":
                result = rng(args, home)
            elif args.command == "inspect":
                result = inspect(home, args.path, args.sha256, args.links)
            elif args.command == "read":
                result = read_page(home, args.path, args.offset, args.length, args.sha256)
            elif args.command == "validate":
                result = validate_text(home, args.path, args.kind)
            elif args.command == "write":
                result = write_text_source(home, args.path, args.sha256, read_write_request())
            elif args.command == "stats":
                result = progression(home, args.ledger)
            elif args.command == "xp-preview":
                result = progression(home, args.ledger, args.id, args.award)
            elif args.command == "plan":
                result = home.plan(args.action, args.path, args.source, args.id, args.reason, args.allow_core)
            elif args.command == "apply":
                result = home.apply(args.id)
            else:
                result = home.records(args.limit, args.id)
        print(json.dumps({"status": "OK", **result}, ensure_ascii=True))
        return 0
    except (SafetyError, OSError, ValueError, KeyError, TypeError, RecursionError) as e:
        print(json.dumps({"status": "ERROR", "error": str(e),
                          "recovery": "Inspect existing records and payloads before retrying any interrupted mutation."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
