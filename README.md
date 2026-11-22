# Virtual Home DIY

Virtual Home DIY 0.3.1 is a Markdown workspace for your AI partner. Open this folder in an agent application with local file access and say “Use Swiss Knife to read START_HERE.md, set up this home and start as Vee.” [Copyable instructions](sysprompt_to_copy.txt) work when the app needs an explicit prompt. The [quick tutorial](TUTORIAL.txt) includes a Cherry Studio example.

## Setup

1. On a fresh home, copy the [Vee identity template](TEMPLATES/IDENTITY.md) to `PERSONA/IDENTITY.md`, [owner handoff](TEMPLATES/OWNER_HANDOFF.md) to `PERSONA/HANDOFF.md`, [EXP ledger](TEMPLATES/EXP.md) to `PERSONA/PROGRESSION/EXP.md`, [memory index](TEMPLATES/MEMORY_INDEX.md) to `MEMORY/INDEX.md`, and [home handoff](TEMPLATES/HOME_HANDOFF.md) to `MEMORY/HANDOFF.md`. Create parent folders as needed. Copy only missing files. On a used home, recover missing identity and handoffs from a verified copy.
2. Keep Vee or choose a name, voice and focus together. Leave personal history blank until you provide facts you want to save.
3. Speak naturally and give the agent a task. It selects task-specific procedures from the [context map](CONTEXT_MAP.md).

With terminal access and Python 3.13+, Vee uses the [Swiss Knife](TOOLS/README.md#agent-workflow) for file work and progression. On Windows it also uses the CLI to initialize the home and write text files with verified snapshots. The [Markdown route](START_HERE.md) works with native file tools when these commands are unavailable.

To update a v0.1 or v0.2 home, first back it up. Bring in the public instructions, templates and tools while keeping your existing identity, memory, projects and recovery data. Keep the original home until the updated home opens correctly and its files are verified.

## Start a project

Choose a folder under `PROJECTS/` and copy the [project](TEMPLATES/PROJECT.md) and [handoff](TEMPLATES/HANDOFF.md) templates there as `PROJECT.md` and `HANDOFF.md`. A [checkpoint](TEMPLATES/PROGRESS.md) belongs in that project's `PROGRESS/` folder. Record a reusable method only when it is worth finding again. See [knowledge](OPERATIONS/KNOWLEDGE.md) and [levelling](OPERATIONS/LEVELLING.md).

## Use another chat or app

Open the same home or supply a current authorized copy and start at [START_HERE](START_HERE.md). A read-only agent can propose exact file edits for you to save. In a chat without folder access, provide the startup files and relevant task files yourself. Save any updates back into your home before switching apps.

## Safety and sharing

[Files and Git](OPERATIONS/FILES_AND_GIT.md) governs writes and recovery. Folder access and cloud processing depend on the application. Use host permissions for real isolation. Back up personalized files independently. Share a clean distribution from public sources, never your used home. Git ignores local runtime records but does not protect or sync them.

## Artwork, licensing, and support

You supply your own artwork and any required permissions. [MIT license](LICENSE) · [Credits](CREDITS.md).
