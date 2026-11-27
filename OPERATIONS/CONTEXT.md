# Context discipline

Identify the actual task, then follow root to relevant branch to required source. Search filenames, symbols, or scoped indexes before expanding retrieval. Read full required procedures and the actual affected source. Recover truncated output.

## Disclosure levels

| Level | What it holds | How it is reached |
| --- | --- | --- |
| L0 pointer | `START_HERE.md` and the action table in `CONTEXT_MAP.md` | always, once per chat |
| L1 index | `ROUTES.json`, `OPERATIONS/INDEX.md`, a catalog `INDEX.md`, a handoff table | when the action is known but not the file |
| L2 module | one `OPERATIONS/` rule file or one template | when the action is selected |
| L3 source | the project file, card, ledger or checkpoint that owns the fact | when the module names it |
| L4 full source | the complete file, through `read --offset` and `--length` pages or one native read | when acting requires the whole document |

Stop at the level that answers the request. A named file, owner or project is an explicit override: go straight to L3 or L4 and skip the table. Never open L4 merely because a link exists. A path, a size, a hash or a search hit is a pointer, not evidence that the file was read.

## Choose the subset from the request

The request decides which sources are needed. Name the kind of task first: reading, a question, a diagnosis, a build, a review, a retrieval, a record, or a release. The kind selects the subset; a single keyword does not. A code task narrows to development rules and the affected source; a memory capture narrows to memory rules and one note; a release question narrows to verification and the package documents. An explicit path, owner or scope wins over any automatic choice, and an explicit instruction not to narrow wins too. Do not infer a task from a single keyword when the sentence already states one.

Use `python TOOLS/homestead.py lookup QUERY --scope PATH` when you know the task scope, or use `search` for the home index. For a keyword lookup, then open the two or three hits that matter. A hit gives a path. An excerpt also gives the current source line and SHA-256. If a candidate differs from the index, search tries one refresh and withholds stale excerpts. A throttled or busy index can still miss new matches. Use `search --full` or scoped `lookup` when you need to check for newly added matches. Adaptive ranking is off; order comes from matched words, then occurrences, then path.

## Choose the effort

Use [adaptive reasoning](REASONING.md) for tasks where better references, a prior method or a deterministic check can resolve uncertainty before increasing model effort.

## Reuse and freshness

Use one canonical source for each detailed rule or fact. Other files hold short triggers and links. Reuse complete sources already read in the current chat while unchanged. A tool cache, a summary or another chat's receipt is not evidence that this chat read the source.

When an already loaded source may have changed, pass its last SHA-256 to `read PATH --if-changed SHA256`. Use this only when the complete text for that exact path, home and active persona is still available in the same chat. If the tool returns `unchanged: true`, reuse that text. Otherwise finish reading the new version with its SHA-256 and next offset. Read normally after a chat or persona switch, or if any of the earlier text is missing. With native file tools, reuse complete current text and reread the exact source when freshness needs checking.

For repetitive UTF-8 logs, start with [fold-log](../TOOLS/README.md#context-efficiency). Check for omitted groups and clipped text. Open the relevant original lines when diagnosing a distinct error.

Data that was not checked is never described as current. A reused index, a throttled refresh or a fallback scan carries its state in the result, and a claim of freshness needs the check that produced it. See [recovery](RECOVERY.md).

Several small topic files keep loading selective. Split a growing topic at meaningful boundaries, preserving decisions, reasons, exceptions, dates and source links. Do not split an unchanged file merely to produce more files.

Keep startup and handoff small. Summaries locate preserved originals; they do not replace required identity or evidence. Do not read every project or all checkpoint history at startup.

Consider input, output, tool results, retries and final quality when comparing cost. Label bytes and line counts honestly. Use exposed provider usage for actual claims; unavailable categories stay unknown. Prompt instructions are not hard spending limits.

Before writes, use [Files and Git](FILES_AND_GIT.md). Personal information also follows [Memory](MEMORY.md).
