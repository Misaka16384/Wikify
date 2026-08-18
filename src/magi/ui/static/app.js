// MAGI WebUI Dashboard Frontend Controller

(function () {
  "use strict";

  // State
  const state = {
    workspace: "",
    kbs: [],
    activeTab: "dashboard",
    activeJobId: null,
    eventSource: null,
    theme: localStorage.getItem("magi-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"),
  };

  // DOM Elements
  const els = {
    themeToggleBtn: document.getElementById("theme-toggle-btn"),
    workspaceSelect: document.getElementById("workspace-select"),
    appVersion: document.getElementById("app-version"),
    syncRatioBadge: document.getElementById("sync-ratio-badge"),
    syncRatioVal: document.getElementById("sync-ratio-val"),
    activeJobsBadge: document.getElementById("active-jobs-badge"),
    activeJobsCount: document.getElementById("active-jobs-count"),
    doctorBtn: document.getElementById("doctor-btn"),

    // Tabs
    tabBtns: document.querySelectorAll(".tab-btn"),
    tabPanels: document.querySelectorAll(".tab-panel"),

    // Dashboard
    dashSyncRatio: document.getElementById("dash-sync-ratio"),
    dashKbCount: document.getElementById("dash-kb-count"),
    dashPendingDigests: document.getElementById("dash-pending-digests"),
    dashBeadsReady: document.getElementById("dash-beads-ready"),
    kbTableBody: document.getElementById("kb-table-body"),
    refreshKbBtn: document.getElementById("refresh-kb-btn"),
    registerKbForm: document.getElementById("register-kb-form"),
    regKbPath: document.getElementById("reg-kb-path"),
    regKbName: document.getElementById("reg-kb-name"),
    regKbEnabled: document.getElementById("reg-kb-enabled"),

    // Melchior
    melchiorConcepts: document.getElementById("melchior-concepts"),
    melchiorRefs: document.getElementById("melchior-refs"),
    melchiorGraphStatus: document.getElementById("melchior-graph-status"),
    melchiorClaimsVal: document.getElementById("melchior-claims-val"),
    melchiorClaimsRate: document.getElementById("melchior-claims-rate"),
    claimsTableBody: document.getElementById("claims-table-body"),
    refreshClaimsBtn: document.getElementById("refresh-claims-btn"),
    backlogCountBadge: document.getElementById("backlog-count-badge"),
    backlogList: document.getElementById("backlog-list"),
    sqlQueryInput: document.getElementById("sql-query-input"),
    runSqlBtn: document.getElementById("run-sql-btn"),
    sqlResultContainer: document.getElementById("sql-result-container"),
    presetSqlBtns: document.querySelectorAll(".preset-sql-btn"),

    // Balthasar
    beadsStatusBanner: document.getElementById("beads-status-banner"),
    beadsReadyVal: document.getElementById("beads-ready-val"),
    beadsProgressVal: document.getElementById("beads-progress-val"),
    beadsBlockedVal: document.getElementById("beads-blocked-val"),
    beadsOpenVal: document.getElementById("beads-open-val"),
    btnBacklogSync: document.getElementById("btn-backlog-sync"),

    // Casper
    searchForm: document.getElementById("search-form"),
    searchQueryInput: document.getElementById("search-query-input"),
    searchModeSelect: document.getElementById("search-mode-select"),
    searchLimitSelect: document.getElementById("search-limit-select"),
    searchInfoBar: document.getElementById("search-info-bar"),
    searchResultsList: document.getElementById("search-results-list"),

    // Radar
    radarSeenCount: document.getElementById("radar-seen-count"),
    radarPendingCount: document.getElementById("radar-pending-count"),
    btnRadarHarvest: document.getElementById("btn-radar-harvest"),
    btnRadarCitationGap: document.getElementById("btn-radar-citation-gap"),
    digestFilesList: document.getElementById("digest-files-list"),
    digestViewer: document.getElementById("digest-viewer"),

    // Operations & Terminal
    opTaskBtns: document.querySelectorAll(".op-task-btn"),
    dangerActionBtns: document.querySelectorAll(".danger-action-btn"),
    termStatusDot: document.getElementById("term-status-dot"),
    termJobName: document.getElementById("term-job-name"),
    terminalOutput: document.getElementById("terminal-output"),
    termAutoscroll: document.getElementById("term-autoscroll"),
    termCancelBtn: document.getElementById("term-cancel-btn"),
    termClearBtn: document.getElementById("term-clear-btn"),

    // Docs
    docSwitchBtns: document.querySelectorAll(".doc-switch-btn"),
    docsContent: document.getElementById("docs-content"),

    // Modals
    dangerModal: document.getElementById("danger-modal"),
    dangerModalTitle: document.getElementById("danger-modal-title"),
    dangerModalDesc: document.getElementById("danger-modal-desc"),
    dangerModalCancel: document.getElementById("danger-modal-cancel"),
    dangerModalConfirm: document.getElementById("danger-modal-confirm"),
    doctorModal: document.getElementById("doctor-modal"),
    doctorModalBody: document.getElementById("doctor-modal-body"),
    doctorModalClose: document.getElementById("doctor-modal-close"),

    toastContainer: document.getElementById("toast-container"),
  };

  let pendingDangerCommand = null;

  // ------------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------------

  async function apiFetch(url, options = {}) {
    try {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.error || `HTTP ${res.status}`);
      }
      return data;
    } catch (err) {
      showToast(err.message, "error");
      throw err;
    }
  }

  function showToast(msg, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = msg;
    els.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function applyTheme(theme) {
    state.theme = theme;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("magi-theme", theme);
    els.themeToggleBtn.textContent = theme === "dark" ? "☀️" : "🌓";
  }

  // ------------------------------------------------------------------------
  // Tab Management
  // ------------------------------------------------------------------------

  function switchTab(tabName) {
    state.activeTab = tabName;
    els.tabBtns.forEach((b) => {
      b.classList.toggle("active", b.dataset.tab === tabName);
    });
    els.tabPanels.forEach((p) => {
      p.classList.toggle("active", p.id === `tab-${tabName}`);
    });
    loadTabData(tabName);
  }

  function loadTabData(tabName) {
    switch (tabName) {
      case "dashboard":
        loadDashboard();
        break;
      case "melchior":
        loadMelchior();
        break;
      case "balthasar":
        loadBalthasar();
        break;
      case "casper":
        // Search is on-demand
        break;
      case "radar":
        loadRadar();
        break;
      case "operations":
        // Terminal stays persistent
        break;
      case "docs":
        loadDocs("readme-zh");
        break;
    }
  }

  // ------------------------------------------------------------------------
  // Workspace & Global Status
  // ------------------------------------------------------------------------

  async function loadInitialStatus() {
    try {
      const status = await apiFetch("/api/status");
      els.appVersion.textContent = `v${status.version}`;
      state.workspace = status.active_workspace || "";

      await loadKBRegistry();
      if (status.active_jobs_count > 0) {
        els.activeJobsBadge.style.display = "flex";
        els.activeJobsCount.textContent = status.active_jobs_count;
      }
      loadSyncRatio();
      loadTabData(state.activeTab);
    } catch (err) {
      console.error("Init status failed:", err);
    }
  }

  async function loadKBRegistry() {
    try {
      const data = await apiFetch("/api/kb");
      state.kbs = data.kbs || [];
      els.dashKbCount.textContent = state.kbs.length;

      // Populate workspace dropdown
      els.workspaceSelect.innerHTML = "";
      state.kbs.forEach((kb) => {
        const opt = document.createElement("option");
        opt.value = kb.path;
        opt.textContent = `${kb.name}${kb.current ? " (Active)" : ""}`;
        if (kb.current || (!state.workspace && opt.value === kb.path)) {
          opt.selected = true;
          state.workspace = kb.path;
        }
        els.workspaceSelect.appendChild(opt);
      });

      // Ensure active workspace is present even if not in registry
      const hasCurrentInKBs = state.kbs.some((kb) => kb.path === state.workspace);
      if (state.workspace && !hasCurrentInKBs) {
        const opt = document.createElement("option");
        opt.value = state.workspace;
        opt.textContent = `Current Workspace (${state.workspace})`;
        opt.selected = true;
        els.workspaceSelect.appendChild(opt);
      }

      renderKBTable(state.kbs);
    } catch (err) {
      console.error("Load KBs failed:", err);
    }
  }

  async function loadSyncRatio() {
    if (!state.workspace) return;
    try {
      const rep = await apiFetch(`/api/workspace/sync?workspace=${encodeURIComponent(state.workspace)}`);
      const ratio = rep.sync_ratio !== null ? `${rep.sync_ratio}%` : "--%";
      els.syncRatioVal.textContent = ratio;
      els.dashSyncRatio.textContent = ratio;

      if (rep.sync_ratio === 100) {
        els.syncRatioBadge.className = "stat-pill success";
      } else if (rep.sync_ratio && rep.sync_ratio < 60) {
        els.syncRatioBadge.className = "stat-pill warning";
      } else {
        els.syncRatioBadge.className = "stat-pill info";
      }
    } catch (err) {
      els.syncRatioVal.textContent = "--%";
    }
  }

  // ------------------------------------------------------------------------
  // Tab 1: Dashboard
  // ------------------------------------------------------------------------

  async function loadDashboard() {
    loadKBRegistry();
    loadSyncRatio();
    if (state.workspace) {
      try {
        const radar = await apiFetch(`/api/workspace/radar?workspace=${encodeURIComponent(state.workspace)}`);
        els.dashPendingDigests.textContent = radar.pending_digests ? radar.pending_digests.length : 0;
      } catch (_) {}

      try {
        const pm = await apiFetch(`/api/workspace/pm?workspace=${encodeURIComponent(state.workspace)}`);
        if (pm.summary) {
          els.dashBeadsReady.textContent = `${pm.summary.ready || 0} ready`;
        } else {
          els.dashBeadsReady.textContent = pm.beads_available ? "0 ready" : "bd offline";
        }
      } catch (_) {}
    }
  }

  function renderKBTable(kbs) {
    if (!kbs.length) {
      els.kbTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">No knowledge bases registered yet.</td></tr>`;
      return;
    }

    els.kbTableBody.innerHTML = kbs
      .map((kb) => {
        const syncBadge = kb.sync_ratio !== null && kb.sync_ratio !== undefined
          ? `<span class="badge ${kb.sync_ratio === 100 ? "badge-sage" : "badge-terracotta"}">${kb.sync_ratio}%</span>`
          : `<span class="badge badge-muted">--</span>`;

        const indexedBadge = kb.indexed
          ? `<span class="badge badge-sage">Indexed</span>`
          : `<span class="badge badge-danger">No Index</span>`;

        const graphBadge = kb.graph_built
          ? `<span class="badge badge-sage">Built</span>`
          : `<span class="badge badge-danger">Missing</span>`;

        return `
          <tr>
            <td>
              <strong>${escapeHtml(kb.name)}</strong>
              ${kb.current ? '<span class="badge badge-terracotta" style="margin-left: 0.4rem;">current</span>' : ""}
            </td>
            <td><code style="font-size: 0.8rem;">${escapeHtml(kb.path)}</code></td>
            <td>
              <input type="checkbox" class="kb-toggle-cb" data-name="${escapeHtml(kb.name)}" ${kb.enabled ? "checked" : ""}>
            </td>
            <td>${indexedBadge}</td>
            <td>${graphBadge}</td>
            <td>${syncBadge}</td>
            <td>
              <button class="btn btn-secondary btn-sm switch-ws-btn" data-path="${escapeHtml(kb.path)}">Switch</button>
              <button class="btn btn-danger btn-sm unreg-kb-btn" data-name="${escapeHtml(kb.name)}">Remove</button>
            </td>
          </tr>
        `;
      })
      .join("");

    // Attach listeners
    els.kbTableBody.querySelectorAll(".kb-toggle-cb").forEach((cb) => {
      cb.addEventListener("change", async (e) => {
        const name = e.target.dataset.name;
        const enabled = e.target.checked;
        try {
          await apiFetch(`/api/kb/${encodeURIComponent(name)}/toggle`, {
            method: "POST",
            body: JSON.stringify({ enabled }),
          });
          showToast(`KB '${name}' search status updated.`, "success");
        } catch (_) {
          e.target.checked = !enabled;
        }
      });
    });

    els.kbTableBody.querySelectorAll(".switch-ws-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.workspace = btn.dataset.path;
        els.workspaceSelect.value = state.workspace;
        loadSyncRatio();
        loadTabData(state.activeTab);
        showToast(`Switched active workspace.`, "info");
      });
    });

    els.kbTableBody.querySelectorAll(".unreg-kb-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const name = btn.dataset.name;
        if (!confirm(`Unregister KB '${name}'? (Workspace files will remain untouched)`)) return;
        try {
          await apiFetch(`/api/kb/${encodeURIComponent(name)}`, { method: "DELETE" });
          showToast(`Unregistered KB '${name}'.`, "info");
          loadKBRegistry();
        } catch (_) {}
      });
    });
  }

  // ------------------------------------------------------------------------
  // Tab 2: Melchior (Cognitive State)
  // ------------------------------------------------------------------------

  async function loadMelchior() {
    if (!state.workspace) return;
    try {
      const rep = await apiFetch(`/api/workspace/sync?workspace=${encodeURIComponent(state.workspace)}`);
      const mel = rep.cores?.melchior || {};
      els.melchiorConcepts.textContent = mel.concepts || 0;
      els.melchiorRefs.textContent = mel.references || 0;
      els.melchiorGraphStatus.textContent = mel.graph || "missing";
      els.melchiorGraphStatus.style.color = mel.graph === "fresh" ? "var(--accent-sage)" : "var(--accent-danger)";
    } catch (_) {}

    // Load Claims
    try {
      const claimsData = await apiFetch(`/api/workspace/claims?workspace=${encodeURIComponent(state.workspace)}`);
      const claims = claimsData.claims || [];
      els.melchiorClaimsVal.textContent = `${claimsData.verified || 0} / ${claimsData.total || 0}`;
      const pct = claimsData.total ? Math.round((claimsData.verified / claimsData.total) * 100) : 100;
      els.melchiorClaimsRate.textContent = `${pct}% verified`;

      if (!claims.length) {
        els.claimsTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">No claims recorded in graph or cards.</td></tr>`;
      } else {
        els.claimsTableBody.innerHTML = claims
          .map((c) => {
            const isVerified = c.status === "verified" || c.status === "web-verified";
            const badgeClass = isVerified ? "badge-sage" : "badge-danger";
            return `
              <tr>
                <td><span class="badge ${badgeClass}">${escapeHtml(c.status || "unverified")}</span></td>
                <td><strong>${escapeHtml(c.text)}</strong></td>
                <td><em style="color: var(--text-secondary);">"${escapeHtml(c.quote || "")}"</em></td>
                <td><code style="font-size: 0.75rem;">${escapeHtml(c.source || "")}</code></td>
              </tr>
            `;
          })
          .join("");
      }
    } catch (_) {}

    // Load Backlog
    try {
      const backlogData = await apiFetch(`/api/workspace/backlog?workspace=${encodeURIComponent(state.workspace)}`);
      const backlog = backlogData.backlog || [];
      els.backlogCountBadge.textContent = `${backlog.length} items`;
      if (!backlog.length) {
        els.backlogList.innerHTML = `<li style="color: var(--text-muted); padding: 0.3rem 0;">Clean: No uncompiled raw files.</li>`;
      } else {
        els.backlogList.innerHTML = backlog
          .map((item) => `<li style="padding: 0.3rem 0; border-bottom: 1px solid var(--border-subtle);">📄 ${escapeHtml(item)}</li>`)
          .join("");
      }
    } catch (_) {}
  }

  async function executeGraphSql(sql) {
    if (!state.workspace || !sql.trim()) return;
    els.sqlResultContainer.innerHTML = `<p style="color: var(--text-muted);">Executing query...</p>`;
    try {
      const data = await apiFetch(
        `/api/workspace/graph/query?sql=${encodeURIComponent(sql)}&workspace=${encodeURIComponent(state.workspace)}`
      );
      const cols = data.columns || [];
      const rows = data.rows || [];

      if (!rows.length) {
        els.sqlResultContainer.innerHTML = `<p style="color: var(--text-muted);">Query returned 0 rows.</p>`;
        return;
      }

      let html = `<table class="data-table"><thead><tr>`;
      cols.forEach((col) => {
        html += `<th>${escapeHtml(col)}</th>`;
      });
      html += `</tr></thead><tbody>`;

      rows.forEach((row) => {
        html += `<tr>`;
        cols.forEach((col) => {
          html += `<td>${escapeHtml(row[col] !== null && row[col] !== undefined ? row[col] : "NULL")}</td>`;
        });
        html += `</tr>`;
      });
      html += `</tbody></table>`;
      els.sqlResultContainer.innerHTML = html;
    } catch (err) {
      els.sqlResultContainer.innerHTML = `<div style="color: var(--accent-danger); font-family: var(--font-mono); font-size: 0.85rem; padding: 0.5rem; background: var(--accent-danger-wash); border-radius: 4px;">${escapeHtml(err.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 3: Balthasar (Tasks)
  // ------------------------------------------------------------------------

  async function loadBalthasar() {
    if (!state.workspace) return;
    try {
      const pm = await apiFetch(`/api/workspace/pm?workspace=${encodeURIComponent(state.workspace)}`);
      if (!pm.beads_available) {
        els.beadsStatusBanner.innerHTML = `
          <div class="stat-pill warning" style="border-radius: var(--radius-md); padding: 0.75rem;">
            ⚠️ Beads (bd) CLI is not installed or not in PATH. Run <code>magi setup</code> to install bd.
          </div>
        `;
        return;
      }
      if (!pm.summary) {
        els.beadsStatusBanner.innerHTML = `
          <div class="stat-pill info" style="border-radius: var(--radius-md); padding: 0.75rem;">
            ℹ️ No Beads database initialized at workspace or hub. Click below to initialize beads.
          </div>
        `;
        return;
      }

      els.beadsStatusBanner.innerHTML = "";
      els.beadsReadyVal.textContent = pm.summary.ready || 0;
      els.beadsProgressVal.textContent = pm.summary.in_progress || 0;
      els.beadsBlockedVal.textContent = pm.summary.blocked || 0;
      els.beadsOpenVal.textContent = pm.summary.open || 0;
    } catch (_) {}
  }

  // ------------------------------------------------------------------------
  // Tab 4: Casper (Retrieval)
  // ------------------------------------------------------------------------

  async function executeSearch(query, mode, limit) {
    if (!state.workspace || !query.trim()) return;
    els.searchResultsList.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">Searching corpus...</p>`;
    els.searchInfoBar.textContent = "";

    try {
      const data = await apiFetch(
        `/api/workspace/search?q=${encodeURIComponent(query)}&mode=${mode}&limit=${limit}&workspace=${encodeURIComponent(state.workspace)}`
      );

      if (data.error) {
        els.searchResultsList.innerHTML = `<div class="stat-pill warning" style="margin: 1rem 0;">${escapeHtml(data.error)}</div>`;
        return;
      }

      els.searchInfoBar.textContent = `Found ${data.results.length} hit(s) · BM25 hits: ${data.bm25_hits || 0} · Vector available: ${data.vector_available ? "Yes" : "No"}`;

      if (!data.results.length) {
        els.searchResultsList.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">No matching passages found.</p>`;
        return;
      }

      els.searchResultsList.innerHTML = data.results
        .map((hit) => {
          return `
            <div class="search-hit-card">
              <div class="search-hit-header">
                <div class="search-hit-title">${escapeHtml(hit.heading || hit.path)}</div>
                <div style="display: flex; gap: 0.4rem; align-items: center;">
                  <span class="badge badge-terracotta">RRF ${hit.score}</span>
                  ${hit.bm25_rank ? `<span class="badge badge-blue">BM25 #${hit.bm25_rank}</span>` : ""}
                  ${hit.vector_rank ? `<span class="badge badge-sage">Vec #${hit.vector_rank}</span>` : ""}
                </div>
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); font-family: var(--font-mono);">
                ${escapeHtml(hit.path)} (lines ${hit.start_line}-${hit.end_line})
              </div>
              <div class="search-hit-snippet">${escapeHtml(hit.content)}</div>
            </div>
          `;
        })
        .join("");
    } catch (err) {
      els.searchResultsList.innerHTML = `<div style="color: var(--accent-danger);">${escapeHtml(err.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 5: Literature Radar
  // ------------------------------------------------------------------------

  async function loadRadar() {
    if (!state.workspace) return;
    try {
      const radar = await apiFetch(`/api/workspace/radar?workspace=${encodeURIComponent(state.workspace)}`);
      els.radarSeenCount.textContent = radar.seen_total || 0;
      els.radarPendingCount.textContent = radar.pending_digests ? radar.pending_digests.length : 0;

      const digests = radar.digests || [];
      if (!digests.length) {
        els.digestFilesList.innerHTML = `<p style="padding: 1rem; color: var(--text-muted);">No digests found in inbox/radar/.</p>`;
        els.digestViewer.innerHTML = `<p style="color: var(--text-muted); text-align: center; margin-top: 3rem;">No digests generated yet.</p>`;
        return;
      }

      els.digestFilesList.innerHTML = digests
        .map((d, idx) => {
          const isPending = d.status === "pending-review";
          const badgeClass = isPending ? "badge-terracotta" : "badge-sage";
          return `
            <div class="pane-item ${idx === 0 ? "active" : ""}" data-file="${escapeHtml(d.name)}">
              <div style="font-weight: 500; font-size: 0.9rem;">${escapeHtml(d.name)}</div>
              <div style="margin-top: 0.3rem;">
                <span class="badge ${badgeClass}">${escapeHtml(d.status)}</span>
              </div>
            </div>
          `;
        })
        .join("");

      // Auto-load first digest
      if (digests.length > 0) {
        loadDigestContent(digests[0].name);
      }

      els.digestFilesList.querySelectorAll(".pane-item").forEach((item) => {
        item.addEventListener("click", () => {
          els.digestFilesList.querySelectorAll(".pane-item").forEach((i) => i.classList.remove("active"));
          item.classList.add("active");
          loadDigestContent(item.dataset.file);
        });
      });
    } catch (_) {}
  }

  async function loadDigestContent(filename) {
    if (!state.workspace || !filename) return;
    els.digestViewer.innerHTML = `<p style="color: var(--text-muted);">Loading ${escapeHtml(filename)}...</p>`;
    try {
      const data = await apiFetch(
        `/api/workspace/radar/digest?file=${encodeURIComponent(filename)}&workspace=${encodeURIComponent(state.workspace)}`
      );
      if (window.marked) {
        els.digestViewer.innerHTML = window.marked.parse(data.content);
      } else {
        els.digestViewer.textContent = data.content;
      }
    } catch (err) {
      els.digestViewer.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 6: Operations & SSE Terminal
  // ------------------------------------------------------------------------

  async function launchJob(command, name) {
    if (!state.workspace) {
      showToast("Please select an active workspace first.", "error");
      return;
    }

    try {
      const cmdParts = command.trim().split(/\s+/).filter(Boolean);
      const res = await apiFetch("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          command: cmdParts,
          workspace: state.workspace,
          name: name || command,
        }),
      });

      showToast(`Started background job: ${name || command}`, "info");
      switchTab("operations");
      startLogStream(res.job_id, name || command);
    } catch (err) {
      showToast(`Failed to dispatch job: ${err.message}`, "error");
    }
  }

  function startLogStream(jobId, jobName) {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }

    state.activeJobId = jobId;
    els.termJobName.textContent = `Terminal: ${jobName}`;
    els.termStatusDot.className = "status-dot running";
    els.termCancelBtn.style.display = "inline-flex";
    els.terminalOutput.textContent = `Connecting to log stream for job ${jobId}...\n`;

    const source = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/stream`);
    state.eventSource = source;

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "log") {
          els.terminalOutput.textContent += payload.line + "\n";
        } else if (payload.type === "status") {
          if (payload.status === "completed") {
            els.termStatusDot.className = "status-dot";
            els.termCancelBtn.style.display = "none";
            showToast(`Job '${jobName}' completed successfully.`, "success");
            source.close();
            loadSyncRatio();
          } else if (payload.status === "failed" || payload.status === "cancelled") {
            els.termStatusDot.className = "status-dot error";
            els.termCancelBtn.style.display = "none";
            showToast(`Job '${jobName}' ended (${payload.status}).`, "error");
            source.close();
          }
        }

        if (els.termAutoscroll.checked) {
          els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
        }
      } catch (_) {}
    };

    source.onerror = () => {
      source.close();
      els.termStatusDot.className = "status-dot";
      els.termCancelBtn.style.display = "none";
    };
  }

  // ------------------------------------------------------------------------
  // Tab 7: Documentation
  // ------------------------------------------------------------------------

  async function loadDocs(type) {
    els.docsContent.innerHTML = `<p style="color: var(--text-muted);">Loading documentation...</p>`;
    try {
      if (type === "commands") {
        const data = await apiFetch("/api/docs/commands");
        const cmds = data.commands || [];
        let html = `<h1>MAGI CLI Commands Reference</h1>`;
        html += `<p>Deterministic CLI operations catalog.</p>`;
        html += `<table class="data-table"><thead><tr><th>Command</th><th>Group</th><th>Description</th></tr></thead><tbody>`;
        cmds.forEach((c) => {
          html += `<tr><td><code>${escapeHtml(c.command)}</code></td><td><span class="badge badge-muted">${escapeHtml(c.group || "core")}</span></td><td>${escapeHtml(c.help)}</td></tr>`;
        });
        html += `</tbody></table>`;
        els.docsContent.innerHTML = html;
      } else {
        const data = await apiFetch("/api/docs/readme");
        const mdText = type === "readme-en" ? data.readme_en : data.readme_zh;
        if (window.marked && mdText) {
          els.docsContent.innerHTML = window.marked.parse(mdText);
        } else {
          els.docsContent.textContent = mdText || "No documentation found.";
        }
      }
    } catch (err) {
      els.docsContent.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // ------------------------------------------------------------------------
  // Doctor Check Modal
  // ------------------------------------------------------------------------

  async function openDoctorModal() {
    els.doctorModal.classList.add("open");
    els.doctorModalBody.innerHTML = `<p style="color: var(--text-muted);">Running diagnostic...</p>`;
    try {
      const data = await apiFetch("/api/doctor");
      const doc = data.doctor || [];
      const legacy = data.legacy || [];

      let html = `<table class="data-table" style="margin-bottom: 1rem;"><thead><tr><th>Component</th><th>Status</th><th>Detail / Path</th></tr></thead><tbody>`;
      doc.forEach((row) => {
        const mark = row.ok
          ? `<span class="badge badge-sage">OK</span>`
          : `<span class="badge badge-danger">Missing</span>`;
        html += `<tr><td><strong>${escapeHtml(row.tool)}</strong></td><td>${mark}</td><td><code style="font-size: 0.8rem;">${escapeHtml(row.detail)}</code></td></tr>`;
      });
      html += `</tbody></table>`;

      if (legacy.length > 0) {
        html += `<div style="margin-top: 1rem;"><strong style="color: var(--accent-danger);">Legacy Wikify copies detected (${legacy.length}):</strong><ul style="margin: 0.5rem 0 0 1.25rem; font-size: 0.85rem; font-family: var(--font-mono);">`;
        legacy.forEach((p) => {
          html += `<li>${escapeHtml(p)}</li>`;
        });
        html += `</ul><p style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary);">Remove them safely in Operations &gt; Danger Zone &gt; Remove Legacy Copies.</p></div>`;
      } else {
        html += `<p style="color: var(--accent-sage); font-size: 0.85rem;">✓ No legacy Wikify copies detected.</p>`;
      }

      els.doctorModalBody.innerHTML = html;
    } catch (err) {
      els.doctorModalBody.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // ------------------------------------------------------------------------
  // Event Listeners
  // ------------------------------------------------------------------------

  // Theme Toggle
  els.themeToggleBtn.addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark");
  });

  // Tab switching
  els.tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Workspace selector change
  els.workspaceSelect.addEventListener("change", (e) => {
    state.workspace = e.target.value;
    loadSyncRatio();
    loadTabData(state.activeTab);
  });

  // Refresh KB button
  els.refreshKbBtn.addEventListener("click", () => loadKBRegistry());

  // Register KB form
  els.registerKbForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const path = els.regKbPath.value.trim();
    const name = els.regKbName.value.trim() || null;
    const enabled = els.regKbEnabled.checked;
    if (!path) return;

    try {
      await apiFetch("/api/kb/register", {
        method: "POST",
        body: JSON.stringify({ path, name, enabled }),
      });
      showToast("Knowledge Base registered successfully.", "success");
      els.regKbPath.value = "";
      els.regKbName.value = "";
      loadKBRegistry();
    } catch (_) {}
  });

  // Refresh Claims
  els.refreshClaimsBtn.addEventListener("click", () => loadMelchior());

  // Graph SQL Console
  els.runSqlBtn.addEventListener("click", () => executeGraphSql(els.sqlQueryInput.value));
  els.presetSqlBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      els.sqlQueryInput.value = btn.dataset.sql;
      executeGraphSql(btn.dataset.sql);
    });
  });

  // Casper Search
  els.searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    executeSearch(
      els.searchQueryInput.value,
      els.searchModeSelect.value,
      parseInt(els.searchLimitSelect.value, 10)
    );
  });

  // Balthasar backlog sync
  els.btnBacklogSync.addEventListener("click", () => {
    launchJob("pm backlog-sync", "Sync Backlog to Beads");
  });

  // Radar actions
  els.btnRadarHarvest.addEventListener("click", () => {
    launchJob("radar harvest", "Radar Harvest");
  });
  els.btnRadarCitationGap.addEventListener("click", () => {
    launchJob("radar citation-gap", "Radar Citation Gap Scouting");
  });

  // Operations common buttons
  els.opTaskBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      launchJob(btn.dataset.cmd, btn.dataset.name);
    });
  });

  // Danger actions with 2-step confirmation modal
  els.dangerActionBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      pendingDangerCommand = {
        cmd: btn.dataset.cmd,
        title: btn.dataset.title,
        desc: btn.dataset.desc,
      };
      els.dangerModalTitle.textContent = `Danger Confirmation: ${pendingDangerCommand.title}`;
      els.dangerModalDesc.innerHTML = `
        <strong style="color: var(--accent-danger);">Warning:</strong> ${escapeHtml(pendingDangerCommand.desc)}
        <br><br>
        Command to be executed: <code>magi ${escapeHtml(pendingDangerCommand.cmd)}</code>
      `;
      els.dangerModal.classList.add("open");
    });
  });

  els.dangerModalCancel.addEventListener("click", () => {
    els.dangerModal.classList.remove("open");
    pendingDangerCommand = null;
  });

  els.dangerModalConfirm.addEventListener("click", () => {
    if (pendingDangerCommand) {
      launchJob(pendingDangerCommand.cmd, pendingDangerCommand.title);
    }
    els.dangerModal.classList.remove("open");
    pendingDangerCommand = null;
  });

  // Terminal buttons
  els.termClearBtn.addEventListener("click", () => {
    els.terminalOutput.textContent = "";
  });

  els.termCancelBtn.addEventListener("click", async () => {
    if (!state.activeJobId) return;
    try {
      await apiFetch(`/api/jobs/${encodeURIComponent(state.activeJobId)}/cancel`, { method: "POST" });
      showToast("Job cancellation requested.", "info");
    } catch (_) {}
  });

  // Docs switcher
  els.docSwitchBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      els.docSwitchBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadDocs(btn.dataset.doc);
    });
  });

  // Doctor check modal
  els.doctorBtn.addEventListener("click", openDoctorModal);
  els.doctorModalClose.addEventListener("click", () => {
    els.doctorModal.classList.remove("open");
  });

  // Init
  applyTheme(state.theme);
  loadInitialStatus();
})();
