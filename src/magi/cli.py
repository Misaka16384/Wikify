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
    ("migrate",): ("magi.migrate", [], "Migrate a pre-magi (Wikify) workspace"),
    # ingestion
    ("ingest", "add"): ("magi.ingest.helper", [], "Normalize + file an inbox document into raw/"),
    ("ingest", "assemble"): ("magi.ingest.assemble", [], "Stitch per-page transcriptions into one document"),
    ("ingest", "mineru"): ("magi.ingest.mineru", [], "PDF -> Markdown via MinerU cloud OCR"),
    ("ingest", "tex"): ("magi.ingest.tex2md", [], "LaTeX / arXiv source -> Markdown (pandoc)"),
    ("ingest", "ocr"): ("magi.ingest.ocr.agent", [], "PDF -> Markdown via local Ollama OCR"),
    ("ingest", "crop"): ("magi.ingest.pdf_math_crop", [], "Crop a PDF region to PNG for visual math checks"),
    ("ingest", "finalize"): ("magi.ingest.pipeline", [], "Post-ingest cleanup + lint + graph + index"),
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
    # quality / validation
    ("lint",): ("magi.kb.llmwiki", ["lint"], "Structural checks and self-healing fixes"),
    ("stats",): ("magi.kb.llmwiki", ["stats"], "Deterministic wiki statistics"),
    ("map",): ("magi.kb.llmwiki", ["map"], "Structural map of headings and math blocks"),
    ("math", "format"): ("magi.kb.format_math", [], "Auto-fix LaTeX delimiter/escaping issues"),
    ("math", "check"): ("magi.kb.validate_math_latex", [], "Detect LaTeX syntax errors"),
    ("validate",): ("magi.kb.validate_output", [], "Schema-validate generated thesis/research docs"),
    ("verify",): ("magi.kb.verify_claims", [], "Verify CLAIM/FINDING evidence blocks"),
    # retrieval
    ("grep",): ("magi.kb.grep", [], "Regex search over given files"),
    ("link",): ("magi.kb.semantic_link", [], "Embedding-based concept linking and dedup"),
    # tags
    ("tags", "extract"): ("magi.kb.tag_reducer", ["extract"], "Extract tag/alias inverted index"),
    ("tags", "apply"): ("magi.kb.tag_reducer", ["apply"], "Apply a canonical tag/alias mapping"),
}

_GROUP_HELP = {
    "hub": "Multi-topic hub management",
    "ingest": "Document ingestion (PDF/LaTeX -> Markdown)",
    "wiki": "Concept and reference card operations",
    "graph": "SQLite knowledge graph",
    "math": "LaTeX math formatting and validation",
    "tags": "Tag ontology normalization",
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
        subs = sorted(k[1] for k in _COMMANDS if len(k) == 2 and k[0] == argv[0])
        print(f"magi {argv[0]}: missing or unknown subcommand. Available: {', '.join(subs)}", file=sys.stderr)
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
        return code if isinstance(code, int) else (0 if code is None else 1)
    except KeyboardInterrupt:
        return 130
    return int(result) if result is not None else 0


if __name__ == "__main__":
    sys.exit(main())
