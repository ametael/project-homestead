# Updating this home

Read this when the user hands you a newer Homestead package, a zip, or says "update this home". The package keeps identity, memory and projects. It only compares and replaces package files.

## What the tool does

`python TOOLS/homestead.py upgrade --zip PATH` or `--package PATH` compares three states:

- the manifest stored in `HOME_STATE.json`, which is what this home was installed with
- the files actually present in this home
- the manifest of the incoming package

It prints a plan and writes nothing. `--apply --confirm FINGERPRINT` performs the safe part. The fingerprint comes from the dry run, so a plan that changed after the user read it cannot be applied. The package `MANIFEST.json` is installed with the files and reported as `manifest_updated`, so a later `release` check describes the package that is actually installed.

`--zip PATH` accepts the release archive directly. The tool validates every entry, extracts it into a temporary stage beside the archive, compares, and removes the stage afterwards. Add `--sha256 PATH` with a detached digest file to verify the archive bytes before extraction.

## A home installed under the old folder name

Homes installed before 1.0.0 keep their files in a folder named `VHD/` and run `TOOLS/vhd.py`. Nothing in the upgrade moves or renames that folder. To update one:

1. Extract the new package anywhere outside the home.
2. Run the new helper against the old folder by path: `python PATH/TO/HOMESTEAD/TOOLS/homestead.py --home PATH/TO/VHD upgrade --package PATH/TO/HOMESTEAD`.
3. Read the plan. It reports `TOOLS/vhd.py` under `legacy` as superseded by `TOOLS/homestead.py`.
4. Apply with the fingerprint from the plan.
5. Recycle `TOOLS/vhd.py` yourself after the update works. The tool never deletes it.
6. Renaming the folder to `HOMESTEAD` is optional. Detection reads the files, not the folder name, so a renamed folder keeps working. Rename only after a verified update, and back up first.

## Archive safety

The archive is refused before any write when it contains an absolute or parent path, a duplicate or case-colliding name, an encrypted entry, a link or special entry, an entry over 64 MiB, an entry that expands more than 200 times its compressed size, or a total expansion over 512 MiB. The stage must sit outside the home, and incoming package code is never executed.

A detached digest proves integrity, not who published the archive. A checksum that travels with an untrusted archive establishes nothing by itself, and no signature check exists yet, so say so plainly instead of calling an update authenticated.

## Check for a newer release

The package makes no network request, so either the user or the agent checks, then brings the archive.

Chat only, no terminal. Send this to the agent:

```
Read UPDATE.md from my Homestead home, then check https://api.github.com/repos/ametael/project-vhd/releases/latest and tell me the newest version and whether my home is older.
```

The reply carries `tag_name` as the version and an `assets` list with the ZIP and its `.sha256`. Compare that version with `version` in the home's `MANIFEST.json`. A host without network access reports that it cannot check, and the home stays untouched.

With a terminal, in a temporary folder outside the home:

1. `curl -sL https://api.github.com/repos/ametael/project-vhd/releases/latest` to read the version and asset names.
2. Download the ZIP and the `.sha256` file beside it.
3. Apply with `python TOOLS/homestead.py upgrade --zip PATH --sha256 PATH.sha256`, read the plan, then apply with its fingerprint.

Check releases, not commits. A commit on `main` can be unfinished work, while a release carries a tag, a ZIP and a digest. The digest proves integrity, not who published the archive.

## Steps

1. Find the home. Do not rely on the folder name, because the user may have renamed it.
   - If the user gave a path, use it.
   - Otherwise run `python TOOLS/homestead.py detect --path PATH` and use the single highest score.
   - On a tie or zero, show the top two candidates with their matched markers and ask. Never guess.
   - A folder with `MANIFEST.json` and no `HOME_STATE.json` is a package, not a home.
2. Pass the archive with `--zip`, or extract it into a temporary folder beside the package, never inside the home, and pass that folder to `--package`.
3. Run the dry plan. Read the counts and every entry that is not `new`, `stale`, `local` or `unchanged`.
4. Tell the user in short plain sentences what will change, how many files, and what stays untouched. Ask before writing.
5. Apply with the fingerprint from that exact dry run.
6. Report the written files, whether the tool was replaced, and whether the copied system prompt is now stale.
7. Run `python TOOLS/homestead.py links` and `python TOOLS/homestead.py routes`. Both must pass.

A batch-level lock covers the whole apply, so two upgrades cannot interleave. Before the first write the tool records `.recycle/pending-upgrade.json`, and it removes that record only after the state file is verified. A crash in between leaves the record behind; the next dry run reports it under `interrupted`, and re-running the same package completes the batch because files that already match the package are classed `applied`.

If an operation was interrupted, inspect the lock with `python TOOLS/homestead.py lock`. `python TOOLS/homestead.py lock --recover` quarantines a confirmed stale lock into `.recycle/locks/` with a record. A foreign host, a legacy record, a missing birth mark or a reused PID stays `unknown` and is refused. Age alone never proves staleness.

## Classes

| Class | Meaning | Action |
| --- | --- | --- |
| `new` | The package adds a file | Written |
| `stale` | Unchanged locally, changed upstream | Snapshot, then written |
| `applied` | The home already holds the package bytes from an earlier partial run | Skipped, then the state file is finalized |
| `local` | Changed locally, unchanged upstream | Left alone |
| `unchanged` | Identical on both sides | Skipped |
| `conflict` | Changed on both sides | Ask the user |
| `relocated` | The same content exists under another path | Ask the user |
| `deleted-locally` | The user removed a file the package still ships | Ask, do not restore silently |
| `dropped` | The package no longer ships a file that exists here | Leave it, offer recycle |
| `refused` | A manifest entry points into user territory | Never written |

## Explaining a conflict

Give the path, what the user has, what the package has, one recommendation with its reason and risk, and three choices: keep theirs, take the package, or keep both with one version moved to an appendix.

Compare tools on the same axes before recommending: input handling, failure reporting, effect on user files, dependencies, and test evidence. Say what the weaker one still does better. A recommendation without that comparison is a guess.

When the user keeps their version on purpose, record that decision in `HOME_STATE.json` under `retained` so the next update does not ask again.

## Never written

`PERSONA/`, `MEMORY/`, `PROJECTS/`, `ASSETS/`, `ARCHIVE/` and `HOME_STATE.json` through the upgrade command. Those hold identity, records and evidence. If the package manifest lists one of them, the entry is refused and reported.

## Degraded mode

Without `HOME_STATE.json` there is no baseline, so no local edit can be told apart from an untouched file. Every existing package file becomes a conflict with the recommendation to take the package. Say so plainly, then let the user choose per file or take all.

## After the update

- `restart_required` means `TOOLS/homestead.py` changed. Start a new command before relying on the new behaviour.
- `manifest_updated` means the package manifest was replaced. `release` compares against it afterwards.
- `host_prompt_stale` means `sysprompt_to_copy.txt` changed. A system prompt already pasted into an application is outside this folder. Show the new text and ask the user to replace it.
- Snapshots of replaced files are listed in the result and can be restored with `vhd.py plan restore --id ID`.
- A migration listed in the package manifest blocks the apply. Print the step and wait; no incoming code is run automatically.

## Updating from 0.6.0

0.6.0 snapshots a changed file only when it is a named core document or sits under a core folder, so a changed `CHANGELOG.md` stops its own apply. Run the newer tool against the older home instead of the home's current tool:

```text
python PATH/TO/HOMESTEAD_1.0.0/TOOLS/homestead.py --home PATH/TO/HOME upgrade --zip PATH/TO/HOMESTEAD_1.0.0.zip --sha256 PATH/TO/HOMESTEAD_1.0.0.zip.sha256
python PATH/TO/HOMESTEAD_1.0.0/TOOLS/homestead.py --home PATH/TO/HOME upgrade --zip PATH/TO/HOMESTEAD_1.0.0.zip --apply --confirm FINGERPRINT
```

0.6.0 also left the previous package manifest in place after an update; 0.7.0 installs it. Upgrades from 0.7.0 onward need no workaround.

## Deferred: checks inside the tool

The check above is a documented procedure for the agent, not a command. The tool still makes no network request, and a package still arrives only when the user or the agent brings it.

A `vhd.py update --check` and `--fetch` remain unimplemented:

1. Check: an explicit command asks the release list for the newest version, prints version, notes link, asset name and digest, and writes nothing.
2. Update: on request, download the release ZIP and digest into a temporary folder outside the home, verify the digest, then run the existing `upgrade --zip` plan. The same plan, fingerprint, snapshot and batch lock apply unchanged.
3. Rollback: list the snapshots recorded by the applied batch and offer the existing `plan restore` for one file or the whole batch. No new recovery path is introduced.
4. Offline default: the check is opt-in, refuses without a configured source, and reports an unavailable network as a skipped check, never as an error in the home.

Open questions before implementation: which release host and API shape to trust, whether a signature should replace a checksum, and how a home without Git records the applied version. A migration listed in the package keeps blocking the apply until the user handles it.

## Limits

- Prose is never merged automatically.
- A dropped file is never deleted by the tool.
- A ledger is evidence, so its format changes are manual.
- A home without a state file cannot prove which edits are local.
