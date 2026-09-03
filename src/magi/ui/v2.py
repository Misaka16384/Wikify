"""The v2 human surface, as HTTP.

The browser gets a *projection* of `threads/` and never a stored copy of one. A
cached map is a second answer to a question the notes already answer, and the
two disagree the first time somebody edits a file outside the UI — which they
will, because the files are the point.

The split of labour is the one the CLI already makes: Python decides, the
browser draws. A row arrives already knowing it is stalled, already carrying
the sentence to show a person, and already listing which statuses it may become
and who is allowed to say so. Nothing here hands the browser a rule to apply,
because a rule applied in two places is a rule that ends up meaning two things
(design-v2 D4).

Every endpoint answers with the fields the matching `--json` prints, for the
same reason: a dashboard reporting a different number than the terminal is
worse than no dashboard, since one of them is wrong and there is no way to tell
which from the outside.
"""

from __future__ import annotations

import datetime as dt
import threading
from pathlib import Path
from typing import List, Optional

#: Serialises the one route that captures a CLI's stdout. `redirect_stdout`
#: mutates `sys.stdout` for the whole process, so two concurrent requests on
#: Starlette's threadpool do not each get their own — they get each other's,
#: and the second one to exit restores a buffer the first had already
#: discarded. One route, one at a time, is cheaper than teaching `_decide` to
#: return its output instead of printing it.
_CAPTURE_LOCK = threading.Lock()

from fastapi import Body, HTTPException, Query


def register(app, resolve_workspace) -> None:
    """Mount the v2 routes on `app`.

    `resolve_workspace` is passed in rather than imported: which workspace a
    request means is policy, and there should be exactly one of it.
    """

    def _state(workspace: Optional[str]):
        from magi import state as state_mod

        ws = resolve_workspace(workspace)
        try:
            return ws, state_mod, state_mod.loaded(ws)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=500, detail=f"could not read notes: {exc}")

    def _inside(ws: Path, rel: str) -> Path:
        """A path the caller named, resolved under the workspace or refused.

        Publishing copies a file into `raw/`, which is the one directory this
        system treats as immutable truth, so "any path a request mentions" is
        not a thing this endpoint accepts.
        """
        rel = (rel or "").strip()
        if not rel:
            raise HTTPException(status_code=400, detail="which paper?")
        target = (ws / rel).resolve()
        try:
            target.relative_to(ws.resolve())
        except ValueError:
            raise HTTPException(status_code=400,
                                detail="that path is outside this project")
        if not target.is_file():
            raise HTTPException(status_code=404, detail=f"no file at {rel}")
        return target

    def _note(ws: Path, slug: str):
        from magi.kb import threads

        if not slug or slug != Path(slug).name or slug.startswith("."):
            raise HTTPException(status_code=400, detail=f"not a slug: {slug!r}")
        path = ws / threads.DIRNAME / f"{slug}.md"
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"no note: {slug}")
        return threads.read_note(path)

    # ------------------------------------------------------------------ map

    @app.get("/api/workspace/map")
    def get_workspace_map(workspace: Optional[str] = Query(None)) -> dict:
        """The two things a person is supposed to look at, plus the record.

        Field-for-field what `magi next --json` prints, with what `MAP.md`
        adds on top — so the dashboard and the terminal cannot drift.
        """
        ws, state_mod, st = _state(workspace)
        actions = state_mod.candidates(st)
        payload = state_mod.to_json(st, actions)
        # WIP is a limit `next` enforces, not a decision anybody is waiting on
        # (design-v2 §6). `render_map` drops it for that reason, so the browser
        # gets the same list already filtered rather than a second copy of the
        # rule — `queue` stays whole for parity with `magi next --json`.
        payload["decisions"] = [item for item in payload["queue"]
                                if item.get("kind") != "wip"]
        payload["retrospective"] = state_mod.retrospective(st)
        payload["unfiled"] = state_mod.unfiled(ws)
        payload["unreviewed"] = state_mod.unreviewed(st)
        payload["coaching"] = st.coaching
        payload["wip_limit"] = st.wip_limit
        # What the week has cost. `MAP.md` has carried this under `## Spending`
        # since M6 and the dashboard had no equivalent, so the browser could
        # see what MAGI's own calls had cost. No budget any more — a count.
        payload["budget"] = state_mod.budget(ws)
        return payload

    @app.get("/api/workspace/models")
    def get_workspace_models(host: Optional[str] = Query(None),
                             refresh: bool = Query(False)) -> dict:
        """What models one host offers, or every reviewable host at once.

        `source` says where the answer came from — `static` (the record knows),
        `live` (the CLI was asked), `cache` (it was asked yesterday), `none`
        (nobody can say, so the panel shows a text box). Never an error status:
        a config panel that will not render because a vendor's listing command
        was slow is worse than one with a text box in it.
        """
        from magi.core import hosts as host_table

        table = host_table.catalog()
        wanted = [host_table.resolve(host)] if host else list(table)
        out = {}
        for key in wanted:
            entry = table.get(key)
            if entry is None or not entry.argv:
                continue
            out[key] = host_table.models(entry, force=bool(refresh))
            out[key]["strong"] = entry.strong
            out[key]["cheap"] = entry.cheap
            out[key]["takes_effort"] = bool(entry.effort_argv)
        if host and not out:
            raise HTTPException(status_code=404, detail=f"no such reviewer: {host}")
        return {"hosts": out, "efforts": list(host_table.EFFORTS)}

    @app.get("/api/workspace/feed")
    def get_workspace_feed(workspace: Optional[str] = Query(None),
                           window: Optional[int] = Query(None),
                           line: Optional[str] = Query(None),
                           author: Optional[str] = Query(None),
                           limit: int = Query(200)) -> dict:
        ws, state_mod, st = _state(workspace)
        since = None
        if window:
            since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=window)
        entries = state_mod.feed(st, since=since, line=line, author=author)
        return {"workspace": str(ws), "total": len(entries),
                "entries": [vars(entry) for entry in entries[:max(0, limit)]]}

    # -------------------------------------------------------------- threads

    @app.get("/api/workspace/threads")
    def get_workspace_threads(workspace: Optional[str] = Query(None),
                              kind: Optional[str] = Query(None),
                              status: Optional[str] = Query(None),
                              line: Optional[str] = Query(None)) -> dict:
        from magi.core import vocab

        ws, _mod, st = _state(workspace)
        rows = []
        for note in st.notes:
            if kind and note.kind != kind:
                continue
            if status and note.status != status:
                continue
            if line and line not in (note.lines or []):
                continue
            rows.append({"slug": note.slug, "title": note.title, "kind": note.kind,
                         "status": note.status, "lines": list(note.lines or []),
                         "bet": note.frontmatter.get("bet"), "tier": note.tier,
                         "purpose": note.frontmatter.get("purpose", ""),
                         "posts": len(note.posts),
                         "last": note.posts[-1].at if note.posts else None})
        rows.sort(key=lambda row: (row["kind"] or "", row["slug"]))
        return {"workspace": str(ws), "threads": rows, "count": len(rows),
                "kinds": list(vocab.KINDS),
                "statuses": {name: list(vocab.statuses(name)) for name in vocab.KINDS}}

    @app.get("/api/workspace/thread")
    def get_workspace_thread(slug: str = Query(...),
                             workspace: Optional[str] = Query(None)) -> dict:
        from magi.core import vocab

        ws = resolve_workspace(workspace)
        note = _note(ws, slug)
        kind, status = note.kind or "", note.status or ""
        return {
            "workspace": str(ws), "slug": note.slug, "title": note.title,
            "kind": note.kind, "status": note.status, "tier": note.tier,
            # Normalised, because YAML lets `line:` be a scalar or a list and
            # the raw frontmatter below carries whichever the author typed.
            # The browser gets one shape or it gets a crash on the other.
            "lines": list(note.lines or []),
            # The prose only: the posts come back parsed, and sending the
            # discussion twice makes the browser render it twice.
            "frontmatter": dict(note.frontmatter), "body": note.prose,
            "path": str(note.path),
            "posts": [{"at": post.at, "host": post.host, "line": post.line,
                       "via": post.via,
                       "src": post.src, "dst": post.dst, "field": post.field,
                       "value": post.value, "text": post.text}
                      for post in note.posts],
            # Which statuses this note may become and who may say so. The
            # buttons are built from this, so the browser holds no copy of the
            # transition table — there is one, in `vocab`.
            # `conflict` is not offered. It is what the close gate *writes* when
            # two writers collide; a person choosing it by hand is recording a
            # disagreement that did not happen, and only a person can undo it.
            "moves": [{"dst": dst,
                       "writers": sorted(vocab.writers(kind, status, dst)),
                       "human_only": vocab.is_human_only(kind, status, dst)}
                      for dst in vocab.allowed_targets(kind, status)
                      if dst != vocab.CONFLICT],
        }

    @app.get("/api/workspace/inbox")
    def get_workspace_inbox(workspace: Optional[str] = Query(None)) -> dict:
        """Documents sitting in `inbox/` that nothing has picked up yet.

        The dashboard tells people to drop papers here and then had no way to
        show them: the Ingest Queue counts only what its own widgets queued,
        so a directory with two PDFs in it read as `WAITING IN QUEUE 0`.

        `notes.md` is not a document — it is the pile, it has its own box, and
        it is never ingested. `radar/` is generated. Directories are skipped
        rather than descended: `ingest auto` takes the top level, and a
        listing that goes deeper than the thing that acts on it would offer
        files nothing will collect.
        """
        ws = resolve_workspace(workspace)
        inbox = ws / "inbox"
        out = []
        if inbox.is_dir():
            for path in sorted(inbox.iterdir()):
                if path.is_dir() or path.name.startswith("."):
                    continue
                # `notes.md` is the pile and has its own box. `.lock` files
                # are this program's own bookkeeping and appeared in the list
                # as if they were documents to ingest.
                if path.name == "notes.md" or path.suffix == ".lock":
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                out.append({"name": path.name, "suffix": path.suffix.lower(),
                            "bytes": stat.st_size})
        return {"files": out, "count": len(out)}

    @app.get("/api/workspace/review/plan")
    def get_workspace_review_plan(workspace: Optional[str] = Query(None),
                                  slug: str = Query(...)) -> dict:
        """Who would be asked, which model, and what is left of the week.

        Spends nothing. The CLI has `--dry-run`; a browser needs the same
        answer before it presses, because otherwise a button that costs money
        looks exactly like a button that does not.
        """
        from magi import review as review_mod
        from magi.core import ledger

        ws = resolve_workspace(workspace)
        settings = review_mod._config(ws)
        refused = review_mod.unreviewable(ws, [slug])
        out = {
            "slug": slug,
            "spending": ledger.summary(ws),
            "enabled": settings.enabled,
            "refused": [{"slug": s, "why": why, "near": near}
                        for s, why, near in refused],
        }
        if refused:
            return dict(out, host=None, model=None, effort=None, tier=None)

        # The author is read off the note, so the browser's review avoids the
        # CLI that wrote the claim the way the command line's does. This used
        # to pass `None` and take the first installed host, which for a claim
        # written by that host was a same-vendor review labelled as nothing.
        author = review_mod.author_of(review_mod._note(ws, slug), settings.config)
        order = review_mod.reviewers(author, configured=settings.host,
                                     config=settings.config)
        if not order:
            return dict(out, host=None, model=None, effort=None, tier=None,
                        refused=out["refused"] + [
                            {"slug": slug,
                             "why": "no reviewer CLI is installed on this machine",
                             "near": []}])
        chosen = order[0]
        entry, model, effort = review_mod.plan(chosen, None, None, settings)
        return dict(out, host=chosen, model=model or None, effort=effort or None,
                    tier=entry.tier_of(model), fallbacks=order[1:], author=author)

    @app.post("/api/workspace/review")
    def post_workspace_review(payload: dict = Body(...)) -> dict:
        """Review one proposition, from the browser.

        One slug, always. `magi review` with no argument reviews everything
        unreviewed at once, which is the shape that let a workspace 39 calls
        into a limit of 40 finish the week at 99/40 — a button must not be
        able to do that by being pressed twice.

        Synchronous on purpose. A headless CLI call is fifteen seconds or so
        and the verdict is the whole point of pressing; handing back a job id
        and putting the answer in a log would be the terminal again, wearing a
        different hat. The caller is expected to show that it is working.
        """
        from magi import review as review_mod
        from magi.core import ledger

        ws = resolve_workspace(payload.get("workspace"))
        slug = (payload.get("slug") or "").strip()
        if not slug:
            raise HTTPException(status_code=400, detail="which proposition?")

        refused = review_mod.unreviewable(ws, [slug])
        if refused:
            _slug, why, near = refused[0]
            hint = f" Did you mean: {', '.join(near)}?" if near else ""
            raise HTTPException(status_code=400, detail=f"{why}.{hint}")

        settings = review_mod._config(ws)
        if not review_mod.installed_hosts(settings.config):
            raise HTTPException(
                status_code=400,
                detail="no reviewer CLI on this machine. The claim stays "
                       "unreviewed rather than self-approved.")
        try:
            # `review` picks the host itself: the author read off the note,
            # the configured host honoured, and the next installed CLI tried
            # when the first fails to answer. Passing a pre-picked host here
            # would take all three away from the browser.
            result = review_mod.review(ws, slug, host=settings.host, settings=settings)
        except ledger.SwitchedOff as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        except (RuntimeError, OSError) as exc:
            raise HTTPException(status_code=502, detail=str(exc))

        try:
            line = review_mod.apply_verdict(ws, result)
        except (ValueError, OSError) as exc:
            raise HTTPException(
                status_code=500,
                detail=f"{slug} was reviewed and the verdict could not be "
                       f"written ({exc}) — the call was spent")
        return {"slug": slug, "verdict": result.verdict, "host": result.host,
                "model": result.model or None, "effort": result.effort or None,
                "tier": result.tier or None, "reason": result.reason,
                "checked": result.checked, "assumption": result.assumption,
                "fell_back": result.fell_back, "said": line,
                "spending": ledger.summary(ws)}

    @app.post("/api/workspace/thread/new")
    def post_workspace_thread_new(payload: dict = Body(...)) -> dict:
        """Open a proposition, a question or a line, from the browser.

        There was no way to do this at all. `magi next` on a fresh workspace
        opens with "what is the next question?", so a person who came to the
        browser to avoid a terminal met the wall on the first screen.

        The slug is canonical or refused, never quietly repaired: it becomes a
        filename, and `P Gap` and `p-gap` would be two notes about one claim.
        """
        from magi.core import vocab
        from magi.core.wiki_common import slugify
        from magi.kb import threads

        ws = resolve_workspace(payload.get("workspace"))
        kind = (payload.get("kind") or "").strip()
        if kind not in (vocab.PROPOSITION, vocab.QUESTION, vocab.LINE):
            raise HTTPException(
                status_code=400,
                detail=f"kind is one of {vocab.PROPOSITION}, {vocab.QUESTION}, "
                       f"{vocab.LINE}")
        title = (payload.get("title") or "").strip()
        purpose = (payload.get("purpose") or "").strip()
        if not title or not purpose:
            raise HTTPException(
                status_code=400,
                detail="a note needs a title and a purpose — what it claims, "
                       "and why it is worth opening now")

        asked = (payload.get("slug") or title).strip()
        slug = slugify(asked)
        if not slug:
            raise HTTPException(status_code=400,
                                detail="that title produces no usable id — give one")
        path = ws / threads.DIRNAME / f"{slug}.md"
        if path.exists():
            raise HTTPException(status_code=409, detail=f"{slug} already exists")

        lines = [str(x) for x in (payload.get("lines") or []) if str(x).strip()]
        try:
            threads.create(path, kind, title, purpose, lines=lines or None)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        note = threads.read_note(path)
        return {"slug": note.slug, "kind": note.kind, "status": note.status,
                "path": str(path)}

    @app.post("/api/workspace/thread/line")
    def post_workspace_thread_line(payload: dict = Body(...)) -> dict:
        """Attach or detach research lines on a note that already exists.

        `--line` was accepted only at creation, so forgetting it once meant the
        note never counted toward that line and nothing in the system could
        repair it — the count was wrong and stayed wrong.
        """
        from magi.kb import threads

        ws = resolve_workspace(payload.get("workspace"))
        note = _note(ws, payload.get("slug") or "")
        lines = [str(x).strip() for x in (payload.get("lines") or [])
                 if str(x).strip()]
        why = (payload.get("text") or "").strip()
        if not why:
            raise HTTPException(
                status_code=400,
                detail="say why this belongs there — the field and the sentence "
                       "explaining it are one action")
        try:
            threads.set_field(note.path, "line", lines, host="human", via="webui", text=why)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"slug": note.slug, "lines": lines}

    @app.get("/api/workspace/line/close")
    def get_workspace_line_close(workspace: Optional[str] = Query(None),
                                 line: str = Query(...)) -> dict:
        """What closing this line would leave behind. Writes nothing.

        The survey *is* the command (see `close_cmd`): closing a line with
        three open propositions is a decision about those three, and a person
        who has not been shown them has not made it. The browser gets the same
        answer before it presses.
        """
        from magi import close_cmd

        return close_cmd.survey(resolve_workspace(workspace), line)

    @app.post("/api/workspace/line/close")
    def post_workspace_line_close(payload: dict = Body(...)) -> dict:
        """Close a research line. design-v2 §6: only a person calls this."""
        from magi import close_cmd
        from magi.core import vocab

        ws = resolve_workspace(payload.get("workspace"))
        line = (payload.get("line") or "").strip()
        why = (payload.get("text") or "").strip()
        if not line or not why:
            raise HTTPException(status_code=400,
                                detail="which line, and why it is ending")
        found = close_cmd.close(ws, line, why, anyway=bool(payload.get("anyway")),
                                host=vocab.HUMAN, via="webui")
        if not found.get("ok"):
            raise HTTPException(status_code=409, detail=found)
        return found

    @app.get("/api/workspace/publish")
    def get_workspace_publish(workspace: Optional[str] = Query(None),
                              paper: str = Query(...),
                              line: List[str] = Query(default=[])) -> dict:
        """What publishing would bury, and what it refuses to bury quietly."""
        from magi import publish_cmd

        ws = resolve_workspace(workspace)
        return publish_cmd.survey(ws, _inside(ws, paper), list(line))

    @app.post("/api/workspace/publish")
    def post_workspace_publish(payload: dict = Body(...)) -> dict:
        """File our own paper and retire the work it reports. §6: a person."""
        from magi import publish_cmd
        from magi.core import vocab

        ws = resolve_workspace(payload.get("workspace"))
        lines = [str(x) for x in (payload.get("lines") or []) if str(x).strip()]
        why = (payload.get("text") or "").strip()
        if not lines or not why:
            raise HTTPException(status_code=400,
                                detail="which line(s) this reports, and a sentence")
        found = publish_cmd.publish(ws, _inside(ws, payload.get("paper") or ""),
                                    lines, why,
                                    anyway=bool(payload.get("anyway")),
                                    host=vocab.HUMAN, via="webui")
        if not found.get("ok"):
            raise HTTPException(status_code=409, detail=found)
        return found

    @app.post("/api/workspace/draft")
    def post_workspace_draft(payload: dict = Body(...)) -> dict:
        """Start or replace a draft in `drafts/`, from the browser.

        `publish` names `drafts/` and the browser had no way to put anything
        there, so the ceremony was reachable and its input was not: pressing
        it answered "no .md in drafts/ or output/ — put the write-up there
        first", which is a terminal instruction wearing a button.

        Not an editor. A place to paste the write-up somebody has, which is
        what makes the next step possible.
        """
        from magi.core.wiki_common import atomic_write, slugify

        ws = resolve_workspace(payload.get("workspace"))
        title = (payload.get("title") or "").strip()
        body = payload.get("body") or ""
        if not title or not body.strip():
            raise HTTPException(status_code=400,
                                detail="a draft needs a title and some text")
        name = slugify(title)
        if not name:
            raise HTTPException(status_code=400,
                                detail="that title produces no usable filename")
        drafts = ws / "drafts"
        drafts.mkdir(parents=True, exist_ok=True)
        path = drafts / f"{name}.md"
        text = body if body.lstrip().startswith("#") else (
            f"# {title}\n\n{body}")
        atomic_write(path, text.rstrip("\n") + "\n")
        return {"path": path.relative_to(ws).as_posix(), "title": title}

    @app.get("/api/workspace/papers")
    def get_workspace_papers(workspace: Optional[str] = Query(None)) -> dict:
        """Documents in this workspace that could be the paper being published.

        `drafts/` is where our own writing lives, so a picker that made
        somebody type a path would be a text box standing in for a list we
        already have.
        """
        ws = resolve_workspace(workspace)
        out = []
        for base in ("drafts", "output"):
            d = ws / base
            if not d.is_dir():
                continue
            for path in sorted(d.rglob("*.md")):
                if path.name.startswith((".", "_")):
                    continue
                out.append((path.relative_to(ws)).as_posix())
        return {"papers": out}

    @app.post("/api/workspace/thread/post")
    def post_workspace_thread_post(payload: dict = Body(...)) -> dict:
        """A person writing in a discussion, signed as a person.

        The UI signs `human` and nothing else. A post signed with a host name
        claims a model said it, and that is the one signature the record cannot
        afford to invent: `sync --close` reads it to decide whether somebody
        has actually ruled on something.
        """
        from magi.kb import threads

        ws = resolve_workspace(payload.get("workspace"))
        text = (payload.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="the post is empty")
        note = _note(ws, payload.get("slug") or "")
        try:
            threads.append_post(note.path, text, host="human", via="webui",
                                line=payload.get("line") or None)
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"slug": note.slug, "path": str(note.path)}

    @app.post("/api/workspace/thread/status")
    def post_workspace_thread_status(payload: dict = Body(...)) -> dict:
        """Flip a status. The reason is required, not optional.

        `set_status` writes the move and the reason as one post under one lock,
        so a flip cannot reach the file without the sentence saying why.
        """
        from magi.kb import threads

        ws = resolve_workspace(payload.get("workspace"))
        dst = (payload.get("dst") or "").strip()
        why = (payload.get("text") or "").strip()
        if not why:
            raise HTTPException(status_code=400,
                                detail="a status change needs a reason")
        note = _note(ws, payload.get("slug") or "")
        try:
            threads.set_status(note.path, dst, why, host="human", via="webui",
                               line=payload.get("line") or None)
        except (ValueError, OSError) as exc:
            # `IllegalTransition` is a `ValueError`, and so is a note whose
            # frontmatter somebody broke by hand. Both are things a request can
            # legitimately hit, and neither is this server failing.
            raise HTTPException(status_code=400, detail=str(exc))
        return {"slug": note.slug, "status": dst, "path": str(note.path)}

    # --------------------------------------------------------- human input

    @app.post("/api/workspace/decide")
    def post_workspace_decide(payload: dict = Body(...)) -> dict:
        """`magi decide`, reached from the browser.

        The same function the CLI calls, so a decision typed here and one an
        agent transcribes produce the same three writes.
        """
        from magi import decide_cmd

        ws = resolve_workspace(payload.get("workspace"))
        try:
            return decide_cmd.record(
                ws, payload.get("text") or "", about=payload.get("about") or None,
                bet=payload.get("bet") or None, kind=payload.get("kind") or None,
                line=payload.get("line") or None)
        except (decide_cmd.Refused, ValueError, OSError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/api/workspace/proposal")
    def post_workspace_proposal(payload: dict = Body(...)) -> dict:
        """Rule on one thing the slow loop has put in front of a person.

        The same code path the CLI takes, so a decision made here and one made
        in the terminal write the same records — and the rule budget can refuse
        here too, which is the point of it refusing rather than truncating.

        `retire` is one of them because the queue asks for it: a rule whose
        pattern has gone quiet comes back as a question every time `magi next`
        runs, and a question a person can only answer in a terminal is one that
        sits in the queue forever.
        """
        from magi.reflect import cmd as reflect_cmd

        ws = resolve_workspace(payload.get("workspace"))
        verb = str(payload.get("verb") or "").strip()
        if verb not in ("accept", "reject", "promote", "retire"):
            raise HTTPException(
                status_code=400,
                detail="a decision is accept, reject, promote or retire")
        ident = str(payload.get("id") or "").strip()
        note = str(payload.get("note") or "")

        # Captured under a lock, because `redirect_stdout` swaps the
        # process-global `sys.stdout` and Starlette runs a sync route on a
        # shared threadpool. Two tabs deciding at once interleaved their
        # contexts: one request got the other's output, and the `with` block
        # exiting second restored `sys.stdout` to a StringIO that was already
        # dead — after which every uvicorn log line went into a buffer nobody
        # reads, for the life of the process.
        import io

        errors, said = io.StringIO(), io.StringIO()
        with _CAPTURE_LOCK:
            import contextlib

            with contextlib.redirect_stderr(errors), contextlib.redirect_stdout(said):
                code = reflect_cmd._decide(ws, verb, ident, note, as_json=False)
        if code != 0:
            raise HTTPException(status_code=400,
                                detail=errors.getvalue().strip() or "refused")
        # What the CLI would have printed comes back rather than being dropped.
        # Re-rendering the block can move somebody's `CLAUDE.md` to a backup,
        # and being told that only in a terminal nobody was looking at is the
        # same as not being told.
        return {"id": ident, "verdict": verb, "said": said.getvalue().strip()}

    @app.post("/api/workspace/dump")
    def post_workspace_dump(payload: dict = Body(...)) -> dict:
        """The one box a person is allowed to be untidy in.

        Appended verbatim: no parsing, no routing, no asking which line it
        belongs to. Deciding that at the moment of having the thought is the
        cost this box exists to remove — `magi next` puts filing at the top of
        the agent's list instead.
        """
        from magi import state as state_mod

        ws = resolve_workspace(payload.get("workspace"))
        text = payload.get("text") or ""
        if not text.strip():
            raise HTTPException(status_code=400, detail="nothing to file")
        path = state_mod.dump(ws, text)
        return {"workspace": str(ws), "path": str(path),
                "unfiled": len(state_mod.unfiled(ws))}
