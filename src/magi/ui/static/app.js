// MAGI WebUI Dashboard Frontend Controller & i18n Engine

(function () {
  "use strict";

  // ------------------------------------------------------------------------
  // I18N Translation Dictionary
  // ------------------------------------------------------------------------

  const I18N = {
    zh: {
      // Page & Brand
      page_title: "MAGI — 科研工作空间控制台",

      // Topbar
      workspace_label: "工作空间:",
      loading_workspaces: "加载工作空间中...",
      sync_label: "三核同步:",
      running_jobs_label: "运行中任务:",
      sync_ratio_tooltip: "Melchior / Balthasar / Casper 三核协同同步率",
      doctor_btn: "🩺 环境体检",
      doctor_btn_title: "环境依赖与规范体检",
      theme_btn_title: "切换深浅配色主题",
      magi_mode_btn: "⚡ MAGI 模式",
      magi_mode_btn_title: "开启/关闭 EVA NERV MAGI 战术主题",

      // Navigation Tabs
      tab_dashboard: "📊 课题总览",
      tab_melchior: "🧠 Melchior (认知状态)",
      tab_balthasar: "🎯 Balthasar (任务追踪)",
      tab_casper: "🔍 Casper (混合检索)",
      tab_radar: "📡 文献雷达",
      tab_operations: "⚙️ 运维与操作",
      tab_docs: "📖 文档与指引",

      // Dashboard Metrics
      dash_sync_label: "三核同步率",
      dash_sync_subtitle: "认知 + 任务 + 检索协同",
      dash_kb_label: "已注册知识库",
      dash_kb_subtitle: "全局知识联合",
      dash_radar_label: "待审阅简报",
      dash_radar_subtitle: "文献雷达追踪",
      dash_task_label: "科研任务状态",
      dash_task_subtitle: "待办及进行中任务",

      // Dashboard KB Table
      dash_kb_table_title: "已注册知识库",
      dash_kb_table_subtitle: "全局注册表位于 ~/.config/magi/registry.json",
      btn_refresh: "🔄 刷新",
      th_kb_name: "知识库名称",
      th_path: "路径",
      th_searchable: "联合检索",
      th_indexed: "检索索引",
      th_graph: "关系图谱",
      th_sync_ratio: "同步率",
      th_actions: "操作",
      loading_kbs: "正在加载知识库列表...",
      no_kbs_registered: "当前尚未注册任何知识库。",
      badge_current: "当前",
      badge_indexed: "已索引",
      badge_no_index: "无索引",
      badge_graph_built: "已构建",
      badge_graph_missing: "未构建",
      btn_switch_ws: "切换",
      btn_unreg_kb: "移除",
      unreg_confirm: "确定要注销知识库 '{name}' 吗？（不会删除物理文件）",

      // Register Form
      reg_kb_title: "注册新知识库",
      reg_kb_subtitle: "将课题目录加入全局注册表",
      reg_kb_path_ph: "绝对或相对目录路径...",
      reg_kb_name_ph: "自定义名称（可选）...",
      reg_kb_enable_label: "启用联合检索",
      btn_reg_kb: "注册知识库",

      // Melchior (Cognitive State)
      mel_concepts_label: "概念卡片",
      mel_concepts_subtitle: "核心概念实体",
      mel_refs_label: "参考文献",
      mel_refs_subtitle: "结构化文献卡片",
      mel_graph_label: "知识图谱状态",
      mel_graph_subtitle: "概念关联网络",
      graph_fresh: "已同步",
      graph_missing_status: "未构建/待同步",
      mel_claims_label: "命题论据验证",
      mel_claims_title: "命题与论据溯源层",
      mel_claims_subtitle: "经本地卡片或网络来源验证的形式化学术断言",
      btn_refresh_claims: "🔄 刷新命题",
      th_claim_status: "状态",
      th_claim_text: "命题内容",
      th_claim_evidence: "论据引文",
      th_claim_source: "来源文献",
      loading_claims: "正在加载学术命题...",
      no_claims: "图谱与卡片中尚未记录任何形式化命题。",
      status_verified: "已验证",
      status_unverified: "待验证",
      status_web_verified: "网络验证",
      claims_verified_rate: "{rate}% 已验证",
      mel_backlog_title: "待编译原始文献",
      mel_backlog_subtitle: "raw/ 目录中尚未编译为结构化参考卡片的原始文档",
      clean_backlog: "干净：无未编译原始文件。",
      items_unit: "项",
      mel_sql_title: "知识图谱只读查询",
      mel_sql_subtitle: "通过 SQLite 安全只读机制查询节点、关系、命题与标签",
      preset_nodes: "节点",
      preset_links: "维基链接",
      preset_claims: "命题",
      sql_query_ph: "SELECT * FROM nodes WHERE type='concept' LIMIT 10",
      btn_run_sql: "执行查询",
      sql_run_prompt: "在上方输入 SQL 查询以查看表格结果。",
      sql_executing: "正在执行查询...",
      sql_zero_rows: "查询返回 0 行结果。",

      // Balthasar (Tasks)
      bal_title: "科研任务流追踪",
      bal_subtitle: "确定性工作流与任务图谱",
      btn_backlog_sync: "🔄 待办文献转任务",
      bal_engine_not_ready: "科研任务追踪引擎未就绪或未安装。请运行 <code>magi setup</code> 初始化工作流引擎。",
      bal_no_db_initialized: "当前工作区或 Hub 尚未初始化任务追踪库。点击下方初始化任务工作流。",
      bal_ready_label: "可执行",
      bal_ready_sub: "可直接启动的任务",
      bal_progress_label: "进行中",
      bal_progress_sub: "正在执行的任务",
      bal_blocked_label: "阻塞",
      bal_blocked_sub: "等待前置依赖",
      bal_open_label: "未完成总数",
      bal_open_sub: "全部待办及进行中任务",
      unit_ready: "项就绪",
      task_engine_offline: "引擎未就绪",

      // Casper (Retrieval)
      cas_title: "智能混合检索",
      cas_subtitle: "FTS5 BM25 全文检索 + 向量嵌入 + RRF 倒数排名融合",
      search_input_ph: "检索概念、实验发现或文献内容...",
      opt_hybrid: "混合检索 (BM25 + 向量)",
      opt_bm25: "仅 BM25",
      opt_vector: "仅向量",
      opt_limit_5: "前 5 项",
      opt_limit_10: "前 10 项",
      opt_limit_20: "前 20 项",
      btn_search: "检索",
      search_prompt: "输入检索关键词以查看混合排名结果与内容片段。",
      searching_text: "正在全库检索中...",
      search_no_results: "未找到匹配的段落内容。",
      search_summary: "找到 {total} 条结果 · BM25 命中: {bm25} · 向量检索: {vec}",
      search_lines: "行 {start}-{end}",
      vec_avail_yes: "可用",
      vec_avail_no: "未启用",

      // Literature Radar
      radar_seen_label: "已跟踪文献记录",
      radar_seen_sub: "文献雷达跟踪记录",
      radar_pending_label: "待审阅简报",
      radar_pending_sub: "等待 Agent 审阅分流",
      btn_radar_harvest: "📡 运行文献雷达扫描",
      btn_radar_citation_gap: "🔎 侦察引文缺口",
      radar_digests_title: "文献简报 (inbox/radar/)",
      loading_digests: "正在加载文献简报...",
      no_digests: "inbox/radar/ 中未发现任何简报文件。",
      digest_viewer_prompt: "在左侧选择文献简报以阅读和审阅。",
      digest_loading: "正在加载简报 {file}...",
      status_pending_review: "待审阅",
      status_reviewed: "已审阅",

      // Operations & Danger Zone
      ops_common_title: "常用维护操作",
      ops_common_sub: "非破坏性例行程序",
      op_rebuild_index: "🔍 重建检索索引",
      op_build_graph: "🕸️ 构建知识图谱",
      op_reindex_wiki: "📑 重建维基索引",
      op_semantic_link: "🔗 语义概念链接",
      op_lint_fix: "🧹 规范检查与修复",
      op_backlog_sync: "🎯 待办文献转任务",
      op_index: "🔍 重建检索索引",
      op_graph_build: "🕸️ 构建知识图谱",
      op_wiki_reindex: "📑 重建维基索引",
      op_link: "🔗 语义概念链接",
      danger_title: "⚠️ 危险操作区",
      danger_sub: "这些操作将修改工作区结构、重置状态或清理历史文件。每项操作均需二次确认。",
      btn_danger_setup: "环境一键配置",
      btn_danger_migrate: "工作区结构迁移",
      btn_danger_pm_init: "初始化任务工作流",
      btn_danger_legacy: "清理旧版历史文件",

      // Danger Actions Meta & Modals
      danger_modal_title: "确认操作",
      danger_modal_default_desc: "确定要继续执行此操作吗？",
      danger_setup_title: "环境一键配置",
      danger_setup_desc: "为当前环境重新配置任务引擎、Ollama 模型与 Claude 插件。",
      danger_migrate_title: "工作区结构迁移",
      danger_migrate_desc: "将旧版工作区布局迁移至 MAGI 标准规范。",
      danger_pm_init_title: "初始化任务工作流",
      danger_pm_init_desc: "在 Hub 目录初始化科研任务追踪数据库。",
      danger_remove_legacy_title: "清理旧版历史文件",
      danger_remove_legacy_desc: "永久清理 ~/.claude/skills 与 ~/.gemini/skills 中的旧版脚本。",
      danger_modal_prefix: "危险操作确认",
      warning_label: "警告",
      cmd_to_execute: "即将执行命令",
      btn_modal_cancel: "取消",
      btn_modal_confirm: "确认执行",

      // Live Terminal
      term_idle: "终端：空闲",
      term_running: "终端：正在执行 ({name})",
      term_autoscroll_label: "自动滚动",
      btn_term_cancel: "中止任务",
      btn_term_clear: "清屏",
      term_ready_msg: "就绪。点击上方操作查看实时执行日志。",
      term_connecting: "正在连接后台任务 {id} 的日志流...\n",

      // Docs
      doc_readme_zh: "README (中文)",
      doc_readme_en: "README (English)",
      doc_commands: "CLI 命令参考手册",
      loading_docs: "正在加载文档...",
      no_docs_found: "未找到相关文档。",
      docs_cmd_title: "MAGI CLI 命令速查手册",
      docs_cmd_sub: "确定性学术命令参考目录。",
      th_cmd_command: "命令",
      th_cmd_group: "分组",
      th_cmd_desc: "说明",

      // Doctor Modal
      doc_modal_title: "环境体检诊断报告",
      doctor_loading: "正在加载环境诊断信息...",
      doctor_running: "正在进行环境体检诊断...",
      doctor_th_comp: "组件",
      doctor_th_status: "状态",
      doctor_th_detail: "详情 / 路径",
      badge_ok: "正常",
      badge_missing: "缺失",
      doctor_legacy_found: "检测到旧版冲突文件 ({count}):",
      doctor_legacy_hint: "您可在「运维与操作」>「危险操作区」>「清理旧版历史文件」中安全清理。",
      doctor_clean: "✓ 未检测到旧版冲突文件，环境处于良好状态。",
      btn_doc_close: "关闭",

      // Toasts & Alerts
      toast_select_ws_first: "请先选择一个有效的工作空间。",
      toast_job_started: "已启动后台任务: {name}",
      toast_job_success: "任务 '{name}' 执行成功。",
      toast_job_ended: "任务 '{name}' 已结束 ({status})。",
      toast_job_cancel_req: "已请求中止任务。",
      toast_job_fail: "启动任务失败: {error}",
      toast_kb_registered: "知识库注册成功。",
      toast_kb_status_updated: "知识库 '{name}' 检索状态已更新。",
      toast_ws_switched: "已切换当前工作空间。",
      toast_kb_unregistered: "已注销知识库 '{name}'。",
    },

    en: {
      // Page & Brand
      page_title: "MAGI — Research Workspace WebUI",

      // Topbar
      workspace_label: "Workspace:",
      loading_workspaces: "Loading workspaces...",
      sync_label: "Sync:",
      running_jobs_label: "Running Jobs:",
      sync_ratio_tooltip: "Three-core sync ratio (Melchior + Balthasar + Casper)",
      doctor_btn: "🩺 Doctor",
      doctor_btn_title: "Environment Doctor Check",
      theme_btn_title: "Toggle Light/Dark Theme",
      magi_mode_btn: "⚡ MAGI MODE",
      magi_mode_btn_title: "Toggle EVA NERV MAGI Command Theme",

      // Navigation Tabs
      tab_dashboard: "📊 Dashboard",
      tab_melchior: "🧠 Melchior (Cognitive)",
      tab_balthasar: "🎯 Balthasar (Tasks)",
      tab_casper: "🔍 Casper (Retrieval)",
      tab_radar: "📡 Literature Radar",
      tab_operations: "⚙️ Operations & Danger Zone",
      tab_docs: "📖 Docs & Help",

      // Dashboard Metrics
      dash_sync_label: "Sync Ratio",
      dash_sync_subtitle: "Melchior + Balthasar + Casper",
      dash_kb_label: "Registered KBs",
      dash_kb_subtitle: "Global federation",
      dash_radar_label: "Pending Digests",
      dash_radar_subtitle: "Literature radar",
      dash_task_label: "Active Task State",
      dash_task_subtitle: "Actionable tasks",

      // Dashboard KB Table
      dash_kb_table_title: "Registered Knowledge Bases",
      dash_kb_table_subtitle: "Global registry located at ~/.config/magi/registry.json",
      btn_refresh: "🔄 Refresh",
      th_kb_name: "KB Name",
      th_path: "Path",
      th_searchable: "Searchable",
      th_indexed: "Indexed",
      th_graph: "Graph",
      th_sync_ratio: "Sync Ratio",
      th_actions: "Actions",
      loading_kbs: "Loading knowledge bases...",
      no_kbs_registered: "No knowledge bases registered yet.",
      badge_current: "current",
      badge_indexed: "Indexed",
      badge_no_index: "No Index",
      badge_graph_built: "Built",
      badge_graph_missing: "Missing",
      btn_switch_ws: "Switch",
      btn_unreg_kb: "Remove",
      unreg_confirm: "Unregister KB '{name}'? (Workspace files will remain untouched)",

      // Register Form
      reg_kb_title: "Register New Knowledge Base",
      reg_kb_subtitle: "Add a topic directory to the global registry",
      reg_kb_path_ph: "Absolute or relative path...",
      reg_kb_name_ph: "Custom name (optional)...",
      reg_kb_enable_label: "Enable in search",
      btn_reg_kb: "Register KB",

      // Melchior (Cognitive State)
      mel_concepts_label: "Concepts",
      mel_concepts_subtitle: "Core concept entities",
      mel_refs_label: "References",
      mel_refs_subtitle: "Structured reference cards",
      mel_graph_label: "Graph Freshness",
      mel_graph_subtitle: "Knowledge graph network",
      graph_fresh: "fresh",
      graph_missing_status: "missing",
      mel_claims_label: "Claims Verified",
      mel_claims_title: "Claims & Evidence Provenance Layer",
      mel_claims_subtitle: "Formal assertions verified against local wiki cards or web sources",
      btn_refresh_claims: "🔄 Refresh Claims",
      th_claim_status: "Status",
      th_claim_text: "Claim",
      th_claim_evidence: "Evidence Quote",
      th_claim_source: "Source",
      loading_claims: "Loading claims...",
      no_claims: "No claims recorded in graph or cards.",
      status_verified: "verified",
      status_unverified: "unverified",
      status_web_verified: "web-verified",
      claims_verified_rate: "{rate}% verified",
      mel_backlog_title: "Uncompiled Raw Document Backlog",
      mel_backlog_subtitle: "Raw ingested files in raw/ without a compiled reference in wiki/references/",
      clean_backlog: "Clean: No uncompiled raw files.",
      items_unit: "items",
      mel_sql_title: "Read-Only Graph SQL Console",
      mel_sql_subtitle: "Query nodes, edges, claims, and tags via SQLite read-only guard",
      preset_nodes: "Nodes",
      preset_links: "Wikilinks",
      preset_claims: "Claims",
      sql_query_ph: "SELECT * FROM nodes WHERE type='concept' LIMIT 10",
      btn_run_sql: "Execute SQL",
      sql_run_prompt: "Run a query above to see tabular results.",
      sql_executing: "Executing query...",
      sql_zero_rows: "Query returned 0 rows.",

      // Balthasar (Tasks)
      bal_title: "Research Task Tracking",
      bal_subtitle: "Deterministic work graph and issue tracker",
      btn_backlog_sync: "🔄 Sync Backlog to Tasks",
      bal_engine_not_ready: "Task tracking engine is not ready or not installed. Run <code>magi setup</code> to initialize workflow engine.",
      bal_no_db_initialized: "No task tracking workspace initialized at workspace or hub. Click below to initialize task tracking.",
      bal_ready_label: "Ready",
      bal_ready_sub: "Actionable tasks",
      bal_progress_label: "In Progress",
      bal_progress_sub: "Active execution",
      bal_blocked_label: "Blocked",
      bal_blocked_sub: "Awaiting dependencies",
      bal_open_label: "Open Total",
      bal_open_sub: "All pending tasks",
      unit_ready: "ready",
      task_engine_offline: "Engine offline",

      // Casper (Retrieval)
      cas_title: "Casper Hybrid Retrieval Playground",
      cas_subtitle: "FTS5 BM25 + sqlite-vec embeddings + RRF (Reciprocal Rank Fusion)",
      search_input_ph: "Search concepts, findings, or literature...",
      opt_hybrid: "Hybrid (BM25 + Vector)",
      opt_bm25: "BM25 Only",
      opt_vector: "Vector Only",
      opt_limit_5: "Top 5",
      opt_limit_10: "Top 10",
      opt_limit_20: "Top 20",
      btn_search: "Search",
      search_prompt: "Enter a search query to inspect hybrid ranking and excerpts.",
      searching_text: "Searching corpus...",
      search_no_results: "No matching passages found.",
      search_summary: "Found {total} hit(s) · BM25 hits: {bm25} · Vector available: {vec}",
      search_lines: "lines {start}-{end}",
      vec_avail_yes: "Yes",
      vec_avail_no: "No",

      // Literature Radar
      radar_seen_label: "Seen Papers Ledger",
      radar_seen_sub: "Literature tracking ledger",
      radar_pending_label: "Pending Digests",
      radar_pending_sub: "Awaiting agent triage",
      btn_radar_harvest: "📡 Run Radar Harvest",
      btn_radar_citation_gap: "🔎 Scout Citation Gaps",
      radar_digests_title: "Digests (inbox/radar/)",
      loading_digests: "Loading digests...",
      no_digests: "No digests found in inbox/radar/.",
      digest_viewer_prompt: "Select a digest file on the left to read and review.",
      digest_loading: "Loading {file}...",
      status_pending_review: "pending-review",
      status_reviewed: "reviewed",

      // Operations & Danger Zone
      ops_common_title: "Common Maintenance Operations",
      ops_common_sub: "Non-destructive routines",
      op_rebuild_index: "🔍 Rebuild Index",
      op_build_graph: "🕸️ Build Graph",
      op_reindex_wiki: "📑 Reindex Wiki Tables",
      op_semantic_link: "🔗 Semantic Link",
      op_lint_fix: "🧹 Lint & Auto-Fix",
      op_backlog_sync: "🎯 Backlog to Tasks",
      op_index: "🔍 Rebuild Index",
      op_graph_build: "🕸️ Build Graph",
      op_wiki_reindex: "📑 Reindex Wiki Tables",
      op_link: "🔗 Semantic Link",
      danger_title: "⚠️ Danger Zone",
      danger_sub: "These operations alter workspace structure, reset state, or delete legacy files. Each action requires explicit confirmation.",
      btn_danger_setup: "Provision Setup",
      btn_danger_migrate: "Migrate Workspace",
      btn_danger_pm_init: "Initialize Task Tracking",
      btn_danger_legacy: "Remove Legacy Copies",

      // Danger Actions Meta & Modals
      danger_modal_title: "Confirm Action",
      danger_modal_default_desc: "Are you sure you want to proceed with this operation?",
      danger_setup_title: "Environment Setup",
      danger_setup_desc: "Re-provision task engine, Ollama models, and Claude plugins for the current environment.",
      danger_migrate_title: "Migrate Workspace",
      danger_migrate_desc: "Migrate old workspace layouts and files to the MAGI standard.",
      danger_pm_init_title: "Initialize Task Tracking",
      danger_pm_init_desc: "Initialize the task tracking database in the hub directory.",
      danger_remove_legacy_title: "Remove Legacy Copies",
      danger_remove_legacy_desc: "Permanently delete old pre-MAGI scripts in ~/.claude/skills and ~/.gemini/skills.",
      danger_modal_prefix: "Danger Confirmation",
      warning_label: "Warning",
      cmd_to_execute: "Command to be executed",
      btn_modal_cancel: "Cancel",
      btn_modal_confirm: "Confirm & Run",

      // Live Terminal
      term_idle: "Terminal: Idle",
      term_running: "Terminal: Running ({name})",
      term_autoscroll_label: "Auto-scroll",
      btn_term_cancel: "Cancel Job",
      btn_term_clear: "Clear",
      term_ready_msg: "Ready. Run an operation above to view real-time log output.",
      term_connecting: "Connecting to log stream for job {id}...\n",

      // Docs
      doc_readme_zh: "README (中文)",
      doc_readme_en: "README (English)",
      doc_commands: "CLI Commands Reference",
      loading_docs: "Loading documentation...",
      no_docs_found: "No documentation found.",
      docs_cmd_title: "MAGI CLI Commands Reference",
      docs_cmd_sub: "Deterministic CLI operations catalog.",
      th_cmd_command: "Command",
      th_cmd_group: "Group",
      th_cmd_desc: "Description",

      // Doctor Modal
      doc_modal_title: "Environment Doctor Report",
      doctor_loading: "Loading environment diagnostic...",
      doctor_running: "Running environment diagnostic...",
      doctor_th_comp: "Component",
      doctor_th_status: "Status",
      doctor_th_detail: "Detail / Path",
      badge_ok: "OK",
      badge_missing: "Missing",
      doctor_legacy_found: "Legacy copies detected ({count}):",
      doctor_legacy_hint: "You can safely remove them in Operations > Danger Zone > Remove Legacy Copies.",
      doctor_clean: "✓ No legacy copies detected. Environment is healthy.",
      btn_doc_close: "Close",

      // Toasts & Alerts
      toast_select_ws_first: "Please select an active workspace first.",
      toast_job_started: "Started background job: {name}",
      toast_job_success: "Job '{name}' completed successfully.",
      toast_job_ended: "Job '{name}' ended ({status}).",
      toast_job_cancel_req: "Job cancellation requested.",
      toast_job_fail: "Failed to dispatch job: {error}",
      toast_kb_registered: "Knowledge Base registered successfully.",
      toast_kb_status_updated: "KB '{name}' search status updated.",
      toast_ws_switched: "Switched active workspace.",
      toast_kb_unregistered: "Unregistered KB '{name}'.",
    },
  };

  // Safe localStorage helpers
  function safeStorageGet(key, fallback = null) {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        return window.localStorage.getItem(key) || fallback;
      }
    } catch (_) {}
    return fallback;
  }

  function safeStorageSet(key, value) {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.setItem(key, value);
      }
    } catch (_) {}
  }

  // Helper for translating strings
  function t(key, params = {}) {
    const lang = state.lang || "zh";
    let str = (I18N[lang] && I18N[lang][key]) || (I18N.en && I18N.en[key]) || key;
    for (const [k, v] of Object.entries(params)) {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), v);
    }
    return str;
  }

  // Detect default language
  function detectInitialLanguage() {
    const saved = safeStorageGet("magi-lang");
    if (saved && typeof saved === "string") {
      const s = saved.trim().toLowerCase();
      if (s.startsWith("zh")) return "zh";
      if (s.startsWith("en")) return "en";
    }
    let nav = "";
    if (typeof navigator !== "undefined") {
      if (Array.isArray(navigator.languages) && navigator.languages.length > 0 && navigator.languages[0]) {
        nav = String(navigator.languages[0]).toLowerCase();
      } else if (navigator.language) {
        nav = String(navigator.language).toLowerCase();
      } else if (navigator.userLanguage) {
        nav = String(navigator.userLanguage).toLowerCase();
      }
    }
    return nav.startsWith("zh") ? "zh" : "en";
  }

  // Detect default theme
  function detectInitialTheme() {
    // Deep-link override: ?theme=eva|dark|light
    try {
      const urlTheme = new URLSearchParams(window.location.search).get("theme");
      if (urlTheme === "eva" || urlTheme === "dark" || urlTheme === "light") {
        return urlTheme;
      }
    } catch (_) {}
    const savedTheme = safeStorageGet("magi-theme");
    const savedMagiMode = safeStorageGet("magi-mode");
    if (savedTheme === "eva" || savedMagiMode === "true") {
      return "eva";
    }
    if (savedTheme === "dark" || savedTheme === "light") {
      return savedTheme;
    }
    if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      return "dark";
    }
    return "light";
  }

  // ------------------------------------------------------------------------
  // State
  // ------------------------------------------------------------------------

  const state = {
    workspace: "",
    kbs: [],
    activeTab: "dashboard",
    activeDoc: "readme",
    activeJobId: null,
    activeJobName: "",
    eventSource: null,
    theme: detectInitialTheme(),
    lang: detectInitialLanguage(),
  };

  // ------------------------------------------------------------------------
  // DOM Elements
  // ------------------------------------------------------------------------

  const els = {
    themeToggleBtn: document.getElementById("theme-toggle-btn"),
    magiModeBtn: document.getElementById("magi-mode-btn"),
    evaClock: document.getElementById("eva-clock"),
    evaBoot: document.getElementById("eva-boot"),
    langToggle: document.getElementById("lang-toggle"),
    langBtnZh: document.getElementById("lang-btn-zh"),
    langBtnEn: document.getElementById("lang-btn-en"),
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
    dashTaskReady: document.getElementById("dash-task-ready"),
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

    // Balthasar (Tasks)
    taskStatusBanner: document.getElementById("task-status-banner"),
    taskReadyVal: document.getElementById("task-ready-val"),
    taskProgressVal: document.getElementById("task-progress-val"),
    taskBlockedVal: document.getElementById("task-blocked-val"),
    taskOpenVal: document.getElementById("task-open-val"),
    btnBacklogSync: document.getElementById("btn-backlog-sync"),

    // Casper (Retrieval)
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
    safeStorageSet("magi-theme", theme);
    if (theme === "eva") {
      safeStorageSet("magi-mode", "true");
      if (els.magiModeBtn) {
        els.magiModeBtn.classList.add("active");
      }
      const base = safeStorageGet("magi-base-theme") || "dark";
      if (els.themeToggleBtn) {
        els.themeToggleBtn.textContent = base === "dark" ? "☀️" : "🌓";
      }
    } else {
      safeStorageSet("magi-mode", "false");
      safeStorageSet("magi-base-theme", theme);
      if (els.magiModeBtn) {
        els.magiModeBtn.classList.remove("active");
      }
      if (els.themeToggleBtn) {
        els.themeToggleBtn.textContent = theme === "dark" ? "☀️" : "🌓";
      }
    }
  }

  // ------------------------------------------------------------------------
  // EVA MAGI MODE: mission clock, boot sequence, tri-monolith HUD
  // ------------------------------------------------------------------------

  let evaClockTimer = null;
  let evaBootTimer = null;

  function startEvaClock() {
    if (!els.evaClock || evaClockTimer) return;
    const pad = (n) => String(n).padStart(2, "0");
    const tick = () => {
      const d = new Date();
      els.evaClock.textContent =
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
        `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };
    tick();
    evaClockTimer = setInterval(tick, 1000);
  }

  function runEvaBoot() {
    const b = els.evaBoot;
    if (!b) return;
    if (typeof window !== "undefined" && window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    b.classList.remove("active");
    void b.offsetWidth; // restart CSS animations from frame zero
    b.classList.add("active");
    if (evaBootTimer) clearTimeout(evaBootTimer);
    evaBootTimer = setTimeout(() => b.classList.remove("active"), 2600);
  }

  // Map a sync-report core dict onto HUD state class + tactical readout
  function evaCoreState(kind, core) {
    if (!core) return { cls: "state-off", stat: "NO LINK", detail: "--" };
    if (kind === "mel") {
      const detail = `${core.concepts || 0} CPT / ${core.references || 0} REF / CLM ${core.claims_verified || 0}/${core.claims || 0}`;
      if (core.graph === "fresh") return { cls: "state-ok", stat: "NOMINAL", detail };
      if (core.graph === "empty-wiki") return { cls: "state-warn", stat: "STANDBY", detail };
      if (core.graph === "stale") return { cls: "state-warn", stat: "STALE", detail };
      return { cls: "state-warn", stat: "NO GRAPH", detail };
    }
    if (kind === "bal") {
      if (core.state === "disabled") return { cls: "state-off", stat: "OFFLINE", detail: "KB-ONLY PROFILE" };
      if (!core.bd_installed) return { cls: "state-err", stat: "NO ENGINE", detail: "RUN MAGI SETUP" };
      if (!core.beads_root) return { cls: "state-warn", stat: "STANDBY", detail: "PM NOT INITIALIZED" };
      return {
        cls: "state-ok",
        stat: "NOMINAL",
        detail: `RDY ${core.ready ?? 0} / ACT ${core.in_progress ?? 0} / BLK ${core.blocked ?? 0}`,
      };
    }
    // casper
    if (core.state === "missing" || core.state === "offline") {
      return { cls: "state-err", stat: "NO INDEX", detail: "RUN MAGI INDEX" };
    }
    const casDetail = `${core.chunks || 0} CHUNKS / ${core.vectors || 0} VEC`;
    if (core.state === "stale") return { cls: "state-warn", stat: "STALE", detail: casDetail };
    return { cls: "state-ok", stat: "NOMINAL", detail: casDetail };
  }

  function updateEvaHud(rep) {
    const hud = document.getElementById("eva-hud");
    if (!hud) return;
    const cores = (rep && rep.cores) || {};
    const mapping = { mel: "melchior", bal: "balthasar", cas: "casper" };
    for (const [short, full] of Object.entries(mapping)) {
      const st = evaCoreState(short, cores[full] || null);
      const g = document.getElementById(`eva-core-${short}`);
      const statEl = document.getElementById(`eva-${short}-stat`);
      const detEl = document.getElementById(`eva-${short}-detail`);
      if (g) {
        g.classList.remove("state-ok", "state-warn", "state-err", "state-off");
        g.classList.add(st.cls);
      }
      if (statEl) statEl.textContent = st.stat;
      if (detEl) detEl.textContent = st.detail;
    }

    const ratio = rep && rep.sync_ratio !== null && rep.sync_ratio !== undefined ? rep.sync_ratio : null;
    const syncEl = document.getElementById("eva-sync-val");
    if (syncEl) syncEl.textContent = ratio !== null ? `${ratio}%` : "--%";

    const modeEl = document.getElementById("eva-hud-mode");
    if (modeEl) {
      let mode = "STANDBY";
      if (ratio === 100) mode = "NOMINAL";
      else if (ratio !== null && ratio < 60) mode = "ALERT";
      modeEl.textContent = `MODE : ${mode}`;
      modeEl.classList.toggle("eva-alert", mode === "ALERT");
    }
  }

  // ------------------------------------------------------------------------
  // Language & i18n Switcher
  // ------------------------------------------------------------------------

  function setLanguage(lang) {
    state.lang = (lang && String(lang).trim().toLowerCase().startsWith("en")) ? "en" : "zh";
    safeStorageSet("magi-lang", state.lang);
    document.documentElement.setAttribute("lang", state.lang);
    document.title = t("page_title");

    // Update switcher pills
    if (els.langBtnZh && els.langBtnEn) {
      els.langBtnZh.classList.toggle("active", state.lang === "zh");
      els.langBtnEn.classList.toggle("active", state.lang === "en");
    }

    // Update all static i18n attributes in the DOM
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) {
        el.innerHTML = t(key);
      }
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) {
        el.placeholder = t(key);
      }
    });

    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      const key = el.getAttribute("data-i18n-title");
      if (key) {
        el.title = t(key);
      }
    });

    // Update terminal idle message if not running
    if (!state.activeJobId && els.termJobName) {
      els.termJobName.textContent = t("term_idle");
    }

    // Re-render workspace select dropdown labels
    renderWorkspaceSelect();

    // Re-render doctor modal if open
    if (els.doctorModal && els.doctorModal.classList.contains("open")) {
      openDoctorModal();
    }

    // Re-render open danger modal with localized content if active
    if (pendingDangerCommand && els.dangerModal && els.dangerModal.classList.contains("open")) {
      const action = pendingDangerCommand.action;
      const title = t(`danger_${action}_title`);
      const desc = t(`danger_${action}_desc`);
      pendingDangerCommand.title = title;
      els.dangerModalTitle.textContent = `${t("danger_modal_prefix")}: ${title}`;
      els.dangerModalDesc.innerHTML = `
        <strong style="color: var(--accent-danger);">${t("warning_label")}:</strong> ${escapeHtml(desc)}
        <br><br>
        ${t("cmd_to_execute")}: <code>magi ${escapeHtml(pendingDangerCommand.cmd)}</code>
      `;
    }

    // Refresh dynamic data of active tab
    if (state.activeTab === "docs") {
      loadDocs(state.activeDoc === "commands" ? "commands" : (state.lang === "zh" ? "readme-zh" : "readme-en"));
    } else {
      loadTabData(state.activeTab);
    }
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
        loadDocs(state.activeDoc === "commands" ? "commands" : (state.lang === "zh" ? "readme-zh" : "readme-en"));
        break;
    }
  }

  // ------------------------------------------------------------------------
  // Workspace & Global Status
  // ------------------------------------------------------------------------

  function renderWorkspaceSelect() {
    if (!els.workspaceSelect) return;
    const currentVal = els.workspaceSelect.value || state.workspace;
    els.workspaceSelect.innerHTML = "";
    state.kbs.forEach((kb) => {
      const opt = document.createElement("option");
      opt.value = kb.path;
      opt.textContent = `${kb.name}${kb.current ? ` (${t("badge_current")})` : ""}`;
      if (kb.path === currentVal || (!currentVal && kb.current)) {
        opt.selected = true;
      }
      els.workspaceSelect.appendChild(opt);
    });

    const hasCurrentInKBs = state.kbs.some((kb) => kb.path === state.workspace);
    if (state.workspace && !hasCurrentInKBs) {
      const opt = document.createElement("option");
      opt.value = state.workspace;
      opt.textContent = `${state.workspace} (${t("badge_current")})`;
      opt.selected = true;
      els.workspaceSelect.appendChild(opt);
    }
  }

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

      renderWorkspaceSelect();
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
      updateEvaHud(rep);
    } catch (err) {
      els.syncRatioVal.textContent = "--%";
      updateEvaHud(null);
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
        const pendingN = radar.pending_digests ? radar.pending_digests.length : 0;
        els.dashPendingDigests.textContent = pendingN;
        els.dashPendingDigests.classList.toggle("eva-alert", pendingN > 0);
      } catch (_) {}

      try {
        const pm = await apiFetch(`/api/workspace/pm?workspace=${encodeURIComponent(state.workspace)}`);
        const engineReady = (pm.task_engine_ready !== undefined ? pm.task_engine_ready : pm.beads_available);
        if (pm.summary) {
          els.dashTaskReady.textContent = `${pm.summary.ready || 0} ${t("unit_ready")}`;
        } else {
          els.dashTaskReady.textContent = engineReady ? `0 ${t("unit_ready")}` : t("task_engine_offline");
        }
      } catch (_) {}
    }
  }

  function renderKBTable(kbs) {
    if (!kbs.length) {
      els.kbTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">${t("no_kbs_registered")}</td></tr>`;
      return;
    }

    els.kbTableBody.innerHTML = kbs
      .map((kb) => {
        const syncBadge = kb.sync_ratio !== null && kb.sync_ratio !== undefined
          ? `<span class="badge ${kb.sync_ratio === 100 ? "badge-sage" : "badge-terracotta"}">${kb.sync_ratio}%</span>`
          : `<span class="badge badge-muted">--</span>`;

        const indexedBadge = kb.indexed
          ? `<span class="badge badge-sage">${t("badge_indexed")}</span>`
          : `<span class="badge badge-danger">${t("badge_no_index")}</span>`;

        const graphBadge = kb.graph_built
          ? `<span class="badge badge-sage">${t("badge_graph_built")}</span>`
          : `<span class="badge badge-danger">${t("badge_graph_missing")}</span>`;

        return `
          <tr>
            <td>
              <strong>${escapeHtml(kb.name)}</strong>
              ${kb.current ? `<span class="badge badge-terracotta" style="margin-left: 0.4rem;">${t("badge_current")}</span>` : ""}
            </td>
            <td><code style="font-size: 0.8rem;">${escapeHtml(kb.path)}</code></td>
            <td>
              <input type="checkbox" class="kb-toggle-cb" data-name="${escapeHtml(kb.name)}" ${kb.enabled ? "checked" : ""}>
            </td>
            <td>${indexedBadge}</td>
            <td>${graphBadge}</td>
            <td>${syncBadge}</td>
            <td>
              <button class="btn btn-secondary btn-sm switch-ws-btn" data-path="${escapeHtml(kb.path)}">${t("btn_switch_ws")}</button>
              <button class="btn btn-danger btn-sm unreg-kb-btn" data-name="${escapeHtml(kb.name)}">${t("btn_unreg_kb")}</button>
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
          showToast(t("toast_kb_status_updated", { name }), "success");
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
        showToast(t("toast_ws_switched"), "info");
      });
    });

    els.kbTableBody.querySelectorAll(".unreg-kb-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const name = btn.dataset.name;
        if (!confirm(t("unreg_confirm", { name }))) return;
        try {
          await apiFetch(`/api/kb/${encodeURIComponent(name)}`, { method: "DELETE" });
          showToast(t("toast_kb_unregistered", { name }), "info");
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
      els.melchiorGraphStatus.textContent = mel.graph === "fresh" ? t("graph_fresh") : t("graph_missing_status");
      els.melchiorGraphStatus.style.color = mel.graph === "fresh" ? "var(--accent-sage)" : "var(--accent-danger)";
    } catch (_) {}

    // Load Claims
    try {
      const claimsData = await apiFetch(`/api/workspace/claims?workspace=${encodeURIComponent(state.workspace)}`);
      const claims = claimsData.claims || [];
      els.melchiorClaimsVal.textContent = `${claimsData.verified || 0} / ${claimsData.total || 0}`;
      const pct = claimsData.total ? Math.round((claimsData.verified / claimsData.total) * 100) : 100;
      els.melchiorClaimsRate.textContent = t("claims_verified_rate", { rate: pct });

      if (!claims.length) {
        els.claimsTableBody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted);">${t("no_claims")}</td></tr>`;
      } else {
        els.claimsTableBody.innerHTML = claims
          .map((c) => {
            const isVerified = c.status === "verified" || c.status === "web-verified";
            const badgeClass = isVerified ? "badge-sage" : "badge-danger";
            const statusText = c.status === "verified"
              ? t("status_verified")
              : c.status === "web-verified"
                ? t("status_web_verified")
                : t("status_unverified");

            return `
              <tr>
                <td><span class="badge ${badgeClass}">${escapeHtml(statusText)}</span></td>
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
      els.backlogCountBadge.textContent = `${backlog.length} ${t("items_unit")}`;
      if (!backlog.length) {
        els.backlogList.innerHTML = `<li style="color: var(--text-muted); padding: 0.3rem 0;">${t("clean_backlog")}</li>`;
      } else {
        els.backlogList.innerHTML = backlog
          .map((item) => `<li style="padding: 0.3rem 0; border-bottom: 1px solid var(--border-subtle);">📄 ${escapeHtml(item)}</li>`)
          .join("");
      }
    } catch (_) {}
  }

  async function executeGraphSql(sql) {
    if (!state.workspace || !sql.trim()) return;
    els.sqlResultContainer.innerHTML = `<p style="color: var(--text-muted);">${t("sql_executing")}</p>`;
    try {
      const data = await apiFetch(
        `/api/workspace/graph/query?sql=${encodeURIComponent(sql)}&workspace=${encodeURIComponent(state.workspace)}`
      );
      const cols = data.columns || [];
      const rows = data.rows || [];

      if (!rows.length) {
        els.sqlResultContainer.innerHTML = `<p style="color: var(--text-muted);">${t("sql_zero_rows")}</p>`;
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
      const engineReady = (pm.task_engine_ready !== undefined ? pm.task_engine_ready : pm.beads_available);
      if (!engineReady) {
        els.taskStatusBanner.innerHTML = `
          <div class="stat-pill warning" style="border-radius: var(--radius-md); padding: 0.75rem;">
            ${t("bal_engine_not_ready")}
          </div>
        `;
        els.taskReadyVal.textContent = "0";
        els.taskProgressVal.textContent = "0";
        els.taskBlockedVal.textContent = "0";
        els.taskOpenVal.textContent = "0";
        return;
      }
      if (!pm.summary) {
        els.taskStatusBanner.innerHTML = `
          <div class="stat-pill info" style="border-radius: var(--radius-md); padding: 0.75rem;">
            ${t("bal_no_db_initialized")}
          </div>
        `;
        els.taskReadyVal.textContent = "0";
        els.taskProgressVal.textContent = "0";
        els.taskBlockedVal.textContent = "0";
        els.taskOpenVal.textContent = "0";
        return;
      }

      els.taskStatusBanner.innerHTML = "";
      els.taskReadyVal.textContent = pm.summary.ready || 0;
      els.taskProgressVal.textContent = pm.summary.in_progress || 0;
      els.taskBlockedVal.textContent = pm.summary.blocked || 0;
      els.taskOpenVal.textContent = pm.summary.open || 0;
    } catch (_) {}
  }

  // ------------------------------------------------------------------------
  // Tab 4: Casper (Retrieval)
  // ------------------------------------------------------------------------

  async function executeSearch(query, mode, limit) {
    if (!state.workspace || !query.trim()) return;
    els.searchResultsList.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">${t("searching_text")}</p>`;
    els.searchInfoBar.textContent = "";

    try {
      const data = await apiFetch(
        `/api/workspace/search?q=${encodeURIComponent(query)}&mode=${mode}&limit=${limit}&workspace=${encodeURIComponent(state.workspace)}`
      );

      if (data.error) {
        els.searchResultsList.innerHTML = `<div class="stat-pill warning" style="margin: 1rem 0;">${escapeHtml(data.error)}</div>`;
        return;
      }

      const vecStatus = data.vector_available ? t("vec_avail_yes") : t("vec_avail_no");
      els.searchInfoBar.textContent = t("search_summary", {
        total: data.results.length,
        bm25: data.bm25_hits || 0,
        vec: vecStatus,
      });

      if (!data.results.length) {
        els.searchResultsList.innerHTML = `<p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">${t("search_no_results")}</p>`;
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
                ${escapeHtml(hit.path)} (${t("search_lines", { start: hit.start_line, end: hit.end_line })})
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
      const radarPendingN = radar.pending_digests ? radar.pending_digests.length : 0;
      els.radarPendingCount.textContent = radarPendingN;
      els.radarPendingCount.classList.toggle("eva-alert", radarPendingN > 0);

      const digests = radar.digests || [];
      if (!digests.length) {
        els.digestFilesList.innerHTML = `<p style="padding: 1rem; color: var(--text-muted);">${t("no_digests")}</p>`;
        els.digestViewer.innerHTML = `<p style="color: var(--text-muted); text-align: center; margin-top: 3rem;">${t("digest_viewer_prompt")}</p>`;
        return;
      }

      els.digestFilesList.innerHTML = digests
        .map((d, idx) => {
          const isPending = d.status === "pending-review";
          const badgeClass = isPending ? "badge-terracotta" : "badge-sage";
          const badgeText = isPending ? t("status_pending_review") : t("status_reviewed");
          const isSelected = state.activeDigest ? (d.name === state.activeDigest) : (idx === 0);
          return `
            <div class="pane-item ${isSelected ? "active" : ""}" data-file="${escapeHtml(d.name)}">
              <div style="font-weight: 500; font-size: 0.9rem;">${escapeHtml(d.name)}</div>
              <div style="margin-top: 0.3rem;">
                <span class="badge ${badgeClass}">${escapeHtml(badgeText)}</span>
              </div>
            </div>
          `;
        })
        .join("");

      // Auto-load selected or first digest
      if (digests.length > 0) {
        const targetDigest = (state.activeDigest && digests.some((d) => d.name === state.activeDigest))
          ? state.activeDigest
          : digests[0].name;
        state.activeDigest = targetDigest;
        loadDigestContent(targetDigest);
      }

      els.digestFilesList.querySelectorAll(".pane-item").forEach((item) => {
        item.addEventListener("click", () => {
          els.digestFilesList.querySelectorAll(".pane-item").forEach((i) => i.classList.remove("active"));
          item.classList.add("active");
          state.activeDigest = item.dataset.file;
          loadDigestContent(item.dataset.file);
        });
      });
    } catch (_) {}
  }

  async function loadDigestContent(filename) {
    if (!state.workspace || !filename) return;
    els.digestViewer.innerHTML = `<p style="color: var(--text-muted);">${t("digest_loading", { file: escapeHtml(filename) })}</p>`;
    try {
      const data = await apiFetch(
        `/api/workspace/radar/digest?file=${encodeURIComponent(filename)}&workspace=${encodeURIComponent(state.workspace)}`
      );
      if (window.marked) {
        // Digests carry external data (paper titles/abstracts from S2/arXiv).
        // Escape raw HTML before markdown parsing so embedded tags render as
        // text instead of executing in the dashboard. YAML frontmatter is
        // dropped — marked would misread it as a setext heading.
        const safeMd = String(data.content)
          .replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
        els.digestViewer.innerHTML = window.marked.parse(safeMd);
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

  async function launchJob(command, displayName) {
    if (!state.workspace) {
      showToast(t("toast_select_ws_first"), "error");
      return;
    }

    try {
      const cmdParts = command.trim().split(/\s+/).filter(Boolean);
      const res = await apiFetch("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          command: cmdParts,
          workspace: state.workspace,
          name: displayName || command,
        }),
      });

      showToast(t("toast_job_started", { name: displayName || command }), "info");
      switchTab("operations");
      startLogStream(res.job_id, displayName || command);
    } catch (err) {
      showToast(t("toast_job_fail", { error: err.message }), "error");
    }
  }

  function startLogStream(jobId, jobName) {
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }

    state.activeJobId = jobId;
    state.activeJobName = jobName;
    els.termJobName.textContent = t("term_running", { name: jobName });
    els.termStatusDot.className = "status-dot running";
    els.termCancelBtn.style.display = "inline-flex";
    els.terminalOutput.textContent = t("term_connecting", { id: jobId });

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
            showToast(t("toast_job_success", { name: jobName }), "success");
            source.close();
            state.activeJobId = null;
            els.termJobName.textContent = t("term_idle");
            loadSyncRatio();
          } else if (payload.status === "failed" || payload.status === "cancelled") {
            els.termStatusDot.className = "status-dot error";
            els.termCancelBtn.style.display = "none";
            showToast(t("toast_job_ended", { name: jobName, status: payload.status }), "error");
            source.close();
            state.activeJobId = null;
            els.termJobName.textContent = t("term_idle");
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
      state.activeJobId = null;
      els.termJobName.textContent = t("term_idle");
    };
  }

  // ------------------------------------------------------------------------
  // Tab 7: Documentation
  // ------------------------------------------------------------------------

  async function loadDocs(docKey) {
    state.activeDoc = docKey;

    // Update active button state
    els.docSwitchBtns.forEach((b) => {
      b.classList.toggle("active", b.dataset.doc === docKey);
    });

    els.docsContent.innerHTML = `<p style="color: var(--text-muted);">${t("loading_docs")}</p>`;
    try {
      if (docKey === "commands") {
        const data = await apiFetch("/api/docs/commands");
        const cmds = data.commands || [];
        let html = `<h1>${t("docs_cmd_title")}</h1>`;
        html += `<p>${t("docs_cmd_sub")}</p>`;
        html += `<table class="data-table"><thead><tr><th>${t("th_cmd_command")}</th><th>${t("th_cmd_group")}</th><th>${t("th_cmd_desc")}</th></tr></thead><tbody>`;
        cmds.forEach((c) => {
          html += `<tr><td><code>${escapeHtml(c.command)}</code></td><td><span class="badge badge-muted">${escapeHtml(c.group || "core")}</span></td><td>${escapeHtml(c.help)}</td></tr>`;
        });
        html += `</tbody></table>`;
        els.docsContent.innerHTML = html;
      } else {
        const langParam = docKey === "readme-en" ? "en" : "zh";
        const data = await apiFetch(`/api/docs/readme?lang=${langParam}`);
        const mdText = data.content || (langParam === "en" ? data.readme_en : data.readme_zh) || t("no_docs_found");
        if (window.marked && mdText) {
          els.docsContent.innerHTML = window.marked.parse(mdText);
        } else {
          els.docsContent.textContent = mdText;
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
    els.doctorModalBody.innerHTML = `<p style="color: var(--text-muted);">${t("doctor_running")}</p>`;
    try {
      const data = await apiFetch("/api/doctor");
      const doc = data.doctor || [];
      const legacy = data.legacy || [];

      let html = `<table class="data-table" style="margin-bottom: 1rem;"><thead><tr><th>${t("doctor_th_comp")}</th><th>${t("doctor_th_status")}</th><th>${t("doctor_th_detail")}</th></tr></thead><tbody>`;
      doc.forEach((row) => {
        const mark = row.ok
          ? `<span class="badge badge-sage">${t("badge_ok")}</span>`
          : `<span class="badge badge-danger">${t("badge_missing")}</span>`;
        html += `<tr><td><strong>${escapeHtml(row.tool)}</strong></td><td>${mark}</td><td><code style="font-size: 0.8rem;">${escapeHtml(row.detail)}</code></td></tr>`;
      });
      html += `</tbody></table>`;

      if (legacy.length > 0) {
        html += `<div style="margin-top: 1rem;"><strong style="color: var(--accent-danger);">${t("doctor_legacy_found", { count: legacy.length })}</strong><ul style="margin: 0.5rem 0 0 1.25rem; font-size: 0.85rem; font-family: var(--font-mono);">`;
        legacy.forEach((p) => {
          html += `<li>${escapeHtml(p)}</li>`;
        });
        html += `</ul><p style="margin-top: 0.5rem; font-size: 0.8rem; color: var(--text-secondary);">${t("doctor_legacy_hint")}</p></div>`;
      } else {
        html += `<p style="color: var(--accent-sage); font-size: 0.85rem;">${t("doctor_clean")}</p>`;
      }

      els.doctorModalBody.innerHTML = html;
    } catch (err) {
      els.doctorModalBody.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // ------------------------------------------------------------------------
  // Event Listeners
  // ------------------------------------------------------------------------

  // Theme Toggle (Light / Dark)
  if (els.themeToggleBtn) {
    els.themeToggleBtn.addEventListener("click", () => {
      if (state.theme === "eva") {
        const currentBase = safeStorageGet("magi-base-theme") || "dark";
        const nextTheme = currentBase === "dark" ? "light" : "dark";
        applyTheme(nextTheme);
      } else {
        applyTheme(state.theme === "dark" ? "light" : "dark");
      }
    });
  }

  // MAGI MODE Toggle
  if (els.magiModeBtn) {
    els.magiModeBtn.addEventListener("click", () => {
      if (state.theme === "eva") {
        const fallback = safeStorageGet("magi-base-theme") || "dark";
        applyTheme(fallback);
      } else {
        safeStorageSet("magi-base-theme", state.theme);
        runEvaBoot();
        applyTheme("eva");
      }
    });
  }

  // Language Switcher
  if (els.langBtnZh) {
    els.langBtnZh.addEventListener("click", () => setLanguage("zh"));
  }
  if (els.langBtnEn) {
    els.langBtnEn.addEventListener("click", () => setLanguage("en"));
  }

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
      showToast(t("toast_kb_registered"), "success");
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
    launchJob("pm backlog-sync", t("btn_backlog_sync"));
  });

  // Radar actions
  els.btnRadarHarvest.addEventListener("click", () => {
    launchJob("radar harvest", t("btn_radar_harvest"));
  });
  els.btnRadarCitationGap.addEventListener("click", () => {
    launchJob("radar citation-gap", t("btn_radar_citation_gap"));
  });

  // Operations common buttons
  els.opTaskBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const opKey = btn.dataset.op || btn.getAttribute("data-i18n");
      const i18nKey = opKey && opKey.startsWith("op_") ? opKey : (opKey ? `op_${opKey}` : null);
      const name = i18nKey ? t(i18nKey) : (btn.dataset.name || btn.dataset.cmd);
      launchJob(btn.dataset.cmd, name);
    });
  });

  // Danger actions with 2-step confirmation modal
  els.dangerActionBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      const title = t(`danger_${action}_title`);
      const desc = t(`danger_${action}_desc`);
      pendingDangerCommand = {
        cmd: btn.dataset.cmd,
        action: action,
        title: title,
      };

      els.dangerModalTitle.textContent = `${t("danger_modal_prefix")}: ${title}`;
      els.dangerModalDesc.innerHTML = `
        <strong style="color: var(--accent-danger);">${t("warning_label")}:</strong> ${escapeHtml(desc)}
        <br><br>
        ${t("cmd_to_execute")}: <code>magi ${escapeHtml(pendingDangerCommand.cmd)}</code>
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
      showToast(t("toast_job_cancel_req"), "info");
    } catch (_) {}
  });

  // Docs switcher
  els.docSwitchBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
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
  setLanguage(state.lang);
  startEvaClock();
  loadInitialStatus();

  // Deep-link override: ?tab=melchior|operations|...
  try {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && document.getElementById(`tab-${urlTab}`)) {
      switchTab(urlTab);
    }
  } catch (_) {}
})();
