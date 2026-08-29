# When an upstream is down

MAGI leans on eleven things it does not control, and none of them owes it a
version guarantee. Seven are network services: arXiv's HTML endpoint is officially beta, ar5iv is a frozen
February-2024 snapshot, Semantic Scholar's anonymous rate limit is undocumented
(measured: 295 ids refused, 100 accepted), MinerU has a thirty-minute
server-side deadline and a separate CDN host for results, Ollama is a local
process that may simply not be running, pandoc is an external binary, and PyPI's
simple index lags its JSON API by minutes.

The other four arrived with v2 and are **other people's programs on this
machine**: the agent CLIs. MAGI asks one of them to review a claim, reads the
session files five of them write, and counts what that costs — and every one of
those is a command line, a directory layout and a flag that somebody else may
rename in a point release. They belong in this table for the same reason the
services do.

This table is the answer to "what happens then", written down once instead of
rediscovered per incident. It is also a test checklist: every row names the
code path that implements the fallback, so a row with no path is a gap, and a
path that stops existing is a regression.

**The rule the table encodes:** an upstream going away must change *how well*
MAGI works, never *whether the user is told*. Every degradation is visible —
a finding, a note on stderr, or a labelled field in JSON. A silent fallback is
the failure this whole pipeline is organised against, and it does not become
acceptable because the cause was somebody else's outage.

| Upstream | Used for | When it is unreachable | What the user sees | Implemented in |
|---|---|---|---|---|
| **arXiv `/html/{id}`** (beta) | Rung 1: LaTeXML HTML carrying the original TeX in `alttext` | Falls through to ar5iv, then to rung 2 (the source tarball) | The batch item names the route that actually ran; a rung-1 miss is normal, not an error | `ingest/arxiv_html.py` (`AR5IV_URL`, `fetch`) |
| **ar5iv** (frozen 2024-02 snapshot) | Rung 1 for anything older than the native backfill | Falls through to rung 2 | As above. A redirect to `/abs/` is treated as a miss, not as a page | `ingest/arxiv_html.py:fetch` |
| **arXiv e-print tarball** | Rung 2: `magi ingest tex` | Falls through to rung 3/4/5 depending on the text-layer gate | Route recorded per item; gates report what the conversion lost | `ingest/batch.py:_run_route` |
| **pandoc** (external binary) | Rung 2 only | Rung 2 returns `ConversionResult.failed` naming pandoc, and the item falls to the next rung | *"pandoc was not found … install it or set pandoc.path in config.yaml"* — a missing tool, not a missing document | `ingest/tex2md.py:convert` |
| **MinerU cloud** | Rung 4, the strongest route for maths and tables | Upload, poll and download each return a structured failure; the download retries, because by then the conversion is finished **and already billed** | *"the extraction SUCCEEDED and the quota for it is already spent, but the result could not be downloaded from `<host>`"* — points at the network, not at the document | `ingest/mineru.py` (`DOWNLOAD_ATTEMPTS`) |
| **Ollama** (local) | Embeddings for `magi index`, `magi search --mode hybrid`, radar scoring | Search falls back to BM25; indexing writes chunks without vectors and backfills next run; radar keeps whatever it scored before the failure | `vector_degraded` in the search payload; radar prints `relevance scoring skipped` | `retrieval.py:Embedder`, `radar.py:_score_candidates` |
| **Semantic Scholar** | Radar recommendations, DOI → arXiv resolution | One retry on a 429, then the harvest continues with the sources that answered | Fewer candidates; the digest says which sources ran | `radar.py:_s2_get` |
| **PyPI simple index** | Version checks only | Nothing degrades; the check is advisory | Silence, or a slightly stale "newer version available" | — |
| **A reviewer CLI** (claude / codex / agy) | `magi review` — the independent second read of a proposition | Another installed vendor is picked instead; a same-host review is second choice and still runs; with none installed the review refuses rather than passing | The verdict records which host gave it, so "same vendor as the author" is visible; with none on PATH, *"no reviewer CLI on PATH (looked for …)"* | `review.py` (`installed_hosts`, `pick_host`) |
| **A reviewer CLI that answers badly** | as above | An unparseable reply is `unclear` — never `stands`. A timeout or a non-zero exit is recorded in the call ledger and re-raised | The reviewer's own words are quoted under the verdict, so a rambling answer is legible rather than summarised into an approval | `review.py` (`parse_verdict`, `_spend`) |
| **A vendor's session store** | `magi reflect read` — the slow loop's transcripts | That host yields nothing; the others are read as usual. A moved schema, a half-written line and an unreadable database are all the same answer | The sweep reports `unreadable: {host: why}` alongside what it found; a host with no reader at all is simply absent | `reflect/transcripts.py:sweep` |
| **The call budget** | Every model call MAGI makes on its own initiative | Counted in *calls*, not money — a headless CLI does not say what a request cost — and the gate refuses once the week's count is spent | *"the weekly budget is spent"*, naming the count and the setting; `research.llm_calls: false` turns them off outright | `core/ledger.py`, `research.weekly_calls` |

## What is *not* covered

Honest gaps, so the table is not read as a promise:

- **No row is exercised against a real outage.** Each fallback has unit tests
  with a stubbed transport; none has been run against the actual service being
  down, except MinerU — which is in here because it happened (seven jobs
  converted, billed, and lost to an unreachable CDN host).
- **Partial availability is not modelled.** A service that answers slowly, or
  answers with truncated data, is not the same as one that is down, and only
  MinerU's poll loop distinguishes them.
- **No upstream is version-pinned**, because none offers a version to pin.
  A change in arXiv's HTML markup, ar5iv's redirect behaviour, or MinerU's
  response shape would show up as a conversion failure, not as a clear error.
- **The tier-2 agent CLIs are described, not measured.** qwen and opencode are
  declared from their vendors' own documentation; the rows above are what
  *should* happen. Tier 1 — Claude Code, Codex, Antigravity — is smoke tested
  against a real install each release, and that is the whole difference between
  the tiers.
- **A vendor renaming its transcript layout is invisible until you look.** The
  sweep reports what it could not read, but a store that moved reads as "this
  host had no sessions in this workspace", which is also what an unused host
  looks like. Nothing distinguishes them without opening the directory.
