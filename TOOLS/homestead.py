import argparse
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import errno
import hashlib
from itertools import islice
import json
import ntpath
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import unquote
import uuid
import zipfile

VERSION = "1.1.0"
LIMIT_FILES = 10000
LIMIT_BYTES = 512 * 1024 * 1024
TEXT_LIMIT = 256 * 1024
PAGE_LIMIT = 4096
DATA_ROOTS = {"PERSONA", "MEMORY", "PROJECTS", "ASSETS"}
CORE_ROOTS = {"TOOLS", "OPERATIONS", "TEMPLATES", "KNOWLEDGE"}
CORE_FILES = {"AGENTS.md", "START_HERE.md", "CONTEXT_MAP.md", "README.md", "LICENSE", ".gitignore", "TUTORIAL.txt", "VERIFICATION.md", "CREDITS.md", "sysprompt_to_copy.txt"}
MANIFEST_NAME = "MANIFEST.json"
STATE_NAME = "HOME_STATE.json"
ROUTES_NAME = "ROUTES.json"
EXPORT_STATE = "SOURCE.json"
STATE_SCHEMA = 1
USER_ROOTS = {"PERSONA", "MEMORY", "PROJECTS", "ASSETS", "ARCHIVE"}
SKIP_ROOTS = USER_ROOTS | {".recycle", "tests"}
SKIP_PARTS = {".git", ".recycle", "__pycache__"}
MANIFEST_KINDS = {"meta", "operations", "tool", "template", "knowledge", "state", "user"}
ROUTE_LIMIT = 4096
INDEX_NAME = "MEMORY/CACHE/index.json"
HEALTH_NAME = "MEMORY/CACHE/health.json"
HEAL_LOG_NAME = "MEMORY/CACHE/selfheal.jsonl"
INDEX_SCHEMA = 1
INDEX_RULES = "index-2"
GUARDIAN_STATE = ".recycle/guardian.json"
GUARDIAN_IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp"}
INDEX_SUFFIXES = {".md", ".json", ".txt", ".py", ".cfg", ".ini", ".toml", ".yml", ".yaml",
                  ".csv", ".html", ".css", ".js", ".ps1", ".cmd", ".sh"}
INDEX_EXCLUDED_PARTS = {"archive", ".recycle", ".git", "__pycache__"}
INDEX_DERIVED_PREFIXES = ("MEMORY/CACHE/", "MEMORY/RUNTIME/")
INDEX_PRIVATE_PARTS = {"private"}
INDEX_TERM_LIMIT = 8192
SEARCH_LIMIT = 50
REFRESH_SECONDS = 60
HEAL_ATTEMPTS = 2
HEAL_BUDGET_SECONDS = 45
HEAL_DEDUPE_SECONDS = 300
EVENT_HOOK = None


class SafetyError(Exception):
    pass


class GuardianDenied(SafetyError):
    def __init__(self, result):
        super().__init__(result["reason"])
        self.result = result


def require(condition, message):
    if not condition:
        raise SafetyError(message)


def require_mutation():
    require(os.name in {"nt", "posix"}, "File mutation is not supported on this platform.")


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


def portable_move(source, destination):
    if source.is_file():
        try:
            os.link(source, destination)
        except FileExistsError:
            raise SafetyError("Destination already exists; nothing overwritten.")
        except OSError as error:
            if error.errno == errno.EXDEV:
                raise SafetyError("Cross-filesystem moves are refused.")
            raise
        source.unlink()
        return
    try:
        os.mkdir(destination)
    except FileExistsError:
        raise SafetyError("Destination already exists; nothing overwritten.")
    for child in sorted(source.iterdir(), key=lambda item: item.name):
        portable_move(child, destination / child.name)
    source.rmdir()


def no_replace(source, destination, platform=None):
    require_mutation()
    check_chain(source)
    check_chain(destination.parent)
    require(not os.path.lexists(destination), "Destination already exists; nothing overwritten.")
    require(source.stat().st_dev == destination.parent.stat().st_dev, "Cross-filesystem moves are refused.")
    if (platform or os.name) == "nt":
        os.rename(source, destination)
    else:
        portable_move(source, destination)


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


def kind_of(relative):
    first = relative.parts[0]
    if first in USER_ROOTS:
        return "user"
    if first == "OPERATIONS":
        return "operations"
    if first == "TOOLS":
        return "tool"
    if first == "TEMPLATES":
        return "template"
    if first == "KNOWLEDGE":
        return "knowledge"
    if relative.as_posix() == STATE_NAME:
        return "state"
    return "meta"


def package_manifest(root, version=None, state="package contents with hashes"):
    root = Path(root)
    require(root.is_dir(), "Package folder is not a directory.")
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if relative.as_posix() in {MANIFEST_NAME, STATE_NAME, EXPORT_STATE} or relative.parts[0] in SKIP_ROOTS:
            continue
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        clean_relative(relative.as_posix())
        files.append({"path": relative.as_posix(), "kind": kind_of(relative),
                      "sha256": hash_file(path), "bytes": path.stat().st_size})
    require(files, "Package has no files to record.")
    require(len(files) <= LIMIT_FILES, "Too many package files.")
    return {"version": version or VERSION, "state": state, "files": files, "moved": [], "migrations": []}


def check_manifest(value):
    require(isinstance(value, dict), "Manifest must be an object.")
    require(re.fullmatch(r"\d+\.\d+\.\d+", str(value.get("version"))), "Manifest version is invalid.")
    files = value.get("files")
    require(isinstance(files, list) and files, "Manifest files are missing.")
    require(len(files) <= LIMIT_FILES, "Manifest lists too many files.")
    seen = set()
    for entry in files:
        require(isinstance(entry, dict), "Manifest entry must be an object.")
        text = clean_relative(entry.get("path")).as_posix()
        require(text not in seen, "Duplicate manifest path.")
        seen.add(text)
        require(entry.get("kind") in MANIFEST_KINDS, "Unknown manifest kind.")
        require(re.fullmatch(r"[0-9a-f]{64}", str(entry.get("sha256"))), "Invalid manifest hash.")
        require(isinstance(entry.get("bytes"), int) and entry["bytes"] >= 0, "Invalid manifest size.")
    require(isinstance(value.get("moved", []), list), "Manifest moves must be a list.")
    require(isinstance(value.get("migrations", []), list), "Manifest migrations must be a list.")
    extras = value.get("export_extra", [])
    require(isinstance(extras, list) and len(extras) <= 20, "Manifest export extras must be a list of at most 20 paths.")
    seen_extras = set()
    for raw in extras:
        text = clean_relative(raw).as_posix()
        require(text not in seen_extras and text not in seen, "Duplicate manifest export extra.")
        seen_extras.add(text)
    return value


def state_document(manifest, previous=None):
    check_manifest(manifest)
    known = previous.get("home_id") if isinstance(previous, dict) else None
    home_id = known if isinstance(known, str) else str(uuid.uuid4())
    require(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", home_id),
            "Invalid home id.")
    retained = previous.get("retained", []) if isinstance(previous, dict) else []
    require(isinstance(retained, list), "Retained choices must be a list.")
    return {"schema": STATE_SCHEMA, "home_id": home_id, "version": manifest["version"],
            "installed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "manifest_sha256": digest(packed(manifest)), "manifest": manifest, "retained": retained}


def read_state(home):
    path = home.path(STATE_NAME)
    if not path.exists():
        return None
    require(path.is_file(), "Home state is not a file.")
    require(path.stat().st_size <= 4 * 1024 * 1024, "Home state is oversized.")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "Home state must be an object.")
    require(value.get("schema") == STATE_SCHEMA, "Unsupported home state schema.")
    check_manifest(value.get("manifest"))
    require(value.get("manifest_sha256") == digest(packed(value["manifest"])), "Home state manifest hash mismatch.")
    require(value.get("version") == value["manifest"]["version"], "Home state version mismatch.")
    require(isinstance(value.get("retained"), list), "Retained choices must be a list.")
    return value


def version_key(text):
    require(re.fullmatch(r"\d+\.\d+\.\d+", str(text)), "Version must be three numbers.")
    return tuple(int(part) for part in str(text).split("."))


def home_markers(path):
    path = Path(path)
    score = 0
    matched = []
    tool = (path / "TOOLS" / "homestead.py").exists() or (path / "TOOLS" / "vhd.py").exists()
    for name, weight, label in (("HOME_STATE.json", 3, "state"), ("START_HERE.md", 2, "start"),
                                ("PERSONA", 2, "persona"), ("TOOLS/homestead.py", 2, "tool"),
                                ("OPERATIONS", 1, "operations"), ("TEMPLATES", 1, "templates")):
        present = tool if name == "TOOLS/homestead.py" else (path / name).exists()
        if present:
            score += weight
            matched.append(label)
    if (path / MANIFEST_NAME).is_file() and not (path / STATE_NAME).is_file():
        score -= 8
        matched.append("package")
    progress = path / "PROGRESS"
    if progress.is_dir() and any(progress.glob("0001-*.md")):
        score -= 3
        matched.append("source")
    if any((parent / "releases").is_dir() for parent in (path.parent, path.parent.parent)):
        score -= 3
        matched.append("release")
    return score, matched


def find_homes(base, depth=3):
    require(isinstance(depth, int) and 1 <= depth <= 4, "Detection depth is one to four.")
    start = Path(os.path.abspath(base))
    require(start.is_dir(), "Detection base is not a folder.")
    found = []
    scanned = 0
    stack = [(start, 0)]
    while stack:
        current, level = stack.pop()
        scanned += 1
        require(scanned <= 2000, "Detection scan is too large for this folder.")
        score, matched = home_markers(current)
        if score > 0:
            found.append({"path": str(current), "score": score, "markers": matched})
        if level < depth and score < 8:
            try:
                children = sorted(p for p in current.iterdir() if p.is_dir())
            except OSError:
                continue
            for child in children:
                if child.name in SKIP_PARTS:
                    continue
                try:
                    check_node(child)
                except (OSError, SafetyError):
                    continue
                stack.append((child, level + 1))
    found.sort(key=lambda entry: (-entry["score"], entry["path"]))
    return found


def select_home(path):
    selected = Path(os.path.abspath(path))
    score, matched = home_markers(selected)
    if score >= 8 and (selected / "START_HERE.md").is_file():
        return {"path": str(selected.resolve()), "score": score, "markers": matched, "source": "direct"}
    candidates = find_homes(selected, 3)
    require(candidates, "No Homestead home found near the given path.")
    top = candidates[0]
    tied = [entry for entry in candidates if entry["score"] == top["score"]]
    require(len(tied) == 1, "Ambiguous Homestead home: " + " | ".join(
        f"{entry['path']} ({entry['score']}: {','.join(entry['markers'])})" for entry in tied[:2]))
    return {**top, "source": "scan"}


def manifest_command(root, write):
    target = Path(os.path.abspath(root))
    prior = {}
    source = target / MANIFEST_NAME
    if source.is_file() and source.stat().st_size <= 4 * 1024 * 1024:
        try:
            prior = json.loads(source.read_text(encoding="utf-8"))
        except ValueError:
            prior = {}
    manifest = package_manifest(target)
    if isinstance(prior, dict) and prior.get("export_extra"):
        manifest["export_extra"] = prior["export_extra"]
    check_manifest(manifest)
    fingerprint = digest(packed(manifest))
    if write:
        require_mutation()
        record_state(target / MANIFEST_NAME, manifest)
    return {"path": str(target / MANIFEST_NAME), "written": bool(write), "version": manifest["version"],
            "files": len(manifest["files"]), "export_extra": manifest.get("export_extra", []),
            "sha256": fingerprint}


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


def host_mark():
    return "%s-%012x" % (platform.node() or "unknown", uuid.getnode())


def process_birth(pid):
    try:
        number = int(pid)
    except (TypeError, ValueError):
        return None
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            handle = kernel32.OpenProcess(0x1000, False, number)
        except (OSError, ValueError, AttributeError):
            return None
        if not handle:
            return None
        try:
            created = ctypes.c_ulonglong(0)
            exited = ctypes.c_ulonglong(0)
            kernel = ctypes.c_ulonglong(0)
            user = ctypes.c_ulonglong(0)
            if not kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                            ctypes.byref(kernel), ctypes.byref(user)):
                return None
            return str(created.value)
        finally:
            kernel32.CloseHandle(handle)
    try:
        raw = Path("/proc/%d/stat" % number).read_text(encoding="utf-8")
        fields = raw[raw.rindex(")") + 2:].split()
        return fields[19]
    except (OSError, ValueError, IndexError):
        return None


def lock_payload(token):
    return {"schema": 1, "pid": os.getpid(), "host": host_mark(),
            "birth": process_birth(os.getpid()), "token": token, "created": stamp()}


def lock_path(home):
    return home.path(".recycle/operation.lock")


def lock_report(home):
    report = {"path": ".recycle/operation.lock", "present": False, "state": "absent"}
    lock = lock_path(home)
    if not lock.is_file():
        return report
    report["present"] = True
    require(lock.stat().st_size <= 4096, "Lock file is oversized; inspect it manually.")
    raw = lock.read_bytes()
    report["sha256"] = digest(raw)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict) or data.get("schema") != 1:
        report.update({"state": "unknown", "reason": "legacy or unreadable lock format"})
        return report
    report["record"] = data
    if data.get("host") != host_mark():
        report.update({"state": "unknown", "reason": "the lock belongs to another host"})
        return report
    if not data.get("birth"):
        report.update({"state": "unknown", "reason": "the lock has no process birth mark"})
        return report
    birth = process_birth(data.get("pid"))
    if birth is None:
        report.update({"state": "stale", "reason": "the owning process is gone"})
    elif birth == data["birth"]:
        report["state"] = "live"
    else:
        report.update({"state": "unknown", "reason": "the PID now belongs to a different process"})
    return report


def lock_recover(home):
    report = lock_report(home)
    require(report["state"] == "stale", "Recovery needs a confirmed stale lock; inspect the report first.")
    lock = lock_path(home)
    require(digest(lock.read_bytes()) == report["sha256"], "The lock changed after inspection; run lock again.")
    folder = home.path(".recycle/locks")
    folder.mkdir(exist_ok=True)
    check_chain(folder)
    identifier = uuid.uuid4().hex
    destination = folder / (identifier + ".lock")
    no_replace(lock, destination)
    record = {"id": identifier, "quarantined": destination.relative_to(home.root).as_posix(),
              "reason": report["reason"], "lock": report.get("record"), "at": stamp()}
    write_json_new(folder / (identifier + ".json"), record)
    return {"recovered": identifier, "quarantined": record["quarantined"], "reason": report["reason"]}


def pending_upgrade_path(home):
    return home.path(".recycle/pending-upgrade.json")


class Home:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        require(not str(absolute).startswith("\\\\"), "Network homes are not supported.")
        check_chain(absolute)
        self.root = absolute.resolve(strict=True)
        require(self.root != Path(self.root.anchor), "A filesystem root cannot be a Homestead home.")
        for name in ("START_HERE.md", "CONTEXT_MAP.md", "TEMPLATES/IDENTITY.md"):
            require(self.path(name).is_file(), "Not a complete Homestead home.")

    def path(self, raw, exists=False):
        relative = clean_relative(raw)
        require(all(p.casefold() != ".git" for p in relative.parts), "Git metadata is protected.")
        target = self.root / relative
        check_chain(target)
        require(target.resolve(strict=False).is_relative_to(self.root), "Path is outside the Homestead home.")
        if exists:
            require(target.exists(), "Selected path does not exist.")
        return target

    def package_files(self):
        if getattr(self, "_package_files", None) is None:
            path = self.path(MANIFEST_NAME)
            found = set()
            if path.is_file() and path.stat().st_size <= 4 * 1024 * 1024:
                try:
                    manifest = check_manifest(json.loads(path.read_text(encoding="utf-8")))
                except (ValueError, SafetyError):
                    manifest = None
                if manifest:
                    found = {entry["path"] for entry in manifest["files"]}
            self._package_files = found
        return self._package_files

    def target(self, raw, action, allow_core=False):
        relative = clean_relative(raw)
        p = self.path(raw, exists=True)
        first = relative.parts[0]
        if first in DATA_ROOTS:
            require(len(relative.parts) > 1, "Local data roots are protected.")
        else:
            is_core_file = (len(relative.parts) == 1 and first in CORE_FILES) or (
                first in CORE_ROOTS and len(relative.parts) > 1 and p.is_file())
            is_package_file = relative.as_posix() in self.package_files()
            require(action in {"snapshot", "update", "restore"} and allow_core and (is_core_file or is_package_file),
                    "Target is protected or outside the permitted data areas.")
        return p

    def store(self, area):
        p = self.path(area)
        p.mkdir(exist_ok=True)
        check_chain(p)
        return p

    @contextmanager
    def lock(self):
        require_mutation()
        base = self.store(".recycle")
        lock = base / "operation.lock"
        if getattr(self, "lock_token", None):
            self.lock_depth += 1
            try:
                yield
            finally:
                self.lock_depth -= 1
            return
        token = uuid.uuid4().hex
        try:
            write_json_new(lock, lock_payload(token))
        except FileExistsError:
            raise SafetyError("Another operation or stale lock exists. Run lock to inspect it; automatic removal is refused.")
        self.lock_token = token
        self.lock_depth = 1
        try:
            yield
        finally:
            self.lock_depth -= 1
            if self.lock_depth == 0:
                self.lock_token = None
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
            previous = read_state(self)
            if previous is None:
                source_path = self.path(MANIFEST_NAME)
                if source_path.is_file():
                    require(source_path.stat().st_size <= 4 * 1024 * 1024, "Package manifest is oversized.")
                    manifest = check_manifest(json.loads(source_path.read_text(encoding="utf-8")))
                    manifest_source = MANIFEST_NAME
                else:
                    manifest = package_manifest(self.root)
                    manifest_source = "generated"
                record_state(self.path(STATE_NAME), state_document(manifest))
                created.append(STATE_NAME)
                state = {"created": True, "version": manifest["version"], "manifest_source": manifest_source}
            else:
                state = {"created": False, "version": previous["version"]}
            return {"created": created, "state": state, "existing_files": "preserved"}

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
                        relative.parts[0] in CORE_ROOTS and len(relative.parts) > 1 and source.is_file()) or (
                        relative.as_posix() in self.package_files())
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


def inspect(home, raw, sha=False, links=False, *, guarded=False, purpose=None):
    path = home.path(raw, exists=True)
    s = check_node(path)
    result = {"path": clean_relative(raw).as_posix(), "kind": "directory" if path.is_dir() else "file",
              "bytes": s.st_size if path.is_file() else None}
    if sha:
        result["sha256"] = hash_file(path)
    if links:
        require(path.is_file() and path.suffix.lower() == ".md" and s.st_size <= 1024 * 1024,
                "Link inspection needs a Markdown file of at most 1 MiB.")
        if guarded:
            data, _ = guardian_bytes(home, raw, purpose, 1024 * 1024)
            text = data.decode("utf-8")
        else:
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


def guardian_path(home, raw):
    relative = clean_relative(raw)
    parts = [part.casefold() for part in relative.parts]
    require(not set(parts) & {".recycle", "archive", ".git", "__pycache__"}
            and parts[:2] not in (["memory", "cache"], ["memory", "runtime"])
            and not any(part == ".env" or part.startswith(".env.") for part in parts),
            "Guardian keeps credentials, recovery files and internal caches outside model reads.")
    path = home.path(raw, exists=True)
    require(path.is_file(), "Guardian needs an exact file.")
    return relative, path


def guardian_public_hash(home, relative):
    if relative.parts[0].upper() in USER_ROOTS:
        return None
    if not hasattr(home, "_guardian_public"):
        home._guardian_public = {}
        manifest = home.path(MANIFEST_NAME)
        if manifest.is_file() and manifest.stat().st_size <= 4 * 1024 * 1024:
            try:
                entries = check_manifest(json.loads(manifest.read_text(encoding="utf-8")))["files"]
                home._guardian_public = {entry["path"]: entry["sha256"] for entry in entries
                                         if entry["kind"] != "user"}
            except (ValueError, SafetyError):
                pass
    return home._guardian_public.get(relative.as_posix())


def guardian_state(home):
    path = home.path(GUARDIAN_STATE)
    if not path.exists():
        return {"schema": 1, "skip_extra_confirmation": False, "decisions": {}}
    require(path.is_file() and path.stat().st_size <= TEXT_LIMIT, "Guardian state is unavailable.")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_json_object)
    require(isinstance(value, dict) and value.get("schema") == 1
            and type(value.get("skip_extra_confirmation")) is bool
            and isinstance(value.get("decisions"), dict), "Guardian state is invalid.")
    return value


def guardian_key(relative, purpose):
    require(isinstance(purpose, str) and 1 <= len(purpose.strip()) <= 160
            and purpose == purpose.strip() and all(char.isprintable() for char in purpose),
            "Provide the stated purpose as one line of 1 to 160 characters.")
    path = relative.as_posix()
    return digest(packed([path.casefold() if os.name == "nt" else path, purpose]))


def guardian_check(home, relative, sha, purpose):
    if guardian_public_hash(home, relative) == sha:
        return
    state = guardian_state(home)
    record = state["decisions"].get(guardian_key(relative, purpose)) if purpose else None
    decision = record.get("decision") if isinstance(record, dict) else None
    if decision == "allow" and record.get("sha256") != sha:
        decision = None
    if decision == "allow":
        return
    ask = not state["skip_extra_confirmation"] and decision != "deny"
    raise GuardianDenied({"status": "CONSENT_REQUIRED" if ask else "DENIED",
                          "path": relative.as_posix(), "purpose": purpose,
                          "reason": "Owner permission is required for this file and purpose."})


def guardian_command(home, action, raw=None, purpose=None, setting=None):
    if action == "status":
        state = guardian_state(home)
        return {"skip_extra_confirmation": state["skip_extra_confirmation"], "default_access": "denied"}
    require(sys.stdin.isatty() and sys.stderr.isatty(),
            "The owner must change Guardian settings or decisions in a local interactive terminal.")
    if action == "forget":
        key = guardian_key(clean_relative(raw), purpose)
    if action == "authorize":
        relative, path = guardian_path(home, raw)
        key = guardian_key(relative, purpose)
        sha = hash_file(path)
        print(f"Allow the model to read {relative.as_posix()!r} for {purpose!r}? "
              "Respect the creator's terms. Type yes or no.", file=sys.stderr, flush=True)
        answer = sys.stdin.readline().strip().casefold()
        require(answer in {"yes", "no"}, "No decision was recorded.")
        decision = "allow" if answer == "yes" else "deny"
    with home.lock():
        state = guardian_state(home)
        if action == "mode":
            state["skip_extra_confirmation"] = setting == "true"
            result = {"skip_extra_confirmation": state["skip_extra_confirmation"]}
        elif action == "forget":
            result = {"forgotten": state["decisions"].pop(key, None) is not None}
        else:
            require(hash_file(home.path(raw, exists=True)) == sha, "File changed. Review it before deciding again.")
            state["decisions"][key] = {"sha256": sha, "decision": decision}
            result = {"decision": decision, "path": relative.as_posix(), "purpose": purpose}
        require(len(packed(state)) < TEXT_LIMIT, "Guardian state is full; remove an old decision first.")
        record_state(home.path(GUARDIAN_STATE), state)
    return result


def guardian_bytes(home, raw, purpose, limit):
    relative, path = guardian_path(home, raw)
    require(path.stat().st_size <= limit, "File exceeds the guarded output limit.")
    sha = hash_file(path)
    guardian_check(home, relative, sha, purpose)
    with path.open("rb") as source:
        data = source.read(limit + 1)
    require(len(data) <= limit, "File exceeds the guarded output limit.")
    require(digest(data) == sha, "File changed after Guardian checked it.")
    return data, sha


def guardian_attachment(home, raw, purpose):
    relative = clean_relative(raw)
    media_type = GUARDIAN_IMAGE_TYPES.get(relative.suffix.lower())
    require(media_type is not None, "Choose a PNG, JPEG, GIF or WebP image.")
    data, sha = guardian_bytes(home, raw, purpose, 2 * 1024 * 1024)
    return {"path": relative.as_posix(), "sha256": sha, "media_type": media_type,
            "encoding": "base64", "data": base64.b64encode(data).decode("ascii")}


def read_text_source(home, raw):
    path = home.path(raw, exists=True)
    require(path.is_file(), "Select a regular text file.")
    with path.open("rb") as source:
        data = source.read(TEXT_LIMIT + 1)
    require(len(data) <= TEXT_LIMIT, "Text files must be at most 256 KiB.")
    return data.decode("utf-8-sig"), digest(data)


def read_page(home, raw, offset, length, expected_sha, *, guarded=False, purpose=None, if_changed=None):
    require(1 <= length <= PAGE_LIMIT, "Page length must be 1 to 4096 characters.")
    if if_changed is not None:
        require(offset == 0 and expected_sha is None, "A refresh must start at offset 0 with no --sha256.")
        require(re.fullmatch(r"[0-9a-fA-F]{64}", if_changed), "Provide a SHA-256 from a complete same-chat read.")
    if guarded:
        data, sha = guardian_bytes(home, raw, purpose, TEXT_LIMIT)
        text = data.decode("utf-8-sig")
    else:
        text, sha = read_text_source(home, raw)
    require(0 <= offset <= len(text), "Offset is outside the source.")
    require(offset == 0 or expected_sha is not None, "A resumed page needs the previous SHA-256.")
    require(expected_sha is None or expected_sha == sha, "Source changed. Start again at offset 0.")
    result = {"path": clean_relative(raw).as_posix(), "sha256": sha}
    if if_changed is not None:
        result["unchanged"] = sha == if_changed.lower()
        if result["unchanged"]:
            return result
    end = min(offset + length, len(text))
    return {**result, "offset": offset, "text": text[offset:end],
            "next_offset": end if end < len(text) else None}


def fold_log(home, raw, limit, purpose):
    require(1 <= limit <= 100, "Limit must be 1 to 100.")
    data, sha = guardian_bytes(home, raw, purpose, TEXT_LIMIT)
    lines = data.decode("utf-8-sig").splitlines()
    groups = {}
    for number, line in enumerate(lines, 1):
        if line not in groups:
            groups[line] = {"count": 0, "first_line": number, "last_line": number}
        groups[line]["count"] += 1
        groups[line]["last_line"] = number
    preview = [{"text": line[:240], "truncated": len(line) > 240, **group}
               for line, group in islice(groups.items(), limit)]
    return {"path": clean_relative(raw).as_posix(), "sha256": sha, "source_bytes": len(data),
            "line_count": len(lines), "distinct_lines": len(groups),
            "omitted_groups": max(0, len(groups) - limit), "groups": preview}


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
    require_mutation()
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


def progression(home, raw, contribution_id=None, award=None, *, purpose=None, guarded=False):
    parts = clean_relative(raw).parts
    require(parts[-2:] == ("PROGRESSION", "EXP.md") and
            ((parts[0] == "PERSONA" and len(parts) in (3, 4)) or parts == ("MEMORY", "USER", *parts[-2:])),
            "Select the requested owner's PROGRESSION/EXP.md.")
    if guarded:
        data, sha = guardian_bytes(home, raw, purpose, TEXT_LIMIT)
        text = data.decode("utf-8-sig")
    else:
        text, sha = read_text_source(home, raw)
    ledger = {}
    projects = set()
    for row in table_rows(text, ["Contribution ID", "Project", "Primary skill", "Title",
                                 "Earned date", "Verification", "Evidence", "Awarded EXP"]):
        identifier, project, skill, _, _, _, _, points = row
        require(all(row) and points in {"0", "1", "2", "3"}, "Ledger row is incomplete or has invalid EXP.")
        require(identifier not in ledger, "Duplicate contribution ID in ledger.")
        ledger[identifier] = (skill, int(points), project)
        projects.add(project)
    xp = sum(points for _, points, _ in ledger.values())
    result = {"ledger": clean_relative(raw).as_posix(), "sha256": sha, **level_card(xp)}
    if contribution_id is not None:
        require(bool(contribution_id.strip()) and len(contribution_id) <= 128 and "|" not in contribution_id,
                "Provide the stable contribution ID from the Markdown ledger.")
        previous = ledger.get(contribution_id, ("", 0, ""))[1]
        delta = max(0, award - previous)
        return {**result, "id": contribution_id, "previous_award": previous, "delta": delta,
                "projected": level_card(xp + delta), "recorded": False}

    catalog = "MEMORY/KNOWLEDGE/CLASSES.md"
    if not home.path(catalog).exists():
        catalog = "KNOWLEDGE/CLASSES.md"
    if guarded:
        data, catalog_sha = guardian_bytes(home, catalog, purpose, TEXT_LIMIT)
        class_text = data.decode("utf-8-sig")
    else:
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
    for skill, points, _ in ledger.values():
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
    skills = {skill: {"xp": points, "status": "verified" if points else "unassessed",
                      "level": level_card(points)["level"] if points else None}
              for skill, points in sorted(skill_totals.items())}
    return {**result, "catalog": catalog, "catalog_sha256": catalog_sha, "skills": skills,
            "projects": len(projects), "title": titles[0] if titles else None, "titles": titles}


def xp_record(home, raw, purpose, record):
    fields = ("id", "project", "skill", "title", "earned_on", "verification", "evidence", "xp")
    require(isinstance(record, dict) and record.keys() == set(fields), "Provide one complete milestone object.")
    *values, xp = [record[field] for field in fields]
    require(all(isinstance(value, str) and 1 <= len(value) <= 512 and value.strip() == value
                and all(char.isprintable() for char in value) and "|" not in value for value in values),
            "Milestone fields must contain one line of Markdown table text.")
    require(type(xp) is int and 0 <= xp <= 3, "Award 0 to 3 EXP.")
    identifier, project, skill, title, earned_on, verification, evidence = values
    require(len(identifier) <= 128, "Contribution ID exceeds 128 characters.")
    require(re.fullmatch(r"\d{4}-\d\d-\d\d", earned_on), "Use a YYYY-MM-DD earned date.")
    datetime.strptime(earned_on, "%Y-%m-%d")
    evidence_path = home.path(evidence, exists=True)
    require(evidence_path.is_file() and " ; " not in evidence, "Use one exact evidence file per award.")
    with home.lock():
        preview = progression(home, raw, identifier, xp, purpose=purpose, guarded=True)
        if not preview["delta"]:
            return preview
        data, sha = guardian_bytes(home, raw, purpose, TEXT_LIMIT)
        ledger = data.decode("utf-8-sig")
        header = ["Contribution ID", "Project", "Primary skill", "Title", "Earned date",
                  "Verification", "Evidence", "Awarded EXP"]
        rows = list(table_rows(ledger, header))
        lines = ledger.splitlines(keepends=True)
        start = next(i for i, line in enumerate(lines) if table_cells(line) == header) + 2
        for index, row in enumerate(rows, start):
            if row[0] != identifier:
                continue
            require(row[1:3] == [project, skill], "Keep the original project and primary skill for this ID.")
            require(evidence not in row[-2].split(" ; "), "An increase needs a new evidence file.")
            values[-1] = row[-2] + " ; " + evidence
            break
        else:
            index = start + len(rows)
        newline = "\r\n" if "\r\n" in ledger else "\n"
        line = "| " + " | ".join([*values, str(xp)]) + " |" + newline
        if index < start + len(rows):
            lines[index] = line
        else:
            if index and not lines[index - 1].endswith("\n"):
                lines[index - 1] += newline
            lines.insert(index, line)
        replacement = "".join(lines).encode("utf-8")
        write = write_text_source(home, raw, sha, replacement)
        return {**preview, "recorded": True, "sha256": write["sha256"], "snapshot_id": write["snapshot_id"]}


def stats_display(card):
    def meter(score, size=10):
        filled = min(size, round(score * size / 100))
        return "#" * filled + "-" * (size - filled)

    title = (card["title"] or {}).get("title", "Unassessed")
    progress = card["cognitive"]["ranks"]["progress"]["score"]
    lines = [f"Level {card['level']} | {title} | {card['xp']} EXP", f"Progress [{meter(progress)}] {progress}%"]
    lines.append("COGNITIVE RANK")
    for name, rank in card["cognitive"]["ranks"].items():
        lines.append(f"{name}: {rank['rank']} [{meter(rank['score'])}] {rank['score']}%")
    lines.append("SKILLS")
    peak = max((skill["xp"] for skill in card["skills"].values()), default=0)
    for name, skill in card["skills"].items():
        lines.append(f"{name}: [{meter(skill['xp'] / peak * 100)}] {skill['xp']} EXP"
                     if skill["xp"] else f"{name}: unassessed")
    return "\n".join(lines)


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
        if hasattr(args, "purpose"):
            data, _ = guardian_bytes(home, args.pool, args.purpose, 1024 * 1024)
            pool = json.loads(data)
        else:
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


def heading_slug(text):
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text).strip("-")


def anchor_matches(path, anchor, text=None):
    if text is None:
        text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("#") and heading_slug(line.lstrip("#").strip()) == anchor:
            return True
    return False


def links_check(home, *, guarded=False):
    scanned = 0
    checked = 0
    failed = 0
    findings = []
    for path in sorted(home.root.rglob("*.md")):
        relative = path.relative_to(home.root)
        if (guarded and relative.parts[0].upper() in USER_ROOTS) or relative.parts[0] in {"ARCHIVE", ".recycle"} \
                or any(part in SKIP_PARTS for part in relative.parts):
            continue
        if not path.is_file():
            continue
        require(path.stat().st_size <= TEXT_LIMIT, "Markdown file exceeds the scan limit.")
        scanned += 1
        if guarded:
            try:
                data, _ = guardian_bytes(home, relative.as_posix(), None, TEXT_LIMIT)
            except GuardianDenied:
                scanned -= 1
                continue
            text = data.decode("utf-8")
        else:
            text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            raw = target.strip().split(" ", 1)[0].strip("<>")
            if not raw or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw) or raw.startswith("//"):
                continue
            checked += 1
            require(checked <= 5000, "Too many references to check.")
            anchor = None
            if "#" in raw:
                raw, anchor = raw.split("#", 1)
            entry = {"file": relative.as_posix(), "target": target.strip()}
            destination = path if not raw else (path.parent / unquote(raw.replace("\\", "/")))
            destination = destination.resolve(strict=False)
            if not destination.is_relative_to(home.root):
                destination = (home.root / unquote(raw.replace("\\", "/"))).resolve(strict=False)
            if not destination.is_relative_to(home.root):
                entry["state"] = "outside"
            elif not destination.exists():
                entry["state"] = "missing"
            elif anchor and destination.suffix.lower() == ".md":
                destination_text = None
                if guarded:
                    try:
                        data, _ = guardian_bytes(home, destination.relative_to(home.root).as_posix(), None, TEXT_LIMIT)
                    except SafetyError:
                        continue
                    destination_text = data.decode("utf-8")
                if not anchor_matches(destination, anchor, destination_text):
                    entry["state"] = "anchor"
            if "state" in entry:
                failed += 1
                require(len(findings) < 200, "Too many broken references; fix the first batch.")
                findings.append(entry)
    return {"files": scanned, "references": checked, "failed": failed, "findings": findings}


def routes_check(home):
    path = home.path(ROUTES_NAME)
    require(path.is_file(), "Route manifest is missing.")
    require(path.stat().st_size <= TEXT_LIMIT, "Route manifest is oversized.")
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict) and data.get("schema") == 1, "Unsupported route manifest.")
    parts = data.get("parts")
    require(isinstance(parts, list) and parts, "Route parts are missing.")
    require(len(parts) <= 50, "Too many route parts.")
    seen_ids = set()
    seen_paths = set()
    failed = 0
    results = []
    for part in parts:
        require(isinstance(part, dict), "Route part must be an object.")
        identifier = part.get("id")
        require(isinstance(identifier, str) and bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", identifier)),
                "Invalid route id.")
        require(identifier not in seen_ids, "Duplicate route id.")
        seen_ids.add(identifier)
        text = clean_relative(part.get("path")).as_posix()
        require(text not in seen_paths, "Duplicate route path.")
        seen_paths.add(text)
        limit = part.get("limit", ROUTE_LIMIT)
        require(isinstance(limit, int) and 0 <= limit <= TEXT_LIMIT, "Invalid route size limit.")
        file = home.path(text)
        if not file.is_file():
            if part.get("required", True):
                failed += 1
                results.append({"id": identifier, "path": text, "state": "missing"})
            else:
                results.append({"id": identifier, "path": text, "state": "absent-optional"})
        elif limit and file.stat().st_size > limit:
            failed += 1
            results.append({"id": identifier, "path": text, "state": "oversized",
                            "bytes": file.stat().st_size, "limit": limit})
        else:
            results.append({"id": identifier, "path": text, "state": "ok", "bytes": file.stat().st_size})
    return {"parts": results, "failed": failed}


def release_check(home, project=None, compare=None):
    manifest_file = home.path(MANIFEST_NAME)
    require(manifest_file.is_file(), "Package manifest is missing; run manifest --write.")
    require(manifest_file.stat().st_size <= 4 * 1024 * 1024, "Package manifest is oversized.")
    manifest = check_manifest(json.loads(manifest_file.read_text(encoding="utf-8")))
    version = manifest["version"]
    findings = []
    count = 0

    def record(name, ok, expected, found, where):
        nonlocal count
        count += 1
        if not ok:
            require(len(findings) < 50, "Too many release findings; fix the first batch.")
            findings.append({"check": name, "path": where, "expected": expected, "found": found})

    def top_lines(raw, lines):
        file = home.path(raw)
        require(file.is_file(), "Required package document is missing: " + raw)
        require(file.stat().st_size <= TEXT_LIMIT, "Package document exceeds the scan limit: " + raw)
        text = file.read_text(encoding="utf-8")
        return text, "\n".join(text.splitlines()[:lines])

    record("code-version", VERSION == version, version, VERSION, "TOOLS/homestead.py")
    for raw, marker in (("README.md", "Project Homestead {v}"), ("VERIFICATION.md", "{v}")):
        _, top = top_lines(raw, 3)
        record("document-version", marker.format(v=version) in top, marker.format(v=version),
               "expected version marker missing", raw)
    changelog, _ = top_lines("CHANGELOG.md", 80)
    headings = re.findall(r"^##\s+(\d+\.\d+\.\d+)\s*$", changelog, flags=re.MULTILINE)
    require(headings, "Changelog has no version heading.")
    record("changelog-current", headings[0] == version, version, headings[0], "CHANGELOG.md")
    persona = home.path("TEMPLATES/IDENTITY.md")
    persona_text = ""
    if persona.is_file():
        require(persona.stat().st_size <= TEXT_LIMIT, "Default persona template is oversized.")
        persona_text = persona.read_text(encoding="utf-8")
    missing_markers = [marker for marker in PERSONA_MARKERS if marker not in persona_text]
    record("default-persona", len(persona_text) >= 800 and not missing_markers,
           "complete Vee template of at least 800 bytes with name, voice, role and continuity",
           {"bytes": len(persona_text), "missing": missing_markers}, "TEMPLATES/IDENTITY.md")
    shipped = {entry["path"]: entry["sha256"] for entry in package_manifest(home.root)["files"]}
    declared = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    missing = sorted(set(declared) - set(shipped))
    extra = sorted(set(shipped) - set(declared))
    changed = sorted(path for path in set(declared) & set(shipped) if declared[path] != shipped[path])
    record("manifest-coverage", not (missing or extra or changed), "manifest matches the shipped files",
           {"missing": missing[:5], "extra": extra[:5], "changed": changed[:5]}, MANIFEST_NAME)
    result = {"version": version, "files": len(declared),
              "manifest": {"missing": missing, "extra": extra, "changed": changed}}
    if project:
        root = Path(os.path.abspath(project))
        require(root.is_dir(), "Project folder is not a directory.")
        for name, marker in (("README.md", "Project Homestead {v}"), ("HANDOFF.md", "Homestead {v}")):
            file = root / name
            if not file.is_file():
                record("project-document", False, marker.format(v=version), "missing", name)
                continue
            require(file.stat().st_size <= TEXT_LIMIT, "Project document exceeds the scan limit: " + name)
            top = "\n".join(file.read_text(encoding="utf-8").splitlines()[:8])
            record("project-document", marker.format(v=version) in top, marker.format(v=version), name, name)
    if compare:
        folder = Path(os.path.abspath(compare))
        require(folder.is_dir(), "Comparison folder is not a directory.")
        mismatch = []
        for entry in manifest["files"]:
            target = folder / entry["path"]
            if not target.is_file():
                mismatch.append({"path": entry["path"], "state": "missing"})
            elif hash_file(target) != entry["sha256"]:
                mismatch.append({"path": entry["path"], "state": "differs"})
        record("release-compare", not mismatch, "release folder matches the manifest",
               {"mismatch": len(mismatch)}, folder.as_posix())
        result["compare"] = {"folder": folder.as_posix(), "mismatch": mismatch[:20]}
    result.update({"checks": count, "failed": len(findings), "findings": findings})
    return result


PENDING_SURFACES = ()
COMMANDS = ("apply", "audit", "detect", "doctor", "git", "guardian", "heal", "index", "init", "inspect", "links",
            "lock", "manifest", "method", "now", "plan", "read", "records", "release", "rng", "routes",
            "runtime", "search", "stats", "status", "upgrade", "validate", "write", "xp-preview", "xp-record", "tools", "preflight", "zone", "triage",
            "privacy", "knowledge", "cashbook", "provider", "lookup")
CARD_STATUS = {"VERIFIED", "HYPOTHESIS", "FAILED", "STALE", "SUPERSEDED"}
CARD_LABELS = ("Stable ID", "Title", "Status", "Steward", "Use when", "Procedure",
               "Environment and prerequisites", "What was tried", "What was assumed", "What actually happened",
               "Why it failed", "Replacement or open question", "Known limits and recheck triggers",
               "Superseded by", "Evidence", "Recheck when")
METHOD_REQUIRED = ("Stable ID", "Title", "Status", "Steward", "Use when", "Procedure",
                   "Environment and prerequisites", "Evidence")
FAILURE_REQUIRED = ("Stable ID", "Title", "Status", "Steward", "Use when", "What was tried",
                    "What was assumed", "What actually happened", "Why it failed",
                    "Replacement or open question", "Evidence", "Recheck when")
PROGRESSION_RULES = "levelling-2"
PERSONA_MARKERS = ("Name: Vee", "Voice:", "Role:", "Continuity")
COGNITIVE_RULES = "cognitive-1"
COGNITIVE_REFERENCE = 20
COGNITIVE_BREADTH_STEP = 12.5
COGNITIVE_PROJECT_STEP = 20
COGNITIVE_LETTERS = ((85, "S"), (70, "A"), (55, "B"), (40, "C"), (25, "D"), (0, "E"))
CLOSEOUT_THRESHOLD = 8
CLOSEOUT_LIMIT = 200
CLOSEOUT_EXCLUDED_PARTS = {"node_modules", "_recycle_bin", ".context_state", "__pycache__", ".git", ".venv"}
CLOSEOUT_EXCLUDED_SUFFIXES = (".tmp", ".lock", "~")
CLOSEOUT_PROTECTED_PARTS = {"private", "archive"}


def card_fields(text):
    fields = {}
    for line in text.splitlines():
        if ":" not in line or line.lstrip().startswith(("#", "|", "-")):
            continue
        label, value = line.split(":", 1)
        label = label.strip()
        for known in CARD_LABELS:
            if label == known or (known == "Evidence" and label.startswith("Evidence")):
                fields.setdefault(known, value.strip())
                break
    return fields


def knowledge_cards(home, catalog=None, *, guarded=False, purpose=None):
    raw = catalog or "MEMORY/KNOWLEDGE"
    folder = home.path(raw)
    if not catalog and not folder.is_dir():
        raw = "KNOWLEDGE"
        folder = home.path(raw)
    require(folder.is_dir(), "Knowledge catalog folder is missing.")
    files = [path for path in sorted(folder.glob("*.md")) if path.stem.upper() not in {"INDEX", "CLASSES"}]
    require(len(files) <= 500, "Too many knowledge cards; keep the catalog focused.")
    cards = []
    for path in files:
        require(path.stat().st_size <= 64 * 1024, "Knowledge card exceeds the size limit.")
        if guarded:
            try:
                data, _ = guardian_bytes(home, path.relative_to(home.root).as_posix(), purpose, 64 * 1024)
            except GuardianDenied:
                continue
            text = data.decode("utf-8")
        else:
            text = path.read_text(encoding="utf-8")
        cards.append((path, card_fields(text)))
    return raw, cards


def method_check(home, catalog=None, *, guarded=False, purpose=None):
    label, cards = knowledge_cards(home, catalog, guarded=guarded, purpose=purpose)
    findings = []
    seen = {}
    listing = []
    for path, fields in cards:
        relative = path.relative_to(home.root).as_posix()
        identifier = fields.get("Stable ID", "")
        status = fields.get("Status", "")
        required = FAILURE_REQUIRED if identifier.startswith("fail.") else METHOD_REQUIRED
        problems = []
        if not identifier:
            problems.append("missing-id")
        elif identifier in seen:
            problems.append("duplicate-id")
        if status not in CARD_STATUS:
            problems.append("invalid-status")
        if identifier.startswith("fail.") and status != "FAILED":
            problems.append("failure-status")
        if not identifier.startswith("fail.") and status == "FAILED":
            problems.append("failure-id")
        if status == "SUPERSEDED" and not fields.get("Superseded by"):
            problems.append("superseded-without-target")
        for field in required:
            if not fields.get(field):
                problems.append("missing-" + field.lower().replace(" ", "-"))
        if identifier.startswith("fail.") and not fields.get("Replacement or open question"):
            problems.append("failure-without-replacement")
        if identifier:
            seen.setdefault(identifier, relative)
        listing.append({"id": identifier or None, "status": status or None,
                        "title": fields.get("Title") or None, "path": relative})
        for problem in problems:
            require(len(findings) < 200, "Too many card findings; fix the first batch.")
            findings.append({"card": relative, "id": identifier or None, "problem": problem})
    return {"catalog": label, "cards": listing, "failed": len(findings), "findings": findings}


def method_show(home, identifier, catalog=None, *, guarded=False, purpose=None):
    require(isinstance(identifier, str) and bool(identifier.strip()), "Provide a card ID.")
    label, cards = knowledge_cards(home, catalog, guarded=guarded, purpose=purpose)
    matches = [(path, fields) for path, fields in cards if fields.get("Stable ID") == identifier.strip()]
    require(matches, "No card carries that ID.")
    require(len(matches) == 1, "Duplicate card IDs; repair the catalog before reading one.")
    path, fields = matches[0]
    if guarded:
        data, _ = guardian_bytes(home, path.relative_to(home.root).as_posix(), purpose, 64 * 1024)
        text = data.decode("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    require(len(text) <= 8192, "Card is too large for one bounded read.")
    return {"catalog": label, "id": identifier.strip(), "status": fields.get("Status"),
            "title": fields.get("Title"), "path": path.relative_to(home.root).as_posix(), "text": text}


def cognitive_rank(result):
    scored = [entry["xp"] for entry in result.get("skills", {}).values() if entry["xp"]]
    next_xp = result.get("next_level_xp")
    xp = result.get("xp", 0)
    scores = {
        "depth": min(100, round(max(scored, default=0) / COGNITIVE_REFERENCE * 100)),
        "breadth": min(100, round(len(scored) * COGNITIVE_BREADTH_STEP)),
        "application": min(100, result.get("projects", 0) * COGNITIVE_PROJECT_STEP),
        "progress": 100 if not next_xp else min(100, round(xp / next_xp * 100)),
    }
    ranks = {}
    for name, score in scores.items():
        ranks[name] = {"score": score,
                       "rank": next(letter for minimum, letter in COGNITIVE_LETTERS if score >= minimum)}
    return {"rules": COGNITIVE_RULES, "derived": True, "ranks": ranks}


def status_card(home, raw, write=False, *, purpose=None, guarded=False):
    result = progression(home, raw, purpose=purpose, guarded=guarded)
    parts = clean_relative(result["ledger"]).parts
    card = {"schema": 1, "derived": True, "generated_by": "homestead.py status", "rules": PROGRESSION_RULES,
            "ledger": result["ledger"], "xp": result["xp"], "level": result["level"],
            "next_level_xp": result["next_level_xp"], "title": result["title"],
            "titles": result["titles"], "skills": result["skills"],
            "projects": result.get("projects", 0), "cognitive": cognitive_rank(result),
            "sources": {"ledger": result["sha256"], "catalog": result["catalog_sha256"],
                        "rules": PROGRESSION_RULES}}
    folder = home.path("/".join(parts[:-1]))
    target = folder / "STATUS.json"
    card["path"] = target.relative_to(home.root).as_posix()
    fresh = None
    if target.is_file():
        require(target.stat().st_size <= 256 * 1024, "Derived status card is oversized.")
        try:
            stored = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            stored = {}
        if isinstance(stored, dict) and isinstance(stored.get("sources"), dict):
            fresh = stored["sources"] == card["sources"]
    payload = {"card": card, "fresh": fresh}
    if write:
        require(parts[0] in {"PERSONA", "MEMORY"}, "Derived status is written only inside a persona or memory area.")
        data = (json.dumps(card, indent=1, sort_keys=True) + "\n").encode()
        with home.lock():
            install_bytes(target, data)
        payload.update({"written": card["path"], "fresh": True})
    return payload


def read_config(home):
    path = home.path("MEMORY/CONFIG.json")
    if not path.is_file():
        return {}
    require(path.stat().st_size <= 16 * 1024, "User configuration is oversized.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return {"unreadable": True}
    require(isinstance(value, dict), "User configuration must be an object.")
    return value


def mode_report(home, mode=None):
    config = read_config(home)
    runtime = {"python_ok": sys.version_info >= (3, 13), "file_mutation": os.name in {"nt", "posix"}}
    available = {"standard": True, "enhanced": bool(runtime["python_ok"] and runtime["file_mutation"]),
                 "autonomous": bool(runtime["python_ok"] and runtime["file_mutation"])}
    opt_in = config.get("autonomous_opt_in") is True
    warnings = []
    if config.get("unreadable"):
        warnings.append("MEMORY/CONFIG.json is not valid JSON; defaults apply.")
    requested = mode or config.get("mode") or "auto"
    if requested not in {"auto", "standard", "enhanced", "autonomous"}:
        warnings.append("Unknown mode in configuration; auto applies.")
        requested = "auto"
    if requested == "autonomous" and not opt_in:
        warnings.append("Autonomous mode needs autonomous_opt_in in MEMORY/CONFIG.json.")
        requested = "auto"
    if requested in {"enhanced", "autonomous"} and not available[requested]:
        warnings.append("Requested mode is unavailable on this host; the best available mode applies.")
        requested = "auto"
    selected = requested if requested in {"standard", "enhanced", "autonomous"} else (
        "enhanced" if available["enhanced"] else "standard")
    return {"available": available, "requested": mode or config.get("mode") or "auto",
            "selected": selected, "opt_in": opt_in, "warnings": warnings}


def doctor(home, mode=None):
    runtime = {"os": sys.platform, "python": "%d.%d.%d" % sys.version_info[:3],
               "python_minimum": "3.13", "python_ok": sys.version_info >= (3, 13),
               "file_mutation": os.name in {"nt", "posix"}, "network": False, "third_party_packages": False}
    state = None
    state_info = {"present": home.path(STATE_NAME).is_file()}
    if state_info["present"]:
        try:
            state = read_state(home)
            state_info.update({"valid": True, "version": state["version"],
                               "installed_at": state.get("installed_at")})
        except (SafetyError, ValueError, OSError) as error:
            state_info.update({"valid": False, "error": str(error)})
    manifest_file = home.path(MANIFEST_NAME)
    package = {"present": manifest_file.is_file()}
    declared = {}
    if package["present"]:
        require(manifest_file.stat().st_size <= 4 * 1024 * 1024, "Package manifest is oversized.")
        manifest = check_manifest(json.loads(manifest_file.read_text(encoding="utf-8")))
        declared = {entry["path"]: entry for entry in manifest["files"]}
        package.update({"version": manifest["version"], "files": len(declared)})
    missing = []
    size_changed = []
    for text, entry in declared.items():
        target = home.path(text)
        if not target.is_file():
            missing.append(text)
        elif target.stat().st_size != entry["bytes"]:
            size_changed.append(text)
    package.update({"missing": missing[:10], "size_changed": size_changed[:10]})
    state_version = state_info.get("version")
    version_sync = None
    if state_version is not None and package.get("version"):
        version_sync = state_version == package["version"]
    startup = routes_check(home)
    startup_bytes = sum(part.get("bytes", 0) for part in startup["parts"] if part["state"] == "ok")
    lock_info = lock_report(home)
    limits = ["Manifest comparison uses recorded sizes; run release for byte hashes.",
              "Mode availability follows detected capabilities, not model names."]
    if not runtime["file_mutation"]:
        limits.insert(0, "File mutation is unavailable on this platform; reads, checks and derivation still work.")
    config = read_config(home)
    compliance = config.get("license_compliance", True)
    warnings = []
    if not isinstance(compliance, bool):
        warnings.append("license_compliance must be true or false; true applies.")
        compliance = True
    briefing = home.path("SYSTEM/POLICIES/EULA.md")
    if not briefing.is_file():
        warnings.append("License briefing is missing; treat third-party licenses as unverified.")
    if not compliance:
        warnings.append("License checks are disabled; this grants no additional rights.")
    modes = mode_report(home, mode)
    warnings = modes["warnings"] + warnings
    cache = {"index": {"present": home.path(INDEX_NAME).is_file()}, "health": None}
    try:
        health = health_read(home)
    except (SafetyError, OSError):
        health = None
    if health:
        cache["health"] = {"state": health.get("state"), "updated": health.get("updated"),
                           "documents": health.get("documents")}
    return {"runtime": runtime, "commands": list(COMMANDS),
            "home": {"root": home.root.as_posix(),
                     "user_areas": sorted(name for name in USER_ROOTS if home.path(name).exists())},
            "package": package, "state": state_info, "version_in_sync": version_sync,
            "startup": {"parts": len(startup["parts"]), "failed": startup["failed"], "bytes": startup_bytes},
            "lock": lock_info, "modes": modes, "cache": cache,
            "license": {"compliance": compliance, "briefing": "SYSTEM/POLICIES/EULA.md",
                        "briefing_present": briefing.is_file()},
            "warnings": warnings,
            "pending": list(PENDING_SURFACES), "limits": limits}


AUDIT_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("credential", re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*['\"]?[A-Za-z0-9/+=_-]{12,}")),
)
DRIVE_PATH = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])")


def absolute_path(line):
    if DRIVE_PATH.search(line):
        return True
    for prefix in ("/" + "Users/", "/" + "home/"):
        if prefix in line:
            return True
    return False


def audit(home, path=None):
    root = home.root if path is None else Path(os.path.abspath(path))
    require(root.is_dir(), "Audit target is not a directory.")
    if path is None:
        files = [home.path(entry["path"]) for entry in package_manifest(home.root)["files"]]
    else:
        files = [item for item in sorted(root.rglob("*")) if item.is_file()]
        require(len(files) <= LIMIT_FILES, "Audit target has too many files.")
    findings = []
    scanned = 0
    warnings = []
    markers = read_config(home).get("private_markers", [])
    if not isinstance(markers, list) or len(markers) > 20 or any(
            not isinstance(marker, str) or not 1 <= len(marker) <= 64 for marker in markers):
        markers = []
        warnings.append("private_markers must be a list of up to 20 short strings; none applied.")
    text_suffixes = {".md", ".json", ".txt", ".py", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".html"}

    def note(relative, kind, detail):
        require(len(findings) < 100, "Too many audit findings; fix the first batch.")
        findings.append({"path": relative, "kind": kind, "detail": detail})

    for item in files:
        relative = item.relative_to(root).as_posix() if path is not None else item.relative_to(home.root).as_posix()
        parts = set(Path(relative).parts)
        scanned += 1
        if ".git" in parts:
            continue
        if parts & {"__pycache__", ".recycle", "ARCHIVE"}:
            note(relative, "runtime-artifact", "path lives in a runtime or recovery area")
            continue
        if item.suffix.lower() in {".log", ".bak", ".tmp", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".db"}:
            note(relative, "runtime-artifact", "log, cache or database file")
            continue
        if item.name == ".env" or item.name.startswith(".env."):
            note(relative, "credential", "environment file present")
            continue
        if item.suffix.lower() not in text_suffixes:
            continue
        require(item.stat().st_size <= TEXT_LIMIT, "Audit text file exceeds the scan limit: " + relative)
        for number, line in enumerate(item.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for marker in markers:
                if marker in line:
                    note(relative, "private-marker", "line %d names a configured marker" % number)
            for kind, pattern in AUDIT_PATTERNS:
                if pattern.search(line):
                    note(relative, kind, "line %d matched a redacted %s" % (number, kind))
            if absolute_path(line):
                note(relative, "absolute-path", "line %d contains a local absolute path" % number)
    return {"scope": root.as_posix(), "files": scanned, "failed": len(findings), "markers": len(markers),
            "warnings": warnings, "redacted": True, "findings": findings}


RUNTIME_KINDS = ("doctor", "links", "routes", "audit", "release", "inference")
RUNTIME_DEFAULT = {"schema": 1, "max_tasks_per_run": 10, "max_attempts": 3, "backoff_seconds": 30,
                   "requests_used": 0, "tasks_used": 0, "tokens": None, "measured_tokens": False}
RUNTIME_STATE = {"schema": 1, "mode": "stopped", "last_beat": None, "runs": 0,
                 "tasks_done": 0, "tasks_failed": 0}


def runtime_fields(home):
    return {"queue": home.path("MEMORY/RUNTIME/queue.json"),
            "state": home.path("MEMORY/RUNTIME/state.json"),
            "budget": home.path("MEMORY/RUNTIME/budget.json"),
            "events": home.path("MEMORY/RUNTIME/events.log"),
            "stop": home.path("MEMORY/RUNTIME/STOP")}


def runtime_load(path, default):
    if not path.is_file():
        return json.loads(json.dumps(default))
    require(path.stat().st_size <= 256 * 1024, "Runtime record is oversized.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return json.loads(json.dumps(default))
    return value if isinstance(value, dict) else json.loads(json.dumps(default))


def runtime_save(path, value):
    install_bytes(path, (json.dumps(value, indent=1, sort_keys=True) + "\n").encode())


def runtime_event(home, line):
    path = runtime_fields(home)["events"]
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    lines.append(stamp() + " " + line)
    install_bytes(path, ("\n".join(lines[-200:]) + "\n").encode())


def runtime_status(home):
    fields = runtime_fields(home)
    queue = runtime_load(fields["queue"], {"schema": 1, "tasks": []})
    state = runtime_load(fields["state"], RUNTIME_STATE)
    budget = runtime_load(fields["budget"], RUNTIME_DEFAULT)
    tasks = queue.get("tasks", [])
    counts = {}
    for task in tasks:
        status = task.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    health = "ok"
    if state.get("mode") == "running":
        beat = state.get("last_beat")
        health = "interrupted"
        if isinstance(beat, str):
            try:
                health = "ok" if (datetime.now(timezone.utc) - datetime.fromisoformat(beat)).total_seconds() < 600 \
                    else "interrupted"
            except ValueError:
                health = "interrupted"
    elif state.get("mode") not in {"stopped", "paused"}:
        health = "unknown"
    lines = fields["events"].read_text(encoding="utf-8").splitlines() if fields["events"].is_file() else []
    return {"mode": state.get("mode"), "health": health, "stop": fields["stop"].is_file(),
            "tasks": len(tasks), "counts": counts,
            "state": {key: state.get(key) for key in ("last_beat", "runs", "tasks_done", "tasks_failed")},
            "budget": budget, "recent": lines[-5:],
            "tokens": {"measured": False, "value": None, "note": "The deterministic runtime makes no model call."}}


def runtime_execute(home, task):
    kind = task.get("kind")
    if kind == "inference":
        raise SafetyError("No provider adapter is configured; no request was made.")
    if kind == "doctor":
        return {"kind": kind, "startup_failed": doctor(home)["startup"]["failed"]}
    checks = {"links": links_check, "routes": routes_check, "audit": audit}
    if kind in checks:
        return {"kind": kind, "failed": checks[kind](home)["failed"]}
    if kind == "release":
        return {"kind": kind, "failed": release_check(home)["failed"]}
    raise SafetyError("Unknown task kind: " + str(kind))


def runtime_command(home, action, kind=None, payload=None, limit=None, now=False):
    require(action in {"status", "add", "start", "pause", "resume", "stop", "run"}, "Unknown runtime action.")
    if action == "status":
        return runtime_status(home)
    require_mutation()
    if action in {"start", "run"}:
        require(read_config(home).get("autonomous_opt_in") is True,
                "Autonomous mode needs autonomous_opt_in in MEMORY/CONFIG.json.")
    require(kind in RUNTIME_KINDS if action == "add" else True, "Unknown task kind.")
    with home.lock():
        fields = runtime_fields(home)
        fields["queue"].parent.mkdir(parents=True, exist_ok=True)
        check_chain(fields["queue"].parent)
        queue = runtime_load(fields["queue"], {"schema": 1, "tasks": []})
        state = runtime_load(fields["state"], RUNTIME_STATE)
        budget = runtime_load(fields["budget"], RUNTIME_DEFAULT)
        tasks = queue.setdefault("tasks", [])
        if action == "add":
            text = (payload or "").strip()
            require(len(text) <= 512, "Task payload must be at most 512 characters.")
            identifier = "task." + digest((kind + "|" + text).encode())[:16]
            for task in tasks:
                if task.get("id") == identifier:
                    return {"added": False, "id": identifier, "status": task.get("status")}
            tasks.append({"id": identifier, "kind": kind, "payload": text, "status": "pending",
                          "attempts": 0, "created": stamp(), "last_error": None,
                          "not_before": None, "result": None})
            runtime_save(fields["queue"], queue)
            runtime_event(home, "add " + identifier + " " + kind)
            return {"added": True, "id": identifier, "status": "pending"}
        if action in {"start", "pause", "resume", "stop"}:
            if action == "start":
                if fields["stop"].is_file():
                    fields["stop"].unlink()
                state["mode"] = "running"
                state["last_beat"] = stamp()
            elif action == "pause":
                state["mode"] = "paused"
            elif action == "resume":
                state["mode"] = "running"
                state["last_beat"] = stamp()
            else:
                state["mode"] = "stopped"
                if now:
                    install_bytes(fields["stop"], (json.dumps({"reason": "emergency stop",
                                                               "at": stamp()}) + "\n").encode())
            runtime_save(fields["state"], state)
            runtime_event(home, action + (" emergency" if now else ""))
            return {"mode": state["mode"], "stop": fields["stop"].is_file()}
        require(state.get("mode") == "running", "Start the runtime before running tasks.")
        require(not fields["stop"].is_file(), "The emergency stop flag is set; clear it with runtime start.")
        cap = budget.get("max_tasks_per_run", 10)
        require(isinstance(cap, int) and 1 <= cap <= 100, "Runtime budget is invalid.")
        if limit is not None:
            require(1 <= limit <= cap, "The run limit must be within the configured budget.")
        allowed = min(limit or cap, cap)
        ran = []
        for task in tasks:
            if len(ran) >= allowed:
                break
            if task.get("status") not in {"pending", "retry"}:
                continue
            due = task.get("not_before")
            if isinstance(due, str):
                try:
                    if datetime.fromisoformat(due) > datetime.now(timezone.utc):
                        continue
                except ValueError:
                    pass
            if task.get("kind") == "inference":
                task["status"] = "blocked"
                task["last_error"] = "No provider adapter is configured; no request was made."
                ran.append({"id": task["id"], "status": "blocked"})
                runtime_save(fields["queue"], queue)
                continue
            task["attempts"] = int(task.get("attempts", 0)) + 1
            try:
                task["result"] = runtime_execute(home, task)
                task["status"] = "done"
                task["last_error"] = None
                state["tasks_done"] = int(state.get("tasks_done", 0)) + 1
            except (SafetyError, OSError, ValueError) as error:
                task["last_error"] = str(error)
                if task["attempts"] >= budget.get("max_attempts", 3):
                    task["status"] = "failed"
                    state["tasks_failed"] = int(state.get("tasks_failed", 0)) + 1
                else:
                    task["status"] = "retry"
                    task["not_before"] = (datetime.now(timezone.utc) + timedelta(
                        seconds=budget.get("backoff_seconds", 30) * task["attempts"])).isoformat()
            state["last_beat"] = stamp()
            runtime_save(fields["queue"], queue)
            runtime_save(fields["state"], state)
            ran.append({"id": task["id"], "status": task["status"]})
        budget["tasks_used"] = int(budget.get("tasks_used", 0)) + len(ran)
        state["runs"] = int(state.get("runs", 0)) + 1
        state["last_beat"] = stamp()
        runtime_save(fields["budget"], budget)
        runtime_save(fields["state"], state)
        runtime_event(home, "run %d task(s)" % len(ran))
        return {"ran": ran, "budget": {key: budget[key] for key in ("max_tasks_per_run", "tasks_used")}}


def git_command(cwd, *args, check=True, encoding=None):
    require(shutil.which("git"), "Git is not available; Smart Git stays optional.")
    completed = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding=encoding, timeout=120)
    if check and completed.returncode != 0:
        raise SafetyError("Git refused %s: %s" % (" ".join(args[:2]), completed.stderr.strip()[:300]))
    return completed


def repo_root(path):
    if not shutil.which("git"):
        return None
    completed = git_command(path, "rev-parse", "--show-toplevel", check=False)
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    return Path(completed.stdout.strip()).resolve()


def git_identity(repo):
    if git_command(repo, "config", "user.email", check=False).stdout.strip():
        return []
    return ["-c", "user.name=Homestead", "-c", "user.email=homestead@localhost"]


def export_files(home):
    manifest = check_manifest(json.loads(home.path(MANIFEST_NAME).read_text(encoding="utf-8")))
    files = sorted({entry["path"] for entry in manifest["files"]} | {MANIFEST_NAME})
    extras = sorted(clean_relative(path).as_posix() for path in manifest.get("export_extra", []))
    return manifest, files, extras


def export_source(home, text):
    return home.root.parent / text


def export_fingerprint(target, files, extras=()):
    entries = []
    for text in list(files) + list(extras):
        path = target / text
        require(path.is_file(), "Export is missing " + text)
        entries.append({"path": text, "sha256": hash_file(path)})
    return digest(packed({"files": entries}))


def git_status(home, public=None):
    local = repo_root(home.root)
    report = {"git": bool(shutil.which("git")), "local": local.as_posix() if local else None}
    if local:
        changes = git_command(local, "status", "--porcelain", check=False).stdout.splitlines()
        report.update({"branch": git_command(local, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip(),
                       "changed": len(changes), "changed_paths": [line[3:] for line in changes[:20]],
                       "remotes": len(git_command(local, "remote", check=False).stdout.split())})
    if public:
        target = Path(os.path.abspath(public))
        public_root = repo_root(target) if target.is_dir() else None
        report["public"] = {"path": target.as_posix(),
                            "repository": public_root.as_posix() if public_root else None,
                            "independent": bool(public_root and local and public_root != local)}
    return report


def git_export(home, destination):
    target = Path(os.path.abspath(destination))
    local = repo_root(home.root)
    require(not target.is_relative_to(home.root), "The export must live outside the home.")
    require(local is None or (target != local and not target.is_relative_to(local)),
            "The export must not be the local repository.")
    manifest, files, extras = export_files(home)
    release = release_check(home)
    require(not release["failed"], "The package has release findings; fix them before exporting:"
            " " + ", ".join(entry["check"] for entry in release["findings"][:5]))
    if target.exists():
        require(target.is_dir(), "Export destination is not a folder.")
        existing = [item for item in target.iterdir() if item.name != ".git"]
        require(not existing or (target / EXPORT_STATE).is_file(),
                "Refusing to overwrite a folder this tool did not export.")
    target.mkdir(parents=True, exist_ok=True)
    keep = set(files) | {EXPORT_STATE}
    for item in sorted(target.rglob("*"), reverse=True):
        relative = item.relative_to(target)
        if relative.parts[0] == ".git" or relative.as_posix() in keep:
            continue
        if item.is_file() or item.is_symlink():
            item.unlink()
    for directory in sorted((item for item in target.rglob("*") if item.is_dir()), reverse=True):
        if directory.relative_to(target).parts[0] == ".git":
            continue
        if not any(directory.iterdir()):
            directory.rmdir()
    for text in files:
        source = home.path(text)
        require(source.is_file(), "Package file is missing: " + text)
        destination_path = target / text
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        install_bytes(destination_path, source.read_bytes())
    included = []
    skipped = []
    for text in extras:
        source = export_source(home, text)
        if not source.is_file():
            skipped.append({"path": text, "reason": "not present beside the home"})
            continue
        destination_path = target / text
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        install_bytes(destination_path, source.read_bytes())
        included.append(text)
    fingerprint = export_fingerprint(target, files, included)
    record = {"schema": 1, "version": manifest["version"], "fingerprint": fingerprint,
              "files": files, "extras": [{"path": text, "sha256": hash_file(target / text)} for text in included],
              "exported_at": stamp()}
    install_bytes(target / EXPORT_STATE, (json.dumps(record, indent=1, sort_keys=True) + "\n").encode())
    return {"destination": target.as_posix(), "version": manifest["version"], "files": len(files),
            "fingerprint": fingerprint, "record": EXPORT_STATE,
            "extras": included, "extras_skipped": skipped}


def git_verify(home, destination):
    target = Path(os.path.abspath(destination))
    require(target.is_dir() and (target / EXPORT_STATE).is_file(), "No export record; export first.")
    local = repo_root(home.root)
    require(not target.is_relative_to(home.root), "The export must live outside the home.")
    require(local is None or not target.is_relative_to(local), "The export must not be the local repository.")
    require((target / EXPORT_STATE).stat().st_size <= 1024 * 1024, "Export record is oversized.")
    record = json.loads((target / EXPORT_STATE).read_text(encoding="utf-8"))
    require(isinstance(record, dict) and record.get("schema") == 1, "Unsupported export record.")
    _, files, extras = export_files(home)
    recorded = {entry["path"]: entry["sha256"] for entry in record.get("extras", [])
                if isinstance(entry, dict) and isinstance(entry.get("path"), str)}
    findings = []
    for text in files:
        path = target / text
        source = home.path(text)
        if not path.is_file():
            findings.append({"path": text, "problem": "missing"})
        elif not source.is_file() or hash_file(path) != hash_file(source):
            findings.append({"path": text, "problem": "differs"})
    for text in extras:
        path = target / text
        expected = recorded.get(text)
        if expected is None:
            if path.is_file():
                findings.append({"path": text, "problem": "unrecorded-extra"})
            continue
        if not path.is_file():
            findings.append({"path": text, "problem": "missing-extra"})
            continue
        if hash_file(path) != expected:
            findings.append({"path": text, "problem": "differs"})
            continue
        source = export_source(home, text)
        if source.is_file() and hash_file(source) != expected:
            findings.append({"path": text, "problem": "source-differs"})
    allowed = set(files) | set(extras) | {EXPORT_STATE}
    for item in sorted(target.rglob("*")):
        relative = item.relative_to(target).as_posix()
        if relative.split("/")[0] == ".git" or relative in allowed:
            continue
        if item.is_file():
            findings.append({"path": relative, "problem": "extra"})
    present = [text for text in files if (target / text).is_file()]
    extras_present = [text for text in extras if text in recorded and (target / text).is_file()]
    fingerprint = export_fingerprint(target, present, extras_present) if len(present) == len(files) else None
    release = release_check(Home(target))
    findings.extend({"path": entry["path"], "problem": "release-" + entry["check"]} for entry in release["findings"])
    findings.extend({"path": entry["path"], "problem": "audit-" + entry["kind"]}
                    for entry in audit(home, target)["findings"])
    passed = bool(fingerprint) and not findings and fingerprint == record.get("fingerprint")
    return {"passed": passed, "fingerprint": fingerprint, "recorded": record.get("fingerprint"),
            "files": len(files), "extras": len(extras), "findings": findings[:50]}


def git_checkpoint(home, paths, message, include_ignored=False, allow_missing=False):
    require_mutation()
    local = repo_root(home.root)
    require(local is not None, "The home is not inside a Git repository.")
    require(paths, "Provide at least one exact path to checkpoint.")
    require(isinstance(message, str) and 1 <= len(message.strip()) <= 200, "Provide a one-line commit message.")
    cleaned = []
    for raw in paths:
        target = home.path(raw, exists=not allow_missing)
        require(target.is_relative_to(local), "Checkpoint paths must stay inside the local repository.")
        require(not target.is_dir(), "Checkpoint scope needs exact files.")
        cleaned.append(target.relative_to(local).as_posix())
    options = ["-f"] if include_ignored else []
    diff_args = ("--name-only", "--no-renames", "-z", "--", *cleaned)
    before = git_command(local, "--literal-pathspecs", "diff", "--cached", *diff_args, encoding="utf-8")
    unstaged = git_command(local, "--literal-pathspecs", "diff", *diff_args, encoding="utf-8")
    partially_staged = set(before.stdout.split("\0")) & set(unstaged.stdout.split("\0"))
    require(not (partially_staged - {""}),
            "A selected file is partially staged. Review its staged changes before closeout.")
    git_command(local, "--literal-pathspecs", "add", *options, "--", *cleaned)
    staged = git_command(local, "--literal-pathspecs", "diff", "--cached", "--name-only", "--", *cleaned)
    if not staged.stdout.strip():
        return {"committed": None, "message": "Nothing staged."}
    git_command(local, "--literal-pathspecs", *git_identity(local), "commit", "--only", "-m", message.strip(),
                "--", *cleaned)
    return {"committed": git_command(local, "rev-parse", "HEAD").stdout.strip()[:12], "files": cleaned}


def closeout_excluded(relative):
    parts = relative.split("/")
    if any(part in CLOSEOUT_EXCLUDED_PARTS for part in parts):
        return True
    name = parts[-1]
    return name.startswith("~$") or name.endswith(CLOSEOUT_EXCLUDED_SUFFIXES)


def closeout_protected(relative):
    return any(part in CLOSEOUT_PROTECTED_PARTS for part in relative.lower().split("/")[:-1])


def closeout_group(state):
    if state == "??":
        return "untracked"
    if "U" in state or state in {"AA", "DD"}:
        return "conflict"
    if "D" in state:
        return "deleted"
    if "A" in state:
        return "added"
    if "R" in state:
        return "renamed"
    if "C" in state:
        return "copied"
    return "modified"


def closeout_entries(home, local, paths):
    report = git_command(local, "--literal-pathspecs", "status", "--porcelain=v1", "-z", "-uall",
                         "--", *paths, encoding="utf-8")
    entries = []
    records = iter(report.stdout.split("\0"))
    for line in records:
        if len(line) < 4 or line[:2] == "!!":
            continue
        state, text = line[:2], line[3:]
        source = None
        if any(kind in state for kind in "RC"):
            try:
                source = clean_relative(next(records, "")).as_posix()
            except SafetyError:
                source = None
        try:
            relative = clean_relative(text).as_posix()
        except SafetyError:
            entries.append({"path": text, "state": state, "group": "unparsed", "source": source})
            continue
        group = closeout_group(state)
        resolved = (local / relative).resolve()
        if not resolved.is_relative_to(home.root):
            entries.append({"path": relative, "state": state, "group": "outside-home", "source": source})
            continue
        entries.append({"path": resolved.relative_to(home.root).as_posix(), "repo_path": relative,
                        "state": state, "group": group, "source": source})
    return sorted(entries, key=lambda entry: entry["path"])


def closeout_kind(local, entry):
    if entry["group"] != "renamed" or not entry.get("source"):
        return entry["group"]
    head = git_command(local, "rev-parse", "HEAD:" + entry["source"], check=False)
    current = git_command(local, "hash-object", "--", entry.get("repo_path", entry["path"]), check=False)
    before, after = head.stdout.strip(), current.stdout.strip()
    if head.returncode == 0 and current.returncode == 0 and before and before == after:
        return "renamed-clean"
    return "renamed-edited"


def closeout_scan(home, repo=None, limit=CLOSEOUT_LIMIT, *, files=None):
    local = Path(os.path.abspath(repo)).resolve() if repo else repo_root(home.root)
    require(local is not None, "Closeout needs Git available and the home inside a repository.")
    require(home.root.is_relative_to(local), "The home must stay inside the scanned repository.")
    paths = []
    for raw in files or ():
        target = home.path(raw)
        require(not target.is_dir(), "Closeout scope needs exact files.")
        paths.append(target.relative_to(local).as_posix())
    entries = closeout_entries(home, local, paths)
    counts = {}
    candidates = []
    protected = []
    for entry in entries:
        counts[entry["group"]] = counts.get(entry["group"], 0) + 1
        if entry["group"] in {"outside-home", "unparsed"}:
            continue
        if closeout_excluded(entry["path"]):
            continue
        if closeout_protected(entry["path"]):
            protected.append(entry["path"])
            continue
        candidates.append({**entry, "kind": closeout_kind(local, entry)})
    gates = []
    if counts.get("deleted"):
        gates.append("a deleted path came without a recorded rename")
    if counts.get("conflict"):
        gates.append("an unresolved merge conflict is present")
    if protected:
        gates.append("a protected path needs an explicit file list")
    if len(candidates) >= CLOSEOUT_THRESHOLD:
        gates.append("%d eligible paths exceed the threshold of %d" % (len(candidates), CLOSEOUT_THRESHOLD - 1))
    if counts.get("unparsed"):
        gates.append("a path with quoted characters needs an explicit file list")
    return {"repo": local.as_posix(), "home": home.root.as_posix(), "counts": counts,
            "changed": len(entries), "candidates": candidates[:limit], "candidate_count": len(candidates),
            "protected": protected[:limit], "gates": gates, "clean": not entries}


def closeout(home, action, repo=None, files=None, message=None):
    scan = closeout_scan(home, repo, limit=max(CLOSEOUT_LIMIT, len(files or ())), files=files)
    if action == "scan":
        return scan
    require_mutation()
    if scan["clean"]:
        return {**scan, "committed": None, "message": "Nothing to close out."}
    available = {entry["path"]: entry for entry in scan["candidates"]}
    if files:
        chosen = []
        rename_sources = {entry["source"] for entry in scan["candidates"] if entry["group"] == "renamed"}
        for raw in files:
            relative = clean_relative(raw).as_posix()
            if relative in scan["protected"]:
                raise SafetyError("A protected path is never closed automatically: " + relative)
            if relative not in available and home.path(relative).relative_to(Path(scan["repo"])).as_posix() in rename_sources:
                continue
            require(relative in available, "Requested path is not an eligible pending change: " + relative)
            require(available[relative]["group"] != "conflict", "Resolve the selected conflict before closeout.")
            chosen.append(relative)
    else:
        require(not scan["gates"], "Closeout is gated: " + "; ".join(scan["gates"]) +
                ". Pass --path to choose files explicitly.")
        chosen = [entry["path"] for entry in scan["candidates"]]
    chosen = list(dict.fromkeys(chosen))
    for entry in scan["candidates"]:
        if entry["path"] not in chosen or entry["group"] != "renamed":
            continue
        require(entry.get("source"), "Select both exact rename paths before closeout.")
        local = Path(scan["repo"])
        source = (local / entry["source"]).resolve()
        require(source.is_relative_to(home.root), "Rename source is outside the home.")
        relative = source.relative_to(home.root).as_posix()
        require(not closeout_protected(relative), "Rename source is protected.")
        require(not files or relative in files, "Select both exact rename paths before closeout.")
        if relative not in chosen:
            chosen.append(relative)
    require(chosen, "No eligible path to close out.")
    require(isinstance(message, str) and message.strip(), "Provide a one-line message for the closeout.")
    result = git_checkpoint(home, chosen, message, allow_missing=True)
    return {**scan, **result, "closed": chosen}


def git_publish(home, destination, confirm, message=None):
    require_mutation()
    target = Path(os.path.abspath(destination))
    local = repo_root(home.root)
    require(local is not None, "The home is not inside a Git repository.")
    require(target != local and not target.is_relative_to(local),
            "The public export must be a separate repository.")
    verify = git_verify(home, target)
    require(verify["passed"], "Export verification failed; publication is blocked.")
    require(confirm == verify["fingerprint"], "Confirm with the verified export fingerprint.")
    existing = repo_root(target)
    if existing is not None:
        require(existing == target, "The export folder belongs to another repository.")
    for name in git_command(local, "remote", check=False).stdout.split():
        url = git_command(local, "remote", "get-url", name, check=False).stdout.strip()
        if url:
            require(Path(url).resolve() != target, "The local repository has a remote pointing at the export.")
    if existing is None:
        git_command(target, "init")
    identity = git_identity(target)
    _, files, extras = export_files(home)
    exported = [entry["path"] for entry in json.loads((target / EXPORT_STATE).read_text(encoding="utf-8")).get("extras", [])
                if isinstance(entry, dict) and isinstance(entry.get("path"), str)]
    staged_extras = [text for text in extras if text in exported and (target / text).is_file()]
    git_command(target, *identity, "add", "--", *files, *staged_extras, EXPORT_STATE)
    if not git_command(target, "status", "--porcelain", check=False).stdout.strip():
        return {"committed": None, "message": "Nothing new to publish.", "pushed": False}
    text = (message or "vhd export " + stamp()).strip()
    require(1 <= len(text) <= 200, "Provide a one-line commit message.")
    git_command(target, *identity, "commit", "-m", text)
    return {"committed": git_command(target, "rev-parse", "HEAD").stdout.strip()[:12],
            "branch": git_command(target, "rev-parse", "--abbrev-ref", "HEAD", check=False).stdout.strip(),
            "pushed": False, "remotes": len(git_command(target, "remote", check=False).stdout.split())}


def install_bytes(path, data):
    check_chain(path.parent)
    tmp = path.parent / ("install-" + uuid.uuid4().hex + ".tmp")
    with tmp.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    require(hash_file(tmp) == digest(data), "Staged file changed before install.")
    if path.exists():
        check_node(path)
        os.replace(tmp, path)
    else:
        no_replace(tmp, path)
    require(path.is_file() and hash_file(path) == digest(data), "Installed file does not match its bytes.")


def home_hash_index(home):
    index = {}
    count = 0
    for path in sorted(home.root.rglob("*")):
        relative = path.relative_to(home.root)
        if relative.parts[0] in SKIP_ROOTS or any(part in SKIP_PARTS for part in relative.parts):
            continue
        if not path.is_file():
            continue
        count += 1
        require(count <= LIMIT_FILES, "Home has too many files to compare.")
        try:
            index.setdefault(hash_file(path), []).append(relative.as_posix())
        except (OSError, SafetyError):
            continue
    return index


def read_checksum(path):
    file = Path(os.path.abspath(path))
    require(file.is_file() and file.stat().st_size <= 4096, "Checksum file is missing or oversized.")
    parts = file.read_text(encoding="utf-8").strip().split()
    require(parts and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]), "Checksum file has no SHA-256 digest.")
    return parts[0].lower()


def inspect_archive(archive):
    path = Path(os.path.abspath(archive))
    require(path.is_file(), "Archive is not a file.")
    require(zipfile.is_zipfile(path), "File is not a valid ZIP archive.")
    entries = []
    total = 0
    seen = set()
    with zipfile.ZipFile(path) as bundle:
        infos = bundle.infolist()
        require(len(infos) <= LIMIT_FILES, "Archive lists too many entries.")
        for info in infos:
            if info.is_dir():
                continue
            text = clean_relative(info.filename).as_posix()
            require(text.casefold() not in seen, "Archive contains a duplicate or case-colliding path: " + text)
            seen.add(text.casefold())
            require(not info.flag_bits & 0x1, "Encrypted archive entries are refused: " + text)
            require((info.external_attr >> 16) & 0o170000 in {0, 0o100000},
                    "Archive contains a link or special entry: " + text)
            require(info.file_size <= 64 * 1024 * 1024, "Archive entry is too large: " + text)
            if info.file_size:
                require(info.file_size / max(info.compress_size, 1) <= 200,
                        "Archive entry expands too far to trust: " + text)
            total += info.file_size
            require(total <= LIMIT_BYTES, "Archive expands beyond the supported size.")
            entries.append((text, info.file_size))
    require(entries, "Archive has no files to install.")
    return entries, total


def extract_archive(archive, entries, destination):
    destination.mkdir()
    with zipfile.ZipFile(archive) as bundle:
        for text, size in entries:
            target = destination / text
            target.parent.mkdir(parents=True, exist_ok=True)
            check_chain(target.parent)
            written = 0
            with bundle.open(text) as source, target.open("xb") as output:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    require(written <= size, "Archive entry is larger than declared: " + text)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            require(written == size, "Extracted size mismatch: " + text)


def upgrade(home, package=None, write=False, confirm=None, archive=None, checksum=None):
    stage = None
    archive_info = None
    try:
        if archive:
            archive_path = Path(os.path.abspath(archive))
            entries, total = inspect_archive(archive_path)
            archive_info = {"path": archive_path.as_posix(), "entries": len(entries), "bytes": total,
                            "authenticity": "a checksum alone does not establish a publisher"}
            if checksum:
                require(hash_file(archive_path) == read_checksum(checksum),
                        "Archive checksum does not match the detached digest.")
                archive_info["integrity"] = "verified against the supplied digest"
            else:
                archive_info["integrity"] = "unverified; no detached digest supplied"
            stage = Path(tempfile.mkdtemp(prefix="vhd-stage-", dir=archive_path.parent))
            require(not stage.is_relative_to(home.root), "Staging must stay outside the home.")
            extract_archive(archive_path, entries, stage / "package")
            package = stage / "package"
        require(package is not None, "Provide a package folder or a release archive.")
        result = upgrade_package(home, package, write, confirm)
        if archive_info:
            result["archive"] = archive_info
        return result
    finally:
        if stage is not None:
            shutil.rmtree(stage, ignore_errors=True)


def upgrade_package(home, package, write=False, confirm=None):
    pkg = Path(os.path.abspath(package))
    require(pkg.is_dir(), "Package folder is not a directory.")
    manifest_file = pkg / MANIFEST_NAME
    if manifest_file.is_file():
        require(manifest_file.stat().st_size <= 4 * 1024 * 1024, "Package manifest is oversized.")
        manifest = check_manifest(json.loads(manifest_file.read_text(encoding="utf-8")))
        manifest_source = MANIFEST_NAME
    else:
        manifest = package_manifest(pkg)
        manifest_source = "generated"
    state = read_state(home)
    base = {entry["path"]: entry["sha256"] for entry in state["manifest"]["files"]} if state else {}
    index = home_hash_index(home) if state else {}
    entries = []
    new_paths = set()
    for item in manifest["files"]:
        relative = clean_relative(item["path"])
        text = relative.as_posix()
        new_paths.add(text)
        if relative.parts[0] in USER_ROOTS or text == STATE_NAME:
            entries.append({"path": text, "class": "refused", "reason": "user zone is never written"})
            continue
        target = home.path(text)
        current = hash_file(target) if target.is_file() else None
        expected = base.get(text)
        relocated = None
        if current is None and expected is not None:
            others = [item for item in index.get(expected, []) if item != text]
            if len(others) == 1:
                relocated = others[0]
        if current is None:
            if relocated:
                klass = "relocated"
            else:
                klass = "new" if expected is None else "deleted-locally"
        elif expected is None:
            klass = "conflict"
        elif current == expected:
            klass = "stale" if item["sha256"] != expected else "unchanged"
        elif item["sha256"] == current:
            klass = "applied"
        else:
            klass = "local" if item["sha256"] == expected else "conflict"
        entry = {"path": text, "class": klass, "package_sha256": item["sha256"],
                 "base_sha256": expected, "current_sha256": current}
        if relocated:
            entry["relocated_to"] = relocated
            entry["suggestion"] = "identical content sits at another path; confirm whether to restore the manifest path"
        elif klass == "conflict":
            entry["suggestion"] = "compare both versions, then keep yours, take the package, or keep both"
        elif klass == "deleted-locally":
            entry["suggestion"] = "you removed this file; add it back only if you want it"
        entries.append(entry)
    for text in sorted(set(base) - new_paths):
        entries.append({"path": text, "class": "dropped", "base_sha256": base[text],
                        "suggestion": "kept in place; recycle it yourself if it is no longer wanted"})
    counts = {}
    for entry in entries:
        counts[entry["class"]] = counts.get(entry["class"], 0) + 1
    home_version = state["version"] if state else None
    if home_version:
        require(version_key(home_version) <= version_key(manifest["version"]),
                "Package is older than this home.")
    fingerprint = digest(packed({"version": manifest["version"], "entries": entries}))
    pending = [entry for entry in entries if entry["class"] in {"conflict", "relocated", "refused"}]
    pending_file = pending_upgrade_path(home)
    interrupted = None
    if pending_file.is_file():
        try:
            interrupted = json.loads(pending_file.read_text(encoding="utf-8"))
        except ValueError:
            interrupted = {"unreadable": True}
    result = {"home_version": home_version, "package_version": manifest["version"],
              "manifest_source": manifest_source, "mode": "normal" if state else "degraded",
              "fingerprint": fingerprint, "counts": counts, "pending": len(pending),
              "migrations": manifest.get("migrations", []),
              "entries": entries, "written": [], "manifest_updated": False}
    if interrupted is not None:
        result["interrupted"] = interrupted
    if home.path("TOOLS/vhd.py").is_file():
        result["legacy"] = {"path": "TOOLS/vhd.py",
                            "suggestion": "superseded by TOOLS/homestead.py; recycle it after this update"}
    if not write:
        result["notice"] = "Preview only. Nothing written."
        return result
    require(confirm == fingerprint, "Show the dry plan to the user and pass its fingerprint with --confirm.")
    require_mutation()
    require(not manifest.get("migrations"),
            "This package lists migrations; apply them explicitly before this update.")
    manifest_data = None
    manifest_file = pkg / MANIFEST_NAME
    if manifest_file.is_file():
        require(manifest_file.stat().st_size <= 4 * 1024 * 1024, "Package manifest is oversized.")
        manifest_data = manifest_file.read_bytes()
        require(digest(packed(check_manifest(json.loads(manifest_data.decode("utf-8"))))) ==
                digest(packed(manifest)), "Package manifest file does not match the parsed plan.")
    current_manifest = home.path(MANIFEST_NAME)
    manifest_current = bool(manifest_data is not None and current_manifest.is_file()
                            and hash_file(current_manifest) == digest(manifest_data))
    writable = [entry for entry in entries if entry["class"] in {"new", "stale"}]
    applied = [entry["path"] for entry in entries if entry["class"] == "applied"]
    if not writable and not applied and manifest_current:
        result["notice"] = "Already current; nothing safe to write."
        return result
    snapshots = []
    with home.lock():
        record_state(pending_file, {"schema": 1, "started": stamp(), "fingerprint": fingerprint,
                                    "version": manifest["version"], "from": home_version,
                                    "planned": [entry["path"] for entry in writable],
                                    "skipped": applied, "previous": interrupted})
        for entry in writable:
            if entry["class"] == "stale":
                plan_id = home.plan("snapshot", target=entry["path"], allow_core=True,
                                    reason="pre-update " + manifest["version"])["plan_id"]
                home.apply(plan_id)
                snapshots.append(plan_id)
        for entry in writable:
            data = (pkg / entry["path"]).read_bytes()
            require(digest(data) == entry["package_sha256"], "Package file changed after the plan.")
            install_bytes(home.path(entry["path"]), data)
            result["written"].append(entry["path"])
        if manifest_data is not None and not manifest_current:
            install_bytes(current_manifest, manifest_data)
            result["manifest_updated"] = True
        record_state(home.path(STATE_NAME), state_document(manifest, previous=state))
        pending_file.unlink()
    result["state_written"] = True
    result["snapshots"] = snapshots
    result["skipped"] = applied
    result["restart_required"] = "TOOLS/homestead.py" in result["written"]
    result["host_prompt_stale"] = "sysprompt_to_copy.txt" in result["written"]
    if counts.get("dropped"):
        result["notice"] = "Dropped files stay in place; recycle them explicitly if unwanted."
    return result


def tokens_of(text):
    return re.findall(r"[^\W_]{2,}", text.casefold())


def index_scope(relative):
    text = relative.as_posix()
    if text.upper().startswith(INDEX_DERIVED_PREFIXES):
        return False
    folded = {part.casefold() for part in relative.parts}
    if folded & INDEX_EXCLUDED_PARTS or folded & INDEX_PRIVATE_PARTS:
        return False
    return relative.suffix.lower() in (INDEX_SUFFIXES | GUARDIAN_IMAGE_TYPES.keys())


def index_entry(home, path, relative, previous=None, full=False):
    s = check_node(path)
    entry = {"path": relative.as_posix(), "bytes": s.st_size, "mtime_ns": s.st_mtime_ns}
    if not full and previous and previous.get("bytes") == s.st_size and previous.get("mtime_ns") == s.st_mtime_ns \
            and previous.get("sha256"):
        entry.update({"sha256": previous["sha256"], "terms": previous.get("terms", {}),
                      "words": previous.get("words", 0), "metadata_only": previous.get("metadata_only", False)})
        return entry, False
    if s.st_size > TEXT_LIMIT:
        entry.update({"sha256": None, "terms": {}, "words": 0, "skipped": "oversized"})
        return entry, False
    entry["sha256"] = hash_file(path)
    if entry["sha256"] != guardian_public_hash(home, relative):
        entry.update({"terms": {}, "words": 0, "metadata_only": True})
        return entry, True
    try:
        data, _ = guardian_bytes(home, relative.as_posix(), None, TEXT_LIMIT)
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        entry.update({"terms": {}, "words": 0, "skipped": "not-utf8"})
        return entry, True
    tokens = tokens_of(text)
    counts = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    if len(counts) > INDEX_TERM_LIMIT:
        counts = dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:INDEX_TERM_LIMIT])
    entry.update({"terms": counts, "words": len(tokens)})
    return entry, True


def index_build(home, previous=None, full=False):
    previous_docs = {}
    if isinstance(previous, dict):
        for doc in previous.get("documents", []):
            if isinstance(doc, dict) and isinstance(doc.get("path"), str):
                previous_docs[doc["path"]] = doc
    documents = []
    skipped = []
    hashed = 0
    for path in sorted(home.root.rglob("*")):
        relative = path.relative_to(home.root)
        if not index_scope(relative):
            continue
        try:
            if not path.is_file():
                continue
            path = home.path(relative.as_posix(), exists=True)
            entry, changed = index_entry(home, path, relative, previous_docs.get(relative.as_posix()), full)
        except (OSError, SafetyError) as error:
            skipped.append({"path": relative.as_posix(), "reason": str(error)[:160]})
            continue
        hashed += int(changed)
        documents.append(entry)
        require(len(documents) <= LIMIT_FILES, "The home has too many indexable files.")
    current = {doc["path"] for doc in documents}
    by_hash = {}
    for doc in documents:
        if doc.get("sha256"):
            by_hash.setdefault(doc["sha256"], []).append(doc["path"])
    added = sorted(current - set(previous_docs))
    removed = sorted(set(previous_docs) - current)
    renamed = []
    ambiguous = []
    for old in removed:
        key = previous_docs[old].get("sha256")
        candidates = sorted(path for path in by_hash.get(key, []) if path in added) if key else []
        if len(candidates) == 1:
            renamed.append({"from": old, "to": candidates[0]})
            added.remove(candidates[0])
        elif candidates:
            ambiguous.append({"from": old, "candidates": candidates})
    value = {"schema": INDEX_SCHEMA, "rules": INDEX_RULES, "generated": stamp(), "checked": stamp(),
             "count": len(documents), "documents": documents, "renamed": renamed,
             "ambiguous": ambiguous, "hashed": hashed, "skipped": skipped[:20]}
    if full:
        new_map = {doc["path"]: doc for doc in documents}
        value["drift"] = {
            "missing": [path for path in sorted(previous_docs) if path not in new_map],
            "extra": added,
            "changed": [path for path in sorted(set(new_map) & set(previous_docs))
                        if new_map[path].get("sha256") != previous_docs[path].get("sha256")]}
    return value


def index_read(home):
    path = home.path(INDEX_NAME)
    if not path.is_file():
        return None
    require(path.stat().st_size <= 64 * 1024 * 1024, "The content index is oversized; rebuild it.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise SafetyError("The content index is unreadable; rebuild it.")
    require(isinstance(value, dict), "The content index must be an object.")
    require(value.get("schema") == INDEX_SCHEMA and value.get("rules") == INDEX_RULES,
            "The content index was written by another ruleset; rebuild it.")
    require(isinstance(value.get("documents"), list), "The content index has no document list.")
    return value


def index_write(home, value):
    target = home.path(INDEX_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    check_chain(target.parent)
    install_bytes(target, (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode())


def index_drift(home, document):
    indexed = {doc["path"]: doc for doc in document.get("documents", []) if isinstance(doc, dict)}
    seen = set()
    changed = []
    for path in sorted(home.root.rglob("*")):
        relative = path.relative_to(home.root)
        if not index_scope(relative):
            continue
        text = relative.as_posix()
        try:
            if not path.is_file():
                continue
            s = check_node(path)
        except (OSError, SafetyError):
            continue
        seen.add(text)
        doc = indexed.get(text)
        if doc is None or doc.get("bytes") != s.st_size or doc.get("mtime_ns") != s.st_mtime_ns:
            changed.append(text)
    return {"missing": sorted(set(indexed) - seen), "extra": sorted(seen - set(indexed)), "changed": sorted(changed)}


def seconds_since(text):
    if not isinstance(text, str):
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - moment).total_seconds())


def index_refresh(home, full=False, force=False):
    previous = None
    recovered = False
    try:
        previous = index_read(home)
    except (SafetyError, OSError):
        previous = None
        recovered = True
    if previous is not None and not full and not force:
        age = seconds_since(previous.get("checked"))
        if age is not None and age < REFRESH_SECONDS:
            return {"index": previous, "state": "throttled", "age_seconds": int(age), "written": False,
                    "recovered": False}
    try:
        with home.lock():
            value = index_build(home, previous, full)
            value["checked"] = stamp()
            index_write(home, value)
    except SafetyError as error:
        if lock_path(home).is_file():
            return {"index": previous, "state": "busy", "reason": str(error)[:200], "written": False,
                    "recovered": recovered}
        raise
    return {"index": value, "state": "verified", "written": True, "recovered": recovered}


FRESHNESS_NOTES = {
    "verified": None,
    "throttled": "The index was checked inside the refresh window and reused without a rescan; "
                 "a change made in that window is not visible yet.",
    "busy": "Another operation holds the home lock; this result comes from the stored index and may be stale.",
    "reconciled": "The stored index changed during this call; rerun to confirm the current result.",
    "unindexed": "No usable index; results come from a bounded direct scan.",
    "error": "The index could not be used; results come from a bounded direct scan.",
}


def freshness_report(state, document, extra=None):
    report = {"state": state, "index": INDEX_NAME, "checked": (document or {}).get("checked"),
              "documents": (document or {}).get("count", 0)}
    note = FRESHNESS_NOTES.get(state)
    if note:
        report["freshness_warning"] = note
    if extra:
        report.update(extra)
    return report


def index_command(home, full=False):
    report = index_refresh(home, full=full, force=True)
    document = report.get("index") or {}
    return {"index": INDEX_NAME, "written": report.get("written", False),
            "documents": document.get("count", 0), "hashed": document.get("hashed", 0),
            "renamed": document.get("renamed", []), "ambiguous": document.get("ambiguous", []),
            "drift": document.get("drift"), "skipped": document.get("skipped", []),
            "freshness": freshness_report(report.get("state", "error"), document)}


def source_snippet(text, sha, terms, width=200):
    for number, line in enumerate(text.splitlines(), 1):
        if any(term in line.casefold() for term in terms):
            return {"line": number, "text": " ".join(line.split())[:width], "sha256": sha}
    return None


def search_matches(home, documents, terms, prefix):
    hits = []
    stale = False
    for doc in documents:
        if not isinstance(doc, dict) or doc.get("skipped"):
            continue
        path = doc.get("path", "")
        if prefix and not (path == prefix or path.startswith(prefix + "/")):
            continue
        name_terms = set(tokens_of(Path(path).stem))
        cached_terms = doc.get("terms") or {}
        if not any(term in name_terms or term in cached_terms for term in terms):
            continue
        counts = {}
        snippet = None
        try:
            relative, current = guardian_path(home, path)
            size = current.stat().st_size
            public_hash = guardian_public_hash(home, relative)
            if public_hash:
                if doc.get("sha256") == public_hash:
                    data, sha = guardian_bytes(home, path, None, TEXT_LIMIT)
                    if sha == public_hash:
                        counts = cached_terms
                        snippet = source_snippet(data.decode("utf-8"), sha, terms)
                    else:
                        stale = True
                elif cached_terms or hash_file(current) == public_hash:
                    stale = True
        except GuardianDenied:
            stale = stale or bool(cached_terms)
        except (OSError, SafetyError, UnicodeDecodeError):
            stale = stale or bool(cached_terms)
            continue
        if not counts:
            counts = dict.fromkeys(name_terms, 1)
        matched = [term for term in terms if term in counts]
        if not matched:
            continue
        hit = {"path": path, "matched": len(matched), "terms": matched,
               "occurrences": sum(int(counts[term]) for term in matched),
               "bytes": size}
        if snippet:
            hit["snippet"] = snippet
        hits.append(hit)
    hits.sort(key=lambda hit: (-hit["matched"], -hit["occurrences"], hit["path"]))
    return hits, stale


def search_scan(home, terms, prefix):
    hits = []
    scanned = 0
    scope = home.path(prefix) if prefix else home.root
    paths = scope.rglob("*") if scope.is_dir() else (scope,)
    for path in sorted(paths):
        relative = path.relative_to(home.root)
        if not index_scope(relative):
            continue
        text = relative.as_posix()
        if prefix and not (text == prefix or text.startswith(prefix + "/")):
            continue
        try:
            if not path.is_file():
                continue
            s = check_node(path)
            _, path = guardian_path(home, text)
            content = path.stem
            snippet = None
            if s.st_size <= TEXT_LIMIT and guardian_public_hash(home, relative):
                try:
                    data, sha = guardian_bytes(home, text, None, TEXT_LIMIT)
                    source = data.decode("utf-8")
                    content += " " + source
                    snippet = source_snippet(source, sha, terms)
                except (GuardianDenied, UnicodeDecodeError):
                    pass
        except (OSError, SafetyError):
            continue
        scanned += 1
        require(scanned <= LIMIT_FILES, "The home has too many files to scan.")
        counts = {}
        for token in tokens_of(content):
            if token in terms:
                counts[token] = counts.get(token, 0) + 1
        if counts:
            hit = {"path": text, "matched": len(counts), "terms": sorted(counts),
                   "occurrences": sum(counts.values()), "bytes": s.st_size}
            if snippet:
                hit["snippet"] = snippet
            hits.append(hit)
    hits.sort(key=lambda hit: (-hit["matched"], -hit["occurrences"], hit["path"]))
    return hits


def search_command(home, query, limit=10, scope=None, full=False):
    terms = sorted(set(tokens_of(query)))
    require(terms, "Provide at least one search word of two or more letters or digits.")
    require(1 <= limit <= SEARCH_LIMIT, "Limit must be 1 to 50.")
    prefix = clean_relative(scope).as_posix() if scope else None
    document = None
    state = "verified"
    warnings = []
    try:
        report = index_refresh(home, full=full)
        document = report.get("index")
        state = report.get("state", "verified")
        if report.get("recovered"):
            warnings.append("the stored index was unreadable and has been rebuilt from the canonical files")
    except (SafetyError, OSError) as error:
        warnings.append(str(error)[:200])
        repaired = heal(home)
        warnings.append("heal " + repaired["state"])
        if repaired["state"] == "HEALTHY":
            try:
                document = index_read(home)
                state = "verified"
            except (SafetyError, OSError):
                document = None
        if document is None:
            state = "unindexed" if repaired["state"] == "HEALTHY" else "error"
    if document is not None:
        hits, stale = search_matches(home, document.get("documents", []), terms, prefix)
        if stale:
            try:
                retry = index_refresh(home, full=True)
                state = retry["state"]
                document = retry["index"]
                if document is not None:
                    hits, stale = search_matches(home, document.get("documents", []), terms, prefix)
            except (SafetyError, OSError):
                state = "error"
                document = None
            if stale:
                warnings.append("Some indexed content changed or could not be verified; stale excerpts were withheld.")
    if document is None:
        hits = search_scan(home, terms, prefix)
        source = "scan"
    else:
        source = "index"
    return {"query": query, "terms": terms, "matches": len(hits), "limit": limit, "results": hits[:limit],
            "source": source, "freshness": freshness_report(state, document), "warnings": warnings}


def health_read(home):
    path = home.path(HEALTH_NAME)
    if not path.is_file():
        return None
    require(path.stat().st_size <= 64 * 1024, "The health record is oversized.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def health_write(home, value):
    target = home.path(HEALTH_NAME)
    target.parent.mkdir(parents=True, exist_ok=True)
    check_chain(target.parent)
    install_bytes(target, (json.dumps(value, indent=1, sort_keys=True) + "\n").encode())


def heal_record(home, entry):
    path = home.path(HEAL_LOG_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    check_chain(path.parent)
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    for line in lines[-200:]:
        try:
            previous = json.loads(line)
        except ValueError:
            continue
        if isinstance(previous, dict) and previous.get("fingerprint") == entry["fingerprint"]:
            age = seconds_since(previous.get("at"))
            if age is not None and age < HEAL_DEDUPE_SECONDS:
                return {"logged": False, "reason": "deduplicated inside the %d second window" % HEAL_DEDUPE_SECONDS}
    lines.append(json.dumps(entry, sort_keys=True, separators=(",", ":")))
    install_bytes(path, ("\n".join(lines[-200:]) + "\n").encode())
    return {"logged": True, "path": HEAL_LOG_NAME}


def heal_outcome(home, state, steps, attempts, document, reason=None, previous=None):
    fingerprint = digest(packed({"steps": [step["step"] for step in steps], "state": state,
                                 "documents": (document or {}).get("count", 0)}))[:16]
    proposal = None
    if state == "DEGRADED":
        proposal = {"kind": "proposal", "title": "Derived state needs a human decision",
                    "detail": reason or "the repair bounds were exhausted",
                    "steps": [step["step"] for step in steps], "at": stamp()}
        steps.append({"ladder": "H5", "step": "propose", "title": proposal["title"]})
    previous_state = (previous or {}).get("state")
    health = {"schema": 1, "state": state, "updated": stamp(),
              "reason": reason or "derived state verified",
              "attempts": attempts, "fingerprint": fingerprint,
              "documents": (document or {}).get("count", 0)}
    if proposal:
        health["proposal"] = proposal
    if previous_state:
        health["previous"] = previous_state
    health_write(home, health)
    if state == "HEALTHY" and previous_state == "DEGRADED":
        steps.append({"ladder": "H6", "step": "restore-primary", "state": "HEALTHY"})
    elif state == "DEGRADED":
        steps.append({"ladder": "H6", "step": "degraded", "reason": health["reason"]})
    log = heal_record(home, {"at": stamp(), "state": state, "fingerprint": fingerprint,
                             "attempts": attempts, "steps": steps})
    return {"state": state, "fingerprint": fingerprint, "attempts": attempts, "steps": steps,
            "proposal": proposal, "health": HEALTH_NAME, "log": log,
            "documents": (document or {}).get("count", 0),
            "restored_primary": state == "HEALTHY" and previous_state == "DEGRADED",
            "limits": ["Repair touches derived cache only; package code and user files are never rewritten.",
                       "Fallback is emergency-only and reports a warning while it is active."]}


def heal(home):
    started = time.monotonic()
    previous = health_read(home) or {}
    steps = []
    attempts = 0
    document = None
    reason = None
    lock_state = lock_report(home)["state"]
    steps.append({"ladder": "H0", "step": "inspect", "lock": lock_state})
    try:
        document = index_read(home)
        if document is None:
            steps.append({"ladder": "H1", "step": "index-absent"})
        else:
            steps.append({"ladder": "H1", "step": "index-readable", "documents": document.get("count")})
    except (SafetyError, OSError) as error:
        document = None
        steps.append({"ladder": "H1", "step": "index-unreadable", "reason": str(error)[:160]})
    if lock_state == "stale":
        attempts += 1
        try:
            recovered = lock_recover(home)
        except (SafetyError, OSError) as error:
            reason = "the stale lock could not be quarantined: " + str(error)[:160]
        else:
            steps.append({"ladder": "H2", "step": "quarantine-stale-lock", "quarantined": recovered["quarantined"]})
    elif lock_state != "absent":
        reason = "the home lock is " + lock_state + "; only its owner can clear it"
        steps.append({"ladder": "H2", "step": "lock-refused", "state": lock_state})
    if reason is None and document is not None and document.get("count", 0) > 0:
        drift = index_drift(home, document)
        steps.append({"ladder": "H2", "step": "reconcile",
                      "drift": {key: len(value) for key, value in drift.items()}})
        if not any(drift.values()):
            steps.append({"ladder": "H4", "step": "verify", "documents": document["count"]})
            return heal_outcome(home, "HEALTHY", steps, attempts, document, previous=previous)
    full_rebuild = document is None
    while reason is None and attempts < HEAL_ATTEMPTS:
        if time.monotonic() - started > HEAL_BUDGET_SECONDS:
            reason = "the repair budget of %d seconds was exhausted" % HEAL_BUDGET_SECONDS
            steps.append({"ladder": "H3", "step": "budget", "seconds": HEAL_BUDGET_SECONDS})
            break
        attempts += 1
        try:
            report = index_refresh(home, full=full_rebuild, force=True)
            document = report.get("index")
        except (SafetyError, OSError) as error:
            steps.append({"ladder": "H3", "step": "rebuild-failed", "attempt": attempts, "reason": str(error)[:160]})
            if attempts < HEAL_ATTEMPTS:
                continue
            reason = str(error)[:200]
            break
        steps.append({"ladder": "H3", "step": "rebuild", "attempt": attempts,
                      "documents": (document or {}).get("count")})
        try:
            value = index_read(home)
        except (SafetyError, OSError) as error:
            steps.append({"ladder": "H4", "step": "verify-failed", "attempt": attempts, "reason": str(error)[:160]})
            continue
        if value.get("count", 0) <= 0:
            steps.append({"ladder": "H4", "step": "verify-empty", "attempt": attempts})
            continue
        document = value
        steps.append({"ladder": "H4", "step": "verify", "attempt": attempts, "documents": value["count"]})
        return heal_outcome(home, "HEALTHY", steps, attempts, document, previous=previous)
    return heal_outcome(home, "DEGRADED", steps, attempts, document,
                        reason=reason or "the repair bounds were exhausted", previous=previous)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Homestead local helpers. No network, purge, or automatic cleanup.")
    parser.add_argument("--home", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--version", action="version", version=VERSION)
    subs = parser.add_subparsers(dest="command", required=True)
    import homestead_portable as portable
    portable.register(subs)
    subs.add_parser("init", help="Create missing starter files on Windows")
    subs.add_parser("now", help="Read the host clock")
    d = subs.add_parser("detect", help="Find Homestead home candidates near a folder")
    d.add_argument("--path")
    d.add_argument("--depth", type=int, default=3)
    m = subs.add_parser("manifest", help="Build or refresh the package manifest")
    m.add_argument("--write", action="store_true")
    r = subs.add_parser("rng", help="Draw random values")
    r.add_argument("mode", choices=["int", "sample", "choose", "shuffle"])
    r.add_argument("--low", type=int)
    r.add_argument("--high", type=int)
    r.add_argument("--count", type=int, default=1)
    r.add_argument("--pool")
    r.add_argument("--purpose")
    i = subs.add_parser("inspect", help="Inspect exact file metadata")
    i.add_argument("path")
    i.add_argument("--sha256", action="store_true")
    i.add_argument("--links", action="store_true")
    i.add_argument("--purpose")
    read = subs.add_parser("read", help="Read one bounded UTF-8 page")
    read.add_argument("path")
    read.add_argument("--offset", type=int, default=0)
    read.add_argument("--length", type=int, default=PAGE_LIMIT)
    read.add_argument("--sha256")
    read.add_argument("--if-changed", metavar="SHA256", help="Skip text already read completely in this chat")
    read.add_argument("--purpose")
    fold = subs.add_parser("fold-log", help="Group identical lines in an authorized UTF-8 log")
    fold.add_argument("path")
    fold.add_argument("--limit", type=int, default=30)
    fold.add_argument("--purpose")
    guardian = subs.add_parser("guardian", help="Manage scoped permissions for sensitive files")
    actions = guardian.add_subparsers(dest="action", required=True)
    actions.add_parser("status")
    actions.add_parser("mode").add_argument("setting", choices=["true", "false"])
    for action in ("authorize", "forget", "attachment"):
        command = actions.add_parser(action)
        command.add_argument("path")
        command.add_argument("--purpose", required=True)
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
    preview.add_argument("--purpose")
    stats.add_argument("--purpose")
    record = subs.add_parser("xp-record", help="Record one verified milestone from JSON on stdin")
    record.add_argument("ledger")
    record.add_argument("--purpose", required=True)
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
    u = subs.add_parser("upgrade", help="Compare a package or archive against this home")
    u.add_argument("--package")
    u.add_argument("--zip")
    u.add_argument("--sha256")
    u.add_argument("--apply", action="store_true")
    u.add_argument("--confirm")
    links = subs.add_parser("links", help="Check Markdown links and anchors")
    links.add_argument("--path", action="append")
    links.add_argument("--purpose")
    subs.add_parser("routes", help="Check the startup route manifest")
    subs.add_parser("audit", help="Scan release files for private or sensitive content").add_argument("--path")
    rtm = subs.add_parser("runtime", help="Inspect or drive the optional deterministic runtime")
    rtm.add_argument("action", choices=["status", "add", "start", "pause", "resume", "stop", "run"])
    rtm.add_argument("--kind", choices=list(RUNTIME_KINDS))
    rtm.add_argument("--payload")
    rtm.add_argument("--limit", type=int)
    rtm.add_argument("--now", action="store_true")
    gt = subs.add_parser("git", help="Local history and sanitized public export helpers")
    gt.add_argument("action", choices=["status", "checkpoint", "export", "verify", "publish"])
    gt.add_argument("--to")
    gt.add_argument("--path", action="append", default=[])
    gt.add_argument("--message")
    gt.add_argument("--confirm")
    gt.add_argument("--public")
    gt.add_argument("--include-ignored", action="store_true")
    co = subs.add_parser("closeout", help="Classify pending changes and close them in one guarded commit")
    co.add_argument("action", choices=["scan", "run"])
    co.add_argument("--repo")
    co.add_argument("--path", action="append", default=[])
    co.add_argument("--message")
    rel = subs.add_parser("release", help="Verify version consistency and release contents")
    rel.add_argument("--project")
    rel.add_argument("--compare")
    subs.add_parser("doctor", help="Report capabilities, modes and home health").add_argument(
        "--mode", choices=["auto", "standard", "enhanced"])
    me = subs.add_parser("method", help="Validate or show knowledge cards")
    me.add_argument("action", choices=["check", "show"])
    me.add_argument("id", nargs="?")
    me.add_argument("--catalog")
    me.add_argument("--purpose")
    st = subs.add_parser("status", help="Derive a compact progression card")
    st.add_argument("ledger")
    st.add_argument("--write", action="store_true")
    st.add_argument("--purpose")
    st.add_argument("--display", action="store_true")
    ix = subs.add_parser("index", help="Build or refresh the local content index")
    ix.add_argument("--full", action="store_true")
    se = subs.add_parser("search", help="Search the local content index")
    se.add_argument("query")
    se.add_argument("--limit", type=int, default=10)
    se.add_argument("--scope")
    se.add_argument("--full", action="store_true")
    subs.add_parser("heal", help="Detect, diagnose and repair derived state")
    lk = subs.add_parser("lock", help="Inspect or quarantine a confirmed stale lock")
    lk.add_argument("--recover", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(sys.version_info >= (3, 13), "Python 3.13 or newer is required.")
        if args.command == "now":
            now = datetime.now(timezone.utc)
            result = {"utc": now.isoformat(), "local": now.astimezone().isoformat(),
                      "zone": now.astimezone().tzname(), "note": "Host clock and zone; not an inferred user location."}
        elif args.command == "rng" and args.mode in {"int", "sample"}:
            result = rng(args, None)
        elif args.command == "detect":
            result = {"candidates": find_homes(args.path or os.getcwd(), args.depth)}
        elif args.command == "manifest":
            result = manifest_command(args.home, args.write)
        else:
            home = Home(args.home)
            if args.command == "init":
                result = home.setup()
            elif args.command == "rng":
                result = rng(args, home)
            elif args.command == "inspect":
                result = inspect(home, args.path, args.sha256, args.links, purpose=args.purpose, guarded=True)
            elif args.command == "read":
                result = read_page(home, args.path, args.offset, args.length, args.sha256,
                                   guarded=True, purpose=args.purpose, if_changed=args.if_changed)
            elif args.command == "fold-log":
                result = fold_log(home, args.path, args.limit, args.purpose)
            elif args.command == "guardian":
                if args.action == "attachment":
                    result = guardian_attachment(home, args.path, args.purpose)
                else:
                    result = guardian_command(home, args.action, getattr(args, "path", None),
                                              getattr(args, "purpose", None), getattr(args, "setting", None))
            elif args.command == "validate":
                result = validate_text(home, args.path, args.kind)
            elif args.command == "write":
                result = write_text_source(home, args.path, args.sha256, read_write_request())
            elif args.command == "stats":
                result = progression(home, args.ledger, purpose=args.purpose, guarded=True)
            elif args.command == "xp-preview":
                result = progression(home, args.ledger, args.id, args.award, purpose=args.purpose, guarded=True)
            elif args.command == "xp-record":
                body = sys.stdin.buffer.read(16385)
                require(len(body) <= 16384, "Milestone input exceeds 16 KiB.")
                record = json.loads(body.decode("utf-8-sig"), object_pairs_hook=unique_json_object)
                result = xp_record(home, args.ledger, args.purpose, record)
            elif args.command == "plan":
                result = home.plan(args.action, args.path, args.source, args.id, args.reason, args.allow_core)
            elif args.command == "apply":
                result = home.apply(args.id)
            elif args.command == "upgrade":
                result = upgrade(home, args.package, args.apply, args.confirm, args.zip, args.sha256)
            elif args.command == "links":
                result = portable.scoped_links(home, args.path, args.purpose) if args.path else links_check(home, guarded=True)
            elif args.command == "routes":
                result = routes_check(home)
            elif args.command == "release":
                result = release_check(home, args.project, args.compare)
            elif args.command == "audit":
                result = audit(home, args.path)
            elif args.command == "runtime":
                result = runtime_command(home, args.action, args.kind, args.payload, args.limit, args.now)
            elif args.command == "git":
                if args.action == "status":
                    result = git_status(home, args.public)
                elif args.action == "export":
                    require(args.to, "Provide --to for the export folder.")
                    result = git_export(home, args.to)
                elif args.action == "verify":
                    require(args.to, "Provide --to for the export folder.")
                    result = git_verify(home, args.to)
                elif args.action == "publish":
                    require(args.to and args.confirm, "Provide --to and --confirm for publication.")
                    result = git_publish(home, args.to, args.confirm, args.message)
                else:
                    result = git_checkpoint(home, args.path, args.message, args.include_ignored)
            elif args.command == "closeout":
                result = closeout(home, args.action, args.repo, args.path, args.message)
            elif args.command == "doctor":
                result = doctor(home, args.mode)
            elif args.command == "method":
                if args.action == "check":
                    result = method_check(home, args.catalog, guarded=True, purpose=args.purpose)
                else:
                    result = method_show(home, args.id, args.catalog, guarded=True, purpose=args.purpose)
            elif args.command == "status":
                result = status_card(home, args.ledger, args.write, purpose=args.purpose, guarded=True)
                if args.display:
                    result["display"] = stats_display(result["card"])
            elif args.command == "index":
                result = index_command(home, args.full)
            elif args.command == "search":
                result = search_command(home, args.query, args.limit, args.scope, args.full)
            elif args.command == "heal":
                result = heal(home)
            elif args.command == "lock":
                result = lock_recover(home) if args.recover else lock_report(home)
            elif args.command == "records":
                result = home.records(args.limit, args.id)
            else:
                result = portable.handle(home, args)
        status = "OK"
        code = 0
        if args.command in {"links", "routes", "release", "method", "audit", "preflight", "privacy", "provider"} and result.get("failed"):
            status, code = "FAIL", 1
        elif args.command == "git" and args.action == "verify" and not result.get("passed"):
            status, code = "FAIL", 1
        elif args.command == "upgrade" and result.get("pending"):
            status, code = "PARTIAL", 3
        elif args.command == "heal" and result.get("state") == "DEGRADED":
            status, code = "PARTIAL", 3
        print(json.dumps({"status": status, **result}, ensure_ascii=True))
        return code
    except GuardianDenied as denied:
        print(json.dumps(denied.result, ensure_ascii=True))
        return 1
    except (SafetyError, OSError, ValueError, KeyError, TypeError, RecursionError) as e:
        print(json.dumps({"status": "ERROR", "error": str(e),
                          "recovery": "Inspect existing records and payloads before retrying any interrupted mutation."}))
        return 1


if __name__ == "__main__":
    sys.modules["homestead"] = sys.modules[__name__]
    raise SystemExit(main())
