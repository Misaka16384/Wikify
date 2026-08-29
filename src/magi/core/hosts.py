"""Every agent CLI this project knows about, as one table of records.

There used to be three. `skills_cmd` had a table saying where a skill gets
installed, `review` had one saying what to run for a headless call, and
`reflect.transcripts` had one saying whose session record we know how to read.
Each was edited on its own, so the same vendor appeared under two names, one
table probed PATH for a binary that was spelled differently in another, and
adding a CLI meant finding all three.

The rule this file follows: **there are too many CLIs in the world; being
general beats being complete.** So a host is *data*. One record says what the
binary is called, where its skills go, how to ask it a question headless, and
whose transcript reader (if any) can read it back. Adding a host is adding a
record — `research.hosts` in `config.yaml` takes records of the same shape, so
a CLI nobody here has heard of can be declared by the person using it.

Two things still need code, and the record only *names* them: the transcript
reader, because every vendor stores a conversation differently and no template
describes that, and the stop hook, because a hook is an entry in the host's own
settings schema. A host missing either is simply one we cannot read sessions
from, or one where the close gate is prose in the managed block rather than an
enforced hook. Neither is an error — the same fail-soft every adapter in
`reflect.transcripts` is built to have.

**Two tiers, and the difference is testing, not quality.** Tier 1 is smoke
tested against a real install every release: Claude Code, Codex, Antigravity.
Tier 2 is declared from each vendor's own documentation and left to fail soft:
qwen, opencode. Nothing behaves differently by tier — it is a statement about
what has been *verified*, so that a bug report against a tier-2 host reads as
"this was never measured" rather than "this regressed".
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Verified against each CLI on 2026-08-20 for tier 1 (their own docs plus a
#: live install), and from vendor documentation alone for tier 2.
TIER_VERIFIED = 1
TIER_BEST_EFFORT = 2


@dataclass(frozen=True)
class Drop:
    """One directory a host loads instructions from.

    Hosts differ in two ways that matter: the folder they scan, and whether
    what lands there becomes a slash command or something the model reaches
    for on its own when the description matches. Both are worth installing.

    The paths are templates, not callables, so a record can come from
    `config.yaml` as easily as from this file. `{home}` is the user's home,
    `{config}` is `XDG_CONFIG_HOME` (or `~/.config`), and `{root}` is the MAGI
    workspace a project-scope install is anchored on.
    """

    kind: str = "skill"          # "skill" | "command"
    global_dir: str = ""         # "" -> this host has no global scope
    project_dir: str = ""        # "" -> this host has no project scope
    layout: str = "dir"          # "dir" -> <dir>/<name>/SKILL.md; "flat" -> <dir>/<name>.md
    invoke: str = ""             # what the person types, or how it fires


@dataclass(frozen=True)
class Host:
    """One CLI, everything about it."""

    key: str
    label: str = ""
    bin: str = ""
    tier: int = TIER_BEST_EFFORT
    marker: str = ""             # a dir whose presence proves the host is installed
    drops: Tuple[Drop, ...] = ()
    argv: Tuple[str, ...] = ()   # headless template; () -> not callable headless
    model_flag: str = ""         # how a model is named on that command line
    model: str = ""              # which model to ask for; "" -> the CLI own default
    reader: str = ""             # transcripts adapter; "" -> sessions unreadable
    hook: str = ""               # stop-gate writer; "" -> no hook, prose instead
    note: str = ""

    @property
    def command(self) -> str:
        return self.bin or self.key

    def headless(self, prompt: str, model: str = "") -> List[str]:
        """The command line that asks this host one question.

        Empty when the host declares no headless mode. A CLI that has one but
        does not document it does not get guessed at here: a flag inferred
        from a sibling product is a flag that fails at the worst moment.

        With no model asked for, no model flag is passed and the CLI uses
        whatever it would use interactively. That is the right default: MAGI
        does not know this account better than the person who configured it.
        """
        if not self.argv:
            return []
        line = [part.format(bin=self.command, prompt=prompt) for part in self.argv]
        wanted = model or self.model
        if wanted and self.model_flag:
            line += [self.model_flag, wanted]
        return line


# --------------------------------------------------------------------------
# Path templates
# --------------------------------------------------------------------------

def _config_home() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg) if xdg else Path.home() / ".config"


def expand(template: str, home: Optional[Path] = None,
           root: Optional[Path] = None) -> Optional[Path]:
    """A path template as a real path, or None when it names nothing.

    Returns None for an empty template and for one that needs `{root}` when no
    root was given — "this host has no project scope" and "we are not in a
    workspace" are the same answer to the caller: nowhere to put it.
    """
    if not template:
        return None
    if "{root}" in template and root is None:
        return None
    base = Path(home) if home is not None else Path.home()
    try:
        text = template.format(home=base.as_posix(),
                               config=_config_home().as_posix(),
                               root=Path(root).as_posix() if root else "")
    except (KeyError, IndexError, ValueError):
        return None
    return Path(text).expanduser()


# --------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------

#: `.agents/skills/` is the cross-agent convention — Codex, Antigravity,
#: opencode and qwen all scan it — which is why every project scope converges
#: there and a new host usually needs no new directory at all.
AGENTS_SKILLS = ".agents/skills"

BUILTIN: Tuple[Host, ...] = (
    Host(
        key="claude", label="Claude Code", bin="claude", tier=TIER_VERIFIED,
        marker="{home}/.claude",
        drops=(
            Drop(kind="skill",
                 global_dir="{home}/.claude/skills",
                 project_dir="{root}/.claude/skills",
                 invoke="/{name}"),
        ),
        argv=("{bin}", "-p", "{prompt}"), model_flag="--model",
        reader="claude", hook="claude",
        note="The magi plugin already serves these as /magi:<name>; a copy here also "
             "answers to a plain /<name>.",
    ),
    Host(
        key="codex", label="Codex CLI", bin="codex", tier=TIER_VERIFIED,
        marker="{home}/.codex",
        drops=(
            Drop(kind="skill",
                 global_dir="{home}/" + AGENTS_SKILLS,
                 project_dir="{root}/" + AGENTS_SKILLS,
                 invoke="$" + "{name}  (or let Codex pick it by description)"),
            Drop(kind="skill",
                 global_dir="{home}/.codex/skills",
                 project_dir="",       # Codex has no project-level .codex/skills
                 invoke="$" + "{name}  (Codex-native location)"),
        ),
        argv=("{bin}", "exec", "{prompt}"), model_flag="-m",
        reader="codex",
        note="Codex skills are not slash commands: type $<name> to force one, or let it "
             "choose by description.",
    ),
    Host(
        key="antigravity", label="Antigravity CLI (agy)", bin="agy",
        tier=TIER_VERIFIED,
        marker="{home}/.gemini/config",
        drops=(
            Drop(kind="skill",
                 global_dir="{home}/.gemini/config/skills",
                 project_dir="{root}/" + AGENTS_SKILLS,
                 invoke="named in your prompt, or auto by description (/skills lists them)"),
        ),
        # `--model`, not `-m`: its own --help says so, and this vendor's other
        # CLI took the short form, which is exactly the kind of near-miss that
        # only shows up on the call you needed.
        argv=("{bin}", "-p", "{prompt}"), model_flag="--model",
        reader="antigravity",
        note="agy has no per-skill slash command — /skills browses what is loaded.",
    ),
    Host(
        key="qwen", label="qwen-code", bin="qwen", tier=TIER_BEST_EFFORT,
        marker="{home}/.qwen",
        drops=(
            Drop(kind="skill",
                 global_dir="{home}/" + AGENTS_SKILLS,
                 project_dir="{root}/" + AGENTS_SKILLS,
                 invoke="named in your prompt, or auto by description"),
        ),
        argv=("{bin}", "-p", "{prompt}"), model_flag="-m",
        reader="qwen",
        note="Tier 2, and here by inheritance rather than by request: qwen-code is a fork "
             "of the CLI Antigravity replaced, so it is described from that lineage and "
             "the vendor's docs, not from a live install.",
    ),
    Host(
        key="opencode", label="opencode", bin="opencode", tier=TIER_BEST_EFFORT,
        marker="{config}/opencode",
        drops=(
            Drop(kind="command",
                 global_dir="{config}/opencode/commands",
                 project_dir="{root}/.opencode/commands",
                 layout="flat",
                 invoke="/{name}"),
            Drop(kind="skill",
                 global_dir="{config}/opencode/skills",
                 project_dir="{root}/.opencode/skills",
                 invoke="auto by description"),
        ),
        reader="opencode",
        note="opencode separates the two: commands/ gives you /<name>, skills/ lets the "
             "model reach for it unprompted. Both get installed. No headless entry: its "
             "non-interactive mode is not one this project has verified, and the reviewer "
             "would rather have one vendor fewer than a command that fails mid-review.",
    ),
)


#: Older spellings that still resolve. `gemini` was briefly the outward name
#: for this vendor's CLI; that product is retired and Antigravity is simply
#: what it is called, but a command line somebody already learned should not
#: start erroring.
ALIASES = {"gemini": "antigravity"}


def resolve(name: str) -> str:
    """The key for a host somebody named, however they spelled it."""
    key = str(name or "").strip().lower()
    return ALIASES.get(key, key)


# --------------------------------------------------------------------------
# Records from config
# --------------------------------------------------------------------------

def _drop_from(raw) -> Optional[Drop]:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "skill")
    layout = str(raw.get("layout") or "dir")
    if kind not in ("skill", "command") or layout not in ("dir", "flat"):
        return None
    drop = Drop(kind=kind,
                global_dir=str(raw.get("global_dir") or ""),
                project_dir=str(raw.get("project_dir") or ""),
                layout=layout,
                invoke=str(raw.get("invoke") or ""))
    return drop if (drop.global_dir or drop.project_dir) else None


def host_from(raw) -> Optional[Host]:
    """One config record as a Host, or None if it is not usable.

    Fail-soft on purpose. A typo in a hand-written host record should cost you
    that host, not every command that reads the table.
    """
    if not isinstance(raw, dict):
        return None
    key = str(raw.get("key") or "").strip().lower()
    if not key or not key.replace("-", "").replace("_", "").isalnum():
        return None
    drops = tuple(drop for drop in (_drop_from(item) for item in raw.get("drops") or [])
                  if drop is not None)
    argv = tuple(str(part) for part in raw.get("argv") or [] if str(part))
    try:
        tier = int(raw.get("tier") or TIER_BEST_EFFORT)
    except (TypeError, ValueError):
        tier = TIER_BEST_EFFORT
    return Host(key=key,
                label=str(raw.get("label") or key),
                bin=str(raw.get("bin") or key),
                tier=tier if tier in (TIER_VERIFIED, TIER_BEST_EFFORT) else TIER_BEST_EFFORT,
                marker=str(raw.get("marker") or ""),
                hook=str(raw.get("hook") or ""),
                drops=drops,
                argv=argv,
                model_flag=str(raw.get("model_flag") or ""),
                model=str(raw.get("model") or ""),
                reader=str(raw.get("reader") or ""),
                note=str(raw.get("note") or ""))


def catalog(config: Optional[dict] = None) -> Dict[str, Host]:
    """Every known host, built-ins first, then whatever `research.hosts` adds.

    A config record under a built-in key replaces it outright rather than
    merging field by field: half a record from here and half from there is a
    host nobody can reason about, and the person who wrote the record is the
    one with the CLI in front of them.
    """
    table: Dict[str, Host] = {host.key: host for host in BUILTIN}
    for raw in _configured(config):
        host = host_from(raw)
        if host is not None:
            table[host.key] = host
    return table


def _configured(config: Optional[dict]) -> List:
    if not isinstance(config, dict):
        return []
    try:
        from .config_loader import get as config_get

        value = config_get(config, "research.hosts", []) or []
    except Exception:
        return []
    return value if isinstance(value, list) else []


def names(config: Optional[dict] = None) -> Tuple[str, ...]:
    """Host keys in a stable order: the built-ins as listed, then the rest."""
    table = catalog(config)
    order = [host.key for host in BUILTIN if host.key in table]
    return tuple(order + [key for key in table if key not in order])
