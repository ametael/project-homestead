from pathlib import Path
import re
from urllib.parse import unquote

import homestead as core


TASKS = {
    "startup": ("read", "routes", "guardian"),
    "diagnostics": ("fold-log", "read", "inspect"),
    "research": ("knowledge", "guardian", "read"),
    "retrieval": ("lookup", "search", "inspect", "guardian", "read"),
    "documents": ("preflight", "links", "read", "write", "closeout"),
    "privacy": ("privacy", "guardian"),
    "progress": ("stats", "xp-preview", "xp-record", "status"),
    "finance": ("cashbook", "privacy"),
    "release": ("preflight", "release", "audit", "closeout"),
}


def size_zone(size, budget):
    core.require(type(budget) is int and 1 <= budget <= core.TEXT_LIMIT, "Use a valid byte budget.")
    zone = "BLOCKED" if size * 100 >= budget * 180 else "YELLOW" if size > budget else "OK"
    return {"bytes": size, "budget": budget, "zone": zone}


def scoped_files(home, files):
    core.require(1 <= len(files) <= 100, "Provide 1 to 100 exact --path values.")
    for raw in dict.fromkeys(files):
        relative = core.clean_relative(raw)
        path = home.path(raw)
        core.require(not path.is_dir(), "Use exact files, not directories.")
        yield relative.as_posix(), path


def preflight(home, files, budget, purpose):
    repo = core.repo_root(home.root)
    checks = []
    for name, path in scoped_files(home, files):
        report = {"path": name, "exists": path.is_file(), "ignored": None}
        if repo:
            target = path.relative_to(repo).as_posix()
            status = core.git_command(repo, "--literal-pathspecs", "check-ignore", "-q", "--", target,
                                      check=False).returncode
            core.require(status in {0, 1}, "Git could not check the selected path.")
            report["ignored"] = status == 0
        if path.is_file():
            report.update(size_zone(path.stat().st_size, budget))
            if path.suffix.lower() in {".md", ".json"} and report["zone"] != "BLOCKED":
                try:
                    if path.suffix.lower() == ".md":
                        report["links"] = scoped_links(home, [name], purpose)["findings"]
                    else:
                        data, _ = core.guardian_bytes(home, name, purpose, core.TEXT_LIMIT)
                        core.json.loads(data, object_pairs_hook=core.unique_json_object,
                                        parse_constant=core.reject_json_constant)
                        report["json"] = "PASS"
                except core.GuardianDenied:
                    report["validation"] = "NEEDS_PERMISSION"
                except (ValueError, core.SafetyError):
                    report["validation"] = "INVALID_OR_UNAVAILABLE"
        else:
            report["zone"] = "YELLOW"
        checks.append(report)
    failed = sum(c["zone"] == "BLOCKED" or c.get("ignored") is True or bool(c.get("links"))
                 or c.get("validation") == "INVALID_OR_UNAVAILABLE" for c in checks)
    return {"files": checks, "failed": failed, "review": sum(c.get("validation") == "NEEDS_PERMISSION" for c in checks)}


def scoped_links(home, files, purpose):
    failures = []
    checked = 0
    for name, path in scoped_files(home, files):
        core.require(path.suffix.lower() == ".md", "Scoped link checks expect Markdown files.")
        data, _ = core.guardian_bytes(home, name, purpose, core.TEXT_LIMIT)
        text = data.decode("utf-8-sig")
        for line_no, line in enumerate(text.splitlines(), 1):
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", line):
                raw, _, anchor = target.strip().strip("<>").partition("#")
                if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw) or raw.startswith("//"):
                    continue
                checked += 1
                core.require(checked <= 5000, "Too many scoped links.")
                candidate = (path.parent / unquote(raw)) if raw else path
                try:
                    relative = candidate.resolve().relative_to(home.root).as_posix()
                    dest = home.path(relative, exists=True)
                except (ValueError, core.SafetyError):
                    failures.append({"path": name, "line": line_no, "state": "missing_or_outside"})
                    continue
                if anchor and dest.suffix.lower() == ".md":
                    try:
                        dest_data, _ = core.guardian_bytes(home, relative, purpose, core.TEXT_LIMIT)
                    except core.GuardianDenied:
                        failures.append({"path": name, "line": line_no, "state": "anchor_needs_permission"})
                        continue
                    if not core.anchor_matches(dest, anchor, dest_data.decode("utf-8-sig")):
                        failures.append({"path": name, "line": line_no, "state": "missing_anchor"})
    return {"references": checked, "failed": len(failures), "findings": failures}


def lookup(home, scope, query, limit):
    prefix = core.clean_relative(scope).as_posix()
    home.path(scope, exists=True)
    terms = sorted(set(core.tokens_of(query)))
    core.require(terms and 1 <= limit <= 50, "Provide search words and a limit from 1 to 50.")
    matches = core.search_scan(home, terms, prefix)
    return {"scope": prefix, "matches": len(matches), "results": matches[:limit]}


def triage(home, folder):
    rel = core.clean_relative(folder)
    path = home.path(folder, exists=True)
    core.require(path.is_dir() and rel.parts[0].upper() in core.USER_ROOTS, "Choose an exact user inbox folder.")
    items = []
    for child in sorted(path.iterdir(), key=lambda item: item.name.casefold()):
        core.require(len(items) < 200, "Select a smaller inbox folder.")
        name = child.relative_to(home.root).as_posix()
        try:
            safe = home.path(name, exists=True)
            size = safe.stat().st_size if safe.is_file() else None
        except (OSError, core.SafetyError):
            items.append({"path": name, "route": "review"})
            continue
        suffix = child.suffix.lower()
        route = ("artwork" if suffix in core.GUARDIAN_IMAGE_TYPES else "spreadsheet" if suffix in {".xlsx", ".csv"}
                 else "document" if suffix in {".md", ".txt", ".pdf", ".docx"} else "review")
        items.append({"path": name, "bytes": size, "route": route if size is not None else "review"})
    return {"folder": rel.as_posix(), "items": items}


def privacy(home, files):
    markers = core.read_config(home).get("private_markers", [])
    core.require(isinstance(markers, list) and len(markers) <= 20
                 and all(isinstance(marker, str) and 1 <= len(marker) <= 64 for marker in markers),
                 "Use up to 20 private markers in the home configuration.")
    findings = []
    checked = 0
    for name, _ in scoped_files(home, files):
        _, path = core.guardian_path(home, name)
        core.require(path.stat().st_size <= core.TEXT_LIMIT, "Select an exact text file within the privacy scan limit.")
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            findings.append({"path": name, "kind": "not_utf8"})
            continue
        checked += 1
        for number, line in enumerate(text.splitlines(), 1):
            kinds = [kind for kind, pattern in core.AUDIT_PATTERNS if pattern.search(line)]
            if any(marker in line for marker in markers):
                kinds.append("private-marker")
            if core.absolute_path(line):
                kinds.append("absolute-path")
            for kind in kinds:
                core.require(len(findings) < 200, "Review the first batch of privacy findings locally.")
                findings.append({"path": name, "line": number, "kind": kind})
    return {"files": checked, "findings": findings, "failed": len(findings), "redacted": True}
