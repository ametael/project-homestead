# VHD 0.6.0 verification

Verified on 23 and 24 November 2026 on Windows with Python 3.13.14. This is the 0.5.0 implementation cycle; every addition is listed in [CHANGELOG.md](CHANGELOG.md).

- **PASS** · 102 local tests, 2 minutes. The 55 original tests are unchanged; three cover `release`, five cover `doctor`, modes and license preference, five cover `method` and `status`, seven cover lock inspection, quarantine and upgrade recovery, four cover portable moves, six cover archive validation, ZIP updates and persona preservation, three cover the release audit, six cover the optional runtime, two cover the default persona, and six cover Smart Git.
- **PASS** · `vhd.py method check`: catalog `KNOWLEDGE`, 0 cards, 0 findings.
- **PASS** · `vhd.py lock`: `absent` on a clean home; a legacy or foreign lock reports `unknown` and is refused.
- **PASS** · `vhd.py doctor`: 6 startup parts, standard and enhanced available, autonomous off, and mode selection follows the config or `--mode` flag.
- **PASS** · `vhd.py release --project ..`: 8 checks, 48 manifest files, 0 findings.
- **PASS** · `vhd.py links`: 45 files, 100 references, 0 failed.
- **PASS** · `vhd.py routes`: 4 required parts present, 1 optional present, 1 optional absent, 0 failed.
- **PASS** · `vhd.py release` rejects a package whose default persona template is blank or incomplete.
- **PASS** · `vhd.py git export` and `verify`: the export carries the complete Vee, excludes persona and memory, refuses an extra file, and passes release and audit checks.
- **PASS** · `vhd.py git publish`: independent repository, two preserved commits, no remote, no push, and a fingerprint gate.
- **PASS** · `vhd.py audit`: 48 shipped files, 5 configured private markers, 0 findings.
- **PASS** · `vhd.py runtime`: stopped by default, deduplicating add, two deterministic tasks done in one bounded run, inference blocked, and the stop flag refusing a later run.
- **PASS** · `vhd.py manifest --write`: 48 files recorded with sizes and SHA-256 hashes.
- **NOT RUN** · Linux and macOS mutation, including the POSIX no-overwrite branch on a real POSIX filesystem. That branch is exercised here through Windows hard links and exclusive directory creation, which is not proof of POSIX semantics.
- **NOT RUN** · A file-only host running standard mode end to end without Python.
- **NOT RUN** · A live agent session, a real user home, a ZIP update against a real released package, an interrupted upgrade batch during a real write, and a cross-host stale lock.
- **NOT RUN** · Git history scanning, signed package verification, a real third-party license review, and a remote push.

The rules added in 0.4.1 are read by the agent from Markdown, so no test can prove a model followed them. What the tests prove is that the package still resolves, still routes, and still carries no private markers. `vhd.py release` now fails when a version heading, the tool version or a shipped hash drifts.
