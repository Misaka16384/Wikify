#!/usr/bin/env python3
"""Local deterministic helpers for llm-wiki.

This is not a replacement for the agentic /wiki workflows. It gives agents and
humans a local command for the checks that can be done without an LLM.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import hashlib
import os
import re
import shutil
import sqlite3
import sys
import yaml
from yaml.scanner import ScannerError
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def wash_windows_path(path_str: str) -> str:
    if os.name != "nt":
        return path_str
    if not path_str:
        return path_str

    # Handle /tmp
    if path_str == "/tmp" or path_str.startswith("/tmp/"):
        import tempfile
        temp_dir = tempfile.gettempdir()
        rest = path_str[len("/tmp"):]
        rest = rest.replace("/", "\\")
        if rest.startswith("\\"):
            return temp_dir + rest
        return temp_dir + ("\\" + rest if rest else "")

    # Handle drive letters /c/... or /C/... or /c
    match = re.match(r"^/([a-zA-Z])(/.*)?$", path_str)
    if match:
        drive = match.group(1).upper()
        rest = match.group(2) or ""
        rest = rest.replace("/", "\\")
        return f"{drive}:{rest}"

    # General absolute unix-like path starting with /
    if path_str.startswith("/") and not path_str.startswith("//"):
        try:
            current_drive = Path.cwd().drive or "C:"
        except Exception:
            current_drive = "C:"
        rest = path_str.replace("/", "\\")
        return f"{current_drive}{rest}"

    return path_str


def get_home_directory() -> Path:
    home_env = os.environ.get("HOME")
    if home_env:
        return Path(wash_windows_path(home_env))

    userprofile_env = os.environ.get("USERPROFILE")
    if userprofile_env:
        return Path(wash_windows_path(userprofile_env))

    return Path.home()



RAW_TYPES = {"articles", "papers", "repos", "notes", "data"}
ARTICLE_CATEGORIES = {"concept", "topic", "reference"}
ARTICLE_DIRS = {
    "concept": "concepts",
    "topic": "topics",
    "reference": "references",
}
INVENTORY_KINDS = {
    "item",
    "ingest-candidate",
    "entity",
    "corpus",
    "question",
    "task",
    "artifact",
    "watch",
}
INVENTORY_STATUSES = {
    "proposed",
    "active",
    "blocked",
    "ingested",
    "superseded",
    "archived",
}
INVENTORY_PRIORITIES = {"p0", "p1", "p2", "p3", "p4"}
DATASET_STATUSES = {"proposed", "active", "external", "archived", "unavailable"}
DATASET_STORAGE = {"local", "remote", "external", "hybrid"}
SCHEMA_STATUSES = {"unknown", "inferred", "declared", "validated"}
CONFIDENCE_VALUES = {"high", "medium", "low"}
VOLATILITY_VALUES = {"hot", "warm", "cold"}
PERMISSION_DENIED_ERRNOS = {1, 13}

ROOT_ALLOWED = {
    "_index.md",
    "config.md",
    "config.yaml",
    "CLAUDE.md",
    "AGENTS.md",
    "log.md",
    "scratch",
    "raw",
    "wiki",
    "drafts",
    "inventory",
    "datasets",
    "output",
    "inbox",
    ".obsidian",
    ".claude",
    ".agents",
    ".git",
    ".gitignore",
    ".vscode",
    ".idea",
    ".librarian",
    ".audit",
    ".research-session.json",
    ".thesis-session.json",
    ".session-events.jsonl",
    ".session-checkpoint.json",
}
HUB_ALLOWED = {"wikis.json", "_index.md", "log.md", "topics"}
RAW_ALLOWED = {"_index.md", "articles", "papers", "repos", "notes", "data"}
WIKI_ALLOWED = {"_index.md", "concepts", "topics", "references", "theses"}
INVENTORY_ALLOWED = {
    "_index.md",
    "items",
    "candidates",
    "entities",
    "corpora",
    "views",
}
DATASET_CHILD_ALLOWED = {"_index.md", "MANIFEST.md", "samples", "profiles", "queries"}


@dataclass
class Issue:
    severity: str
    message: str
    path: Path | None = None
    fixable: bool = False
    fixed: bool = False

    def sort_key(self) -> tuple[int, str, str]:
        order = {"critical": 0, "warning": 1, "suggestion": 2, "info": 3}
        return (order.get(self.severity, 9), self.rel, self.message)

    @property
    def rel(self) -> str:
        return str(self.path) if self.path else ""


@dataclass
class Document:
    path: Path
    frontmatter: dict[str, Any]
    body: str
    raw_text: str = ""


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (dt.date, dt.datetime)):
            return obj.isoformat()
        return super().default(obj)


class LintContext:
    def __init__(self, root: Path, fix: bool = False) -> None:
        self.root = root.resolve()
        self.fix = fix
        self.issues: list[Issue] = []
        self.fixes: list[str] = []
        self.documents: dict[Path, Document] = {}
        self.referenced_raw: set[Path] = set()

        self.cache_path = self.root / "output" / ".lint_cache.json"
        self.cache_data: dict[str, Any] = {"metadata": {}, "files": {}}
        self.cache_updated = False
        self.load_cache()

    def load_cache(self) -> None:
        if self.cache_path.exists():
            try:
                self.cache_data = json.loads(self.cache_path.read_text(encoding="utf-8"))
                if not isinstance(self.cache_data, dict):
                    self.cache_data = {"metadata": {}, "files": {}}
                if "metadata" not in self.cache_data:
                    self.cache_data["metadata"] = {}
                if "files" not in self.cache_data:
                    self.cache_data["files"] = {}
            except Exception:
                self.cache_data = {"metadata": {}, "files": {}}

    def save_cache(self) -> None:
        if not self.cache_updated:
            return
        # Clean up stale entries for files that no longer exist or are not schema-checked
        existing_rel_paths = set()
        for path in content_markdown_files(self.root):
            if is_schema_checked_path(self.root, path):
                try:
                    rel = str(path.resolve().relative_to(self.root))
                    existing_rel_paths.add(rel)
                except ValueError:
                    pass
        if "files" in self.cache_data:
            self.cache_data["files"] = {
                k: v for k, v in self.cache_data["files"].items()
                if k in existing_rel_paths
            }
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(
                json.dumps(self.cache_data, indent=2, ensure_ascii=False, cls=DateTimeEncoder),
                encoding="utf-8"
            )
        except Exception as e:
            sys.stderr.write(f"Warning: Could not save lint cache: {e}\n")



    def rel(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def issue(
        self,
        severity: str,
        message: str,
        path: Path | None = None,
        fixable: bool = False,
        fixed: bool = False,
    ) -> None:
        self.issues.append(Issue(severity, message, path, fixable, fixed))

    def fixed(self, message: str) -> None:
        self.fixes.append(message)

    def active_issues(self) -> list[Issue]:
        return [issue for issue in self.issues if not issue.fixed]

    def counts(self) -> dict[str, int]:
        counts = {"critical": 0, "warning": 0, "suggestion": 0, "info": 0}
        for issue in self.active_issues():
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in split_inline_list(inner)]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def split_inline_list(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for char in value:
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            current.append(char)
        elif char == "," and quote is None:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append("".join(current).strip())
    return parts


def parse_frontmatter_block(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - ") and current_key:
            current_value = data.setdefault(current_key, [])
            if not isinstance(current_value, list):
                current_value = []
                data[current_key] = current_value
            current_value.append(parse_scalar(raw_line[4:]))
            continue
        if raw_line.startswith(" ") or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        current_key = key
        value = value.strip()
        if value == "":
            data[key] = []
        else:
            data[key] = parse_scalar(value)
    return data


def split_markdown_frontmatter(text: str) -> tuple[str, str] | None:
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    return text[4:end], text[end + 4 :]


def frontmatter_field_value(frontmatter: str, field: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(field)}\s*:\s*(.*)$", frontmatter)
    if not match:
        return None
    value = match.group(1).strip()
    return value if value else None


def frontmatter_has_value(frontmatter: str, field: str) -> bool:
    value = frontmatter_field_value(frontmatter, field)
    if value not in {None, "", "[]"}:
        return True
    return bool(
        re.search(
            rf"(?ms)^{re.escape(field)}\s*:\s*\n(?:  - .+\n?)+",
            frontmatter,
        )
    )


def yaml_quote(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def insert_frontmatter_after_title(frontmatter: str, lines: list[str]) -> str:
    parts = frontmatter.splitlines()
    insert_at = 1 if parts else 0
    for index, line in enumerate(parts):
        if line.startswith("title:"):
            insert_at = index + 1
            break
    return "\n".join(parts[:insert_at] + lines + parts[insert_at:])


def append_frontmatter_lines(frontmatter: str, lines: list[str]) -> str:
    return frontmatter.rstrip() + "\n" + "\n".join(lines)


def set_frontmatter_list(frontmatter: str, field: str, values: list[str]) -> str:
    lines = frontmatter.splitlines()
    output: list[str] = []
    index = 0
    replaced = False
    while index < len(lines):
        line = lines[index]
        if re.match(rf"^{re.escape(field)}\s*:", line):
            output.append(f"{field}:")
            output.extend(f"  - {value}" for value in values)
            index += 1
            while index < len(lines) and lines[index].startswith("  - "):
                index += 1
            replaced = True
            continue
        output.append(line)
        index += 1
    if not replaced:
        output.append(f"{field}:")
        output.extend(f"  - {value}" for value in values)
    return "\n".join(output)


def first_body_summary(body: str) -> str:
    summary_match = re.search(r"(?m)^\*\*Summary\*\*:\s*(.+)$", body)
    if summary_match:
        return clean_summary(summary_match.group(1))

    paragraphs: list[str] = []
    current: list[str] = []
    in_code = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if (
            line.startswith("#")
            or line.startswith("|")
            or line.startswith("- ")
            or re.match(r"^\d+\.\s", line)
            or line == "---"
        ):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(" ".join(current))

    for paragraph in paragraphs:
        cleaned = clean_summary(paragraph)
        if len(cleaned) >= 40:
            return cleaned
    return "Compiled wiki article."


def clean_summary(value: str) -> str:
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    value = re.sub(r"\[\[[^|\]]+\|([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"[*_`]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value[:260].rstrip()


def write_markdown_frontmatter(path: Path, frontmatter: str, body: str) -> None:
    path.write_text("---\n" + frontmatter.rstrip() + "\n---" + body, encoding="utf-8")


def is_permission_denied(exc: BaseException) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "errno", None) in PERMISSION_DENIED_ERRNOS


def permission_denied_message(path: Path | None, operation: str, exc: BaseException) -> str:
    target = str(path or getattr(exc, "filename", None) or "wiki path")
    return (
        f"permission denied while trying to {operation}: {target}\n"
        f"{type(exc).__name__}: {exc}\n\n"
        "The path exists, but this process cannot read or list its contents. "
        "On macOS this usually means the app launching Codex/the terminal lacks "
        "Full Disk Access or iCloud Drive access. Grant access to the exact launcher, "
        "restart Codex, and try again. The configured hub_path is probably correct; "
        "do not switch to a ~/wiki fallback or machine-local resolved_path for this error."
    )


def read_document(ctx: LintContext, path: Path) -> Document | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        ctx.issue("critical", "Markdown file is not valid UTF-8.", path)
        return None
    except OSError as exc:
        if is_permission_denied(exc):
            ctx.issue("critical", permission_denied_message(path, "read file", exc), path)
            return None
        ctx.issue("critical", f"Could not read file: {exc}", path)
        return None

    # Normalize line endings for Windows compatibility
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    if not text.startswith("---\n"):
        ctx.issue("critical", "Markdown file is missing YAML frontmatter.", path)
        return None
    end = text.find("\n---", 4)
    if end == -1:
        ctx.issue("critical", "Markdown file has unterminated YAML frontmatter.", path)
        return None
    frontmatter_text = text[4:end]
    body = text[end + 4 :]

    # Use yaml.safe_load as the primary parser (most robust)
    try:
        parsed_fm = yaml.safe_load(frontmatter_text)
        if not isinstance(parsed_fm, dict):
            parsed_fm = {}
    except ScannerError:
        fixed_text = re.sub(
            r'\nsummary:\s*"(.*?)"\n',
            lambda m: '\nsummary: "' + m.group(1).replace('\\', '\\\\').replace('\\\\\\\\', '\\\\') + '"\n',
            "\n" + frontmatter_text + "\n",
            flags=re.DOTALL
        )
        if fixed_text != "\n" + frontmatter_text + "\n":
            frontmatter_text = fixed_text.strip("\n")
            ctx.issue("info", "Auto-escaped backslashes in YAML summary.", path, fixable=True, fixed=True)
            if ctx.fix:
                write_markdown_frontmatter(path, frontmatter_text, body)
                ctx.fixed(f"Auto-escaped backslashes in {path.name} YAML summary.")
        else:
            ctx.issue("critical", "YAML syntax error (likely unescaped backslashes).", path)
        # Fall back to custom parser on YAML error
        parsed_fm = parse_frontmatter_block(frontmatter_text)
    except yaml.YAMLError:
        parsed_fm = parse_frontmatter_block(frontmatter_text)

    return Document(path=path, frontmatter=parsed_fm, body=body, raw_text=text)


def markdown_files(root: Path) -> list[Path]:
    try:
        if not root.exists():
            return []
        return sorted(path for path in root.rglob("*.md") if path.is_file())
    except OSError as exc:
        if is_permission_denied(exc):
            raise SystemExit(permission_denied_message(root, "list markdown files under", exc)) from exc
        raise


def content_markdown_files(root: Path) -> list[Path]:
    """Return content markdown files, targeting known directories to avoid traversing .git/.obsidian."""
    known_dirs = ("raw", "wiki", "inventory", "datasets")
    result: list[Path] = []

    # If root's name is one of the known dirs AND none of those dirs exist as children,
    # treat root itself as the search root (we're already inside a known dir).
    if root.name in known_dirs and not any((root / d).exists() for d in known_dirs):
        search_roots = [root]
    else:
        search_roots = [root / d for d in known_dirs if (root / d).exists()]

    for search_root in search_roots:
        try:
            result.extend(
                p for p in search_root.rglob("*.md")
                if p.is_file() and p.name not in {"_index.md", "config.md"}
            )
        except OSError:
            continue
    return sorted(result)


def load_documents(ctx: LintContext) -> None:
    ctx.documents = {}
    for path in content_markdown_files(ctx.root):
        if not is_schema_checked_path(ctx.root, path):
            continue
            
        doc = None
        try:
            rel_path_str = str(path.resolve().relative_to(ctx.root))
        except ValueError:
            rel_path_str = None

        if rel_path_str and rel_path_str in ctx.cache_data["files"]:
            cached = ctx.cache_data["files"][rel_path_str]
            try:
                stat = path.stat()
                if cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
                    doc = Document(
                        path=path,
                        frontmatter=cached.get("frontmatter", {}),
                        body=cached.get("body", ""),
                        raw_text=cached.get("raw_text", "")
                    )
            except Exception:
                pass

        if doc is None and rel_path_str and rel_path_str in ctx.cache_data["files"]:
            cached = ctx.cache_data["files"][rel_path_str]
            try:
                # Fallback: MD5 hash match
                raw_text = path.read_text(encoding="utf-8", errors="replace")
                raw_text_norm = raw_text.replace('\r\n', '\n').replace('\r', '\n')
                file_md5 = hashlib.md5(raw_text_norm.encode("utf-8", errors="replace")).hexdigest()
                if cached.get("md5") == file_md5:
                    doc = Document(
                        path=path,
                        frontmatter=cached.get("frontmatter", {}),
                        body=cached.get("body", ""),
                        raw_text=raw_text_norm
                    )
                    # Self-heal cached mtime/size for fast subsequent runs
                    stat = path.stat()
                    cached["mtime"] = stat.st_mtime
                    cached["size"] = stat.st_size
                    ctx.cache_updated = True
            except Exception:
                pass

        if doc is None:
            doc = read_document(ctx, path)
            if doc is not None and rel_path_str:
                try:
                    stat = path.stat()
                    file_md5 = hashlib.md5(doc.raw_text.encode("utf-8", errors="replace")).hexdigest()
                    ctx.cache_data["files"][rel_path_str] = {
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "md5": file_md5,
                        "frontmatter": doc.frontmatter,
                        "body": doc.body,
                        "raw_text": doc.raw_text
                    }
                    ctx.cache_updated = True
                except Exception:
                    pass

        if doc is not None:
            ctx.documents[path.resolve()] = doc



def is_schema_checked_path(root: Path, path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return False
    parts = rel.parts
    if not parts or any(part.startswith(".") for part in parts[:-1]):
        return False
    return parts[0] in {"raw", "wiki", "inventory", "datasets"}


def require_fields(ctx: LintContext, doc: Document, fields: list[str], severity: str = "critical") -> None:
    for field in fields:
        value = doc.frontmatter.get(field)
        if value in (None, "", []):
            ctx.issue(severity, f"Required frontmatter field is missing or empty: {field}.", doc.path)


def check_enum(
    ctx: LintContext,
    doc: Document,
    field: str,
    allowed: set[str],
    severity: str = "critical",
) -> None:
    value = doc.frontmatter.get(field)
    if value in (None, ""):
        return
    if str(value) not in allowed:
        expected = ", ".join(sorted(allowed))
        ctx.issue(severity, f"Invalid {field}: {value!r}; expected one of {expected}.", doc.path)


def ensure_dir_index(ctx: LintContext, directory: Path, title: str) -> None:
    if not directory.exists():
        if ctx.fix:
            directory.mkdir(parents=True, exist_ok=True)
            ctx.fixed(f"Created directory {ctx.rel(directory)}.")
        else:
            ctx.issue("critical", "Required directory is missing.", directory, fixable=True)
            return
    index = directory / "_index.md"
    if not index.exists():
        if ctx.fix:
            index.write_text(minimal_index(title), encoding="utf-8")
            ctx.fixed(f"Created index {ctx.rel(index)}.")
        else:
            ctx.issue("critical", "Required _index.md is missing.", index, fixable=True)


def minimal_index(title: str) -> str:
    today = dt.date.today().isoformat()
    return (
        f"# {title} Index\n\n"
        "> Generated by local magi lint.\n\n"
        f"Last updated: {today}\n\n"
        "## Contents\n\n"
        "| File | Summary | Tags | Updated |\n"
        "|------|---------|------|---------|\n\n"
        "## Recent Changes\n\n"
        f"- {today}: Created missing index.\n"
    )


def check_structure(ctx: LintContext) -> None:
    if not ctx.root.exists():
        ctx.issue("critical", "Wiki root does not exist.", ctx.root)
        return
    if is_hub(ctx.root):
        for name in ["wikis.json", "_index.md", "log.md", "topics"]:
            path = ctx.root / name
            if not path.exists():
                ctx.issue("critical", "Required hub path is missing.", path)
        return
    if not (ctx.root / "_index.md").exists():
        ctx.issue("critical", "Master _index.md is missing.", ctx.root / "_index.md", fixable=True)
    if not (ctx.root / "config.md").exists():
        ctx.issue("critical", "config.md is missing.", ctx.root / "config.md")

    required = [
        ("raw", "Raw"),
        ("raw/articles", "Articles"),
        ("raw/papers", "Papers"),
        ("raw/repos", "Repos"),
        ("raw/notes", "Notes"),
        ("raw/data", "Data"),
        ("wiki", "Wiki"),
        ("wiki/concepts", "Concepts"),
        ("wiki/topics", "Topics"),
        ("wiki/references", "References"),
        ("wiki/theses", "Theses"),
        ("output", "Output"),
    ]
    for rel, title in required:
        ensure_dir_index(ctx, ctx.root / rel, title)

    if (ctx.root / "inventory").exists():
        ensure_dir_index(ctx, ctx.root / "inventory", "Inventory")
        for rel, title in [
            ("inventory/items", "Items"),
            ("inventory/candidates", "Candidates"),
            ("inventory/entities", "Entities"),
            ("inventory/corpora", "Corpora"),
            ("inventory/views", "Views"),
        ]:
            path = ctx.root / rel
            if path.exists():
                ensure_dir_index(ctx, path, title)

    if (ctx.root / "datasets").exists():
        ensure_dir_index(ctx, ctx.root / "datasets", "Datasets")

        for manifest in sorted((ctx.root / "datasets").glob("*/MANIFEST.md")):
            dataset_dir = manifest.parent
            ensure_dir_index(ctx, dataset_dir, dataset_dir.name)
            for rel, title in [
                ("samples", f"{dataset_dir.name} Samples"),
                ("profiles", f"{dataset_dir.name} Profiles"),
                ("queries", f"{dataset_dir.name} Queries"),
            ]:
                path = dataset_dir / rel
                if path.exists():
                    ensure_dir_index(ctx, path, title)

    inbox = ctx.root / "inbox"
    if not inbox.exists():
        if ctx.fix:
            inbox.mkdir(parents=True, exist_ok=True)
            (inbox / ".processed").mkdir(exist_ok=True)
            ctx.fixed("Created inbox/ and inbox/.processed/.")
        else:
            ctx.issue("warning", "inbox/ is missing.", inbox, fixable=True)


def is_hub(path: Path) -> bool:
    return (path / "wikis.json").exists() and (path / "topics").exists()


def check_frontmatter_schema(ctx: LintContext) -> None:
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        rel = doc.path.resolve().relative_to(ctx.root)
        parts = rel.parts
        if not parts:
            continue
        if parts[0] == "raw":
            require_fields(ctx, doc, ["title", "source", "type", "ingested"])
            # tags/summary on raw conversions are enrichment the ingest tools
            # cannot infer — flag them, but a fresh `magi ingest tex` output
            # must not fail its own toolchain's lint.
            require_fields(ctx, doc, ["tags", "summary"], severity="warning")
            check_enum(ctx, doc, "type", RAW_TYPES)
        elif parts[0] == "wiki":
            if doc.frontmatter.get("type") == "thesis":
                require_fields(ctx, doc, ["title", "created", "updated", "tags", "summary"])
            else:
                require_fields(ctx, doc, ["title", "category", "created", "updated", "tags", "summary"])
                check_enum(ctx, doc, "category", ARTICLE_CATEGORIES)
            if "confidence" in doc.frontmatter:
                check_enum(ctx, doc, "confidence", CONFIDENCE_VALUES, severity="warning")
            if "volatility" in doc.frontmatter:
                check_enum(ctx, doc, "volatility", VOLATILITY_VALUES, severity="warning")
        elif parts[0] == "inventory":
            if len(parts) >= 2 and parts[1] == "views":
                require_fields(ctx, doc, ["title", "view", "updated", "summary"])
            else:
                require_fields(
                    ctx,
                    doc,
                    ["title", "kind", "status", "priority", "created", "updated", "tags", "summary"],
                )
                check_enum(ctx, doc, "kind", INVENTORY_KINDS)
                check_enum(ctx, doc, "status", INVENTORY_STATUSES)
                check_enum(ctx, doc, "priority", INVENTORY_PRIORITIES)
        elif parts[0] == "datasets" and doc.path.name == "MANIFEST.md":
            require_fields(
                ctx,
                doc,
                [
                    "title",
                    "dataset_id",
                    "status",
                    "storage",
                    "locations",
                    "formats",
                    "schema_status",
                    "created",
                    "updated",
                    "tags",
                    "summary",
                ],
            )
            check_enum(ctx, doc, "status", DATASET_STATUSES)
            check_enum(ctx, doc, "storage", DATASET_STORAGE)
            check_enum(ctx, doc, "schema_status", SCHEMA_STATUSES)

        tags = doc.frontmatter.get("tags")
        if "tags" in doc.frontmatter and (not isinstance(tags, list) or not tags):
            ctx.issue("warning", "tags must be a non-empty list.", doc.path)


def check_body_structure(ctx: LintContext) -> None:
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            continue
            
        body = doc.body
        
        # Papers Structure Check
        if parts[0] == "wiki" and len(parts) >= 2 and parts[1] == "references":
            if str(doc.frontmatter.get("exclude_structure_check")).lower() != "true":
                if not re.search(r"^##\s+\d*\.?\s*Key\s+Contributions", body, re.MULTILINE | re.IGNORECASE):
                    ctx.issue("critical", "Paper is missing required structural heading: '## 1. Key Contributions...'", doc.path)
                if not re.search(r"^##\s+\d*\.?\s*Theoretical\s+Framework", body, re.MULTILINE | re.IGNORECASE):
                    ctx.issue("critical", "Paper is missing required structural heading: '## 2. Theoretical Framework...'", doc.path)
                
        # Concepts Structure Check
        elif parts[0] == "wiki" and len(parts) >= 2 and parts[1] == "concepts":
            if str(doc.frontmatter.get("exclude_structure_check")).lower() != "true":
                if not re.search(r"^##\s+\d*\.?\s*Core\s+Definition", body, re.MULTILINE | re.IGNORECASE):
                    ctx.issue("critical", "Concept is missing required structural heading: '## 1. Core Definition...'", doc.path)
                if not re.search(r"^##\s+\d*\.?\s*Mathematical\s+Formalism", body, re.MULTILINE | re.IGNORECASE):
                    ctx.issue("critical", "Concept is missing required structural heading: '## 2. Mathematical Formalism...'", doc.path)


def fix_legacy_wiki_frontmatter(ctx: LintContext) -> None:
    if not ctx.fix:
        return
    changed = False
    today = dt.date.today().isoformat()
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if len(rel.parts) < 3 or rel.parts[0] != "wiki":
            continue
        text = doc.path.read_text(encoding="utf-8")
        parts = split_markdown_frontmatter(text)
        if parts is None:
            continue
        frontmatter, body = parts
        original = frontmatter
        bucket = rel.parts[1]
        is_thesis = doc.frontmatter.get("type") == "thesis" or bucket == "theses"

        if not is_thesis and bucket in {"concepts", "topics", "references"} and not frontmatter_has_value(
            frontmatter, "category"
        ):
            frontmatter = insert_frontmatter_after_title(
                frontmatter,
                [f"category: {bucket[:-1] if bucket.endswith('s') else bucket}"],
            )

        if not frontmatter_has_value(frontmatter, "summary"):
            frontmatter = insert_frontmatter_after_title(
                frontmatter,
                [f"summary: {yaml_quote(first_body_summary(body))}"],
            )

        if not frontmatter_has_value(frontmatter, "tags"):
            tag = "thesis" if is_thesis else bucket[:-1] if bucket.endswith("s") else "wiki"
            frontmatter = append_frontmatter_lines(frontmatter, [f"tags: [{tag}]"])

        if not frontmatter_has_value(frontmatter, "created"):
            created = (
                frontmatter_field_value(frontmatter, "updated")
                or frontmatter_field_value(frontmatter, "verified")
                or today
            )
            frontmatter = append_frontmatter_lines(frontmatter, [f"created: {created}"])

        if not frontmatter_has_value(frontmatter, "updated"):
            updated = (
                frontmatter_field_value(frontmatter, "created")
                or frontmatter_field_value(frontmatter, "verified")
                or today
            )
            frontmatter = append_frontmatter_lines(frontmatter, [f"updated: {updated}"])

        if not frontmatter_has_value(frontmatter, "volatility"):
            frontmatter = append_frontmatter_lines(frontmatter, ["volatility: warm"])

        if frontmatter != original:
            write_markdown_frontmatter(doc.path, frontmatter, body)
            ctx.fixed(f"Repaired frontmatter in {ctx.rel(doc.path)}.")
            changed = True

    if changed:
        load_documents(ctx)


def canonical_path_for(root: Path, doc: Document) -> Path | None:
    rel = doc.path.resolve().relative_to(root)
    parts = rel.parts
    if not parts:
        return None
    fm = doc.frontmatter
    if parts[0] == "raw":
        source_type = fm.get("type")
        if source_type in RAW_TYPES:
            return root / "raw" / str(source_type) / doc.path.name
    if parts[0] == "wiki":
        if fm.get("type") == "thesis":
            return root / "wiki" / "theses" / doc.path.name
        category = fm.get("category")
        if category in ARTICLE_DIRS:
            return root / "wiki" / ARTICLE_DIRS[str(category)] / doc.path.name
    if parts[0] == "inventory" and len(parts) >= 2 and parts[1] != "views":
        kind = fm.get("kind")
        if kind == "item":
            return root / "inventory" / "items" / doc.path.name
        if kind == "entity":
            return root / "inventory" / "entities" / doc.path.name
        if kind == "corpus":
            return root / "inventory" / "corpora" / doc.path.name
        if kind in {"ingest-candidate", "question", "task", "artifact", "watch"}:
            return root / "inventory" / "candidates" / doc.path.name
    return None


def check_canonical_placement(ctx: LintContext) -> None:
    moved = False
    for doc in list(sorted(ctx.documents.values(), key=lambda item: str(item.path))):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] not in {"raw", "wiki", "inventory"}:
            continue
        expected = canonical_path_for(ctx.root, doc)
        if expected is None or expected.resolve() == doc.path.resolve():
            continue
        if ctx.fix:
            expected.parent.mkdir(parents=True, exist_ok=True)
            if expected.exists():
                ctx.issue(
                    "critical",
                    f"File belongs at {ctx.rel(expected)}, but destination already exists.",
                    doc.path,
                )
                continue
            shutil.move(str(doc.path), str(expected))
            ctx.issue(
                "critical",
                f"Moved misplaced file to {ctx.rel(expected)}.",
                doc.path,
                fixed=True,
            )
            ctx.fixed(f"Moved {ctx.rel(doc.path)} to {ctx.rel(expected)}.")
            moved = True
        else:
            ctx.issue(
                "critical",
                f"File is in the wrong directory; expected {ctx.rel(expected)}.",
                doc.path,
                fixable=True,
            )

    for manifest in sorted((ctx.root / "datasets").glob("*/MANIFEST.md")):
        doc = ctx.documents.get(manifest.resolve())
        if not doc:
            continue
        dataset_id = doc.frontmatter.get("dataset_id")
        if dataset_id and dataset_id != manifest.parent.name:
            ctx.issue(
                "warning",
                f"Dataset manifest directory does not match dataset_id {dataset_id!r}.",
                manifest,
            )

    if moved:
        load_documents(ctx)


def check_unknown_files(ctx: LintContext) -> None:
    if not ctx.root.exists():
        return
    root_allowed = HUB_ALLOWED if is_hub(ctx.root) else ROOT_ALLOWED
    for child in sorted(ctx.root.iterdir()):
        if child.name.startswith("."):
            continue
        if child.name not in root_allowed:
            handle_unknown(ctx, child, "Unexpected file or directory at wiki root.")

    scan_fixed_allowed(ctx, ctx.root / "raw", RAW_ALLOWED, "raw/")
    scan_fixed_allowed(ctx, ctx.root / "wiki", WIKI_ALLOWED, "wiki/")
    scan_fixed_allowed(ctx, ctx.root / "inventory", INVENTORY_ALLOWED, "inventory/")

    datasets = ctx.root / "datasets"
    if datasets.exists():
        for child in sorted(datasets.iterdir()):
            if child.name == "_index.md":
                continue
            if child.is_dir():
                for dataset_child in sorted(child.iterdir()):
                    if dataset_child.name not in DATASET_CHILD_ALLOWED:
                        handle_unknown(
                            ctx,
                            dataset_child,
                            f"Unexpected file or directory in datasets/{child.name}/.",
                        )
                for subdir_name in ["samples", "profiles", "queries"]:
                    subdir = child / subdir_name
                    if subdir.exists():
                        for note in sorted(subdir.iterdir()):
                            if note.name == "_index.md":
                                continue
                            if not note.is_file() or note.suffix != ".md":
                                handle_unknown(
                                    ctx,
                                    note,
                                    f"Unexpected file in datasets/{child.name}/{subdir_name}/.",
                                )
            else:
                handle_unknown(ctx, child, "Unexpected file in datasets/.")

    for base, allowed_dirs in [
        (ctx.root / "raw", {"articles", "papers", "repos", "notes", "data"}),
        (ctx.root / "wiki", {"concepts", "topics", "references", "theses"}),
        (ctx.root / "inventory", {"items", "candidates", "entities", "corpora", "views"}),
    ]:
        if not base.exists():
            continue
        for subdir in allowed_dirs:
            path = base / subdir
            if not path.exists():
                continue
            for child in sorted(path.iterdir()):
                if child.name in {"_index.md", ".backup", "images", ".images"} or child.name.startswith(".embeddings_cache"):
                    continue
                # Transient FileLock artifacts (e.g. add_concept.py's <slug>.md.lock)
                # may linger after a crash; ignore them rather than relocating.
                if child.suffix == ".lock" or child.name.endswith(".md.lock"):
                    continue
                if not child.is_file() or child.suffix != ".md":
                    handle_unknown(ctx, child, f"Unexpected file in {ctx.rel(path)}/.")


def scan_fixed_allowed(ctx: LintContext, directory: Path, allowed: set[str], label: str) -> None:
    if not directory.exists():
        return
    for child in sorted(directory.iterdir()):
        if child.name not in allowed:
            handle_unknown(ctx, child, f"Unexpected file or directory in {label}.")


def handle_unknown(ctx: LintContext, path: Path, message: str) -> None:
    if path.is_dir():
        ctx.issue("warning", f"{message} Unknown directories are not auto-fixed.", path)
        return
    if ctx.fix:
        unknown = ctx.root / "inbox" / ".unknown"
        unknown.mkdir(parents=True, exist_ok=True)
        dest = unique_destination(unknown / path.name)
        shutil.move(str(path), str(dest))
        ctx.issue("warning", f"Moved unexpected file to {ctx.rel(dest)}.", path, fixed=True)
        ctx.fixed(f"Moved {ctx.rel(path)} to {ctx.rel(dest)}.")
    else:
        ctx.issue("warning", message, path, fixable=True)


def unique_destination(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not choose unique destination for {path}")


def check_index_consistency(ctx: LintContext) -> None:
    known_roots = ["raw", "wiki", "inventory", "datasets", "output"]
    all_dirs: list[Path] = []
    for name in known_roots:
        base = ctx.root / name
        if base.exists():
            all_dirs.extend(p for p in base.rglob("*") if p.is_dir())
    for directory in sorted(all_dirs):
        if not is_index_checked_directory(ctx.root, directory):
            continue
        index = directory / "_index.md"
        if not index.exists():
            continue
        try:
            text = index.read_text(encoding="utf-8")
        except OSError as exc:
            ctx.issue("warning", f"Could not read index: {exc}", index)
            continue
        missing_files: list[Path] = []
        dead_links: list[str] = []
        for md_file in sorted(directory.glob("*.md")):
            if md_file.name == "_index.md":
                continue
            if md_file.name not in text:
                missing_files.append(md_file)
        for link in extract_markdown_links(text):
            if not is_local_markdown_link(link):
                continue
            target = resolve_link_target(directory, link, ctx.root)
            if not target.exists():
                dead_links.append(link)
        if ctx.fix and (missing_files or dead_links):
            regenerate_directory_index(ctx, directory)
            continue
        for md_file in missing_files:
            ctx.issue("warning", "Markdown file is missing from directory index.", md_file)
        for link in dead_links:
            ctx.issue("warning", f"Index links to missing file: {link}.", index)


def is_index_checked_directory(root: Path, directory: Path) -> bool:
    try:
        rel = directory.resolve().relative_to(root)
    except ValueError:
        return False
    if not rel.parts or any(part.startswith(".") for part in rel.parts):
        return False
    return rel.parts[0] in {"raw", "wiki", "inventory", "datasets", "output"}


def regenerate_directory_index(ctx: LintContext, directory: Path) -> None:
    index = directory / "_index.md"
    rows: list[str] = []
    for md_file in sorted(directory.glob("*.md")):
        if md_file.name == "_index.md":
            continue
        doc = ctx.documents.get(md_file.resolve())
        frontmatter = doc.frontmatter if doc else {}
        title = str(frontmatter.get("title") or md_file.stem)
        summary = str(frontmatter.get("summary") or "")
        tags = ", ".join(as_string_list(frontmatter.get("tags")))
        updated = str(
            frontmatter.get("updated")
            or frontmatter.get("ingested")
            or frontmatter.get("created")
            or ""
        )
        rows.append(
            f"| [{table_cell(title)}]({markdown_link_destination(md_file.name)}) | {table_cell(summary)} | {table_cell(tags)} | {table_cell(updated)} |"
        )

    title = index_title(directory)
    today = dt.date.today().isoformat()
    text = (
        f"# {title}\n\n"
        "> Generated by local magi lint.\n\n"
        f"Last updated: {today}\n\n"
        "## Contents\n\n"
        "| File | Summary | Tags | Updated |\n"
        "|------|---------|------|---------|\n"
        + "\n".join(rows)
        + ("\n" if rows else "")
    )
    index.write_text(text, encoding="utf-8")
    ctx.fixed(f"Regenerated index {ctx.rel(index)}.")


def index_title(directory: Path) -> str:
    name = directory.name
    if name == "wiki":
        return "Wiki Index"
    if name == "raw":
        return "Raw Index"
    return name.replace("-", " ").replace("_", " ").title() + " Index"


def markdown_link_destination(path: str) -> str:
    if any(char.isspace() for char in path) or ")" in path:
        return f"<{path}>"
    return path


def extract_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r"\]\((<([^>\n]+)>|([^)\n]+))\)", text):
        links.append(match.group(2) or match.group(3))
    return links


def is_local_markdown_link(link: str) -> bool:
    if "://" in link or link.startswith("mailto:"):
        return False
    target = link.split("#", 1)[0]
    return target.endswith(".md")


def resolve_link_target(base_dir: Path, link: str, root: Path | None = None) -> Path:
    target = link.split("#", 1)[0]
    if target.startswith("/"):
        resolved_root = root if root is not None else base_dir
        return (resolved_root / target.lstrip("/")).resolve()
    return (base_dir / target).resolve()


def check_links(ctx: LintContext) -> None:
    alias_map: dict[str, str] = {}
    for doc in ctx.documents.values():
        if doc.path.parent.name == "concepts":
            aliases = doc.frontmatter.get("aliases", [])
            if isinstance(aliases, list):
                for a in aliases:
                    alias_slug = str(a).lower().replace(" ", "_").replace("-", "_")
                    alias_map[alias_slug] = doc.path.name

    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] not in {"wiki", "inventory"}:
            continue
        full_text = doc.raw_text if doc.raw_text else doc.path.read_text(encoding="utf-8")
        modified = False
        for link in extract_markdown_links(full_text):
            is_external = "://" in link or link.startswith("mailto:")
            if " " in link and not is_external:
                if f"(<{link}>)" not in full_text and f"(<{link} " not in full_text:
                    ctx.issue("warning", f"Markdown link contains unescaped spaces: '{link}'. Consider URL encoding spaces (%20) or using Obsidian Wikilinks (![[...]]).", doc.path)
            if not is_local_markdown_link(link):
                continue
            target = resolve_link_target(doc.path.parent, link, ctx.root)
            if not target.exists():
                target_stem = target.stem
                if target_stem in alias_map:
                    new_target_name = alias_map[target_stem]
                    new_link = link.replace(target.name, new_target_name)
                    if ctx.fix:
                        full_text = full_text.replace(f"]({link})", f"]({new_link})")
                        full_text = full_text.replace(f"](<{link}>)", f"](<{new_link}>)")
                        ctx.issue("info", f"Auto-fixed markdown link {link} -> {new_link} via alias mapping.", doc.path, fixable=True, fixed=True)
                        modified = True
                        ctx.fixed(f"Auto-fixed markdown link {link} -> {new_link} in {doc.path.name}")
                    else:
                        ctx.issue("warning", f"Markdown link {link} can be auto-fixed to {new_link} via alias mapping (re-run with --fix).", doc.path)
                else:
                    ctx.issue("warning", f"Markdown link points to missing file: {link}.", doc.path)
        if modified:
            doc.path.write_text(full_text, encoding="utf-8")


def check_wikilinks_formatting(ctx: LintContext) -> None:
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] != "wiki":
            continue
        full_text = doc.raw_text if doc.raw_text else doc.path.read_text(encoding="utf-8", errors="replace")
        links = extract_wikilinks(full_text)
        for link in links:
            # Check for Windows illegal filename characters
            illegal_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
            has_illegal = any(c in link for c in illegal_chars)
            if has_illegal:
                ctx.issue("warning", f"Wikilink [[{link}]] contains Windows-illegal filename character(s). This will fail or crash on Windows.", doc.path)
                continue
            
            # Check for raw LaTeX equations or formula markers
            if link.startswith('$') or link.endswith('$') or '{' in link or '}' in link or ('\\' in link and any(kw in link for kw in ['int', 'sum', 'frac', 'partial', 'nabla'])):
                ctx.issue("warning", f"Wikilink [[{link}]] appears to contain a raw mathematical equation or LaTeX code instead of a clean conceptual term. This will lead to malformed filenames.", doc.path)


def check_math_syntax(ctx: LintContext) -> None:
    bin_dir = str(Path(__file__).parent.resolve())
    if bin_dir not in sys.path:
        sys.path.insert(0, bin_dir)
        
    try:
        from validate_math_latex import validate_math_pylatexenc, validate_math_pdflatex, format_issue_for_cli, HAS_PYLATEXENC
    except ImportError as e:
        ctx.issue("warning", f"Could not import validate_math_latex: {e}")
        return

    has_pdflatex = shutil.which("pdflatex") is not None

    cache_meta = ctx.cache_data.get("metadata", {})
    env_matches = (
        cache_meta.get("has_pdflatex") == has_pdflatex and
        cache_meta.get("has_pylatexenc") == HAS_PYLATEXENC
    )
    if not env_matches:
        ctx.cache_data["metadata"] = {
            "has_pdflatex": has_pdflatex,
            "has_pylatexenc": HAS_PYLATEXENC
        }
        ctx.cache_updated = True

    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        
        is_raw = rel.parts[0] == "raw"
        severity = "warning" if is_raw else "critical"
        rel_path_str = str(rel)

        math_issues = None
        if env_matches and rel_path_str in ctx.cache_data["files"]:
            cached = ctx.cache_data["files"][rel_path_str]
            try:
                stat = doc.path.stat()
                if cached.get("mtime") == stat.st_mtime and cached.get("size") == stat.st_size:
                    if "math_issues" in cached:
                        math_issues = cached["math_issues"]
            except Exception:
                pass

        if math_issues is None:
            full_text = doc.raw_text if doc.raw_text else doc.path.read_text(encoding="utf-8", errors="replace")
            
            math_issues, valid_blocks, valid_inlines = validate_math_pylatexenc(full_text)
            if has_pdflatex and (valid_blocks or valid_inlines):
                pdflatex_issues = validate_math_pdflatex(valid_blocks, valid_inlines)
                math_issues.extend(pdflatex_issues)

            if rel_path_str in ctx.cache_data["files"]:
                ctx.cache_data["files"][rel_path_str]["math_issues"] = math_issues
                ctx.cache_updated = True

        for issue in math_issues:
            formatted_msg = format_issue_for_cli(issue)
            ctx.issue(severity, formatted_msg, doc.path)




def check_source_provenance(ctx: LintContext) -> None:
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] == "wiki":
            sources = doc.frontmatter.get("sources")
            compiled_from = doc.frontmatter.get("compiled-from")
            if not sources and compiled_from not in {"conversation", "mixed"}:
                ctx.issue(
                    "warning",
                    "Compiled article is missing sources and has no compiled-from exemption.",
                    doc.path,
                )
                continue
            if sources:
                if not isinstance(sources, list):
                    ctx.issue("warning", "sources must be a list.", doc.path)
                    continue
                for source in sources:
                    if str(source).startswith(("http://", "https://")):
                        continue
                    resolved = resolve_source_ref(ctx, doc.path, str(source), wiki_source=True)
                    if resolved is None:
                        ctx.issue("warning", f"Source reference does not resolve: {source}.", doc.path)
                    elif is_under(resolved, ctx.root / "raw"):
                        ctx.referenced_raw.add(resolved.resolve())
        elif rel.parts[0] == "inventory":
            sources = doc.frontmatter.get("sources")
            if sources and isinstance(sources, list):
                for source in sources:
                    if str(source).startswith(("http://", "https://")):
                        continue
                    resolved = resolve_source_ref(ctx, doc.path, str(source), wiki_source=False)
                    if resolved is None:
                        ctx.issue(
                            "warning",
                            f"Inventory source reference does not resolve: {source}.",
                            doc.path,
                        )

        if "RETRACTED-SOURCE" in doc.body:
            ctx.issue("warning", "Retracted-source marker remains in the file body.", doc.path)


def fix_source_references(ctx: LintContext) -> None:
    if not ctx.fix:
        return
    changed = False
    for doc in sorted(ctx.documents.values(), key=lambda item: str(item.path)):
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] != "wiki":
            continue
        sources = doc.frontmatter.get("sources")
        if not isinstance(sources, list) or not sources:
            continue
        new_sources: list[str] = []
        doc_changed = False
        for source in sources:
            source_text = str(source)
            resolved = resolve_source_ref(ctx, doc.path, source_text, wiki_source=True)
            if resolved is not None and is_under(resolved, ctx.root / "raw"):
                canonical = ctx.rel(resolved)
                new_sources.append(canonical)
                if canonical != strip_matching_quotes(source_text.strip()):
                    doc_changed = True
            else:
                new_sources.append(source_text)
        if not doc_changed:
            continue
        text = doc.path.read_text(encoding="utf-8")
        parts = split_markdown_frontmatter(text)
        if parts is None:
            continue
        frontmatter, body = parts
        frontmatter = set_frontmatter_list(frontmatter, "sources", new_sources)
        write_markdown_frontmatter(doc.path, frontmatter, body)
        ctx.fixed(f"Rewrote source refs in {ctx.rel(doc.path)}.")
        changed = True
    if changed:
        load_documents(ctx)


def resolve_source_ref(ctx: LintContext, owner: Path, ref: str, wiki_source: bool) -> Path | None:
    ref = strip_matching_quotes(ref.strip())
    if ref.startswith(("http://", "https://")):
        return None if wiki_source else Path(ref)
    candidates: list[Path] = []
    ref_path = Path(ref)
    if ref_path.is_absolute():
        candidates.append(ref_path)
    elif ref.startswith(("../", "./")):
        candidates.append((owner.parent / ref).resolve())
    else:
        candidates.append((ctx.root / ref).resolve())
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    if wiki_source:
        slug = slugify(Path(ref).stem)

        # Reference-card fallback: sources are frequently given as a paper
        # title (exactly what `add-concept --source "<Title>"` writes) —
        # resolve against wiki cards by file slug, frontmatter title, or
        # aliases before falling back to raw/ scanning.
        card_matches: list[Path] = []
        for doc in ctx.documents.values():
            try:
                rel_doc = doc.path.resolve().relative_to(ctx.root)
            except ValueError:
                continue
            if rel_doc.parts[0] != "wiki" or doc.path.resolve() == owner.resolve():
                continue
            names = [doc.path.stem]
            title = doc.frontmatter.get("title")
            if title:
                names.append(str(title))
            aliases = doc.frontmatter.get("aliases")
            if isinstance(aliases, list):
                names.extend(str(a) for a in aliases)
            if any(slugify(str(n)) == slug for n in names if n):
                card_matches.append(doc.path.resolve())
        if len(card_matches) == 1:
            return card_matches[0]
        if len(card_matches) > 1:
            ctx.issue("warning", f"Source reference is ambiguous (matches multiple wiki cards): {ref}.", owner)
            return None

        exact_matches: list[Path] = []
        contains_matches: list[Path] = []
        for raw_file in content_markdown_files(ctx.root / "raw"):
            raw_slug = slugify(raw_file.stem)
            raw_slug_without_date = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", raw_slug)
            if slug in {raw_slug, raw_slug_without_date}:
                exact_matches.append(raw_file.resolve())
            elif len(slug) >= 8 and (
                slug in raw_slug_without_date or raw_slug_without_date in slug
            ):
                contains_matches.append(raw_file.resolve())
        if len(exact_matches) == 1:
            return exact_matches[0]
        if len(exact_matches) > 1:
            ctx.issue("warning", f"Source reference is ambiguous after slug fallback: {ref}.", owner)
            return None
        if len(contains_matches) == 1:
            return contains_matches[0]
        if len(contains_matches) > 1:
            ctx.issue("warning", f"Source reference is ambiguous after fuzzy slug fallback: {ref}.", owner)
            return None
    return None


def strip_matching_quotes(value: str) -> str:
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def slugify(value: str) -> str:
    value = value.lower().replace("_", "-")
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"[^\w-]", "", value, flags=re.UNICODE)
    value = re.sub(r"-+", "-", value).strip("-")
    return value


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def check_tags(ctx: LintContext) -> None:
    tag_locations: dict[str, list[Path]] = {}
    for doc in ctx.documents.values():
        tags = doc.frontmatter.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                tag_locations.setdefault(str(tag), []).append(doc.path)

    alias_groups = [
        {"ml", "machine-learning", "machinelearning"},
        {"ai", "artificial-intelligence", "artificialintelligence"},
        {"llm", "llms", "large-language-models"},
    ]
    present = set(tag_locations)
    for group in alias_groups:
        matches = sorted(group & present)
        if len(matches) > 1:
            ctx.issue("warning", f"Near-duplicate tags found: {', '.join(matches)}.")


def check_coverage(ctx: LintContext) -> None:
    unreferenced: list[Path] = []
    for raw_file in content_markdown_files(ctx.root / "raw"):
        doc = ctx.documents.get(raw_file.resolve())
        if doc and "collection-manifest" in as_string_list(doc.frontmatter.get("tags")):
            continue
        if raw_file.resolve() not in ctx.referenced_raw:
            unreferenced.append(raw_file)
    if ctx.fix and unreferenced:
        create_or_update_coverage_reference(ctx, unreferenced)
        return
    for raw_file in unreferenced:
        ctx.issue("suggestion", "Raw source is not referenced by any compiled article.", raw_file)


def create_or_update_coverage_reference(ctx: LintContext, unreferenced: list[Path]) -> None:
    references_dir = ctx.root / "wiki" / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = references_dir / "uncompiled-source-coverage.md"
    existing_sources: list[Path] = []
    existing_doc = ctx.documents.get(coverage_path.resolve())
    if existing_doc and isinstance(existing_doc.frontmatter.get("sources"), list):
        for source in existing_doc.frontmatter["sources"]:
            resolved = resolve_source_ref(ctx, coverage_path, str(source), wiki_source=True)
            if resolved is not None and is_under(resolved, ctx.root / "raw"):
                existing_sources.append(resolved)

    all_sources = sorted({path.resolve() for path in existing_sources + unreferenced})
    today = dt.date.today().isoformat()
    source_refs = [ctx.rel(path) for path in all_sources]
    rows: list[str] = []
    for raw_file in all_sources:
        doc = ctx.documents.get(raw_file.resolve())
        frontmatter = doc.frontmatter if doc else {}
        title = str(frontmatter.get("title") or raw_file.stem)
        summary = str(frontmatter.get("summary") or "")
        tags = ", ".join(as_string_list(frontmatter.get("tags")))
        rel_link = markdown_relative_link(references_dir, raw_file)
        rows.append(
            f"| [{table_cell(title)}]({rel_link}) | `{ctx.rel(raw_file)}` | {table_cell(summary)} | {table_cell(tags)} |"
        )

    text = "\n".join(
        [
            "---",
            'title: "Uncompiled Source Coverage"',
            "category: reference",
            "sources:",
            *[f"  - {source_ref}" for source_ref in source_refs],
            f"created: {today}",
            f"updated: {today}",
            f"verified: {today}",
            "tags: [coverage, uncompiled-sources, backlog, lint-repair]",
            "confidence: low",
            "volatility: warm",
            'summary: "Reference backlog for raw sources that existed in the wiki but were not yet referenced by compiled articles during lint repair."',
            "exclude_structure_check: true",
            "---",
            "",
            "# Uncompiled Source Coverage",
            "",
            "This reference page makes the remaining raw-source coverage gap explicit. These sources are now discoverable from the compiled wiki layer, but they have not all been fully synthesized into concept or topic articles. Treat this as a follow-up compilation backlog, not as evidence that every listed source has been integrated into surrounding articles.",
            "",
            "## Sources Needing Synthesis",
            "",
            "| Source | Path | Raw Summary | Tags |",
            "|--------|------|-------------|------|",
            *rows,
            "",
            "## Next Action",
            "",
            "Compile these sources selectively into existing articles when their claims materially change the wiki, then remove rows whose content is fully integrated elsewhere.",
            "",
        ]
    )
    coverage_path.write_text(text, encoding="utf-8")
    ctx.fixed(f"Updated coverage reference {ctx.rel(coverage_path)}.")
    for raw_file in all_sources:
        ctx.referenced_raw.add(raw_file.resolve())
    load_documents(ctx)
    regenerate_directory_index(ctx, references_dir)


def markdown_relative_link(base_dir: Path, target: Path) -> str:
    rel = os.path.relpath(target, base_dir)
    return markdown_link_destination(rel)


def table_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).replace("|", "\\|").strip()


def as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def check_freshness(ctx: LintContext) -> None:
    today = dt.date.today()
    thresholds = {"hot": 30, "warm": 180, "cold": 365}
    for doc in ctx.documents.values():
        try:
            rel = doc.path.resolve().relative_to(ctx.root)
        except ValueError:
            continue
        if rel.parts[0] != "wiki":
            continue
        volatility = doc.frontmatter.get("volatility")
        if volatility is None:
            ctx.issue("info", "Compiled article has no volatility field.", doc.path)
            continue
        if volatility not in thresholds:
            continue
        verified = doc.frontmatter.get("verified") or doc.frontmatter.get("updated")
        verified_date = parse_date(str(verified)) if verified else None
        if not verified_date:
            ctx.issue("warning", "Compiled article has no valid verified/updated date.", doc.path)
            continue
        age = (today - verified_date).days
        if age > thresholds[str(volatility)]:
            ctx.issue(
                "warning",
                f"Compiled article may be stale: {age} days since verification for {volatility} volatility.",
                doc.path,
            )


def parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError:
        return None


def check_projects(ctx: LintContext) -> None:
    projects = ctx.root / "output" / "projects"
    if not projects.exists():
        return
    for project in sorted(child for child in projects.iterdir() if child.is_dir()):
        why = project / "WHY.md"
        if not why.exists() or not why.read_text(encoding="utf-8", errors="replace").strip():
            ctx.issue("warning", "Project is missing a non-empty WHY.md.", project)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,39}", project.name) or re.search(
            r"\d{4}-\d{2}-\d{2}", project.name
        ):
            ctx.issue("warning", "Project slug should be lowercase, hyphen-separated, <=40 chars, no dates.", project)


def append_lint_log(ctx: LintContext) -> None:
    if not ctx.fix:
        return
    log = ctx.root / "log.md"
    if not log.exists():
        return
    counts = ctx.counts()
    today = dt.date.today().isoformat()
    entry = (
        f"\n## [{today}] lint | local command: "
        f"{counts['critical']} critical, {counts['warning']} warnings, "
        f"{counts['suggestion']} suggestions, {len(ctx.fixes)} auto-fixed\n"
    )
    with log.open("a", encoding="utf-8") as handle:
        handle.write(entry)


def get_home() -> Path:
    home_env = os.environ.get("HOME")
    if home_env:
        return Path(home_env)
    return get_home_directory()


def expand_leading_tilde(value: str) -> Path:
    if value == "~":
        return get_home_directory()
    if value.startswith("~/"):
        return get_home_directory() / value[2:]
    return Path(value)


def initialized_wiki_root(path: Path) -> bool:
    return (path / "_index.md").exists()


def resolve_hub(args: argparse.Namespace) -> Path:
    if args.hub:
        return expand_leading_tilde(str(args.hub))
    config = get_home_directory() / ".config" / "magi" / "config.json"
    if not config.exists():  # legacy pre-magi location
        config = get_home_directory() / ".config" / "llm-wiki" / "config.json"
    if config.exists():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
        except OSError as exc:
            if is_permission_denied(exc):
                raise SystemExit(permission_denied_message(config, "read hub config", exc)) from exc
            raise SystemExit(f"could not read hub config {config}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid hub config {config}: {exc}") from exc
        hub_path = data.get("hub_path")
        hub_candidate = expand_leading_tilde(str(hub_path)) if hub_path else None
        resolved_path = data.get("resolved_path")
        resolved_candidate = (
            expand_leading_tilde(str(resolved_path)) if resolved_path else None
        )

        if hub_candidate:
            # resolved_path is a convenience cache and may be stale when the
            # config is synced between machines. Prefer the portable hub_path
            # unless it is unavailable and the legacy cache clearly points at
            # an initialized hub.
            if hub_candidate.exists() or not (
                resolved_candidate and initialized_wiki_root(resolved_candidate)
            ):
                return hub_candidate
        if resolved_candidate:
            return resolved_candidate
    # No config entry: walk up from cwd so hub commands work from inside a
    # hub (or a topic under one) without --hub.
    from magi.core.workspace import find_hub_root

    found = find_hub_root()
    if found is not None:
        return found
    fallback = get_home_directory() / "wiki"
    return fallback


def resolve_registry_path(raw_path: str, hub: Path) -> Path:
    if raw_path in {".", "<HUB>", "HUB"}:
        return hub
    if raw_path.startswith("<HUB>/"):
        return hub / raw_path[len("<HUB>/") :]
    if raw_path.startswith("HUB/"):
        return hub / raw_path[len("HUB/") :]

    path = expand_leading_tilde(raw_path)
    if path.is_absolute():
        return path
    # Reject '..' traversal in relative paths
    if ".." in Path(raw_path).parts:
        raise SystemExit(f"registry path escapes hub (traversal not allowed): {raw_path}")
    candidate = hub / path
    if not is_under(candidate, hub):
        raise SystemExit(f"registry path escapes hub: {raw_path}")
    return candidate


def is_archived_registry_entry(entry: dict[str, Any] | None) -> bool:
    if not entry:
        return False
    status = str(entry.get("status") or "")
    path = str(entry.get("path") or "")
    return status == "archived" or path.startswith("topics/.archive/")


def validate_registry(data: Any, path: Path) -> None:
    """Validate wikis.json top-level schema. Raises SystemExit on corruption."""
    if not isinstance(data, dict):
        raise SystemExit(f"invalid registry {path}: root must be a JSON object")
    wikis = data.get("wikis")
    if wikis is not None and not isinstance(wikis, dict):
        raise SystemExit(f"invalid registry {path}: 'wikis' must be an object")
    for slug, entry in (wikis or {}).items():
        if not isinstance(entry, dict):
            raise SystemExit(f"invalid registry {path}: entry '{slug}' must be an object")
        status = entry.get("status")
        if status and status not in {"active", "archived"}:
            raise SystemExit(
                f"invalid registry {path}: entry '{slug}' has unknown status '{status}'"
            )


def read_registry(hub: Path) -> dict[str, Any]:
    registry = hub / "wikis.json"
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except OSError as exc:
        if is_permission_denied(exc):
            raise SystemExit(permission_denied_message(registry, "read wiki registry", exc)) from exc
        raise SystemExit(f"could not read wiki registry {registry}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid wiki registry {registry}: {exc}") from exc
    validate_registry(data, registry)
    return data


def write_registry(hub: Path, data: dict[str, Any]) -> None:
    registry = hub / "wikis.json"
    tmp = registry.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, registry)


def topic_entry(data: dict[str, Any], slug: str) -> dict[str, Any] | None:
    entry = data.get("wikis", {}).get(slug)
    return entry if isinstance(entry, dict) else None


def active_topic_path(hub: Path, slug: str, entry: dict[str, Any] | None = None) -> Path:
    if entry and entry.get("path") and not is_archived_registry_entry(entry):
        return resolve_registry_path(str(entry["path"]), hub)
    return hub / "topics" / slug


def archived_topic_path(hub: Path, slug: str, entry: dict[str, Any] | None = None) -> Path:
    if entry and entry.get("path") and is_archived_registry_entry(entry):
        return resolve_registry_path(str(entry["path"]), hub)
    return hub / "topics" / ".archive" / slug


def is_initialized_topic(path: Path) -> bool:
    return (path / "_index.md").exists() and (path / "config.md").exists()


def resolve_wiki_root(args: argparse.Namespace) -> Path:
    if args.path:
        return expand_leading_tilde(str(args.path))
    if args.local:
        return Path.cwd() / ".wiki"
    hub = resolve_hub(args)
    if args.wiki:
        registry = hub / "wikis.json"
        fallback_topic = hub / "topics" / args.wiki
        fallback_archived_topic = hub / "topics" / ".archive" / args.wiki
        include_archived = bool(getattr(args, "include_archived", False))
        if not registry.exists():
            if initialized_wiki_root(fallback_topic):
                return fallback_topic
            if initialized_wiki_root(fallback_archived_topic):
                if include_archived:
                    return fallback_archived_topic
                raise SystemExit(
                    f"wiki is archived: {args.wiki}. Use --include-archived or restore it first."
                )
            raise SystemExit(f"wiki registry not found: {registry}")
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except OSError as exc:
            if is_permission_denied(exc):
                raise SystemExit(permission_denied_message(registry, "read wiki registry", exc)) from exc
            if initialized_wiki_root(fallback_topic):
                return fallback_topic
            if initialized_wiki_root(fallback_archived_topic):
                if include_archived:
                    return fallback_archived_topic
                raise SystemExit(
                    f"wiki is archived: {args.wiki}. Use --include-archived or restore it first."
                )
            raise SystemExit(f"could not read wiki registry {registry}: {exc}") from exc
        except json.JSONDecodeError as exc:
            if initialized_wiki_root(fallback_topic):
                return fallback_topic
            if initialized_wiki_root(fallback_archived_topic):
                if include_archived:
                    return fallback_archived_topic
                raise SystemExit(
                    f"wiki is archived: {args.wiki}. Use --include-archived or restore it first."
                )
            raise SystemExit(f"invalid wiki registry {registry}: {exc}") from exc
        entry = data.get("wikis", {}).get(args.wiki)
        if not entry or not entry.get("path"):
            if initialized_wiki_root(fallback_topic):
                return fallback_topic
            if initialized_wiki_root(fallback_archived_topic):
                if include_archived:
                    return fallback_archived_topic
                raise SystemExit(
                    f"wiki is archived: {args.wiki}. Use --include-archived or restore it first."
                )
            raise SystemExit(f"wiki not found in registry: {args.wiki}")
        if is_archived_registry_entry(entry) and not include_archived:
            raise SystemExit(
                f"wiki is archived: {args.wiki}. Use --include-archived or restore it first."
            )
        registry_path = resolve_registry_path(str(entry["path"]), hub)
        if (
            not initialized_wiki_root(registry_path)
            and initialized_wiki_root(fallback_topic)
        ):
            return fallback_topic
        if (
            not initialized_wiki_root(registry_path)
            and include_archived
            and initialized_wiki_root(fallback_archived_topic)
        ):
            return fallback_archived_topic
        return registry_path
    cwd = Path.cwd()
    if (cwd / "wiki").is_dir() or is_initialized_topic(cwd):
        return cwd
    local = cwd / ".wiki"
    if local.exists():
        return local
    return hub


def run_lint(args: argparse.Namespace) -> int:
    root = resolve_wiki_root(args)
    ctx = LintContext(root, fix=args.fix)
    hub_root = is_hub(root)

    check_structure(ctx)
    check_unknown_files(ctx)
    if hub_root:
        append_lint_log(ctx)
        ctx.save_cache()
        if args.json:
            print_json_report(ctx)
        else:
            print_text_report(ctx)
        counts = ctx.counts()
        return 1 if counts["critical"] else 0  # PASS (even with warnings) exits 0

    load_documents(ctx)
    fix_legacy_wiki_frontmatter(ctx)
    check_frontmatter_schema(ctx)
    check_body_structure(ctx)
    check_canonical_placement(ctx)
    if ctx.fix:
        load_documents(ctx)  # Reload only when fix mode may have changed files
    fix_source_references(ctx)
    check_index_consistency(ctx)
    check_links(ctx)
    check_wikilinks_formatting(ctx)
    if not getattr(args, "skip_math", False):
        check_math_syntax(ctx)
    check_source_provenance(ctx)
    check_tags(ctx)
    check_coverage(ctx)
    check_freshness(ctx)
    check_projects(ctx)
    append_lint_log(ctx)
    ctx.save_cache()

    if args.json:
        print_json_report(ctx)
    else:
        print_text_report(ctx)

    counts = ctx.counts()
    return 1 if counts["critical"] else 0  # PASS (even with warnings) exits 0



def print_json_report(ctx: LintContext) -> None:
    counts = ctx.counts()
    report = {
        "root": str(ctx.root),
        "status": "pass"
        if not (counts["critical"] or counts["warning"] or counts["suggestion"])
        else "fail",
        "counts": counts,
        "fixes": ctx.fixes,
        "issues": [
            {
                "severity": issue.severity,
                "message": issue.message,
                "path": ctx.rel(issue.path) if issue.path else None,
                "fixable": issue.fixable,
            }
            for issue in sorted(ctx.active_issues(), key=lambda item: item.sort_key())
        ],
    }
    print(json.dumps(report, indent=2, sort_keys=True))


def print_text_report(ctx: LintContext) -> None:
    counts = ctx.counts()
    # Only criticals fail the run: researchers must be able to reach a green
    # verdict, or the lint gets ignored entirely. Warnings stay visible in
    # the summary as review items.
    failed = counts["critical"]
    print(f"magi lint: {ctx.root}")
    if ctx.fixes:
        print("\nAuto-fixed:")
        for fix in ctx.fixes:
            print(f"- {fix}")
    if any(counts[k] for k in ("critical", "warning", "suggestion", "info")):
        print("\nFindings:")
        for issue in sorted(ctx.active_issues(), key=lambda item: item.sort_key()):
            prefix = {
                "critical": "Critical",
                "warning": "Warning",
                "suggestion": "Suggestion",
                "info": "Info",
            }.get(issue.severity, issue.severity.title())
            location = f" ({ctx.rel(issue.path)})" if issue.path else ""
            fixable = " Run again with --fix to apply the safe fix." if issue.fixable and not ctx.fix else ""
            print(f"- {prefix}: {issue.message}{location}{fixable}")
    else:
        print("\nFindings: none")
    print(
        "\nSummary: "
        f"{counts['critical']} critical, {counts['warning']} warnings, "
        f"{counts['suggestion']} suggestions, {counts['info']} info, "
        f"{len(ctx.fixes)} auto-fixed."
    )
    verdict = "FAIL" if failed else "PASS"
    if not failed and (counts["warning"] or counts["suggestion"]):
        verdict += f" ({counts['warning']} warning(s) to review)"
    print("Result: " + verdict)

    # Math errors are the one class lint reports but cannot repair: an OCR'd
    # formula needs someone who can read it. Point at the tools that do.
    if any("[Block Math]" in i.message or "[Inline Math]" in i.message
           for i in ctx.active_issues()):
        print("\nBroken formulas need reading, not a --fix flag:")
        print("  magi math format                # the mechanical half, whole workspace")
        print("  magi math check --json          # the rest, as a worklist")
        print("  (the wiki_math_fix skill works that list one formula at a time)")


def append_log(path: Path, operation: str, message: str) -> None:
    log = path / "log.md"
    if not log.exists():
        return
    today = dt.date.today().isoformat()
    with log.open("a", encoding="utf-8") as handle:
        handle.write(f"\n## [{today}] {operation} | {message}\n")


def topic_title(path: Path, slug: str) -> str:
    config = path / "config.md"
    if config.exists():
        try:
            text = config.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'(?m)^title:\s*"?([^"\n]+)"?', text)
            if match:
                return match.group(1).strip()
        except OSError:
            pass
    return slug.replace("-", " ").title()


def write_hub_index(hub: Path, data: dict[str, Any]) -> None:
    today = dt.date.today().isoformat()
    active_rows: list[str] = []
    archived_count = 0
    for slug, entry in sorted(data.get("wikis", {}).items()):
        if slug == "hub":
            continue
        if not isinstance(entry, dict):
            continue
        if is_archived_registry_entry(entry):
            archived_count += 1
            continue
        raw_path = str(entry.get("path") or f"topics/{slug}")
        path = resolve_registry_path(raw_path, hub)
        title = topic_title(path, slug)
        description = str(entry.get("description") or "")
        active_rows.append(
            f"| [{table_cell(slug)}]({markdown_link_destination(raw_path)}) | {table_cell(title)} | {table_cell(description)} |"
        )

    text = "\n".join(
        [
            "# Wiki Hub Index",
            "",
            "> Registry of active topic wikis.",
            "",
            f"Last updated: {today}",
            "",
            "## Statistics",
            "",
            f"- Active topics: {len(active_rows)}",
            f"- Archived topics: {archived_count}",
            "",
            "## Topic Wikis",
            "",
            "| Wiki | Title | Description |",
            "|------|-------|-------------|",
            *active_rows,
            "",
            "## Archive",
            "",
            f"Archived topics are preserved under `topics/.archive/`: {archived_count}",
            "",
        ]
    )
    (hub / "_index.md").write_text(text, encoding="utf-8")


def ensure_hub_for_archive(hub: Path) -> dict[str, Any]:
    if not (hub / "wikis.json").exists() or not (hub / "topics").exists():
        raise SystemExit(
            f"initialized hub not found: {hub} "
            "(pass --hub <path> to target a specific hub)"
        )
    return read_registry(hub)


def run_archive(args: argparse.Namespace) -> int:
    hub = resolve_hub(args)
    data = ensure_hub_for_archive(hub)
    subcommand = args.archive_command
    if subcommand == "list":
        return archive_list(hub, data, include_archived=args.archived, json_output=args.json)
    if subcommand == "topic":
        return archive_topic(hub, data, args.slug, args.reason)
    if subcommand == "restore":
        return restore_topic(hub, data, args.slug)
    if subcommand == "register":
        return register_topic(hub, data, args.slug, args.path, args.description)
    raise SystemExit("unknown archive subcommand")


def archive_list(
    hub: Path,
    data: dict[str, Any],
    include_archived: bool,
    json_output: bool = False,
) -> int:
    active: list[dict[str, str]] = []
    archived: list[dict[str, str]] = []
    for slug, entry in sorted(data.get("wikis", {}).items()):
        if slug == "hub" or not isinstance(entry, dict):
            continue
        path_text = str(entry.get("path") or f"topics/{slug}")
        row = {
            "slug": slug,
            "path": path_text,
            "description": str(entry.get("description") or ""),
            "archived": str(entry.get("archived") or ""),
            "reason": str(entry.get("archive_reason") or ""),
        }
        if is_archived_registry_entry(entry):
            archived.append(row)
        else:
            active.append(row)

    archive_dir = hub / "topics" / ".archive"
    if archive_dir.exists():
        registered = {row["slug"] for row in archived}
        for topic in sorted(child for child in archive_dir.iterdir() if child.is_dir()):
            if topic.name not in registered and initialized_wiki_root(topic):
                archived.append(
                    {
                        "slug": topic.name,
                        "path": f"topics/.archive/{topic.name}",
                        "description": "(missing from registry)",
                        "archived": "",
                        "reason": "registry repair needed",
                    }
                )

    topics_dir = hub / "topics"
    if topics_dir.exists():
        registered_active = {row["slug"] for row in active}
        for topic in sorted(child for child in topics_dir.iterdir() if child.is_dir()):
            if topic.name == ".archive":
                continue
            if topic.name not in registered_active and initialized_wiki_root(topic):
                active.append(
                    {
                        "slug": topic.name,
                        "path": f"topics/{topic.name}",
                        "description": "(missing from registry — run `archive register`)",
                        "archived": "",
                        "reason": "registry repair needed",
                    }
                )

    if json_output:
        print(json.dumps({"hub": str(hub), "active": active, "archived": archived}, indent=2))
        return 0

    print(f"magi hub: {hub}")
    print(f"\nActive topics ({len(active)})")
    print("| Slug | Path | Description |")
    print("|------|------|-------------|")
    for row in active:
        print(f"| {row['slug']} | {row['path']} | {table_cell(row['description'])} |")
    print(f"\nArchived topics: {len(archived)}")
    if include_archived:
        print("\nArchived topics")
        print("| Slug | Path | Archived | Reason |")
        print("|------|------|----------|--------|")
        for row in archived:
            print(
                f"| {row['slug']} | {row['path']} | {row['archived']} | {table_cell(row['reason'])} |"
            )
    elif archived:
        print("Run `magi hub list --archived` to show archived topics.")
    return 0


def archive_topic(hub: Path, data: dict[str, Any], slug: str, reason: str | None) -> int:
    if slug == "hub":
        raise SystemExit("cannot archive the synthetic hub entry")
    if slug in {".", ".."} or "/" in slug or os.sep in slug or "\\" in slug or slug.startswith("."):
        raise SystemExit(f"invalid topic slug: {slug}")
    entry = topic_entry(data, slug)
    source = active_topic_path(hub, slug, entry)
    fallback_source = hub / "topics" / slug
    if not initialized_wiki_root(source) and initialized_wiki_root(fallback_source):
        source = fallback_source
    if entry and is_archived_registry_entry(entry):
        raise SystemExit(f"topic already archived: {slug}")
    if not initialized_wiki_root(source):
        raise SystemExit(f"active topic not found: {source}")
    archive_dir = hub / "topics" / ".archive"
    dest = archive_dir / slug
    if not is_under(source, hub / "topics") or not is_under(dest, hub / "topics"):
        raise SystemExit(f"path escapes topics directory — refusing to archive: {slug}")
    if dest.exists():
        raise SystemExit(f"archive destination already exists: {dest}")

    wikis = data.setdefault("wikis", {})
    if not isinstance(wikis, dict):
        raise SystemExit("invalid registry: wikis must be an object")

    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))

    entry = wikis.setdefault(slug, {})
    if not isinstance(entry, dict):
        entry = {}
        wikis[slug] = entry
    entry.setdefault("description", topic_title(dest, slug))
    entry["path"] = f"topics/.archive/{slug}"
    entry["status"] = "archived"
    entry["archived"] = dt.date.today().isoformat()
    if reason:
        entry["archive_reason"] = reason
    write_registry(hub, data)
    write_hub_index(hub, data)
    append_log(hub, "archive", f"archived topic {slug}")
    append_log(dest, "archive", f"archived topic {slug}")
    print(f"Archived topic `{slug}`")
    print(f"Old path: {source}")
    print(f"New path: {dest}")
    print(f"Restore with: magi hub restore {slug} --hub {hub}")
    return 0


def restore_topic(hub: Path, data: dict[str, Any], slug: str) -> int:
    if slug == "hub":
        raise SystemExit("cannot restore the synthetic hub entry")
    entry = topic_entry(data, slug)
    source = archived_topic_path(hub, slug, entry)
    fallback_source = hub / "topics" / ".archive" / slug
    if not initialized_wiki_root(source) and initialized_wiki_root(fallback_source):
        source = fallback_source
    dest = hub / "topics" / slug
    if dest.exists():
        raise SystemExit(f"active topic destination already exists: {dest}")
    if not initialized_wiki_root(source):
        raise SystemExit(f"archived topic not found: {source}")

    wikis = data.setdefault("wikis", {})
    if not isinstance(wikis, dict):
        raise SystemExit("invalid registry: wikis must be an object")

    shutil.move(str(source), str(dest))

    entry = wikis.setdefault(slug, {})
    if not isinstance(entry, dict):
        entry = {}
        wikis[slug] = entry
    entry.setdefault("description", topic_title(dest, slug))
    entry["path"] = f"topics/{slug}"
    entry["status"] = "active"
    entry.pop("archived", None)
    entry.pop("archive_reason", None)
    entry["restored"] = dt.date.today().isoformat()
    write_registry(hub, data)
    write_hub_index(hub, data)
    append_log(hub, "archive", f"restored topic {slug}")
    append_log(dest, "archive", f"restored topic {slug}")
    print(f"Restored topic `{slug}`")
    print(f"Path: {dest}")
    return 0


def register_topic(
    hub: Path,
    data: dict[str, Any],
    slug: str,
    path: str | None,
    description: str | None,
) -> int:
    if slug == "hub":
        raise SystemExit("cannot register the synthetic hub entry")
    rel_path = path or f"topics/{slug}"
    target = resolve_registry_path(rel_path, hub)
    if not initialized_wiki_root(target):
        raise SystemExit(f"topic not initialized (no _index.md): {target}")

    wikis = data.setdefault("wikis", {})
    if not isinstance(wikis, dict):
        raise SystemExit("invalid registry: wikis must be an object")

    entry = wikis.setdefault(slug, {})
    if not isinstance(entry, dict):
        entry = {}
        wikis[slug] = entry
    existed = bool(entry.get("path")) and not is_archived_registry_entry(entry)
    entry["description"] = description or entry.get("description") or topic_title(target, slug)
    entry["path"] = rel_path
    entry["status"] = "active"
    entry.pop("archived", None)
    entry.pop("archive_reason", None)
    write_registry(hub, data)
    write_hub_index(hub, data)
    append_log(hub, "register", f"registered topic {slug}")
    append_log(target, "register", f"registered topic {slug}")
    print(f"{'Updated' if existed else 'Registered'} topic `{slug}` -> {rel_path}")
    return 0


def extract_wikilinks(text: str) -> list[str]:
    """Extract all [[Concept]] and [[Concept|Alias]] wikilinks from text."""
    return re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)


def run_stats(args: argparse.Namespace) -> int:
    root = resolve_wiki_root(args)
    subcmd = args.stats_command

    if subcmd == "concept-density":
        target = (root / args.file).resolve()
        if not target.exists():
            raise SystemExit(f"file not found: {target}")
        text = target.read_text(encoding="utf-8")
        parts = split_markdown_frontmatter(text)
        body = parts[1] if parts else text
        links = extract_wikilinks(body)
        body_clean = body
        # Strip block math $$ ... $$
        body_clean = re.sub(r'\$\$.*?\$\$', '', body_clean, flags=re.DOTALL)
        # Strip inline math $ ... $
        body_clean = re.sub(r'(?<!\\)\$.*?(?<!\\)\$', '', body_clean)
        # Strip standard LaTeX environments \begin{...} ... \end{...}
        body_clean = re.sub(r'\\begin\{.*?\}.*?\\end\{.*?\}', '', body_clean, flags=re.DOTALL)
        
        words = len(body_clean.split())
        density = round(len(links) / max(words, 1) * 1000, 2)
        report = {
            "file": str(target),
            "total_wikilinks": len(links),
            "unique_concepts": sorted(set(links)),
            "word_count": words,
            "density_per_1k_words": density,
        }
        print(json.dumps(report, indent=2))
        return 0

    if subcmd == "verify-refs":
        target = (root / args.file).resolve()
        if not target.exists():
            raise SystemExit(f"file not found: {target}")
        text = target.read_text(encoding="utf-8")
        parts = split_markdown_frontmatter(text)
        body = parts[1] if parts else text
        links = sorted(set(extract_wikilinks(body)))
        concepts_dir = root / "wiki" / "concepts"
        refs_dir = root / "wiki" / "references"
        valid: list[str] = []
        dangling: list[str] = []
        for link in links:
            slug_snake = link.replace(" ", "_")
            slug_kebab = slugify(link)
            candidates = [
                concepts_dir / f"{slug_kebab}.md",
                concepts_dir / f"{slug_snake}.md",
                concepts_dir / f"{link}.md",
                refs_dir / f"{slug_kebab}.md",
                refs_dir / f"{slug_snake}.md",
                refs_dir / f"{link}.md",
            ]
            if any(c.exists() for c in candidates):
                valid.append(link)
            else:
                dangling.append(link)
        report = {
            "file": str(target),
            "valid_refs": valid,
            "dangling_refs": dangling,
            "dangling_count": len(dangling),
        }
        print(json.dumps(report, indent=2))
        return 0

    if subcmd == "wiki-summary":
        wiki_dir = root / "wiki"
        if not wiki_dir.exists():
            raise SystemExit(f"wiki directory not found: {wiki_dir}")
        dir_counts: dict[str, int] = {}
        total_files = 0
        files_without_sources = 0
        total_wikilinks = 0
        file_list: list[dict[str, Any]] = []
        for md_file in sorted(wiki_dir.rglob("*.md")):
            if md_file.name == "_index.md" or ".backup" in md_file.parts:
                continue
            try:
                rel = md_file.relative_to(wiki_dir)
            except ValueError:
                continue
            subdir = str(rel.parts[0]) if len(rel.parts) > 1 else "."
            dir_counts[subdir] = dir_counts.get(subdir, 0) + 1
            total_files += 1
            try:
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            links = extract_wikilinks(text)
            total_wikilinks += len(links)
            parts = split_markdown_frontmatter(text)
            fm = parse_frontmatter_block(parts[0]) if parts else {}
            sources = fm.get("sources")
            if not sources:
                files_without_sources += 1
            file_list.append({
                "path": str(rel),
                "wikilinks": len(links),
                "has_sources": bool(sources),
                "title": str(fm.get("title") or md_file.stem),
            })
        report = {
            "wiki_root": str(root),
            "total_files": total_files,
            "directory_counts": dir_counts,
            "files_without_sources": files_without_sources,
            "total_wikilinks": total_wikilinks,
            "avg_density": round(total_wikilinks / max(total_files, 1), 1),
            "files": file_list,
        }
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
            return 0
        # Default to the summary a person asked for. This used to print the
        # whole per-file array — 759 lines on a 124-card library — into the
        # WebUI's terminal, where the six numbers anyone wanted scrolled off
        # the top instantly. `--json` still gives the full structure.
        print(f"wiki: {total_files} cards in {root}")
        for name, count in sorted(dir_counts.items(), key=lambda kv: -kv[1]):
            print(f"  {name:<14} {count}")
        print(f"wikilinks: {total_wikilinks} total · {report['avg_density']} per card")
        if files_without_sources:
            print(f"cards with no `sources:` in frontmatter: {files_without_sources}")
            worst = [f for f in file_list if not f["has_sources"]][:10]
            for f in worst:
                print(f"  {f['path']}")
            if files_without_sources > len(worst):
                print(f"  … and {files_without_sources - len(worst)} more "
                      f"(run with --json for the full list)")
        else:
            print("every card cites at least one source")
        return 0

    raise SystemExit(f"unknown stats subcommand: {subcmd}")


def run_graph(args: argparse.Namespace) -> int:
    root = resolve_wiki_root(args)
    wiki_dir = root / "wiki"
    if not wiki_dir.exists():
        raise SystemExit(f"wiki directory not found: {wiki_dir}")
    
    output_dir = root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    db_path = output_dir / "graph.db"
    
    print(f"magi graph: building index at {db_path}...")
    
    with sqlite3.connect(str(db_path), timeout=30.0) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA busy_timeout = 30000")
        # WAL, matching index.db: the dashboard and `magi graph query` read
        # this file while a build may be writing it, and in the default
        # rollback-journal mode a writer blocks every reader for the whole
        # build. The setting is persistent, so this also upgrades existing dbs.
        cursor.execute("PRAGMA journal_mode = WAL")
        
        # Create tables
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY,
            path TEXT,
            title TEXT,
            type TEXT,
            category TEXT,
            summary TEXT,
            created TEXT,
            updated TEXT
        );
        CREATE TABLE IF NOT EXISTS edges (
            source_id TEXT,
            target_id TEXT,
            type TEXT,
            UNIQUE(source_id, target_id, type)
        );
        CREATE TABLE IF NOT EXISTS tags (
            node_id TEXT,
            tag TEXT,
            UNIQUE(node_id, tag)
        );
        CREATE TABLE IF NOT EXISTS aliases (
            node_id TEXT,
            alias TEXT,
            UNIQUE(node_id, alias)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            doc_id TEXT,
            text TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS evidence (
            claim_id TEXT,
            source_type TEXT,
            source TEXT,
            quote TEXT,
            UNIQUE(claim_id, source_type, source, quote)
        );
        """)

        # Clear existing data to do a full rebuild
        cursor.executescript("""
        DELETE FROM nodes;
        DELETE FROM edges;
        DELETE FROM tags;
        DELETE FROM aliases;
        DELETE FROM claims;
        DELETE FROM evidence;
        """)
        
        # Collect all data for batch insert
        node_rows: list[tuple] = []
        edge_rows: list[tuple] = []
        tag_rows: list[tuple] = []
        alias_rows: list[tuple] = []
        claim_rows: list[tuple] = []
        evidence_rows: list[tuple] = []
        # Raw [[wikilink]] references, resolved to node ids after the scan
        # so links to files parsed later in the walk still resolve.
        wikilink_refs: list[tuple[str, str]] = []
        link_resolution: dict[str, str] = {}

        def link_key(text: str) -> str:
            return text.strip().lower().replace("_", " ")


        for md_file in sorted(wiki_dir.rglob("*.md")):
            if md_file.name == "_index.md" or ".backup" in md_file.parts:
                continue
                
            try:
                rel = md_file.relative_to(root)
                text = md_file.read_text(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                continue
                
            parts = split_markdown_frontmatter(text)
            fm = parse_frontmatter_block(parts[0]) if parts else {}
            body = parts[1] if parts else text
            
            # Use relative path as node_id to avoid collisions across subdirectories
            node_id = str(rel).replace("\\", "/").removesuffix(".md")
            title = str(fm.get("title") or md_file.stem)
            node_type = str(fm.get("type") or "")
            if not node_type:
                # Fall back to the containing directory so concept/reference
                # nodes get a non-empty `type` even when frontmatter omits it.
                # Use the singular canonical form so it lines up with `category`
                # (e.g. concepts/foo.md -> "concept"). Frontmatter still wins.
                parent_name = md_file.parent.name
                node_type = {
                    "concepts": "concept",
                    "references": "reference",
                    "theses": "thesis",
                    "topics": "topic",
                }.get(parent_name, parent_name)
            category = str(fm.get("category") or "")
            if not category:
                # Fall back to the containing wiki subdir so `category`
                # filters documented for wiki_ask keep working when the
                # frontmatter omits the field.
                category = {
                    "concepts": "concept",
                    "references": "reference",
                    "theses": "thesis",
                    "topics": "topic",
                }.get(md_file.parent.name, "")
            summary = str(fm.get("summary") or "")
            created = str(fm.get("created") or "")
            updated = str(fm.get("updated") or "")
            
            node_rows.append((node_id, str(rel).replace("\\", "/"), title, node_type, category, summary, created, updated))

            # Map title, file stem, and aliases to this node id so wikilink
            # edges can be resolved to real node ids (first file wins).
            link_resolution.setdefault(link_key(title), node_id)
            link_resolution.setdefault(link_key(md_file.stem), node_id)

            tags = fm.get("tags")
            if isinstance(tags, list):
                for tag in tags:
                    tag_rows.append((node_id, str(tag)))

            aliases = fm.get("aliases")
            if isinstance(aliases, list):
                for alias in aliases:
                    alias_rows.append((node_id, str(alias)))
                    link_resolution.setdefault(link_key(str(alias)), node_id)

            links = extract_wikilinks(body)
            for link in links:
                wikilink_refs.append((node_id, link))

            # Provenance: parse <!-- magi:claims ... --> blocks into
            # first-class claim nodes with has_claim / supported_by edges.
            for claims_block in re.findall(r"<!--\s*magi:claims\s*\n(.*?)-->", body, re.DOTALL):
                from magi.kb.verify_claims import parse_blocks as parse_claim_blocks

                for cb in parse_claim_blocks(claims_block):
                    claim_text = cb.get("claim")
                    if not claim_text:
                        continue
                    claim_id = "claim:" + hashlib.sha1(
                        f"{node_id}|{claim_text}".encode("utf-8")).hexdigest()[:12]
                    status = (cb.get("status") or "unverified").lower()
                    claim_rows.append((claim_id, node_id, claim_text, status))
                    node_rows.append((claim_id, str(rel).replace("\\", "/"), claim_text[:120],
                                      "claim", "claim", claim_text, "", ""))
                    edge_rows.append((node_id, claim_id, "has_claim"))
                    src_type = (cb.get("source_type") or "").lower()
                    src = cb.get("source") or ""
                    quote = cb.get("evidence") or ""
                    if src:
                        evidence_rows.append((claim_id, src_type, src, quote))
                        if src_type == "local_wiki":
                            src_node = src.replace("\\", "/").removesuffix(".md")
                            edge_rows.append((claim_id, src_node, "supported_by"))

        # Resolve wikilink targets to node ids; unresolved links keep the
        # raw link text as a dangling-edge marker.
        for source_id, link in wikilink_refs:
            edge_rows.append((source_id, link_resolution.get(link_key(link), link), "wikilink"))

        # Batch insert for performance
        cursor.executemany(
            "INSERT OR REPLACE INTO nodes (id, path, title, type, category, summary, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            node_rows
        )
        cursor.executemany("INSERT OR IGNORE INTO tags (node_id, tag) VALUES (?, ?)", tag_rows)
        cursor.executemany("INSERT OR IGNORE INTO aliases (node_id, alias) VALUES (?, ?)", alias_rows)
        cursor.executemany("INSERT OR IGNORE INTO edges (source_id, target_id, type) VALUES (?, ?, ?)", edge_rows)
        cursor.executemany(
            "INSERT OR REPLACE INTO claims (id, doc_id, text, status) VALUES (?, ?, ?, ?)",
            claim_rows)
        cursor.executemany(
            "INSERT OR IGNORE INTO evidence (claim_id, source_type, source, quote) VALUES (?, ?, ?, ?)",
            evidence_rows)
        
        # Insert tags as nodes and create has_tag edges
        cursor.executescript("""
        INSERT OR REPLACE INTO nodes (id, path, title, type, category, summary, created, updated)
        SELECT 'tag:' || tag, '', tag, 'tag', 'tag', '', '', ''
        FROM tags GROUP BY tag;
        
        INSERT OR IGNORE INTO edges (source_id, target_id, type)
        SELECT node_id, 'tag:' || tag, 'has_tag'
        FROM tags;
        """)
        
        conn.commit()
    
    print(f"Indexed {len(node_rows)} nodes and {len(edge_rows)} edges"
          + (f" ({len(claim_rows)} claims)." if claim_rows else "."))
    return 0


def run_map(args: argparse.Namespace) -> int:
    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Path not found: {args.target}")
        return 1
        
    if target.is_file():
        try:
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            print(f"Error reading file: {e}")
            return 1
            
        lines = content.splitlines()
        total_lines = len(lines)
        
        fm_start = -1
        fm_end = -1
        if lines and lines[0].strip() == "---":
            fm_start = 1
            for idx in range(1, len(lines)):
                if lines[idx].strip() == "---":
                    fm_end = idx + 1
                    break
                    
        headings = []
        for idx, line in enumerate(lines):
            match = re.match(r'^(#{1,6})\s+(.*)', line.strip())
            if match:
                level = len(match.group(1))
                text = match.group(2).strip()
                headings.append((idx + 1, level, text))
                
        sections = []
        current_line = 1
        if fm_start != -1 and fm_end != -1:
            sections.append((fm_start, fm_end, "--- (frontmatter)"))
            current_line = fm_end + 1
            
        for i, (line_num, level, text) in enumerate(headings):
            if sections:
                prev_start, prev_end, prev_name = sections[-1]
                if prev_end == -1:
                    sections[-1] = (prev_start, line_num - 1, prev_name)
            sections.append((line_num, -1, f"{'#' * level} {text}"))
            
        if sections:
            prev_start, prev_end, prev_name = sections[-1]
            if prev_end == -1:
                sections[-1] = (prev_start, total_lines, prev_name)
                
        block_math_count = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))
        inline_math_count = len(re.findall(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', content, re.DOTALL))
        
        print(f"Map: {target.name} ({total_lines} lines)")
        for start, end, name in sections:
            print(f"  [L{start}-{end}]".ljust(13) + f"{name}")
        print(f"  Math blocks: {block_math_count} (block), {inline_math_count} (inline)")
        return 0
        
    elif target.is_dir():
        print(f"Directory Map: {target}")
        print(f"{'File':<65} | {'Lines':<6} | {'Sections':<8} | {'Block Math':<10} | {'Inline Math':<11}")
        print("-" * 110)
        
        for root, dirs, files in os.walk(target):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            for file in sorted(files):
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    try:
                        rel_path = Path(file_path).relative_to(target.parent)
                    except ValueError:
                        rel_path = Path(file_path)
                        
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                    except OSError:
                        continue
                        
                    lines = content.splitlines()
                    total_lines = len(lines)
                    
                    headings_count = 0
                    for line in lines:
                        if line.strip().startswith('#'):
                            if re.match(r'^#{1,6}\s+', line.strip()):
                                headings_count += 1
                                
                    fm_exists = lines and lines[0].strip() == "---"
                    sections_count = headings_count + (1 if fm_exists else 0)
                    
                    block_math_count = len(re.findall(r'\$\$(.*?)\$\$', content, re.DOTALL))
                    inline_math_count = len(re.findall(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', content, re.DOTALL))
                    
                    print(f"{str(rel_path).replace(os.sep, '/'):<65} | {total_lines:<6} | {sections_count:<8} | {block_math_count:<10} | {inline_math_count:<11}")
        return 0
    return 1



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="magi",
        description="Local deterministic helpers for magi.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    lint = subparsers.add_parser(
        "lint",
        help="Run local structural checks on a wiki root.",
        description=(
            "Run deterministic checks that do not require an LLM. Pass a wiki root "
            "path, or use --local/--wiki to resolve one through the normal hub rules."
        ),
    )
    lint.add_argument("path", nargs="?", help="Wiki root path to lint.")
    lint.add_argument("--fix", action="store_true", help="Apply unambiguous structural fixes.")
    lint.add_argument("--local", action="store_true", help="Lint .wiki/ in the current directory.")
    lint.add_argument("--wiki", help="Named wiki from the hub registry.")
    lint.add_argument("--hub", help="Override hub path for --wiki resolution.")
    lint.add_argument(
        "--include-archived",
        action="store_true",
        help="Allow linting an explicitly targeted archived wiki.",
    )
    lint.add_argument("--json", action="store_true", help="Print a machine-readable JSON report.")
    lint.add_argument("--skip-math", action="store_true", help="Skip LaTeX/math syntax checks.")
    lint.set_defaults(func=run_lint)

    archive = subparsers.add_parser(
        "archive",
        prog="magi hub",
        help="Archive, restore, or list hub topic wikis.",
        description=(
            "Move whole topic wikis between topics/<slug> and topics/.archive/<slug>, "
            "updating wikis.json so archived topics stay out of default context."
        ),
    )
    # NOTE: --hub deliberately lives ONLY on the leaf subparsers below. A
    # parent-level --hub would be silently clobbered by the leaf's None
    # default (argparse namespace behavior, verified on py3.10), so the
    # old "archive --hub X list" form now fails loudly instead of
    # operating on the wrong hub.
    archive_sub = archive.add_subparsers(dest="archive_command", required=True)

    archive_list_parser = archive_sub.add_parser(
        "list", prog="magi hub list", help="List active and archived topics."
    )
    # --hub is accepted on each leaf too: the magi dispatcher rewrites
    # "magi hub list --hub X" to "archive list --hub X", where the
    # parent-level flag is no longer reachable.
    archive_list_parser.add_argument("--hub", help="Override hub path.")
    archive_list_parser.add_argument(
        "--archived",
        action="store_true",
        help="Show archived topics in addition to active topics.",
    )
    archive_list_parser.add_argument("--json", action="store_true", help="Print JSON.")

    archive_topic_parser = archive_sub.add_parser(
        "topic", prog="magi hub archive", help="Archive an active topic wiki."
    )
    archive_topic_parser.add_argument("slug", help="Topic slug to archive.")
    archive_topic_parser.add_argument("--reason", help="Optional archive reason.")
    archive_topic_parser.add_argument("--hub", help="Override hub path.")

    archive_restore_parser = archive_sub.add_parser(
        "restore", prog="magi hub restore", help="Restore an archived topic wiki."
    )
    archive_restore_parser.add_argument("slug", help="Topic slug to restore.")
    archive_restore_parser.add_argument("--hub", help="Override hub path.")

    archive_register_parser = archive_sub.add_parser(
        "register",
        prog="magi hub register",
        help="Register an existing active topic in the hub registry (idempotent).",
    )
    archive_register_parser.add_argument("slug", help="Topic slug to register.")
    archive_register_parser.add_argument(
        "--path",
        help="Registry-relative path to the topic (default: topics/<slug>).",
    )
    archive_register_parser.add_argument("--description", help="Optional topic description.")
    archive_register_parser.add_argument("--hub", help="Override hub path.")

    archive.set_defaults(func=run_archive)

    stats = subparsers.add_parser(
        "stats",
        help="Deterministic wiki statistics and verification.",
        description=(
            "Compute concept-link density, verify wikilink targets, "
            "or produce a structural summary of the wiki directory."
        ),
    )
    stats.add_argument("--local", action="store_true", help="Use .wiki/ in the current directory.")
    stats.add_argument("--wiki", help="Named wiki from the hub registry.")
    stats.add_argument("--hub", help="Override hub path.")
    stats.add_argument("path", nargs="?", help="Wiki root path.")
    stats_sub = stats.add_subparsers(dest="stats_command", required=True)

    stats_density = stats_sub.add_parser(
        "concept-density",
        help="Count [[wikilinks]] in a file and report density.",
    )
    stats_density.add_argument("file", help="Markdown file to analyze.")

    stats_verify = stats_sub.add_parser(
        "verify-refs",
        help="Check that [[wikilink]] targets exist as files.",
    )
    stats_verify.add_argument("file", help="Markdown file to check.")

    stats_summary = stats_sub.add_parser(
        "wiki-summary",
        help="Produce a structural summary of the wiki directory.",
    )
    stats_summary.add_argument(
        "--json", action="store_true",
        help="Full machine-readable report including the per-file array")

    stats.set_defaults(func=run_stats)

    graph = subparsers.add_parser(
        "graph",
        help="Extract a SQLite knowledge graph from the wiki.",
        description=(
            "Parse [[wikilinks]], tags, and aliases from the wiki/ folder "
            "and build an AI-friendly SQLite graph database in output/graph.db."
        ),
    )
    graph.add_argument("--local", action="store_true", help="Use .wiki/ in the current directory.")
    graph.add_argument("--wiki", help="Named wiki from the hub registry.")
    graph.add_argument("--hub", help="Override hub path.")
    graph.add_argument("path", nargs="?", help="Wiki root path.")
    graph.set_defaults(func=run_graph)

    map_parser = subparsers.add_parser(
        "map",
        help="Produce a structural map of headings and math blocks for a file or directory.",
        description=(
            "Generate a table of heading line ranges and math block counts for a single file, "
            "or a compact summary for all markdown files under a directory."
        ),
    )
    map_parser.add_argument("target", help="Markdown file or directory to map.")
    map_parser.set_defaults(func=run_map)

    return parser


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if os.name == "nt":
        argv = [wash_windows_path(arg) for arg in argv]
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PermissionError as exc:
        print(permission_denied_message(None, "access wiki files", exc), file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 1


if __name__ == "__main__":
    sys.exit(main())
