import argparse
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "VHD" if (REPO / "VHD").is_dir() else REPO
IGNORE = shutil.ignore_patterns("PERSONA", "MEMORY", "PROJECTS", "ASSETS", "ARCHIVE",
                                ".recycle", ".git", "tests", "__pycache__")
FAKE_CREDENTIAL = "api_" + "key = " + "abcdefghijklmnop"
FAKE_DRIVE = "D" + ":" + "\\private\\path"
spec = importlib.util.spec_from_file_location("vhd_helpers", SOURCE / "TOOLS" / "vhd.py")
vhd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vhd)


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-safety-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(self.base.name.startswith("vhd-safety-"))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()
        (self.root / "PROJECTS" / "Alpha").mkdir()
        self.path = self.root / "PROJECTS" / "Alpha" / "draft.md"
        self.path.write_text("original\n", encoding="utf-8")
        self.original = self.path.read_bytes()
        self.outside = self.base / "outside"
        self.outside.mkdir()
        (self.outside / "keep.txt").write_text("outside", encoding="utf-8")

    def tearDown(self):
        vhd.EVENT_HOOK = None
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(self.base.name.startswith("vhd-safety-"))
        self.temp.cleanup()

    def plan(self, action="snapshot", target="PROJECTS/Alpha/draft.md", **kwargs):
        return self.home.plan(action, target=target, reason="synthetic safety test", **kwargs)["plan_id"]

    def apply(self, action="snapshot", target="PROJECTS/Alpha/draft.md", **kwargs):
        identifier = self.plan(action, target, **kwargs)
        self.home.apply(identifier)
        return identifier

    def cli(self, *args, input_data=None):
        result = subprocess.run([sys.executable, "-B", str(SOURCE / "TOOLS" / "vhd.py"),
                                 "--home", str(self.root), *args],
                                input=input_data, capture_output=True, text=True)
        return result.returncode, json.loads(result.stdout)

    def test_setup_is_idempotent_and_preserves_persona(self):
        identity = self.root / "PERSONA" / "IDENTITY.md"
        self.assertIn("Name: Vee", identity.read_text(encoding="utf-8"))
        self.assertTrue((self.root / "PERSONA" / "HANDOFF.md").is_file())
        self.assertTrue((self.root / "PERSONA" / "PROGRESSION" / "EXP.md").is_file())
        identity.write_text("Name: Mira\nVoice: quiet\n", encoding="utf-8")
        before = identity.read_bytes()
        self.assertEqual(self.home.setup()["created"], [])
        self.assertEqual(identity.read_bytes(), before)

    def test_setup_creates_the_complete_default_persona(self):
        identity = (self.root / "PERSONA" / "IDENTITY.md").read_text(encoding="utf-8")
        self.assertGreaterEqual(len(identity), 800)
        self.assertIn("Name: Vee", identity)
        self.assertIn("Continuity", identity)

    def test_swiss_knife_page_requires_current_fingerprint_and_validates_json(self):
        path = "PROJECTS/Alpha/draft.md"
        code, page = self.cli("read", path, "--length", "3")
        self.assertEqual((code, page["text"], page["next_offset"]), (0, "ori", 3))
        code, rest = self.cli("read", path, "--offset", "3", "--sha256", page["sha256"])
        self.assertEqual((code, rest["text"], rest["next_offset"]),
                         (0, self.original.decode("utf-8")[3:], None))
        self.path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
        self.assertEqual(self.cli("read", path, "--offset", "3", "--sha256", page["sha256"])[0], 1)
        self.assertEqual(self.cli("validate", path, "--kind", "json")[0], 1)
        self.path.write_text('{"a": 1}', encoding="utf-8")
        self.assertEqual(self.cli("validate", path, "--kind", "json")[1]["validation"], "PASS")
        self.assertEqual(self.cli("read", "../outside/keep.txt")[0], 1)

    def test_progression_preview_replay_and_titles_from_markdown(self):
        raw = "PERSONA/PROGRESSION/EXP.md"
        ledger = self.root / raw
        code, initial = self.cli("stats", raw)
        self.assertEqual((code, initial["level"], initial["xp"], initial["title"]), (0, 1, 0, None))
        row = "| alpha.summary | Alpha | engineering.integration | Summary | 2026-11-21 | PASS | draft.md | 2 |\n"
        content = ledger.read_text(encoding="utf-8").replace("\n\nOne row", "\n" + row + "\nOne row")
        ledger.write_text(content, encoding="utf-8")
        code, stats = self.cli("stats", raw)
        self.assertEqual((code, stats["xp"], stats["title"]["title"]), (0, 2, "Builder"))
        code, replay = self.cli("xp-preview", raw, "--id", "alpha.summary", "--award", "2")
        self.assertEqual((code, replay["delta"], replay["recorded"]), (0, 0, False))
        _, upgraded = self.cli("xp-preview", raw, "--id", "alpha.summary", "--award", "3")
        self.assertEqual((upgraded["delta"], upgraded["projected"]["xp"]), (1, 3))
        self.assertEqual(ledger.read_text(encoding="utf-8"), content)
        ledger.write_text(content.replace(row, row + row), encoding="utf-8")
        self.assertEqual(self.cli("stats", raw)[0], 1)

    def test_swiss_knife_writes_with_snapshot_and_refuses_stale_or_core_edits(self):
        target = "PROJECTS/Alpha/PROGRESS/0001.md"
        initial = json.dumps({"text": "Checkpoint: Vee\n"})
        code, created = self.cli("write", target, "--sha256", "absent", input_data=initial)
        self.assertEqual((code, created["changed"], created["snapshot_id"]), (0, True, None))
        code, unchanged = self.cli("write", target, "--sha256", created["sha256"], input_data=initial)
        self.assertEqual((code, unchanged["changed"]), (0, False))
        update = json.dumps({"text": "Checkpoint: verified ✓\n"})
        code, saved = self.cli("write", target, "--sha256", created["sha256"], input_data=update)
        self.assertEqual((code, saved["changed"]), (0, True))
        retained = self.root / "ARCHIVE" / saved["snapshot_id"] / "payload"
        self.assertEqual(retained.read_bytes(), b"Checkpoint: Vee\n")
        self.assertEqual((self.root / target).read_text(encoding="utf-8"), json.loads(update)["text"])
        self.assertEqual(self.cli("write", target, "--sha256", created["sha256"], input_data=initial)[0], 1)
        self.assertEqual(self.cli("write", target, "--sha256", "absent", input_data=initial)[0], 1)
        self.assertEqual(self.cli("write", "START_HERE.md", "--sha256", "absent", input_data=initial)[0], 1)
        self.assertEqual(self.cli("write", "ASSETS/data.txt", "--sha256", "absent", input_data="[]")[0], 1)
        self.assertEqual(self.cli("read", target)[1]["sha256"], saved["sha256"])

    def test_home_root_and_missing_marker_refused(self):
        with self.assertRaises(vhd.SafetyError):
            vhd.Home(self.outside)
        with self.assertRaises(vhd.SafetyError):
            vhd.Home(Path(self.root.anchor))

    def test_rng_inclusive_bounds_no_files_written(self):
        before = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        args = argparse.Namespace(mode="int", low=7, high=7, count=20, pool=None)
        self.assertEqual(vhd.rng(args, None)["values"], [7] * 20)
        after = sorted(str(p.relative_to(self.root)) for p in self.root.rglob("*"))
        self.assertEqual(before, after)

    def test_rng_sample_and_invalid_inputs(self):
        args = argparse.Namespace(mode="sample", low=2, high=5, count=4, pool=None)
        self.assertEqual(set(vhd.rng(args, None)["values"]), {2, 3, 4, 5})
        for count in (0, 5, 1001):
            args.count = count
            with self.assertRaises(vhd.SafetyError):
                vhd.rng(args, None)
        args.count, args.low, args.high = 1, 3, 2
        with self.assertRaises(vhd.SafetyError):
            vhd.rng(args, None)

    def test_rng_pool_choice_and_shuffle(self):
        pool = self.root / "PROJECTS" / "Alpha" / "pool.json"
        pool.write_text('["same", "same", "other"]', encoding="utf-8")
        args = argparse.Namespace(mode="choose", count=4, pool="PROJECTS/Alpha/pool.json")
        rows = vhd.rng(args, self.home)["values"]
        values = ["same", "same", "other"]
        self.assertTrue(all(r["value"] == values[r["index"] - 1] for r in rows))
        args.mode, args.count = "shuffle", 1
        self.assertEqual(sorted(vhd.rng(args, self.home)["values"]), sorted(values))
        for data in ("[]", "{}", "bad json"):
            pool.write_text(data, encoding="utf-8")
            with self.assertRaises((vhd.SafetyError, ValueError)):
                vhd.rng(args, self.home)

    def test_clock_and_cli_error_contract(self):
        code, result = self.cli("now")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "OK")
        self.assertTrue(result["utc"].endswith("+00:00"))
        code, result = self.cli("inspect", "../outside/keep.txt")
        self.assertNotEqual(code, 0)
        self.assertEqual(result["status"], "ERROR")
        result = subprocess.run([sys.executable, "-B", str(SOURCE / "TOOLS" / "vhd.py"), "purge"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)

    def test_inspect_unicode_spaces_hash_and_links(self):
        p = self.path.parent / "space é.md"
        p.write_text("[ok](draft.md)\n[missing](missing.md)\n[escape](../../../outside/keep.txt)\n", encoding="utf-8")
        result = vhd.inspect(self.home, "PROJECTS/Alpha/space é.md", True, True)
        self.assertEqual(result["bytes"], p.stat().st_size)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertEqual([row["exists"] for row in result["links"]], [True, False, False])

    def test_invalid_paths_refused(self):
        for raw in ("", ".", "..", "../outside/keep.txt", "/tmp/a", "C:relative",
                    "C" + ":" + "/Windows", "PROJECTS//Alpha/draft.md", "PROJECTS/Alpha/../draft.md",
                    "PROJECTS/Alpha/*", "PROJECTS/NUL", "PROJECTS/trailing.",
                    "PROJECTS/Alpha/draft.md:secret", "PROJECTS/Alpha/file "):
            with self.subTest(raw=raw), self.assertRaises(vhd.SafetyError):
                self.plan(target=raw)
        self.assertEqual((self.outside / "keep.txt").read_text(), "outside")

    def test_protected_targets_and_git_metadata_refused(self):
        for target in ("PERSONA", "MEMORY", "PROJECTS", "ASSETS", "TOOLS", "START_HERE.md"):
            with self.subTest(target=target), self.assertRaises(vhd.SafetyError):
                self.plan("recycle", target)
        (self.path.parent / ".git").mkdir()
        with self.assertRaises(vhd.SafetyError):
            self.plan("archive", "PROJECTS/Alpha")

    def test_core_snapshot_needs_explicit_flag(self):
        with self.assertRaises(vhd.SafetyError):
            self.plan(target="START_HERE.md")
        identifier = self.apply(target="START_HERE.md", allow_core=True)
        self.assertEqual(self.home.records(identifier=identifier)["record"]["state"], "complete")
        with self.assertRaises(vhd.SafetyError):
            self.plan("recycle", "START_HERE.md", allow_core=True)

    def test_snapshot_has_complete_old_bytes_and_keeps_source(self):
        identifier = self.apply()
        info = self.home.records(identifier=identifier)
        folder, record = self.home.transaction(identifier)
        self.assertEqual((folder / "payload").read_bytes(), self.original)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(record["state"], "complete")
        self.assertTrue(info["payload_present"])
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(identifier)

    def test_recycle_and_archive_restore_without_losing_history(self):
        for action in ("recycle", "archive"):
            with self.subTest(action=action):
                identifier = self.apply(action)
                self.assertFalse(self.path.exists())
                restore = self.plan("restore", None, identifier=identifier)
                self.home.apply(restore)
                self.assertEqual(self.path.read_bytes(), self.original)
                folder, _ = self.home.transaction(identifier)
                self.assertTrue((folder / "payload").exists())

    def test_restore_collision_never_overwrites(self):
        identifier = self.apply("recycle")
        self.path.write_text("new active", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)
        self.assertEqual(self.path.read_text(), "new active")

    def test_stale_target_and_replacement_plans_refused(self):
        identifier = self.plan("recycle")
        self.path.write_text("changed", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(identifier)
        self.assertEqual(self.path.read_text(), "changed")
        replacement = self.path.parent / "replacement.md"
        replacement.write_text("first", encoding="utf-8")
        identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
        replacement.write_text("second", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(identifier)
        self.assertEqual(self.path.read_text(), "changed")

    def test_file_update_retains_old_and_current_before_backtrack(self):
        replacement = self.path.parent / "replacement.md"
        replacement.write_text("new version", encoding="utf-8")
        identifier = self.apply("update", source="PROJECTS/Alpha/replacement.md")
        folder, _ = self.home.transaction(identifier)
        self.assertEqual(self.path.read_text(), "new version")
        self.assertEqual(replacement.read_text(), "new version")
        self.assertEqual((folder / "payload").read_bytes(), self.original)
        self.assertEqual((folder / "displaced").read_bytes(), self.original)
        current = self.apply("recycle")
        self.home.apply(self.plan("restore", None, identifier=identifier))
        self.assertEqual(self.path.read_bytes(), self.original)
        other, _ = self.home.transaction(current)
        self.assertEqual((other / "payload").read_text(), "new version")

    def test_folder_update_keeps_hidden_and_ignored_contents(self):
        old = self.path.parent / "old"
        new = self.path.parent / "new"
        old.mkdir()
        new.mkdir()
        (old / ".hidden").write_text("retain hidden")
        (old / "ignored.dat").write_bytes(b"\x00\xff")
        (old / "empty").mkdir()
        (new / "next.txt").write_text("next")
        identifier = self.apply("update", "PROJECTS/Alpha/old", source="PROJECTS/Alpha/new")
        folder, _ = self.home.transaction(identifier)
        self.assertEqual((folder / "payload" / ".hidden").read_text(), "retain hidden")
        self.assertEqual((folder / "payload" / "ignored.dat").read_bytes(), b"\x00\xff")
        self.assertTrue((folder / "payload" / "empty").is_dir())
        self.assertEqual((old / "next.txt").read_text(), "next")

    def test_overlapping_replacement_refused(self):
        with self.assertRaises(vhd.SafetyError):
            self.plan("update", source="PROJECTS/Alpha/draft.md")
        with self.assertRaises(vhd.SafetyError):
            self.plan("update", "PROJECTS/Alpha", source="PROJECTS/Alpha/draft.md")

    def test_failed_archive_blocks_update(self):
        p = self.path.parent / "replacement.md"
        p.write_text("replacement")
        for error in (PermissionError("denied"), OSError(28, "No space left")):
            identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
            with patch.object(vhd, "copy_checked", side_effect=error):
                with self.assertRaises(OSError):
                    self.home.apply(identifier)
            self.assertEqual(self.path.read_bytes(), self.original)

    def test_capture_drift_refused_before_target_update(self):
        p = self.path.parent / "replacement.md"
        p.write_text("replacement")
        identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
        def change(name):
            if name == "captured":
                self.path.write_text("external edit")
        vhd.EVENT_HOOK = change
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertEqual(self.path.read_text(), "external edit")

    def test_interrupt_before_move_keeps_original(self):
        identifier = self.plan("recycle")
        def stop(name):
            if name == "prepared":
                raise OSError("simulated interruption")
        vhd.EVENT_HOOK = stop
        with self.assertRaises(OSError):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(self.home.records(identifier=identifier)["record"]["state"], "prepared")

    def test_interrupt_after_move_payload_can_restore(self):
        identifier = self.plan("recycle")
        def stop(name):
            if name == "after_move":
                raise OSError("simulated interruption")
        vhd.EVENT_HOOK = stop
        with self.assertRaises(OSError):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertFalse(self.path.exists())
        self.home.apply(self.plan("restore", None, identifier=identifier))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_interrupt_after_old_retained_can_restore(self):
        replacement = self.path.parent / "replacement.md"
        replacement.write_text("new")
        identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
        def stop(name):
            if name == "old_retained":
                raise OSError("simulated interruption")
        vhd.EVENT_HOOK = stop
        with self.assertRaises(OSError):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertFalse(self.path.exists())
        self.home.apply(self.plan("restore", None, identifier=identifier))
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(replacement.read_text(), "new")

    def test_target_collision_after_archive_is_preserved(self):
        replacement = self.path.parent / "replacement.md"
        replacement.write_text("new")
        identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
        def collide(name):
            if name == "old_retained":
                self.path.write_text("concurrent active")
        vhd.EVENT_HOOK = collide
        with self.assertRaises((vhd.SafetyError, FileExistsError)):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertEqual(self.path.read_text(), "concurrent active")
        folder, _ = self.home.transaction(identifier)
        self.assertEqual((folder / "payload").read_bytes(), self.original)

    def test_restore_collision_after_preview_is_preserved(self):
        identifier = self.apply("recycle")
        restore = self.plan("restore", None, identifier=identifier)
        self.path.write_text("new active")
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(restore)
        self.assertEqual(self.path.read_text(), "new active")

    def test_tampered_manifest_and_payload_refused(self):
        identifier = self.apply("recycle")
        folder, record = self.home.transaction(identifier)
        (folder / "payload").write_text("corrupted")
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)
        record["target"] = "../outside/keep.txt"
        (folder / "record.json").write_text(json.dumps(record))
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)
        self.assertEqual((self.outside / "keep.txt").read_text(), "outside")

    def test_lock_and_duplicate_concurrent_apply(self):
        with self.home.lock():
            self.home.apply(self.plan())
        self.assertFalse((self.root / ".recycle" / "operation.lock").exists())
        identifier = self.plan()
        def run():
            other = vhd.Home(self.root)
            try:
                other.apply(identifier)
                return "OK"
            except (vhd.SafetyError, FileExistsError):
                return "ERROR"
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(lambda _: run(), range(2)))
        self.assertEqual(sorted(result), ["ERROR", "OK"])

    def test_stale_lock_is_not_automatically_removed(self):
        p = self.root / ".recycle" / "operation.lock"
        p.write_text('{"pid":-1}')
        with self.assertRaises(vhd.SafetyError):
            self.plan()
        self.assertEqual(p.read_text(), '{"pid":-1}')

    def test_hardlink_refused(self):
        linked = self.path.parent / "linked.md"
        os.link(self.path, linked)
        with self.assertRaises(vhd.SafetyError):
            self.plan()
        with self.assertRaises(vhd.SafetyError):
            vhd.inspect(self.home, "PROJECTS/Alpha/linked.md", True)

    def test_junction_target_and_nested_junction_refused(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        link = self.path.parent / "junction"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.outside)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.assertRaises(vhd.SafetyError):
            self.plan("recycle", "PROJECTS/Alpha/junction/keep.txt")
        with self.assertRaises(vhd.SafetyError):
            self.plan("snapshot", "PROJECTS/Alpha")
        self.assertEqual((self.outside / "keep.txt").read_text(), "outside")

    def test_restore_parent_link_refused(self):
        identifier = self.apply("recycle")
        if os.name != "nt":
            self.skipTest("Windows junction test")
        moved = self.root / "PROJECTS" / "Alpha_old"
        os.rename(self.path.parent, moved)
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(self.path.parent), str(self.outside)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)

    def test_entry_and_byte_caps(self):
        with patch.object(vhd, "LIMIT_FILES", 1):
            with self.assertRaises(vhd.SafetyError):
                self.plan(target="PROJECTS/Alpha")
        with patch.object(vhd, "LIMIT_BYTES", 2):
            with self.assertRaises(vhd.SafetyError):
                self.plan()

    def test_cross_device_move_is_refused(self):
        class Device:
            def __init__(self, original, value):
                self.original = original
                self.st_dev = value
            def __getattr__(self, name):
                return getattr(self.original, name)
        original = Path.stat
        def dev(path, *args, **kwargs):
            if path == self.path:
                return Device(original(path, *args, **kwargs), 123)
            if path == self.outside:
                return Device(original(path, *args, **kwargs), 456)
            return original(path, *args, **kwargs)
        with patch.object(Path, "stat", dev):
            with self.assertRaises(vhd.SafetyError):
                vhd.no_replace(self.path, self.outside / "destination.md")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_platform_mutation_fails_closed(self):
        with patch.object(vhd.os, "name", "unsupported"):
            with self.assertRaises(vhd.SafetyError):
                with self.home.lock():
                    pass

    def test_core_and_runtime_markdown_links(self):
        for p in self.root.rglob("*.md"):
            if ".recycle" in p.parts or "ARCHIVE" in p.parts:
                continue
            for link in __import__("re").findall(r"\[[^\]]*\]\(([^)]+)\)", p.read_text(encoding="utf-8")):
                if not link.startswith(("https://", "http://", "#")):
                    self.assertTrue((p.parent / link.split("#", 1)[0]).exists(), (p, link))

    def test_interrupt_after_install_preserves_both_versions(self):
        replacement = self.path.parent / "replacement.md"
        replacement.write_text("new active")
        identifier = self.plan("update", source="PROJECTS/Alpha/replacement.md")
        def stop(name):
            if name == "after_install":
                raise OSError("simulated interruption")
        vhd.EVENT_HOOK = stop
        with self.assertRaises(OSError):
            self.home.apply(identifier)
        vhd.EVENT_HOOK = None
        self.assertEqual(self.path.read_text(), "new active")
        folder, record = self.home.transaction(identifier)
        self.assertEqual((folder / "payload").read_bytes(), self.original)
        self.assertEqual(record["state"], "ready")
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)

    def test_interrupt_during_restore_keeps_source_and_restored_target(self):
        identifier = self.apply("recycle")
        restore = self.plan("restore", None, identifier=identifier)
        def stop(name):
            if name == "after_restore":
                raise OSError("simulated interruption")
        vhd.EVENT_HOOK = stop
        with self.assertRaises(OSError):
            self.home.apply(restore)
        vhd.EVENT_HOOK = None
        self.assertEqual(self.path.read_bytes(), self.original)
        folder, _ = self.home.transaction(identifier)
        self.assertEqual((folder / "payload").read_bytes(), self.original)
        info = self.home.records(identifier=restore)
        self.assertEqual(info["record"]["state"], "captured")
        self.assertTrue(info["target_present"])
        with self.assertRaises(vhd.SafetyError):
            self.home.apply(restore)

    def test_partial_capture_is_not_restored(self):
        identifier = self.plan()
        def partial(source, destination, expected):
            destination.write_bytes(b"incomplete")
            raise OSError("simulated disk failure")
        with patch.object(vhd, "copy_checked", side_effect=partial):
            with self.assertRaises(OSError):
                self.home.apply(identifier)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.apply("recycle")
        with self.assertRaises(vhd.SafetyError):
            self.plan("restore", None, identifier=identifier)

    def test_windows_rename_refuses_a_last_moment_collision(self):
        destination = self.outside / "collision.md"
        original_rename = os.rename
        def collide(source, target):
            Path(target).write_bytes(b"other writer")
            return original_rename(source, target)
        with patch.object(vhd.os, "rename", side_effect=collide):
            with self.assertRaises(FileExistsError):
                vhd.no_replace(self.path, destination)
        self.assertEqual(destination.read_bytes(), b"other writer")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_cli_mutation_roundtrip(self):
        code, preview = self.cli("plan", "recycle", "--path", "PROJECTS/Alpha/draft.md", "--reason", "Synthetic test")
        self.assertEqual(code, 0)
        code, done = self.cli("apply", preview["plan_id"])
        self.assertEqual(code, 0)
        self.assertFalse(self.path.exists())
        code, restore = self.cli("plan", "restore", "--id", done["operation_id"], "--reason", "Synthetic restore")
        self.assertEqual(code, 0)
        code, result = self.cli("apply", restore["plan_id"])
        self.assertEqual(code, 0)
        self.assertEqual(result["state"], "complete")
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_setup_refuses_directory_as_identity(self):
        identity = self.root / "PERSONA" / "IDENTITY.md"
        retained = identity.with_suffix(".old")
        os.rename(identity, retained)
        identity.mkdir()
        with self.assertRaises(vhd.SafetyError):
            self.home.setup()
        self.assertTrue(retained.is_file())
        self.assertTrue(identity.is_dir())

    def test_two_projects_and_renamed_persona_resume(self):
        identity = self.root / "PERSONA" / "IDENTITY.md"
        identity.write_text("Name: Mira\nVoice: calm and direct.\n", encoding="utf-8")
        for name, secret in (("Alpha", "blue"), ("Beta", "green")):
            project = self.root / "PROJECTS" / name
            project.mkdir(exist_ok=True)
            (project / "PROGRESS").mkdir()
            (project / "PROGRESS" / "0001.md").write_text(f"# Complete\nDecision: {secret}\nNext: inspect source\n")
            (project / "HANDOFF.md").write_text("[latest](PROGRESS/0001.md)")
        (self.root / "MEMORY" / "HANDOFF.md").write_text(
            "[Alpha](../PROJECTS/Alpha/HANDOFF.md)\n", encoding="utf-8")
        (self.root / "PERSONA" / "HANDOFF.md").write_text(
            "[Alpha](../PROJECTS/Alpha/HANDOFF.md)\n", encoding="utf-8")
        other = vhd.Home(self.root)
        other.setup()
        self.assertEqual(identity.read_text(), "Name: Mira\nVoice: calm and direct.\n")
        alpha = vhd.inspect(other, "PROJECTS/Alpha/HANDOFF.md", links=True)
        self.assertEqual(len(alpha["links"]), 1)
        self.assertTrue(alpha["links"][0]["exists"])
        for path in ("MEMORY/HANDOFF.md", "PERSONA/HANDOFF.md", "PROJECTS/Alpha/HANDOFF.md"):
            code, handoff = self.cli("read", path)
            self.assertEqual(code, 0)
            link = handoff["text"].split("(", 1)[1].split(")", 1)[0]
            target = (self.root / path).parent / link
            self.assertTrue(target.is_file())
        code, checkpoint = self.cli("read", "PROJECTS/Alpha/PROGRESS/0001.md")
        self.assertEqual(code, 0)
        self.assertIn("Decision: blue", checkpoint["text"])
        self.assertNotIn("green", checkpoint["text"])


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-upgrade-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.source = self.base / "pkg"
        shutil.copytree(SOURCE, self.source, ignore=IGNORE)
        vhd.record_state(self.source / vhd.MANIFEST_NAME, vhd.package_manifest(self.source))
        self.root = self.base / "my-home"
        shutil.copytree(self.source, self.root)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def package(self, name="next", version=None, edits=None):
        target = self.base / name
        shutil.copytree(self.source, target)
        for relative, text in (edits or {}).items():
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        manifest = vhd.package_manifest(target, version=version or vhd.VERSION)
        vhd.record_state(target / vhd.MANIFEST_NAME, manifest)
        return target

    def test_init_records_state_and_keeps_it_on_second_run(self):
        state = vhd.read_state(self.home)
        self.assertEqual(state["version"], vhd.VERSION)
        self.assertEqual(state["manifest_sha256"], vhd.digest(vhd.packed(state["manifest"])))
        identifier = state["home_id"]
        self.assertEqual(self.home.setup()["created"], [])
        self.assertEqual(vhd.read_state(self.home)["home_id"], identifier)

    def test_manifest_skips_state_and_user_roots(self):
        (self.root / vhd.STATE_NAME).write_text("{}", encoding="utf-8")
        (self.root / "PERSONA" / "NOTE.md").write_text("mine\n", encoding="utf-8")
        paths = [entry["path"] for entry in vhd.package_manifest(self.root)["files"]]
        self.assertNotIn(vhd.STATE_NAME, paths)
        self.assertNotIn(vhd.MANIFEST_NAME, paths)
        self.assertFalse([path for path in paths if path.startswith("PERSONA/")])
        self.assertIn("OPERATIONS/CONTEXT.md", paths)

    def test_detect_prefers_home_over_package_copy(self):
        found = vhd.find_homes(self.base)
        self.assertTrue(found)
        self.assertEqual(Path(found[0]["path"]).name, "my-home")
        self.assertNotIn("package", found[0]["markers"])

    def test_detect_stops_on_a_tie(self):
        twin = self.base / "twin"
        shutil.copytree(self.root, twin)
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.select_home(self.base)
        self.assertIn("Ambiguous VHD home", str(caught.exception))

    def test_upgrade_marks_stale_and_writes_with_fingerprint(self):
        package = self.package("next", version=vhd.VERSION, edits={"OPERATIONS/CONTEXT.md": "# Context discipline\n\nRewritten upstream.\n"})
        preview = vhd.upgrade(self.home, package)
        self.assertEqual(preview["mode"], "normal")
        self.assertEqual(preview["counts"].get("stale"), 1)
        self.assertEqual(preview["written"], [])
        result = vhd.upgrade(self.home, package, True, preview["fingerprint"])
        self.assertEqual(result["written"], ["OPERATIONS/CONTEXT.md"])
        self.assertTrue(result["snapshots"])
        self.assertEqual((self.root / "OPERATIONS" / "CONTEXT.md").read_text(encoding="utf-8").strip(), "# Context discipline\n\nRewritten upstream.".strip())
        self.assertEqual(vhd.read_state(self.home)["version"], vhd.VERSION)

    def test_upgrade_keeps_local_edits_and_reports_conflict(self):
        local = self.root / "OPERATIONS" / "DEVELOPMENT.md"
        local.write_text("# Development workflow\n\nlocal rules\n", encoding="utf-8")
        package = self.package("next", version=vhd.VERSION, edits={"OPERATIONS/DEVELOPMENT.md": "# Development workflow\n\nupstream rules\n"})
        preview = vhd.upgrade(self.home, package)
        self.assertEqual(preview["counts"].get("conflict"), 1)
        self.assertGreater(preview["pending"], 0)
        with self.assertRaises(vhd.SafetyError):
            vhd.upgrade(self.home, package, True, "wrong")
        self.assertIn("local rules", local.read_text(encoding="utf-8"))

    def test_upgrade_degrades_without_state_and_refuses_user_zone(self):
        (self.root / vhd.STATE_NAME).unlink()
        preview = vhd.upgrade(self.home, self.source)
        self.assertEqual(preview["mode"], "degraded")
        self.assertGreater(preview["counts"].get("conflict"), 0)
        self.assertEqual(preview["written"], [])
        manifest = vhd.package_manifest(self.source)
        manifest["files"].append({"path": "PERSONA/IDENTITY.md", "kind": "meta",
                                  "sha256": "0" * 64, "bytes": 1})
        target = self.base / "bad"
        shutil.copytree(self.source, target)
        vhd.record_state(target / vhd.MANIFEST_NAME, manifest)
        entries = vhd.upgrade(self.home, target)["entries"]
        self.assertEqual([entry["class"] for entry in entries if entry["path"] == "PERSONA/IDENTITY.md"], ["refused"])

    def test_upgrade_refuses_downgrade(self):
        package = self.package("old", version="0.0.1")
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.upgrade(self.home, package)
        self.assertIn("older than this home", str(caught.exception))

    def test_upgrade_is_idempotent_at_the_same_version(self):
        package = self.package("same")
        preview = vhd.upgrade(self.home, package)
        result = vhd.upgrade(self.home, package, True, preview["fingerprint"])
        self.assertEqual(result["written"], [])
        self.assertIn("Already current", result["notice"])
        self.assertFalse((self.root / ".recycle" / "operation.lock").exists())
        self.assertFalse((self.root / ".recycle" / "pending-upgrade.json").exists())

    def test_upgrade_resumes_a_partly_applied_batch(self):
        text = "# Context discipline\n\nRewritten upstream.\n"
        package = self.package("next", version=vhd.VERSION, edits={"OPERATIONS/CONTEXT.md": text})
        shutil.copy2(package / "OPERATIONS" / "CONTEXT.md", self.root / "OPERATIONS" / "CONTEXT.md")
        preview = vhd.upgrade(self.home, package)
        applied = [entry["path"] for entry in preview["entries"] if entry["class"] == "applied"]
        self.assertEqual(applied, ["OPERATIONS/CONTEXT.md"])
        result = vhd.upgrade(self.home, package, True, preview["fingerprint"])
        self.assertEqual(result["written"], [])
        self.assertEqual(result["skipped"], ["OPERATIONS/CONTEXT.md"])
        self.assertEqual(vhd.read_state(self.home)["version"], vhd.VERSION)
        self.assertFalse((self.root / ".recycle" / "pending-upgrade.json").exists())

    def test_upgrade_reports_an_interrupted_batch(self):
        record = {"schema": 1, "fingerprint": "abc", "version": vhd.VERSION, "planned": ["UPDATE.md"]}
        area = self.root / ".recycle"
        area.mkdir(exist_ok=True)
        (area / "pending-upgrade.json").write_text(json.dumps(record), encoding="utf-8")
        preview = vhd.upgrade(self.home, self.package("same"))
        self.assertEqual(preview["interrupted"]["fingerprint"], "abc")

    def test_upgrade_installs_the_package_manifest(self):
        package = self.package("next", version=vhd.VERSION,
                               edits={"OPERATIONS/CONTEXT.md": "# Context discipline\n\nRewritten upstream.\n"})
        preview = vhd.upgrade(self.home, package)
        result = vhd.upgrade(self.home, package, True, preview["fingerprint"])
        self.assertTrue(result["manifest_updated"])
        self.assertEqual((self.root / vhd.MANIFEST_NAME).read_bytes(),
                         (package / vhd.MANIFEST_NAME).read_bytes())
        self.assertEqual(vhd.release_check(self.home)["failed"], 0)

    def test_upgrade_snapshots_a_changed_package_document(self):
        package = self.package("next", version=vhd.VERSION,
                               edits={"CHANGELOG.md": "# Changelog\n\n## " + vhd.VERSION + "\n\n- Upstream note.\n"})
        preview = vhd.upgrade(self.home, package)
        self.assertEqual(preview["counts"].get("stale"), 1)
        result = vhd.upgrade(self.home, package, True, preview["fingerprint"])
        self.assertEqual(result["written"], ["CHANGELOG.md"])
        self.assertTrue(result["snapshots"])
        self.assertIn("Upstream note", (self.root / "CHANGELOG.md").read_text(encoding="utf-8"))

    def test_links_finds_missing_target_and_anchor(self):
        (self.root / "NOTES.md").write_text("[a](missing.md) and [b](START_HERE.md#nope)\n", encoding="utf-8")
        result = vhd.links_check(self.home)
        self.assertGreaterEqual(result["failed"], 2)
        states = sorted(entry["state"] for entry in result["findings"])
        self.assertEqual(states, ["anchor", "missing"])

    def test_routes_flags_missing_and_oversized_parts(self):
        (self.root / vhd.ROUTES_NAME).write_text(json.dumps({"schema": 1, "parts": [
            {"id": "gone", "path": "NOPE.md", "limit": 100},
            {"id": "big", "path": "START_HERE.md", "limit": 10}]}), encoding="utf-8")
        result = vhd.routes_check(self.home)
        self.assertEqual(result["failed"], 2)
        self.assertEqual([entry["state"] for entry in result["parts"]], ["missing", "oversized"])

    def test_package_carries_no_private_markers(self):
        config = SOURCE / "MEMORY" / "CONFIG.json"
        if not config.is_file():
            self.skipTest("no local private marker list beside this package")
        markers = json.loads(config.read_text(encoding="utf-8")).get("private_markers", [])
        if not markers:
            self.skipTest("no private marker configured for this home")
        entries = vhd.package_manifest(SOURCE)["files"]
        self.assertTrue(entries)
        for entry in entries:
            path = SOURCE / entry["path"]
            if path.suffix.lower() not in {".md", ".py", ".json", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in markers:
                self.assertNotIn(marker, text, f"{marker} found in {entry['path']}")


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-release-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_package_ships_the_line_ending_rule(self):
        rule = (SOURCE / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* -text", rule)
        entries = {entry["path"] for entry in vhd.package_manifest(SOURCE)["files"]}
        self.assertIn(".gitattributes", entries)

    def test_release_check_passes_on_consistent_package(self):
        result = vhd.release_check(self.home)
        self.assertEqual(result["version"], vhd.VERSION)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(result["manifest"]["changed"], [])
        self.assertGreaterEqual(result["checks"], 5)

    def test_release_check_flags_an_incomplete_default_persona(self):
        (self.root / "TEMPLATES" / "IDENTITY.md").write_text("# Identity\n\nName: Vee\n", encoding="utf-8")
        result = vhd.release_check(self.home)
        self.assertIn("default-persona", [entry["check"] for entry in result["findings"]])

    def test_release_check_flags_document_and_manifest_drift(self):
        (self.root / "README.md").write_text("# Virtual Home DIY 0.3.1\n\nold text\n", encoding="utf-8")
        result = vhd.release_check(self.home)
        self.assertGreaterEqual(result["failed"], 2)
        checks = {entry["check"] for entry in result["findings"]}
        self.assertIn("document-version", checks)
        self.assertIn("manifest-coverage", checks)
        self.assertIn("README.md", result["manifest"]["changed"])

    def test_release_check_project_and_compare(self):
        project = self.base / "project"
        project.mkdir()
        (project / "README.md").write_text("# Project\n\n**Virtual Home DIY " + vhd.VERSION + "**\n", encoding="utf-8")
        (project / "HANDOFF.md").write_text("Current package: VHD " + vhd.VERSION + ".\n", encoding="utf-8")
        release = self.base / "release"
        shutil.copytree(self.root, release)
        (release / "UPDATE.md").write_text("drifted\n", encoding="utf-8")
        result = vhd.release_check(self.home, str(project), str(release))
        self.assertEqual([entry["check"] for entry in result["findings"]], ["release-compare"])
        self.assertEqual(result["compare"]["mismatch"][0]["state"], "differs")
        (project / "HANDOFF.md").write_text("Current package: VHD 0.0.1.\n", encoding="utf-8")
        drift = vhd.release_check(self.home, str(project))
        self.assertEqual([entry["path"] for entry in drift["findings"]], ["HANDOFF.md"])


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-doctor-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_doctor_reports_modes_commands_and_startup_bytes(self):
        result = vhd.doctor(self.home)
        self.assertTrue(result["modes"]["available"]["standard"])
        self.assertTrue(result["modes"]["available"]["autonomous"])
        self.assertFalse(result["modes"]["opt_in"])
        self.assertIn(result["modes"]["selected"], {"standard", "enhanced"})
        self.assertFalse(result["lock"]["present"])
        self.assertIsNone(result["version_in_sync"])
        self.assertIn("doctor", result["commands"])
        self.assertGreaterEqual(len(result["commands"]), 15)
        self.assertEqual(result["package"]["missing"], [])
        self.assertGreater(result["startup"]["bytes"], 0)
        self.assertEqual(result["startup"]["failed"], 0)

    def test_doctor_reports_size_drift_and_present_lock(self):
        (self.root / "UPDATE.md").write_text("short\n", encoding="utf-8")
        area = self.root / ".recycle"
        area.mkdir(exist_ok=True)
        (area / "operation.lock").write_text(json.dumps({"schema": 1, "pid": 4321, "host": "another-host",
                                                          "birth": "1", "token": "t",
                                                          "created": "2026-11-24T00:00:00+00:00"}),
                                            encoding="utf-8")
        result = vhd.doctor(self.home)
        self.assertIn("UPDATE.md", result["package"]["size_changed"])
        self.assertTrue(result["lock"]["present"])
        self.assertEqual(result["lock"]["record"]["pid"], 4321)
        self.assertEqual(result["lock"]["state"], "unknown")

    def test_mode_override_follows_config_and_flag(self):
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "mode": "standard"}), encoding="utf-8")
        self.assertEqual(vhd.doctor(self.home)["modes"]["selected"], "standard")
        self.assertEqual(vhd.doctor(self.home, "enhanced")["modes"]["selected"], "enhanced")
        self.assertTrue(vhd.doctor(self.home, "enhanced")["modes"]["available"]["enhanced"])

    def test_unavailable_or_unknown_mode_falls_back_with_a_warning(self):
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "mode": "autonomous"}), encoding="utf-8")
        result = vhd.doctor(self.home)
        self.assertIn(result["modes"]["selected"], {"standard", "enhanced"})
        self.assertTrue(result["modes"]["warnings"])
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "mode": "turbo"}), encoding="utf-8")
        self.assertTrue(vhd.doctor(self.home)["modes"]["warnings"])
        (memory / "CONFIG.json").write_text("not json", encoding="utf-8")
        self.assertTrue(vhd.doctor(self.home)["modes"]["warnings"])

    def test_license_preference_defaults_true_and_warns_when_disabled(self):
        result = vhd.doctor(self.home)
        self.assertTrue(result["license"]["compliance"])
        self.assertTrue(result["license"]["briefing_present"])
        self.assertFalse([item for item in result["warnings"] if "no additional rights" in item])
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "license_compliance": False}),
                                             encoding="utf-8")
        disabled = vhd.doctor(self.home)
        self.assertFalse(disabled["license"]["compliance"])
        self.assertTrue([item for item in disabled["warnings"] if "no additional rights" in item])
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "license_compliance": "no"}),
                                             encoding="utf-8")
        self.assertTrue(vhd.doctor(self.home)["license"]["compliance"])


class KnowledgeTests(unittest.TestCase):
    METHOD = ("# Method card\n\nStable ID: eng.test\nTitle: Test method\nStatus: VERIFIED\nSteward: owner\n"
              "Use when: testing a card\nProcedure: run the check\n"
              "Environment and prerequisites: Python 3.13\n"
              "Evidence and verification date: 2026-11-24 PASS\n"
              "Known limits and recheck triggers: none\n")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-knowledge-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def write_card(self, name, text):
        folder = self.root / "MEMORY" / "KNOWLEDGE"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_method_check_passes_on_empty_catalog(self):
        result = vhd.method_check(self.home)
        self.assertEqual((result["catalog"], result["failed"], result["cards"]), ("KNOWLEDGE", 0, []))

    def test_method_check_flags_invalid_cards(self):
        self.write_card("good.md", self.METHOD)
        self.write_card("copy.md", self.METHOD)
        self.write_card("bad.md", "# Method card\n\nStable ID: eng.bad\nTitle: Bad\nStatus: DONE\n")
        result = vhd.method_check(self.home)
        problems = {entry["problem"] for entry in result["findings"]}
        self.assertEqual(result["catalog"], "MEMORY/KNOWLEDGE")
        self.assertEqual(len(result["cards"]), 3)
        self.assertIn("duplicate-id", problems)
        self.assertIn("invalid-status", problems)
        self.assertIn("missing-procedure", problems)
        self.assertIn("missing-steward", problems)

    def test_failure_card_requires_a_replacement(self):
        self.write_card("fail.md", "# Failure card\n\nStable ID: fail.eng.bad\nTitle: Bad\nStatus: FAILED\n"
                                   "Steward: owner\nUse when: symptom\nWhat was tried: x\nWhat was assumed: y\n"
                                   "What actually happened: z\nWhy it failed: w\nReplacement or open question:\n"
                                   "Environment: Windows\nEvidence and date: 2026-11-24 FAIL\n"
                                   "Recheck when: a version change\n")
        problems = {entry["problem"] for entry in vhd.method_check(self.home)["findings"]}
        self.assertIn("failure-without-replacement", problems)

    def test_method_show_returns_one_bounded_card(self):
        self.write_card("good.md", self.METHOD)
        shown = vhd.method_show(self.home, "eng.test")
        self.assertEqual((shown["status"], shown["path"]), ("VERIFIED", "MEMORY/KNOWLEDGE/good.md"))
        self.assertIn("Procedure: run the check", shown["text"])
        with self.assertRaises(vhd.SafetyError):
            vhd.method_show(self.home, "eng.missing")

    def test_status_card_writes_and_detects_staleness(self):
        raw = "PERSONA/PROGRESSION/EXP.md"
        ledger = self.root / raw
        row = "| alpha.summary | Alpha | engineering.integration | Summary | 2026-11-24 | PASS | draft.md | 2 |\n"
        text = ledger.read_text(encoding="utf-8").replace("\n\nOne row", "\n" + row + "\nOne row")
        ledger.write_text(text, encoding="utf-8")
        derived = vhd.status_card(self.home, raw, True)
        self.assertEqual((derived["card"]["xp"], derived["written"]), (2, "PERSONA/PROGRESSION/STATUS.json"))
        self.assertTrue((self.root / derived["written"]).is_file())
        self.assertTrue(vhd.status_card(self.home, raw)["fresh"])
        ledger.write_text(text.replace(row, row + "| beta.row | Beta | engineering.implementation | Next | 2026-11-24 | PASS | b.md | 1 |\n"),
                          encoding="utf-8")
        self.assertFalse(vhd.status_card(self.home, raw)["fresh"])


class LockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-lock-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def write_lock(self, payload):
        area = self.root / ".recycle"
        area.mkdir(exist_ok=True)
        path = area / "operation.lock"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_lock_report_absent_and_legacy_refused(self):
        self.assertEqual(vhd.lock_report(self.home)["state"], "absent")
        self.write_lock({"pid": 1, "created": "2026-11-24T00:00:00+00:00"})
        report = vhd.lock_report(self.home)
        self.assertEqual((report["present"], report["state"]), (True, "unknown"))
        with self.assertRaises(vhd.SafetyError):
            vhd.lock_recover(self.home)

    def test_lock_report_quarantines_a_stale_owner(self):
        self.write_lock({"schema": 1, "pid": 99999999, "host": vhd.host_mark(), "birth": "1",
                         "token": "synthetic", "created": "2026-11-24T00:00:00+00:00"})
        self.assertEqual(vhd.lock_report(self.home)["state"], "stale")
        result = vhd.lock_recover(self.home)
        self.assertTrue((self.root / result["quarantined"]).is_file())
        self.assertFalse((self.root / ".recycle" / "operation.lock").exists())
        self.assertEqual(vhd.lock_report(self.home)["state"], "absent")
        self.assertEqual(len(list((self.root / ".recycle" / "locks").glob("*.json"))), 1)

    def test_lock_report_refuses_a_foreign_host(self):
        self.write_lock({"schema": 1, "pid": os.getpid(), "host": "another-host", "birth": "1",
                         "token": "synthetic", "created": "2026-11-24T00:00:00+00:00"})
        report = vhd.lock_report(self.home)
        self.assertEqual(report["state"], "unknown")
        self.assertIn("another host", report["reason"])

    def test_lock_is_reentrant_and_blocks_a_second_owner(self):
        with self.home.lock():
            self.assertEqual(vhd.lock_report(self.home)["state"], "live")
            with self.home.lock():
                self.assertEqual(vhd.lock_report(self.home)["state"], "live")
            with self.assertRaises(vhd.SafetyError):
                with vhd.Home(self.root).lock():
                    pass
        self.assertFalse((self.root / ".recycle" / "operation.lock").exists())
        self.assertIsNone(self.home.lock_token)


class PortableMoveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-move-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))

    def tearDown(self):
        self.temp.cleanup()

    def test_file_move_keeps_bytes_and_removes_source(self):
        source = self.base / "payload.txt"
        source.write_text("portable move\n", encoding="utf-8")
        destination = self.base / "archived.txt"
        vhd.portable_move(source, destination)
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_text(encoding="utf-8"), "portable move\n")

    def test_destination_collision_is_refused(self):
        source = self.base / "payload.txt"
        source.write_text("keep\n", encoding="utf-8")
        destination = self.base / "taken.txt"
        destination.write_text("existing\n", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError):
            vhd.portable_move(source, destination)
        self.assertEqual(source.read_text(encoding="utf-8"), "keep\n")
        self.assertEqual(destination.read_text(encoding="utf-8"), "existing\n")

    def test_directory_move_is_recursive(self):
        source = self.base / "folder"
        (source / "nested").mkdir(parents=True)
        (source / "top.md").write_text("top\n", encoding="utf-8")
        (source / "nested" / "deep.md").write_text("deep\n", encoding="utf-8")
        destination = self.base / "restored"
        vhd.portable_move(source, destination)
        self.assertFalse(source.exists())
        self.assertEqual((destination / "top.md").read_text(encoding="utf-8"), "top\n")
        self.assertEqual((destination / "nested" / "deep.md").read_text(encoding="utf-8"), "deep\n")

    def test_explicit_posix_dispatch(self):
        source = self.base / "payload.txt"
        source.write_text("dispatch\n", encoding="utf-8")
        destination = self.base / "moved.txt"
        vhd.no_replace(source, destination, platform="posix")
        self.assertEqual(destination.read_text(encoding="utf-8"), "dispatch\n")
        self.assertFalse(source.exists())


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-archive-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.source = self.base / "pkg"
        shutil.copytree(SOURCE, self.source, ignore=IGNORE)
        vhd.record_state(self.source / vhd.MANIFEST_NAME, vhd.package_manifest(self.source))
        self.root = self.base / "my-home"
        shutil.copytree(self.source, self.root)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def release(self, name="release.zip", edits=None):
        folder = self.base / ("zip-" + name)
        shutil.copytree(self.source, folder)
        for relative, text in (edits or {}).items():
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        vhd.record_state(folder / vhd.MANIFEST_NAME, vhd.package_manifest(folder))
        archive = self.base / name
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(folder).as_posix())
        return archive, folder

    def test_zip_update_installs_and_cleans_staging(self):
        archive, _ = self.release(edits={"OPERATIONS/CONTEXT.md": "# Context discipline\n\nZip upstream.\n"})
        preview = vhd.upgrade(self.home, archive=archive)
        self.assertGreater(preview["archive"]["entries"], 0)
        self.assertEqual([entry["path"] for entry in preview["entries"] if entry["class"] == "stale"],
                         ["OPERATIONS/CONTEXT.md"])
        digest_file = self.base / "release.sha256"
        digest_file.write_text(vhd.hash_file(archive) + "  release.zip\n", encoding="utf-8")
        result = vhd.upgrade(self.home, archive=archive, checksum=digest_file, write=True,
                             confirm=preview["fingerprint"])
        self.assertEqual(result["written"], ["OPERATIONS/CONTEXT.md"])
        self.assertIn("verified", result["archive"]["integrity"])
        self.assertFalse([path for path in self.base.iterdir() if path.name.startswith("vhd-stage-")])

    def test_zip_refuses_traversal_absolute_and_duplicate_names(self):
        for name, entry in (("traversal.zip", "../evil.txt"), ("absolute.zip", "/evil.txt")):
            archive = self.base / name
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr(entry, "x")
            with self.assertRaises(vhd.SafetyError):
                vhd.upgrade(self.home, archive=archive)
        duplicate = self.base / "duplicate.zip"
        with zipfile.ZipFile(duplicate, "w") as bundle:
            bundle.writestr("same.txt", "one")
            bundle.writestr("same.txt", "two")
        with self.assertRaises(vhd.SafetyError):
            vhd.upgrade(self.home, archive=duplicate)

    def test_zip_refuses_symlink_and_bomb_entries(self):
        link = self.base / "link.zip"
        with zipfile.ZipFile(link, "w") as bundle:
            info = zipfile.ZipInfo("link")
            info.external_attr = 0o120777 << 16
            bundle.writestr(info, "target")
        with self.assertRaises(vhd.SafetyError):
            vhd.upgrade(self.home, archive=link)
        bomb = self.base / "bomb.zip"
        with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("expand.bin", b"\0" * (5 * 1024 * 1024))
        with self.assertRaises(vhd.SafetyError):
            vhd.upgrade(self.home, archive=bomb)

    def test_zip_update_keeps_a_customized_persona(self):
        identity = self.root / "PERSONA" / "IDENTITY.md"
        custom = "# My assistant\n\nName: Rin\nVoice: dry and brief\n"
        identity.write_text(custom, encoding="utf-8")
        archive, _ = self.release(edits={"OPERATIONS/CONTEXT.md": "# Context discipline\n\nZip upstream.\n"})
        preview = vhd.upgrade(self.home, archive=archive)
        vhd.upgrade(self.home, archive=archive, write=True, confirm=preview["fingerprint"])
        self.assertEqual(identity.read_text(encoding="utf-8"), custom)

    def test_checksum_mismatch_is_refused(self):
        archive, _ = self.release()
        digest_file = self.base / "wrong.sha256"
        digest_file.write_text("0" * 64 + "  release.zip\n", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.upgrade(self.home, archive=archive, checksum=digest_file)
        self.assertIn("checksum", str(caught.exception))

    def test_listed_migrations_block_apply(self):
        _, folder = self.release()
        manifest = vhd.package_manifest(folder)
        manifest["migrations"] = ["0001-rename-context"]
        vhd.record_state(folder / vhd.MANIFEST_NAME, manifest)
        archive = self.base / "migrate.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(folder).as_posix())
        preview = vhd.upgrade(self.home, archive=archive)
        self.assertEqual(preview["migrations"], ["0001-rename-context"])
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.upgrade(self.home, archive=archive, write=True, confirm=preview["fingerprint"])
        self.assertIn("migrations", str(caught.exception))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-audit-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def test_clean_package_has_no_findings(self):
        result = vhd.audit(self.home)
        self.assertEqual((result["failed"], result["redacted"]), (0, True))
        self.assertEqual(result["markers"], 0)

    def test_release_folder_findings_are_redacted(self):
        release = self.base / "release"
        release.mkdir()
        (release / "notes.md").write_text("marker ExampleOwner " + FAKE_CREDENTIAL + " " + FAKE_DRIVE + chr(10), encoding="utf-8")
        (release / "debug.log").write_text("trace\n", encoding="utf-8")
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "private_markers": ["ExampleOwner"]}),
                                              encoding="utf-8")
        result = vhd.audit(self.home, release)
        kinds = {entry["kind"] for entry in result["findings"]}
        self.assertIn("private-marker", kinds)
        self.assertIn("credential", kinds)
        self.assertIn("absolute-path", kinds)
        self.assertIn("runtime-artifact", kinds)
        self.assertTrue(result["redacted"])
        self.assertNotIn("abcdefghijklmnop", json.dumps(result))

    def test_invalid_markers_are_ignored_with_a_warning(self):
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "private_markers": "ExampleOwner"}),
                                             encoding="utf-8")
        result = vhd.audit(self.home)
        self.assertEqual(result["markers"], 0)
        self.assertTrue(result["warnings"])


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-runtime-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()

    def tearDown(self):
        self.temp.cleanup()

    def opt_in(self):
        memory = self.root / "MEMORY"
        memory.mkdir(exist_ok=True)
        (memory / "CONFIG.json").write_text(json.dumps({"schema": 1, "autonomous_opt_in": True}),
                                             encoding="utf-8")

    def test_default_status_is_stopped_with_no_tasks(self):
        result = vhd.runtime_command(self.home, "status")
        self.assertEqual((result["mode"], result["health"], result["tasks"]), ("stopped", "ok", 0))
        self.assertFalse(result["stop"])
        self.assertFalse(result["tokens"]["measured"])

    def test_add_is_deduplicated_by_kind_and_payload(self):
        first = vhd.runtime_command(self.home, "add", kind="doctor")
        second = vhd.runtime_command(self.home, "add", kind="doctor")
        other = vhd.runtime_command(self.home, "add", kind="links")
        self.assertTrue(first["added"])
        self.assertFalse(second["added"])
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["id"], other["id"])
        self.assertEqual(vhd.runtime_status(self.home)["tasks"], 2)

    def test_run_requires_opt_in_and_a_started_runtime(self):
        vhd.runtime_command(self.home, "add", kind="doctor")
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.runtime_command(self.home, "run")
        self.assertIn("autonomous_opt_in", str(caught.exception))
        self.opt_in()
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.runtime_command(self.home, "run")
        self.assertIn("Start the runtime", str(caught.exception))

    def test_run_executes_deterministic_tasks_within_budget(self):
        self.opt_in()
        vhd.runtime_command(self.home, "add", kind="doctor")
        vhd.runtime_command(self.home, "add", kind="links")
        vhd.runtime_command(self.home, "start")
        result = vhd.runtime_command(self.home, "run")
        self.assertEqual(len(result["ran"]), 2)
        self.assertEqual([entry["status"] for entry in result["ran"]], ["done", "done"])
        status = vhd.runtime_status(self.home)
        self.assertEqual(status["counts"]["done"], 2)
        self.assertEqual(status["state"]["runs"], 1)
        self.assertEqual(status["budget"]["tasks_used"], 2)
        self.assertTrue(status["recent"])

    def test_inference_is_blocked_without_a_provider(self):
        self.opt_in()
        vhd.runtime_command(self.home, "add", kind="inference", payload="summarize the log")
        vhd.runtime_command(self.home, "start")
        result = vhd.runtime_command(self.home, "run")
        self.assertEqual(result["ran"][0]["status"], "blocked")
        self.assertEqual(vhd.runtime_status(self.home)["budget"]["requests_used"], 0)

    def test_failure_backs_off_and_emergency_stop_blocks_a_run(self):
        self.opt_in()
        vhd.runtime_command(self.home, "add", kind="doctor")
        vhd.runtime_command(self.home, "start")
        with patch.object(vhd, "doctor", side_effect=vhd.SafetyError("synthetic failure")):
            first = vhd.runtime_command(self.home, "run")
        self.assertEqual(first["ran"][0]["status"], "retry")
        again = vhd.runtime_command(self.home, "run")
        self.assertEqual(again["ran"], [])
        stop = self.root / "MEMORY" / "RUNTIME" / "STOP"
        stop.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.runtime_command(self.home, "run")
        self.assertIn("emergency stop", str(caught.exception))


class SmartGitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-git-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()
        subprocess.run(["git", "init"], cwd=self.root, capture_output=True)
        self.public = self.base / "public"

    def tearDown(self):
        try:
            self.temp.cleanup()
        except OSError:
            pass

    def test_export_keeps_vee_and_excludes_user_data(self):
        (self.root / "MEMORY" / "PRIVATE").mkdir(parents=True, exist_ok=True)
        (self.root / "MEMORY" / "PRIVATE" / "note.md").write_text("private note\n", encoding="utf-8")
        (self.root / "PERSONA" / "IDENTITY.md").write_text("# Identity\n\nName: Rin\n", encoding="utf-8")
        exported = vhd.git_export(self.home, self.public)
        self.assertFalse((self.public / "MEMORY").exists())
        self.assertFalse((self.public / "PERSONA").exists())
        persona = (self.public / "TEMPLATES" / "IDENTITY.md").read_text(encoding="utf-8")
        self.assertIn("Name: Vee", persona)
        self.assertGreaterEqual(len(persona), 800)
        self.assertEqual(exported["version"], vhd.VERSION)
        self.assertTrue(vhd.git_verify(self.home, self.public)["passed"])

    def test_export_refuses_a_destination_inside_the_home(self):
        with self.assertRaises(vhd.SafetyError):
            vhd.git_export(self.home, self.root / "public")

    def test_verify_blocks_an_extra_file_and_a_missing_record(self):
        vhd.git_export(self.home, self.public)
        (self.public / "extra.md").write_text("unexpected\n", encoding="utf-8")
        result = vhd.git_verify(self.home, self.public)
        self.assertFalse(result["passed"])
        self.assertIn("extra", [entry["problem"] for entry in result["findings"]])
        with self.assertRaises(vhd.SafetyError):
            vhd.git_verify(self.home, self.base)

    def test_publish_needs_the_verified_fingerprint(self):
        vhd.git_export(self.home, self.public)
        with self.assertRaises(vhd.SafetyError) as caught:
            vhd.git_publish(self.home, self.public, "0" * 64, "wrong digest")
        self.assertIn("fingerprint", str(caught.exception))

    def test_publish_keeps_independent_history(self):
        vhd.git_export(self.home, self.public)
        first = vhd.git_publish(self.home, self.public, vhd.git_verify(self.home, self.public)["fingerprint"], "one")
        self.assertIsNotNone(first["committed"])
        self.assertFalse(first["pushed"])
        (self.root / "MEMORY" / "note.md").write_text("changed\n", encoding="utf-8")
        vhd.git_export(self.home, self.public)
        second = vhd.git_publish(self.home, self.public, vhd.git_verify(self.home, self.public)["fingerprint"], "two")
        self.assertNotEqual(first["committed"], second["committed"])
        log = subprocess.run(["git", "log", "--oneline"], cwd=self.public, capture_output=True, text=True)
        self.assertEqual(len(log.stdout.strip().splitlines()), 2)
        self.assertNotEqual(vhd.repo_root(self.public), vhd.repo_root(self.root))

    def test_export_includes_tests_outside_the_release_allowlist(self):
        source = self.base / "tests" / "test_vhd.py"
        source.parent.mkdir()
        source.write_text("# public test stand-in\n", encoding="utf-8")
        result = vhd.git_export(self.home, self.public)
        self.assertEqual(result["extras"], ["tests/test_vhd.py"])
        self.assertEqual(result["extras_skipped"], [])
        self.assertTrue((self.public / "tests" / "test_vhd.py").is_file())
        manifest = json.loads((self.public / vhd.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertNotIn("tests/test_vhd.py", {entry["path"] for entry in manifest["files"]})
        self.assertTrue(vhd.git_verify(self.home, self.public)["passed"])

    def test_verify_reports_a_changed_test_source(self):
        source = self.base / "tests" / "test_vhd.py"
        source.parent.mkdir()
        source.write_text("first\n", encoding="utf-8")
        vhd.git_export(self.home, self.public)
        self.assertTrue(vhd.git_verify(self.home, self.public)["passed"])
        source.write_text("second\n", encoding="utf-8")
        result = vhd.git_verify(self.home, self.public)
        self.assertFalse(result["passed"])
        self.assertIn("source-differs", {entry["problem"] for entry in result["findings"]})

    def test_export_skips_a_missing_test_source(self):
        result = vhd.git_export(self.home, self.public)
        self.assertEqual(result["extras"], [])
        self.assertEqual(result["extras_skipped"][0]["path"], "tests/test_vhd.py")
        self.assertTrue(vhd.git_verify(self.home, self.public)["passed"])

    def test_manifest_keeps_export_extras_and_skips_top_level_tests(self):
        (self.root / "tests").mkdir(exist_ok=True)
        (self.root / "tests" / "note.md").write_text("local test note\n", encoding="utf-8")
        manifest = vhd.package_manifest(self.root)
        self.assertNotIn("tests/note.md", {entry["path"] for entry in manifest["files"]})
        vhd.manifest_command(self.root, True)
        stored = json.loads((self.root / vhd.MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(stored["export_extra"], ["tests/test_vhd.py"])

    def test_checkpoint_commits_an_ignored_private_note(self):
        note = self.root / "MEMORY" / "PRIVATE" / "note.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text("private memory\n", encoding="utf-8")
        result = vhd.git_checkpoint(self.home, ["MEMORY/PRIVATE/note.md"], "checkpoint private note", True)
        self.assertIsNotNone(result["committed"])
        tracked = subprocess.run(["git", "ls-files"], cwd=self.root, capture_output=True, text=True).stdout
        self.assertIn("MEMORY/PRIVATE/note.md", tracked)
        self.assertEqual(note.read_text(encoding="utf-8"), "private memory\n")


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-index-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()
        self.notes = self.root / "PROJECTS" / "Beta" / "notes.md"
        self.notes.parent.mkdir(parents=True, exist_ok=True)
        self.notes.write_text("# Notes\n\nThe recovery ladder keeps derived state honest.\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_index_covers_text_and_skips_private_and_derived(self):
        private = self.root / "PROJECTS" / "Beta" / "PRIVATE" / "secret.md"
        private.parent.mkdir()
        private.write_text("the recovery ladder stays private\n", encoding="utf-8")
        result = vhd.index_command(self.home)
        document = vhd.index_read(self.home)
        paths = {entry["path"] for entry in document["documents"]}
        self.assertIn("PROJECTS/Beta/notes.md", paths)
        self.assertIn("START_HERE.md", paths)
        self.assertNotIn("PROJECTS/Beta/PRIVATE/secret.md", paths)
        self.assertNotIn(vhd.INDEX_NAME, paths)
        self.assertEqual(result["freshness"]["state"], "verified")
        self.assertGreater(result["documents"], 0)

    def test_index_reuses_hashes_and_reports_a_rename(self):
        first = vhd.index_command(self.home)
        self.assertGreater(first["hashed"], 0)
        second = vhd.index_command(self.home)
        self.assertEqual((second["hashed"], second["documents"]), (0, first["documents"]))
        self.notes.rename(self.notes.parent / "journal.md")
        third = vhd.index_command(self.home)
        self.assertEqual(third["renamed"], [{"from": "PROJECTS/Beta/notes.md", "to": "PROJECTS/Beta/journal.md"}])
        self.assertEqual(third["hashed"], 1)

    def test_index_full_reports_drift_against_the_previous_index(self):
        vhd.index_command(self.home)
        self.notes.unlink()
        (self.notes.parent / "fresh.md").write_text("brand new\n", encoding="utf-8")
        result = vhd.index_command(self.home, full=True)
        self.assertIn("PROJECTS/Beta/notes.md", result["drift"]["missing"])
        self.assertIn("PROJECTS/Beta/fresh.md", result["drift"]["extra"])

    def test_search_returns_ranked_hits_with_a_snippet(self):
        result = vhd.search_command(self.home, "honest derived")
        self.assertEqual(result["source"], "index")
        self.assertGreaterEqual(result["matches"], 1)
        top = result["results"][0]
        self.assertEqual((top["path"], top["matched"]), ("PROJECTS/Beta/notes.md", 2))
        self.assertEqual(top["snippet"]["line"], 3)
        self.assertIn("keeps derived state honest", top["snippet"]["text"])

    def test_search_throttles_and_respects_scope(self):
        vhd.search_command(self.home, "recovery")
        again = vhd.search_command(self.home, "recovery")
        self.assertEqual(again["freshness"]["state"], "throttled")
        self.assertIn("freshness_warning", again["freshness"])
        scoped = vhd.search_command(self.home, "recovery", scope="PROJECTS/Beta")
        self.assertEqual([hit["path"] for hit in scoped["results"]], ["PROJECTS/Beta/notes.md"])

    def test_search_rejects_an_empty_query_and_clamps_the_limit(self):
        with self.assertRaises(vhd.SafetyError):
            vhd.search_command(self.home, " - ")
        with self.assertRaises(vhd.SafetyError):
            vhd.search_command(self.home, "recovery", limit=vhd.SEARCH_LIMIT + 1)
        self.assertEqual(len(vhd.search_command(self.home, "recovery", limit=1)["results"]), 1)

    def test_search_falls_back_to_a_direct_scan_when_the_index_cannot_be_built(self):
        (self.root / "MEMORY" / "CACHE").mkdir(parents=True, exist_ok=True)
        (self.root / vhd.INDEX_NAME).write_text("broken", encoding="utf-8")
        with patch.object(vhd, "index_build", side_effect=vhd.SafetyError("synthetic index failure")):
            result = vhd.search_command(self.home, "recovery")
        self.assertEqual((result["source"], result["freshness"]["state"]), ("scan", "error"))
        self.assertIn("freshness_warning", result["freshness"])
        self.assertGreaterEqual(result["matches"], 1)


class HealTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="vhd-heal-")
        self.base = Path(self.temp.name).resolve()
        self.assertTrue(self.base.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.root = self.base / "home"
        shutil.copytree(SOURCE, self.root, ignore=IGNORE)
        self.home = vhd.Home(self.root)
        self.home.setup()
        self.notes = self.root / "PROJECTS" / "Beta" / "notes.md"
        self.notes.parent.mkdir(parents=True, exist_ok=True)
        self.notes.write_text("the recovery ladder keeps derived state honest\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def write_lock(self, payload):
        area = self.root / ".recycle"
        area.mkdir(exist_ok=True)
        path = area / "operation.lock"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_heal_rebuilds_a_missing_index(self):
        result = vhd.heal(self.home)
        self.assertEqual((result["state"], result["restored_primary"]), ("HEALTHY", False))
        self.assertIn("rebuild", [step["step"] for step in result["steps"]])
        self.assertGreater(result["documents"], 0)
        self.assertTrue((self.root / vhd.INDEX_NAME).is_file())
        self.assertEqual(vhd.health_read(self.home)["state"], "HEALTHY")
        self.assertTrue(result["log"]["logged"])

    def test_heal_reconciles_a_changed_file(self):
        vhd.index_command(self.home)
        self.notes.write_text("changed content about governance\n", encoding="utf-8")
        result = vhd.heal(self.home)
        steps = [step["step"] for step in result["steps"]]
        self.assertEqual(result["state"], "HEALTHY")
        self.assertIn("reconcile", steps)
        self.assertIn("rebuild", steps)
        terms = {term for doc in vhd.index_read(self.home)["documents"] for term in doc.get("terms", {})}
        self.assertIn("governance", terms)

    def test_heal_quarantines_a_stale_lock(self):
        self.write_lock({"schema": 1, "pid": 99999999, "host": vhd.host_mark(), "birth": "1",
                         "token": "synthetic", "created": "2026-11-24T00:00:00+00:00"})
        result = vhd.heal(self.home)
        self.assertEqual((result["state"], result["attempts"]), ("HEALTHY", 2))
        self.assertIn("quarantine-stale-lock", [step["step"] for step in result["steps"]])
        self.assertFalse((self.root / ".recycle" / "operation.lock").exists())

    def test_heal_degrades_on_a_foreign_lock_then_restores_the_primary(self):
        lock = self.write_lock({"schema": 1, "pid": os.getpid(), "host": "another-host", "birth": "1",
                              "token": "synthetic", "created": "2026-11-24T00:00:00+00:00"})
        first = vhd.heal(self.home)
        self.assertEqual(first["state"], "DEGRADED")
        self.assertEqual(first["proposal"]["kind"], "proposal")
        self.assertTrue(lock.is_file())
        self.assertFalse(vhd.heal(self.home)["log"]["logged"])
        lock.unlink()
        second = vhd.heal(self.home)
        self.assertEqual((second["state"], second["restored_primary"]), ("HEALTHY", True))
        self.assertIn("restore-primary", [step["step"] for step in second["steps"]])

    def test_heal_records_a_proposal_after_the_attempt_bound(self):
        with patch.object(vhd, "index_build", side_effect=vhd.SafetyError("synthetic rebuild failure")):
            result = vhd.heal(self.home)
        self.assertEqual((result["state"], result["attempts"]), ("DEGRADED", 2))
        self.assertIn("propose", [step["step"] for step in result["steps"]])
        health = vhd.health_read(self.home)
        self.assertEqual(health["state"], "DEGRADED")
        self.assertEqual(health["proposal"]["kind"], "proposal")
        self.assertFalse((self.root / vhd.INDEX_NAME).is_file())

    def test_doctor_reports_the_cache_and_new_commands(self):
        report = vhd.doctor(self.home)
        self.assertTrue({"index", "search", "heal"} <= set(report["commands"]))
        self.assertFalse(report["cache"]["index"]["present"])
        vhd.heal(self.home)
        self.assertEqual(vhd.doctor(self.home)["cache"]["health"]["state"], "HEALTHY")


if __name__ == "__main__":
    unittest.main()
