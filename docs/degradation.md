# When an upstream is down

MAGI leans on seven services it does not control, and none of them owes it a
version guarantee: arXiv's HTML endpoint is officially beta, ar5iv is a frozen
February-2024 snapshot, Semantic Scholar's anonymous rate limit is undocumented
(measured: 295 ids refused, 100 accepted), MinerU has a thirty-minute
server-side deadline and a separate CDN host for results, Ollama is a local
process that may simply not be running, pandoc is an external binary, and PyPI's
simple index lags its JSON API by minutes.

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
