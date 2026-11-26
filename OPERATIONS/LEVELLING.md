# Levelling

Use the active or requested owner's `PROGRESSION/EXP.md` under their persona slot. For optional user progress use `MEMORY/USER/PROGRESSION/EXP.md` only at the user's request. Start from the [empty ledger](../TEMPLATES/EXP.md). An owner with a fresh empty ledger starts at level 1 and 0 EXP. Recover a missing used ledger before reporting its stats.

## Scoring

Record evidence in its owning project before recording EXP. Use one stable contribution ID per owner and contribution across retries, chats and hosts. Keep project, primary skill, title, earned date, verification, evidence link and total awarded EXP in the ledger.

Score a completed contribution only when it introduces a capability, method or antipola not yet recorded, or the first application under materially different conditions.

- **0** for routine work, retries, resume, reading or recording alone.
- **0** for applying an already recorded method under the same conditions. A clean result is the expected outcome, not a missing score.
- **0** for environment friction. A renamed path, a moved file or a host quirk is not a learned lesson once a workaround proves clean.
- **1** for verified adaptation of an established method under materially different conditions.
- **2** for a verified new method or capability.
- **3** for a major verified milestone, such as reusable work demonstrated across projects or hosts.

Complexity alone never sets the score. A checklist or tool earns one milestone after its usefulness is verified.

Before saving, look up the ID in the owner's current ledger. If it exists, keep one row and award zero on an equal or lower score. An increase needs fresh evidence, retains earlier evidence, and adds only the difference. Save under one active writer, reopen the ledger, and verify the row and total. A read-only agent reports the proposed row for the user to save. A checkpoint can record the EXP delta even when it is zero.

At closeout of qualifying work, check the evidence, run the [Swiss Knife EXP preview](../TOOLS/README.md#progression) when available, then use `xp-record` to record one milestone under the home lock. The toolbox checks the existing ID and keeps the prior award and evidence if the new submission adds no verified EXP. Preview is arithmetic. Verify the resulting stats after recording. Routine work and equal or lower replays require no ledger edit. User EXP remains opt-in.

A derived `STATUS.json` beside the ledger is optional. `python TOOLS/homestead.py status LEDGER --write` regenerates it and records fingerprints for the ledger, the class catalog and the derivation rules. It is a cache, never a second source of truth, and a changed source makes it stale.

## Milestones and checkpoints

For complex work, give each milestone a stable ID, a usable result and a minimum check. Before starting the next one, save the last verified artifact, the checks that ran, any meaningful failure, and the exact next step. Record token readings only when the host exposes them. Use `UNKNOWN` otherwise. Resume from the latest verified checkpoint.

## Level, classes and titles

Sum awarded EXP once per ID. Level thresholds for levels 1–4 are 0, 5, 12 and 22 EXP. Each level beyond 4 costs another 10 EXP. Cap level at 255 and keep recording earned EXP.

Map each contribution to one primary skill and one class using the [class catalog](../KNOWLEDGE/CLASSES.md). For each class sum its EXP and count distinct scored milestones. Tier 1 requires one milestone. Tier 2 requires 4 class EXP and two milestones. Tier 3 requires 9 class EXP and three milestones. Feature the class with highest class EXP, then milestone count, then ascending class ID. Show a skill as unassessed until it has a scored milestone. Use the ledger and current catalog to answer stats. Levels and titles confer no permissions.

Each scored skill also has its own level on the same scale. Skills with zero verified EXP remain unassessed.

## Status card and cognitive rank

`python TOOLS/homestead.py status LEDGER` derives the progression card from the ledger and the class catalog. `--write` saves it beside the ledger as `STATUS.json`. A changed ledger, catalog or rule set makes the saved card stale; it is a cache, never a second source of truth.

The same card carries four derived ranks under the rule set `cognitive-1`:

| Rank | Derived from | Reaches 100 at |
| --- | --- | --- |
| depth | XP of the strongest class | 20 class XP |
| breadth | skills with a scored milestone | 8 skills |
| application | distinct projects named in the ledger | 5 projects |
| progress | awarded XP toward the next level | the next level |

A score maps to a letter: S at 85, A at 70, B at 55, C at 40, D at 25, E below. Ranks add no EXP, grant no permission and never replace the ledger. They answer one question: where is this owner strong, and where is the record still thin.

## Closing out a change

Order matters: scan, classify, gate, score, handoff, commit.

1. Scan once. `python TOOLS/homestead.py closeout scan` reads the pending paths for the home and sorts them into added, modified, untracked, deleted, renamed, copied, conflict, outside the home, or unparsed.
2. Classify a rename by content. A renamed file whose content hash matches the old blob is a clean rename. Otherwise it is a rename with an edit. Include both paths in a scoped closeout.
3. Respect the gates. A deletion without a recorded rename, an unresolved conflict, a protected path, an unparsed quoted path, or more than seven eligible paths stops automatic closing. Use repeated `--path` options to scope the review and commit to exact task files.
4. Leave generated noise alone: `node_modules`, `_recycle_bin`, `.context_state`, `__pycache__`, `.git`, `.venv`, and names ending in `.tmp`, `.lock` or `~`. A path with a `private` or `archive` segment is protected and never closes automatically.
5. Score only after the evidence exists. Preview with `xp-preview`, record one row per stable ID, and keep a zero delta at zero.
6. Update the handoff line and the touched topic rows, then commit them with the scanned files.
7. Commit last, so a closeout never leaves a commit whose handoff is missing.

`python TOOLS/homestead.py closeout run --message "..."` performs the scan, the classification and the commit in one pass. It writes nothing on a clean scan, and it refuses a gated set unless the file list is explicit.

The shipped `.gitignore` keeps the user areas untracked, so a fresh home closes out package files only. Track the areas you want included, or pass explicit paths from a repository that already tracks them. Ignored files never appear in a scan.

## Experience and growth

Use [experience](../TEMPLATES/EXPERIENCE.md) to link referenced or applied methods, and [growth](../TEMPLATES/GROWTH.md) for durable feedback, lessons and reversible trials. Cite the evidence, outcome and where it applies. Private material stays in its owner's notes. These records inform future work and carry no EXP by themselves. Ask the user before changing canonical identity or permissions.
