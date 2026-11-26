import sys

import homestead as core
from homestead_workflow import TASKS, lookup, preflight, privacy, scoped_links, size_zone, triage


def register(commands):
    subsets = commands.add_parser("tools", help="Discover the small tool set for one task")
    subsets.add_argument("--task", required=True, choices=sorted(TASKS))
    retrieve = commands.add_parser("lookup", help="Search within one exact workspace scope")
    retrieve.add_argument("query")
    retrieve.add_argument("--scope", required=True)
    retrieve.add_argument("--limit", type=int, default=10)
    pf = commands.add_parser("preflight", help="Check exact files before editing")
    pf.add_argument("--path", action="append", required=True)
    pf.add_argument("--budget", type=int, default=4096)
    pf.add_argument("--purpose")
    zones = commands.add_parser("zone", help="Measure the size of one exact file")
    zones.add_argument("path")
    zones.add_argument("--budget", type=int, default=4096)
    incoming = commands.add_parser("triage", help="Suggest routes for a selected inbox")
    incoming.add_argument("folder")
    private = commands.add_parser("privacy", help="Check exact text files and report redacted findings")
    private.add_argument("--path", action="append", required=True)
    kb = commands.add_parser("knowledge", help="Keep and search sources in the selected home")
    action = kb.add_subparsers(dest="action", required=True)
    pull = action.add_parser("ingest")
    pull.add_argument("url")
    pull.add_argument("--topic", required=True)
    pull.add_argument("--archive", action="store_true")
    paste = action.add_parser("paste")
    paste.add_argument("url")
    paste.add_argument("--topic", required=True)
    paste.add_argument("--title", required=True)
    find = action.add_parser("find")
    find.add_argument("query")
    find.add_argument("--limit", type=int, default=10)
    deny = action.add_parser("block")
    deny.add_argument("url")
    deny.add_argument("--reason", required=True)
    action.add_parser("lists")
    cash = commands.add_parser("cashbook", help="Export the selected transaction CSV to Excel")
    cash.add_argument("source")
    cash.add_argument("--out", required=True)
    cash.add_argument("--csv-out")
    cash.add_argument("--purpose", required=True)
    cash.add_argument("--currency")
    cash.add_argument("--column", action="append")
    provider = commands.add_parser("provider", help="Plan or send an explicitly authorized provider request")
    provider.add_argument("action", choices=["plan", "send"])
    provider.add_argument("path")
    provider.add_argument("--allow-provider", action="append", required=True)


def handle(home, args):
    if args.command == "tools":
        return {"task": args.task, "commands": TASKS[args.task]}
    if args.command == "lookup":
        return lookup(home, args.scope, args.query, args.limit)
    if args.command == "preflight":
        return preflight(home, args.path, args.budget, args.purpose)
    if args.command == "zone":
        return {**core.inspect(home, args.path), **size_zone(home.path(args.path, exists=True).stat().st_size, args.budget)}
    if args.command == "triage":
        return triage(home, args.folder)
    if args.command == "privacy":
        return privacy(home, args.path)
    if args.command == "cashbook":
        from homestead_cashbook import export
        return export(home, args.source, args.out, args.purpose, args.column, args.currency, args.csv_out)
    if args.command == "provider":
        from homestead_provider import plan, send
        command = plan if args.action == "plan" else send
        return command(home, args.path, args.allow_provider)
    if args.command == "knowledge":
        from homestead_knowledge import LIBRARY, block, find, ingest, library_state
        if args.action == "ingest":
            return ingest(home, args.url, args.topic, allow_archive=args.archive)
        if args.action == "paste":
            body = sys.stdin.buffer.read(core.TEXT_LIMIT + 1)
            core.require(0 < len(body) <= core.TEXT_LIMIT, "Supply permitted text on stdin within 256 KiB.")
            return ingest(home, args.url, args.topic, pasted=body, title=args.title)
        if args.action == "find":
            return find(home, args.query, args.limit)
        if args.action == "block":
            return block(home, args.url, args.reason)
        records = library_state(home).values()
        return {"bibliography": LIBRARY + "/BIBLIOGRAPHY.md", "blocklist": LIBRARY + "/BLOCKLIST.md",
                "sources": sum(record["status"] != "BLOCKED" for record in records),
                "blocked": sum(record["status"] == "BLOCKED" for record in records)}
    return None
