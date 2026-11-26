# Development workflow

For all work, understand the request, inspect actual sources, preserve accepted behavior, implement the smallest complete change, verify it, and stop when requirements pass.

State the acceptance check before starting substantial work: the observable result that means done, and the accepted behavior that must not change. When the request is ambiguous, name the assumption you are working from rather than asking for permission the request already implies.

Work at the lowest effort that can satisfy that check. Ordinary work runs at a normal setting; raise effort after a demonstrated gap, not in anticipation of one. Delegate or parallelize only when the subtasks are independent, the net gain is concrete, and the host can hold them, and keep the result and the final check with the caller.

Before deriving an answer again, check the catalog, the experience records and the ledger. Skip the lookup when the task is clear and small.

For substantial implementation, debugging or refactoring, check a `FAILED` entry on the same topic before reaching for a successful method. One lookup of the knowledge index, at most two cards, and name the ID you used or state plainly that none matched.

For substantial new work, research the actual runtime, versions, architecture and relevant primary references. Analyze suitable approaches. Present scope, interfaces, sequence and acceptance checks. Obtain approval before implementation and reuse that authorization for work within scope.

A small fix needs focused source/caller inspection, coherent repair, and proportionate validation. Do not disguise a new feature as a fix. Do not reopen accepted work without a defect, new requirement, or material evidence.

Preserve unrelated changes, interfaces, schemas, valid comments, dependencies, and defaults. Avoid unsolicited refactoring, renaming, formatting, optimization, or extra features. Add comments only when requested or technically needed.

Check the project sources and relevant reusable methods under [Knowledge](KNOWLEDGE.md). Define observable verification criteria independently of the implementation. Use deterministic local tools for parsing, building, comparing, and testing. Select checks based on risk, including callers, persistence, races, lifecycle, or boundaries when affected. No network/install is implied by a test command; establish its effects first.

For substantial work, consolidate diagnostics and repair understood causes together. When an attempt fails, diagnose the cause and adjust the retrieval, context or method before adding effort; repeating the same approach with more force is not a diagnosis. Never repeat an edit or a command that already failed on the same text with the same method; change the matching strategy or the tool. Never hide errors, weaken tests, or delete unrelated functionality to pass checks. After three distinct failed approaches to the same blocker, report the known cause and limits rather than continuing speculative retries.

Report PASS for executed passing checks, FAIL for executed failures, NOT RUN for unattempted checks, and BLOCKED for a concrete prevention. Syntax is not runtime proof. Reuse evidence only while relevant source, dependencies, command, and environment remain valid.

Before any write follow [Files and Git](FILES_AND_GIT.md). At meaningful milestones follow [Continuity](CONTINUITY.md). Close a tracked change in the order recorded under [closing out a change](LEVELLING.md#closing-out-a-change): scan once, classify, respect the gates, score only verified work, update the handoff, commit last. Check licenses before adapting third-party material and preserve applicable notices.
