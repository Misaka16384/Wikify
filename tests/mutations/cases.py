"""The cases, grouped by the review round that found them.

Each one is a defect that reached the repository and was caught by reading,
not by the suite. The mutation is the defect; the target is the guard that now
stands where it was.
"""

from __future__ import annotations

from . import Case

CASES: list[Case] = [

    # ---------------------------------------------------------------- layout
    Case(
        area="layout",
        label="a new scaffold directory nobody classified",
        path="src/magi/init_workspace.py",
        fixed='"threads",',
        broken='"threads",\n        "annexes",',
        target="tests/test_project_layout.py -k both_directions",
    ),
    Case(
        area="layout",
        label="a row for a directory that no longer exists",
        path="src/magi/core/project.py",
        fixed='    "scratch": Dir(',
        broken='    "inventory": Dir(\n'
               '        what="Gone since v1.",\n'
               '        rewritten=False, searchable=False, documents=False, graphed=False,\n'
               '        note="stale",\n'
               '    ),\n'
               '    "scratch": Dir(',
        target="tests/test_project_layout.py -k both_directions",
    ),
    Case(
        area="layout",
        label="lint retypes its own directory list, as it did for years",
        path="src/magi/kb/llmwiki.py",
        fixed="DOCUMENT_DIRS = _document_dirs()",
        broken='DOCUMENT_DIRS = ("raw", "wiki", "inventory", "datasets")',
        target="tests/test_project_layout.py -k lint_document_loader",
    ),
    Case(
        area="layout",
        label="the retrieval index retypes its own list",
        path="src/magi/retrieval.py",
        fixed="CORPUS = _searchable_dirs()",
        broken='CORPUS = ("wiki", "raw")',
        target="tests/test_project_layout.py -k retrieval_index",
    ),
    Case(
        area="layout",
        label="wikilink priority stops matching the column",
        path="src/magi/state.py",
        fixed="_LINK_DIRS = _link_dirs()",
        broken='_LINK_DIRS = ("wiki", "drafts", "threads")',
        target="tests/test_project_layout.py -k wikilink_resolution",
    ),
    Case(
        area="layout",
        label="Project.resolve stops refusing an escape",
        path="src/magi/core/project.py",
        fixed="        if candidate != root and root not in candidate.parents:\n"
              "            raise ValueError(f\"{ref!r} resolves outside {self.root}\")\n",
        broken="",
        target="tests/test_project_layout.py -k cannot_leave",
    ),

    # ------------------------------------------------------------------- cli
    Case(
        area="cli",
        label="the bottom handler is removed, so a stack reaches the user",
        path="src/magi/cli.py",
        fixed="    except Exception as exc:                                    # noqa: BLE001",
        broken="    except _NeverRaised as exc:  # type: ignore[name-defined]",
        target="tests/test_cli_last_resort.py -k one_line_not_a_stack",
    ),
    Case(
        area="cli",
        label="--json loses its contract exactly when it matters",
        path="src/magi/cli.py",
        fixed='        if "--json" in rest:',
        broken="        if False:",
        target="tests/test_cli_last_resort.py -k json_stays_json",
    ),
    Case(
        area="cli",
        label="--verbose stops being consumed at the entry",
        path="src/magi/cli.py",
        fixed="    argv = trace.consume_flag(list(argv))",
        broken="    argv = list(argv)",
        target="tests/test_cli_last_resort.py -k verbose_is_accepted",
    ),

    Case(
        area="cli",
        label="a subcommand is implemented, wired and never routed",
        path="src/magi/cli.py",
        fixed='    ("kb", "prune"): ("magi.kb_registry", ["prune"], "Drop registrations whose project directory is gone"),\n',
        broken="",
        target="tests/test_contracts.py -k reachable",
    ),
    Case(
        area="cli",
        label="prune keeps the dead rows and deletes the living projects",
        path="src/magi/kb_registry.py",
        fixed='if not Path(entry["path"]).is_dir())',
        broken='if Path(entry["path"]).is_dir())',
        target="tests/test_registry_integrity.py -k prune",
    ),

    # -------------------------------------------------------------- skills
    Case(
        area="skills",
        label="magi verify loses the claims file, so the pre-completion check cannot run",
        path="src/magi/skills/draft/SKILL.md",
        fixed="`magi verify <claims.json> --project-dir .` for the",
        broken="`magi verify` for the",
        target="tests/test_skill_conventions.py -k can_start",
    ),
    Case(
        area="skills",
        label="a skill restates the NEEDS-DECISION template design-v2 §8 forbids",
        path="src/magi/skills/compile/SKILL.md",
        fixed="- Collect the questions your sub-agents could not ask (Invariant 4) and put",
        broken="- A sub-agent that needs a decision returns\n"
               "  `NEEDS-DECISION: <question> | options: <a> / <b> | default if unanswered: <x>`.\n"
               "- Collect the questions your sub-agents could not ask (Invariant 4) and put",
        target="tests/test_skill_conventions.py -k collect_the_questions",
    ),
    Case(
        area="skills",
        label="a retired word comes back into a skill",
        path="src/magi/skills/magi/SKILL.md",
        fixed="Any turn in a MAGI project where",
        broken="Any turn in a MAGI workspace where",
        target="tests/test_one_thing_one_word.py -k skills_use_one_word",
    ),

    # ------------------------------------------------------------- reflect
    Case(
        area="reflect",
        label="pick_host stops being told which project is asking",
        path="src/magi/reflect/cmd.py",
        fixed="    chosen = review.pick_host(None, configured=host or settings.host,\n"
              "                              config=settings.config)",
        broken="    chosen = review.pick_host(None, configured=host or settings.host)",
        target="tests/test_reflect_cmd.py -k declares_reaches",
    ),
    Case(
        area="reflect",
        label="the transcript sweep stops being told which project is asking",
        path="src/magi/reflect/cmd.py",
        fixed="    swept = transcripts.sweep(root, home=home, config=settings.config)",
        broken="    swept = transcripts.sweep(root, home=home)",
        target="tests/test_reflect_cmd.py -k sweep_is_told",
    ),
    Case(
        area="reflect",
        label="a refusal goes back to prose while the success path emits JSON",
        path="src/magi/reflect/cmd.py",
        fixed='            return _fail(f"the rule could not be written ({exc})", as_json)',
        broken='            print(f"the rule could not be written ({exc})", file=sys.stderr)\n'
               "            return 1",
        target="tests/test_reflect_cmd.py -k prints_prose",
    ),
    Case(
        area="reflect",
        label="the config write loses the lock its siblings have",
        path="src/magi/core/config_edit.py",
        fixed="def set_config_value(config_path: Path, dotted_key: str, value) -> None:\n"
              "    with _lock_for(config_path):\n"
              "        return _set_config_value(config_path, dotted_key, value)\n"
              "\n"
              "\n"
              "def _set_config_value(config_path: Path, dotted_key: str, value) -> None:",
        broken="def set_config_value(config_path: Path, dotted_key: str, value) -> None:",
        target="tests/test_config_edit.py -k two_writers",
    ),

    # ------------------------------------------------------------- migrate
    Case(
        area="migrate",
        label="v1's own index line counts as a person's note again",
        path="src/magi/migrate.py",
        fixed='    kept = _V1_BOOTSTRAP_LINE.sub("", kept)\n',
        broken="",
        target="tests/test_migrate_real_v1.py -k persons_note",
    ),
    Case(
        area="migrate",
        label="a name collision leaves an empty file behind",
        path="src/magi/migrate.py",
        fixed="        if target.exists():\n            skipped.append(note.name)\n            continue",
        broken="        if target.exists():\n            skipped.append(note.name)\n"
               '            note.write_text("", encoding="utf-8")\n            continue',
        target="tests/test_migrate_real_v1.py -k keeps_its_content",
    ),
    Case(
        area="migrate",
        label="the dry run starts writing",
        path="src/magi/migrate.py",
        fixed="    moved, skipped = retire_theses(root, dry_run=True)",
        broken="    moved, skipped = retire_theses(root)",
        target="tests/test_migrate_real_v1.py -k writes_absolutely_nothing",
    ),
    Case(
        area="migrate",
        label="a captured child is handed a terminal it cannot use",
        path="src/magi/sync.py",
        fixed="        proc = trace.run([sys.executable, \"-m\", \"magi\", *cmd],",
        broken="        proc = subprocess.run([sys.executable, \"-m\", \"magi\", *cmd],",
        target="tests/test_onboarding_path.py -k hand_its_child",
    ),
    Case(
        area="migrate",
        label="the handover gate goes back to checking stdin alone",
        path="src/magi/pm.py",
        fixed="    if assumed_yes or not (sys.stdin.isatty() and sys.stdout.isatty()):",
        broken="    if assumed_yes or not sys.stdin.isatty():",
        target="tests/test_onboarding_path.py -k both_ends",
    ),

    # ------------------------------------------------------------- v1 遗留
    Case(
        area="legacy",
        label="drafts/ drops out of the maintenance corpus",
        path="src/magi/core/wiki_common.py",
        fixed="CORPUS_DIRS = _corpus_dirs()",
        broken='CORPUS_DIRS = ("wiki", "raw")',
        target="tests/test_math_worklist.py -k every_tree_in_the_corpus",
    ),
    Case(
        area="legacy",
        label="the printed graph count goes back to the collected rows",
        path="src/magi/kb/llmwiki.py",
        fixed='        counted_nodes = cursor.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]',
        broken="        counted_nodes = len(node_rows)",
        target="tests/test_graph_threads.py -k number_it_prints",
    ),
    Case(
        area="legacy",
        label="a SOURCE: field can address a file outside the project again",
        path="src/magi/kb/verify_claims.py",
        fixed="    if not real_path.startswith(real_topic + os.sep) and real_path != real_topic:\n"
              '        return "unverified", f"path traversal: {abs_path} resolves outside {topic_dir}"\n',
        broken="",
        target="tests/test_verify_claims_loose.py -k cannot_climb_out",
    ),
    Case(
        area="legacy",
        label="a sources: field can resolve outside the project again",
        path="src/magi/kb/llmwiki.py",
        fixed="        if not is_under(candidate, ctx.root):\n            continue\n",
        broken="",
        target="tests/test_cold_backing.py -k outside_the_project",
    ),

    # ---------------------------------------------------------- cross-cutting
    Case(
        area="crosscut",
        label="thread creation loses the lock every sibling writer has",
        path="src/magi/kb/threads.py",
        fixed="    lock = lock_path(path)\n"
              "    with FileLock(str(lock), timeout=APPEND_TIMEOUT):\n"
              "        if path.exists():\n"
              "            raise FileExistsError(str(path))\n"
              "        atomic_write(path, render(kind, title, purpose, **kwargs))",
        broken="    if path.exists():\n"
               "        raise FileExistsError(str(path))\n"
               "    import time\n"
               "    time.sleep(0.05)\n"
               "    atomic_write(path, render(kind, title, purpose, **kwargs))",
        target="tests/test_threads.py -k two_creators_of_one_slug",
    ),
    Case(
        area="crosscut",
        label="a corrupt index crashes search instead of being skipped",
        path="src/magi/retrieval.py",
        fixed='    try:\n        conn.execute("PRAGMA journal_mode=WAL")\n    except sqlite3.DatabaseError:',
        broken='    if True:\n        conn.execute("PRAGMA journal_mode=WAL")\n    if False:',
        target="tests/test_retrieval_threads.py -k corrupt_index_does_not_crash",
    ),
    Case(
        area="crosscut",
        label="sync calls a corrupt index fresh",
        path="src/magi/sync.py",
        fixed='    if not readable:\n        return {"state": "unreadable", "chunks": 0, "vectors": 0, "score": 0.0}\n',
        broken="",
        target="tests/test_retrieval_threads.py -k not_call_a_corrupt_index_fresh",
    ),
    Case(
        area="crosscut",
        label="the lint cache goes back to holding a copy of the library",
        path="src/magi/kb/llmwiki.py",
        fixed='                        "frontmatter": doc.frontmatter,\n                    }',
        broken='                        "frontmatter": doc.frontmatter,\n'
               '                        "body": doc.body,\n'
               '                        "raw_text": doc.raw_text,\n                    }',
        target="tests/test_lint_cache.py",
    ),

    # ------------------------------------------------------------------ webui
    Case(
        area="webui",
        label="a mode block blanks a card's fill and leaves nothing behind (shipped 3x)",
        path="src/magi/ui/static/styles.css",
        fixed="  :root {\n    --glass-specular-color: transparent !important;\n  }\n}",
        broken="  .card,\n  .modal-window,\n  .toast {\n    background-image: none !important;\n  }\n}",
        target="tests/test_liquid_glass.py -k nothing_blanks_a_fill",
    ),
    Case(
        area="webui",
        label="forced colours loses the opaque backstop under the blanked fill",
        path="src/magi/ui/static/styles.css",
        fixed="    background-image: none !important;\n    background-color: Canvas !important;",
        broken="    background-image: none !important;",
        target="tests/test_liquid_glass.py -k nothing_blanks_a_fill",
    ),
    Case(
        area="webui",
        label="reduced motion starts forcing opacity, which is not what it asks for",
        path="src/magi/ui/static/styles.css",
        fixed="    --glass-specular-color: transparent !important;\n  }\n}",
        broken="    --glass-specular-color: transparent !important;\n    --glass-blur: 0px !important;\n  }\n}",
        target="tests/test_liquid_glass.py -k asks_for_less_movement",
    ),
    Case(
        area="webui",
        label="a var() fallback that can never fire, disagreeing with the real token",
        path="src/magi/ui/static/styles.css",
        fixed="  border-radius: var(--radius-sm);",
        broken="  border-radius: var(--radius-sm, 6px);",
        target="tests/test_liquid_glass.py -k carries_a_fallback",
    ),

    Case(
        area="webui",
        label="a surface hand-composes a glass recipe instead of naming one",
        path="src/magi/ui/static/styles.css",
        fixed="box-shadow: var(--fx-surface-sm);",
        broken="box-shadow: var(--glass-shadow-sm), var(--glass-rim-top);",
        target="tests/test_liquid_glass.py -k composes_its_own",
    ),
    Case(
        area="webui",
        label="a preset loses the bottom rim the author said everything gets",
        path="src/magi/ui/static/styles.css",
        fixed="  --fx-surface-md: var(--glass-shadow-md), var(--glass-rim-top), var(--glass-rim-bottom);",
        broken="  --fx-surface-md: var(--glass-shadow-md), var(--glass-rim-top);",
        target="tests/test_liquid_glass.py -k carries_both_rims",
    ),
    Case(
        area="webui",
        label="a thirtieth hardcoded core colour arrives unnoticed",
        path="src/magi/ui/static/styles.css",
        fixed='[data-theme="eva"] #tab-melchior { --core:',
        broken='[data-theme="eva"] .brand-new { color: #45D5EA; }\n[data-theme="eva"] #tab-melchior { --core:',
        target="tests/test_liquid_glass.py -k ledger_of_hardcoded",
    ),

    Case(
        area="webui",
        label="a textarea falls back to cols=20 inside a full-width card",
        path="src/magi/ui/static/styles.css",
        fixed="  width: 100%;\n}",
        broken="}",
        target="tests/test_liquid_glass.py -k textarea_is_given_a_width",
    ),
    Case(
        area="webui",
        label="a Chinese entry is the English one, so every key-exists check passes",
        path="src/magi/ui/static/app.js",
        fixed='      threads_title: "命题 · 问题 · 线",',
        broken='      threads_title: "Threads",',
        target="tests/test_one_thing_one_word.py -k nobody_translated",
    ),

    Case(
        area="ingest",
        label="the free PDF route asks if the document can be read, not if this machine can",
        path="src/magi/ingest/batch.py",
        fixed="        if not verdict.available:",
        broken="        if verdict.available:",
        target="tests/test_batch.py -k missing_extractor",
    ),
    Case(
        area="ci",
        label="a declared extra is installed nowhere the suite runs",
        path=".github/workflows/tests.yml",
        fixed='uv pip install -e ".[test,textlayer]"',
        broken='uv pip install -e ".[test]"',
        target="tests/test_packaging_matches_ci.py",
    ),

    # ------------------------------------------------------------------- docs
    Case(
        area="docs",
        label="the README drifts back to a retired word, outside every sweep",
        path="README.md",
        fixed="### 项目成品",
        broken="### 知识库成品",
        target="tests/test_one_thing_one_word.py -k readme",
    ),
    Case(
        area="docs",
        label="migration stops telling people they can look before they leap",
        path="README.md",
        fixed="magi migrate --dry-run   # 说清会改什么，一个字节都不写\n",
        broken="",
        target="tests/test_docs_quote_real_output.py -k capabilities",
    ),

    Case(
        area="ci",
        label="a test imports the repo root, green locally and red on CI",
        path="tests/test_docs_quote_real_output.py",
        fixed="    import test_one_thing_one_word as vocab",
        broken="    from tests import test_one_thing_one_word as vocab",
        target="tests/test_contracts.py -k repository_root_as_a_package",
    ),

    # ------------------------------------------------------------------ vocab
    Case(
        area="vocab",
        label="an argparse default writes a retired word into the user's config",
        path="src/magi/init_workspace.py",
        fixed='default="My Project"',
        broken='default="My Topic"',
        target="tests/test_one_thing_one_word.py -k cli_prints",
    ),
    Case(
        area="vocab",
        label="a bare library beside an excused Zotero one",
        path="src/magi/ingest/zotero_import.py",
        fixed='help="The whole Zotero library"',
        broken='help="The whole library"',
        target="tests/test_one_thing_one_word.py -k cli_prints",
    ),
]
