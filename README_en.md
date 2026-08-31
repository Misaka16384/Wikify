# MAGI

*[English](README_en.md) | [中文](README.md)*

[![PyPI](https://img.shields.io/pypi/v/magi-research?label=PyPI)](https://pypi.org/project/magi-research/)
[![Downloads](https://static.pepy.tech/personalized-badge/magi-research?period=month&units=abbreviation&left_color=grey&right_color=blue&left_text=downloads/month)](https://pepy.tech/project/magi-research)
[![Python](https://img.shields.io/pypi/pyversions/magi-research)](https://pypi.org/project/magi-research/)
[![License](https://img.shields.io/pypi/l/magi-research)](LICENSE)

**MAGI** is an agent-native research project environment: the human pilots, the LLM agent is the mecha, and the deterministic `magi` CLI is the restraint armor — the higher the sync ratio, the faster the science. It ingests academic papers (PDF/LaTeX) into Obsidian-compatible concept cards and manages the full research state through a three-core architecture:

| Core | State | Carried by | Question answered |
|---|---|---|---|
| **MELCHIOR** | Epistemic (knowledge) | concept/reference cards + SQLite knowledge graph + claim/evidence provenance | What do we know, and why is it credible? |
| **BALTHASAR** | Intent (research) | propositions, questions and lines in `threads/` + `decisions.md` (mechanical chores go to [Beads](https://github.com/gastownhall/beads)) | What are we doing, and what's next? |
| **CASPER** | Retrieval | local hybrid search (FTS5 BM25 + sqlite-vec vectors + RRF) | What should I read right now? |

Enter any project and run **`magi sync`** — it reports the **sync ratio**, three-core status, and concrete restore hints. `magi radar` is the literature radar: scheduled discovery of relevant new papers, plus scouting for recent papers that arguably should cite yours but don't. One shared skills tree serves Claude Code / Codex / Antigravity / opencode and other CLI agent hosts — `magi install` puts it where each of them looks.

Full syntax for any command: `magi <command> --help`; overview: `magi --help`.

---

## Start here

```powershell
pipx upgrade --install magi-research           # install or upgrade — safe to re-run
mkdir my-topic ; cd my-topic ; magi init ; magi install
```

That is the whole setup. `magi init` scaffolds the project; `magi install` puts the skills, the protocol and the session hooks into **every** agent CLI it detects — it does not ask, because they do not conflict.

Now open your agent there and **say what you want** — "ingest the papers in inbox", "compile the backlog", "what should I work on?". The skills load themselves by description; you do not have to remember any of them.

From the terminal, **`magi next`** is the same question and answers it from the notes rather than from a model. **`magi guide`** is the full manual. Everything else — ingest, search, the graph, the WebUI — is in §3 below, and `magi --help` fits on one screen.

---

## What a day looks like

The whole system is one loop. Both the terminal and the browser walk all of
it — **no step needs the other one**.

| What you want | Terminal | Browser (`magi ui`) |
|---|---|---|
| What now? | `magi next` | top of the dashboard |
| Open a proposition / question / line | `magi thread new <slug> --kind proposition --title … --purpose …` | "Open a new one" |
| Something happened | `magi thread post <slug> --text …` | the box on the note |
| The conclusion moved | `magi thread status <slug> supported --text …` | the status buttons |
| I decided this | `magi decide --about <slug> --text …` | "Record this as my decision" |
| Have it checked | `magi review <slug>` | "Have this reviewed" |
| Take in a paper | drop it in `inbox/`, then `magi ingest auto` | "Pick these up" |
| Find something | `magi search "…"` | the search tab |
| This line is finished | `magi close <line> --text …` | "End this line" |
| Written up — publish | `magi publish <draft> --line <line>` | "Publish and file" |
| Done for now | `magi sync --close` | "End of session" on the dashboard |

**Only two are worth memorising**: `magi next` asks what is next, and
`magi sync --close` ends the session. The rest it tells you when you need
them, command line and all.

With the skills installed it is shorter still: say "what should I do next",
"take this paper in", "I don't buy this one" to your agent and it reaches for
these itself.

> A review costs one external model call. `magi review` says who it will ask
> and which model before it spends, and reports the week's usage after; the
> browser shows the same before you press. The weekly budget is
> `research.weekly_calls` — spent, it refuses to start rather than quietly
> doing less.

---

## 🌟 Showcase

### MAGI MODE — the WebUI tactical theme

`magi ui` opens a local web console (default `http://127.0.0.1:8737`) with three themes: Institute light / dark, and the headline **EVA "MAGI MODE"** — a full NERV command-deck visual system with two alert states, **red combat** and **blue quiet-watch**:

![MAGI MODE, red combat state](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-magi-red.jpg)
*Red combat: the tri-sage HUD, full-bleed EVA artwork, liquid-glass panels, and an amber breathing glow hugging the viewport edges.*

![MAGI MODE, blue quiet-watch state](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-magi-blue.jpg)
*Blue quiet-watch: the same HUD as a true light mode — white-frosted glass, dark cyan ink, a cyan edge glow.*

![Liquid glass](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-glass.jpg)
*iOS-material liquid glass: the artwork reads through every panel while text stays legible; the ◐ tuner (bottom-right) adjusts blur / opacity / CRT scanlines live.*

![Knowledge graph view](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-graph.jpg)
*An Obsidian-style force-directed graph: drag to arrange, scroll to zoom, hover to focus a neighbourhood, click a node to read its card — unresolved wikilinks render as ghost nodes.*

![Card preview](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-preview.jpg)
*Click any node in the graph, or any search result, and the card opens where you are: formulas typeset by KaTeX, `[[links]]` you can follow, figures and mermaid diagrams drawn in place, an outline and the graph links beside the prose. A search hit scrolls straight to the passage it matched.*

<img src="https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-tuner.jpg" width="340" alt="The ◐ material tuner">

*The ◐ tuner: blur, opacity and CRT scanlines on live sliders, with the backdrop picker underneath — pin the artwork you want, or leave it unpinned and let it rotate by window aspect.*

- Light/dark and MAGI MODE act **independently**: light base → blue state, dark base → red state; ☀︎/☽ switches the alert state inside the mode
- Backdrops are aspect-matched to your screen and rotate on tab switches with a smooth crossfade — or pin one (or a few) from the thumbnail picker in the ◐ tuner. Fully replaceable via `~/.config/magi/ui-backgrounds/{blue,red}/`
- Every animation respects `prefers-reduced-motion`; the UI is bilingual (中 / EN) with one click

### The project itself

![Knowledge Graph Visualization](https://raw.githubusercontent.com/Misaka16384/magi/main/graph.png)
*An automatically generated dense semantic graph of physics and math concepts.*

![Compiled Literature Card](https://raw.githubusercontent.com/Misaka16384/magi/main/note1.png)
*A clean reference card compiled from a messy PDF.*

![Math & Concept Extraction](https://raw.githubusercontent.com/Misaka16384/magi/main/note2.png)
*Proofs and lemmas extracted and formatted from LaTeX sources.*

---

## 1. Architecture: CLI, skills, and hosts

```text
You (the pilot)
  └─ Claude Code / Codex / Antigravity / opencode  (the mecha: reasoning, writing, judgment)
       ├─ skills (ship with the CLI) — teach the agent WHEN and WHY to run each pipeline
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

The script does everything: installs [uv](https://docs.astral.sh/uv/) if missing, installs `magi-research` from PyPI (Python included — no preinstall needed), then runs **`magi setup`**: installs [Beads](https://github.com/gastownhall/beads) (`bd`), pulls the Ollama embedding model (when Ollama is present), registers the Claude Code plugin (when `claude` is present), reports which agent CLIs it found, detects legacy Wikify leftovers, and prints an environment doctor table. **Idempotent — re-run to upgrade.**

Check your environment any time:

```powershell
magi setup --check
```

`magi setup` flags: `--no-beads` / `--no-models` / `--no-plugin` / `--no-skills` (skip the agent-CLI report) / `--remove-legacy` (delete detected legacy copies).

The last four doctor rows are the agent CLIs on your machine (claude / codex / agy / opencode): whether each is installed, and how many skills the current project has for it. **`magi setup` does not install skills for you** — they go in per project, see §2.4.

**Want the classic Wikify experience (the compiled cards only, no task management)?** Use `magi setup --kb-only`: skips the Beads install and `magi sync` stops suggesting task tracking (the BALTHASAR core shows disabled and is excluded from the sync ratio). Restore any time with `magi setup --full`. Everything else (radar etc.) is invoke-only — unused features stay invisible.

### 2.2 Manual install (fallback)

<details>
<summary>Expand manual steps</summary>

**CLI** (pipx first; use uv when there is no Python 3.10+, since it brings its own. MAGI never calls either again after install):

```powershell
# One command for install and upgrade, idempotent — a no-op when already current
pipx upgrade --install magi-research    # needs a Python 3.10+ already on the machine
                                        # (--install wants pipx >= 1.5; on older pipx use
                                        #  pipx install magi-research, then pipx upgrade)

# Alternative: uv, which brings Python 3.12 — also one command for both
uv tool install --force magi-research

# unreleased changes: uv tool install --force git+https://github.com/Misaka16384/magi
# or local dev: git clone ... && cd magi && uv tool install .
```

**Beads**: Windows `irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex`; macOS/Linux see the [official docs](https://github.com/gastownhall/beads/blob/main/docs/getting-started/installation.md). MAGI degrades gracefully without `bd`.

**Ollama models**: `ollama pull qwen3-embedding:0.6b` (vector search); `ollama pull glm-ocr:q8_0` (local OCR, optional). **You never run `ollama serve` yourself** — a local Ollama that is merely stopped gets started the first time something needs it (once per process; `ollama.autostart` in `config.yaml` is on by default, and `MAGI_NO_OLLAMA_AUTOSTART` turns it off). Retrieval only degrades to BM25-only when Ollama really is not installed, or the configured endpoint is a remote one that is down.

</details>

### 2.3 Optional external tools

**MAGI runs without any of these.** Each one turns on a specific feature; not having it is not a fault, and `magi setup --check` will not paint it red.

Run `magi setup` and it asks about each one, with the official download link. Say no and it stops being mentioned. Change your mind later with `magi setup --optionals`.

| Tool | What it unlocks | Where to get it |
|---|---|---|
| **Ollama** | semantic (vector) search, and local offline OCR | https://ollama.com/download |
| **Pandoc** | the LaTeX and arXiv-HTML ingest routes — the two best-fidelity ways in | https://pandoc.org/installing.html |
| **Poppler** (`pdftoppm`) | local OCR page rendering (needed alongside Ollama) | https://poppler.freedesktop.org/ |
| **pdflatex** | deep math validation — checks a formula actually compiles; falls back to `pylatexenc` when absent | https://www.tug.org/texlive/ |
| **MinerU** (a hosted service, not a binary) | cloud PDF conversion, strong on layout and formulas | https://mineru.net/ |

`pandoc-crossref` is optional — without it cross-references degrade, nothing fails. If you installed from a source checkout, the Windows build is in `vendor/windows/`: add it to PATH or set `tools.pandoc_crossref_path` in config.yaml. A pipx or uv install does not carry it (a 19 MB Windows binary has no business shipping to every platform); get it from https://github.com/lierdakil/pandoc-crossref/releases when you want it. A MinerU token goes in your project's config.yaml under `ocr.mineru_api_token`.

(The historic ripgrep dependency is gone.)

### 2.4 Installing the skills (teaching your agent)

All 8 skills ship inside the wheel (`magi/skills/*/SKILL.md`), so **one command inside your project** installs them into every agent CLI on your machine — no repo clone needed:

```powershell
cd <your project>
magi skills install                   # into this project; lists the CLIs it found and asks
magi skills install --host codex      # name one and skip the question
magi skills install --host auto       # every CLI it detects
magi skills where                     # per CLI: where it reads, what is installed, how it fires
magi skills install --scope global    # machine-wide (rarely useful — these are project skills)
```

**Not global by default**: these skills revolve around one research project, and installing into the project also lets them travel with the repo to collaborators.

| Host | Global | Project | How it fires |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/skill-name` (`/magi:skill-name` via the plugin), and auto by description |
| **Codex** | `~/.agents/skills/` (plus `~/.codex/skills/`) | `<repo root>/.agents/skills/` | `$skill-name`, or auto by description |
| **Antigravity (agy)** | `~/.gemini/config/skills/` | `<repo root>/.agents/skills/` | auto by description; `/skills` browses |
| **opencode** | `~/.config/opencode/{commands,skills}/` | `.opencode/{commands,skills}/` | `/skill-name` (commands) + auto by description (skills); both are installed |

> Not every CLI has slash commands (Codex uses `$`, agy fires on description only). The habit that works everywhere: just say what you want — "ingest the papers in inbox". `.agents/skills/` is the cross-agent convention Codex and agy share, so one project install covers both; opencode reads it too but gets its own `.opencode/` copies, which is where the slash commands come from.

**Claude Code plugin route** (run by the one-line installer; coexists with the above):

```powershell
claude plugin marketplace add Misaka16384/magi && claude plugin install magi
```

---

## 3. Quick start (5 minutes)

```powershell
mkdir quantum-toys ; cd quantum-toys
magi init --name "Quantum Toys" --scope "quantum phenomena in toy models"
# ^ creates raw/ wiki/ threads/ drafts/ decisions.md, AGENTS.md (managed block), config.yaml
magi install                 # skills + protocol block + stop gate (every CLI it finds, no prompt)
magi pm init                 # optional task tracking. It hands this directory to bd, which
                             # git-inits and commits under your own identity — it says so
                             # and asks before it does

magi sync --fix              # sync ratio + three cores, and run the repairs it suggests
```

```text
MAGI SYSTEM ONLINE — sync ratio 59.2%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 1
|- BALTHASAR (intent)     2 lines · 1 open · 1 waiting on you · 1 unrecorded
`- CASPER    (retrieval)  index missing · 0 chunks · vectors 0/0
  -> 1 source(s) in raw/ are not compiled yet — run the compile skill
  -> magi index   # build the retrieval index
```

> **BALTHASAR reports research state, not chores.** `1 waiting on you` is a decision only a person can make; `1 unrecorded` is something that happened and nobody wrote down — that one is bookkeeping debt, and every number below it is computed from notes that are currently wrong, which is why `magi next` puts it first. The score is cleanliness, not progress: six open propositions with nothing unrecorded is perfectly healthy.
>
> The sync ratio moves with how many cores are ready. Follow the hints in order; a low number on a new project is not a misconfiguration.

Then drop PDFs / LaTeX / notes into `inbox/` and tell your agent to ingest them (or invoke `/magi:ingest`).

> 📖 **The full user guide ships with the CLI** — three entrances, one text:
>
> ```powershell
> magi guide                                # list the twelve chapters
> magi guide ingest                         # read one
> magi guide --search "no project found"    # paste an error verbatim
> magi guide --symptoms                     # the symptom -> cause -> fix index
> ```
>
> Or `magi ui` → **Docs & Help** → **User Guide** (with chapter navigation), or read [`guide.en.md`](./src/magi/docs/guide.en.md) directly. Twelve scenario chapters (get it running / install / migrate / build a project / ingest / compile / graph tuning / search / writing / radar / dashboard / troubleshooting), each stating what you should see and what to do when you don't. Stuck? Have your agent run `magi guide --search "<the error>"` — the manual ships with the CLI, no network needed.

---

## 4. The research lifecycle (skills overview)

Trigger via slash commands in your agent (namespaced `magi:` under the Claude Code plugin) or plain natural language:

| Phase | Skill | What it does |
|---|---|---|
| Entry | `magi` | Run `magi next`, do what it says, call the skill it names. Start here when you do not already know what you are doing |
| Ingest | `ingest` | PDF/LaTeX/link/DOI/citation → `raw/`, routed down a ladder: arXiv HTML → LaTeX source → the PDF's own text layer → MinerU cloud → local OCR. **Native vision is not on the ladder** — it bills per page and has burned a user's entire weekly quota, so it runs only after you have seen the page count and said yes |
| Compile | `compile` | raw sources → reference and concept cards, and mines the concepts a thin card left implicit |
| Tidy | `tidy` | Repairs what the mechanical passes cannot: LaTeX broken by conversion, sprawling tags, two concept cards that are one concept |
| Ask | `ask` | Hybrid retrieval + graph traversal + strict citation. When retrieval finds nothing it says so instead of filling the gap |
| Research | `research` | Several angles at once, verified, landing as propositions in `threads/` plus at most one synthesis. Contradiction-hunting is the same skill with an adversarial brief, not a separate one |
| Draft | `draft` | Write in `drafts/`: ground in the project, export citations with `magi bib`, check claims, formulas and links |
| Radar | `radar_review` | Triage a radar digest — the score is a rank, not a verdict; the judgement is yours |

A single-command wrapper is not a skill any more: `magi init` scaffolds,
`magi lint --fix` repairs, `magi graph build` builds the graph, `magi link`
links, `magi guide` reads the manual. The boilerplate — tool capabilities, who
may ask a human, what to do with nobody there — is stated once, in the
`AGENTS.md` managed block.

### Searching across projects

**`magi search` reads the project you are standing in, and nothing else** unless
you say otherwise.

It used to federate by default, and the result was somebody searching for a note
they had written ten minutes earlier and getting a page of another project's
research — because every `magi init` registers itself and the registry's
searchable flag is machine-wide, so that cross-project set grew on its own and
nobody ever chose it.

Two questions, two homes:

```powershell
magi kb list                     # every project registered on this machine
magi kb disable <name>           # this project may not be read from elsewhere
magi search "..."                # default: this project only
magi search "..." --scope all    # plus the ones research.search_projects names
                                 # (naming none means every enabled project)
magi search "..." --kb <name>    # one, by name
```

- **`enable` / `disable`, in the registry, machine-wide** — whether a project
  *may* be read from elsewhere at all.
- **`research.search_projects`, in the project's own config.yaml** — which ones
  *this* project reads.

Searching stops at your own project, but the results name the others that are
available, so nothing disappears. `magi kb register <path>` registers a project
by hand; `unregister` removes the entry and never a file. In the WebUI, a hit tagged `[kb:name]` opens its card in place like any other — the preview request carries the source project along, so there is nothing to switch to first.

> Search tips: `--path 'raw/papers/2026-*<slug>*'` narrows semantic search to one paper; Chinese and English queries both work (CJK bigram tokenization feeds BM25, and the embedding model handles cross-lingual matching on the vector side).

### Writing & citations (`drafts/` + `magi bib`)

Drafts are first-class citizens: they live in `drafts/`, are indexed for search (collection `drafts`), but stay out of the graph and sync ratio. Citations export straight from reference cards:

```powershell
magi bib pretko-2020            # reference-card frontmatter → BibTeX entry
magi bib --all -o drafts/refs.bib
magi bib pretko-2020 --fetch    # pull arXiv's official BibTeX when the card has an arxiv_id
```

`magi ingest tex` preserves the source package's `.bib`/`.bbl` next to the raw markdown (`raw/papers/<slug>.bib`), and writes any arXiv ID found in the filename into frontmatter `arxiv_id:` for the radar. See the `draft` skill for the full workflow.

> Claims boundary: `magi verify`'s `verified` means **quote-existence verification** (the quote really appears verbatim in the source, with whitespace/ligature/full-width-punctuation-robust matching) — it does not judge whether the claim and the quote agree semantically; that layer belongs to LLM/human review (`magi claims verify` is an alias of the same command).

### The literature radar (`magi radar`)

After configuring the `radar:` section of the project `config.yaml` (arXiv categories, seed papers, your own papers):

```powershell
magi radar harvest              # manual harvest: S2 recommendations ∪ new arXiv listings → inbox/radar/<date>-digest.md
                                # (candidates sorted by cosine relevance to the project's embedding centroid,
                                #  each annotated with a relevance score; set radar.min_relevance to filter)
magi radar install-schedule     # daily scheduled harvest (Task Scheduler / launchd; --uninstall to remove)
magi radar citation-gap         # scout recent papers that arguably should cite yours (four-layer funnel, human-review queue)
```

Deterministic harvest runs at night; the `radar_review` skill does LLM triage in your next session — `magi sync` will point at pending digests.

### Local WebUI Dashboard (`magi ui`)

MAGI includes a zero-build, Claude-styled local inspection and operations dashboard (FastAPI + native SPA) for visual triaging and maintenance:

```powershell
magi ui                       # launch and open the local dashboard (default http://127.0.0.1:8737; auto-probes 8738-8746 when busy)
magi ui --port 8080 --no-open # custom port without auto-opening the browser
```

Features 7 functional panels: Dashboard (the two things you are supposed to look at — **decisions waiting on you** and **where each line stands** — plus a box that types straight into `inbox/notes.md` and a **looking back** line with your prediction record; below them the sync ratio, one-click hints, KB registry and config.yaml fields), Melchior (threads and the single-note forum view, the feed, epistemic state, claims, graph SQL, BibTeX copy, drafts; the graph now draws `threads/` too, filtered to the knowledge, to the research state, or down to the skeleton), Balthasar (Beads tasks), Casper (hybrid search lab with federation/collection/path filters), Radar (digest reader + review actions: mark reviewed / accept to inbox / create reading task), Operations & Danger Zone (server-side ops whitelist, type-to-confirm, live SSE terminal, persisted job history), and Documentation. The API is field-identical to the CLI's `--json` contracts.

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

# 3. One command at the old hub root (non-destructive, and it finishes the job):
cd <your-old-KnowledgeHub>
magi migrate --dry-run   # says what would change and writes nothing
magi migrate
#    ↳ per project: adds CLAUDE.md / AGENTS.md / config.yaml / scratch/ (reusing
#      the old title & scope from config.md), carries the old config.yaml's
#      token/models/thresholds across, rebuilds graph.db (now with
#      claims/evidence tables) and _index.md; raw/ and wiki/ untouched.
#      Then runs magi pm init and a magi sync --fix per project (index, backlog).
#      --minimal migrates only; run it inside one project to migrate just that one.
#      Run inside a single project dir to migrate just that one.

# Finish up: `magi install` in each project (skills + protocol + stop gate); `magi index`;
# `magi sync` to verify. The hub's own wikis.json / topics/ / log.md are inert afterwards.
```

### 5.2 What changed

| Old (Wikify) | New (MAGI) |
|---|---|
| `install.ps1` / `install.sh` **copying** `skills/`+`bin/` into agent dirs | same filenames are now the **one-line bootstrap installer** (uv + CLI + `magi setup`, §2.1); skills ship inside the package and install per project with `magi skills install` (§2.4) |
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

Open the **specific project directory** in Obsidian (not the hub root). Under Settings → Files and links → Excluded files, add these two regexes so the graph shows only pure knowledge cards:

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

