# VHD 0.8.1 verification

Verified on 25 November 2026 on Windows with Python 3.13.14. Counts below come from a clean package extraction, not a working home. Every addition is listed in [CHANGELOG.md](CHANGELOG.md).

- **PASS** · 122 local tests: 102 from 0.6.0 unchanged, 13 for the content index, search and repair ladder, 2 for the upgrade manifest and a changed package document, and 5 for the published test suite, its hashes and the line-ending rule.
- **PASS** · `.gitattributes` ships `* -text` and is part of the manifest, so a clone keeps the exact bytes the manifest records.
- **PASS** · A clean Windows clone with `core.autocrlf=true` reports `release` PASS with no changed file, while the same clone without the rule reports 40 or more changed files.
- **PASS** · The published suite runs from a clean clone: `python -m unittest discover -s tests -p test_vhd.py` reports 122 tests OK, with the package found at the repository root and one check skipping itself when no local marker list exists.
- **PASS** · `git export` copies the extra test file, records its hash in `SOURCE.json`, and `git verify` fails when that source changes or an unrecorded copy appears.
- **PASS** · `git publish` stages only the extras the export actually recorded, and top-level `tests/` is never treated as package content by `manifest`, `upgrade` or `audit`.
- **PASS** · `vhd.py index`: 54 documents on a synthetic home, every file hashed once, and a second run hashed none.
- **PASS** · `vhd.py index`: a manual rename was reported as one `renamed` pair with a single rehashed document, and `--full` reported deleted and added paths as drift.
- **PASS** · `vhd.py search`: a query returned path, matched words, occurrences, line and a bounded snippet; order is matched words, occurrences, path with ranking off.
- **PASS** · `vhd.py search`: a second call inside the refresh window reported `throttled` with a warning, and `--scope` limited the result to one folder.
- **PASS** · `vhd.py search`: an index that cannot be built falls back to a bounded direct scan and reports `error` with a warning.
- **PASS** · `vhd.py heal`: a missing index was rebuilt and verified; a changed file was reconciled and rebuilt; a confirmed stale lock was quarantined.
- **PASS** · `vhd.py heal`: a foreign lock produced `DEGRADED`, a recorded proposal and no lock change, a repeat record was deduplicated, and the next healthy run logged `restore_primary` with exit status 0.
- **PASS** · `vhd.py heal`: two failed rebuilds stop at the attempt bound and leave `DEGRADED` with a proposal; no user file is written.
- **PASS** · `vhd.py upgrade` on a real 0.6.0 archive: 10 stale and 2 new files, 12 written, 10 snapshots, package manifest installed, `restart_required` reported, and `release`, `links`, `routes`, `index`, `heal` and `search` clean afterwards.
- **PASS** · `vhd.py release --project ..`: 8 checks, 52 manifest files, 0 findings.
- **PASS** · `vhd.py links` on the clean package: 44 files, 113 references, 0 failed.
- **PASS** · `vhd.py routes`: 6 parts, 0 failed.
- **PASS** · `vhd.py audit`: 52 shipped files, 0 findings, private markers read from the local configuration.
- **PASS** · `vhd.py method check`: 0 cards, 0 findings.
- **PASS** · `vhd.py doctor` on the clean package: 6 startup parts, 0 failed, 7,028 bytes.
- **NOT RUN** · Linux and macOS mutation, including the POSIX no-overwrite branch on a real POSIX filesystem. That branch is exercised here through Windows hard links and exclusive directory creation, which is not proof of POSIX semantics.
- **NOT RUN** · A file-only host running standard mode end to end without Python, including manual index and repair steps.
- **NOT RUN** · A live agent session, a real user home, and a cross-host stale lock.
- **NOT RUN** · Git history scanning, signed package verification, a real third-party license review, and a remote push from this package.

The rules are read by the agent from Markdown, so no test can prove a model followed them. What the tests prove is that the package still resolves, still routes, still carries no private markers, and that every derived-state command fails closed. `vhd.py release` fails when a version heading, the tool version or a shipped hash drifts.
