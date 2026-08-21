# MAGI — add to library

A browser button that sends the page you are reading to a local MAGI knowledge base.

## What it does, and what it deliberately does not

It sends two things to MAGI running on your own machine: the current tab's URL,
and which library you picked. That is all.

It does **not** scrape the page, download anything, work out what kind of
document it is, or convert anything. MAGI does all of that server-side, where it
is deterministic and covered by tests. Doing any of it here would be a second
implementation that quietly drifts from the first.

Nothing enters your library from this button. It adds a line to a queue. You
then run the pipeline and approve what came out:

```
magi ingest batch-run      # fetch and convert, unattended
magi ingest batch-list     # look at what came out
magi ingest batch-commit   # only approved items land in raw/
```

If you never install this, `magi ingest url "<URL>"` does exactly the same thing
from a terminal, and the **wiki_inbox** skill does it from an agent. All three
call the same function.

## Install (unpacked)

1. `magi ui` — MAGI must be running; the button looks on ports 8737–8741.
2. Chrome/Edge → `chrome://extensions` → turn on **Developer mode**
3. **Load unpacked** → choose this `browser-extension/` folder

Firefox: `about:debugging` → **This Firefox** → **Load Temporary Add-on** →
pick `manifest.json`.

## Security

MAGI's local API has no authentication. It is bound to loopback, and it ships no
CORS middleware on purpose — a hostile web page cannot make your browser call it.
This extension talks to it from the popup with `host_permissions`, which is not
subject to that restriction, so the safety argument has to come from somewhere
else: the one endpoint it uses can only append a line to a queue. It cannot start
a job, write into `raw/` or `wiki/`, or reach anything destructive, and what it
queues is inert until you approve it.

If you later expose MAGI beyond loopback, revisit this — the reasoning above
depends on the server only being reachable from your own machine.

## Troubleshooting

| What you see | What it means |
|---|---|
| *Could not reach MAGI* | MAGI is not running. Start it with `magi ui`. |
| *no libraries registered yet* | Run `magi kb register <PATH>` for at least one workspace. |
| *This only works on a web page* | The active tab is a browser page (settings, new tab), not a site. |
| A 404 naming your library | The name is not registered any more; reopen the popup to refresh the list. |
