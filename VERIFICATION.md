# VHD 0.7.0 verification

Verified on 24 November 2026 on Windows with Python 3.13.14. This is the 0.7.0 integration cycle; every addition is listed in [CHANGELOG.md](CHANGELOG.md).

- **PASS** · 117 local tests, about 119 seconds. The 102 tests from 0.6.0 are unchanged; 13 cover the derived content index, keyword search and the repair ladder, and 2 cover the upgrade manifest and a changed package document.
- **PASS** · `vhd.py index`: 54 documents on a synthetic home, every file hashed once, and a second run hashed none.
- **PASS** · `vhd.py index`: a manual rename was reported as one `renamed` pair with a single rehashed document, and `--full` reported deleted and added paths as drift.
- **PASS** · `vhd.py search`: a two word query returned path, matched words, occurrences, line and a bounded snippet; order is matched words, occurrences, path with ranking off.
- **PASS** · `vhd.py search`: a second call inside the refresh window reported `throttled` with a warning, and `--scope` limited the result to one folder.
- **PASS** · `vhd.py search`: an index that cannot be built falls back to a bounded direct scan and reports `error` with a warning.
- **PASS** · `vhd.py heal`: a missing index was rebuilt and verified in one attempt; a changed file was reconciled and rebuilt; a confirmed stale lock was quarantined.
- **PASS** · `vhd.py heal`: a foreign lock produced `DEGRADED`, a recorded proposal and no lock change, a repeat record was deduplicated, and the next healthy run logged `restore_primary` with exit status 0.
- **PASS** · `vhd.py heal`: two failed rebuilds stop at the attempt bound and leave `DEGRADED` with a proposal; no user file is written.
- **PASS** · `vhd.py doctor`: reports the index and health cache state, and lists `index`, `search` and `heal`.
- **PASS** · `vhd.py upgrade` on a real 0.6.0 archive: 10 stale and 2 new files, 12 written, 10 snapshots, package manifest installed, `restart_required` reported, and `release`, `links`, `routes`, `index`, `heal` and `search` clean afterwards.
- **PASS** · `vhd.py upgrade` refuses the same archive when 0.6.0 applies it with its own tool, which is the documented workaround in [UPDATE.md](UPDATE.md#updating-from-060).
- **PASS** · `vhd.py release --project ..`: 8 checks, 50 manifest files, 0 findings.
- **PASS** · `vhd.py links`: 46 files, 111 references, 0 failed.
- **PASS** · `vhd.py routes`: 6 parts, 0 failed.
- **PASS** · `vhd.py audit`: 50 shipped files, 5 configured private markers, 0 findings.
- **PASS** · `vhd.py method check`: catalog `KNOWLEDGE`, 0 cards, 0 findings.
- **NOT RUN** · Linux and macOS mutation, including the POSIX no-overwrite branch on a real POSIX filesystem. That branch is exercised here through Windows hard links and exclusive directory creation, which is not proof of POSIX semantics.
- **NOT RUN** · A file-only host running standard mode end to end without Python, including manual index and repair steps.
- **NOT RUN** · A live agent session, a real user home, a ZIP update against a real released package, an interrupted upgrade batch during a real write, and a cross-host stale lock.
- **NOT RUN** · Git history scanning, signed package verification, a real third-party license review, and a remote push.

The rules added in 0.4.1 and extended here are read by the agent from Markdown, so no test can prove a model followed them. What the tests prove is that the package still resolves, still routes, still carries no private markers, and that every derived-state command fails closed. `vhd.py release` fails when a version heading, the tool version or a shipped hash drifts.
