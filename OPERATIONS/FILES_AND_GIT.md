# Files, archives, and Git

Verify the exact target and authorization before changing files. Preserve unrelated work, hidden/ignored data, and existing history. No destructive shell cleanup, permanent deletion, bulk wildcard removal, or automatic expiry.

Use [Swiss Knife write](../TOOLS/README.md#writing-one-file) for ordinary requested text edits and authorized continuity records. A clear user request authorizes the routine edits it requires. Use the [recovery helper](../TOOLS/README.md#recovery) for other operations. Preview exact targets, then apply within the authorized scope.

Before updating existing content, snapshot and verify the affected prior version into ARCHIVE. Swiss Knife write does this automatically. For a file/folder replacement from a prepared file or folder, use an archive-first update plan. Snapshot first before native-editor changes as well. Stop if capture fails or the source drifts.

For removal use recycle or archive moves. Archive deliberately retained versions; recycle material removed from active use. Both retain recovery records and have no automatic expiry. Backtracking over active work first requires retaining that current version. Never force a restore collision.

Protected core files may only be snapshotted/updated/restored as exact files with explicit core-edit intent and `--allow-core`. Ordinary cleanup cannot remove core, data roots, tool sources, Git metadata, or retention stores. Folders containing Git metadata are refused; use project version control and scoped source snapshots instead.

If interrupted, inspect the operation record and actual payload/target state. Preserve both copies when uncertain. Do not blindly retry an applied plan or clear a stale lock; use `lock` to inspect and `lock --recover` only for a confirmed stale owner. A same-drive archive is not an independent backup.

The helper cannot intercept arbitrary editor/terminal actions. Follow host restrictions for hard enforcement. Do not bypass a refusal by using another command.

Git is optional. Check scoped status, preserve existing staging, stage exact intended files, honor hooks, and make one coherent commit when authorized. Do not initialize a project repository, push, amend, reset, rewrite history, or include private runtime data automatically. A commit does not cover ignored files.

At closeout update [continuity](CONTINUITY.md) before committing. Backups, checkpoints, and handoffs stay local unless the user authorizes sharing.

Run the reference and route checks before writing, not only after, so a broken link is found while the change is still cheap to adjust. When a repeated text edit fails on the same content, change the matching method or the tool instead of repeating it.
