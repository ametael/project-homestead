# Development workflow

For all work, understand the request, inspect actual sources, preserve accepted behavior, implement the smallest complete change, verify it, and stop when requirements pass.

For substantial new work, research the actual runtime, versions, architecture and relevant primary references. Analyze suitable approaches. Present scope, interfaces, sequence and acceptance checks. Obtain approval before implementation and reuse that authorization for work within scope.

A small fix needs focused source/caller inspection, coherent repair, and proportionate validation. Do not disguise a new feature as a fix. Do not reopen accepted work without a defect, new requirement, or material evidence.

Preserve unrelated changes, interfaces, schemas, valid comments, dependencies, and defaults. Avoid unsolicited refactoring, renaming, formatting, optimization, or extra features. Add comments only when requested or technically needed.

Check the project sources and relevant reusable methods under [Knowledge](KNOWLEDGE.md). Define observable verification criteria independently of the implementation. Use deterministic local tools for parsing, building, comparing, and testing. Select checks based on risk, including callers, persistence, races, lifecycle, or boundaries when affected. No network/install is implied by a test command; establish its effects first.

For substantial work, consolidate diagnostics and repair understood causes together. Never hide errors, weaken tests, or delete unrelated functionality to pass checks. After three distinct failed approaches to the same blocker, report the known cause and limits rather than continuing speculative retries.

Report PASS for executed passing checks, FAIL for executed failures, NOT RUN for unattempted checks, and BLOCKED for a concrete prevention. Syntax is not runtime proof. Reuse evidence only while relevant source, dependencies, command, and environment remain valid.

Before any write follow [Files and Git](FILES_AND_GIT.md). At meaningful milestones follow [Continuity](CONTINUITY.md). Check licenses before adapting third-party material and preserve applicable notices.
