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
from pathlib import Path
from typing import Optional

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
            threads.append_post(note.path, text, host="human",
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
            threads.set_status(note.path, dst, why, host="human",
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

        import contextlib
        import io

        errors, said = io.StringIO(), io.StringIO()
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
