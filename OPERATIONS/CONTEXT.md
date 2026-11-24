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

The request decides which sources are needed. A code task narrows to development rules and the affected source; a memory capture narrows to memory rules and one note; a release question narrows to verification and the package documents. An explicit path, owner or scope wins over any automatic choice, and an explicit instruction not to narrow wins too. Do not infer a task from a single keyword when the sentence already states one.

Use `python TOOLS/vhd.py search QUERY` for a keyword lookup, then open the two or three hits that matter. A hit gives a path, a line and a freshness state. `throttled`, `busy`, `error` or `unindexed` means the list may not match the current files, so read the file before relying on it. Adaptive ranking is off; order comes from matched words, then occurrences, then path.

## Reuse and freshness

Use one canonical source for each detailed rule or fact. Other files hold short triggers and links. Reuse complete sources already read in the current chat while unchanged. A tool cache, a summary or another chat's receipt is not evidence that this chat read the source.

Data that was not checked is never described as current. A reused index, a throttled refresh or a fallback scan carries its state in the result, and a claim of freshness needs the check that produced it. See [recovery](RECOVERY.md).

Several small topic files keep loading selective. Split a growing topic at meaningful boundaries, preserving decisions, reasons, exceptions, dates and source links. Do not split an unchanged file merely to produce more files.

Keep startup and handoff small. Summaries locate preserved originals; they do not replace required identity or evidence. Do not read every project or all checkpoint history at startup.

Consider input, output, tool results, retries and final quality when comparing cost. Label bytes and line counts honestly. Use exposed provider usage for actual claims; unavailable categories stay unknown. Prompt instructions are not hard spending limits.

Before writes, use [Files and Git](FILES_AND_GIT.md). Personal information also follows [Memory](MEMORY.md).
