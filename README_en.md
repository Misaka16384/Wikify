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

### 2.1 The `magi` CLI (required)

Requires **Python 3.10+** and [uv](https://docs.astral.sh/uv/) (or pipx):

```powershell
git clone https://github.com/Misaka16384/magi.git
cd magi
uv tool install .            # or: pipx install .
magi --version               # magi 0.1.0
```

Upgrade:

```powershell
git pull && uv tool install . --force --reinstall
```

> Package name `magi-research`, command name `magi`. Not on PyPI yet — install from the repo.

### 2.2 Beads (`bd`, strongly recommended)

Work state lives in [Beads](https://github.com/gastownhall/beads); `magi pm init` provisions six research issue types (question / survey / derivation / computation / experiment / review).

- **Windows**: `irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex` (or grab `beads_*_windows_amd64.zip` from [Releases](https://github.com/gastownhall/beads/releases) and put `bd.exe` on PATH)
- **macOS / Linux**: see the [official install docs](https://github.com/gastownhall/beads/blob/main/docs/getting-started/installation.md) (Homebrew / npm / go install)

MAGI degrades gracefully without `bd` (sync will hint at installing it).

### 2.3 Ollama (recommended)

Vector retrieval (`magi index` / `magi search` hybrid mode, `magi link` semantic linking) and local OCR use a local Ollama:

```powershell
ollama pull qwen3-embedding:0.6b   # embeddings
ollama pull glm-ocr                # local OCR (optional; MinerU cloud also supported)
```

When Ollama is unreachable, retrieval degrades to BM25-only and vectors can be backfilled later.

### 2.4 System-level external tools (as needed)

| Tool | Used by | Notes |
|---|---|---|
| **Pandoc** | `magi ingest tex` (LaTeX → Markdown) | Windows `pandoc-crossref.exe` is vendored in `vendor/windows/` (add to PATH or set `tools.pandoc_crossref_path` in config.yaml) |
| **Poppler** (`pdftoppm`/`pdfimages`) | local OCR pipeline PDF rendering | `scoop/choco/brew/apt install poppler` |
| **pdflatex** (optional) | deep math validation | falls back to `pylatexenc` when absent |

(The historic ripgrep dependency is gone.)

### 2.5 Installing the skills (teaching your agent)

Every host shares the same `skills/*/SKILL.md` tree:

- **Claude Code** (recommended: plugin; ships a SessionStart hook that runs `magi sync` automatically):
  ```bash
  claude plugin marketplace add Misaka16384/magi
  claude plugin install magi
  ```
  Skills appear namespaced as `/magi:wiki_ingest` etc.; for local dev use `claude plugin install <repo-dir>`.
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
| Maintain | `wiki_hub_manager` | archive / restore topics (`magi hub archive/restore`) |

### The literature radar (`magi radar`)

After configuring the `radar:` section of the workspace `config.yaml` (arXiv categories, seed papers, your own papers):

```powershell
magi radar harvest              # manual harvest: S2 recommendations ∪ new arXiv listings → inbox/radar/<date>-digest.md
magi radar install-schedule     # daily scheduled harvest (Task Scheduler / launchd; --uninstall to remove)
magi radar citation-gap         # scout recent papers that arguably should cite yours (four-layer funnel, human-review queue)
```

Deterministic harvest runs at night; the `radar_review` skill does LLM triage in your next session — `magi sync` will point at pending digests.

---

## 5. Migrating from Wikify (existing users)

MAGI is a full rebuild of Wikify: the script collection became a unified CLI, task state moved to Beads, and hybrid retrieval, claim provenance, and the literature radar are new. **Your data is fully compatible** — `raw/`, `wiki/`, `inbox/` formats are unchanged.

### 5.1 Migration steps

```powershell
# 1. Delete the old installed copies (important: stale SKILL.md files will
#    mislead agents into calling script paths that no longer exist).
#    Remove the skills/wiki_* and bin/ folders that install.ps1 copied into
#    ~/.claude (or your project's .claude / .agents).

# 2. Install the new stack (§2): magi CLI + host plugin.

# 3. In each old topic workspace, run (non-destructive):
cd <your-old-topic-dir>
magi migrate
#    ↳ adds CLAUDE.md / AGENTS.md / config.yaml / scratch/ (reusing the old
#      title & scope from config.md), rebuilds output/graph.db (now with
#      claims/evidence tables) and _index.md; raw/ and wiki/ are untouched.

# 4. Enable work-state at the hub root and build each topic's search index:
magi pm init
magi index

# 5. Verify:
magi sync
```

### 5.2 What changed

| Old (Wikify) | New (MAGI) |
|---|---|
| `install.ps1` / `install.sh` copying `skills/`+`bin/` | `uv tool install .` + host plugin (§2.5) |
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
