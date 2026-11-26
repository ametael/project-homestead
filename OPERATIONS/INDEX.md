# Operations index

Every rule module in this folder, owned by the package. Local rules belong in `MEMORY/`, because an update replaces this folder.

| Module | Use when |
| --- | --- |
| [Adaptive reasoning](REASONING.md) | Choosing effort, evidence and checks for a task |
| [Context](CONTEXT.md) | Deciding what to read, how much, and when to stop |
| [Continuity](CONTINUITY.md) | Closing out a milestone, resuming a session, keeping pointers current |
| [Development](DEVELOPMENT.md) | Building, changing or reviewing code |
| [Files and Git](FILES_AND_GIT.md) | Writing, archiving, recycling, committing |
| [KnowledgeBank](KNOWLEDGEBANK.md) | Finding and keeping cited web and archive sources |
| [Cashbook](CASHBOOK.md) | Exporting a user-owned transaction log to Excel |
| [Provider routing](PROVIDERS.md) | Sending an explicitly authorized model request |
| [Knowledge](KNOWLEDGE.md) | Recording or reusing a method card |
| [Levelling](LEVELLING.md) | Scoring EXP, classes, tiers and titles |
| [Memory](MEMORY.md) | Recording durable facts, keeping privacy boundaries, reading an inbox |
| [Personas](PERSONAS.md) | Selecting an owner, adding one, handing work over |
| [Recovery](RECOVERY.md) | Repairing derived state, rebuilding an index, resuming a scoped change |
| [Guardian](GUARDIAN.md) | Opening or sharing sensitive images and text |
| [Sources](SOURCES.md) | Reading a page, an archive, an API or pasted text, and judging what it says |
| [Runtime](RUNTIME.md) | Running the optional deterministic queue, budgets and emergency stop |

Check the package with `python TOOLS/homestead.py routes` after editing this index or `ROUTES.json`.
