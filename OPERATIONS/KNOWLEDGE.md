# Knowledge and reusable methods

Use the [catalog entry point](../KNOWLEDGE/INDEX.md). For recurring or unfamiliar work, find one relevant method by stable ID. Open its canonical card and verify the runtime, conditions and evidence before reusing it. Prefer a proven compatible method. Recheck only material changes, stale evidence or gaps.

Store shared user methods in `MEMORY/KNOWLEDGE/`. Initialize its `INDEX.md` from the [catalog template](../TEMPLATES/KNOWLEDGE_INDEX.md). Make one [method card](../TEMPLATES/METHOD.md) per ID. Links to evidence belong on the card; keep existing history and identify untested ideas clearly. Keep personal experience in its authorized scope.

Before substantial implementation, debugging or refactoring, check a `FAILED` entry on the same topic first, then a successful method. One lookup of the index and at most two cards per task. Name the ID you used in the work plan, or state plainly that nothing matched. A recorded failure is cheaper to read than to repeat, and the catalog is useless if nobody opens it.

## Status and expiry

Every card names one status: `VERIFIED`, `HYPOTHESIS`, `FAILED`, `STALE` or `SUPERSEDED`. A `VERIFIED` card needs evidence another reader can inspect. A `SUPERSEDED` card names the active ID that replaced it and keeps its provenance.

A failed approach uses the same ID space with a `fail.` prefix and the [failure card](../TEMPLATES/FAILURE.md) fields. It must name a replacement or an open question, because a ban without a replacement is superstition. It must also name a recheck trigger. When the named version, dependency or environment changes, the card becomes a candidate `STALE` until rechecked, never a rule to obey forever.

Recording a failure earns no EXP on its own. The verified replacement earns under [Levelling](LEVELLING.md).

An owner can record a method as `referenced` in its [experience record](../TEMPLATES/EXPERIENCE.md). It becomes `applied` when linked to an actual verified milestone for that owner. Record pointers and applicability; leave the method itself in the shared catalog. Referring to or sharing knowledge earns zero EXP. A distinct verified outcome may earn EXP under [Levelling](LEVELLING.md).

## Validation and retrieval

Run `python TOOLS/vhd.py method check` before trusting or adding a card. It reports a missing ID, a duplicate ID, an invalid status, a missing required field, a `fail.` ID without a replacement, and a `SUPERSEDED` card without a target. Read one card with `python TOOLS/vhd.py method show ID`. Both commands are read-only and resolve the local `MEMORY/KNOWLEDGE/` first, then the shipped catalog.
