"""magi — umbrella CLI dispatcher.

Design contract (see ROADMAP.md):
- Every deterministic operation is a subcommand; skills teach *when/why*,
  ``magi <cmd> --help`` teaches syntax.
- Subcommand modules keep their own argparse ``main(argv) -> int``; this
  dispatcher only routes. Modules are imported lazily so ``magi --help``
  stays fast and an import error in one subsystem cannot break the rest.
- JSON-capable commands accept ``--json``; their output shapes are the
  future ``magi mcp`` tool contracts — keep them stable.
"""

from __future__ import annotations

import importlib
import json
from magi.core import trace
import sys

from magi import __version__

# key: ("cmd",) or ("cmd", "subcmd") — longest match wins.
# value: (module, prepend_argv, help)
_COMMANDS: dict[tuple[str, ...], tuple[str, list[str], str]] = {
    # workspace / hub
    ("init",): ("magi.init_workspace", [], "Scaffold a project (raw/ wiki/ inbox/ output/)"),
    ("sync",): ("magi.sync", [], "Where the project stands; --close to end a session"),
    ("ui",): ("magi.ui.server", [], "Launch the local MAGI WebUI dashboard"),
    ("guide",): ("magi.guide", [], "Read the built-in manual (chapters, --search, --symptoms)"),
    ("skills", "list"): ("magi.skills_cmd", ["list"], "List the agent skills bundled with magi"),
    ("skills", "where"): ("magi.skills_cmd", ["where"], "Show where each agent CLI loads skills from"),
    ("skills", "install"): ("magi.skills_cmd", ["install"], "Install the skills into your agent CLI(s) (--scope global|project)"),
    ("skills", "uninstall"): ("magi.skills_cmd", ["uninstall"], "Remove magi's skills from an agent CLI"),
    ("setup",): ("magi.setup_cmd", [], "Provision the environment (beads, models, plugin) + doctor"),
    ("update",): ("magi.update", [], "Check for a newer release and install it"),
    ("migrate",): ("magi.migrate", [], "Upgrade a pre-magi (Wikify) directory — one project, or a hub of them"),
    ("adopt", "survey"): ("magi.adopt", ["survey"], "Inventory a folder of existing research material"),
    ("adopt", "apply"): ("magi.adopt", ["apply"], "Move what a plan says to move, and record it"),
    ("adopt", "undo"): ("magi.adopt", ["undo"], "Put back what the last adopt apply moved"),
    # work state (Beads bridge)
    ("pm", "init"): ("magi.pm", ["init"], "Initialize beads with research issue types"),
    ("pm", "backlog-sync"): ("magi.pm", ["backlog-sync"], "Uncompiled raw sources -> bd issues"),
    # ingestion
    ("ingest", "auto"): ("magi.ingest.auto", [], "Route a file (or all of inbox/) to the right ingester and finalize"),
    ("ingest", "add"): ("magi.ingest.helper", [], "Normalize + file an inbox document into raw/"),
    ("ingest", "assemble"): ("magi.ingest.assemble", [], "Stitch per-page transcriptions into one document"),
    ("ingest", "mineru"): ("magi.ingest.mineru", [], "PDF -> Markdown via MinerU cloud OCR"),
    ("ingest", "url"): ("magi.ingest.enqueue", [], "Queue a URL/DOI/arXiv id for acquisition"),
    ("ingest", "zotero-dirs"): ("magi.ingest.zotero", [], "List Zotero libraries and choose one"),
    ("ingest", "zotero"): ("magi.ingest.zotero_import", [], "Queue a Zotero collection for ingest"),
    ("ingest", "batch-run"): ("magi.ingest.batch", ["run"], "Acquire, convert and gate-check the queue"),
    ("ingest", "audit-titles"): ("magi.ingest.audit_titles", [], "Which cards no longer match the title they were filed with"),
    ("ingest", "review"): ("magi.ingest.batch", ["review"],
                           "The approval step: list, decide one item, or commit"),
    # `batch-list`, `batch-decide` and `batch-commit` were here. They are the
    # three things `magi ingest review` already does — its own help says so —
    # and having both spellings is most of why this group read as seventeen
    # commands. `batch.py` keeps the internal subcommands; `review` is how you
    # reach them.
    ("ingest", "arxiv-html"): ("magi.ingest.arxiv_html", [], "arXiv's LaTeXML HTML -> Markdown (best fidelity)"),
    ("ingest", "tex"): ("magi.ingest.tex2md", [], "LaTeX / arXiv source -> Markdown (pandoc)"),
    ("ingest", "ocr"): ("magi.ingest.ocr.agent", [], "PDF -> Markdown via local Ollama OCR"),
    ("ingest", "crop"): ("magi.ingest.pdf_math_crop", [], "Crop a PDF region to PNG for visual math checks"),
    ("ingest", "finalize"): ("magi.ingest.pipeline", [], "Post-ingest cleanup + lint + graph + wiki reindex (not 'magi index')"),
    # knowledge base
    ("wiki", "add-concept"): ("magi.kb.add_concept", [], "Create or append a concept card"),
    ("wiki", "refactor-concept"): ("magi.kb.refactor_concept", [], "Merge/rename a concept across the wiki"),
    ("wiki", "context"): ("magi.kb.extract_concept_context", [], "Extract paragraphs mentioning a concept"),
    ("wiki", "chunk"): ("magi.kb.chunker", [], "Split a large file into LLM-window chunks"),
    ("wiki", "placeholders"): ("magi.kb.find_placeholders", [], "Detect stub/placeholder text in a document"),
    ("wiki", "uncompiled"): ("magi.kb.detect_uncompiled", [], "List raw sources without compiled references"),
    ("wiki", "reindex"): ("magi.kb.index_builder", [], "Regenerate _index.md tables"),
    # research state
    ("install",): ("magi.install_cmd", [], "Install this project into your agent CLIs (skills + protocol + stop gate)"),
    ("next",): ("magi.state", ["next"], "What to do next, derived from the notes"),
    ("decide",): ("magi.decide_cmd", [], "Write down what the person decided (verbatim, where it can be audited)"),
    ("review",): ("magi.review", [], "Have another agent CLI check a claim that says it is solved"),
    ("close",): ("magi.close_cmd", [], "Close a research line, after showing what is still open"),
    ("publish",): ("magi.publish_cmd", [], "File our own paper into raw/ and retire the work it reports"),
    ("hook",): ("magi.hook_cmd", [], "Called by an agent CLI's hooks; not for typing by hand"),
    ("reflect",): ("magi.reflect.cmd", [], "Read the sessions where something happened, and write down what keeps happening"),
    ("feed",): ("magi.state", ["feed"], "Every post, newest first"),
    ("thread", "new"): ("magi.kb.thread_cmd", ["new"],
                        "Open a proposition, question or research line"),
    ("thread", "post"): ("magi.kb.thread_cmd", ["post"],
                         "Add a signed post to a note's discussion"),
    ("thread", "status"): ("magi.kb.thread_cmd", ["status"],
                           "Move a note along, with the reason as a post"),
    # graph
    ("graph", "build"): ("magi.kb.llmwiki", ["graph"], "Build/refresh the SQLite knowledge graph"),
    ("graph", "query"): ("magi.kb.graph_query", [], "Read-only SQL over output/graph.db"),
    ("graph", "browse"): ("magi.kb.graph_browse", [], "Browse the knowledge graph without SQL (nodes/links/claims/tags/broken)"),
    # quality / validation
    ("lint",): ("magi.kb.llmwiki", ["lint"], "Structural checks and self-healing fixes"),
    ("stats",): ("magi.kb.llmwiki", ["stats"], "Deterministic wiki statistics"),
    ("map",): ("magi.kb.llmwiki", ["map"], "Structural map of headings and math blocks"),
    ("math", "format"): ("magi.kb.format_math", [], "Auto-fix LaTeX delimiter/escaping issues project-wide"),
    ("math", "check"): ("magi.kb.validate_math_latex", [], "Find broken formulas; --json for a worklist"),
    ("validate",): ("magi.kb.validate_output", [], "Schema-validate generated thesis/research docs"),
    ("verify",): ("magi.kb.verify_claims", [], "Verify CLAIM/FINDING evidence blocks"),
    ("claims", "verify"): ("magi.kb.verify_claims", [], "Alias of 'magi verify' (claim/evidence check)"),
    ("bib",): ("magi.kb.bib_export", [], "Export BibTeX from reference cards (--fetch pulls arXiv's official entry)"),
    # retrieval
    ("index",): ("magi.retrieval", ["index"], "Build/refresh the hybrid retrieval index"),
    ("search",): ("magi.retrieval", ["search"], "Hybrid search: local project + enabled global KBs"),
    ("kb", "register"): ("magi.kb_registry", ["register"], "Register a project in the global KB registry"),
    ("kb", "list"): ("magi.kb_registry", ["list"], "List registered projects"),
    ("kb", "enable"): ("magi.kb_registry", ["enable"], "Include a KB in global search"),
    ("kb", "disable"): ("magi.kb_registry", ["disable"], "Exclude a KB from global search"),
    ("kb", "unregister"): ("magi.kb_registry", ["unregister"], "Remove a KB from the registry"),
    ("kb", "prune"): ("magi.kb_registry", ["prune"], "Drop registrations whose project directory is gone"),
    ("grep",): ("magi.kb.grep", [], "Regex search over given files"),
    ("link",): ("magi.kb.semantic_link", [], "Embedding-based concept linking and dedup"),
    # literature radar
    ("radar", "harvest"): ("magi.radar", ["harvest"], "Fetch + dedupe new paper candidates"),
    ("radar", "citation-gap"): ("magi.radar", ["citation-gap"], "Scout papers that should cite ours but don't"),
    ("radar", "status"): ("magi.radar", ["status"], "Radar ledger + pending digests"),
    ("radar", "triage"): ("magi.radar", ["triage"], "Record/list review decisions on radar candidates"),
    ("radar", "install-schedule"): ("magi.radar", ["install-schedule"], "Register a daily harvest job"),
    # tags
    ("tags", "extract"): ("magi.kb.tag_reducer", ["extract"], "Extract tag/alias inverted index"),
    ("tags", "apply"): ("magi.kb.tag_reducer", ["apply"], "Apply a canonical tag/alias mapping"),
}

_GROUP_HELP = {
    "kb": "Global project registry (cross-project search)",
    "ingest": "Document ingestion (PDF/LaTeX -> Markdown)",
    "wiki": "Concept and reference card operations",
    "thread": "Propositions, questions and research lines",
    "graph": "SQLite knowledge graph",
    "math": "LaTeX math formatting and validation",
    "pm": "Work-state bridge to Beads (bd)",
    "claims": "Claim/evidence provenance",
    "radar": "Literature radar (scheduled discovery)",
    "adopt": "Take a folder of existing material into a project",
    "tags": "Tag ontology normalization",
    "skills": "Agent skills, installed per CLI host",
}

#: Steps the conversion ladder walks by itself. Listed apart in `--help`
#: because typing one is forcing a route, not using the feature — and six of
#: them printed beside the five verbs is most of why this group looked like
#: seventeen decisions.
_RUNGS = {
    "ingest": ("arxiv-html", "tex", "mineru", "ocr", "assemble", "crop",
               "add", "finalize"),
}

_RUNG_NOTE = {
    "ingest": ("The ladder tries these in order by itself — name one only to "
               "force that route:"),
}


#: The commands a person is expected to know. Everything else still ships, is
#: still supported, and still appears under `--help --all` — it is just not on
#: the page somebody reads to find out what this tool is. The v1 surface was
#: seventy leaf commands listed at once, which is a reference manual printed
#: where a menu belongs: it made a first-time reader's job harder and told an
#: agent nothing it could not get from `magi next`.
#:
#: `sync` is on this list because the managed block tells every session to end
#: with `magi sync --close`, and on the three hosts with no stop hook that is
#: the only self-check a person has. A command the protocol requires and the
#: menu hides is a command somebody has to already know about.
PORCELAIN = ("next", "sync", "close", "publish", "init", "install", "ui",
             "search", "feed", "guide")


def _print_help(everything: bool = False) -> None:
    print(f"magi {__version__} — agent-native research project")
    print("\nUsage: magi <command> [subcommand] [args...]")
    print("       magi <command> --help          for syntax of any command\n")

    singles = {k[0]: v for k, v in _COMMANDS.items() if len(k) == 1}
    groups: dict[str, list[tuple[str, str]]] = {}
    for key, (_, _, help_text) in _COMMANDS.items():
        if len(key) == 2:
            groups.setdefault(key[0], []).append((key[1], help_text))

    if not everything:
        for name in PORCELAIN:
            entry = singles.get(name)
            if entry is not None:
                print(f"  {name:<22} {entry[2]}")
        print("\n  magi --help --all      every other command "
              f"({len(_COMMANDS) - len(PORCELAIN)} more: ingest, compile, graph, "
              "threads, radar, …)")
        return

    for name, (_, _, help_text) in sorted(singles.items()):
        print(f"  {name:<22} {help_text}")
    for group in sorted(groups):
        print(f"  {group:<22} {_GROUP_HELP.get(group, '')}")
        for sub, help_text in groups[group]:
            print(f"    {group + ' ' + sub:<20} {help_text}")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Consumed here rather than declared by forty subparsers: the commands
    # that most need tracing are the ones that spawn other commands, and a
    # flag only some of them accept is a flag nobody remembers.
    argv = trace.consume_flag(list(argv))

    if not argv:
        # Bare `magi` is `magi next` (design-v2 §7): one entry, and the router
        # decides. Outside a workspace there is no state to route, so the help
        # is the only useful answer.
        from magi.core.workspace import find_workspace_root

        if find_workspace_root() is None:
            _print_help()
            return 0
        argv = ["next"]
    if argv[0] in ("-h", "--help", "help"):
        _print_help(everything=any(a in ("--all", "-a") for a in argv[1:]))
        return 0
    if argv[0] in ("-V", "--version", "version"):
        print(f"magi {__version__}")
        return 0

    # Longest-prefix match: try (cmd, sub) then (cmd,)
    entry = None
    rest: list[str] = []
    if len(argv) >= 2 and (argv[0], argv[1]) in _COMMANDS:
        entry = _COMMANDS[(argv[0], argv[1])]
        rest = argv[2:]
    elif (argv[0],) in _COMMANDS:
        entry = _COMMANDS[(argv[0],)]
        rest = argv[1:]
    elif any(k[0] == argv[0] for k in _COMMANDS):
        group = argv[0]
        entries = sorted((k[1], _COMMANDS[k][2]) for k in _COMMANDS if len(k) == 2 and k[0] == group)
        # `magi <group>` / `magi <group> --help` is a help request, not an error
        if len(argv) == 1 or argv[1] in ("-h", "--help", "help"):
            print(f"magi {group} — {_GROUP_HELP.get(group, '')}\n")
            # The ladder's own steps are not choices a person makes. Printed
            # in one flat list with the verbs, six rungs read as six more
            # decisions standing between somebody and a filed paper.
            rungs = [row for row in entries if row[0] in _RUNGS.get(group, ())]
            verbs = [row for row in entries if row not in rungs]
            for sub_name, help_text in verbs:
                print(f"  magi {group} {sub_name:<18} {help_text}")
            if rungs:
                print(f"\n  {_RUNG_NOTE.get(group, 'Used automatically:')}")
                for sub_name, help_text in rungs:
                    print(f"  magi {group} {sub_name:<18} {help_text}")
            print(f"\nSyntax: magi {group} <subcommand> --help")
            return 0
        subs = ", ".join(s for s, _ in entries)
        print(f"magi {group}: unknown subcommand '{argv[1]}'. Available: {subs}", file=sys.stderr)
        return 2
    else:
        # `magi review` suggests a slug when you misspell one; typing the
        # command name wrong got "run --help" and a menu of 76 to scan.
        import difflib

        known = sorted({key[0] for key in _COMMANDS})
        near = difflib.get_close_matches(argv[0], known, n=3, cutoff=0.6)
        hint = f" Did you mean: {', '.join(near)}?" if near else ""
        print(f"magi: unknown command '{argv[0]}'.{hint} Run 'magi --help'.",
              file=sys.stderr)
        return 2

    module_name, prepend, _ = entry
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        print(f"magi: failed to load {module_name}: {exc}", file=sys.stderr)
        return 1

    try:
        result = module.main(prepend + rest)
    except SystemExit as exc:  # modules may still sys.exit(); normalize
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        # SystemExit("message") — the interpreter would have printed this;
        # swallowing it here loses ~40 llmwiki error messages. Print it.
        print(str(code), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except Exception as exc:                                    # noqa: BLE001
        # Everything that is not one of the three above used to reach the
        # interpreter as a traceback, `--json` or not. A caller that asked for
        # JSON gets JSON even when the answer is "it broke"; a person gets the
        # error rather than a stack; and the stack still exists on the trace
        # channel, which is what `--verbose` is for.
        import traceback

        trace.say("".join(traceback.format_exception(exc)).rstrip())
        if "--json" in rest:
            print(json.dumps({"error": f"{type(exc).__name__}: {exc}"},
                             ensure_ascii=False))
        else:
            print(f"magi {argv[0]}: {type(exc).__name__}: {exc}",
                  file=sys.stderr)
            if not trace.enabled():
                print("  run again with --verbose for the full traceback",
                      file=sys.stderr)
        return 1
    finally:
        _update_notice(argv)
    return int(result) if result is not None else 0


def _update_notice(argv: list[str]) -> None:
    """Tell a person about a newer release, after their command has finished.

    Three rules, all of them about not being in the way:

    * **It never waits on the network.** The line comes from a cache the
      *previous* invocation filled, and the refresh runs on a daemon thread. The
      worst case is hearing about a release a day late.
    * **stderr, and only for a terminal.** ``--json`` output is a contract that
      other programs parse; a version notice in the middle of it is a bug in
      whatever reads it, caused by us.
    * **Silence on every failure.** An update check that breaks a command has
      already cost more than it could ever save.
    """
    try:
        # Not after `magi update` itself, which has just said more about
        # versions than one cached line could.
        if not argv or argv[0] == "update":
            return
        if "--json" in argv or not sys.stderr.isatty():
            return
        from magi import update

        # An upgrade a previous `magi update` handed to the background helper.
        # This is not the update *check* and none of its opt-outs apply: it is
        # the outcome of something the person explicitly asked for, and until
        # it is said nobody knows whether it worked.
        done = update.pending_upgrade_report()
        if done:
            print(f"\n{done}", file=sys.stderr)

        if not update.notice_enabled():
            return
        line = update.pending_notice()
        if line:
            print(f"\n{line}", file=sys.stderr)
        update.refresh_in_background()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    sys.exit(main())
