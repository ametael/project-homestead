# Changelog

One line per change a user can see. Evidence and counts live in [VERIFICATION.md](VERIFICATION.md). Newest version first.

## 1.1.0

- Verify search excerpts against the current Guardian-approved source, retry stale indexed candidates once, and report each excerpt's source SHA-256.
- Reuse complete sources in the same chat with conditional reads, group repeated log lines, and support an optional daily persona rhythm.

## 1.0.0

- All personas can use adaptive reasoning, verified methods and scoped checks for token efficiency.
- Preflight, link checks, lookup and inbox routing can work on the selected files or folder.
- KnowledgeBank keeps public sources with provenance, an opt-in archive route, a bibliography and a per-URL blocklist.
- Optional provider routing checks the exact destination through Guardian. The local privacy check returns redacted results.
- Cashbook exports a user-owned transaction CSV to Excel and can also produce a normalized CSV.
- The public README explains companion portability, selective context and keeping creative choices with the user.
- Guardian requires scoped permission for sensitive file content and keeps it out of search previews.
- Record a verified milestone with `xp-record` and view a derived card with `status --display`.
- Closeout accepts exact task paths for both review and commit.
- The package is renamed Project Homestead: the folder, the helper and every user-facing reference use the new name.
- The user guide and the vision page describe a home for an original character and the assistant that occupies it, opening with a starter character rather than a fixed one.
- `TOOLS/homestead.py` replaces `TOOLS/vhd.py`. An upgrade reports the old helper and leaves it in place for the owner to recycle.
- Home detection accepts a folder that still carries the old helper, so an existing home is found without renaming it first.
- `UPDATE.md` gains the procedure for a home installed under the old folder name.
- The published test suite moves to `tests/test_homestead.py`.

## 0.9.0

- New `OPERATIONS/SOURCES.md` fixes the access rules: a refusal or a paywall stops the attempt, and no mode, flag or stored file weakens that.
- A public archive is allowed only when the owner enables it for that fetch, and the result states that the copy is archived.
- Fetched text is data: invisible characters are stripped, an attempt to steer the reader is reported, and the source URL is marked rather than the whole domain.
- Source assessment stays neutral about the owner: verdicts are per URL, and the owner's own standards supply the threshold.
- `OPERATIONS/KNOWLEDGE.md` adds canonical source identity, one entry per URL, and the criteria for choosing between methods.
- `status` also reports four derived ranks under `cognitive-1` and a project count; ranks award no EXP and grant no permission.
- `OPERATIONS/LEVELLING.md` records a closeout order: scan, classify, gate, score, handoff, commit.
- New `closeout scan` and `closeout run` classify pending changes, apply the gates and commit the eligible set in one pass.
- Generated noise and protected paths stay out of an automatic closeout, and a deletion or a set beyond seven files needs an explicit file list.
- `OPERATIONS/DEVELOPMENT.md` adds lowest sufficient effort, the conditions for delegation, and the rule that a failed approach changes before it repeats.
- `OPERATIONS/CONTINUITY.md` and `FILES_AND_GIT.md` record measuring a handoff before editing and checking references before writing.

## 0.8.1

- The user guide opens with a one-line setup for apps that have a terminal, and a short update procedure.
- `UPDATE.md` gains a release check that works by chat alone or with a terminal, and discloses that the tool itself still makes no network request.

## 0.8.0

- EXP scores only a capability, method or antipola not yet recorded; routine work, clean reapplications and environment friction score zero.
- Closeout of a tracked change records the user-visible changelog line and the checks actually run before the commit.

## 0.7.2

- Adds `VISION.md`, a short page on what the folder holds and who owns it.
- Links that page from the user guide and from the project README.

## 0.7.1

- `.gitattributes` with `* -text` keeps package bytes identical after a clone, so the manifest hashes survive Git on Windows and POSIX.
- The sanitized test suite is published beside the package through `export_extra`, and stays outside the release allowlist.
- `git export`, `verify` and `publish` copy, hash and stage those extra files; a changed test source now fails verification.
- Top-level `tests/` is never treated as package content by the manifest, upgrade or audit scans.
- `VERIFICATION.md` reports clean-package counts, and `README.md` explains `SOURCE.json`.
- `UPDATE.md` records on-demand release update, check and rollback as a deferred 0.8.0 feature over the existing upgrade engine.

## 0.7.0

- `vhd.py index` builds a derived content index in `MEMORY/CACHE/index.json` from UTF-8 text files, hashes only files whose size or timestamp moved, and reports a detected rename when a removed path and a new path share content.
- `vhd.py index --full` rehashes every document and reports drift against the previous index as missing, extra and changed.
- `vhd.py search QUERY` returns path, matched words, occurrences, line and a bounded snippet, ordered by matched words, occurrences and path; adaptive ranking stays off.
- Every search result carries a freshness state and a warning when the list was not checked in that call.
- `vhd.py heal` runs detect, diagnose, repair, verify and restore with two attempts, a 45 second budget and 300 second duplicate suppression.
- Fallback to a bounded direct scan is emergency-only and reported, and a healthy index is restored to the primary path automatically.
- Repair touches derived cache only; package code, Markdown and user files are never rewritten.
- `doctor` reports the index and health cache state, and the command list now includes `index`, `search` and `heal`.
- New `OPERATIONS/RECOVERY.md` owns the repair ladder, fallback, canonical versus derived state and journal rules.
- New `TEMPLATES/RECOVERY.json` is a portable journal for bounded multi-step changes.
- `OPERATIONS/CONTEXT.md` gains the L0 to L4 disclosure table, request-based subset selection and a freshness rule for reused data.
- `OPERATIONS/KNOWLEDGE.md` gains a manual card check without Python and a three step proposal gate.
- `upgrade` installs the package `MANIFEST.json` and reports `manifest_updated`, so a later release check describes the installed package.
- Upgrade snapshots now accept any file listed in the package manifest, not only named core files; 0.6.0 stopped on a changed `CHANGELOG.md`.
- `UPDATE.md` records that workaround for 0.6.0 homes and the manifest behaviour.
- `TOOLS/README.md` gains task subsets, the index and search reference, and the repair reference.
- `TUTORIAL.txt` carries a three-line short version and a current version header; `README.md` states the same setup path in one sentence.

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
