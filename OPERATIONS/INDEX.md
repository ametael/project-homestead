# Operations index

Every rule module in this folder, owned by the package. Local rules belong in `MEMORY/`, because an update replaces this folder.

| Module | Use when |
| --- | --- |
| [Context](CONTEXT.md) | Deciding what to read, how much, and when to stop |
| [Continuity](CONTINUITY.md) | Closing out a milestone, resuming a session, keeping pointers current |
| [Development](DEVELOPMENT.md) | Building, changing or reviewing code |
| [Files and Git](FILES_AND_GIT.md) | Writing, archiving, recycling, committing |
| [Knowledge](KNOWLEDGE.md) | Recording or reusing a method card |
| [Levelling](LEVELLING.md) | Scoring EXP, classes, tiers and titles |
| [Memory](MEMORY.md) | Recording durable facts, keeping privacy boundaries, reading an inbox |
| [Personas](PERSONAS.md) | Selecting an owner, adding one, handing work over |
| [Runtime](RUNTIME.md) | Running the optional deterministic queue, budgets and emergency stop |

Check the package with `python TOOLS/vhd.py routes` after editing this index or `ROUTES.json`.
