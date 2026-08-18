# MAGI

*[English](README_en.md) | [中文](README.md)*

**MAGI** is an agent-native research workspace: the human pilots, the LLM agent is the mecha, and the deterministic `magi` CLI is the restraint armor — the higher the sync ratio, the faster the science. It ingests academic papers (PDF/LaTeX) into an Obsidian-compatible concept-card knowledge base and manages the full research state through a three-core architecture:

| Core | State | Carried by | Question answered |
|---|---|---|---|
| **MELCHIOR** | Epistemic (knowledge) | concept/reference cards + SQLite knowledge graph + claim/evidence provenance | What do we know, and why is it credible? |
| **BALTHASAR** | Intent (work) | [Beads](https://github.com/gastownhall/beads) (`bd`) research task graph | What are we doing, and what's next? |
| **CASPER** | Retrieval | local hybrid search (FTS5 BM25 + sqlite-vec vectors + RRF) | What should I read right now? |

Enter any workspace and run **`magi sync`** — it reports the **sync ratio**, three-core status, and concrete restore hints. `magi radar` is the literature radar: scheduled discovery of relevant new papers, plus scouting for recent papers that arguably should cite yours but don't. One shared skills tree serves Claude Code / Codex / Antigravity and other CLI agent hosts.

Full syntax for any command: `magi <command> --help`; overview: `magi --help`.

---

## 🌟 Showcase

![Knowledge Graph Visualization](./graph.png)
*An automatically generated dense semantic graph of physics and math concepts.*

![Compiled Literature Card](./note1.png)
*A clean reference card compiled from a messy PDF.*

![Math & Concept Extraction](./note2.png)
*Proofs and lemmas extracted and formatted from LaTeX sources.*

---

## 1. Architecture: CLI, skills, and hosts

```text
You (the pilot)
  └─ Claude Code / Codex / Antigravity  (the mecha: reasoning, writing, judgment)
       ├─ skills/*/SKILL.md   — teach the agent WHEN and WHY to run each pipeline
       └─ magi CLI (restraint armor) — every deterministic operation:
            ingestion, graph, retrieval, validation, tasks, radar
            └─ durable state lives on disk: raw/ wiki/ output/ .beads/
```

- The **CLI owns syntax** and is self-describing (`--help`); **skills teach methodology** and never duplicate flag lists.
- Durable state always lives in files/databases; agent context is disposable (fresh-context workers).
- The `--json` output shapes are the future `magi mcp` tool contracts.

---

## 2. Installation

### 2.1 One-line install (recommended)

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
```

**macOS / Linux:**

```bash
curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
```

The script does everything: installs [uv](https://docs.astral.sh/uv/) if missing, installs the `magi` CLI from GitHub (Python included — no preinstall needed), then runs **`magi setup`**: installs [Beads](https://github.com/gastownhall/beads) (`bd`), pulls the Ollama embedding model (when Ollama is present), registers the Claude Code plugin (when `claude` is present), detects legacy Wikify leftovers, and prints an environment doctor table. **Idempotent — re-run to upgrade.**

Check your environment any time:

```powershell
magi setup --check
```

`magi setup` flags: `--no-beads` / `--no-models` / `--no-plugin` / `--remove-legacy` (delete detected legacy copies).

**Want the classic Wikify experience (knowledge base only, no task management)?** Use `magi setup --kb-only`: skips the Beads install and `magi sync` stops suggesting task tracking (the BALTHASAR core shows disabled and is excluded from the sync ratio). Restore any time with `magi setup --full`. Everything else (radar etc.) is invoke-only — unused features stay invisible.

### 2.2 Manual install (fallback)

<details>
<summary>Expand manual steps</summary>

**CLI** (Python 3.10+, uv or pipx):

```powershell
uv tool install --python 3.12 git+https://github.com/Misaka16384/magi
# or local dev: git clone ... && cd magi && uv tool install .
# upgrade: re-run with --force
```

**Beads**: Windows `irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex`; macOS/Linux see the [official docs](https://github.com/gastownhall/beads/blob/main/docs/getting-started/installation.md). MAGI degrades gracefully without `bd`.

**Ollama models**: `ollama pull qwen3-embedding:0.6b` (vector search); `ollama pull glm-ocr` (local OCR, optional). Retrieval degrades to BM25-only when Ollama is unreachable.

</details>

### 2.3 System-level external tools (as needed; `magi setup --check` reports them)

| Tool | Used by | Notes |
|---|---|---|
| **Pandoc** | `magi ingest tex` (LaTeX → Markdown) | Windows `pandoc-crossref.exe` is vendored in `vendor/windows/` (add to PATH or set `tools.pandoc_crossref_path` in config.yaml) |
| **Poppler** (`pdftoppm`/`pdfimages`) | local OCR pipeline PDF rendering | `scoop/choco/brew/apt install poppler` |
| **pdflatex** (optional) | deep math validation | falls back to `pylatexenc` when absent |

(The historic ripgrep dependency is gone.)

### 2.4 Installing the skills (teaching your agent)

Every host shares the same `skills/*/SKILL.md` tree:

- **Claude Code**: the one-line installer registers this automatically (`magi setup` runs `claude plugin marketplace add Misaka16384/magi` + `claude plugin install magi`). Skills appear namespaced as `/magi:wiki_ingest` etc., and the plugin ships a SessionStart hook that runs `magi sync`; for local dev use `claude plugin install <repo-dir>`.
- **Codex and other Agent Plugins 1.0 hosts**: the repo root ships a `plugin.json`; point your host's plugin flow at this repository.
- **Gemini / Antigravity**: copy (or link) `skills/` into `<project>/.agents/skills/`.

---

## 3. Quick start (5 minutes)

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init                # central hub (wikis.json registry)
magi pm init                 # beads + research issue types (git-inits this directory)

mkdir topics\quantum-toys ; cd topics\quantum-toys
magi init --name "Quantum Toys" --scope "quantum phenomena in toy models"
# ↑ auto-registers in the hub; generates CLAUDE.md / AGENTS.md (agent entry
#   protocol), config.yaml, scratch/

magi sync                    # sync ratio + three cores + next-step hints
```

```text
MAGI SYSTEM ONLINE — sync ratio 90.0%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     0 ready · 0 in progress · 0 blocked
`- CASPER    (retrieval)  index fresh · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the wiki_ingest skill to start building the library
```

> The sync ratio depends on how many cores are ready: the example shows an empty library with beads initialized and an index built (90%). Without `magi pm init` or `magi index` yet, the number is lower — just follow the hints; nothing is misconfigured.

Then drop PDFs / LaTeX / notes into `inbox/` and tell your agent to ingest them (or invoke `/magi:wiki_ingest`).

---

## 4. The research lifecycle (skills overview)

Trigger via slash commands in your agent (namespaced `magi:` under the Claude Code plugin) or plain natural language:

| Phase | Skill | What it does |
|---|---|---|
| Setup | `wiki_hub_init` / `wiki_init` | scaffold the hub / a topic workspace |
| Ingest | `wiki_ingest` | PDF/LaTeX/URL → Markdown (MinerU cloud or native vision; put your MinerU token in the workspace `config.yaml` under `ocr.mineru_api_token`) |
| Ingest | `wiki_ingest_ocr` | fully local OCR route (Ollama `glm-ocr`) |
| Compile | `wiki_compile` | raw sources → reference + concept cards (closes the bd loop: `magi pm backlog-sync`'s `magi-compile` label) |
| Compile | `wiki_enrich` | deep-scan compiled sources for missed theorems/concepts |
| Link | `wiki_semantic_link` | Ollama-embedding semantic wikilinks + auto-merge of near-duplicates (`magi link`) |
| Normalize | `wiki_tag_sync` / `wiki_concept_sync` | tag ontology cleanup / physical merge of synonym concepts |
| Quality | `wiki_lint` | dead-link healing, frontmatter repair, LaTeX validation (`magi lint --fix`) |
| Graph | `wiki_graph_index` | rebuild the SQLite graph (`magi graph build` / `magi graph query`) |
| Q&A | `wiki_ask` | hybrid retrieval + graph traversal + strictly cited, zero-hallucination answers |
| Audit | `wiki_audit` | cross-paper contradiction audit (claim/evidence verification + provenance) |
| Survey | `wiki_research` | parallel subagent research → a provenance-backed survey report |
| Radar | `radar_review` | triage radar digests: score → bd survey issues → mark reviewed |
| Write | `wiki_draft` | paper drafts in `drafts/`: evidence-backed writing → `magi bib` citation export → pandoc LaTeX export |
| Maintain | `wiki_hub_manager` | archive / restore topics (`magi hub archive/restore`) |

### The global KB registry (cross-workspace search)

Every workspace auto-registers in a user-global registry (`~/.config/magi/registry.json`) when you run `magi index`. **`magi search` federates by default: the current workspace + every enabled registered KB**, with results tagged `[kb:name]`:

```powershell
magi kb list                    # all registered KBs and their searchable state
magi kb disable <name>          # exclude a KB from global search (enable to restore)
magi search "..." --scope local # current workspace only (classic behavior)
magi search "..." --kb <name>   # target one registered KB
```

The current workspace is always searchable; other KBs are governed by enable/disable. `magi kb register <path>` registers any workspace manually; `unregister` removes only the registry entry, never files.

> Search tips: `--path 'raw/papers/2026-*<slug>*'` narrows semantic search to one paper; Chinese and English queries both work (CJK bigram tokenization feeds BM25, and the embedding model handles cross-lingual matching on the vector side).

### Writing & citations (`drafts/` + `magi bib`)

Drafts are first-class citizens: they live in `drafts/`, are indexed for search (collection `drafts`), but stay out of the graph and sync ratio. Citations export straight from reference cards:

```powershell
magi bib pretko-2020            # reference-card frontmatter → BibTeX entry
magi bib --all -o drafts/refs.bib
magi bib pretko-2020 --fetch    # pull arXiv's official BibTeX when the card has an arxiv_id
```

`magi ingest tex` preserves the source package's `.bib`/`.bbl` next to the raw markdown (`raw/papers/<slug>.bib`), and writes any arXiv ID found in the filename into frontmatter `arxiv_id:` for the radar. See the `wiki_draft` skill for the full workflow.

> Claims boundary: `magi verify`'s `verified` means **quote-existence verification** (the quote really appears verbatim in the source, with whitespace/ligature/full-width-punctuation-robust matching) — it does not judge whether the claim and the quote agree semantically; that layer belongs to LLM/human review (`magi claims verify` is an alias of the same command).

### The literature radar (`magi radar`)

After configuring the `radar:` section of the workspace `config.yaml` (arXiv categories, seed papers, your own papers):

```powershell
magi radar harvest              # manual harvest: S2 recommendations ∪ new arXiv listings → inbox/radar/<date>-digest.md
                                # (candidates sorted by cosine relevance to the library's embedding centroid,
                                #  each annotated with a relevance score; set radar.min_relevance to filter)
magi radar install-schedule     # daily scheduled harvest (Task Scheduler / launchd; --uninstall to remove)
magi radar citation-gap         # scout recent papers that arguably should cite yours (four-layer funnel, human-review queue)
```

Deterministic harvest runs at night; the `radar_review` skill does LLM triage in your next session — `magi sync` will point at pending digests.

### Local WebUI Dashboard (`magi ui`)

MAGI includes a zero-build, Claude-styled local inspection and operations dashboard (FastAPI + native SPA) for visual triaging and maintenance:

```powershell
magi ui                       # launch and open the local dashboard in default browser (http://127.0.0.1:8000)
magi ui --port 8080 --no-open # custom port without auto-opening the browser
```

Features 7 functional panels: Dashboard (global sync & KB registry), Melchior (epistemic state & claims), Balthasar (Beads tasks), Casper (hybrid search lab), Radar (digest reader), Operations & Danger Zone (live SSE terminal & double-confirmation actions), and Documentation.

The **⚡ MAGI MODE** toggle in the top bar switches to an EVA/NERV tactical theme: a live tri-monolith HUD (MELCHIOR·1 / BALTHASAR·2 / CASPER·3 core states + sync ratio), CRT scanlines, honeycomb field, hazard-striped Danger Zone, and a boot synchronization sequence. The dashboard binds to `127.0.0.1` only, enforces a trusted-Host allowlist, and emits no CORS headers.

---

## 5. Migrating from Wikify (existing users)

MAGI is a full rebuild of Wikify: the script collection became a unified CLI, task state moved to Beads, and hybrid retrieval, claim provenance, and the literature radar are new. **Your data is fully compatible** — `raw/`, `wiki/`, `inbox/` formats are unchanged.

### 5.1 Migration steps (three commands)

```powershell
# 1. One-line install of the new stack (the §2.1 script; magi setup also
#    detects legacy copies and warns about them)
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. Delete the old installed copies (stale SKILL.md files mislead agents
#    into calling script paths that no longer exist)
magi setup --remove-legacy

# 3. Migrate ALL topics in one go from the hub root (non-destructive):
cd <your-KnowledgeHub>
magi migrate
#    ↳ per topic: adds CLAUDE.md / AGENTS.md / config.yaml / scratch/ (reusing
#      the old title & scope from config.md), rebuilds graph.db (now with
#      claims/evidence tables) and _index.md; raw/ and wiki/ untouched.
#      Run inside a single topic dir to migrate just that topic.

# Finish up: `magi pm init` at the hub root; `magi index` in each topic; `magi sync` to verify.
```

### 5.2 What changed

| Old (Wikify) | New (MAGI) |
|---|---|
| `install.ps1` / `install.sh` **copying** `skills/`+`bin/` into agent dirs | same filenames are now the **one-line bootstrap installer** (uv + CLI + `magi setup`, §2.1); skills ship via host plugins |
| `python <BIN>/llm-wiki.py lint --fix <dir>` | `magi lint --fix <dir>` |
| `python <BIN>/llm-wiki.py graph <dir>` | `magi graph build <dir>` |
| `python <BIN>/query-graph.py "<SQL>"` | `magi graph query "<SQL>"` |
| `python <BIN>/search-wiki.py <regex> <files>` | `magi grep <regex> <files>`; semantic search is new: `magi index` + `magi search` |
| `python <BIN>/ingest_helper.py --file ...` | `magi ingest add --file ...` (all ingestion scripts live under `magi ingest *`) |
| `semantic_linker.py` | `magi link` |
| `verify_claims.py` | `magi verify` (v2: `--json`, whitespace-normalized matching, `--fetch-web`) |
| manual `requirements.txt` install | dependencies ship with the CLI |
| progress tracked in `log.md` | Beads (`bd`) task graph; `log.md` is now a human-readable narrative |
| `~/.config/llm-wiki/config.json` (hub path) | `~/.config/magi/config.json` (the legacy path is still read as a fallback) |
| ripgrep dependency | no longer needed |

---

## 6. Obsidian integration

Open the **specific topic workspace directory** in Obsidian (not the hub root). Under Settings → Files and links → Excluded files, add these two regexes so the graph shows only pure knowledge cards:

```regex
/(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
```

```regex
/^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
```

---

## 7. Development

```powershell
git clone https://github.com/Misaka16384/magi.git ; cd magi
uv venv && uv pip install -e .
.venv\Scripts\python.exe tests\smoke_test.py     # end-to-end smoke (with regression locks)
```

Roadmap and handoff notes: [ROADMAP.md](./ROADMAP.md).
