# Updating this home

Read this when the user hands you a newer VHD package, a zip, or says "update this home". The package keeps identity, memory and projects. It only compares and replaces package files.

## What the tool does

`python TOOLS/vhd.py upgrade --zip PATH` or `--package PATH` compares three states:

- the manifest stored in `HOME_STATE.json`, which is what this home was installed with
- the files actually present in this home
- the manifest of the incoming package

It prints a plan and writes nothing. `--apply --confirm FINGERPRINT` performs the safe part. The fingerprint comes from the dry run, so a plan that changed after the user read it cannot be applied.

`--zip PATH` accepts the release archive directly. The tool validates every entry, extracts it into a temporary stage beside the archive, compares, and removes the stage afterwards. Add `--sha256 PATH` with a detached digest file to verify the archive bytes before extraction.

## Archive safety

The archive is refused before any write when it contains an absolute or parent path, a duplicate or case-colliding name, an encrypted entry, a link or special entry, an entry over 64 MiB, an entry that expands more than 200 times its compressed size, or a total expansion over 512 MiB. The stage must sit outside the home, and incoming package code is never executed.

A detached digest proves integrity, not who published the archive. A checksum that travels with an untrusted archive establishes nothing by itself, and no signature check exists yet, so say so plainly instead of calling an update authenticated.

## Steps

1. Find the home. Do not rely on the folder name, because the user may have renamed it.
   - If the user gave a path, use it.
   - Otherwise run `python TOOLS/vhd.py detect --path PATH` and use the single highest score.
   - On a tie or zero, show the top two candidates with their matched markers and ask. Never guess.
   - A folder with `MANIFEST.json` and no `HOME_STATE.json` is a package, not a home.
2. Pass the archive with `--zip`, or extract it into a temporary folder beside the package, never inside the home, and pass that folder to `--package`.
3. Run the dry plan. Read the counts and every entry that is not `new`, `stale`, `local` or `unchanged`.
4. Tell the user in short plain sentences what will change, how many files, and what stays untouched. Ask before writing.
5. Apply with the fingerprint from that exact dry run.
6. Report the written files, whether the tool was replaced, and whether the copied system prompt is now stale.
7. Run `python TOOLS/vhd.py links` and `python TOOLS/vhd.py routes`. Both must pass.

A batch-level lock covers the whole apply, so two upgrades cannot interleave. Before the first write the tool records `.recycle/pending-upgrade.json`, and it removes that record only after the state file is verified. A crash in between leaves the record behind; the next dry run reports it under `interrupted`, and re-running the same package completes the batch because files that already match the package are classed `applied`.

If an operation was interrupted, inspect the lock with `python TOOLS/vhd.py lock`. `python TOOLS/vhd.py lock --recover` quarantines a confirmed stale lock into `.recycle/locks/` with a record. A foreign host, a legacy record, a missing birth mark or a reused PID stays `unknown` and is refused. Age alone never proves staleness.

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

- `restart_required` means `TOOLS/vhd.py` changed. Start a new command before relying on the new behaviour.
- `host_prompt_stale` means `sysprompt_to_copy.txt` changed. A system prompt already pasted into an application is outside this folder. Show the new text and ask the user to replace it.
- Snapshots of replaced files are listed in the result and can be restored with `vhd.py plan restore --id ID`.
- A migration listed in the package manifest blocks the apply. Print the step and wait; no incoming code is run automatically.

## Limits

- Prose is never merged automatically.
- A dropped file is never deleted by the tool.
- A ledger is evidence, so its format changes are manual.
- A home without a state file cannot prove which edits are local.
