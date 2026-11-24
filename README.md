# Virtual Home DIY

Virtual Home DIY 0.7.1 is a Markdown workspace for your AI partner. Open this folder in an agent application with local file access and say “Use Swiss Knife to read START_HERE.md, set up this home and start as Vee.” [Copyable instructions](sysprompt_to_copy.txt) work when the app needs an explicit prompt. The [quick tutorial](TUTORIAL.txt) includes a Cherry Studio example.

## Setup

Short version: extract the package into a folder you keep, open that folder as your agent's working folder, and point the system prompt at [sysprompt_to_copy.txt](sysprompt_to_copy.txt). Step 1 below covers the same setup in detail.

1. On a fresh home, copy the [Vee identity template](TEMPLATES/IDENTITY.md) to `PERSONA/IDENTITY.md`, [owner handoff](TEMPLATES/OWNER_HANDOFF.md) to `PERSONA/HANDOFF.md`, [EXP ledger](TEMPLATES/EXP.md) to `PERSONA/PROGRESSION/EXP.md`, [memory index](TEMPLATES/MEMORY_INDEX.md) to `MEMORY/INDEX.md`, and [home handoff](TEMPLATES/HOME_HANDOFF.md) to `MEMORY/HANDOFF.md`. Create parent folders as needed. Copy only missing files. On a used home, recover missing identity and handoffs from a verified copy.
2. Keep Vee or choose a name, voice and focus together. Leave personal history blank until you provide facts you want to save.
3. Speak naturally and give the agent a task. It selects task-specific procedures from the [context map](CONTEXT_MAP.md).

With terminal access and Python 3.13+, Vee uses the [Swiss Knife](TOOLS/README.md#agent-workflow) for file work and progression. It also uses the CLI to initialize the home and write text files with verified snapshots on Windows and POSIX hosts. Windows behaviour is tested here; Linux and macOS are NOT RUN. Check version and package consistency with `python TOOLS/vhd.py release`. The [Markdown route](START_HERE.md) works with native file tools when these commands are unavailable.

To update an older home, back it up or let `python TOOLS/vhd.py upgrade --zip` snapshot the package files it replaces. Bring in the public instructions, templates and tools while keeping your existing identity, memory, projects and recovery data. Keep the original home until the updated home opens correctly and its files are verified.

## Modes

- **Standard** works on a file-only host. Markdown and JSON access, selective loading, compact readable status, persona customization, memory and knowledge continuity, and manual distillation with the templates.
- **Enhanced** works on a host with a terminal and Python 3.13+. The [Swiss Knife](TOOLS/README.md) adds deterministic reads, writes, validation, progression, guarded recovery, a derived content index with keyword search, a repair ladder, ZIP updates and read-only diagnostics.

Both use one workspace, so switching modes needs no migration and creates no second copy of identity, memory or progress. `python TOOLS/vhd.py doctor` reports the available and selected mode. A user can pin one in `MEMORY/CONFIG.json` with `{"schema": 1, "mode": "standard"}`, or ask for `doctor --mode`. An unavailable or unknown choice falls back with a warning.

## Optional runtime

Autonomous operation is off by default and never required. With `autonomous_opt_in` in `MEMORY/CONFIG.json`, `python TOOLS/vhd.py runtime` keeps a local queue of deterministic checks and runs them within a fixed budget. No model call happens while idle, and an inference task is blocked until a provider adapter exists. See [runtime](OPERATIONS/RUNTIME.md).

## Start a project

Choose a folder under `PROJECTS/` and copy the [project](TEMPLATES/PROJECT.md) and [handoff](TEMPLATES/HANDOFF.md) templates there as `PROJECT.md` and `HANDOFF.md`. A [checkpoint](TEMPLATES/PROGRESS.md) belongs in that project's `PROGRESS/` folder. Record a reusable method only when it is worth finding again. See [knowledge](OPERATIONS/KNOWLEDGE.md) and [levelling](OPERATIONS/LEVELLING.md).

## Search and repair

Enhanced mode can index the home and search it: `python TOOLS/vhd.py index` then `python TOOLS/vhd.py search "keyword"`. The index lives in `MEMORY/CACHE/`, is rebuilt from the Markdown whenever it drifts, and never replaces a file. `python TOOLS/vhd.py heal` inspects, repairs and verifies that derived state, and a bounded direct scan is the emergency fallback. Standard mode works without any of it. See [recovery](OPERATIONS/RECOVERY.md).

## Use another chat or app

Open the same home or supply a current authorized copy and start at [START_HERE](START_HERE.md). A read-only agent can propose exact file edits for you to save. In a chat without folder access, provide the startup files and relevant task files yourself. Save any updates back into your home before switching apps.

## Learning and reuse

Save what works and what fails as cards instead of prose scattered across chats. A [method card](TEMPLATES/METHOD.md) records a proven approach. A [failure card](TEMPLATES/FAILURE.md) records one that did not, with the replacement and the condition that would make it worth retrying. Both use one stable ID, one status and one evidence line, and both live in your catalog under `MEMORY/KNOWLEDGE/`.

Before substantial coding, check a failure first. The rules are in [Knowledge and reusable methods](OPERATIONS/KNOWLEDGE.md). Recording a failure earns no EXP; the verified replacement does.

## Safety and sharing

[Files and Git](OPERATIONS/FILES_AND_GIT.md) governs writes and recovery. Folder access and cloud processing depend on the application. Use host permissions for real isolation. Back up personalized files independently. Share a clean distribution from public sources, never your used home. Git ignores local runtime records but does not protect or sync them.

## Disclaimer

Provided as-is, without warranties. AI output can be wrong, costs stay with you, and third-party licenses remain your responsibility. Read the [full disclaimer](DISCLAIMER.md).

## Compatibility

| Host | Status |
| --- | --- |
| Windows 10 and 11, Python 3.13.14 | Tested |
| Linux and macOS | Portable primitives implemented, NOT RUN in this environment |
| File-only host, no Python | Standard mode, NOT RUN end to end here |

Only tested behaviour is claimed. Python 3.13 or newer is required for the helper.

## Known limitations

- Prose is never merged automatically, and a conflict needs a human choice.
- A dropped file is never deleted by the tool.
- Prose, cards and ledgers are Markdown, so a concurrent editor can overwrite a change the helper never saw.
- A local file lock is not coordination between hosts on SMB or NFS.
- Package integrity is checked per file; publisher authenticity needs a trusted signature that this version does not provide.
- Inference tasks in the runtime stay blocked until a provider adapter is configured.
- The content index is derived. A missing or stale index costs speed, not content, and a direct scan is used when it fails.
- A repair report describes derived state only; it says nothing about files the tool never reads.
- Recovery helpers reduce risk for operations that use them. They are not a backup.

## Optional Git

Smart Git is optional and VHD works without Git. `python TOOLS/vhd.py git` checkpoints the local repository, exports only the manifest allowlist into a separate public folder, verifies privacy and completeness, and publishes a local commit bound to the verified fingerprint. It never pushes, never forces, and never rewrites history. The export also carries `SOURCE.json`, a small record of the exported paths, their hashes and the export fingerprint. That file belongs to the export, not to the package, so a release ZIP never contains it. See [tools](TOOLS/README.md#smart-git).

## Artwork, licensing, and support

You supply your own artwork and any required permissions. [MIT license](LICENSE) · [Credits](CREDITS.md).
