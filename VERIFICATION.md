# Homestead 1.0.0 verification

Verified on 26 November 2026 on Windows with Python 3.13.14. The original rename baseline used a clean package extraction. Every addition is listed in [CHANGELOG.md](CHANGELOG.md).

## Portable tools and adaptive reasoning update

- **PASS** · 146 distinct local tests across the Windows batches and focused regressions. The package-marker check used a synthetic marker in a separate home.
- **PASS** · KnowledgeBank ingested public IANA text over HTTPS and retrieved a readable IANA capture with explicit archive access. Fixtures cover a source refusal, compression limits, deduplication and per-URL blocking.
- **PASS** · The cashbook wrote CSV and XLSX from the same three transactions. The workbook was reopened using the bundled spreadsheet reader and OpenPyXL. Currency totals remained separate and formula-like descriptions remained text.
- **PASS** · Sandbox provider tests enforce permission per endpoint and model, pass the configured Low effort, and stop when delivery is uncertain.
- **NOT RUN** · An authenticated production provider call, live desktop Excel, and a controlled Low versus Medium benchmark.

## Guardian and scoped tools update

- **PASS** · 140 distinct local tests across the Windows test batches and the final regression run. Coverage includes both Guardian modes, approval scope, changed-file approval, image attachments, indexed metadata, same-version upgrade fixtures, EXP recording and exact Git staging. Owner input was simulated in the tests.
- **PASS** · 8 release checks, 54 manifest files, 127 link references, and no audit findings.
- **NOT RUN** · A live model app, a file-only host, a real installed-home upgrade, and macOS or Linux mutation.

## Original rename baseline

- **PASS** · 131 local tests: 122 carried unchanged, 7 for closeout classification, gating and the one-pass commit, and 2 for the legacy helper name in detection and in the upgrade report.
- **PASS** · The package folder, the helper filename and every current-facing document carry the new name. The only remaining references to the old name are the documented upgrade path in `UPDATE.md` and historical changelog entries.
- **PASS** · `home_markers` accepts a home whose helper is still `TOOLS/vhd.py` and reports the `tool` marker with a score of at least 8, so an older folder is found without being renamed.
- **PASS** · `upgrade_package` reports `TOOLS/vhd.py` under `legacy` with a recycle suggestion and leaves the file in place.
- **PASS** · `status` reports `cognitive-1` with depth, breadth, application and progress, and a project count derived from the ledger.
- **PASS** · `closeout scan` and `closeout run` behave as recorded in 0.9.0: clean scan, excluded noise, protected path gate, explicit-list deletion, threshold gate, rename classification and one-pass commit.
- **PASS** · `homestead.py release --project .`: 8 checks, 53 manifest files, 0 findings.
- **PASS** · `homestead.py links` on the clean package: 45 files, 121 references, 0 failed.
- **PASS** · `homestead.py routes`: 6 parts, 0 failed, every startup part under its 4,096-byte limit.
- **PASS** · `homestead.py audit`: 53 shipped files, 0 findings, private markers read from the local configuration.
- **PASS** · `homestead.py doctor` on the clean package: 6 startup parts, 0 failed, 7,232 bytes.
- **NOT RUN** · An upgrade of a real installed home from 0.7.x or 0.8.x to 1.0.0. The legacy report and detection are tested on a synthetic home; a real used home was not carried through the upgrade.
- **NOT RUN** · A closeout in a home that tracks its own data. The shipped `.gitignore` keeps `PERSONA/`, `MEMORY/`, `PROJECTS/`, `ASSETS/` and `ARCHIVE/` untracked, so a fresh home closes out package files only.
- **NOT RUN** · Linux and macOS mutation, a file-only host running standard mode, a live agent session, a live source fetch and any archive retrieval. At that baseline, the package made no network requests.
- **NOT RUN** · A public export or release for 1.0.0, a GitHub repository rename, and a repository description change. Those are publication steps that have not happened.

The Guardian and scoped tools update adds tests for owner decisions, search and preview restrictions, a same-version package update, progression recording, and Git staging boundaries. The host controls access outside the toolbox. `homestead.py release` checks version headings and shipped hashes.