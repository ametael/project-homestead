# Changelog

One line per change. Newest version first.

## 0.6.0

- Optional Smart Git interface: `git status`, `checkpoint`, `export`, `verify` and `publish`.
- The public export copies only the manifest allowlist and excludes persona, memory, projects and recovery data.
- Export refuses a package that already has release findings; verify fails closed on an extra file, a private marker or a release finding.
- Publish binds to the verified export fingerprint, keeps independent history and never pushes or rewrites history.

## 0.5.1

- Restored the complete default Vee identity in `TEMPLATES/IDENTITY.md`; 0.2.0 through 0.5.0 shipped a blank form.
- `release` now rejects a package whose default persona template is missing, too small, or lacks name, voice, role and continuity.
- Fresh `init` and file-only setup start from the restored template, and still never overwrite a customized identity.

## 0.5.0

- `vhd.py release` checks the manifest version against the tool version, README, verification header, newest changelog heading and shipped file hashes.
- `vhd.py release --project` compares project-level README and handoff versions; `--compare` byte-checks a prepared release folder.
- `vhd.py doctor` reports runtime, modes, startup bytes, manifest size drift, state validity and lock presence without writing.
- `vhd.py method check` validates card IDs, statuses, required fields, failure replacements and superseded targets.
- `vhd.py method show ID` returns one bounded card for selective retrieval.
- `vhd.py status` derives a compact `STATUS.json` with ledger, catalog and rule fingerprints and reports staleness.
- `vhd.py lock` reports absent, live, stale or unknown from host, PID and process birth mark; `--recover` quarantines only a confirmed stale owner.
- The upgrade apply now holds one batch lock, writes a pending record before the first write and clears it after state verification.
- A partially applied upgrade classifies finished files as `applied`, so the same package can be re-run to completion.
- Portable no-overwrite moves: Windows keeps atomic rename; POSIX uses exclusive hard link and unlink for files, and exclusive directory creation with per-child moves.
- File mutation is no longer gated to one platform; a single guard reports an unsupported platform instead of a Windows check.
- Platform claims match the evidence: Windows is tested, Linux and macOS are NOT RUN.
- `vhd.py upgrade --zip` validates and stages a release archive directly, with duplicate, traversal, link, encryption, size and expansion checks.
- `--sha256` verifies a detached digest and reports integrity separately from publisher authenticity.
- A package that lists migrations now blocks the apply instead of doing nothing silently.
- `doctor` reports available, requested and selected mode with warnings, and accepts `--mode auto|standard|enhanced`.
- `MEMORY/CONFIG.json` is the user-owned place to pin a mode without touching package files.
- The startup entry and user guide document standard and enhanced modes over one workspace.
- New `DISCLAIMER.md` with a short visible notice and link in the user guide.
- `SYSTEM/POLICIES/EULA.md` is the third-party license briefing, loaded only when a license question appears.
- `license_compliance` defaults to true in `MEMORY/CONFIG.json`; disabling it adds one warning and grants no rights.
- `vhd.py audit` scans shipped files or a release folder for private keys, credentials, absolute paths, environment files and runtime artifacts, with redacted findings.
- Private markers are user-configured, so the package never ships private names.
- Optional deterministic runtime with a stable-ID queue, dedupe, fixed budget, bounded retries and emergency stop.
- An inference task is blocked without a provider adapter, so no request or paid call occurs.
- Runtime state, events and the stop flag stay in `MEMORY/RUNTIME/`, and the runtime is off by default.
- Project README version matches the package again, and `DESIGN.md` structure and exclusions match the shipped home.
- Master implementation plan and phase state recorded in `PROGRESS/0008-implementation-master.md`.

## 0.4.1

- A card carries one status: `VERIFIED`, `HYPOTHESIS`, `FAILED`, `STALE` or `SUPERSEDED`.
- New `TEMPLATES/FAILURE.md` records what was tried, what was assumed, what happened, and why.
- A failure card must name a replacement or an open question, so no bare ban is accepted.
- A failure card must name the version, dependency or environment change that invalidates it.
- Development and knowledge rules tell the agent to read a `FAILED` card before a successful one.
- Recording a failure earns no EXP; the verified replacement does.
- The knowledge index names both card kinds and the status values.

## 0.4.0

- Package manifest with a hash, a kind and a size for every shipped file.
- Home state file recording the installed version, a copy of its manifest and choices the user keeps on purpose.
- `vhd.py upgrade` comparing the installed base, the current home and the incoming package three ways.
- Apply requires the fingerprint printed by the dry run, so a plan that changed after review cannot be written.
- Every replaced file is snapshotted into `ARCHIVE` before it is overwritten.
- Entries that point into `PERSONA`, `MEMORY`, `PROJECTS`, `ASSETS` or `ARCHIVE` are refused, never written.
- A package older than the home is refused before any write.
- Degraded mode for a home without a state file: existing package files become conflicts instead of silent replacements.
- Content found at another path by hash is reported as relocated, so a renamed file or folder is not duplicated.
- `vhd.py links` checks every Markdown target and heading across the home.
- `vhd.py routes` checks the startup parts in `ROUTES.json` for missing files, oversized parts and duplicate entries.
- `vhd.py detect` scores candidate homes by markers, so a renamed home folder is still found.
- `vhd.py manifest` rebuilds the package manifest for a release.
- `OPERATIONS/INDEX.md` gives the package one owned pointer file, so adding a module no longer patches a file the user may have edited.
- `UPDATE.md` lets an agent update a home from a bare zip without guessing.
- Shipped text stays English only, with no personal markers.
