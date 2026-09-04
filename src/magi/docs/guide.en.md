# MAGI User Guide

From a fresh install to a working project you can search, cite, and write from.

Every chapter follows the same rhythm: **what to do → how to do it → what you should see → what to do if you don't**. Jump around anytime with the sidebar; use `Ctrl+F` to search the full page directly; every command block has a one-click copy button in its corner.

---

## Get it running once {#start}

From nothing to a project you can search — three commands and one sentence to your agent:

```powershell
pipx upgrade --install magi-research     # 1. install or upgrade (idempotent)
mkdir my-topic ; cd my-topic ; magi init # 2. one project
magi install                             # 3. into your agent CLI: skills, protocol, stop gate
magi ingest auto                         # after dropping PDFs into inbox/
```

One directory per project, and nothing above it. **Cross-project search runs off the
user-level registry** (`magi kb list`): `magi search` reads the project you are in,
and `--scope all` reaches the enabled
project by default, so they never have to share a parent directory.

Then say to your agent, in Claude Code or Codex: **"compile the backlog"**. That is the one step no command can do — it reads the papers and writes the cards. When it finishes, `magi index` and you can search.

The rest of this chapter is what those layers are and how to read the manual.

MAGI has three layers, and their jobs don't overlap:

| Layer | What it is | How you use it |
|---|---|---|
| **magi CLI** | Every deterministic operation: ingest, graph-build, search, verify, tasks, radar | Type it in a terminal, or have an agent type it for you |
| **skills** | Teach the agent when and why to call each pipeline | Trigger with a sentence in Claude Code / Codex |
| **project** | Knowledge on disk: `raw/` `wiki/` `output/` `drafts/` | View directly with Obsidian, an editor, or the dashboard |

An agent's context is disposable — **state always lives on disk**. So any step you interrupt can pick up right where it left off.

> [!WARN]
> **The agent isn't optional.** Going from raw sources in `raw/` to concept cards in `wiki/` is a step of understanding and synthesis — there's no CLI command for it. Only the `compile` skill, driving an LLM, can do it. Install just the CLI without connecting an agent host, and you can ingest papers and run keyword searches, but you'll never get concept cards, a knowledge graph, or cited Q&A. Section 2.4 covers how to connect one.

### Three ways to get started

**① Brand-new user** — install per Chapter 2, then two commands:

```powershell
mkdir quantum-toys ; cd quantum-toys
magi init --name "Quantum Toys" --scope "Quantum phenomena in toy models"
magi install                 # skills + the AGENTS.md protocol block + the session hooks
```

After that, one word. Bare `magi` is `magi next`: it derives what this
project needs from its own notes and proposes it — including `magi sync --fix`
and `magi pm init`, at the moment each is actually worth running.

```text
No propositions yet — nothing here is being tested yet.
  magi thread new <slug> --kind proposition --title '<claim>' --purpose '<why now>'
  magi sync    # what the project itself needs
```

**② Existing Wikify user** — leave your data as-is; jump straight to Chapter 3, three commands to migrate.

**③ Just want to try it** — `magi init` works right away in any empty directory, and it registers the project so `magi search` finds it from anywhere else too.

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
magi guide --search "no project found"   # Full-text search — paste the error verbatim
magi guide --symptoms               # The whole symptom -> cause -> fix index
```

`--json` is the machine format for agents; `--lang en` switches language.

**Let the agent do the diagnosing**: the manual ships with the CLI, so it works offline and nobody has to remember it. Paste the error as-is and the agent will run `magi guide --search`, reading the manual by symptom, read the relevant chapter, confirm the current state with `magi sync` / `magi setup --check`, and hand you the exact command the manual prescribes — instead of inventing a flag from memory.

> [!NOTE]
> Every command in this manual is checked against the real CLI, and a test keeps it from drifting. That makes an agent quoting the manual considerably more reliable than an agent recalling one — for anything MAGI-related, it's worth telling it to look it up first.

### How to read `magi sync`

`magi sync` is the first command you run every time you sit down, and the first command you run whenever you're stuck:

```text
MAGI SYSTEM ONLINE — sync ratio 33.3%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     beads offline
`- CASPER    (retrieval)  index missing · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the ingest skill to start filling this project
  -> magi pm init   # initialize beads in this project
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
- **BALTHASAR** = how legible the research state is: `1 − debt/notes`, where debt is something that happened in `threads/` and was not written down. It is cleanliness, not progress — six open propositions and no debt is perfectly healthy. A project with no `threads/` yet keeps the old measure (0.6 task-store reachability + 0.4 state readability); `--kb-only` mode excludes the core entirely.
- **CASPER** = 0.7 index freshness + 0.3 vector coverage

> [!NOTE]
> Sync ratio isn't a score for "how much knowledge you have." An empty project can still get a perfect MELCHIOR score — it only penalizes **staleness, backlog, and unverified claims**, never "hasn't started yet." So a freshly created project showing 33.3% is normal: that's "only the knowledge core is online, out of three." Run `magi pm init` and `magi index` and it climbs from there.
> Outside of any project, sync ratio shows blank rather than 0 — it won't make up a number for you.

---

## Installation {#install}

Installing is one command, and it is the same command you use to upgrade:

```powershell
pipx upgrade --install magi-research
```

It installs when MAGI is missing, upgrades when it is out of date, and does nothing when it is already current — so re-run it as often as you like. (`--install` needs pipx 1.5 or newer; on an older pipx use `pipx install magi-research` the first time and `pipx upgrade magi-research` after that.)

No git required, and MAGI never calls pipx or uv again after the install. **pipx** is the default and needs Python 3.10+ already on the machine; **uv** is the alternative for a machine without one, since it brings its own 3.12:

```powershell
uv tool install --force magi-research   # the uv equivalent — also install-or-upgrade
```

Everything below is per-project installs and the optional external tools some ingestion routes need.

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

1. Find a package manager: pipx if you have it, else install pipx onto a Python 3.10+ it finds, else fall back to [uv](https://docs.astral.sh/uv/) — which brings its own Python 3.12, so **you don't need Python pre-installed**;
2. `pipx upgrade --install magi-research` (or the uv equivalent) — from PyPI, install or upgrade in one step;
3. Run `magi setup`: ask which optional features you want, install Beads (`bd`) if you want task tracking, pull the Ollama embedding model, register the Claude Code plugin, report which agent CLIs it found, check for leftover legacy Wikify installs, and print a health-check table at the end.

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
pipx upgrade --install magi-research    # install or upgrade — the same command for both
pipx uninstall magi-research            # uninstall
pipx list                               # see what version is installed

# Or with uv, if you would rather not have a Python of your own:
uv tool install --force magi-research   # install or upgrade
uv tool uninstall magi-research         # uninstall
uv tool list                            # see what version is installed

# To try changes that are not released yet:
uv tool install --force git+https://github.com/Misaka16384/magi
```

> [!WARN]
> pipx and uv put their shims in the **same** directory (`~/.local/bin`). Installing MAGI with both, then uninstalling one, deletes the shim the other is still relying on — `magi` disappears from PATH while `uv tool list` still swears it is installed. Pick one and stay with it; if you did hit this, `uv tool install --force magi-research` (or the pipx equivalent) puts the shim back.

### Staying current {#update}

MAGI tells you when there is a newer release, and can install it for you.

```powershell
magi update            # check, then upgrade (asks first)
magi update --check    # only tell me; change nothing
magi update --json     # machine-readable
```

After any command, a one-line notice appears on stderr when a newer release
exists. It never delays anything: the line comes from a cache the *previous*
invocation filled in a background thread, so no run of `magi` ever waits on
pypi.org. Turn it off with `MAGI_NO_UPDATE_CHECK=1`, or by setting
`update_check: false` in the global settings file.

The check reads `pypi.org/simple/`, the index installers actually resolve
against — not the JSON API, which publishes a version minutes earlier. That
gap is why a notice sourced from the JSON API can announce a version your
package manager then correctly refuses to install.

In the WebUI, a badge appears next to the version number; clicking it opens a
dialog with **Upgrade now**.

> [!NOTE]
> The dashboard shuts itself down to upgrade, then starts again on the same
> address, and the page comes back on its own. This is not caution: a running
> `magi ui` holds its own environment's `python.exe` and every loaded extension
> module open, and on Windows a package manager cannot replace files that are
> open. Upgrading in place would fail halfway and leave a broken install — in
> front of somebody whose page had just gone blank. So a detached helper waits
> for the server to exit, upgrades, relaunches it, and writes down what
> happened; the reopened dashboard reports the result, including the case where
> the command succeeded but the version did not actually change.

A source checkout is never upgraded by a package manager — `magi update` says
so and stops.

> [!NOTE]
> **If you installed with plain `pip`**, the upgrade command is
> `python -m pip install --upgrade magi-research` — and the `--upgrade` is
> the whole point. pip is the one tool here whose *install* command does not
> install: run `pip install magi-research` over a copy you already have and
> it prints `Requirement already satisfied`, exits 0, and changes nothing.
> That reads exactly like a successful upgrade, and the version number is the
> only thing that gives it away. `magi update` detects a pip install — user
> site or interpreter-wide — and runs the right command for you. Where the
> Python marks itself externally managed (PEP 668: Debian, Fedora, Homebrew,
> and any Python `uv` installed for you), pip refuses either way — so MAGI
> says so instead of running a command that was never going to work, and
> points you at pipx.

> [!NOTE]
> **On Windows the upgrade can be blocked by `magi` itself.** pipx may point
> `~/.local/bin/magi.exe` at the venv's `Scripts/magi.exe` with a symlink, so
> typing `magi` maps the very file the upgrade has to replace — and Windows
> will not delete a program that is running. Nothing else is holding it; the
> command in the way is the one doing the upgrading. You do not have to run
> anything by hand: the upgrade is handed to a helper that waits for the
> command to exit, does the work, and writes down the result. Your shell comes
> back immediately, and the next `magi` command tells you how it went.

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
> Just want the notes and cards, no task management? `magi setup --kb-only` skips Beads; `magi sync` then shows the BALTHASAR core as disabled and excludes it from the sync ratio. The mode is stored in `~/.config/magi/settings.json` — restore it anytime with `magi setup --full`.

### Install once globally, or per project {#install-scope}

This is the one people most often get backwards. **You only need one global CLI install — what repeats per project is `magi init` / `magi install`.**

| Thing | Where it lives | How many |
|---|---|---|
| `magi` CLI | User-level (`pipx install` / `uv tool install`), on PATH | One per machine |
| skills | **Inside each project**, one directory per host (`magi skills install`) | One set per project |
| project | Your project directory | One per project |
| Global config & registry | `~/.config/magi/` (on Windows: `C:\Users\<you>\.config\magi\`, **not** AppData) | One per machine |

Install the CLI once; after that, starting a new project only takes `magi init` + `magi install`.

`magi install` does three things, and an agent runs badly without any one of them: it puts the eight skills where the host looks for them; it writes the current protocol into the `AGENTS.md` managed block (leaving everything you wrote around it untouched); and it installs Claude Code's hooks. **Host enforcement is not symmetric**: Claude Code is the only host that documents any hook API, so on the other hosts the same rules exist as instructions in the block — which an agent can ignore, and sometimes will. The command says so rather than reporting four identical installs.

Three hooks, and only the first can refuse anything:

| Hook | Runs | What it does |
|---|---|---|
| `Stop` | `magi sync --close --hook` | Refuses to end a session that left bookkeeping undone |
| `PreToolUse` (on `Task`) | `magi hook fanout` | **Counts** sub-agent spawns; says the running total every 25th |
| `SessionStart` | `magi hook session-start` | Hands the agent what `magi next` would say, and nothing when there is nothing |

The fan-out hook counts and never blocks. Invariant 5 in the managed block asks the agent to say what a fan-out costs before starting one, and a rule only the agent enforces stops holding in exactly the sessions where it matters; counting makes it checkable. Blocking would make it a budget, and MAGI's budget covers only the calls MAGI itself starts — a sub-agent is your agent's work on your account.

Every 25th, not every one past the 25th: the skills cap a fan-out at ten concurrent and require the total to be announced first, so a compile of a dozen sources is normal and correct. A hook that fired there would be reminding the one workflow that had already done what it was asking for — and a hook that is noise gets switched off along with the gate beside it.

`magi hook` is called by the host, not typed by you. Its one hard rule is that it can never break a session: every path exits 0 with parseable JSON, including a missing project, an unparseable payload and a file it cannot write. A hook that errors is a hook you turn off, and then the gate it was guarding is gone too.

Your own hooks on the same events are left exactly as they were — MAGI recognises its own by command string, so installing twice changes nothing.

> [!WARN]
> A true in-project install (`uv venv && uv pip install -e .`) is only for people modifying MAGI's source. A `magi` installed that way **is not on PATH** — you can only invoke it as `.venv\Scripts\python.exe -m magi.cli ...`. Skills, Claude Code's SessionStart hook, and the radar's scheduled job all look for the bare command name `magi` on PATH, and won't find it there. For everyday use, install with `pipx` (or `uv tool install`).

### Teach your CLI agent to use MAGI {#install-hosts}

This step isn't a nice-to-have: **the project's compile step only runs inside an agent** (see Chapter 6).

**One command, run inside the project**, teaches every agent CLI on your machine:

```powershell
cd <your project directory>
magi skills install              # into this project (the default)
magi skills where                # where each CLI reads from, and what is installed
magi skills install --dry-run    # see the exact files first, write nothing
magi skills uninstall            # take them back out
```

The skill files ship with the CLI — **no repo clone, no network**.

> [!WARN]
> **The default is this project, not your whole machine.** All 9 skills revolve around one research project — ingest into its `raw/`, compile into its `wiki/`, query its graph — so a machine-wide install makes every unrelated project carry them for nothing. If you really want that: `magi skills install --scope global` (it warns once).
> Installing into the project has a second benefit: the files travel with the repo, so a collaborator who clones it gets them.

| Host | Global | Project | How it fires |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/skill-name`, and auto by description |
| **Codex** | `~/.agents/skills/` (plus `~/.codex/skills/`) | `<repo root>/.agents/skills/` | `$skill-name`, or Codex picks it by description |
| **Antigravity (agy)** | `~/.gemini/config/skills/` | `<repo root>/.agents/skills/` | Name it in your prompt, or auto by description; `/skills` browses |
| **qwen-code** | `~/.agents/skills/` | `<repo root>/.agents/skills/` | Name it in your prompt, or auto by description |
| **opencode** | `~/.config/opencode/commands/` + `skills/` | `.opencode/commands/` + `skills/` | `/skill-name` |

> [!NOTE]
> **Not every CLI has slash commands.** Claude Code and opencode do; Codex uses `$skill-name`; agy only fires on description matching (`/skills` is just a browser). So the one habit that works everywhere is simply to **say what you want** — "ingest the papers in inbox", "look up this error" — and let the matching skill load itself.
> `.agents/skills/` is the cross-agent convention Codex, agy and qwen share, so one copy serves all three. opencode scans it too, but its slash commands come from its own `.opencode/commands/`, so the installer writes there as well.

> [!NOTE]
> **Your CLI isn't in the table? Add it — no code.** There are far too many agent CLIs to enumerate, so a host is a *record*: `research.hosts` in `config.yaml` takes entries of exactly the shape the built-in ones have. Add one and `magi skills where` lists it, `magi skills install --host <key>` writes to it, and `magi review` can call it.
>
> ```yaml
> research:
>   hosts:
>     - key: mycli
>       label: My CLI
>       bin: mycli                     # what it is called on PATH
>       marker: "{home}/.mycli"        # a directory whose presence proves it is installed
>       drops:
>         - kind: skill                # skill | command
>           global_dir: "{home}/.mycli/skills"
>           project_dir: "{root}/.agents/skills"
>           layout: dir                # dir -> <dir>/<name>/SKILL.md ; flat -> <dir>/<name>.md
>           invoke: "/{name}"          # what you type; shown back in the report
>       argv: ["{bin}", "-p", "{prompt}"]   # omit if it has no headless mode
>       model_flag: "--model"
> ```
>
> The substitutions are `{home}`, `{config}` (`XDG_CONFIG_HOME`) and `{root}` (this project). The one thing a record **cannot** declare is how to read that CLI's saved sessions: every vendor stores them differently, and `magi reflect read` needs a parser, not a template. A host with no reader simply contributes no sessions to the slow loop — nothing else about it changes.
> A record whose `key` matches a built-in replaces that built-in outright, which is how you point MAGI at a CLI you installed under another name.

**Claude Code can also use the plugin** (the one-line installer does this for you): skills arrive namespaced, and the plugin adds a SessionStart hook that runs `magi sync` at the start of every session:

```powershell
claude plugin marketplace add Misaka16384/magi
claude plugin install magi
claude plugin install <local-repo-dir>      # local development mode
```

The plugin and `magi skills install` coexist — one gives you `/magi:skill-name`, the other `/skill-name`.

**Any other agent** — the project's `CLAUDE.md` and `AGENTS.md` (identical content, two copies) are the onboarding protocol: run `magi sync` on entry, which commands map to which core, use `magi guide --search` when stuck, and never answer research questions from memory. Any host that reads either file can work here; if it reads neither, pasting `magi --help` is enough.

> [!EXPECT]
> `magi skills where` shows 9/9 on the project rows. Start a fresh agent session **from that project directory** and the skills appear under `/` (Claude Code, opencode), or just say "ingest the papers in inbox" and watch it act. `magi setup --check` also shows the per-CLI count for the project you are in.

> [!FIX]
> - **Installed but not showing**: skills are scanned at startup — **start a new session from the project directory** (project skills are only visible when the CLI is launched there).
> - **Not sure where they went**: `magi skills where` prints the real path and count per CLI.
> - **It says skipped**: a file of the same name was already there and didn't look like ours, so it wasn't overwritten. Check it, then `magi skills install --force`.
> - **The agent calls a script that doesn't exist** (`python bin/llm-wiki.py ...`): old Wikify SKILL.md files are still around — run `magi setup --remove-legacy`.
> - **To remove them**: `magi skills uninstall [--host X] [--scope project]`.
> - `magi setup`, `magi migrate`, and `magi ui` **have no skill** — they are CLI-only commands.

### External tools — all optional {#install-tools}

**Start here:** run `magi setup`. It asks you about each one, tells you what it
unlocks, and hands you the official download link. Say no to anything you don't
want and it stops being mentioned — `magi setup --check` will not report it as a
problem, because a tool you chose not to install is not a fault in your machine.
Changed your mind? `magi setup --optionals`.

| Tool | What it unlocks | What happens without it | Where to get it |
|---|---|---|---|
| **Beads** (`bd`) | Task tracking | Task features degrade; everything else is unaffected | `magi setup` installs it |
| **Ollama** + `qwen3-embedding:0.6b` | Semantic search, semantic linking, radar relevance scoring | Search falls back to keyword matching; `magi link` errors out | https://ollama.com/download |
| **Ollama** + `glm-ocr:q8_0` | Fully local OCR ingestion | You're limited to cloud OCR, the LaTeX route, or arXiv HTML | https://ollama.com/download |
| **Pandoc** | `magi ingest arxiv-html` and `magi ingest tex` — the two best-fidelity routes | Can't process arXiv HTML or source packages | https://pandoc.org/installing.html |
| **Poppler** (`pdftoppm`) | Rendering pages for local OCR | Local OCR errors out directly | https://poppler.freedesktop.org/ |
| **pdflatex** | Deep verification of math formulas | Falls back to lightweight `pylatexenc` verification | https://www.tug.org/texlive/ |
| **Ghostscript** | Converting EPS figures in LaTeX source to raster images | EPS files are copied as-is and won't display in markdown | https://www.ghostscript.com/ |
| **MinerU** (hosted, not a binary) | Cloud PDF conversion, strong on layout and formulas | Use local OCR, or the LaTeX/HTML routes | https://mineru.net/ |

> [!NOTE]
> You never need to run `ollama serve` yourself. If Ollama is installed but not
> running, MAGI starts it the first time something needs it (once per process).
> Set `ollama.autostart: false` in `config.yaml`, or `MAGI_NO_OLLAMA_AUTOSTART=1`,
> to keep the daemon under your own control.

```powershell
ollama pull qwen3-embedding:0.6b     # vector search (~640MB)
ollama pull glm-ocr:q8_0             # local OCR (optional)
```

`pandoc-crossref` is optional; without it cross-references degrade but conversion still works. From a source checkout the Windows build sits in `vendor/windows/` — add it to PATH or set `tools.pandoc_crossref_path` in the project's `config.yaml`. A pipx or uv install does not include it (a 19 MB Windows-only binary has no business shipping to macOS and Linux users); download it from https://github.com/lierdakil/pandoc-crossref/releases if you want it.

The last rows of the health check are the agent CLIs on your machine (claude / codex / agy / qwen / opencode): whether each is installed, and how many skills it has. If any are missing, it prints the command to fix that.

> [!WARN]
> `magi setup --check`'s health check only looks at PATH — it **doesn't read** the `tools.*` paths in `config.yaml`. So if the table shows `[-] pdftoppm` but you've already set an absolute path in the config, ingestion will actually still work — trust the real run, not the table.

---

## Migrating from Wikify {#migrate}

Migrating is one command:

```powershell
magi migrate            # from the old repo root
```

It carries your old config across, flags stale project-level skills, and runs `magi sync --fix` in every project. It does **not** set up task tracking any more: a task store belongs to a project, not to the directory above it, so each project asks for its own when `magi sync` decides it wants one. `raw/`, `wiki/` and `inbox/` formats are unchanged, so your data comes over as-is. Below: what each step touches, and the old-command-to-new-command table.

MAGI is a rebuild of Wikify: the script collection becomes a unified CLI, task state moves out to Beads, and you get hybrid search, claim provenance, and a literature radar. **The `raw/`, `wiki/`, and `inbox/` formats haven't changed — your existing data is fully compatible.**

### Three commands {#migrate-steps}

```powershell
# 1. Install the new version (the one-liner from Chapter 2)
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. Remove the old install copy — the old SKILL.md tells the agent to call scripts that no longer exist
magi setup --remove-legacy

# 3. Migrate every project from the hub root in one shot (non-destructive)
cd <your-KnowledgeHub>
magi migrate
```

`magi migrate` automatically figures out whether the path you give it is a hub or a single project: hub mode migrates every **unarchived** project under `topics/` in one pass; single-project mode migrates only the current one.

**It only ever adds.** It fills in whatever's missing — `CLAUDE.md` / `AGENTS.md` / `config.yaml` / `scratch/` and the `_index.md` files at every level — then rebuilds `output/graph.db` (adding the claims/evidence tables) and `wiki/{concepts,references}/_index.md`. Any file that already exists is skipped outright — not a single character of `raw/`, `wiki/` content, `config.md`, or `log.md` gets touched.

**Your old settings come with you.** It looks for the previous `config.yaml` in `<project>/.agents/`, `<hub>/.agents/`, `~/.claude` and `~/.gemini`, and copies values — MinerU token, model names, dpi, semantic-link thresholds — into the new config. Only settings still at their default are filled, so an edit you made after migrating is never overwritten, and it prints which keys it carried (key names only, never the token itself).

> [!NOTE]
> `magi migrate` has **no** `--force`. Non-destructiveness isn't guaranteed by a flag — it's hard-coded into the implementation: when it calls the scaffolding, it never passes `--force`, so all it can ever do is create missing files. Running it again is safe; the second run just takes the "refresh index" branch. There *is* a `--dry-run`, which prints what each project would get without touching anything.

One step is left, because it needs a project to install into:

```powershell
cd <your-project> && magi install
```

It installs into every agent CLI it detects on the machine — it does not ask.
`magi skills install` is the one that asks, and only when several are present
and you did not name one.

> [!EXPECT]
> Each project prints `Migrating project: <path>`, then `config carried from ...` when there were old settings to bring across, then `magi graph build: ok` / `magi wiki reindex: ok`. At the end, "Finishing up" runs `magi sync --fix` per project and reports the new sync ratio.

> [!FIX]
> - **A project that reports `FAILED` in the middle**: scaffolding failure now counts — the summary line and the exit code both reflect it. A `FAILED` on `graph build` or `wiki reindex` deliberately does not: those are derived from files that are already in place, and `magi sync --fix` in that project rebuilds them.
> - **You were not reminded to build indexes**: migration runs `magi sync --fix` per project, which covers the graph and the index. If you passed `--minimal`, it did neither — run `magi sync --fix` in each one yourself.
> - **The agent still mentions the old commands after migrating**: either `magi setup --remove-legacy` hasn't run, or the agent host's skill cache hasn't refreshed — restart the agent session.
> - **A project didn't get migrated**: migration skips any directory that has neither `wiki/` nor `raw/`. Go into that directory and run `magi migrate` on its own — it registers the project on the way through.
> - **It throws a raw Python exception**: the scaffolding step has no exception guard for this; the usual cause is a locked file or insufficient permissions (on Windows, an editor holding `CLAUDE.md` open). Close whatever's holding the file and rerun — you won't be left with a half-finished result.

> [!WARN]
> **Project-local old skills need separate handling.** If your hub or project directory has a `.agents/skills/` (copied there in the Wikify days), `magi setup --remove-legacy` **will not find it** — that only scans `~/.claude` and `~/.gemini`. And `.agents/skills/` is exactly what Codex, agy and opencode all read, so those stale SKILL.md files will send your agent after scripts that no longer exist. `magi migrate` now detects this and warns; rename it to keep a backup: `mv .agents .agents.wikify-backup`.

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

## Adopting a folder you already have {#adopt}

`magi migrate` is for a project Wikify built. A folder that has never been near
MAGI but already holds half a year of work — papers, your own drafts, code and
data, arranged however they ended up — goes this way instead:

```powershell
magi adopt survey .                     # read-only inventory; nothing moves
magi init --name "..." --scope "..."    # scaffold in place: only adds files
magi adopt apply plan.json --dry-run    # what would move, what gets repointed
magi adopt apply plan.json
```

Besides listing the folder, `survey` pulls every arXiv id and DOI written in the
markdown. A references table is often half the project's sources already, and
extracting it is a regex; deciding what each one is worth is the reading. When
the whole folder sits under one wrapper directory it descends and says so —
otherwise a repo with everything under `research/` inventories as a single row
reading "112 files", which tells nobody anything.

`survey --json` is what the skill reads. Its keys: `root` (the folder surveyed),
`is_project` (already a MAGI project?), `descended_into` (the wrapper
directories it stepped through, outermost first; empty when it stayed put),
`entries` (one row per item: `path`, `name`, `kind` — `dir` or `file` —
`bytes`, `types` (a suffix histogram), `scaffold` and `name_collision` (does
the name belong to MAGI's own layout — already, or would it), and for a
directory `files` and `depth`, for a text file `head`, its first line),
`markdown_files` (count), `internal_links` (count of `[[…]]` and relative
markdown links between the files), and `identities` — `{"arxiv": [...],
"doi": [...]}`, every id found in the markdown, deduplicated.

The plan is JSON, written by the agent and read by a person:

```json
{"moves": [{"from": "gate0", "to": "drafts/gate0"},
           {"from": "notes", "to": "drafts/notes"}]}
```

### The references get repaired {#adopt-links}

A research folder is held together by ordinary relative paths. Moving whole
directories happens to preserve them — two subtrees moved under one new parent
still reach each other through `../` — but a folder messy enough to be worth
adopting cannot be fitted to MAGI's shape that way: sooner or later a file has
to go somewhere its neighbours do not.

`apply` does not stop there; it repairs them. **The arithmetic that proves a
link is about to break is the same arithmetic that says where it should point
instead.** That includes paths written inside code spans — nothing renders
those, so nothing else would ever notice they stopped matching. On one real
repository, all 28 references needing repair were of exactly that kind.

```powershell
magi adopt apply plan.json --no-rewrite  # move only (refuses unless --break-links)
magi adopt apply plan.json --no-prose    # real links only, leave code spans alone
```

### Undo {#adopt-undo}

Every apply writes a manifest under `output/adopt/` recording each move **and
each edit**:

```powershell
magi adopt undo                                  # the most recent one
magi adopt undo output/adopt/2026-09-02-021152.json
```

The words go back with the files — verified byte-for-byte against two real
repositories.

> [!NOTE]
> `apply` never deletes, never overwrites, never moves anything out of the
> project, and never touches MAGI's own scaffold. One invalid entry means the
> whole plan is refused: a half-adopted folder is worse than an untouched one.

The matching skill is `adopt` — an operating manual for the agent, so a person
only reads the plan and says yes. Its last step is not "the files are in place"
but `magi next` saying something real: a project still answering "no
propositions" was tidied, not adopted.

## Setting up your project {#workspace}

Two commands make a project:

```powershell
magi init               # inside the project's own folder
magi install            # into your agent CLI: skills, protocol block, stop gate
```

One directory per project, and nothing above it. A second project is a second directory anywhere you like; they find each other through the user-level registry, not through a shared parent. Below: what gets generated, how to manage projects, and how MAGI decides which project it is looking at.

### One project or several {#workspace-shape}

One project, one directory, `magi init` and you are done. A second project is a
second directory — no shared parent, no planning ahead. `magi init` registers
it in a user-level list, and that list is what ties them together:

```powershell
mkdir my-topic ; cd my-topic
magi init --name "Display name" --scope "one line on what belongs here and what does not"
magi install
magi pm init           # optional: a task store for mechanical work (git-inits the directory)
```

`magi search` reads only the project you are standing in; `--scope all` adds the
ones `research.search_projects` names. `magi kb list`
shows them. v1's hub — a parent directory with `wikis.json` and `topics/` — is
gone: the registry was the part doing the work, and it is now per-machine, so a
project is findable wherever it lives.

`--scope` is not decoration. It goes into the `AGENTS.md` managed block and
becomes what an agent judges "does this paper belong here" against. **The more
specific it is, the better every later automatic decision gets.**

### What `magi init` generates {#workspace-layout}

```text
my-topic/
├─ AGENTS.md               agent onboarding protocol (the `magi:begin` managed block + whatever you write around it)
├─ CLAUDE.md               one line, `@AGENTS.md` — there is only ever one protocol
├─ config.md               human-readable description of this project (title + research scope)
├─ config.yaml             this project's config (OCR, models, radar... see Chapter 5)
├─ decisions.md            what a person decided, and nothing else; an agent transcribes it
├─ inbox/                  drop zone for unprocessed material (dump PDFs here) · notes.md is your unsorted scratch box
├─ raw/                    ingested source literature, as Markdown
│   articles/ papers/ repos/ notes/ data/
├─ wiki/                   compiled output
│   concepts/  concept cards    references/ reference cards    topics/  topic pages
├─ threads/                propositions, questions, research lines (a forum; `magi thread`)
├─ drafts/                 derivations and working-out
├─ tools/                  scripts that check a derivation; a proposition's `evidence:` names them
├─ output/                 graph.db, index.db, MAP.md, the radar ledger
└─ scratch/                the agent's scratch pad, safe to clear anytime
```

Every directory except `inbox/` and `scratch/` gets an `_index.md` directory listing.

> [!NOTE]
> **`wiki/theses/` is gone.** Its two halves went to different places: the working-out to `drafts/`, and the claims it made to `threads/`, where each one carries a status somebody keeps current. An older project keeps its copy until `magi migrate` moves it.

> [!TIP]
> Open the **project directory** in Obsidian. Add these two regex patterns under Settings → Files and Links → Excluded files, and the graph view will show nothing but pure knowledge cards:
> ```regex
> /(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
> ```
> ```regex
> /^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
> ```

### Working across projects {#workspace-hub}

There is no layer above a project. A project is a directory; `magi init`
registers it in a user-level list, and that list is what makes several of them
one searchable whole:

```powershell
magi kb list                      # every project this machine knows about
magi kb disable <name>            # stop other projects reading it
magi search "toric code"          # searches here, then every enabled project
```

v1 had a *hub*: a parent directory with a `wikis.json` registry, `topics/`
underneath, and commands to register, archive, restore and fan out across them.
It is gone. The registry it existed to hold is now per-machine rather than per
parent directory, which is the part that was actually doing the work — and a
project no longer has to live in a particular place to be findable. Archiving
a project is `magi kb disable` plus moving the directory wherever you keep
finished things.

A project that was under a hub keeps working: `magi migrate` registers each
one and leaves the files where they are. The hub's own `wikis.json`, `topics/`
and `log.md` become inert — delete them when you are ready.

### How MAGI finds the "current project" {#workspace-discovery}

Every command locates the project by **walking up from the current directory** (up to 30 levels):

- **A project root** is identified by having either `wiki/` or `raw/`, plus at least one of `config.md` / `log.md` / `config.yaml`.
- **A hub root** is identified by having both `wikis.json` and `topics/`.

**No environment variable changes this behavior** — there's no such thing as `MAGI_HOME`. To operate across directories, use explicit arguments like `--project-dir` / `--db`.

> [!FIX]
> - **You get `no project found`**: you're standing at the hub root or higher. `cd` into the specific project directory, or add `--project-dir <path>`.
> - **Rerunning `magi init` says `Skipping existing ...`**: that's not an error. It doesn't overwrite existing files by default; if you really want to regenerate them with a new `--name`/`--scope`, add `--force` (this discards any manual edits you made to those files).

> [!WARN]
> **Don't nest projects inside each other.** `magi init` doesn't check whether the parent directory is already a project. If you `init` a project inside another project's `raw/`, the outer project's compile-backlog count will pull in every `raw/*.md` from the inner one, and the sync ratio will drop for no obvious reason. If you've already nested them, move the inner one outside the outer project's `raw/ wiki/ inbox/ output/`.

---

## Where it is slow, and why {#slow}

Two things look like a hang and are not.

### 15 seconds per figure

Figures are fetched one at a time with a 15-second wait between them. Measured
across 37 papers: the time tracks the figure count almost perfectly and does
not track body size at all — 692 KB of text took 20 s, 113 KB took 16 s, and a
23-figure paper took 356 s of which about 345 was waiting.

That is arXiv's `robots.txt` (`Crawl-delay: 15` for a default user agent), not
a performance problem. To skip them:

```powershell
magi ingest batch-run --no-figures
```

Parallelising does not help: the throttle is one lock shared across threads, so
a thread pool moves the waiting rather than removing it. Only sending fewer
requests helps.

### Do not pipe a long command to `tail`

```powershell
magi index | tail -20        # shows nothing at all until it finishes
magi ingest batch-run | tail -60
```

`magi index` prints a flushed progress line every 3 seconds, but `tail` cannot
know which lines are the last twenty until the stream ends. **A perfectly
healthy 50-minute index looks completely silent**, which is enough to conclude
it has wedged.

For the same reason, never pipe the mutation suite to `tail`: it edits source
files and restores them, and SIGPIPE killing it mid-restore leaves those edits
behind — its own docstring warns that an interrupted run is indistinguishable
from your unsaved work. Redirect instead:

```powershell
magi index > index.log 2>&1
python -m tests.mutations > mut.log 2>&1
```

## Ingesting literature {#ingest}

Ingesting is one command:

```powershell
magi ingest auto              # everything sitting in inbox/
magi ingest auto paper.pdf    # or one named file
```

It picks the route by what the file is — LaTeX source for arXiv bundles; for a
PDF, its own text layer when that suffices, else cloud OCR with a token or local
OCR without one — and finalises for you. Reach for the specific commands below only when you need a page range, want to force a route, or are fighting a difficult scan.

### Have a link instead of a file? Queue it {#ingest-queue}

When you have an arXiv link, a DOI, or a journal page rather than a PDF on disk,
don't download anything. Hand it over and let MAGI pick the route:

```powershell
magi ingest url "https://arxiv.org/abs/2608.16520"   # or a DOI, or several at once
magi ingest url 2608.16520 --expect "fracton"   # an id from memory: fetch the title, refuse a mismatch
magi ingest batch-run                                 # fetch + convert, unattended
magi ingest review                                    # see what came out
magi ingest review --item <ID> --decision approve      # one at a time
magi ingest review --commit                           # only now does anything enter raw/
```

`--library <NAME>` queues into a registered project by name, so you don't
have to be standing in it (`magi kb list` shows the names).

Two things about this worth knowing:

**It tries the best source first.** arXiv publishes its own LaTeXML rendering of
most papers, and every formula in it carries the original LaTeX verbatim — no
recognition involved. That is tried before the source tarball, which is tried
before any PDF route.

For a PDF the same principle applies one rung further down. Before spending a
MinerU token or a GPU minute, MAGI asks whether the document needs either: a
born-digital paper with no mathematics can be read straight out of its own text
layer, which is free, fast and faithful. One *with* mathematics cannot — the
characters come out fine and the two-dimensional structure does not — so it goes
to a model regardless. You do not choose between these; the check decides, and
prints what it decided.

**Nothing reaches your project until you say so.** `batch-run` writes into a
staging area and stops. `batch-commit` refuses outright while any item in a batch
is still undecided. Rejecting an item isn't discarding it — it comes back on the
next route down, in the next batch, so "this conversion is bad, try another way"
costs one command.

Your agent can drive all of this for you: the **ingest** skill takes links,
citations, or even a screenshot, works out what each one is, and runs the
commands above.

### Routes, and how to pick one {#ingest-routes}

| Command | Best for | Dependencies | Quality |
|---|---|---|---|
| `magi ingest url` → `batch-run` | Anything you have a link, DOI, or arXiv id for | Pandoc | **Best available** — picks the highest-fidelity route that works |
| `magi ingest arxiv-html` | One arXiv paper, directly | Pandoc | **Best** — the original LaTeX arrives verbatim inside the HTML |
| `magi ingest tex` | arXiv source packages (`.tar.gz`) or `.tex` | Pandoc | **Best** — formulas, citations, and numbering stay natively faithful |
| *(automatic)* text layer | Born-digital PDFs with no mathematics | `magi-research[textlayer]` | Faithful and free — it is the document's own text, not a reading of it |
| `magi ingest mineru` | General PDFs (including scans) | MinerU cloud token | Good, strong layout/formula recognition |
| `magi ingest ocr` | General PDFs, fully offline | Ollama + poppler | Moderate — page-by-page visual transcription; formulas are its strength, and tables survive since pages with one are read in halves |
| `magi ingest add` | Material that's already Markdown/text | None | Just archives it and injects frontmatter |

> [!NOTE]
> **The text-layer route does not export figures by default.** `pymupdf4llm`
> writes every embedded image *object* rather than every figure and inlines each
> one: measured on a 23-page paper carrying 4 figures, 117 files, the smallest a
> 40×24 strip that is really a display equation rendered as a picture. Set
> `ingest.textlayer_images: true` in `config.yaml` if you want them anyway. For
> documents where the figures matter, the OCR route crops them by caption anchor
> and is the better choice.

**Don't want to choose?** `magi ingest auto` picks by what the file *is* — source
bundle → tex; PDF → its own text layer when that is enough, otherwise MinerU with
a token or local OCR without one; text → add — and finalizes for you. It reaches
the same conclusion `batch-run` would, from the same code:

```powershell
magi ingest auto paper.pdf        # one file
magi ingest auto                  # everything in inbox/
magi ingest auto --dry-run        # see the routing first
```

Reach for the specific commands below when you need a page range, want to force a route, or are wrestling with a difficult scan.

**If you can get the arXiv source package, use `tex` first** — it keeps `.bib`/`.bbl` alongside the markdown, and writes the arXiv ID into frontmatter for the radar and `magi bib` to use.

Two more supporting routes: `magi ingest assemble` stitches `page_1.md, page_2.md…` — page-by-page transcriptions the agent produced itself — together into one document in page order; `magi ingest crop` crops a region of a PDF into a PNG so you can eyeball a formula directly.

### What you need to configure {#ingest-config}

Configuration lives in **the `config.yaml` at your project root** (it only falls back to `~/.config/magi/config.yaml` when that's missing; the two are never merged — whichever one is closer completely overrides the global one).

```yaml
ocr:
  mineru_api_token: ""      # ← required for MinerU cloud OCR; get it from https://mineru.net
  dpi: 130                  # local OCR render resolution; below 110 misreads dense subscripts
  timeout: 180              # per-page OCR timeout (seconds)

models:
  ocr: glm-ocr:q8_0               # local OCR model (glm-ocr:q8_0 / qwen3-vl / qwen3-vl:4b ...)
  embedding: qwen3-embedding:0.6b # shared by semantic search and semantic linking

ollama:
  base_url: http://127.0.0.1:11434
  autostart: true                 # start a stopped local Ollama on demand

embedding:                  # only needed if you would rather not run Ollama
  provider: ollama          # ollama | openai  ("openai" = any OpenAI-compatible endpoint)
  base_url: ""              # e.g. https://api.siliconflow.com/v1  — include the /v1
  model: ""                 # e.g. BAAI/bge-m3 ; blank falls back to models.embedding
  api_key: ""               # or set $MAGI_EMBEDDING_API_KEY, which wins over this

tools:                      # only needed if these programs aren't on PATH
  pandoc_path: ""
  pandoc_crossref_path: ""
  pdftoppm_path: ""
```

#### Semantic search without a local Ollama {#embedding-cloud}

Semantic search needs an embedding model. The default is a local Ollama, but
any endpoint speaking OpenAI's `/v1/embeddings` schema works — set
`embedding.provider: openai` and fill in the three fields above, or set them
from the WebUI's Project Config card, where the key field is masked.

Four that were checked against their own live documentation for endpoint shape:

| Service | `base_url` | Model | Notes |
|---|---|---|---|
| SiliconFlow | `https://api.siliconflow.com/v1` | `BAAI/bge-m3`, `Qwen/Qwen3-Embedding-0.6B` | Strong in English and Chinese, several models free; signing up may want a Chinese phone number |
| Jina AI | `https://api.jina.ai/v1` | `jina-embeddings-v3` | Schema modelled on OpenAI's, multilingual, free trial tokens |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-embedding-001` | Ordinary Google account; the free allowance is shown in AI Studio |
| DeepInfra | `https://api.deepinfra.com/v1/openai` | `BAAI/bge-m3` | No free tier, but cents per million tokens |

Treat the specific free allowances as provisional — providers change them
often, and the numbers were not all confirmable from a static page. The
endpoint shapes were.

**Cohere, Voyage AI and Zhipu are not supported.** Their APIs are not
OpenAI-shaped, so each would need a client of its own.

> [!WARN]
> Changing the embedding model changes the vector width, and an existing
> index cannot hold vectors of a different size. Run `magi index --rebuild`
> after switching — it deletes the index and builds it again from `wiki/` and
> `raw/`, which is derived data, so nothing of yours is lost.

> [!EXPECT]
> `magi index` prints the same per-file progress as before, and `magi search`
> reports `semantic search: on`.

> [!FIX]
> - **`no API key is set`**: `embedding.provider` is `openai` but neither
>   `embedding.api_key` nor `$MAGI_EMBEDDING_API_KEY` has one.
> - **`this index holds N-dimension vectors`**: you changed model without
>   rebuilding. `magi index --rebuild`.
> - **401 or 403 from the endpoint**: the key is wrong, or it has no quota
>   left. Every provider above shows remaining quota on its dashboard.

### Running it {#ingest-run}

The easiest approach: drop the PDF into `inbox/` and tell the agent "ingest the papers in inbox" (or run `/magi:ingest`). It picks the route, converts the format, and wraps up. To run it by hand:

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
magi ingest finalize inbox/paper.pdf --project-dir . --md-file raw/papers/2026-08-20-paper.md
```

`finalize` is the step that actually wires the file into the project: it archives the original to `inbox/.processed/`, cleans up frontmatter, converts image links to Obsidian wikilinks, runs formula formatting and validation, and finishes with `magi lint --fix` + `magi graph build` + `magi wiki reindex`.

> [!WARN]
> Those last three run against **the entire project**, not just this one document — and **if any of them fails, it just prints one warning line; nothing stops, and the exit code doesn't change**. On your first ingestion, watch the terminal for a line like `Warning: 'magi lint' failed` — it will keep silently repeating on every ingestion after that until you deal with it. If you see one, run that command on its own to see the real error.

> [!TIP]
> When ingesting in bulk, don't rebuild the graph after every single paper: add `--skip-lint` to each one, then run `magi ingest finalize none --project-dir . --lint-only` once at the end.

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
| `OCR 模型 X 不可用` | The model hasn't been pulled | `ollama pull glm-ocr:q8_0` |
| `pdftoppm 未找到` | poppler is missing | Install poppler, or set `tools.pdftoppm_path` |
| `第 N 页 OCR 失败` | That single page failed both retries | **Just rerun the exact same command** — successful pages are cached in `.temp/`, so only the failed page gets redone |
| Garbled formulas, subscripts running together | Render resolution is too low | Bump `ocr.dpi` to 150 and rerun |
| `Warning: 'magi math check' failed` after ingestion | Formula validation found an issue | `finalize` doesn't stop for this; run `magi math check <file>` on its own for details — see Chapter 6 |

> [!NOTE]
> **Pages that contain a table are read in two halves.** Sent a whole page, the
> model transcribes about half a long table and then stops — measured, 24 of 49
> rows, and raising the context window fourfold changes nothing byte for byte.
> Given the left and right halves separately, at the same resolution, it
> returns all 49. Only pages where PyMuPDF finds a table are split, so the cost
> (roughly twice the time for that page) falls only where it buys something.
> A scanned page has no text layer to find a table in and is read whole, as
> before.
>
> A cache in `.temp/` written by an older version records the prompt and split
> it was produced with, and is re-read only if both still match — otherwise the
> page is transcribed again rather than replaying an answer from a recipe that
> has since changed.

> [!NOTE]
> `magi ingest ocr` has **no** `--resume` flag — resuming is automatic. As long as the output directory still exists, rerunning the same command reuses whatever pages are already done in `.temp/page_N.json`. `.temp/` is deliberately kept around whenever there are failed pages; once you've confirmed everything's finished, you can delete it by hand.

---

## Compiling into the project {#compile}

Compiling is the one step with no command — you ask your agent:

> "compile the backlog"

It runs the `compile` skill: reads each ingested paper, extracts its concepts, decides what belongs in your wiki, and writes structured, interlinked cards. `magi compile` does not exist and will not; this is understanding work, and the CLI's job at this layer is only to check and repair what the agent produced.

Afterwards, three commands tidy up:

```powershell
magi lint --fix         # structural problems, self-healing where it can
magi link               # find concepts that should be linked or merged
magi graph build        # refresh the graph with the new cards
```

> [!WARN]
> `magi graph build` **still returns success** even when `wiki/` is empty — it just builds an empty graph. So "the graph is empty" usually doesn't mean the graph is broken; it means you haven't compiled yet. Confirm with:
> ```powershell
> magi graph query "SELECT COUNT(*) FROM nodes"
> ```

### The main flow {#compile-main}

Tell your agent these, in order (or use the slash commands):

| What to say | Skill | What it does |
|---|---|---|
| "Compile the new papers in raw" | `compile` | Turns each raw source into a `wiki/references/` reference card, and extracts concept cards along the way |
| "Dig deeper into this paper's concepts" | `compile` | Re-scans already-compiled cards to catch theorems/lemmas the first pass missed |
| "Merge duplicate concepts" | `tidy` | Physically merges synonymous concepts, splits overly broad ones, and rewrites multi-source definitions |
| "Clean up tags" | `tidy` | Normalizes the tag/alias ontology (see Chapter 7) |
| "Run a checkup and fix" | `magi lint --fix` | Auto-repairs broken links, frontmatter and formulas — a deterministic command, no skill needed |
| "Ingestion mangled the formulas" | `tidy` | Harvests every broken formula in the project, then reads and repairs them one at a time |

The corresponding deterministic commands:

```powershell
magi wiki uncompiled                      # Which raw sources are still uncompiled (this is how you track compile progress)
magi lint --fix                           # Self-heal structure: fill in frontmatter, relocate files, rebuild directory indexes
magi wiki reindex .                       # Rebuild the _index.md tables under concepts/, references/, topics/ and theses/
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
> - **Running lint outside a project checks almost nothing**: it does the outermost structural check and stops. The real quality gate runs inside a project directory.

> [!WARN]
> The `status` field in `magi lint --json` and the exit code **use different criteria**: the JSON status is `fail` as soon as there's any warning or suggestion, while the exit code and the text-mode `Result:` line only look at criticals. In CI, go by the exit code.

### Formulas {#compile-math}

```powershell
magi math format                    # Mechanical fixes: pairing $$, \tag placement, eqnarray→align, OCR run-ons
magi math check                     # Reports only, doesn't fix: sweeps the project, grouped by file
magi math check --json              # The same, as a worklist you can go through one entry at a time
```

**Both default to the whole project**, the way `magi lint` does — or name a file
or directory (`magi math check raw/papers/x.md`) to narrow it. Scoped to
`wiki/ raw/ drafts/`: `format` edits in place with no dry-run, and `scratch/` is
where the concept backups live.

The order is always **format first, then check** — clear the mechanical damage,
and what remains is worth a human reading.

`--fast` skips the per-file pdflatex pass (minutes, on a large project);
`--wiki-only` narrows to compiled cards.

`--json` gives one entry per formula, with an `id` (`path:line`, so you can tick
them off), the line range, the offending TeX verbatim, and a `confidence`:

| `confidence` | What it means |
|---|---|
| `certain` | Genuinely broken structure: unbalanced braces, mismatched environment, an unclosed `$$` |
| `likely-macro` | pdflatex doesn't recognize the macro — **nine times in ten a package it doesn't load, not a typo** |

> [!TIP]
> **Several consecutive entries in one file are usually one defect.** `$$` pairs
> up in order, so a single missing closer shifts every pair after it and each
> shifted pair gets reported. Fix the *first* one, re-check that file, and a
> hundred entries often collapse to a dozen real edits. Never work such a file
> bottom-up.

**You don't have to work the list by hand**: the `tidy` skill exists for
exactly this — deterministic pass first, then `wiki/` before `raw/`, reading the
source and cropping the PDF when the intent is unclear. Just ask your agent to
fix the formulas.

> [!NOTE]
> `Undefined control sequence` is usually a **false positive** — the checker just doesn't recognize a macro from some package. Spot-check one against the original PDF, and you can ignore the rest of that kind. What you actually need to fix are structural errors like `Double subscript`, `Missing }`, and `Unexpected end of stream`: crop the original text out with `magi ingest crop <pdf> --text "<nearby text>" --out scratch/crop.png` and edit against it.
> `[WARNING] Orphaned $$ remains on line L` is a boundary case format can't resolve on its own — you have to pair it up by hand.

---

## Knowledge graph {#graph}

The graph is one command to build and one to look at:

```powershell
magi graph build              # after compiling new cards
magi graph browse overview    # counts, tags, claims, broken links
```

The dashboard's graph view shows the same data if you would rather click than type. Below: every browse view, what to do when the graph looks wrong, and reading it in Obsidian.

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
| **Too few nodes** | Papers haven't been compiled into cards yet; or the graph is stale | Check the backlog with `magi wiki uncompiled` → compile with `compile` → `magi graph build` |
| **A bunch of isolated points** | Cards' bodies have no wikilinks, and semantic linking hasn't run | `magi link .` (below); for systematic linking use `compile` |
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

Search is two commands:

```powershell
magi index                       # after you add or change cards
magi search "kramers-wannier"    # find things
```

`index` is incremental and cheap to rerun; `search` blends keyword and meaning matching, and **its default scope is the project you are standing in** — `--scope all` reaches the others. Below: the modes, the scopes, and what the score badges mean.

### Building the index {#search-index}

```powershell
magi index                # Build/refresh output/index.db
magi index --no-vectors   # Build a keyword-only index (when Ollama isn't available)
magi index --quiet        # Suppress the progress lines (the summary still prints)
```

The index covers every `.md` file under `wiki/`, `raw/`, and `drafts/`, chunked by level-1 through level-3 headings, with a 250-line cap per chunk. **It updates incrementally**: files whose content hash hasn't changed are skipped, and deleted files are cleaned up automatically.

Embedding is the slow half, and on a project first indexed without Ollama it has the whole corpus to catch up on. It reports as it goes and commits each batch, so a run you interrupt keeps everything it had already embedded and the next run picks up from there.

> [!EXPECT]
> ```
> index: backfilling vectors for 1371 chunks
> index: backfill: 320/1371 chunks
> index: 1371 chunks (0 files updated, 141 unchanged, 0 pruned) · vectors 1371/1371
> ```
> If it ends with `· BM25-only (Ollama unavailable)`, the vector half didn't get built.

Chunks go to Ollama 16 at a time. Set `ollama.embed_batch` in `config.yaml` to change that — higher is faster but uses more memory on the Ollama side, and an embedding server that gets killed halfway through costs more than the throughput is worth.

`magi index` also **automatically registers** the current project in the global project table (`~/.config/magi/registry.json`), so other projects can search it too.

### Searching {#search-query}

```powershell
magi search "anyon statistics"                # Default: this project only
magi search "anyon" -k 20 --mode vector      # Semantic search only
magi search "exact phrase" --mode bm25        # Keyword search only
magi search "..." --collection concepts      # Search only concept cards
magi search "..." --path 'raw/papers/2026-*fracton*'   # Restrict the search to one paper
magi search "..." --scope all                # Plus the projects research.search_projects names
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
> - `no project here and no searchable registered projects` → You're not inside a project, and there's no searchable registered project. `cd` into one, or `magi kb register` + `enable`.
> - **Can't find something you just wrote** → The index updates incrementally by hash, but it **doesn't trigger automatically**. Rerun `magi index` after editing.
> - **Results are all keyword hits, no semantic ones** → It ends with a `BM25-only` notice. MAGI already tried to wake a local Ollama; if it's still BM25-only, Ollama isn't installed or the embedding model isn't pulled. Check with `magi setup --check`, then rerun `magi index` to fill in the vectors.
> - **Search says it fell back to keywords while an index job runs** → Ollama answers one request at a time, so an indexing run holds it. The search gives up on vectors after 8 seconds and returns its keyword half rather than hanging; search again once the job finishes.
> - **`magi index` stopped early with `Ollama stopped responding mid-run`** → The embedding server died (most often out of memory). Everything embedded before that point is committed; rerun `magi index` to backfill the rest. If it keeps happening, lower `ollama.embed_batch`.
> - **Chinese search turns up nothing** → When you see `this index predates CJK-aware tokenization`, just rerun `magi index` (it rebuilds the tokenization layer automatically).
> - `index dims mismatch current embedding model` → You switched embedding models. Switch back, or rerun `magi index` for a full re-embed.
> - `sqlite-vec unavailable` → The vector extension failed to load (common on macOS when the system Python doesn't support loading extensions). Use uv/Homebrew Python, or fall back to keyword search.

> [!NOTE]
> `magi index --rebuild` deletes the index and builds it again — the clean slate. You need it after changing the embedding model, because the vector table is created at a fixed width and cannot hold vectors of a different size. Deleting `output/index.db` by hand does the same thing; the index is derived from `wiki/` and `raw/`, so nothing of yours is lost either way.
> `magi grep "<regex>" <files...> [-i]` is a different thing entirely — it doesn't read the index, it just does regex line-matching against the files you name (Python regex syntax, JSON output, capped at 200 matches, with a 5-second hang guard). Use it when there are only a few files and you need an exact literal match; use `magi search` when you want to "find related content."

---

## Research state {#threads}

A project's state lives in files, not in a task tracker. Every note under
`threads/` is a **proposition** (it has a truth value; this is the unit research
is made of), a **question** (open-ended — its answers are propositions), or a
**line** (a research direction, whose body *is* its status: where it got to,
what is stuck, what is next). The filename is its id and never changes.

```bash
magi thread new p-gap --kind proposition --title "The gap survives weak disorder" \
  --purpose "Decide before committing a month of numerics" --line qec --bet supported
magi thread status p-gap testing --text "Started at L=64"   # move it, and say why
magi thread post p-gap --text "L=64 converged; trying L=128"  # just a remark
magi thread bet p-gap refuted --text "the L=128 drift looks real"   # the person's prediction, signed human
magi thread new p-dual --kind proposition --title "The dual is a Z2 gauge theory" \
  --purpose "Came out of the L=128 run" --found 2026-09-01   # a finding: no bet is asked for
magi thread new p-idx --kind proposition --title "Twisted index" --purpose "From the L=128 run" \
  --claim "For h = 1, the twisted index equals 3." --derivation drafts/index.md --evidence tools/index.m2
magi thread post p-idx --evidence tools/index_check.py --text "second, independent count"
magi thread claim p-idx --text "For h = 1 and 2, the twisted index equals 3."   # restate, as a recorded change
```

**Title, claim, evidence.** The title is a name; `--claim` is the statement a
reviewer judges, quantifiers included, and `magi thread claim` restates it as a
recorded change when a reviewer says the words are too wide. `--derivation`
points at the argument, `--evidence` at the files a reviewer must read or run
(scripts, data, notebooks), and both are checked at the keystroke: the path has
to be inside the project and has to exist. Scripts live in `tools/`. A CLI's
scratch directory is outside the project, and evidence left there is evidence
no reviewer can open: `sync --close` and `magi next` list any post that cites a
path outside the project, and `magi review` warns before it spends.

**Who typed it.** A post signed `human` is the person's decision, usually
transcribed by an agent. The signature says so: `human/qec · via claude`. It is
still the person's post to every gate; `via` is provenance, so a reader can
tell a transcription from their own keystrokes.

**Where the log goes.** There is no journal file. A remark about a line goes
on the line's note (`magi thread post <line> --text …`), a remark about a claim
on the claim's, a person's decision through `magi decide`; `magi feed` reads
them all back in time order. `log.md` is a v1 file that nothing writes.

A proposition runs `open → conjectured → testing → supported | refuted →
superseded`; a review rejection or a clash of evidence puts it in `disputed`,
which is a person's call. **A status change carries a post** — which is why
`magi thread status` does both, so you cannot do half of it.

**Conjecture or finding.** A prediction is only worth anything before the
answer, and most propositions in real work are opened *after* the number came
out. So a proposition opened with `--found [DATE]` is a **finding**: it records
when the result was found and nobody is asked to bet on it — a bet placed after
the answer is not a prediction. One opened without it is a **conjecture**, and
`magi next` asks for the bet once, at `conjectured` or `testing`, before the
work. `magi thread bet` records it whenever it arrives, signed `human` unless
you say otherwise; hand-editing `bet:` in the frontmatter is what it replaces.

A note already open becomes a finding with `magi thread found <slug> [DATE]` —
the case that matters most, because a proposition being asked for a prediction
it can no longer honestly give is one somebody opened yesterday. Any prediction
already recorded stays: a bet on record is on record, and the scoreboard reads
it the same way.

**Asking somebody to predict means showing them the claim.** `magi next` prints
one card per waiting proposition — the claim, whether a `derivation:` and
`evidence:` exist and are readable, whether anybody has reviewed it, and how
long it has been open — and `magi next --json` carries all of them under
`bets_waiting`. A list of slugs is not a question anybody can answer, which is
how this was found: somebody was asked to bet on ten of them and could not.
Where a card shows the working-out already exists, it offers `magi thread
found` alongside the bet, because there the honest answer is usually that it
was never a prediction.

Each note has two halves: the body belongs to whoever opened it, and
`## Discussion` is append-only — nobody edits anybody's post. **Use the command
rather than an editor**: appending takes a lock and writing the whole file in an
editor does not, so two agents at once lose posts (especially on Windows, where
appending is not atomic).

`magi lint` checks all of this in passing: whether the status word belongs to
the kind, whether the posted chain of transitions is legal, and whether a status
was changed without anybody saying why.

### What to do next

```bash
magi next             # what to do, derived from the notes — proposes, never acts
magi next --line qec  # one research line only
magi feed -n 20       # every post, newest first — the record in time order
magi sync --close     # the end-of-session gate: refuses while work is unrecorded
```

Running the CLI with no arguments inside a project does the same thing — one entry, and the router decides.

The order `magi next` uses is the point of it. **Bookkeeping debt first**, because
every line below it is computed from notes that are currently wrong. Then the things
**only a person can decide** — a review rejected, two writers collided, a line that may
have turned — which must not queue behind machine work. Then the work itself, at most
one proposition per line: listing every open proposition is listing the whole project,
and then the ranking it was for stops meaning anything. With nothing owed, nothing
waiting and nothing in flight, it prints the open questions and stops.

### Review and the call

```bash
magi review               # have another vendor's CLI check every claim that says it is solved
magi review p-gap --dry-run   # see who would be asked, about what
magi decide --about p-gap --bet supported --text "I expect it holds in the bulk"
```

**Judgement comes from far away.** An agent grading its own work is not a
review: it was convinced once already, by the same reasoning, and the second
pass agrees for the same reasons. So the reviewer runs headless in **another
vendor's CLI**, picked by probing PATH for one that is not the author — another
model, another system prompt, none of the conversation. With only one CLI
installed it still runs (a fresh session with no context is not nothing) and
the verdict says which kind it was. With none installed **nothing passes**:
better an unreviewed claim than "no reviewer available" quietly meaning
"approved".

The reviewer sees the proposition, its `derivation:`, the `raw/` it cites, and
the drafts and cards the argument leans on — not the chat, not the line's own
account of how it is going, not the other notes in `threads/`. "Far" means not
sharing context, not being denied evidence. The note's own `## Discussion` is
commentary: it may read it for context, but a slip in a post is not a flaw in
the claim, and a refutation has to rest on `drafts/` or `raw/`.

**What it checks, in order** — the places claims of this kind actually fail:
the title's quantifiers against what the derivation covers; whether each object
is what it is called; counts and indices; whether the proof covers the whole
claimed domain or a slice of representatives; whether the numerics survive a
broken step; and the **load-bearing assumption** — the one definition the claim
leans on most, and whether the conclusion survives a reasonable alternative.
It must also **verify one thing itself** — recompute a formula, re-derive a
step, or rerun a script the derivation names — and the post records what it
checked. "The proof is on line 40" is not a review. `magi review --allow-run`
adds the flag that lets a host execute scripts, where MAGI knows one — Claude
Code and Codex have one, agy has none and the command says so.

> **A host without that flag is not a host that only reads.** `agy -p` has been
> observed running the scripts a note's `evidence:` named and reporting their
> output, on calls that passed nothing of the sort — twice, on two different
> machines. MAGI can tell you what it passes; what a vendor's CLI does by
> default is the vendor's choice. Treat anything under `evidence:` as something
> a reviewer may execute, whatever flags you used.

**Four verdicts.** `stands`. `restate`: the conclusion holds and the words do
not — a quantifier written too wide, a wrong index, a mislabelled object; the
claim goes back to `testing`, its author fixes the statement or the derivation
as the post says, and marks it `supported` again. That puts it back on the
review queue — `magi next` and `sync --close` list it, and `magi review <slug>`
asks again. **Nothing re-runs a review on its own**: a model call is minutes and
money, so MAGI lists and never spends unasked (design-v2 §11). Nobody is asked
either, which is the point — a restate is the author's to fix, not a person's
to rule on. `refuted`: a counterexample or a specific step that does not hold;
the claim moves to `disputed`, which is a question for a person — not
`refuted`, which would be a finding, and never back to `supported` on the next
run. `unclear`: not an answer; the claim comes back.

**It runs on the strong tier unless you say otherwise.** It ran on the cheap
tier until 2026-09-03, on the theory that reading one claim does not need much
model. One measured day said otherwise: on the same propositions the cheap
reader gave twelve verdicts, one useful remark, and waved through all four
substantive errors while reporting line numbers it had not read; the strong
reader found the one real proof gap. A review that manufactures confidence is
worse than none. So each host record names a strong model — `opus` at `high`
for Claude Code, `gemini-3.8-flash-high` for agy; Codex runs its own default
at `high`, because it will not list its models and a dated id written into
MAGI becomes an "unknown model" error on some future release. The cheap tier
is still there by name (`--model haiku`), and every verdict's post says which
tier answered, so `sync --close` and `magi next` can list the claims only a
cheap reader has seen.

Four things decide the model, most specific first:

```bash
magi review --model sonnet --effort high     # 1. this call
# 2. `model:` on that host's record in research.hosts
# 3. research.review_model in config.yaml
# 4. the host record's strong tier
```

`research.review_model` is one string and the reviewer host is picked automatically,
so a name that is right for one vendor is an "unknown model" error on the next: pin
`research.review_host` alongside it, or put `model:` on the record instead. The WebUI
config panel does this for you — pin a host and the model field becomes a list of
what that host actually offers (`agy models`, cached for a day; Claude Code's three
aliases; a text box for Codex, which cannot be asked).

`--effort low|medium|high` is the same chain, ending in the strong tier's own level
only when the model *is* the strong tier — and dropped when the model id already
carries the level: `gemini-3.8-flash-high` **is** the high one, so agy is not sent
`--effort` on top of it.

`magi review --dry-run` prints the host, the model, the effort and the tier it would
use, per claim, which is the cheap way to check a four-link chain before spending a
call.

**Who is asked.** The CLI that wrote the claim is read off the post that moved
it to `supported`, and the reviewer avoids it; `--author` overrides. When the
host picked fails to answer — its vendor's quota, a timeout, a crash — the next
installed CLI is asked, cross-vendor first and the author's own last, and the
verdict's signature says who failed first and why. A host that failed once in a
batch is not asked about the next claim.

**How long it waits.** Ten minutes by default, longer when the derivation and
evidence run long (`--timeout` sets it exactly). It was five, and a strong
reader at high effort on a four-hundred-line derivation ran past it.

A CLI that keeps *its own* ceiling is told the same number: `agy` defaults to
five minutes, and until MAGI passed `--print-timeout` its default quietly won —
two real reviews died at about 310 seconds while MAGI sat waiting ten minutes,
and the fallback then asked another vendor, so it read as "agy is slow" rather
than "nobody told agy to wait". With the flag the same two finished in 214 and
373 seconds. MAGI then waits half a minute longer than the number it handed
over, so the host's own timeout fires first and says so in its own words. A
host you declare yourself takes `timeout_argv` in its `research.hosts` record.

**`--no-fallback`** asks only the host you named. The fallback chain is right
for getting a claim read; it is wrong when you are comparing two reviewers,
because `--host antigravity` failing and quietly landing on Claude gives you a
verdict filed under the wrong name.

**A review that could not run writes nothing.** A claim stops being offered for
review the moment a reviewer posts on it, so a missing CLI, a timeout or a
crashed process leaves the note untouched and the claim on the list. A reply
nobody can parse is posted — with the reply quoted, since that is the only way
to tell a broken adapter from a claim that genuinely cannot be judged — but
`unclear` is not an answer either, and the claim comes back.

**There is no weekly budget.** There was one, and the person using it cancelled
it: token plans make a per-call cap pointless, review turned out to be worth far
more than forty calls a week, and on the day it went the cap was counting four
calls that had failed on a vendor's own quota. Calls are still written to
`output/llm-ledger.jsonl` with host, model, effort, tier, duration and outcome;
`MAP.md` and the dashboard show the week's count. The one refusal left is
`research.llm_calls: false`.

### Ending a line

```bash
magi close l-sweeps --dry-run              # what is still open on it
magi close l-sweeps --text 'the question moved on'
magi publish paper.md --line l-sweeps --text 'this is what it reports'
```

A line is a *view*, not a folder, so closing one moves no files. What it
changes is attention: `magi next` skips a closed line entirely. That is the
point of closing it and also the whole danger — every proposition still open
on that line stops being offered, and nothing raises its hand later.

So `magi close` surveys before it writes, and **refuses** while anything is
open, listing each one with the command that would settle it. `--anyway`
closes regardless and the closing post names every slug that was left, because
after that the router never will.

`magi publish` is the same line ending the other way: the work got written up.
The paper goes into `raw/` as cold layer like any other source, every
proposition the line was about gets `superseded_by: [[raw/papers/…]]`, and the
line closes. It refuses over two things — a `disputed` proposition, where a
reviewer objected and nobody ruled, and work still open — and `--anyway`
records which ones were buried. `superseded` is terminal: `vocab` gives it no
way out, which is why there is a survey in front of it.

> [!NOTE]
> **Two commands share the word "close".** `magi sync --close` ends a *session*
> — the bookkeeping gate every session runs. `magi close <line>` ends a
> *research line*. They sit next to each other in `magi --help` so you meet
> both descriptions at once rather than finding out from the wrong one.

**`skeleton: true`** in a note's frontmatter pins it into the graph's skeleton
view, which otherwise keeps the sixty best-connected nodes. Degree is a good
proxy for importance and a systematically wrong one about the newest note —
which is usually what you are working on. A pin takes a slot rather than
widening the map, and `MAP.md` lists what is pinned, so the two renderings of
`threads/` agree.

`magi decide` is the agent transcribing, **verbatim**, what a person said. They
speak in the conversation and never open a file — a system that needs them to
has an empty record by the second week. One command writes the entry into
`decisions.md`, sets the proposition's `bet:`, and leaves a post signed `human`
in the discussion; that signature is exactly what `sync --close` looks for when
a claim leaves `disputed`.

Verbatim survives words that look like structure. Somebody saying "my worry is
exactly this: `status: testing -> refuted`" gets that line quoted in a fence
rather than parsed — otherwise it would come back as a transition **signed with
their name**, and inventing a person's signature is worse than losing a line.

### The slow loop {#reflect}

```bash
magi reflect --dry-run    # which sessions would be read, and by whom
magi reflect              # read them, and write down what keeps happening
```

Everything above happens inside one session. `magi reflect` is the loop that
runs *across* them: it reads the transcripts your agent CLIs already keep, and
writes down patterns — things that recur, with the words that showed them.

It does not read every session. MAGI already knows *that* certain things
happened — a claim that was solved and then refuted, bookkeeping nobody
recorded, a review that rejected something, a claim that went out and stood
first time — and each of those happened at a knowable moment. The sessions that
were running at those moments are the ones worth paying to read: at most eight
of them, and **at least a few where the work went well**. A loop fed only
failures grows only prohibitions; improvements to method can only come from
sessions where the method worked.

What comes back lands in `output/reflect/patterns/`, one page per pattern,
recording which sessions and which hosts showed it. That directory exists so
two rules can be checked rather than hoped for: *the same thing in at least two
independent sessions* before anything is proposed, and *ninety days without
recurring* before what it produced is questioned.

> [!NOTE]
> **Nothing your working agent reads mentions that directory** — not the
> `AGENTS.md` block, not a skill, not a suggestion from `magi next`. An agent
> that can read the pattern library starts defending against the patterns
> instead of following the rules, and then the loop can no longer tell whether
> the rules it hardened are doing anything. That is measured, not assumed.

Reading costs one model call per pass, written to the same ledger as the
reviewer's calls, and refused the same way — by `research.llm_calls: false`.

```bash
magi reflect propose      # turn what recurred into at most five proposals
magi reflect list         # what is waiting on you
magi reflect accept  <id> # put it in the protocol every session reads
magi reflect reject  <id> # no — and say why, in your words
magi reflect promote <id> # make it a rule the gates actually check
magi reflect retire  <id> # its reason has gone; take it back out
```

Nothing is proposed until an observation has been seen in **two independent
sessions**. That gate is a query against the pattern files, not a wish in a
prompt, and it usually takes two runs a week apart to pass — which is the
point: one bad afternoon is not evidence.

What you turn down is kept in full and handed back to the next pass, so the
loop stops suggesting it and has to say what makes the next idea different.
Being told no is the one place you said what you actually wanted.

**The four verbs are the only way a verdict is ever written.** The loop
proposes; you decide; the CLI writes. Accepting a rule puts one line into the
`AGENTS.md` block — the most expensive place in the system, since every session
on every host reads it, which is why that section has its own small budget
(`research.rule_budget`, seven lines). When it is full, accepting says which
rule to retire first rather than quietly dropping the eighth.

**Promoting is the way out of prose.** A rule in the block is read by every
session and reliably followed by none; a check runs. `magi reflect promote`
turns a proposal into an instance of one of five predicates — `require_field`,
`field_points_into`, `forbid_transition`, `max_open_per_line`,
`leaving_status_requires_post_by` — which lands in `research.rules` and is
enforced from then on by `magi lint` and `magi sync --close`. The prose comes
out of the block, because the check has replaced it.

A proposal that fits none of the five cannot be promoted, and that is not a
failure: most good advice is prose. Keep it as a rule, or propose adding a
predicate.

`magi sync --close` is the gate between a session and its end. It refuses while
something has happened that nobody wrote down, and says which notes. It also settles
**a status two different writers set within five minutes** as `conflict` — that is not a
status, it is a disagreement, and only a person can say which reading was right — and
rewrites `output/MAP.md`. **MAP.md is a rendering**: editing it changes nothing, because
the status lives in the note.


## Writing your paper {#writing}

Day to day this is three commands, in this order:

```powershell
bd ready                # what is worth working on right now
magi verify             # check every CLAIM has evidence behind it
magi bib --fetch        # BibTeX for what you cited
```

The writing itself happens in `drafts/` with your agent, against the cards you compiled. Below: setting up task tracking, the drafting flow, and how claims get verified.

### Using tasks and to-dos {#writing-tasks}

MAGI doesn't implement its own task system — it connects to [Beads](https://github.com/gastownhall/beads) (`bd`). **One store per project**, with issues distinguished by a `line:<name>` label.

```powershell
magi pm init          # run once in the project: creates the DB + registers the six research issue types
magi sync              # ready / in progress / blocked counts, with the rest of the state
magi pm backlog-sync   # turn "uncompiled raw sources" into to-dos
```

> [!NOTE]
> `magi pm init` creates the store in the project you are standing in — since v2 it no longer walks up looking for a hub, so it is one store per project. The store holds mechanical work only: a compile backlog, a reading queue, a review to run. A project's *state* lives in `threads/`, which can carry a status and an argument. Tasks opened for a research line carry a `line:<name>` label.

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

Drafts live in `drafts/<slug>.md`, a directory `magi init` creates. It **is searchable** (in a collection called `drafts`), **doesn't enter the knowledge graph**, and **doesn't count toward the sync ratio** — it's something you're still writing, not established knowledge.

The drafting loop (the `draft` skill walks you through this, but it's the same by hand):

```powershell
magi search "what this paragraph argues" -k 5   # 1. gather your evidence first
magi wiki context --name "some concept"         #   pull every paragraph that mentions the concept into scratch/
#                                             # 2. write drafts/paper.md, citing with [[reference card]] links
magi bib --all -o drafts/refs.bib             # 3. export the bibliography
magi bib pretko-2020 --fetch                  # 　 pull the official arXiv entry when an arxiv_id is present
magi stats . verify-refs drafts/paper.md      # 4. check that every wikilink points to a real file
magi verify drafts/paper.md --project-dir .     # 　 check that claims' evidence quotes really exist
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
SOURCE: raw/papers/laughlin-1983.md
```

`SOURCE:` points into `raw/`, never at a card under `wiki/references/`. A reference card is a view compiled out of `raw/`, and it can be wrong in exactly the way the claim is trying to rule out — citing the card launders a compilation mistake into a fact. `magi lint` flags evidence that points at one.

`FINDING:` is a synonym for `CLAIM:`. All four fields are required. Then:

```powershell
magi verify drafts/paper.md --project-dir .              # exit code 0 = everything passed, 1 = something unverified
magi verify drafts/paper.md --project-dir . --fetch-web  # also actually fetches and checks web sources
magi validate wiki/topics/x.md                        # structural check of one synthesis
```

> [!NOTE]
> `verified` means **the evidence quote exists** — that exact sentence really appears in the source file, verbatim (differences in whitespace, full-width punctuation, and hyphenation are tolerated). It does **not** judge whether your claim actually follows from that quote semantically — that layer is for humans and LLM review (the `research` skill). `magi claims verify` is an alias for the same command.
> The evidence quote must be single-line quoted content; multi-line quotes aren't supported.

> [!WARN]
> The "N paragraphs have no citation" message from `magi validate` sounds mild, but it **does set the exit code to 1**. Keep that in mind if you're writing CI.

---

## Literature radar {#radar}

Set it going once, then triage weekly:

```powershell
magi radar install-schedule     # once — harvests every night at 03:00
magi radar harvest              # or run it by hand any time
```

New candidates land in `inbox/radar/<date>-digest.md`. Triage them in the dashboard's **Literature Radar** tab — skip / accept / make a reading task, one row per paper — or tell your agent "review the radar digest" and let the `radar_review` skill do the scoring.

The harvest itself is deterministic: it never judges, it only collects. Everything below is configuration and tuning.

### Configuration {#radar-config}

Configured in the project's `config.yaml`:

```yaml
radar:
  arxiv_categories: [cond-mat.str-el, hep-th]   # which arXiv categories to scan each day
  seed_arxiv_ids: ["2301.01234"]                # seed papers (positive examples for the recommender)
  days: 7                    # arXiv lookback window
  max_candidates: 40         # max candidates to keep per run
  min_relevance: 0.50        # relevance floor (optional; omit = no filtering — see below)
  own_arxiv_ids: ["2402.05678"]     # "our papers", used by citation-gap
  citation_gap:
    min_shared_refs: 2       # co-citation threshold
    years: 2                 # only look at recent years
```

`min_relevance`, `own_arxiv_ids`, and `citation_gap.*` are **not in the template `magi init` generates** — add them yourself when you need them.

Relevance is "the cosine similarity between a candidate's abstract and your project's embedding centroid," so it depends on the vector index `magi index` builds plus a working Ollama; without those, candidates are just listed in source order, unscored.

> [!NOTE]
> **Read the score as a rank, not as a probability.** Everything that reaches a digest already came from your arXiv categories or from recommendations seeded on your own papers, so the candidates are all plausible before they are scored and the numbers bunch near the top of the scale. Measured on a real 67-paper project: all forty candidates landed between **0.55 and 0.70**, while genuinely unrelated text scores far lower — a generic condensed-matter paper 0.45, a machine-learning paper 0.37, random characters 0.31.
>
> That means `min_relevance` is a floor against *category-level* mistakes (a mis-typed arXiv category pulling in another field), not a precision dial. Around 0.50 it will catch that and nothing else; pushed up to 0.60+ it starts cutting real hits. The ordering is informative at the top of the list and close to noise around the median — the UI shows it as **strong / related / weak** within each harvest for exactly that reason, with the raw cosine on hover.

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
- **Linux**: **installs nothing at all** — it prints one suggested crontab line (honouring `--time`) for you to add with `crontab -e`.

> [!WARN]
> The task name includes a hash of the project path. **After you move or rename the project, `--uninstall` can no longer find the old task** — you have to delete it by hand (`schtasks /Delete /TN <name> /F`, or delete the plist).

### Tuning the noise {#radar-tuning}

| Symptom | Fix |
|---|---|
| `harvest: no new candidates` | Are your seeds and categories empty? Is the window too narrow? Try `--days 30`. It's also possible you really have harvested everything already — the ledger is `output/radar/seen.jsonl`, and **no command resets it**; to re-harvest, delete lines from it by hand |
| Too many, too noisy candidates | Trim `arxiv_categories` first — that is where noise enters. Then lower `max_candidates`. `min_relevance` is a blunt instrument here (see the note above) |
| Pause the radar without uninstalling the schedule | Set `max_candidates: 0`; the harvest exits immediately without calling arXiv or S2 |
| Relevance scores are all blank | You'll see `relevance scoring unavailable` — run `magi index` to build the vector index first. A stopped Ollama starts itself; if the scores stay blank, it isn't installed or the model isn't pulled |
| `warning: S2 recommendations failed` | Semantic Scholar is rate-limiting you or there's a network issue; the calls are anonymous, there's no API key to configure — just retry later |
| `arXiv query failed for <category>` | The digest's frontmatter records `sources_failed`, and `magi radar status` flags it too; rerun to fill in the gap |
| `citation-gap: no candidates survived` | The funnel is too strict: lower `min_shared_refs`, raise `years` |
| `has no reference data on S2 yet` | The paper is too new — S2 hasn't indexed its references yet. Wait a few days |
| `Semantic Scholar did not answer (rate limit or outage)` | Different thing: S2 refused the request, so whether the paper has references is simply unknown. Retry later |
| Digests keep piling up | Only a review action flips `status: pending-review` to `reviewed`; re-harvesting on the same day generates `-2`, `-3` copies, and it piles up fast. Review regularly |

---

## Local dashboard {#webui}

The dashboard is one command:

```powershell
magi ui                 # opens http://127.0.0.1:8737
```

Run it from inside a project. Every registered project is in the picker at the top, so one server covers all of them. It is a view over the same files the CLI uses — nothing lives only in the browser, and the dashboard is derived from `threads/` on every load exactly as `magi next` is.

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
| **Dashboard** | The two things you are supposed to look at, and one box to be untidy in: **say it here** (types straight into `inbox/notes.md`; filing is the agent's job), **decisions waiting on you**, **research lines** with phase and what is open, and **looking back** — your prediction record and the last few decisions. Below them: sync ratio, one-click fix suggestions, registered-project management, and key `config.yaml` fields |
| **MELCHIOR (knowledge)** | **Threads** (every proposition, question and line, with kind, status, temperature and the bet on record) and the **thread view**: the note's prose, its whole discussion, a box to say something, and one button per status it may legally become — starred when only a person may make that move. Then the **feed** (every post, newest first), claims and evidence, compile backlog, seven graph views + a read-only SQL console, BibTeX copy, draft list. The graph draws `threads/` alongside the project, coloured by kind, and filters to either side of it or down to the skeleton |
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
> and preview follows a hit into whichever registered project it actually lives in.

**The whole daily loop runs in the browser.** Open a claim, argue it, move its
status, record a decision, have it reviewed, take in what is sitting in
`inbox/`, search, end a research line, publish, close the session — every step
has a control. The criterion is the author's: **a step whose absence blocks the
flow, forcing somebody to a terminal to carry on, belongs in the browser**.

The step that costs money is handled differently. **"Have this reviewed" asks
first**: which host, which model, and what is left of the week. Pressing it
disables the button and says "asking…" — a headless call takes fifteen seconds
or so, and a silent button is one somebody presses again. The verdict and the
reviewer's own sentence come back into the panel, with `unclear` spelled out as
neither a pass nor a rejection. The week's usage is on the dashboard.

**There are 21 background tasks**: build index, build graph, rebuild the
directory table, semantic linking, lint fix, stats, close the session
(`magi sync --close`), install into your agent CLIs, backlog sync, radar
harvest, citation gap, the three ingest steps (pick up `inbox/`, run the queue,
commit), model pulls and task-engine install, plus the ones that need a second
confirmation: setup / migrate / pm init / delete legacy copies / radar
scheduling.

> [!NOTE]
> **Still terminal-only**: `magi init` (there is no dashboard before there is a
> project), the maintenance commands `validate` / `verify` / `tags *` /
> `math *`, and **compiling** — compiling needs an LLM, so it is a skill rather
> than a command, and `magi compile` does not exist and will not (see the
> compile chapter). That last one is equally true at the terminal; it is not a
> gap in the browser.

The **⚡ MAGI MODE** toggle in the top bar switches the tactical theme: red is combat state (dark), blue is silent watch (light), and ☀︎/☽ switches between the two.

The ◐ in the bottom-right corner is the material and backdrop panel: glass blur, opacity, CRT scanlines, and **which artwork to use** — click one thumbnail to pin it, several to rotate only among those, none to let it rotate by window shape (red and blue remember separately). To use your own images, drop them in `~/.config/magi/ui-backgrounds/blue|red/`.

> [!FIX]
> - **Port already in use**: switch `--port`, or shut down the previous instance first.
> - **Changed code / upgraded, but the UI didn't change**: static files take effect immediately, but **backend changes require restarting `magi ui`**. If styles aren't updating, that's the browser cache — hard-refresh once.
> - **The graph is empty**: run `magi graph build` first.
> - **The dashboard won't open, or shows no project**: switch projects from the top bar; the dashboard only listens on `127.0.0.1` with a Host allowlist, so **by default it's not reachable from another machine** (use SSH port forwarding for remote access).

---

## Troubleshooting quick reference {#troubleshoot}

Two commands answer most of it:

```powershell
magi sync                          # what this project needs next, with the commands to fix it
magi guide --symptoms              # look up an error message you actually saw
```

`magi sync --fix` runs the deterministic repairs itself. Below: the symptoms that need a human.

When a command fails and does not say enough, add `--verbose` (or set
`MAGI_DEBUG=1`):

```powershell
magi sync --fix --verbose
```

It changes nothing you normally see. It opens a second channel carrying **each
subprocess's full argv, exit code, duration and entire output**. `sync --fix`
otherwise reports the last two lines of each step, and when a step fails the
reason is usually in the part that got cut. The switch is inherited by child
processes, so turning it on at the outermost command answers for the innermost.

Look things up by symptom — you don't need to remember which command belongs where. The same table is available in the terminal:

```powershell
magi guide --symptoms                       # The whole index (~84 entries)
magi guide --symptoms --search "ollama"     # Filtered by keyword
```

Or paste the error to your agent and have it run `magi guide --search` (see [1.2](#howto-read)).

| Symptom | Run this first |
|---|---|
| No idea what to do next | `magi sync` — check the last line, `->`; `magi sync --fix` lets it repair |
| Maintaining several projects one by one | there is no fan-out command; loop in your shell over the paths `magi kb list --json` gives you |
| Installed, but `magi` isn't found | Open a **new terminal**; if that still doesn't work, add `~/.local/bin` to PATH |
| Upgrade fails with `failed to remove directory ... Lib` | On Windows a running `magi ui` holds the install directory. Stop the dashboard, then upgrade |
| A feature complains about a missing dependency | `magi setup --check` |
| The command says `no project found` | `cd` into the project directory, or add `--project-dir` |
| Don't know where a project lives | `magi kb list` |
| Ingestion finished, but it's not in the project | You forgot `magi ingest finalize` |
| The graph is stale | `magi graph build` — it has no incremental mode |
| Can't search for something you just wrote | `magi index` — it never triggers automatically |
| Search returns no semantic results | `magi setup --check` — a stopped Ollama starts itself, so it's not installed or the model isn't pulled; then `magi index` to backfill vectors |
| Wikilinks won't open / lots of broken links | `magi graph browse broken` |
| Duplicate concepts, sprawling tags | `magi link . --dedup-only`; `magi tags extract` |
| Card format errors | `magi lint --fix` |
| Formulas render incorrectly | `magi math format` → `magi math check` (whole project; `--json` hands the list to the `tidy` skill) |
| Citations won't export | Check the reference card's `title/authors/year/arxiv_id` frontmatter |
| A claim is marked unverified | The evidence quote must match the source verbatim, and it must be a single line |
| The radar has nothing new | Check `arxiv_categories` / `seed_arxiv_ids`; widen `--days` |
| The scheduled task never fires | Windows: `schtasks /Query`; on Linux it was never installed in the first place — write the crontab yourself |
| Changed the config, but nothing happened | Validate it with `python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"` — YAML parse failures fail silently |
| Want to see exactly what flags a command takes | `magi <command> --help`, or the **CLI command reference** at the top of this page |

> [!TIP]
> The full set of flags for every command is authoritative in `magi <command> --help` — this guide covers **when to use something, what to expect, and how to recover from errors**; it doesn't duplicate the flag reference.
