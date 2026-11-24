# Recovery and repair

Derived state can be rebuilt. Canonical state cannot. The cache under `MEMORY/CACHE/` is derived from the Markdown and JSON files, so a damaged cache costs time, never content.

## Ladder

Detect, diagnose, repair, verify, restore the primary path. `python TOOLS/vhd.py heal` runs the ladder in order and stops at the first usable result.

| Step | Action | Bound |
| --- | --- | --- |
| H0 detect | Inspect the home lock, the stored index and the health record | read-only |
| H1 diagnose | Read the index; absent, foreign or corrupt is a named state, not a guess | read-only |
| H2 repair | Quarantine a confirmed stale lock, then reconcile only drift the files themselves show | two attempts |
| H3 rebuild | Rebuild the index from the canonical files | 45 seconds |
| H4 verify | Parse the rebuilt index and require at least one document | two attempts |
| H5 propose | Record a proposal for a human when repair fails | no code change |
| H6 restore | Return to the primary path and log `restore_primary` once the index verifies | automatic |

Repair means recreating derived data and moving a lock that its own owner already left behind. A live or foreign lock is reported and left untouched. The ladder never rewrites package code, never edits Markdown and never deletes a user file.

## Fallback

The local index is the primary path. A bounded direct scan is the emergency fallback: it runs only when the index cannot be used, and it reports `freshness.state` `error` or `unindexed` with a warning. An active fallback is always visible in the result. Adaptive ranking stays off because no measured gain justifies the extra ordering rule.

## Canonical and derived

| Derived, rebuildable | Canonical, never auto-repaired |
| --- | --- |
| `MEMORY/CACHE/index.json` | `PERSONA/`, `MEMORY/` notes, `PROJECTS/` |
| `MEMORY/CACHE/health.json` | Markdown rules under `OPERATIONS/` |
| `MEMORY/CACHE/selfheal.jsonl` | `TOOLS/vhd.py` |
| `MEMORY/RUNTIME/` records | Archive and recycle payloads |

Derived files are local runtime data. Git ignores them, no release carries them, and nothing else depends on their survival.

## Recovery journal

For multi-step work, keep one portable journal from the [journal template](../TEMPLATES/RECOVERY.json). It records one operation per bounded step, with the files touched, the scoped backup, the evidence and the next action. A journal is a plan and a receipt, not proof of approval.

- Back up only the affected originals, on the same drive, with a manifest of bytes and hashes.
- Never copy a whole workspace or a parent folder as a backup.
- Write one checkpoint per verified operation before the next operation starts.
- A failed operation names its cause and its way back; it never claims success.
- Keep the journal with the work and link it from the checkpoint.

## Standard mode

Without Python there is no automatic rebuild. Read the index and health record, or ignore both and work from the Markdown. Removing a derived cache by hand needs the user's authorization and loses only speed; nothing in the home depends on the cache being present.

## Limits

- A rebuild is only as good as the files it reads. It cannot recover deleted content.
- The index covers UTF-8 text up to 256 KiB per file and skips private folders by name.
- The health record reports the last repair, not the condition of the machine.
- No timer runs in the background. Repair happens when a command needs it.
