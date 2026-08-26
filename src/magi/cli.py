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
import sys

from magi import __version__

# key: ("cmd",) or ("cmd", "subcmd") — longest match wins.
# value: (module, prepend_argv, help)
_COMMANDS: dict[tuple[str, ...], tuple[str, list[str], str]] = {
    # workspace / hub
    ("init",): ("magi.hub.init_workspace", [], "Scaffold a topic workspace (raw/ wiki/ inbox/ output/)"),
    ("hub", "init"): ("magi.hub.init_hub", [], "Scaffold a multi-topic hub (wikis.json registry)"),
    ("hub", "resolve"): ("magi.hub.router", [], "Resolve a topic slug to its path"),
    ("hub", "list"): ("magi.kb.llmwiki", ["archive", "list"], "List active and archived topics"),
    ("hub", "archive"): ("magi.kb.llmwiki", ["archive", "topic"], "Archive an active topic"),
    ("hub", "restore"): ("magi.kb.llmwiki", ["archive", "restore"], "Restore an archived topic"),
    ("hub", "register"): ("magi.kb.llmwiki", ["archive", "register"], "Register an existing topic in the hub"),
    ("sync",): ("magi.sync", [], "Workspace onboarding: sync ratio + three-core status"),
    ("ui",): ("magi.ui.server", [], "Launch the local MAGI WebUI dashboard"),
    ("guide",): ("magi.guide", [], "Read the built-in manual (chapters, --search, --symptoms)"),
    ("each",): ("magi.each", [], "Run one command in every topic of the hub"),
    ("skills", "list"): ("magi.skills_cmd", ["list"], "List the agent skills bundled with magi"),
    ("skills", "where"): ("magi.skills_cmd", ["where"], "Show where each agent CLI loads skills from"),
    ("skills", "install"): ("magi.skills_cmd", ["install"], "Install the skills into your agent CLI(s) (--scope global|project)"),
    ("skills", "uninstall"): ("magi.skills_cmd", ["uninstall"], "Remove magi's skills from an agent CLI"),
    ("setup",): ("magi.setup_cmd", [], "Provision the environment (beads, models, plugin) + doctor"),
    ("update",): ("magi.update", [], "Check for a newer release and install it"),
    ("migrate",): ("magi.migrate", [], "Migrate a pre-magi (Wikify) workspace (hub or topic)"),
    # work state (Beads bridge)
    ("pm", "init"): ("magi.pm", ["init"], "Initialize beads with research issue types"),
    ("pm", "status"): ("magi.pm", ["status"], "Beads availability + issue counts"),
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
    ("ingest", "batch-list"): ("magi.ingest.batch", ["list"], "Review batches awaiting approval"),
    ("ingest", "batch-decide"): ("magi.ingest.batch", ["decide"], "Approve/reject/reset one batch item"),
    ("ingest", "batch-commit"): ("magi.ingest.batch", ["commit"], "Commit fully-decided batches into raw/"),
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
    # graph
    ("graph", "build"): ("magi.kb.llmwiki", ["graph"], "Build/refresh the SQLite knowledge graph"),
    ("graph", "query"): ("magi.kb.graph_query", [], "Read-only SQL over output/graph.db"),
    ("graph", "browse"): ("magi.kb.graph_browse", [], "Browse the knowledge graph without SQL (nodes/links/claims/tags/broken)"),
    # quality / validation
    ("lint",): ("magi.kb.llmwiki", ["lint"], "Structural checks and self-healing fixes"),
    ("stats",): ("magi.kb.llmwiki", ["stats"], "Deterministic wiki statistics"),
    ("map",): ("magi.kb.llmwiki", ["map"], "Structural map of headings and math blocks"),
    ("math", "format"): ("magi.kb.format_math", [], "Auto-fix LaTeX delimiter/escaping issues workspace-wide"),
    ("math", "check"): ("magi.kb.validate_math_latex", [], "Find broken formulas; --json for a worklist"),
    ("validate",): ("magi.kb.validate_output", [], "Schema-validate generated thesis/research docs"),
    ("verify",): ("magi.kb.verify_claims", [], "Verify CLAIM/FINDING evidence blocks"),
    ("claims", "verify"): ("magi.kb.verify_claims", [], "Alias of 'magi verify' (claim/evidence check)"),
    ("bib",): ("magi.kb.bib_export", [], "Export BibTeX from reference cards (--fetch pulls arXiv's official entry)"),
    # retrieval
    ("index",): ("magi.retrieval", ["index"], "Build/refresh the hybrid retrieval index"),
    ("search",): ("magi.retrieval", ["search"], "Hybrid search: local workspace + enabled global KBs"),
    ("kb", "register"): ("magi.kb_registry", ["register"], "Register a workspace in the global KB registry"),
    ("kb", "list"): ("magi.kb_registry", ["list"], "List registered knowledge bases"),
    ("kb", "enable"): ("magi.kb_registry", ["enable"], "Include a KB in global search"),
    ("kb", "disable"): ("magi.kb_registry", ["disable"], "Exclude a KB from global search"),
    ("kb", "unregister"): ("magi.kb_registry", ["unregister"], "Remove a KB from the registry"),
    ("grep",): ("magi.kb.grep", [], "Regex search over given files"),
    ("link",): ("magi.kb.semantic_link", [], "Embedding-based concept linking and dedup"),
    # literature radar
    ("radar", "harvest"): ("magi.radar", ["harvest"], "Fetch + dedupe new paper candidates"),
    ("radar", "citation-gap"): ("magi.radar", ["citation-gap"], "Scout papers that should cite ours but don't"),
    ("radar", "status"): ("magi.radar", ["status"], "Radar ledger + pending digests"),
    ("radar", "install-schedule"): ("magi.radar", ["install-schedule"], "Register a daily harvest job"),
    # tags
    ("tags", "extract"): ("magi.kb.tag_reducer", ["extract"], "Extract tag/alias inverted index"),
    ("tags", "apply"): ("magi.kb.tag_reducer", ["apply"], "Apply a canonical tag/alias mapping"),
}

_GROUP_HELP = {
    "hub": "Multi-topic hub management",
    "kb": "Global knowledge-base registry (cross-workspace search)",
    "ingest": "Document ingestion (PDF/LaTeX -> Markdown)",
    "wiki": "Concept and reference card operations",
    "graph": "SQLite knowledge graph",
    "math": "LaTeX math formatting and validation",
    "pm": "Work-state bridge to Beads (bd)",
    "claims": "Claim/evidence provenance",
    "radar": "Literature radar (scheduled discovery)",
    "tags": "Tag ontology normalization",
    "skills": "Agent skills, installed per CLI host",
}


def _print_help() -> None:
    print(f"magi {__version__} — agent-native research workspace")
    print("\nUsage: magi <command> [subcommand] [args...]")
    print("       magi <command> --help          for syntax of any command\n")
    singles = {k[0]: v for k, v in _COMMANDS.items() if len(k) == 1}
    groups: dict[str, list[tuple[str, str]]] = {}
    for key, (_, _, help_text) in _COMMANDS.items():
        if len(key) == 2:
            groups.setdefault(key[0], []).append((key[1], help_text))
    for name, (_, _, help_text) in sorted(singles.items()):
        print(f"  {name:<22} {help_text}")
    for group in sorted(groups):
        print(f"  {group:<22} {_GROUP_HELP.get(group, '')}")
        for sub, help_text in groups[group]:
            print(f"    {group + ' ' + sub:<20} {help_text}")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        _print_help()
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
            for sub_name, help_text in entries:
                print(f"  magi {group} {sub_name:<18} {help_text}")
            print(f"\nSyntax: magi {group} <subcommand> --help")
            return 0
        subs = ", ".join(s for s, _ in entries)
        print(f"magi {group}: unknown subcommand '{argv[1]}'. Available: {subs}", file=sys.stderr)
        return 2
    else:
        print(f"magi: unknown command '{argv[0]}'. Run 'magi --help'.", file=sys.stderr)
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
