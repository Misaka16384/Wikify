# MAGI User Guide

From a fresh install to a working library you can search, cite, and write from.

Every chapter follows the same rhythm: **what to do → how to do it → what you should see → what to do if you don't**. Jump around anytime with the sidebar; use `Ctrl+F` to search the full page directly; every command block has a one-click copy button in its corner.

---

## Get it running once {#start}

MAGI has three layers, and their jobs don't overlap:

| Layer | What it is | How you use it |
|---|---|---|
| **magi CLI** | Every deterministic operation: ingest, graph-build, search, verify, tasks, radar | Type it in a terminal, or have an agent type it for you |
| **skills** | Teach the agent when and why to call each pipeline | Trigger with a sentence in Claude Code / Codex |
| **workspace** | Knowledge on disk: `raw/` `wiki/` `output/` `drafts/` | View directly with Obsidian, an editor, or the dashboard |

An agent's context is disposable — **state always lives on disk**. So any step you interrupt can pick up right where it left off.

> [!WARN]
> **The agent isn't optional.** Going from raw sources in `raw/` to concept cards in `wiki/` is a step of understanding and synthesis — there's no CLI command for it. Only the `wiki_compile` skill, driving an LLM, can do it. Install just the CLI without connecting an agent host, and you can ingest papers and run keyword searches, but you'll never get concept cards, a knowledge graph, or cited Q&A. Section 2.4 covers how to connect one.

### Three ways to get started

**① Brand-new user** — install per Chapter 2, then:

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init                # hub (wikis.json registry)
magi pm init                 # task system (git-inits this directory)

mkdir topics\quantum-toys ; cd topics\quantum-toys
magi init --name "Quantum Toys" --scope "Quantum phenomena in toy models"
magi skills install          # give this workspace's skills to your agent CLI (it asks which)

magi sync --fix                    # sanity check: sync ratio + three-core status + next-step hint
```

**② Existing Wikify user** — leave your data as-is; jump straight to Chapter 3, three commands to migrate.

**③ Just want to try it** — skip the hub; `magi init` works right away in any empty directory, and you can fold it into a hub later with `magi hub register <slug>`.

### How to read this manual {#howto-read}

The same content has three entrances — take whichever is closest to hand:

| Entrance | Best for | How |
|---|---|---|
| **Dashboard** | Reading it through, working alongside it | `magi ui` → Docs & Help → User Guide |
| **Terminal** | You're stuck on a command right now | `magi guide` lists chapters; `magi guide ingest` reads one |
| **Ask your agent** | You'd rather not look it up yourself | Paste the error into the chat and let it search |

The three that earn their keep in a terminal:

```powershell
magi guide                          # List every chapter (number + anchor + one-line summary)
magi guide graph                    # Read a chapter by number 7, anchor graph, or part of its title
magi guide --search "no workspace found"   # Full-text search — paste the error verbatim
magi guide --symptoms               # The whole symptom -> cause -> fix index
```

`--json` is the machine format for agents; `--lang en` switches language.

**Let the agent do the diagnosing**: the repo ships a `magi_guide` skill, installed with the plugin. Paste the error as-is, or just say "use magi_guide," and it will search the manual by symptom, read the relevant chapter, confirm the current state with `magi sync` / `magi setup --check`, and hand you the exact command the manual prescribes — instead of inventing a flag from memory.

> [!NOTE]
> Every command in this manual is checked against the real CLI, and a test keeps it from drifting. That makes an agent quoting the manual considerably more reliable than an agent recalling one — for anything MAGI-related, it's worth telling it to look it up first.

### How to read `magi sync`

`magi sync` is the first command you run every time you sit down, and the first command you run whenever you're stuck:

```text
MAGI SYSTEM ONLINE — sync ratio 33.3%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     beads offline
`- CASPER    (retrieval)  index missing · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the wiki_ingest skill to start building the library
  -> magi pm init   # initialize beads at the hub root
  -> magi index   # build the retrieval index
```

The three cores are knowledge, work state, and retrieval. **The last line, the one starting with `->`, is what to do next** — do it, or let it do it:

```powershell
magi sync --fix             # graph, index, backlog sync, task store — whatever it just asked for
magi sync --fix --dry-run   # see which of them first
```

`--fix` only runs the deterministic, repeatable steps. Anything needing judgment — installing Beads, ingesting sources, reviewing a radar digest — it just lists for you.

Sync ratio is a weighted average of the three cores' readiness (only cores that currently apply are counted):

- **MELCHIOR** = 0.55 graph freshness + 0.25 compile backlog + 0.20 claim health
- **BALTHASAR** = 0.6 task-store reachability + 0.4 state readability (excluded entirely in `--kb-only` mode)
- **CASPER** = 0.7 index freshness + 0.3 vector coverage

> [!NOTE]
> Sync ratio isn't a score for "how much knowledge you have." An empty library can still get a perfect MELCHIOR score — it only penalizes **staleness, backlog, and unverified claims**, never "hasn't started yet." So a freshly created library showing 33.3% is normal: that's "only the knowledge core is online, out of three." Run `magi pm init` and `magi index` and it climbs from there.
> Outside of any workspace, sync ratio shows blank rather than 0 — it won't make up a number for you.

---

## Installation {#install}

### One-line install (recommended) {#install-oneline}

No Python needed, and **no git either** — the package comes from PyPI. `git` only matters later: registering the Claude Code plugin, and `magi pm init` (Beads git-inits the task store). If you want those, run `winget install Git.Git` on Windows, or use your platform's package manager elsewhere.

**Windows (PowerShell)**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
```

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
```

The script does three things in order:

1. Install [uv](https://docs.astral.sh/uv/) first, if it's missing;
2. `uv tool install --force --python 3.12 magi-research` — from PyPI; uv brings its own Python 3.12, so **you don't need Python pre-installed**;
3. Run `magi setup`: install Beads (`bd`), pull the Ollama embedding model, register the Claude Code plugin, report which agent CLIs it found, check for leftover legacy Wikify installs, and print a health-check table at the end.

**Idempotent**: rerunning the same command is how you upgrade.

> [!EXPECT]
> The terminal shows an `=== MAGI environment ===` health-check table, and `magi --version` prints a version number.

> [!FIX]
> - **`magi` not found**: `uv tool update-shell` only edits config files — your current window's PATH is still the old one. **Open a new terminal** (both install scripts remind you of this at the end). If it still doesn't work, manually add `~/.local/bin` (Windows: `%USERPROFILE%\.local\bin`) to PATH.
> - **`note: git not found`**: just a warning — the install continues. Install git when you want the Claude Code plugin or the task store.
> - **`magi setup reported issues`**: `magi setup` crashed outright (not a single component failing). The CLI itself is installed — rerun `magi setup` to see the real error, or `magi setup --check` for just the current state.
> - **Whether a component installed is in the table, not the exit code**: `magi setup` always exits 0. A failed Beads / Ollama / plugin step shows up only in the `=== setup results ===` rows.
> - **Corporate network blocks GitHub**: use the manual install below, or set up a proxy first and rerun.

### Manual install, upgrade, uninstall {#install-manual}

```powershell
uv tool install magi-research           # install (pipx install magi-research works too)
uv tool install --force magi-research   # upgrade
uv tool uninstall magi-research         # uninstall
uv tool list                            # see what version is installed

# To try changes that are not released yet:
uv tool install --force git+https://github.com/Misaka16384/magi
```

Health-check anytime after installing:

```powershell
magi setup --check
```

`magi setup` flags:

| Flag | What it does |
|---|---|
| `--check` | Health-check only — installs nothing, deletes nothing |
| `--no-beads` | Skip Beads install |
| `--no-models` | Skip pulling Ollama models |
| `--no-plugin` | Skip Claude Code plugin registration |
| `--no-skills` | Skip the agent-CLI report (`magi setup` never installs skills for you) |
| `--remove-legacy` | Delete any legacy Wikify copies it finds (the only destructive flag) |
| `--kb-only` / `--full` | Switch between "knowledge-base-only" and "full" mode |

> [!TIP]
> Just want a knowledge base, no task management? `magi setup --kb-only` skips Beads; `magi sync` then shows the BALTHASAR core as disabled and excludes it from the sync ratio. The mode is stored in `~/.config/magi/settings.json` — restore it anytime with `magi setup --full`.

### Install once globally, or per project {#install-scope}

This is the one people most often get backwards. **You only need one global CLI install — it's the workspace that's per-project.**

| Thing | Where it lives | How many |
|---|---|---|
| `magi` CLI | User-level (`uv tool install`), on PATH | One per machine |
| skills | **Inside each workspace**, one directory per host (`magi skills install`) | One set per topic |
| workspace | Your topic directory | One per topic |
| Global config & registry | `~/.config/magi/` (on Windows: `C:\Users\<you>\.config\magi\`, **not** AppData) | One per machine |

Install the CLI once; after that, starting a new topic only takes `magi init` + `magi skills install`.

> [!WARN]
> A true in-project install (`uv venv && uv pip install -e .`) is only for people modifying MAGI's source. A `magi` installed that way **is not on PATH** — you can only invoke it as `.venv\Scripts\python.exe -m magi.cli ...`. Skills, Claude Code's SessionStart hook, and the radar's scheduled job all look for the bare command name `magi` on PATH, and won't find it there. For everyday use, install with `uv tool install`.

### Teach your CLI agent to use MAGI {#install-hosts}

This step isn't a nice-to-have: **the knowledge base's compile step only runs inside an agent** (see Chapter 6).

**One command, run inside the workspace**, teaches every agent CLI on your machine:

```powershell
cd <your topic workspace>
magi skills install              # into this workspace (the default)
magi skills where                # where each CLI reads from, and what is installed
magi skills install --dry-run    # see the exact files first, write nothing
magi skills uninstall            # take them back out
```

The skill files ship with the CLI — **no repo clone, no network**.

> [!WARN]
> **The default is this workspace, not your whole machine.** All 19 skills revolve around one research workspace — ingest into its `raw/`, compile into its `wiki/`, query its graph — so a machine-wide install makes every unrelated project carry them for nothing. If you really want that: `magi skills install --scope global` (it warns once).
> Installing into the workspace has a second benefit: the files travel with the repo, so a collaborator who clones it gets them.

| Host | Global | Project | How it fires |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/skill-name`, and auto by description |
| **Codex** | `~/.agents/skills/` (plus `~/.codex/skills/`) | `<repo root>/.agents/skills/` | `$skill-name`, or Codex picks it by description |
| **Antigravity (agy)** | `~/.gemini/config/skills/` | `<repo root>/.agents/skills/` | Name it in your prompt, or auto by description; `/skills` browses |
| **opencode** | `~/.config/opencode/commands/` + `skills/` | `.opencode/commands/` + `skills/` | `/skill-name` |

> [!NOTE]
> **Not every CLI has slash commands.** Claude Code and opencode do; Codex uses `$skill-name`; agy only fires on description matching (`/skills` is just a browser). So the one habit that works everywhere is simply to **say what you want** — "ingest the papers in inbox", "look up this error" — and let the matching skill load itself.
> `.agents/skills/` is the cross-agent convention Codex and agy share, so one copy serves both. opencode scans it too, but its slash commands come from its own `.opencode/commands/`, so the installer writes there as well.

**Claude Code can also use the plugin** (the one-line installer does this for you): skills arrive namespaced, and the plugin adds a SessionStart hook that runs `magi sync` at the start of every session:

```powershell
claude plugin marketplace add Misaka16384/magi
claude plugin install magi
claude plugin install <local-repo-dir>      # local development mode
```

The plugin and `magi skills install` coexist — one gives you `/magi:skill-name`, the other `/skill-name`.

**Any other agent** — the workspace's `CLAUDE.md` and `AGENTS.md` (identical content, two copies) are the onboarding protocol: run `magi sync` on entry, which commands map to which core, use `magi guide --search` when stuck, and never answer research questions from memory. Any host that reads either file can work here; if it reads neither, pasting `magi --help` is enough.

> [!EXPECT]
> `magi skills where` shows 19/19 on the project rows. Start a fresh agent session **from that workspace directory** and the skills appear under `/` (Claude Code, opencode), or just say "ingest the papers in inbox" and watch it act. `magi setup --check` also shows the per-CLI count for the workspace you are in.

> [!FIX]
> - **Installed but not showing**: skills are scanned at startup — **start a new session from the workspace directory** (project skills are only visible when the CLI is launched there).
> - **Not sure where they went**: `magi skills where` prints the real path and count per CLI.
> - **It says skipped**: a file of the same name was already there and didn't look like ours, so it wasn't overwritten. Check it, then `magi skills install --force`.
> - **The agent calls a script that doesn't exist** (`python bin/llm-wiki.py ...`): old Wikify SKILL.md files are still around — run `magi setup --remove-legacy`.
> - **To remove them**: `magi skills uninstall [--host X] [--scope project]`.
> - `magi setup`, `magi migrate`, and `magi ui` **have no skill** — they are CLI-only commands.

### External tools (as needed) {#install-tools}

| Tool | Who needs it | What happens without it |
|---|---|---|
| **Beads** (`bd`) | Task tracking | Task features degrade; everything else is unaffected |
| **Ollama** + `qwen3-embedding:0.6b` | Semantic search, semantic linking, radar relevance scoring | Search automatically falls back to keyword matching; `magi link` errors out |
| **Ollama** + `glm-ocr` | Fully local OCR ingestion | You're limited to cloud OCR or the LaTeX route |
| **Pandoc** | `magi ingest tex` | Can't process arXiv source packages |
| **Poppler** (`pdftoppm`) | Rendering pages for local OCR | Local OCR errors out directly |
| **pdflatex** | Deep verification of math formulas | Automatically falls back to lightweight `pylatexenc` verification |
| **Ghostscript** | Converting EPS figures in LaTeX source to raster images | EPS files are copied as-is and won't display in markdown |

> [!NOTE]
> You never need to run `ollama serve` yourself. If Ollama is installed but not
> running, MAGI starts it the first time something needs it (once per process).
> Set `ollama.autostart: false` in `config.yaml`, or `MAGI_NO_OLLAMA_AUTOSTART=1`,
> to keep the daemon under your own control.

```powershell
ollama pull qwen3-embedding:0.6b     # vector search (~640MB)
ollama pull glm-ocr                  # local OCR (optional)
```

Windows's `pandoc-crossref.exe` already ships in the repo under `vendor/windows/`: add it to PATH, or point to it in the workspace's `config.yaml` under `tools.pandoc_crossref_path`.

The last four rows of the health check are the agent CLIs on your machine (claude / codex / agy / opencode): whether each is installed, and how many skills it has. If any are missing, it prints the command to fix that.

> [!WARN]
> `magi setup --check`'s health check only looks at PATH — it **doesn't read** the `tools.*` paths in `config.yaml`. So if the table shows `[-] pdftoppm` but you've already set an absolute path in the config, ingestion will actually still work — trust the real run, not the table.

---

## Migrating from Wikify {#migrate}

MAGI is a rebuild of Wikify: the script collection becomes a unified CLI, task state moves out to Beads, and you get hybrid search, claim provenance, and a literature radar. **The `raw/`, `wiki/`, and `inbox/` formats haven't changed — your existing data is fully compatible.**

### Three commands {#migrate-steps}

```powershell
# 1. Install the new version (the one-liner from Chapter 2)
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. Remove the old install copy — the old SKILL.md tells the agent to call scripts that no longer exist
magi setup --remove-legacy

# 3. Migrate every topic from the hub root in one shot (non-destructive)
cd <your-KnowledgeHub>
magi migrate
```

`magi migrate` automatically figures out whether the path you give it is a hub or a single topic: hub mode migrates every **unarchived** topic under `topics/` in one pass; single-topic mode migrates only the current one.

**It only ever adds.** It fills in whatever's missing — `CLAUDE.md` / `AGENTS.md` / `config.yaml` / `scratch/` and the `_index.md` files at every level — then rebuilds `output/graph.db` (adding the claims/evidence tables) and `wiki/{concepts,references}/_index.md`. Any file that already exists is skipped outright — not a single character of `raw/`, `wiki/` content, `config.md`, or `log.md` gets touched.

**Your old settings come with you.** It looks for the previous `config.yaml` in `<topic>/.agents/`, `<hub>/.agents/`, `~/.claude` and `~/.gemini`, and copies values — MinerU token, model names, dpi, semantic-link thresholds — into the new config. Only settings still at their default are filled, so an edit you made after migrating is never overwritten, and it prints which keys it carried (key names only, never the token itself).

> [!NOTE]
> `magi migrate` has **no** `--dry-run` and **no** `--force`. Non-destructiveness isn't guaranteed by a flag — it's hard-coded into the implementation: when it calls the scaffolding, it never passes `--force`, so all it can ever do is create missing files. Running it again is safe; the second run just takes the "refresh index" branch.

One step is left — it asks which agent CLI, so it is not done for you:

```powershell
cd topics\<your-topic> && magi skills install
```

> [!EXPECT]
> Each topic prints `Migrating workspace: <path>`, then `config carried from ...` when there were old settings to bring across, then `magi graph build: ok` / `magi wiki reindex: ok`. At the end, "Finishing up" runs `magi pm init` and a `magi sync --fix` per topic and reports the new sync ratio.

> [!FIX]
> - **Hub mode reports `N/N topics migrated` at the end, but you saw a `FAILED` in the middle**: the summary line and exit code don't reflect sub-step failures (a known gap). **Search the output for `FAILED` yourself**, then `cd` into the failing topic and rerun `magi migrate` there on its own.
> - **Hub mode didn't remind you to build indexes**: hub mode only prompts `magi pm init` — it won't remind you to run `magi index` / `magi sync` in each topic. Do it manually.
> - **The agent still mentions the old commands after migrating**: either `magi setup --remove-legacy` hasn't run, or the agent host's skill cache hasn't refreshed — restart the agent session.
> - **A topic didn't get migrated**: hub mode skips `topics/.archive/` and any directory that has neither `wiki/` nor `raw/`. Go into that directory and run `magi migrate` on its own, then `magi hub register <slug>`.
> - **It throws a raw Python exception**: the scaffolding step has no exception guard for this; the usual cause is a locked file or insufficient permissions (on Windows, an editor holding `CLAUDE.md` open). Close whatever's holding the file and rerun — you won't be left with a half-finished result.

> [!WARN]
> **Project-local old skills need separate handling.** If your hub or topic directory has a `.agents/skills/` (copied there in the Wikify days), `magi setup --remove-legacy` **will not find it** — that only scans `~/.claude` and `~/.gemini`. And `.agents/skills/` is exactly what Codex, agy and opencode all read, so those stale SKILL.md files will send your agent after scripts that no longer exist. `magi migrate` now detects this and warns; rename it to keep a backup: `mv .agents .agents.wikify-backup`.

> [!WARN]
> `magi setup --remove-legacy` doesn't just delete that one `llm-wiki.py` file: the moment it finds it under `~/.claude/bin` (or `~/.gemini/bin`), **it recursively deletes the entire bin directory** — no confirmation prompt. Take a look inside that directory before you run it, in case you've stashed anything of your own there.

### Command mapping {#migrate-map}

| Old (Wikify) | New (MAGI) |
|---|---|
| `python <BIN>/llm-wiki.py lint --fix <dir>` | `magi lint --fix <dir>` |
| `python <BIN>/llm-wiki.py graph <dir>` | `magi graph build <dir>` |
| `python <BIN>/query-graph.py "<SQL>"` | `magi graph query "<SQL>"` (or `magi graph browse`, no SQL needed) |
| `python <BIN>/search-wiki.py <regex> <files>` | `magi grep <regex> <files>` |
| `python <BIN>/ingest_helper.py --file ...` | `magi ingest add --file ...` |
| `semantic_linker.py` | `magi link` |
| `verify_claims.py` | `magi verify` |
| Manual `requirements.txt` install | Installed automatically with the CLI |
| Progress tracked in `log.md` | Beads task graph; `log.md` is now just a human-readable narrative |
| `~/.config/llm-wiki/config.json` | `~/.config/magi/config.json` (the old path still falls back automatically, forever — no manual move needed) |
| Requires ripgrep | No longer needed |

---

## Setting up your library {#workspace}

### Hub or single topic {#workspace-shape}

- **Single topic**: one project, one directory — `magi init` and you're done.
- **Hub**: multiple projects sharing one root directory, with **one shared task store** and a topic registry. Cross-project search and a unified task view both depend on it.

We recommend setting up a hub from the start — it's one extra command now, and adding projects later costs nothing.

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init          # Generates topics/, topics/.archive/, wikis.json, _index.md, log.md
magi pm init           # Installs the task system at the hub root (runs git-init)

mkdir topics\my-topic ; cd topics\my-topic
magi init --name "Display name" --scope "One line on what this library collects and what it does not"
```

When you create the topic directory under `<hub>/topics/`, `magi init` **registers it into the hub automatically**. Create it anywhere else and you'll need to register it yourself: `magi hub register <slug> --path <relative/path>`.

`--scope` isn't decoration: it gets written into `CLAUDE.md`, where the agent uses it to judge "does this paper belong here, does this concept fall inside the library's scope." **The more specific you write it, the more accurate the automation's judgment calls will be later.**

### What `magi init` generates {#workspace-layout}

```text
my-topic/
├─ CLAUDE.md / AGENTS.md   agent onboarding protocol (both files hold the same content)
├─ config.md               human-readable description of this library (title + research scope)
├─ config.yaml             this workspace's config (OCR, models, radar... see Chapter 5)
├─ log.md                  human-readable running narrative
├─ inbox/                  drop zone for unprocessed material (dump PDFs here) · .processed/ holds the originals once processed
├─ raw/                    ingested source literature, as Markdown
│   articles/ papers/ repos/ notes/ data/
├─ wiki/                   compiled output
│   concepts/  concept cards    references/ reference cards    topics/  topic pages    theses/ claim reports
├─ output/                 graph.db, index.db, radar ledger
└─ scratch/                the agent's scratch pad, safe to clear anytime
```

Every directory except `inbox/` and `scratch/` gets an `_index.md` directory listing.

> [!NOTE]
> **`drafts/` isn't in this list** — `magi init` doesn't create it. It appears naturally the first time you write `drafts/xxx.md`, and the toolchain (search, lint) already recognizes the directory. See Chapter 9.

> [!TIP]
> Open the **topic directory** in Obsidian (not the hub root). Add these two regex patterns under Settings → Files and Links → Excluded files, and the graph view will show nothing but pure knowledge cards:
> ```regex
> /(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
> ```
> ```regex
> /^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
> ```

### Managing topics {#workspace-hub}

```powershell
magi hub list                     # All topics; --archived includes archived ones too; --json for machine-readable output
magi hub resolve <hub-path> <slug>  # Topic slug → absolute path (for cd in scripts)
magi hub register <slug> --path topics/<slug>   # Adopt an already-initialized directory
magi hub archive <slug> --reason "project closed"   # Archive: moves it into topics/.archive/, doesn't delete files
magi hub restore <slug>           # Restore it
```

`magi hub list` self-heals: any topic that exists on disk but isn't in the registry gets listed and flagged `registry repair needed` — just `register` it as prompted.

**One command across every topic** — most maintenance is per-workspace, and `cd`-ing through a multi-topic hub gets old fast:

```powershell
magi each sync --fix        # bring every topic back to green
magi each index             # rebuild every topic's retrieval index
magi each lint --fix        # structural pass over the whole hub
magi each skills install --host codex
```

Run it at the hub root: it picks the **unarchived** topics out of the registry, runs the command in each, and ends with one `N/N ok` line. `--stop-on-error` halts on the first failure, `--json` is for machines.

### How MAGI finds the "current workspace" {#workspace-discovery}

Every command locates the workspace by **walking up from the current directory** (up to 30 levels):

- **A topic root** is identified by having either `wiki/` or `raw/`, plus at least one of `config.md` / `log.md` / `config.yaml`.
- **A hub root** is identified by having both `wikis.json` and `topics/`.

**No environment variable changes this behavior** — there's no such thing as `MAGI_HOME`. To operate across directories, use explicit arguments like `--topic-dir` / `--hub` / `--db`.

> [!FIX]
> - **You get `no workspace found`**: you're standing at the hub root or higher. `cd` into the specific topic directory, or add `--topic-dir <path>`.
> - **Rerunning `magi init` says `Skipping existing ...`**: that's not an error. It doesn't overwrite existing files by default; if you really want to regenerate them with a new `--name`/`--scope`, add `--force` (this discards any manual edits you made to those files).

> [!WARN]
> **Don't nest workspaces inside each other.** `magi init` doesn't check whether the parent directory is already a workspace. If you `init` a workspace inside another topic's `raw/`, the outer workspace's compile-backlog count will pull in every `raw/*.md` from the inner one, and the sync ratio will drop for no obvious reason. If you've already nested them, move the inner one outside the outer workspace's `raw/ wiki/ inbox/ output/`.

---

## Ingesting literature {#ingest}

### Four routes, and how to pick one {#ingest-routes}

| Command | Best for | Dependencies | Quality |
|---|---|---|---|
| `magi ingest tex` | arXiv source packages (`.tar.gz`) or `.tex` | Pandoc | **Best** — formulas, citations, and numbering stay natively faithful |
| `magi ingest mineru` | General PDFs (including scans) | MinerU cloud token | Good, strong layout/formula recognition |
| `magi ingest ocr` | General PDFs, fully offline | Ollama + poppler | Moderate, page-by-page visual transcription |
| `magi ingest add` | Material that's already Markdown/text | None | Just archives it and injects frontmatter |

**Don't want to choose?** `magi ingest auto` picks by file type (source bundle → tex, PDF → mineru when a token is configured, otherwise local ocr, text → add) and finalizes for you:

```powershell
magi ingest auto paper.pdf        # one file
magi ingest auto                  # everything in inbox/
magi ingest auto --dry-run        # see the routing first
```

Reach for the specific commands below when you need a page range, want to force a route, or are wrestling with a difficult scan.

**If you can get the arXiv source package, use `tex` first** — it keeps `.bib`/`.bbl` alongside the markdown, and writes the arXiv ID into frontmatter for the radar and `magi bib` to use.

Two more supporting routes: `magi ingest assemble` stitches `page_1.md, page_2.md…` — page-by-page transcriptions the agent produced itself — together into one document in page order; `magi ingest crop` crops a region of a PDF into a PNG so you can eyeball a formula directly.

### What you need to configure {#ingest-config}

Configuration lives in **the `config.yaml` at your workspace root** (it only falls back to `~/.config/magi/config.yaml` when that's missing; the two are never merged — whichever one is closer completely overrides the global one).

```yaml
ocr:
  mineru_api_token: ""      # ← required for MinerU cloud OCR; get it from https://mineru.net
  dpi: 130                  # local OCR render resolution; below 110 misreads dense subscripts
  timeout: 180              # per-page OCR timeout (seconds)

models:
  ocr: glm-ocr                    # local OCR model (glm-ocr / qwen3-vl / qwen3-vl:4b ...)
  embedding: qwen3-embedding:0.6b # shared by semantic search and semantic linking

ollama:
  base_url: http://127.0.0.1:11434
  autostart: true                 # start a stopped local Ollama on demand

tools:                      # only needed if these programs aren't on PATH
  pandoc_path: ""
  pandoc_crossref_path: ""
  pdftoppm_path: ""
```

These six environment variables — `OLLAMA_HOST` / `PANDOC_PATH` / `PANDOC_CROSSREF_PATH` / `PDFTOPPM_PATH` / `PDFIMAGES_PATH` / `MAGI_NO_OLLAMA_AUTOSTART` — **take priority over `config.yaml`**; every other key can only be changed by editing the file.

> [!WARN]
> **A malformed YAML file fails silently.** If the auto-discovered `config.yaml` doesn't parse, the program silently falls back to its built-in defaults — no message at all. After editing, verify it with this:
> ```bash
> python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"
> ```

> [!NOTE]
> The `ocr.use_mineru` key **only matters to the agent** — it's a routing hint the `wiki_ingest` skill reads. When you type `magi ingest mineru` directly in the terminal, it ignores this key and just checks whether the token is configured. Likewise, `pdf.quality` and `output.encoding` currently do nothing — changing them has no effect.
> There's also a set of keys that aren't in the template `magi init` generates, but that the code does read: the entire `tools:`, `pdf:`, and `output:` sections, plus `radar.min_relevance` / `radar.own_arxiv_ids` / `radar.citation_gap.*`. Add them yourself when you need them.

### Running it {#ingest-run}

The easiest approach: drop the PDF into `inbox/` and tell the agent "ingest the papers in inbox" (or run `/magi:wiki_ingest`). It picks the route, converts the format, and wraps up. To run it by hand:

```powershell
# arXiv source package (most recommended)
magi ingest tex 2401.12345.tar.gz -o raw/papers

# Cloud OCR
magi ingest mineru paper.pdf -o raw/papers

# Local OCR (can target a page range only)
magi ingest ocr paper.pdf -o raw/papers --pages 1-12

# Already markdown
magi ingest add --file inbox/notes.md --type notes --move
```

**Every route needs to be finalized once it finishes**:

```powershell
magi ingest finalize inbox/paper.pdf --topic-dir . --md-file raw/papers/2026-08-20-paper.md
```

`finalize` is the step that actually wires the file into the knowledge base: it archives the original to `inbox/.processed/`, cleans up frontmatter, converts image links to Obsidian wikilinks, runs formula formatting and validation, and finishes with `magi lint --fix` + `magi graph build` + `magi wiki reindex`.

> [!WARN]
> Those last three run against **the entire workspace**, not just this one document — and **if any of them fails, it just prints one warning line; nothing stops, and the exit code doesn't change**. On your first ingestion, watch the terminal for a line like `Warning: 'magi lint' failed` — it will keep silently repeating on every ingestion after that until you deal with it. If you see one, run that command on its own to see the real error.

> [!TIP]
> When ingesting in bulk, don't rebuild the graph after every single paper: add `--skip-lint` to each one, then run `magi ingest finalize none --topic-dir . --lint-only` once at the end.

> [!EXPECT]
> `raw/<type>/YYYY-MM-DD-<slug>.md` appears, with figures in a sibling `images/`; the last terminal line reads `Successfully converted and saved to ...`, or `✓ 转换完成！` for local OCR.

### When ingestion quality falls short {#ingest-trouble}

| Symptom | Cause | Fix |
|---|---|---|
| `Error: mineru_api_token not configured` | Token isn't configured (the error message won't tell you where to get one) | Register at [mineru.net](https://mineru.net) to get a token, then fill it into `ocr.mineru_api_token` |
| `MinerU extraction timed out after 30 minutes` | Cloud queue backup, or the document is too large; **the timeout is hard-coded and can't be adjusted** | Split the PDF, or switch to `magi ingest ocr` |
| `MinerU Processing failed` | The cloud service can't parse this particular PDF | Switch to the local OCR route |
| `Pandoc conversion failed` | The LaTeX uses a macro pandoc doesn't recognize, or pandoc isn't installed | Check the stderr it prints to pinpoint the exact command; confirm `tools.pandoc_path` |
| `pandoc-crossref not found` | Cross-references don't render | Non-fatal; install it or set `tools.pandoc_crossref_path` |
| `TeX source references N figure(s) but only M survived` | pandoc dropped a subfigure/wrapfigure | Compare against the original PDF and add the figure back by hand |
| `EPS not rasterized (install Ghostscript)` | Ghostscript is missing | Install it and rerun, or accept the figure not being inlined |
| `OCR 模型 X 不可用` | The model hasn't been pulled | `ollama pull glm-ocr` |
| `pdftoppm 未找到` | poppler is missing | Install poppler, or set `tools.pdftoppm_path` |
| `第 N 页 OCR 失败` | That single page failed both retries | **Just rerun the exact same command** — successful pages are cached in `.temp/`, so only the failed page gets redone |
| Garbled formulas, subscripts running together | Render resolution is too low | Bump `ocr.dpi` to 150 and rerun |
| `Warning: 'magi math check' failed` after ingestion | Formula validation found an issue | `finalize` doesn't stop for this; run `magi math check <file>` on its own for details — see Chapter 6 |

> [!NOTE]
> `magi ingest ocr` has **no** `--resume` flag — resuming is automatic. As long as the output directory still exists, rerunning the same command reuses whatever pages are already done in `.temp/page_N.json`. `.temp/` is deliberately kept around whenever there are failed pages; once you've confirmed everything's finished, you can delete it by hand.

---

## Compiling into the knowledge base {#compile}

Ingestion just turns papers into Markdown. **Compiling** is what turns them into interlinked cards: reading a paper, extracting its concepts, deciding what belongs in your wiki, and writing it up as a structured card.

**There's no CLI command for this step** — `magi compile` doesn't exist. It's pure understanding work that only an agent can do, by running the `wiki_compile` skill. At this layer, the CLI only handles deterministic checking and repair.

> [!WARN]
> `magi graph build` **still returns success** even when `wiki/` is empty — it just builds an empty graph. So "the graph is empty" usually doesn't mean the graph is broken; it means you haven't compiled yet. Confirm with:
> ```powershell
> magi graph query "SELECT COUNT(*) FROM nodes"
> ```

### The main flow {#compile-main}

Tell your agent these, in order (or use the slash commands):

| What to say | Skill | What it does |
|---|---|---|
| "Compile the new papers in raw" | `wiki_compile` | Turns each raw source into a `wiki/references/` reference card, and extracts concept cards along the way |
| "Dig deeper into this paper's concepts" | `wiki_enrich` | Re-scans already-compiled cards to catch theorems/lemmas the first pass missed |
| "Merge duplicate concepts" | `wiki_concept_sync` | Physically merges synonymous concepts, splits overly broad ones, and rewrites multi-source definitions |
| "Clean up tags" | `wiki_tag_sync` | Normalizes the tag/alias ontology (see Chapter 7) |
| "Run a checkup and fix" | `wiki_lint` | Auto-repairs broken links, frontmatter, and formulas |
| "Ingestion mangled the formulas" | `wiki_math_fix` | Harvests every broken formula in the library, then reads and repairs them one at a time |

The corresponding deterministic commands:

```powershell
magi wiki uncompiled                      # Which raw sources are still uncompiled (this is how you track compile progress)
magi lint --fix                           # Self-heal structure: fill in frontmatter, relocate files, rebuild directory indexes
magi wiki reindex .                       # Rebuild only the _index.md files under concepts/ and references/
magi stats . wiki-summary                 # Structural stats for the whole wiki
magi map wiki/concepts                    # Section and equation-block layout for every file in a directory
magi wiki placeholders wiki/concepts/x.md # Find unfinished placeholder sections
```

### What a card looks like {#compile-cards}

`magi lint` grades against the rules below — write your cards to match:

**Required frontmatter** — for reference cards/concept cards: `title`, `category`, `created`, `updated`, `tags`, `summary`; `category` must be one of `concept` / `topic` / `reference`, and it **determines which directory the file belongs in** (get it wrong and `--fix` moves the file for you). Raw sources require `title`, `source`, `type`, `ingested`.

**Required body sections** — reference cards need `## 1. Key Contributions` and `## 2. Theoretical Framework`; concept cards need `## 1. Core Definition` and `## 2. Mathematical Formalism`. For a card where these genuinely don't apply, exempt it with `exclude_structure_check: true` in the frontmatter.

**Provenance** — the `sources:` list must resolve to real files; a card produced purely from conversation is exempted with `compiled-from: conversation`.

**Freshness** — `volatility` is `hot`/`warm`/`cold`, corresponding to 30/180/365 days. Once a card ages past that window it's flagged stale; re-verify it and update `verified` or `updated` to today.

> [!EXPECT]
> `magi lint` finishes by printing `Summary: N critical, N warnings, ...` and `Result: PASS`. **Only criticals cause a FAIL** — warnings are a to-do list, not a blocker.

> [!FIX]
> - `Markdown file is missing YAML frontmatter` / missing fields: fill them in from the checklist above.
> - `File is in the wrong directory` → `magi lint --fix` relocates it automatically; if a file with the same name already exists at the destination, it refuses to move and you'll need to handle it by hand.
> - `Wikily [[...]] contains Windows-illegal filename character(s)`: the wikilink contains `\ / : * ? " < > |` — rename it.
> - `Wikilink appears to contain a raw mathematical equation`: the wikilink has LaTeX stuffed into it — swap in a clean concept name and put the formula on its own line.
> - `Master _index.md is missing` is flagged fixable but **`--fix` never actually repairs it**; `config.md is missing` isn't flagged fixable at all. Create both by hand.
> - **Running lint at the hub root checks almost nothing**: the hub root only does the outermost structural check. The real quality gate runs inside a topic directory.

> [!WARN]
> The `status` field in `magi lint --json` and the exit code **use different criteria**: the JSON status is `fail` as soon as there's any warning or suggestion, while the exit code and the text-mode `Result:` line only look at criticals. In CI, go by the exit code.

### Formulas {#compile-math}

```powershell
magi math format raw/papers/x.md    # Mechanical fixes: pairing $$, \tag placement, eqnarray→align, OCR run-ons
magi math check raw/papers/x.md     # Reports only, doesn't fix: pylatexenc structural check (goes deeper if pdflatex is available)
```

The order is always **format first, then check**.

> [!NOTE]
> `Undefined control sequence` is usually a **false positive** — the checker just doesn't recognize a macro from some package. Spot-check one against the original PDF, and you can ignore the rest of that kind. What you actually need to fix are structural errors like `Double subscript`, `Missing }`, and `Unexpected end of stream`: crop the original text out with `magi ingest crop <pdf> --text "<nearby text>" --out scratch/crop.png` and edit against it.
> `[WARNING] Orphaned $$ remains on line L` is a boundary case format can't resolve on its own — you have to pair it up by hand.

---

## Knowledge graph {#graph}

### Building and browsing the graph {#graph-build}

```powershell
magi graph build .                 # Full rebuild of output/graph.db from wiki/
magi graph browse overview         # Overview: node/edge counts, tag count, claim status, broken-link count
magi graph browse nodes --q topology  # Fuzzy node search by title/ID (sorted by degree, descending)
magi graph browse links --node <id> # In/out edges for a node
magi graph browse tags             # Tag frequency (descending)
magi graph browse broken           # All broken links: what points to pages that don't exist
magi graph browse claims --status unverified
magi graph browse map --tags       # Full-graph snapshot (this is what the dashboard's graph view uses)
```

Every view supports `--limit N` and `--json`.

For more open-ended queries, use read-only SQL (only `SELECT` / `WITH` / `PRAGMA` are allowed):

```powershell
magi graph query "SELECT type, COUNT(*) FROM nodes GROUP BY type"
```

Schema: `nodes(id, path, title, type, category, summary, created, updated)`, `edges(source_id, target_id, type)`, `tags(node_id, tag)`, `aliases(node_id, alias)`, `claims(id, doc_id, text, status)`, `evidence(claim_id, source_type, source, quote)`.

> [!NOTE]
> **Every `graph build` is a full rebuild** — there's no incremental mode and no file watcher. **Rerun it after any batch of edits**, or you're looking at a stale graph.
> `graph build` only scans `wiki/` — anything in `raw/` never makes it into the graph.

### When the graph looks bad: symptoms and fixes {#graph-tuning}

| What you're seeing | The real cause | The fix |
|---|---|---|
| **Too few nodes** | Papers haven't been compiled into cards yet; or the graph is stale | Check the backlog with `magi wiki uncompiled` → compile with `wiki_compile` → `magi graph build` |
| **A bunch of isolated points** | Cards' bodies have no wikilinks, and semantic linking hasn't run | `magi link .` (below); for systematic linking use `wiki_enrich` |
| **A hairball — everything connected to everything** | The linking threshold is too low; or some tag is too broad and every card hangs off it | Raise `magi link --threshold`; normalize tags first, then rerun linking |
| **Duplicate concepts** | Nothing merges concepts automatically | `magi link . --dedup-only` lists candidates — merge after a manual check |
| **Tags are a mess** | Every paper writes its own | `magi tags extract` → write a mapping by hand/LLM → `magi tags apply` |
| **Lots of broken links** | The wikilink text doesn't match any title/filename/alias | Go through `magi graph browse broken` one by one: fix the wording, add `aliases:` to the target, or create the missing concept with `magi wiki add-concept` |
| **Can't see topic clusters** | You're using the `--tags` view and the tag nodes become universal hubs | Drop `--tags` to see the pure wikilink topology; then check whether `magi lint` is flagging misplaced files |

**Semantic linking** (requires Ollama):

```powershell
magi link .                       # Insert mutual [[wikilinks]] wherever similarity crosses the threshold
magi link . --dedup-only          # Only list duplicate candidates, don't touch files
magi link . --dedup-only --auto-merge   # Automatically merge pairs with extremely high similarity
```

You can set the three thresholds permanently in `config.yaml`, or override them for one run with the matching flag:

```yaml
semantic_link:
  threshold: 0.75          # Above this → insert a wikilink
  merge_threshold: 0.85    # Above this → list as a merge candidate
  auto_merge_threshold: 0.95   # Above this → actually merged when --auto-merge is set
```

> [!WARN]
> `--auto-merge` picks whichever name is **shorter** as the canonical one — not whichever has the more complete content. Review the list with `--dedup-only` before merging.
> Also: shared tags boost the similarity score (+0.05 per shared tag, +0.10 for a matching alias). So **the messier your tags, the easier it is for links to cross the threshold** — cleaning up tags before linking makes a real difference.

**Tag normalization** happens in three stages:

```powershell
magi tags extract .                  # → scratch/raw_tags.json, raw_aliases.json (inverted index)
#   ↑ Based on this, you (or the agent) write scratch/tag_mapping.json {"tags": {"old":"new"}}
#     and scratch/alias_mapping.json {"aliases": {"old":"new"}}
magi tags apply . scratch/tag_mapping.json scratch/alias_mapping.json
```

`apply` rewrites all frontmatter, writes the canonical tag list to `output/ontology.txt`, and automatically rebuilds the graph and index (`--no-rebuild` skips that second half). **There's no dry-run** — it edits real files, so commit to git before you run it.

> [!FIX]
> - `[Error] Cannot reach Ollama`: a stopped local Ollama gets started for you, so this means it isn't installed at all (or autostart is off). Get it from https://ollama.com.
> - `Embedding model ... is not installed`: starting the server is all MAGI does — pull the model yourself with `ollama pull qwen3-embedding:0.6b`.
> - `[Info] Not enough concepts to analyze`: fewer than two non-stub concept cards — a normal exit, not an error.
> - `magi graph browse links --node X` says `node not found`: X is neither a node ID nor a unique title. Get the exact ID first with `browse nodes --q X`.
> - A file's tags just won't make it into the graph: the frontmatter list isn't formatted correctly. Run `magi lint --fix`, then rebuild.

### Viewing it in Obsidian {#graph-obsidian}

MAGI's wikilinks are Obsidian's wikilinks — you can use both at once: Obsidian handles visual browsing and manual editing, `magi graph` handles structured queries. For the exclusion rules, see the callout in 4.2. The dashboard's **MELCHIOR → Graph view** is a force-directed rendering of the same data; links that point to pages that don't exist show up as "ghost nodes" — matching Obsidian's behavior.

---

## Search {#search}

### Building the index {#search-index}

```powershell
magi index                # Build/refresh output/index.db
magi index --no-vectors   # Build a keyword-only index (when Ollama isn't available)
```

The index covers every `.md` file under `wiki/`, `raw/`, and `drafts/`, chunked by level-1 through level-3 headings, with a 250-line cap per chunk. **It updates incrementally**: files whose content hash hasn't changed are skipped, and deleted files are cleaned up automatically.

> [!EXPECT]
> `index: 42 chunks (5 files updated, 37 unchanged, 0 pruned) · vectors 42/42`
> If it ends with `· BM25-only (Ollama unavailable)`, the vector half didn't get built.

`magi index` also **automatically registers** the current workspace in the global knowledge-base table (`~/.config/magi/registry.json`), so other workspaces can search it too.

### Searching {#search-query}

```powershell
magi search "anyon statistics"                # Default: this wiki + every enabled registered KB
magi search "anyon" -k 20 --mode vector      # Semantic search only
magi search "exact phrase" --mode bm25        # Keyword search only
magi search "..." --collection concepts      # Search only concept cards
magi search "..." --path 'raw/papers/2026-*fracton*'   # Restrict the search to one paper
magi search "..." --scope local              # Search only the current workspace
magi search "..." --kb <name>                # Search only one registered KB
magi search "..." --json                     # Machine-readable output
```

The default `hybrid` mode merges keyword and semantic results with RRF ranking, and it supports both Chinese and English (Chinese text is bigram-split for the keyword index; the semantic side is naturally cross-lingual via the embedding model).

**Cross-KB search**:

```powershell
magi kb list                  # All registered KBs and whether each is searchable
magi kb disable <name>         # Exclude it from global search (enable to restore)
magi kb register <path>        # Register manually (named after the directory by default; duplicates get -2 appended)
magi kb unregister <name>      # Remove only the registry entry, files untouched
```

> [!FIX]
> - `no index at output/index.db` → Run `magi index` first.
> - `no workspace here and no searchable registered KBs` → You're not inside a workspace, and there's no searchable registered KB. `cd` into one, or `magi kb register` + `enable`.
> - **Can't find something you just wrote** → The index updates incrementally by hash, but it **doesn't trigger automatically**. Rerun `magi index` after editing.
> - **Results are all keyword hits, no semantic ones** → It ends with a `BM25-only` notice. MAGI already tried to wake a local Ollama; if it's still BM25-only, Ollama isn't installed or the embedding model isn't pulled. Check with `magi setup --check`, then rerun `magi index` to fill in the vectors.
> - **Chinese search turns up nothing** → When you see `this index predates CJK-aware tokenization`, just rerun `magi index` (it rebuilds the tokenization layer automatically).
> - `index dims mismatch current embedding model` → You switched embedding models. Switch back, or rerun `magi index` for a full re-embed.
> - `sqlite-vec unavailable` → The vector extension failed to load (common on macOS when the system Python doesn't support loading extensions). Use uv/Homebrew Python, or fall back to keyword search.

> [!NOTE]
> `magi index` has no `--force` / `--rebuild`, and no clear-the-index command; if you really need a clean slate, delete `output/index.db` and rerun.
> `magi grep "<regex>" <files...> [-i]` is a different thing entirely — it doesn't read the index, it just does regex line-matching against the files you name (Python regex syntax, JSON output, capped at 200 matches, with a 5-second hang guard). Use it when there are only a few files and you need an exact literal match; use `magi search` when you want to "find related content."

---

## Writing your paper {#writing}

### Using tasks and to-dos {#writing-tasks}

MAGI doesn't implement its own task system — it connects to [Beads](https://github.com/gastownhall/beads) (`bd`). **One task database per hub**, with each topic's issues distinguished by a `topic:<name>` label.

```powershell
magi pm init          # run once at the hub root: creates the DB + registers the six research issue types
magi pm status         # current ready / in progress / blocked / open counts
magi pm backlog-sync   # turn "uncompiled raw sources" into to-dos
```

> [!NOTE]
> If you're a single-topic user, you don't need a hub. When `magi pm status` can't find a task database, it prints "run 'magi pm init' at the hub root" — that message is misleading if you have no hub. Just run `magi pm init` inside the topic directory; it creates the database in place.

The six research types: `question`, `survey`, `derivation`, `computation`, `experiment`, `review` (plus Beads' own built-in `task`/`bug`/`feature`/`epic`/`chore`/`decision`).

Day to day, the commands you'll actually type are Beads' own:

```powershell
bd ready                                   # what you can work on right now (check this before you start)
bd create -t derivation "Derive the duality transform in section 3.2" -d "..."
bd close <id> --reason "Done — conclusion in drafts/paper.md#3.2"
bd list --label magi-compile --all         # view the compile backlog
```

The pattern for writing a paper is simple: **open one issue per subsection**, close it when you finish, and leave a one-line conclusion in the reason. Contradictions the audit turns up, must-read papers the radar surfaces — those become issues too, not TODO comments. That way, when a new session picks this up, `bd ready` is a complete handoff.

> [!WARN]
> Don't use `-t thesis` — it isn't a valid type (`thesis` is just the name of the `wiki/theses/` directory). Use `derivation` / `review` / `question` for writing tasks.

> [!NOTE]
> `magi pm backlog-sync` only **creates** issues — it never closes them automatically. After you compile a paper, you (or the agent) find the matching entry with `bd list --label magi-compile` and close it by hand.
> MAGI works fine without `bd` installed: every skill that hits a missing `bd` just warns once and moves on. Task tracking is never a hard gate.

### Drafting {#writing-draft}

Drafts live in `drafts/<slug>.md`. `magi init` doesn't create this directory — it appears naturally the first time you write a file there. It **is searchable** (in a collection called `drafts`), **doesn't enter the knowledge graph**, and **doesn't count toward the sync ratio** — it's something you're still writing, not established knowledge.

The drafting loop (the `wiki_draft` skill walks you through this, but it's the same by hand):

```powershell
magi search "what this paragraph argues" -k 5   # 1. gather your evidence first
magi wiki context --name "some concept"         #   pull every paragraph that mentions the concept into scratch/
#                                             # 2. write drafts/paper.md, citing with [[reference card]] links
magi bib --all -o drafts/refs.bib             # 3. export the bibliography
magi bib pretko-2020 --fetch                  # 　 pull the official arXiv entry when an arxiv_id is present
magi stats . verify-refs drafts/paper.md      # 4. check that every wikilink points to a real file
magi verify drafts/paper.md --topic-dir .     # 　 check that claims' evidence quotes really exist
magi math check drafts/paper.md
```

> [!FIX]
> - `magi bib` says `has no citable frontmatter ... skipped`: that reference card's frontmatter is missing `title`/`authors`/`year`/`doi`/`arxiv_id`/`url` — add one and you're done.
> - `magi bib` says `matches several cards`: the slug is too ambiguous — give the full name or the complete path.

### Claims and verification {#writing-claims}

Any assertion that needs to be held accountable gets written as a claim block (you can embed it right in the body text, wrapped in a `<!-- magi:claims -->` comment; `magi graph build` pulls these into the knowledge graph):

```text
CLAIM: The fractionalized excitations in this model carry a charge of e/3.
EVIDENCE: "the fractionalized excitations carry charge e/3"
SOURCE_TYPE: local_wiki
SOURCE: wiki/references/laughlin-1983.md
```

`FINDING:` is a synonym for `CLAIM:`. All four fields are required. Then:

```powershell
magi verify drafts/paper.md --topic-dir .              # exit code 0 = everything passed, 1 = something unverified
magi verify drafts/paper.md --topic-dir . --fetch-web  # also actually fetches and checks web sources
magi validate wiki/theses/x.md --schema thesis         # structural validation of a claims report
```

> [!NOTE]
> `verified` means **the evidence quote exists** — that exact sentence really appears in the source file, verbatim (differences in whitespace, full-width punctuation, and hyphenation are tolerated). It does **not** judge whether your claim actually follows from that quote semantically — that layer is for humans and LLM review (the `wiki_audit` skill). `magi claims verify` is an alias for the same command.
> The evidence quote must be single-line quoted content; multi-line quotes aren't supported.

> [!WARN]
> The "N paragraphs have no citation" message from `magi validate --schema research` sounds mild, but it **does set the exit code to 1**. Keep that in mind if you're writing CI.

---

## Literature radar {#radar}

What the radar does: every day it deterministically harvests new paper candidates → writes them into a digest → next session, the `radar_review` skill scores them with an LLM → keepers go into the task database and the ingestion queue.

### Configuration {#radar-config}

Configured in the workspace's `config.yaml`:

```yaml
radar:
  arxiv_categories: [cond-mat.str-el, hep-th]   # which arXiv categories to scan each day
  seed_arxiv_ids: ["2301.01234"]                # seed papers (positive examples for the recommender)
  days: 7                    # arXiv lookback window
  max_candidates: 40         # max candidates to keep per run
  min_relevance: 0.35        # relevance threshold (optional; omit = no filtering)
  own_arxiv_ids: ["2402.05678"]     # "our papers", used by citation-gap
  citation_gap:
    min_shared_refs: 2       # co-citation threshold
    years: 2                 # only look at recent years
```

`min_relevance`, `own_arxiv_ids`, and `citation_gap.*` are **not in the template `magi init` generates** — add them yourself when you need them.

Relevance is "the cosine similarity between a candidate's abstract and your library's embedding centroid," so it depends on the vector index `magi index` builds plus a working Ollama; without those, candidates are just listed in source order, unscored.

### Harvesting and review {#radar-run}

```powershell
magi radar harvest                # harvest: S2 recommendations ∪ new arXiv papers → inbox/radar/date-digest.md
magi radar harvest --days 14      # temporarily widen the window
magi radar status                 # ledger size + how many digests are still unreviewed
magi radar citation-gap           # find recent papers that should cite our papers but don't
```

Each candidate in the digest looks like this:

```text
## Paper Title
- id: `2408.01234` · 2026 · source: arxiv · relevance: 0.71
- authors: A Name, B Name, et al.
- https://arxiv.org/abs/2408.01234
- abstract: ...
```

There are two ways to review: tell the agent "review the radar digest" (the `radar_review` skill), or go entry by entry in the dashboard's **Literature radar** panel with "accept into inbox / create a reading task / mark reviewed". Both paths write to the same state.

> [!NOTE]
> Either way, **MAGI never downloads the PDF for you**. "Accept into inbox" just writes a to-do card (`inbox/radar-accept-*.md`); once you actually have the PDF, you still go through the ingestion flow from Chapter 5.

### Scheduled harvesting {#radar-schedule}

```powershell
magi radar install-schedule --time 03:00     # register the daily task
magi radar install-schedule --uninstall      # uninstall it
```

- **Windows**: registers into Task Scheduler, with a task name like `magi-radar-<dir-name>-<hash>`; check it with `schtasks /Query /TN <name>`.
- **macOS**: writes to `~/Library/LaunchAgents/com.magi.radar.*.plist`; check it with `launchctl list | grep com.magi.radar`.
- **Linux**: **installs nothing at all** — it just prints one suggested crontab line, and that line **ignores whatever `--time` you passed and always says 3 AM**. Add it yourself with `crontab -e`.

> [!WARN]
> The task name includes a hash of the workspace path. **After you move or rename the workspace, `--uninstall` can no longer find the old task** — you have to delete it by hand (`schtasks /Delete /TN <name> /F`, or delete the plist).

### Tuning the noise {#radar-tuning}

| Symptom | Fix |
|---|---|
| `harvest: no new candidates` | Are your seeds and categories empty? Is the window too narrow? Try `--days 30`. It's also possible you really have harvested everything already — the ledger is `output/radar/seen.jsonl`, and **no command resets it**; to re-harvest, delete lines from it by hand |
| Too many, too noisy candidates | Raise `min_relevance`, lower `max_candidates`, trim down `arxiv_categories` |
| Relevance scores are all blank | You'll see `relevance scoring unavailable` — run `magi index` to build the vector index first. A stopped Ollama starts itself; if the scores stay blank, it isn't installed or the model isn't pulled |
| `warning: S2 recommendations failed` | Semantic Scholar is rate-limiting you or there's a network issue; the calls are anonymous, there's no API key to configure — just retry later |
| `arXiv query failed for <category>` | The digest's frontmatter records `sources_failed`, and `magi radar status` flags it too; rerun to fill in the gap |
| `citation-gap: no candidates survived` | The funnel is too strict: lower `min_shared_refs`, raise `years` |
| `has no reference data on S2 yet` | The paper is too new — S2 hasn't indexed its references yet. Wait a few days |
| Digests keep piling up | Only a review action flips `status: pending-review` to `reviewed`; re-harvesting on the same day generates `-2`, `-3` copies, and it piles up fast. Review regularly |

---

## Local dashboard {#webui}

```powershell
magi ui                          # defaults to http://127.0.0.1:8737, opens a browser automatically
magi ui --port 8080 --no-open    # use a specific port and don't auto-launch
magi ui --check                  # run a structural self-check only, don't listen on a port
magi ui --host 0.0.0.0           # change the bind address (defaults to localhost only — see the security note below)
magi ui --reload                 # auto-reload on code changes (for development)
```

If you don't specify a port, it probes 8737→8746 automatically; **if you explicitly specify a port and it's taken, it just errors out** — it won't fall through to the next one.

Seven panels:

| Panel | What it does |
|---|---|
| **Topic overview** | Sync ratio, one-click fix suggestions, registered-library management, editing key `config.yaml` fields |
| **MELCHIOR (knowledge)** | Concept/reference counts, claims and evidence table, compile backlog, seven graph views + a read-only SQL console, BibTeX copy, draft list — click any node to read its card |
| **BALTHASAR (work state)** | Beads counts + a one-click "sync backlog to tasks" |
| **CASPER (retrieval)** | A search testbed: mode/scope/collection/path filters, exactly mirroring `magi search --json` — click a hit to open the card at the passage that matched |
| **Literature radar** | Digest reading + entry-by-entry review actions |
| **Ops & danger zone** | An allowlist of server-side operations + type-the-operation-ID confirmation + a live terminal, with task history persisted to disk |
| **Docs & guides** | This very page, plus the README and the CLI command reference |

> [!NOTE]
> **Reading a card is the same everywhere.** A graph node, a link in the sidebar, a
> `[[wikilink]]` inside a card, a CASPER search hit — all of them open one rendered
> preview: markdown with the math typeset, figures resolved from the card's own
> `images/`, mermaid diagrams drawn in place, and an outline beside the prose. A
> search hit scrolls to the passage that matched rather than the top of the file,
> and preview follows a hit into whichever registered library it actually lives in.

**The dashboard can trigger exactly 14 background tasks**: build index, build graph, rebuild the directory table, semantic linking, lint fix, stats, backlog sync, radar harvest, citation gap, plus the ones that need a second confirmation: setup / migrate / pm init / delete legacy copies / radar scheduling.

> [!NOTE]
> **Ingestion isn't among them** — the entire `magi ingest *` family can only be run from the terminal or through an agent. Likewise, `magi init`, `hub *`, `sync`, `validate`, `verify`, `tags *`, and `math *` have no buttons either.

The **⚡ MAGI MODE** toggle in the top bar switches the tactical theme: red is combat state (dark), blue is silent watch (light), and ☀︎/☽ switches between the two.

The ◐ in the bottom-right corner is the material and backdrop panel: glass blur, opacity, CRT scanlines, and **which artwork to use** — click one thumbnail to pin it, several to rotate only among those, none to let it rotate by window shape (red and blue remember separately). To use your own images, drop them in `~/.config/magi/ui-backgrounds/blue|red/`.

> [!FIX]
> - **Port already in use**: switch `--port`, or shut down the previous instance first.
> - **Changed code / upgraded, but the UI didn't change**: static files take effect immediately, but **backend changes require restarting `magi ui`**. If styles aren't updating, that's the browser cache — hard-refresh once.
> - **The graph is empty**: run `magi graph build` first.
> - **The dashboard won't open, or shows no workspace**: switch workspaces from the top bar; the dashboard only listens on `127.0.0.1` with a Host allowlist, so **by default it's not reachable from another machine** (use SSH port forwarding for remote access).

---

## Troubleshooting quick reference {#troubleshoot}

Look things up by symptom — you don't need to remember which command belongs where. The same table is available in the terminal:

```powershell
magi guide --symptoms                       # The whole index (~84 entries)
magi guide --symptoms --search "ollama"     # Filtered by keyword
```

Or paste the error to your agent and let the `magi_guide` skill look it up (see [1.2](#howto-read)).

| Symptom | Run this first |
|---|---|
| No idea what to do next | `magi sync` — check the last line, `->`; `magi sync --fix` lets it repair |
| Maintaining a multi-topic hub one by one | `magi each <command>` — run it once at the hub root |
| Installed, but `magi` isn't found | Open a **new terminal**; if that still doesn't work, add `~/.local/bin` to PATH |
| Upgrade fails with `failed to remove directory ... Lib` | On Windows a running `magi ui` holds the install directory. Stop the dashboard, then upgrade |
| A feature complains about a missing dependency | `magi setup --check` |
| The command says `no workspace found` | `cd` into the topic directory, or add `--topic-dir` |
| Don't know where a topic lives | `magi hub list` / `magi hub resolve <hub> <slug>` |
| Ingestion finished, but it's not in the library | You forgot `magi ingest finalize` |
| The graph is stale | `magi graph build` — it has no incremental mode |
| Can't search for something you just wrote | `magi index` — it never triggers automatically |
| Search returns no semantic results | `magi setup --check` — a stopped Ollama starts itself, so it's not installed or the model isn't pulled; then `magi index` to backfill vectors |
| Wikilinks won't open / lots of broken links | `magi graph browse broken` |
| Duplicate concepts, sprawling tags | `magi link . --dedup-only`; `magi tags extract` |
| Card format errors | `magi lint --fix` |
| Formulas render incorrectly | `magi math format` → `magi math check` (whole library; `--json` hands the list to the `wiki_math_fix` skill) |
| Citations won't export | Check the reference card's `title/authors/year/arxiv_id` frontmatter |
| A claim is marked unverified | The evidence quote must match the source verbatim, and it must be a single line |
| The radar has nothing new | Check `arxiv_categories` / `seed_arxiv_ids`; widen `--days` |
| The scheduled task never fires | Windows: `schtasks /Query`; on Linux it was never installed in the first place — write the crontab yourself |
| Changed the config, but nothing happened | Validate it with `python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"` — YAML parse failures fail silently |
| Want to see exactly what flags a command takes | `magi <command> --help`, or the **CLI command reference** at the top of this page |

> [!TIP]
> The full set of flags for every command is authoritative in `magi <command> --help` — this guide covers **when to use something, what to expect, and how to recover from errors**; it doesn't duplicate the flag reference.
