# Optional runtime

Disabled by default. It needs `autonomous_opt_in: true` in `MEMORY/CONFIG.json`; a missing key means off. Standard and enhanced work never require it.

## Data

Everything stays in `MEMORY/RUNTIME/`: `queue.json`, `state.json`, `budget.json`, `events.log` with the last 200 lines, and the `STOP` flag. Nothing is written outside the home, and no request leaves the machine.

## Commands

```text
python TOOLS/homestead.py runtime status
python TOOLS/homestead.py runtime add --kind links
python TOOLS/homestead.py runtime start
python TOOLS/homestead.py runtime run --limit 2
python TOOLS/homestead.py runtime pause
python TOOLS/homestead.py runtime resume
python TOOLS/homestead.py runtime stop
python TOOLS/homestead.py runtime stop --now
```

`status` is read-only. `add` deduplicates on kind and payload into a stable ID. `start` clears a previous `STOP` flag only because the user asked for it. `run` processes pending and due retry tasks within `max_tasks_per_run`, records a heartbeat after each task and stops early when the budget is exhausted. `stop --now` also writes the `STOP` flag, which blocks every later run until `start` is used again.

## Task kinds

Deterministic kinds are `doctor`, `links`, `routes`, `audit` and `release`. An `inference` task is accepted into the queue and remains blocked. Use [provider routing](PROVIDERS.md) separately to approve the exact file and destinations for a manual request.

## Limits

Attempts are capped at `max_attempts` with a fixed backoff, and a failed task keeps its error and stops. Idle time makes no model call, so token use is reported as unmeasured rather than estimated. Health reads `interrupted` when a running state has a heartbeat older than ten minutes; recover by inspecting the queue and running again, because completed tasks are skipped. A local file queue is not coordination between hosts. No DRM, telemetry or hidden network request is involved.