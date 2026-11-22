# Progress and continuity

For complex work, give each milestone a stable ID, an owner, a usable outcome and a verification criterion. Check that there is enough context and time to finish and verify the next milestone. When low or uncertain, record an exact resume point before opening more work.

For each meaningful milestone or interruption, carry out the applicable closeout in the same session. Do not wait for the user to request an ordinary checkpoint:

1. Create a distinct [checkpoint](../TEMPLATES/PROGRESS.md) under the owning project's `PROGRESS/`. Record the last verified artifact, results and evidence, relevant decisions, and the next action. Use `UNKNOWN` for unavailable token readings, and record the reading type and time when present.
2. Score a distinct verified contribution only if it qualifies under [Levelling](LEVELLING.md). Record the EXP delta once. An interruption, duplicate checkpoint or retry earns zero on its own.
3. Verify checkpoint links. Use the [Swiss Knife](../TOOLS/README.md#writing-one-file) to snapshot and update the relevant handoffs, or follow [Files and Git](FILES_AND_GIT.md) when using native tools. Point the project handoff at the checkpoint. Keep the topic route in the owner handoff and, for shared work, the home handoff. The home handoff is a small routing table and one latest pointer.

Keep prior checkpoints. Correct them with linked entries. Preserve private boundaries when routing evidence. Use one active writer for the same files and coordinate handoff before another session edits them.

On resume, load the current identity, then the home and selected owner handoffs. Follow the matching route to the project handoff, its current checkpoint and the owning artifacts. Prefer an explicit current user direction when it conflicts with a stored next action. A stale or missing pointer needs focused recovery from the owning project. Check actual artifacts and rerun only checks invalidated by the interruption or new evidence. A new model or application needs access to the same current, authorized files.
