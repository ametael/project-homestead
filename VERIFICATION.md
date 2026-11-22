# VHD 0.3.1 verification

Verified on 21 November 2026 on Windows with Python 3.13.14.

- **PASS** · 44 local tests covering setup and preservation, Markdown links, recovery, bounded UTF-8 reading, JSON validation, guarded UTF-8 writes, ledger stats and EXP replay. Writes tested creation, no-op, verified snapshot, stale hash, collision and scope refusal.
- **PASS** · Synthetic handoffs routed a fresh reader from the home and owner pointers through the relevant project to its verified checkpoint.
- **NOT RUN** · Cherry Studio or other live agent sessions, model behavior, and CLI mutation on other operating systems.

The [tutorial](TUTORIAL.txt) uses the documented Cherry Studio Work flow. Vee's tool selection comes from the startup instructions. The test suite verifies local files, commands and evidence handling. Each model and host needs access to the selected home.
