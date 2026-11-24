# Levelling

Use the active or requested owner's `PROGRESSION/EXP.md` under their persona slot. For optional user progress use `MEMORY/USER/PROGRESSION/EXP.md` only at the user's request. Start from the [empty ledger](../TEMPLATES/EXP.md). An owner with a fresh empty ledger starts at level 1 and 0 EXP. Recover a missing used ledger before reporting its stats.

## Scoring

Record evidence in its owning project before recording EXP. Use one stable contribution ID per owner and contribution across retries, chats and hosts. Keep project, primary skill, title, earned date, verification, evidence link and total awarded EXP in the ledger.

- **0** for routine work, retries, resume, reading or recording alone.
- **1** for verified adaptation of an established method.
- **2** for a verified new method or capability.
- **3** for a major verified milestone.

Before saving, look up the ID in the owner's current ledger. If it exists, keep one row and award zero on an equal or lower score. An increase needs fresh evidence, retains earlier evidence, and adds only the difference. Save under one active writer, reopen the ledger, and verify the row and total. A read-only agent reports the proposed row for the user to save. A checkpoint can record the EXP delta even when it is zero.

At closeout of qualifying work, check the evidence, run the [Swiss Knife EXP preview](../TOOLS/README.md#progression) when available, and save the owner's updated Markdown ledger with the guarded write command. Preview is arithmetic. Verify the resulting stats after recording. Routine work and equal or lower replays require no ledger edit. User EXP remains opt-in.

A derived `STATUS.json` beside the ledger is optional. `python TOOLS/vhd.py status LEDGER --write` regenerates it and records fingerprints for the ledger, the class catalog and the derivation rules. It is a cache, never a second source of truth, and a changed source makes it stale.

## Level, classes and titles

Sum awarded EXP once per ID. Level thresholds for levels 1–4 are 0, 5, 12 and 22 EXP. Each level beyond 4 costs another 10 EXP. Cap level at 255 and keep recording earned EXP.

Map each contribution to one primary skill and one class using the [class catalog](../KNOWLEDGE/CLASSES.md). For each class sum its EXP and count distinct scored milestones. Tier 1 requires one milestone. Tier 2 requires 4 class EXP and two milestones. Tier 3 requires 9 class EXP and three milestones. Feature the class with highest class EXP, then milestone count, then ascending class ID. Show a skill as unassessed until it has a scored milestone. Use the ledger and current catalog to answer stats. Levels and titles confer no permissions.

## Experience and growth

Use [experience](../TEMPLATES/EXPERIENCE.md) to link referenced or applied methods, and [growth](../TEMPLATES/GROWTH.md) for durable feedback, lessons and reversible trials. Cite the evidence, outcome and where it applies. Private material stays in its owner's notes. These records inform future work and carry no EXP by themselves. Ask the user before changing canonical identity or permissions.
