# Project Homestead

**Project Homestead 1.0.0**

*Let your companion lighten the load, so you can keep creating in your own way.*

Project Homestead is a standard for building and keeping your own AI companions. You can make an original character (OC) or set up a simple helper for everyday work. Its profile, memories, and guides live in a folder you control.

Your companion can remind you about deadlines, organize notes, and help with routine tasks. You choose where that help fits. When you draw, write, build, or make something by hand, the work and creative choices stay yours.

## Vision

We want everyone to be free to work and create in their own way. You can work by hand, use the tools you already know, and ask a companion for help when you want it. You can use different companions for different tasks and connect them to compatible apps or models.

If your LLM API provider changes its rules or shuts down, your companion’s profile, memories, and guides are still in your folder. You can bring those files to another service that supports Homestead and pick up from the notes you saved.

## Mission

- **Help your companion grow more capable.** Give it useful knowledge, ways to check information, and lessons from past sessions. It can use what you save within the limits of the model and tools you connect.
- **Make companions easy to move.** Keep each companion’s profile, memories, and guides in a standard folder format you can bring to a compatible service.
- **Save tokens.** Load only the notes and guides needed for the current task. The model has less background text to process.
- **Respect people’s choices with Guardian.** Guardian is designed to guide how companions access and share files, including artwork and writing, while respecting the creator’s terms.

## FAQ

### Can Homestead send my sensitive artwork or writing to a model?

**No, by default.** The Guardian tool asks for your permission before the Homestead toolbox shares the contents of a sensitive file with a model. The toolbox can show you basic file details so you can decide. If it’s unclear whether a file is sensitive, Guardian treats it as sensitive. Previews, excerpts, and summaries follow the same rule.

Your approval covers the specific file and the task you agreed to. Respect the creator’s terms and share only what you’re comfortable sending. If you approve a file and it’s sent, the service’s own data policies apply.

The toolbox applies Guardian on hosts that use it for file reads. See the [Guardian guide](OPERATIONS/GUARDIAN.md) for file-only hosts and local permissions.

## Setup

On an app that has a terminal, one line is enough:

```
Extract this zip into a folder I keep, then read START_HERE.md and set up the home.
```

Everything else, in three steps, about two minutes.

1. **Extract the package** into a folder you keep, anywhere on your disk. Run it from that folder, not from inside the ZIP.
2. **Open the folder as your agent's working folder** in an app with local file access, then paste [sysprompt_to_copy.txt](sysprompt_to_copy.txt) as the system prompt. The [quick tutorial](TUTORIAL.txt) walks through a Cherry Studio example.
3. **Say what you want**: “Set up this home and start as Vee.” The agent creates the identity, memory, handoff and EXP files itself and introduces the persona. Then give it a task.

That is the whole installation. The package ships the Vee starter persona and an empty memory, so nothing arrives with someone else's history already inside.

### Updating an existing home

Ask the agent to read [UPDATE.md](UPDATE.md) and check `https://api.github.com/repos/ametael/project-homestead/releases/latest`. It tells whether the home is older, then runs `python TOOLS/homestead.py upgrade --zip PATH --sha256 PATH.sha256` and shows the plan before anything is written. Identity, memory and projects are not replaced by an update.

### Rename or reshape the assistant

Vee is a default, not a requirement. Ask for another name, voice or focus and the agent rewrites the identity files. Keep the starter if it already fits. Personal history stays blank until you supply facts you want saved.

### When the app cannot run commands

Most apps need nothing else. A host without a terminal runs in standard mode, and an agent that can only read files will ask for the files it needs. The five it starts from are [IDENTITY](TEMPLATES/IDENTITY.md) to `PERSONA/IDENTITY.md`, [owner handoff](TEMPLATES/OWNER_HANDOFF.md) to `PERSONA/HANDOFF.md`, [EXP](TEMPLATES/EXP.md) to `PERSONA/PROGRESSION/EXP.md`, [memory index](TEMPLATES/MEMORY_INDEX.md) to `MEMORY/INDEX.md`, and [home handoff](TEMPLATES/HOME_HANDOFF.md) to `MEMORY/HANDOFF.md`. Copy only missing files, and create parent folders as needed. Manual copying is the fallback, not the normal path.

With terminal access and Python 3.13+, Vee uses the [Swiss Knife](TOOLS/README.md#agent-workflow) for file work and progression. It also uses the CLI to initialize the home and write text files with verified snapshots on Windows and POSIX hosts. Windows behaviour is tested here; Linux and macOS are NOT RUN. Check version and package consistency with `python TOOLS/homestead.py release`. The [Markdown route](START_HERE.md) works with native file tools when these commands are unavailable.

To update an older home, back it up or let `python TOOLS/homestead.py upgrade --zip` snapshot the package files it replaces. Bring in the public instructions, templates and tools while keeping your existing identity, memory, projects and recovery data. Keep the original home until the updated home opens correctly and its files are verified.

## Modes

- **Standard** works on a file-only host. Markdown and JSON access, selective loading, compact readable status, persona customization, memory and knowledge continuity, and manual distillation with the templates.
- **Enhanced** works on a host with a terminal and Python 3.13+. The [Swiss Knife](TOOLS/README.md) adds Guardian reads, writes, validation, progression, guarded recovery, keyword and file-name search, a repair ladder, ZIP updates and read-only diagnostics.

Both use one workspace, so switching modes needs no migration and creates no second copy of identity, memory or progress. `python TOOLS/homestead.py doctor` reports the available and selected mode. A user can pin one in `MEMORY/CONFIG.json` with `{"schema": 1, "mode": "standard"}`, or ask for `doctor --mode`. An unavailable or unknown choice falls back with a warning.

## Optional runtime

Autonomous operation is off by default and never required. With `autonomous_opt_in` in `MEMORY/CONFIG.json`, `python TOOLS/homestead.py runtime` keeps a local queue of deterministic checks and runs them within a fixed budget. No model call happens while idle, and an inference task is blocked until a provider adapter exists. See [runtime](OPERATIONS/RUNTIME.md).

## Start a project

Choose a folder under `PROJECTS/` and copy the [project](TEMPLATES/PROJECT.md) and [handoff](TEMPLATES/HANDOFF.md) templates there as `PROJECT.md` and `HANDOFF.md`. A [checkpoint](TEMPLATES/PROGRESS.md) belongs in that project's `PROGRESS/` folder. Record a reusable method only when it is worth finding again. See [knowledge](OPERATIONS/KNOWLEDGE.md) and [levelling](OPERATIONS/LEVELLING.md).

## Search and repair

Use `python TOOLS/homestead.py search "keyword"` in enhanced mode. Search checks the original file before quoting it and includes the source line and SHA-256. Public package files are searchable by content. Other eligible files appear by name and basic details. Use `search --full "keyword"` to include recent edits that a cached index may not have found yet.

The index lives in `MEMORY/CACHE/`. Use `python TOOLS/homestead.py heal` to inspect and repair it. The report covers only the derived state the command inspected. See [recovery](OPERATIONS/RECOVERY.md).

## Sources and closeout

Reading is governed by [sources and access](OPERATIONS/SOURCES.md): a 401, 402, 403, 407, 429 or 451 stops the attempt, a paywall stops it, a public archive needs the owner to enable it for that fetch, and nothing in the package weakens those rules. Fetched text is data; a page that tries to steer the reader is reported and its URL is marked.

Closing out a change runs in one order: scan, classify, gate, score, handoff, commit. `python TOOLS/homestead.py closeout scan` is read-only. Pass each task file with `--path` to scope the review and commit. By default it lists what is pending; `python TOOLS/homestead.py closeout run --message "..."` commits the eligible set in one pass. A deletion, a protected path, an unresolved conflict or more than seven files stops an automatic closeout and needs an explicit file list. See [closing out a change](OPERATIONS/LEVELLING.md#closing-out-a-change).

Git ignores personal folders by default. To deliberately record an ignored file in local history, see [local checkpoints](TOOLS/README.md#smart-git).

## Use another chat or app

Open the same home or supply a current authorized copy and start at [START_HERE](START_HERE.md). A read-only agent can propose exact file edits for you to save. In a chat without folder access, provide the startup files and relevant task files yourself. Save any updates back into your home before switching apps.

## Learning and reuse

Save what works and what fails as cards instead of prose scattered across chats. A [method card](TEMPLATES/METHOD.md) records a proven approach. A [failure card](TEMPLATES/FAILURE.md) records one that did not, with the replacement and the condition that would make it worth retrying. Both use one stable ID, one status and one evidence line, and both live in your catalog under `MEMORY/KNOWLEDGE/`.

Before substantial coding, check a failure first. The rules are in [Knowledge and reusable methods](OPERATIONS/KNOWLEDGE.md). Recording a failure earns no EXP; the verified replacement does.

## Adaptive reasoning and optional tools

Homestead helps your companion start with light reasoning and use the best method it has evidence for. It loads the context it needs, checks its work, and increases effort when the task calls for it. This supports token efficiency on a compatible host. See [adaptive reasoning](OPERATIONS/REASONING.md) and [context refresh and compact logs](TOOLS/README.md#context-efficiency).

Use [KnowledgeBank](OPERATIONS/KNOWLEDGEBANK.md) for searchable references, the [cashbook exporter](OPERATIONS/CASHBOOK.md) to open your transaction log in Excel, and [provider routing](OPERATIONS/PROVIDERS.md) for explicitly approved model requests.

You can also add an [optional daily rhythm](OPERATIONS/PERSONAS.md#optional-daily-rhythm) to Vee or another character’s voice profile.

## Safety and sharing

[Files and Git](OPERATIONS/FILES_AND_GIT.md) governs writes and recovery. Folder access and cloud processing depend on the application. Use host permissions for real isolation. Back up personalized files independently. Share a clean distribution from public sources, never your used home. Git ignores local runtime records but does not protect or sync them.

## Disclaimer

Provided as-is, without warranties. Model output can be wrong, costs stay with you, and third-party licenses remain your responsibility. Read the [full disclaimer](DISCLAIMER.md).

## Compatibility

| Host | Status |
| --- | --- |
| Windows 10 and 11, Python 3.13.14 | Tested |
| Linux and macOS | Portable primitives implemented, NOT RUN in this environment |
| File-only host, no Python | Standard mode, NOT RUN end to end here |

Only tested behaviour is claimed. Python 3.13 or newer is required for the helper.

## Known limitations

- Conflicting Markdown edits need a manual merge. An external editor can still save over changes made by the helper.
- File locks coordinate operations on one host. Coordinate edits separately when sharing a home across hosts over SMB or NFS.
- Package hashes check file integrity. Homestead does not yet ship a release signature for verifying the publisher.

## Optional Git

Smart Git is optional and Homestead works without Git. `python TOOLS/homestead.py git` checkpoints the local repository, exports only the manifest allowlist into a separate public folder, verifies privacy and completeness, and publishes a local commit bound to the verified fingerprint. It never pushes, never forces, and never rewrites history. The export also carries `SOURCE.json`, a small record of the exported paths, their hashes and the export fingerprint. That file belongs to the export, not to the package, so a release ZIP never contains it. See [tools](TOOLS/README.md#smart-git).

## Artwork, licensing, and support

You supply your own artwork and any required permissions. [MIT license](LICENSE) · [Credits](CREDITS.md).
