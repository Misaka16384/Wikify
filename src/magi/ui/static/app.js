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
      workspace_label: "查看工作空间:",
      loading_workspaces: "加载工作空间中...",
      browsing_badge: "浏览中",
      browsing_badge_title: "面板正在浏览另一个工作空间（会话级选择，服务器启动位置不变）",
      term_retention_note: "任务历史跨重启保留（最近 40 条，magi 配置目录下 ui-jobs.jsonl）。",
      sync_label: "三核同步:",
      running_jobs_label: "运行中任务:",
      sync_ratio_tooltip: "Melchior / Balthasar / Casper 三核协同同步率",
      doctor_btn: "环境体检",
      doctor_btn_title: "环境依赖与规范体检",
      theme_btn_title: "切换深浅配色主题",
      magi_mode_btn: "MAGI 模式",
      magi_mode_btn_title: "开启/关闭 EVA NERV MAGI 战术主题",

      // Navigation Tabs
      tab_dashboard: "课题总览",
      tab_melchior: "Melchior (认知状态)",
      tab_balthasar: "Balthasar (任务追踪)",
      tab_casper: "Casper (文献检索)",
      tab_radar: "文献雷达",
      tab_operations: "运维与操作",
      tab_docs: "文档与指引",

      // Dashboard Metrics
      dash_sync_label: "三核同步率",
      dash_sync_subtitle: "认知 + 任务 + 检索协同",
      dash_kb_label: "已注册知识库",
      dash_kb_subtitle: "全局知识联合",
      dash_radar_label: "待审阅简报",
      dash_radar_subtitle: "文献雷达追踪",
      dash_task_label: "科研任务状态",
      dash_task_subtitle: "待办及进行中任务",

      // Three-core status band
      core_role_mel: "认知状态",
      core_role_bal: "任务追踪",
      core_role_cas: "文献检索",
      core_sync_label: "三核同步率",
      core_state_ok: "正常",
      core_state_attention: "待处理",
      core_state_fault: "故障",
      core_state_offline: "未接入",
      core_detail_nolink: "尚未选择工作区",
      core_detail_mel: "{c} 概念 · {r} 文献 · 命题 {v}/{n} 已核验",
      core_detail_bal: "就绪 {r} · 进行中 {p} · 阻塞 {b}",
      core_detail_bal_kbonly: "纯知识库模式，未启用任务追踪",
      core_detail_bal_noengine: "未安装 beads，请运行 magi setup",
      core_detail_bal_uninit: "任务库尚未初始化",
      core_detail_cas: "{c} 条内容索引 · {v} 条语义索引",
      core_detail_cas_noindex: "尚未建立检索索引",

      // Dashboard KB Table
      dash_kb_table_title: "已注册知识库",
      dash_kb_table_subtitle: "全局注册表位于 ~/.config/magi/registry.json",
      btn_refresh: "刷新",
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
      btn_refresh_claims: "刷新命题",
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
      btn_backlog_sync: "待办文献转任务",
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
      cas_title: "文献检索",
      cas_subtitle: "关键词与语义双通道检索，按相关度融合排序",
      search_input_ph: "检索概念、实验发现或文献内容...",
      opt_hybrid: "智能检索（关键词 + 语义）",
      opt_bm25: "仅关键词匹配",
      opt_vector: "仅语义相似",
      opt_limit_5: "前 5 项",
      opt_limit_10: "前 10 项",
      opt_limit_20: "前 20 项",
      btn_search: "检索",
      search_prompt: "输入检索关键词以查看混合排名结果与内容片段。",
      searching_text: "正在全库检索中...",
      search_no_results: "未找到匹配的段落内容。",
      search_summary: "找到 {total} 条结果 · 关键词命中 {bm25} · 语义检索{vec}",
      search_lines: "行 {start}-{end}",
      vec_avail_yes: "已启用",
      vec_avail_no: "未启用",

      // Literature Radar
      radar_seen_label: "已跟踪文献记录",
      radar_seen_sub: "文献雷达跟踪记录",
      radar_pending_label: "待审阅简报",
      radar_pending_sub: "等待 Agent 审阅分流",
      btn_radar_harvest: "运行文献雷达扫描",
      btn_radar_citation_gap: "侦察引文缺口",
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
      op_rebuild_index: "重建检索索引",
      op_build_graph: "构建知识图谱",
      op_reindex_wiki: "重建维基索引",
      op_semantic_link: "语义概念链接",
      op_lint_fix: "规范检查与修复",
      op_backlog_sync: "待办文献转任务",
      op_index: "重建检索索引",
      op_graph_build: "构建知识图谱",
      op_wiki_reindex: "重建维基索引",
      op_link: "语义概念链接",
      danger_title: "危险操作区",
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

      // Sync Hints (actionable)
      hints_title: "建议操作",
      hints_subtitle: "同步报告给出的下一步建议——点按钮直接执行",
      hint_graph_build: "知识图谱落后于卡片内容，需要重建",
      hint_index: "检索索引缺失或已过期，需要重建",
      hint_backlog_sync: "有未编译文献尚未纳入任务追踪",
      hint_pm_init: "任务引擎尚未初始化（在 运维与操作 中初始化）",
      hint_radar_review: "有文献雷达简报等待审阅",
      hint_claims_unverified: "有学术命题尚未验证（到 Melchior 面板查看）",
      hint_bd_ready: "有可直接开工的任务（到 Balthasar 面板查看）",
      hint_install_beads: "任务引擎 (beads) 未安装——见安装指引",
      hint_ingest_start: "把论文 PDF / 源文件放进 inbox/，用 wiki_ingest 技能开始建库",
      btn_hint_run: "执行",
      btn_hint_goto: "前往",

      // Search guidance
      vec_unavailable_hint: "语义检索未启用：需要本机 Ollama 语义模型，且在运行 magi index 建立索引时可用。当前仅按关键词匹配。",
      search_no_results_hint: "建议：改用 2-3 个关键词（而非整句）、切换检索模式，或确认当前工作区已运行过「重建检索索引」。",

      // Radar kinds
      badge_kind_citation_gap: "引文缺口",

      // References & drafts (Melchior)
      mel_bib_title: "文献与引用",
      mel_bib_subtitle: "参考卡一键导出 BibTeX（magi bib）",
      btn_copy_all_bibtex: "复制全库 BibTeX",
      btn_copy_bibtex: "复制 BibTeX",
      bib_loading: "正在加载参考卡...",
      bib_none: "wiki/references/ 下还没有参考卡。",
      bib_no_entry: "缺少可引用的 frontmatter（title/authors/year）",
      toast_bib_copied: "BibTeX 已复制到剪贴板（{n} 条）",
      mel_drafts_title: "论文草稿",
      mel_drafts_subtitle: "drafts/ 下的草稿——进检索、不进图谱（wiki_draft skill）",
      drafts_none: "还没有草稿——用 wiki_draft skill 开始写作流程。",

      // Workspace config
      cfg_title: "工作区配置",
      cfg_subtitle: "config.yaml 的科研旋钮——修改只动对应行，注释与其余内容原样保留",
      cfg_loading: "正在加载配置...",
      btn_cfg_save: "保存",
      toast_cfg_saved: "已写入 {key}",
      cfg_list_hint: "多个值用逗号分隔",
      cfg_f_radar_min_relevance: "雷达相关度阈值（低于此分的候选被丢弃；留空 = 不过滤）",
      cfg_f_radar_days: "雷达回溯天数（arXiv 新文窗口）",
      cfg_f_radar_max_candidates: "每次收割的候选上限",
      cfg_f_radar_arxiv_categories: "arXiv 分类（如 cond-mat.str-el）",
      cfg_f_radar_seed_arxiv_ids: "种子论文 arXiv ID（推荐引擎的输入）",
      cfg_f_radar_own_arxiv_ids: "我方论文 arXiv ID（citation-gap 的锚点）",
      cfg_f_ocr_use_mineru: "使用 MinerU 云端 OCR（需在 config 中配 token）",
      cfg_f_models_embedding: "语义模型（Ollama 模型名）",

      // Search filters
      opt_scope_auto: "联邦检索（本库 + 启用的注册库）",
      opt_scope_local: "仅当前工作区",
      opt_coll_all: "全部集合",
      opt_coll_concepts: "concepts 概念卡",
      opt_coll_references: "references 文献卡",
      opt_coll_topics: "topics 主题卡",
      opt_coll_raw: "raw 原始文献",
      opt_coll_drafts: "drafts 草稿",
      search_path_ph: "路径 glob 过滤，如 raw/papers/2026-*",

      // Radar review actions
      radar_actions_title: "候选操作",
      btn_accept_inbox: "收入 inbox",
      btn_create_issue: "建阅读任务",
      btn_mark_reviewed: "✓ 标记本报告已审",
      toast_marked_reviewed: "已标记为已审：{file}",
      toast_accepted: "已写入 {path}（等待摄入）",
      toast_issue_created: "已创建阅读任务 (bd survey)",

      // Ops catalog & danger confirm
      ops_loading: "正在加载操作目录...",
      op_stats: "工作区统计",
      btn_danger_install_schedule: "注册/卸载定时收割",
      danger_install_schedule_desc: "在系统任务计划中注册（或卸载）每日文献雷达定时收割任务。",
      danger_confirm_ph: "在此输入操作 ID 以确认",
      danger_type_to_confirm: "为防误触，请在下方输入框输入 {op} 后点击确认。",
      danger_confirm_mismatch: "确认文本不匹配：需要输入 {op}",

      // Knowledge graph browser
      graph_card_title: "知识图谱",
      graph_card_subtitle: "词条、链接、命题与标签的结构化视图",
      graph_view_overview: "总览",
      graph_view_nodes: "词条",
      graph_view_links: "链接",
      graph_view_claims: "命题",
      graph_view_tags: "标签",
      graph_view_broken: "断链",
      graph_q_ph: "按标题或编号筛选…",
      graph_type_all: "全部类型",
      graph_type_concept: "概念",
      graph_type_reference: "文献",
      graph_type_topic: "课题",
      graph_type_thesis: "论点",
      graph_type_claim: "命题",
      graph_type_tag: "标签",
      graph_loading: "正在加载图谱视图…",
      graph_empty: "没有匹配的记录。",
      graph_back: "返回词条列表",
      graph_out: "出链",
      graph_in: "入链",
      graph_hubs_hint: "连接最多的词条，点击查看其链接",
      graph_broken_empty: "没有断链，链接网络完整。",
      graph_view_map: "图谱",
      graph_map_tags: "显示标签节点",
      graph_map_hint: "拖拽节点 · 滚轮缩放 · 点击节点查看链接",
      graph_map_empty: "图谱为空——先运行 magi graph build 构建知识图谱。",
      graph_map_truncated: "节点较多，已按连接度显示前 {n} 个",
      graph_map_no_d3: "图谱物理引擎未加载——请检查 /vendor/d3-*.min.js 是否可访问",

      // Liquid-glass tuner
      glass_btn_title: "玻璃材质调节（模糊 / 不透明度）",
      glass_blur_label: "模糊",
      glass_alpha_label: "不透明",
      glass_crt_label: "CRT 扫描线",
      glass_reset: "重置",
      graph_th_title: "标题",
      graph_th_type: "类型",
      graph_th_degree: "连接度",
      graph_th_updated: "更新",
      graph_th_text: "内容",
      graph_th_doc: "所在文档",
      graph_th_tag: "标签",
      graph_th_count: "引用数",
      graph_th_source: "来源",
      graph_th_target_missing: "指向（不存在）",
      adv_sql_title: "高级：只读 SQL 控制台",

      // Radar digest filter
      radar_filter_ph: "按作者或标题筛选候选…",
      radar_filter_count: "显示 {shown} / {total} 条",
    },

    en: {
      // Page & Brand
      page_title: "MAGI — Research Workspace WebUI",

      // Topbar
      workspace_label: "Viewing:",
      loading_workspaces: "Loading workspaces...",
      browsing_badge: "Browsing",
      browsing_badge_title: "The panel is browsing a different workspace (session-level choice; the server's launch location is unchanged)",
      term_retention_note: "Job history persists across restarts (last 40 records, ui-jobs.jsonl in the magi config directory).",
      sync_label: "Sync:",
      running_jobs_label: "Running Jobs:",
      sync_ratio_tooltip: "Three-core sync ratio (Melchior + Balthasar + Casper)",
      doctor_btn: "Doctor",
      doctor_btn_title: "Environment Doctor Check",
      theme_btn_title: "Toggle Light/Dark Theme",
      magi_mode_btn: "MAGI MODE",
      magi_mode_btn_title: "Toggle EVA NERV MAGI Command Theme",

      // Navigation Tabs
      tab_dashboard: "Dashboard",
      tab_melchior: "Melchior (Cognitive)",
      tab_balthasar: "Balthasar (Tasks)",
      tab_casper: "Casper (Retrieval)",
      tab_radar: "Literature Radar",
      tab_operations: "Operations & Danger Zone",
      tab_docs: "Docs & Help",

      // Dashboard Metrics
      dash_sync_label: "Sync Ratio",
      dash_sync_subtitle: "Melchior + Balthasar + Casper",
      dash_kb_label: "Registered KBs",
      dash_kb_subtitle: "Global federation",
      dash_radar_label: "Pending Digests",
      dash_radar_subtitle: "Literature radar",
      dash_task_label: "Active Task State",
      dash_task_subtitle: "Actionable tasks",

      // Three-core status band
      core_role_mel: "Cognitive state",
      core_role_bal: "Task state",
      core_role_cas: "Retrieval",
      core_sync_label: "Three-core sync",
      core_state_ok: "Nominal",
      core_state_attention: "Needs attention",
      core_state_fault: "Fault",
      core_state_offline: "Not linked",
      core_detail_nolink: "No workspace selected",
      core_detail_mel: "{c} concepts · {r} references · {v}/{n} claims verified",
      core_detail_bal: "{r} ready · {p} in progress · {b} blocked",
      core_detail_bal_kbonly: "Knowledge-base only, task tracking off",
      core_detail_bal_noengine: "beads not installed — run magi setup",
      core_detail_bal_uninit: "Task store not initialized",
      core_detail_cas: "{c} indexed passages · {v} with semantic index",
      core_detail_cas_noindex: "No retrieval index built",

      // Dashboard KB Table
      dash_kb_table_title: "Registered Knowledge Bases",
      dash_kb_table_subtitle: "Global registry located at ~/.config/magi/registry.json",
      btn_refresh: "Refresh",
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
      btn_refresh_claims: "Refresh Claims",
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
      btn_backlog_sync: "Sync Backlog to Tasks",
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
      cas_title: "Literature Search",
      cas_subtitle: "Keyword and meaning search in one pass, fused by relevance",
      search_input_ph: "Search concepts, findings, or literature...",
      opt_hybrid: "Smart search (keyword + meaning)",
      opt_bm25: "Keyword match only",
      opt_vector: "Meaning match only",
      opt_limit_5: "Top 5",
      opt_limit_10: "Top 10",
      opt_limit_20: "Top 20",
      btn_search: "Search",
      search_prompt: "Enter a search query to inspect hybrid ranking and excerpts.",
      searching_text: "Searching corpus...",
      search_no_results: "No matching passages found.",
      search_summary: "Found {total} hit(s) · keyword hits: {bm25} · semantic search: {vec}",
      search_lines: "lines {start}-{end}",
      vec_avail_yes: "on",
      vec_avail_no: "off",

      // Literature Radar
      radar_seen_label: "Seen Papers Ledger",
      radar_seen_sub: "Literature tracking ledger",
      radar_pending_label: "Pending Digests",
      radar_pending_sub: "Awaiting agent triage",
      btn_radar_harvest: "Run Radar Harvest",
      btn_radar_citation_gap: "Scout Citation Gaps",
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
      op_rebuild_index: "Rebuild Index",
      op_build_graph: "Build Graph",
      op_reindex_wiki: "Reindex Wiki Tables",
      op_semantic_link: "Semantic Link",
      op_lint_fix: "Lint & Auto-Fix",
      op_backlog_sync: "Backlog to Tasks",
      op_index: "Rebuild Index",
      op_graph_build: "Build Graph",
      op_wiki_reindex: "Reindex Wiki Tables",
      op_link: "Semantic Link",
      danger_title: "Danger Zone",
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

      // Sync Hints (actionable)
      hints_title: "Suggested Actions",
      hints_subtitle: "What the sync report recommends next — click to run",
      hint_graph_build: "Knowledge graph is behind the cards and needs a rebuild",
      hint_index: "Retrieval index is missing or stale and needs a rebuild",
      hint_backlog_sync: "Uncompiled sources are not yet tracked as tasks",
      hint_pm_init: "Task engine is not initialized (do it in Operations)",
      hint_radar_review: "Literature radar digests are waiting for review",
      hint_claims_unverified: "Some claims are still unverified (see Melchior)",
      hint_bd_ready: "There is actionable work ready (see Balthasar)",
      hint_install_beads: "Task engine (beads) is not installed — see install guide",
      hint_ingest_start: "Drop paper PDFs / sources into inbox/ and run the wiki_ingest skill",
      btn_hint_run: "Run",
      btn_hint_goto: "Open",

      // Search guidance
      vec_unavailable_hint: "Semantic search is off: it needs a local Ollama model available when 'magi index' builds the index. Keyword matching only for now.",
      search_no_results_hint: "Try 2-3 keywords instead of a full sentence, switch the search mode, or make sure this workspace has a built index (Rebuild Index).",

      // Radar kinds
      badge_kind_citation_gap: "Citation Gap",

      // References & drafts (Melchior)
      mel_bib_title: "References & Citations",
      mel_bib_subtitle: "Reference cards with one-click BibTeX export (magi bib)",
      btn_copy_all_bibtex: "Copy all BibTeX",
      btn_copy_bibtex: "Copy BibTeX",
      bib_loading: "Loading reference cards...",
      bib_none: "No reference cards under wiki/references/ yet.",
      bib_no_entry: "missing citable frontmatter (title/authors/year)",
      toast_bib_copied: "BibTeX copied to clipboard ({n} entrie(s))",
      mel_drafts_title: "Drafts",
      mel_drafts_subtitle: "Paper drafts under drafts/ — indexed for search, outside the graph (wiki_draft skill)",
      drafts_none: "No drafts yet — the wiki_draft skill sets up the writing workflow.",

      // Workspace config
      cfg_title: "Workspace Config",
      cfg_subtitle: "Research knobs from config.yaml — edits touch only the target line, comments preserved",
      cfg_loading: "Loading config...",
      btn_cfg_save: "Save",
      toast_cfg_saved: "Saved {key}",
      cfg_list_hint: "separate multiple values with commas",
      cfg_f_radar_min_relevance: "Radar relevance threshold (candidates below are dropped; empty = keep all)",
      cfg_f_radar_days: "Radar lookback window in days (new arXiv listings)",
      cfg_f_radar_max_candidates: "Max candidates per harvest",
      cfg_f_radar_arxiv_categories: "arXiv categories (e.g. cond-mat.str-el)",
      cfg_f_radar_seed_arxiv_ids: "Seed paper arXiv IDs (recommendation input)",
      cfg_f_radar_own_arxiv_ids: "Your own papers' arXiv IDs (citation-gap anchors)",
      cfg_f_ocr_use_mineru: "Use MinerU cloud OCR (token configured in config)",
      cfg_f_models_embedding: "Semantic model (Ollama model name)",

      // Search filters
      opt_scope_auto: "Federated (this KB + enabled KBs)",
      opt_scope_local: "This workspace only",
      opt_coll_all: "All collections",
      opt_coll_concepts: "concepts",
      opt_coll_references: "references",
      opt_coll_topics: "topics",
      opt_coll_raw: "raw",
      opt_coll_drafts: "drafts",
      search_path_ph: "path glob filter, e.g. raw/papers/2026-*",

      // Radar review actions
      radar_actions_title: "Candidate Actions",
      btn_accept_inbox: "Accept to inbox",
      btn_create_issue: "Create reading task",
      btn_mark_reviewed: "✓ Mark report reviewed",
      toast_marked_reviewed: "Marked reviewed: {file}",
      toast_accepted: "Wrote {path} (queued for ingestion)",
      toast_issue_created: "Reading task created (bd survey)",

      // Ops catalog & danger confirm
      ops_loading: "Loading operations…",
      op_stats: "Workspace Stats",
      btn_danger_install_schedule: "Install/Remove Schedule",
      danger_install_schedule_desc: "Register (or uninstall) the daily literature-radar harvest in the system scheduler.",
      danger_confirm_ph: "type the operation id to confirm",
      danger_type_to_confirm: "To prevent accidents, type {op} below and press Confirm.",
      danger_confirm_mismatch: "Confirmation text mismatch: type {op}",

      // Knowledge graph browser
      graph_card_title: "Knowledge Graph",
      graph_card_subtitle: "Structured views over entries, links, claims and tags",
      graph_view_overview: "Overview",
      graph_view_nodes: "Entries",
      graph_view_links: "Links",
      graph_view_claims: "Claims",
      graph_view_tags: "Tags",
      graph_view_broken: "Broken links",
      graph_q_ph: "Filter by title or id…",
      graph_type_all: "All types",
      graph_type_concept: "Concept",
      graph_type_reference: "Reference",
      graph_type_topic: "Topic",
      graph_type_thesis: "Thesis",
      graph_type_claim: "Claim",
      graph_type_tag: "Tag",
      graph_loading: "Loading graph view…",
      graph_empty: "No matching records.",
      graph_back: "Back to entries",
      graph_out: "Outgoing",
      graph_in: "Incoming",
      graph_hubs_hint: "Most-connected entries — click one to inspect its links",
      graph_broken_empty: "No broken links — the link network is intact.",
      graph_view_map: "Graph",
      graph_map_tags: "Show tag nodes",
      graph_map_hint: "Drag nodes · scroll to zoom · click a node to inspect its links",
      graph_map_empty: "The graph is empty — run magi graph build first.",
      graph_map_truncated: "Large graph — showing the top {n} nodes by degree",
      graph_map_no_d3: "Graph physics library failed to load — check /vendor/d3-*.min.js",

      // Liquid-glass tuner
      glass_btn_title: "Glass material tuning (blur / opacity)",
      glass_blur_label: "Blur",
      glass_alpha_label: "Opacity",
      glass_crt_label: "CRT scanlines",
      glass_reset: "Reset",
      graph_th_title: "Title",
      graph_th_type: "Type",
      graph_th_degree: "Degree",
      graph_th_updated: "Updated",
      graph_th_text: "Text",
      graph_th_doc: "Document",
      graph_th_tag: "Tag",
      graph_th_count: "Count",
      graph_th_source: "Source",
      graph_th_target_missing: "Target (missing)",
      adv_sql_title: "Advanced: read-only SQL console",

      // Radar digest filter
      radar_filter_ph: "Filter candidates by author or title…",
      radar_filter_count: "Showing {shown} of {total}",
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
    serverWorkspace: "",
    kbs: [],
    activeTab: "dashboard",
    activeDoc: "readme",
    graphView: "map",
    graphNode: null,
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

    // Knowledge graph browser
    graphViewBtns: document.querySelectorAll(".graph-view-btn"),
    graphFilterRow: document.getElementById("graph-filter-row"),
    graphMapWrap: document.getElementById("graph-map-wrap"),
    graphMapCanvas: document.getElementById("graph-map-canvas"),
    graphMapTags: document.getElementById("graph-map-tags"),
    graphMapNote: document.getElementById("graph-map-note"),
    // Liquid-glass tuner
    glassTunerBtn: document.getElementById("glass-tuner-btn"),
    glassTunerPanel: document.getElementById("glass-tuner-panel"),
    glassBlurRange: document.getElementById("glass-blur-range"),
    glassAlphaRange: document.getElementById("glass-alpha-range"),
    glassBlurVal: document.getElementById("glass-blur-val"),
    glassAlphaVal: document.getElementById("glass-alpha-val"),
    glassCrtToggle: document.getElementById("glass-crt-toggle"),
    glassResetBtn: document.getElementById("glass-reset-btn"),
    graphQ: document.getElementById("graph-q"),
    graphType: document.getElementById("graph-type"),
    graphBrowseContainer: document.getElementById("graph-browse-container"),

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

  // ------------------------------------------------------------------------
  // Utilities
  // ------------------------------------------------------------------------

  // Common backend errors arrive in English; translate the frequent ones so a
  // Chinese-UI researcher gets an actionable message instead of raw API text.
  function localizeApiError(msg) {
    if (state.lang !== "zh" || !msg) return msg;
    const rules = [
      [/^Directory does not exist: (.+)$/, "目录不存在：$1"],
      [/^Unknown operation: (.+)$/, "未知操作：$1"],
      [/^Dangerous operation requires confirm='(.+)'$/, "危险操作需要输入 $1 确认"],
      [/^max 3 concurrent jobs.*$/, "已有 3 个任务在运行——请等待其中一个结束"],
      [/^this workspace already has an active job$/, "该工作区已有任务在运行"],
      [/^a global operation is running.*$/, "有全局操作正在运行——请等待其结束"],
      [/^global operations require no other running jobs$/, "全局操作要求没有其他任务在运行"],
      [/^KB '(.+)' not found in registry$/, "注册表中找不到知识库 '$1'"],
      [/^Job not found$/, "找不到该后台任务"],
      [/^Unable to cancel job.*$/, "无法中止该任务（不存在或已结束）"],
      [/^[Nn]o index (found|at) .*$/, "当前工作区还没有检索索引——请先在 运维与操作 里点「重建检索索引」"],
      [/^Knowledge graph database not found.*$/, "知识图谱数据库不存在——请先在 运维与操作 里点「构建知识图谱」"],
      [/^Digest file not found: (.+)$/, "找不到简报文件：$1"],
      [/^Report is not pending-review: (.+)$/, "该报告不在待审状态：$1"],
      [/^Already accepted: (.+)$/, "该候选已收入过：$1"],
      [/^No beads workspace found.*$/, "尚未初始化任务引擎——请先运行 magi pm init"],
      [/^bd \(Beads\) is not installed$/, "任务引擎 (beads) 未安装"],
      [/^Failed to generate sync report: (.+)$/, "生成同步报告失败：$1"],
    ];
    for (const [re, rep] of rules) {
      if (re.test(msg)) return msg.replace(re, rep);
    }
    return msg;
  }

  async function apiFetch(url, options = {}) {
    try {
      const res = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(localizeApiError(data.detail || data.error) || `HTTP ${res.status}`);
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
      // MAGI MODE reads the base theme as its alert state — light base means
      // the blue quiet-watch variant, dark base the red combat variant — so
      // the theme toggle keeps working inside the mode instead of exiting it.
      const base = safeStorageGet("magi-base-theme") || "dark";
      document.documentElement.setAttribute("data-eva", base === "light" ? "blue" : "red");
      if (els.themeToggleBtn) {
        els.themeToggleBtn.textContent = base === "dark" ? "☀︎" : "☽";
      }
      startEvaClock();
    } else {
      document.documentElement.removeAttribute("data-eva");
      safeStorageSet("magi-mode", "false");
      safeStorageSet("magi-base-theme", theme);
      if (els.magiModeBtn) {
        els.magiModeBtn.classList.remove("active");
      }
      if (els.themeToggleBtn) {
        els.themeToggleBtn.textContent = theme === "dark" ? "☀︎" : "☽";
      }
      stopEvaClock();
      if (evaBootTimer) {
        clearTimeout(evaBootTimer);
        evaBootTimer = null;
      }
      if (els.evaBoot) {
        els.evaBoot.classList.remove("active");
      }
    }
    applyBackground("state");
    // A settled graph map never re-ticks on its own, so a theme flip must
    // trigger one repaint to resample the token colours.
    scheduleGraphMapDraw();
  }

  // ------------------------------------------------------------------------
  // EVA artwork backdrop engine
  //
  // Two stacked .app-bg-photo layers crossfade between images from the
  // bundled (or user-overridden) background sets: the blue set under the
  // quiet-watch variant, the red set under combat. Selection matches the
  // viewport's aspect ratio; near-ties rotate randomly on tab switches.
  // ------------------------------------------------------------------------

  const bgEngine = { manifest: null, baseUrl: "", front: null, shown: null, variant: null, req: 0 };

  function currentEvaVariant() {
    if (state.theme !== "eva") return null;
    return (safeStorageGet("magi-base-theme") || "dark") === "light" ? "blue" : "red";
  }

  async function initBackgrounds() {
    try {
      const res = await fetch("/api/ui/backgrounds");
      if (!res.ok) return;
      const data = await res.json();
      bgEngine.manifest = data.variants || {};
      bgEngine.baseUrl = data.base_url || "";
    } catch (_) {
      bgEngine.manifest = {};
    }
    applyBackground("state");
  }

  // |log(image aspect / viewport aspect)| — 0 is a perfect fit. Anything
  // within 0.28 of the best fit competes, so similarly-cropped images
  // rotate instead of one image monopolising a viewport shape. Entries
  // without dimensions (user-supplied, no manifest) are always eligible.
  function bgEligible(variant) {
    const entries = (bgEngine.manifest && bgEngine.manifest[variant]) || [];
    if (!entries.length) return [];
    const winAspect = window.innerWidth / Math.max(1, window.innerHeight);
    const scored = entries.map((e) => ({
      e,
      d: e.aspect ? Math.abs(Math.log(e.aspect / winAspect)) : 0,
    }));
    scored.sort((a, b) => a.d - b.d);
    const best = scored[0].d;
    return scored.filter((s) => s.d <= best + 0.28).map((s) => s.e);
  }

  // reason: "state" = theme/variant changed, "rotate" = tab switch,
  // "fit" = viewport resized (only swaps when the current image no longer
  // belongs to the eligible pool).
  function applyBackground(reason) {
    const layerA = document.getElementById("bg-photo-a");
    const layerB = document.getElementById("bg-photo-b");
    if (!layerA || !layerB) return;
    const layers = [layerA, layerB];
    const variant = currentEvaVariant();
    const pool = variant ? bgEligible(variant) : [];
    document.body.classList.toggle("has-bg-photo", pool.length > 0);
    if (!variant || !pool.length) {
      layers.forEach((l) => l.classList.remove("visible"));
      bgEngine.shown = null;
      bgEngine.variant = null;
      bgEngine.front = null;
      return;
    }
    const sameVariant = bgEngine.variant === variant;
    if (reason === "fit" && sameVariant && pool.some((e) => e.file === bgEngine.shown)) {
      return;
    }
    let candidates = pool;
    if (candidates.length > 1 && bgEngine.shown) {
      const rest = candidates.filter((e) => e.file !== bgEngine.shown);
      if (rest.length) candidates = rest;
    }
    const chosen = candidates[Math.floor(Math.random() * candidates.length)];
    if (sameVariant && chosen.file === bgEngine.shown) return;
    const url = bgEngine.baseUrl + chosen.file;
    // Decode can outlast rapid theme/tab flips — only the newest request may
    // paint, or an older image would land on top of a newer one.
    const req = ++bgEngine.req;
    const img = new Image();
    img.onload = () => {
      if (req !== bgEngine.req || currentEvaVariant() !== variant) return;
      const nextIdx = bgEngine.front === 0 ? 1 : 0;
      const next = layers[nextIdx];
      const cur = bgEngine.front === null ? null : layers[bgEngine.front];
      next.style.backgroundImage = `url("${url}")`;
      next.classList.add("visible");
      if (cur && cur !== next) cur.classList.remove("visible");
      bgEngine.front = nextIdx;
      bgEngine.shown = chosen.file;
      bgEngine.variant = variant;
    };
    img.onerror = () => {
      if (req !== bgEngine.req || currentEvaVariant() !== variant) return;
      // Failed decode: retry once with another candidate, else degrade to the
      // flat canvas instead of stranding the previous variant's artwork.
      const rest = pool.filter((e) => e.file !== chosen.file);
      if (!rest.length) {
        layers.forEach((l) => l.classList.remove("visible"));
        document.body.classList.remove("has-bg-photo");
        bgEngine.shown = null;
        bgEngine.variant = null;
        bgEngine.front = null;
        return;
      }
      const next = rest[Math.floor(Math.random() * rest.length)];
      const retry = new Image();
      retry.onload = () => {
        if (req !== bgEngine.req || currentEvaVariant() !== variant) return;
        const nextIdx = bgEngine.front === 0 ? 1 : 0;
        const layer = layers[nextIdx];
        const cur = bgEngine.front === null ? null : layers[bgEngine.front];
        layer.style.backgroundImage = `url("${bgEngine.baseUrl + next.file}")`;
        layer.classList.add("visible");
        if (cur && cur !== layer) cur.classList.remove("visible");
        bgEngine.front = nextIdx;
        bgEngine.shown = next.file;
        bgEngine.variant = variant;
      };
      retry.src = bgEngine.baseUrl + next.file;
    };
    img.src = url;
  }

  let bgResizeTimer = null;
  window.addEventListener("resize", () => {
    if (bgResizeTimer) clearTimeout(bgResizeTimer);
    bgResizeTimer = setTimeout(() => applyBackground("fit"), 400);
  });

  // ------------------------------------------------------------------------
  // Liquid-glass tuner
  //
  // Two knobs drive every glass panel via the --glass-blur / --glass-alpha
  // custom properties (see the EVA token block in styles.css). Values are
  // per-browser preferences; at the defaults the inline overrides are
  // removed so the stylesheet's own numbers stay authoritative.
  // ------------------------------------------------------------------------

  const GLASS_DEFAULTS = { blur: 10, alpha: 100 };

  function glassSetting(key, fallback, min, max) {
    // Clamped to the slider bounds: a stale or hand-edited localStorage value
    // must never drive the CSS outside what the UI can express.
    const v = parseInt(safeStorageGet(key), 10);
    if (!Number.isFinite(v)) return fallback;
    return Math.min(max, Math.max(min, v));
  }

  function applyGlassSettings() {
    const blur = glassSetting("magi-glass-blur", GLASS_DEFAULTS.blur, 0, 30);
    const alpha = glassSetting("magi-glass-alpha", GLASS_DEFAULTS.alpha, 40, 170);
    const crt = safeStorageGet("magi-crt") === "on";
    const root = document.documentElement.style;
    if (blur === GLASS_DEFAULTS.blur) root.removeProperty("--glass-blur");
    else root.setProperty("--glass-blur", `${blur}px`);
    if (alpha === GLASS_DEFAULTS.alpha) root.removeProperty("--glass-alpha");
    else root.setProperty("--glass-alpha", String(alpha / 100));
    document.documentElement.classList.toggle("crt-on", crt);
    if (els.glassBlurRange) els.glassBlurRange.value = blur;
    if (els.glassAlphaRange) els.glassAlphaRange.value = alpha;
    if (els.glassBlurVal) els.glassBlurVal.textContent = `${blur}px`;
    if (els.glassAlphaVal) els.glassAlphaVal.textContent = `${alpha}%`;
    if (els.glassCrtToggle) els.glassCrtToggle.checked = crt;
  }

  if (els.glassTunerBtn) {
    els.glassTunerBtn.addEventListener("click", () => {
      els.glassTunerPanel.classList.toggle("open");
    });
  }
  if (els.glassBlurRange) {
    els.glassBlurRange.addEventListener("input", () => {
      safeStorageSet("magi-glass-blur", els.glassBlurRange.value);
      applyGlassSettings();
    });
  }
  if (els.glassAlphaRange) {
    els.glassAlphaRange.addEventListener("input", () => {
      safeStorageSet("magi-glass-alpha", els.glassAlphaRange.value);
      applyGlassSettings();
    });
  }
  if (els.glassCrtToggle) {
    els.glassCrtToggle.addEventListener("change", () => {
      safeStorageSet("magi-crt", els.glassCrtToggle.checked ? "on" : "off");
      applyGlassSettings();
    });
  }
  if (els.glassResetBtn) {
    els.glassResetBtn.addEventListener("click", () => {
      safeStorageSet("magi-glass-blur", String(GLASS_DEFAULTS.blur));
      safeStorageSet("magi-glass-alpha", String(GLASS_DEFAULTS.alpha));
      safeStorageSet("magi-crt", "off");
      applyGlassSettings();
    });
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
      if (!els.evaClock) return;
      const d = new Date();
      els.evaClock.textContent =
        `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
        `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };
    tick();
    evaClockTimer = setInterval(tick, 1000);
  }

  function stopEvaClock() {
    if (evaClockTimer) {
      clearInterval(evaClockTimer);
      evaClockTimer = null;
    }
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
    evaBootTimer = setTimeout(() => {
      b.classList.remove("active");
      evaBootTimer = null;
    }, 2600);
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
    const casDetail = `INDEX ${core.chunks || 0} / SEMANTIC ${core.vectors || 0}`;
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
  // Three-core status band (persistent across tabs)
  // ------------------------------------------------------------------------

  // Reuses evaCoreState()'s classification so the band and the EVA HUD can
  // never disagree about a core's health; only the wording differs — the HUD
  // speaks NERV codes, the band speaks the UI language.
  const CORE_STATUS_KEYS = {
    "state-ok": "core_state_ok",
    "state-warn": "core_state_attention",
    "state-err": "core_state_fault",
    "state-off": "core_state_offline",
  };

  function coreBandVitals(kind, core) {
    const st = evaCoreState(kind, core);
    const cls = st.cls;
    const stat = t(CORE_STATUS_KEYS[cls] || "core_state_offline");
    if (!core) return { cls, stat, detail: t("core_detail_nolink") };
    if (kind === "mel") {
      return {
        cls,
        stat,
        detail: t("core_detail_mel", {
          c: core.concepts || 0,
          r: core.references || 0,
          v: core.claims_verified || 0,
          n: core.claims || 0,
        }),
      };
    }
    if (kind === "bal") {
      if (core.state === "disabled") return { cls, stat, detail: t("core_detail_bal_kbonly") };
      if (!core.bd_installed) return { cls, stat, detail: t("core_detail_bal_noengine") };
      if (!core.beads_root) return { cls, stat, detail: t("core_detail_bal_uninit") };
      return {
        cls,
        stat,
        detail: t("core_detail_bal", {
          r: core.ready ?? 0,
          p: core.in_progress ?? 0,
          b: core.blocked ?? 0,
        }),
      };
    }
    if (core.state === "missing" || core.state === "offline") {
      return { cls, stat, detail: t("core_detail_cas_noindex") };
    }
    return { cls, stat, detail: t("core_detail_cas", { c: core.chunks || 0, v: core.vectors || 0 }) };
  }

  function updateCoreBand(rep) {
    const cores = (rep && rep.cores) || {};
    const mapping = { mel: "melchior", bal: "balthasar", cas: "casper" };
    for (const [short, full] of Object.entries(mapping)) {
      const v = coreBandVitals(short, cores[full] || null);
      const dot = document.getElementById(`core-dot-${short}`);
      const statEl = document.getElementById(`core-stat-${short}`);
      const detEl = document.getElementById(`core-detail-${short}`);
      if (dot) dot.className = `core-dot ${v.cls}`;
      if (statEl) statEl.textContent = v.stat;
      if (detEl) detEl.textContent = v.detail;
    }

    const ratio = rep && rep.sync_ratio !== null && rep.sync_ratio !== undefined ? rep.sync_ratio : null;
    const fill = document.getElementById("core-sync-fill");
    if (fill) {
      fill.style.width = ratio !== null ? `${Math.max(0, Math.min(100, ratio))}%` : "0%";
      fill.className = ratio === null ? "" : ratio === 100 ? "is-ok" : ratio < 60 ? "is-low" : "is-mid";
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

    // Core-band text is generated, not data-i18n — repaint it from the last
    // sync report rather than refetching.
    updateCoreBand(state.syncReport || null);

    // Re-render doctor modal if open
    if (els.doctorModal && els.doctorModal.classList.contains("open")) {
      openDoctorModal();
    }

    // Re-render open danger modal with localized content if active
    if (pendingDangerOp && els.dangerModal && els.dangerModal.classList.contains("open")) {
      openDangerConfirm(pendingDangerOp);
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
    // Lets CSS react to the active tab (the EVA dashboard suppresses the
    // core band because the HUD monolith already states the same thing).
    document.body.dataset.tab = tabName;
    applyBackground("rotate");
    if (tabName !== "melchior") stopGraphMap();
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
        loadGraphBrowse(state.graphView);
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

  // "Server workspace" (launch location) vs "browsing workspace" (this
  // browser session's dropdown choice) are DIFFERENT concepts — the badge
  // makes the divergence visible instead of silent.
  function _normPath(p) {
    return String(p || "").replace(/\\/g, "/").replace(/\/+$/, "").toLowerCase();
  }

  function updateBrowsingBadge() {
    const badge = document.getElementById("browsing-badge");
    if (!badge) return;
    const browsing = state.workspace && state.serverWorkspace &&
      _normPath(state.workspace) !== _normPath(state.serverWorkspace);
    badge.style.display = browsing ? "" : "none";
  }

  async function loadInitialStatus() {
    try {
      const status = await apiFetch("/api/status");
      els.appVersion.textContent = `v${status.version}`;
      state.workspace = status.active_workspace || "";
      state.serverWorkspace = status.active_workspace || "";

      await loadKBRegistry();

      // Restore this browser's last viewed workspace (session-level concept)
      const savedView = safeStorageGet("magi-view-workspace");
      if (savedView && savedView !== state.workspace &&
          state.kbs.some((kb) => kb.path === savedView)) {
        state.workspace = savedView;
        renderWorkspaceSelect();
      }
      updateBrowsingBadge();
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
      state.syncReport = rep;
      updateEvaHud(rep);
      updateCoreBand(rep);
      renderSyncHints(rep.hints_structured, rep.hints);
    } catch (err) {
      els.syncRatioVal.textContent = "--%";
      state.syncReport = null;
      if (els.dashSyncRatio) els.dashSyncRatio.textContent = "--%";
      updateEvaHud(null);
      updateCoreBand(null);
      renderSyncHints([], []);
    }
  }

  // ------------------------------------------------------------------------
  // Actionable sync hints
  // ------------------------------------------------------------------------

  // Keyed by the sync report's structured hint codes (report.hints_structured
  // from the backend) — no prose parsing.
  const HINT_ACTIONS = {
    "graph-stale": { i18n: "hint_graph_build", action: { type: "job", op: "graph-build", nameKey: "op_build_graph" } },
    "index-missing": { i18n: "hint_index", action: { type: "job", op: "index", nameKey: "op_rebuild_index" } },
    "index-stale": { i18n: "hint_index", action: { type: "job", op: "index", nameKey: "op_rebuild_index" } },
    "backlog-untracked": { i18n: "hint_backlog_sync", action: { type: "job", op: "backlog-sync", nameKey: "op_backlog_sync" } },
    "pm-uninit": { i18n: "hint_pm_init", action: { type: "tab", tab: "operations" } },
    "radar-digests-pending": { i18n: "hint_radar_review", action: { type: "tab", tab: "radar" } },
    "radar-gaps-pending": { i18n: "hint_radar_review", action: { type: "tab", tab: "radar" } },
    "claims-unverified": { i18n: "hint_claims_unverified", action: { type: "tab", tab: "melchior" } },
    "bd-ready": { i18n: "hint_bd_ready", action: { type: "tab", tab: "balthasar" } },
    "beads-missing": { i18n: "hint_install_beads", action: null },
    "ingest-start": { i18n: "hint_ingest_start", action: null },
    "hub-topics": { i18n: null, action: null },
  };

  function renderSyncHints(structured, plain) {
    const card = document.getElementById("sync-hints-card");
    const list = document.getElementById("sync-hints-list");
    if (!card || !list) return;
    list.innerHTML = "";
    // Prefer structured hints; fall back to bare strings from older servers.
    let items = Array.isArray(structured) ? structured : [];
    if (!items.length && Array.isArray(plain)) {
      items = plain.map((s) => ({ code: null, text: s }));
    }
    if (!items.length) {
      card.style.display = "none";
      return;
    }
    card.style.display = "";
    items.forEach((item) => {
      const raw = item.text || "";
      const rule = item.code ? HINT_ACTIONS[item.code] : null;
      const row = document.createElement("div");
      row.className = "action-row";
      const left = document.createElement("div");
      left.className = "row-main";
      if (rule && rule.i18n) {
        const label = document.createElement("div");
        label.className = "row-title";
        label.textContent = t(rule.i18n);
        left.appendChild(label);
      }
      const code = document.createElement("code");
      code.className = "row-code";
      code.textContent = raw;
      left.appendChild(code);
      row.appendChild(left);
      if (rule && rule.action) {
        const btn = document.createElement("button");
        btn.className = "btn btn-secondary btn-sm";
        if (rule.action.type === "job") {
          btn.textContent = t("btn_hint_run");
          btn.addEventListener("click", () => launchJob(rule.action.op, t(rule.action.nameKey)));
        } else {
          btn.textContent = t("btn_hint_goto");
          btn.addEventListener("click", () => switchTab(rule.action.tab));
        }
        row.appendChild(btn);
      }
      list.appendChild(row);
    });
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
        const pendingN = (radar.pending_digests ? radar.pending_digests.length : 0)
          + (radar.pending_citation_gaps ? radar.pending_citation_gaps.length : 0);
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

      loadConfigCard();
    }
  }

  function renderKBTable(kbs) {
    if (!kbs.length) {
      els.kbTableBody.innerHTML = `<tr><td colspan="7" class="empty-cell">${t("no_kbs_registered")}</td></tr>`;
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
        safeStorageSet("magi-view-workspace", state.workspace);
        updateBrowsingBadge();
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
        els.claimsTableBody.innerHTML = `<tr><td colspan="4" class="empty-cell">${t("no_claims")}</td></tr>`;
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
                <td><em class="row-sub">"${escapeHtml(c.quote || "")}"</em></td>
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
        els.backlogList.innerHTML = `<li class="file-li muted">${t("clean_backlog")}</li>`;
      } else {
        els.backlogList.innerHTML = backlog
          .map((item) => `<li class="file-li">${escapeHtml(item)}</li>`)
          .join("");
      }
    } catch (_) {}

    loadBibList();
    loadDraftsList();
  }

  async function executeGraphSql(sql) {
    if (!state.workspace || !sql.trim()) return;
    els.sqlResultContainer.innerHTML = `<p class="empty-note">${t("sql_executing")}</p>`;
    try {
      const data = await apiFetch(
        `/api/workspace/graph/query?sql=${encodeURIComponent(sql)}&workspace=${encodeURIComponent(state.workspace)}`
      );
      const cols = data.columns || [];
      const rows = data.rows || [];

      if (!rows.length) {
        els.sqlResultContainer.innerHTML = `<p class="empty-note">${t("sql_zero_rows")}</p>`;
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
      els.sqlResultContainer.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------------
  // Knowledge graph browser
  // ------------------------------------------------------------------------

  const GRAPH_TYPE_KEYS = {
    concept: "graph_type_concept",
    reference: "graph_type_reference",
    topic: "graph_type_topic",
    thesis: "graph_type_thesis",
    claim: "graph_type_claim",
    tag: "graph_type_tag",
  };

  const GRAPH_FILTERED_VIEWS = ["nodes", "claims", "tags"];

  function graphTypeLabel(type) {
    return GRAPH_TYPE_KEYS[type] ? t(GRAPH_TYPE_KEYS[type]) : (type || "");
  }

  function graphClaimStatusLabel(status) {
    if (status === "verified") return t("status_verified");
    if (status === "web-verified") return t("status_web_verified");
    if (status === "unverified") return t("status_unverified");
    return status || "";
  }

  function updateGraphChips(view) {
    // "hubs" is the server's answer to "links without a node" — same chip.
    const chipView = view === "hubs" ? "links" : view;
    els.graphViewBtns.forEach((b) => b.classList.toggle("active", b.dataset.view === chipView));
  }

  function updateGraphFilterRow(view) {
    if (!els.graphFilterRow) return;
    els.graphFilterRow.style.display = GRAPH_FILTERED_VIEWS.includes(view) ? "" : "none";
    if (els.graphType) els.graphType.style.display = view === "nodes" ? "" : "none";
  }

  function openGraphNode(nodeId) {
    state.graphNode = nodeId;
    loadGraphBrowse("links");
  }

  async function loadGraphBrowse(view) {
    if (!els.graphBrowseContainer || !state.workspace) return;
    state.graphView = view;
    updateGraphChips(view);
    updateGraphFilterRow(view);
    const isMap = view === "map";
    if (els.graphMapWrap) els.graphMapWrap.style.display = isMap ? "" : "none";
    els.graphBrowseContainer.style.display = isMap ? "none" : "";
    if (isMap) {
      loadGraphMap();
      return;
    }
    stopGraphMap();
    els.graphBrowseContainer.innerHTML = `<p class="empty-note">${t("graph_loading")}</p>`;
    const params = new URLSearchParams({ view, workspace: state.workspace });
    if (GRAPH_FILTERED_VIEWS.includes(view) && els.graphQ && els.graphQ.value.trim()) {
      params.set("q", els.graphQ.value.trim());
    }
    if (view === "nodes" && els.graphType && els.graphType.value) {
      params.set("type", els.graphType.value);
    }
    if (view === "links" && state.graphNode) {
      params.set("node", state.graphNode);
    }
    // Rapid view/workspace switches race their fetches; only the newest
    // request may paint the container.
    const token = ++loadGraphBrowse._req;
    try {
      const data = await apiFetch(`/api/workspace/graph/browse?${params.toString()}`);
      if (token !== loadGraphBrowse._req) return;
      renderGraphBrowse(data);
    } catch (err) {
      if (token !== loadGraphBrowse._req) return;
      els.graphBrowseContainer.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
    }
  }
  loadGraphBrowse._req = 0;

  function renderGraphBrowse(data) {
    let view = data.view;
    const results = data.results;
    // Older servers answer node-less "links" with a hub list under the
    // requested view name; the payload shape is the reliable signal.
    if (view === "links" && Array.isArray(results)) view = "hubs";
    updateGraphChips(view);
    switch (view) {
      case "overview":
        renderGraphOverview(results || {});
        break;
      case "nodes":
        renderGraphNodes(results || []);
        break;
      case "links":
        renderGraphLinks(results || {});
        break;
      case "hubs":
        renderGraphHubs(results || []);
        break;
      case "claims":
        renderGraphClaims(results || []);
        break;
      case "tags":
        renderGraphTags(results || []);
        break;
      case "broken":
        renderGraphBroken(results || []);
        break;
    }
  }

  function renderGraphOverview(ov) {
    const section = (label) =>
      `<tr><td colspan="2"><span class="badge badge-muted">${escapeHtml(label)}</span></td></tr>`;
    let html = `<table class="data-table"><tbody>`;
    html += section(t("graph_view_nodes"));
    Object.entries(ov.nodes_by_type || {}).forEach(([type, n]) => {
      html += `<tr><td>${escapeHtml(graphTypeLabel(type))}</td><td>${escapeHtml(String(n))}</td></tr>`;
    });
    html += section(t("graph_view_links"));
    Object.entries(ov.edges_by_type || {}).forEach(([type, n]) => {
      html += `<tr><td><code>${escapeHtml(type)}</code></td><td>${escapeHtml(String(n))}</td></tr>`;
    });
    html += `<tr><td>${escapeHtml(t("graph_view_tags"))}</td><td>${escapeHtml(String(ov.tags || 0))}</td></tr>`;
    html += section(t("graph_view_claims"));
    Object.entries(ov.claims_by_status || {}).forEach(([status, n]) => {
      html += `<tr><td>${escapeHtml(graphClaimStatusLabel(status))}</td><td>${escapeHtml(String(n))}</td></tr>`;
    });
    html += `<tr><td>${escapeHtml(t("graph_view_broken"))}</td>` +
      `<td><button type="button" class="graph-link-btn" data-goto="broken">${escapeHtml(String(ov.broken_links || 0))}</button></td></tr>`;
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    const jump = els.graphBrowseContainer.querySelector('[data-goto="broken"]');
    if (jump) jump.addEventListener("click", () => loadGraphBrowse("broken"));
  }

  function attachGraphRowClicks() {
    els.graphBrowseContainer.querySelectorAll("[data-node-id]").forEach((tr) => {
      tr.addEventListener("click", () => openGraphNode(tr.dataset.nodeId));
    });
  }

  function renderGraphNodes(rows) {
    if (!rows.length) {
      els.graphBrowseContainer.innerHTML = `<p class="empty-note">${t("graph_empty")}</p>`;
      return;
    }
    let html = `<table class="data-table"><thead><tr>` +
      `<th>${t("graph_th_title")}</th><th>${t("graph_th_type")}</th>` +
      `<th>${t("graph_th_degree")}</th><th>${t("graph_th_updated")}</th></tr></thead><tbody>`;
    rows.forEach((r) => {
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.id)}">` +
        `<td>${escapeHtml(r.title || r.id)}</td>` +
        `<td><span class="badge badge-muted">${escapeHtml(graphTypeLabel(r.type))}</span></td>` +
        `<td>${escapeHtml(String(r.degree ?? 0))}</td>` +
        `<td>${escapeHtml(r.updated || "")}</td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    attachGraphRowClicks();
  }

  function renderGraphLinks(res) {
    const node = res.node;
    const nodeTitle = node ? (node.title || node.id) : (state.graphNode || "");
    let html = `<div class="graph-node-head">` +
      `<strong>${escapeHtml(nodeTitle)}</strong>` +
      (node ? `<span class="badge badge-muted">${escapeHtml(graphTypeLabel(node.type))}</span>` : "") +
      `<button type="button" class="btn btn-secondary btn-sm" data-graph-back>${t("graph_back")}</button>` +
      `</div>`;
    // "type" here is the edge type (wikilink / supported_by / has_claim),
    // not a node type — render it raw.
    const linkTable = (label, rows, direction) => {
      let s = `<div class="graph-subhead"><span class="badge badge-muted">${escapeHtml(label)}</span></div>`;
      if (!rows.length) {
        s += `<p class="empty-note">${t("graph_empty")}</p>`;
        return s;
      }
      s += `<table class="data-table"><tbody>`;
      rows.forEach((r) => {
        if (direction === "out" && (r.title === null || r.title === undefined)) {
          s += `<tr><td><span class="graph-dangling">${escapeHtml(r.target_id)}</span> ` +
            `<span class="badge badge-terracotta">${t("graph_view_broken")}</span></td>` +
            `<td><code>${escapeHtml(r.type || "")}</code></td></tr>`;
          return;
        }
        const id = direction === "out" ? r.target_id : r.source_id;
        s += `<tr class="graph-row-click" data-node-id="${escapeHtml(id)}">` +
          `<td>${escapeHtml(r.title || id)}</td>` +
          `<td><code>${escapeHtml(r.type || "")}</code></td></tr>`;
      });
      s += `</tbody></table>`;
      return s;
    };
    html += linkTable(t("graph_out"), res.outgoing || [], "out");
    html += linkTable(t("graph_in"), res.incoming || [], "in");
    els.graphBrowseContainer.innerHTML = html;
    const back = els.graphBrowseContainer.querySelector("[data-graph-back]");
    if (back) {
      back.addEventListener("click", () => {
        state.graphNode = null;
        loadGraphBrowse("nodes");
      });
    }
    attachGraphRowClicks();
  }

  function renderGraphHubs(rows) {
    let html = `<p class="empty-note">${t("graph_hubs_hint")}</p>`;
    if (!rows.length) {
      els.graphBrowseContainer.innerHTML = html + `<p class="empty-note">${t("graph_empty")}</p>`;
      return;
    }
    html += `<table class="data-table"><thead><tr>` +
      `<th>${t("graph_th_title")}</th><th>${t("graph_th_type")}</th>` +
      `<th>${t("graph_th_degree")}</th></tr></thead><tbody>`;
    rows.forEach((r) => {
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.id)}">` +
        `<td>${escapeHtml(r.title || r.id)}</td>` +
        `<td><span class="badge badge-muted">${escapeHtml(graphTypeLabel(r.type))}</span></td>` +
        `<td>${escapeHtml(String(r.degree ?? 0))}</td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    attachGraphRowClicks();
  }

  function renderGraphClaims(rows) {
    if (!rows.length) {
      els.graphBrowseContainer.innerHTML = `<p class="empty-note">${t("graph_empty")}</p>`;
      return;
    }
    let html = `<table class="data-table"><thead><tr>` +
      `<th>${t("th_claim_status")}</th><th>${t("graph_th_text")}</th>` +
      `<th>${t("graph_th_doc")}</th></tr></thead><tbody>`;
    rows.forEach((c) => {
      const badgeClass = c.status === "verified" ? "badge-sage" : "badge-muted";
      html += `<tr><td><span class="badge ${badgeClass}">${escapeHtml(graphClaimStatusLabel(c.status))}</span></td>` +
        `<td>${escapeHtml(c.text || "")}</td>` +
        `<td><code>${escapeHtml(c.doc_id || "")}</code></td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
  }

  function renderGraphTags(rows) {
    if (!rows.length) {
      els.graphBrowseContainer.innerHTML = `<p class="empty-note">${t("graph_empty")}</p>`;
      return;
    }
    let html = `<table class="data-table"><thead><tr>` +
      `<th>${t("graph_th_tag")}</th><th>${t("graph_th_count")}</th></tr></thead><tbody>`;
    rows.forEach((r) => {
      html += `<tr class="graph-row-click" data-tag="${escapeHtml(r.tag)}">` +
        `<td>${escapeHtml(r.tag)}</td><td>${escapeHtml(String(r.count ?? 0))}</td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    els.graphBrowseContainer.querySelectorAll("[data-tag]").forEach((tr) => {
      tr.addEventListener("click", () => {
        if (els.graphQ) els.graphQ.value = tr.dataset.tag;
        loadGraphBrowse("nodes");
      });
    });
  }

  function renderGraphBroken(rows) {
    if (!rows.length) {
      els.graphBrowseContainer.innerHTML = `<p class="empty-note">${t("graph_broken_empty")}</p>`;
      return;
    }
    let html = `<table class="data-table"><thead><tr>` +
      `<th>${t("graph_th_source")}</th><th>${t("graph_th_target_missing")}</th>` +
      `<th>${t("graph_th_type")}</th></tr></thead><tbody>`;
    rows.forEach((r) => {
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.source_id)}">` +
        `<td>${escapeHtml(r.source_title || r.source_id)}</td>` +
        `<td><span class="graph-dangling">${escapeHtml(r.target_text)}</span></td>` +
        `<td><code>${escapeHtml(r.type || "")}</code></td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    attachGraphRowClicks();
  }

  // ------------------------------------------------------------------------
  // Knowledge-graph map — Obsidian-style force layout on canvas.
  // Physics comes from the vendored d3-force microlibs; rendering and
  // interaction are hand-rolled so node colours track the CSS theme tokens.
  // ------------------------------------------------------------------------

  const graphMap = {
    key: "",       // workspace|tags of the dataset currently simulated
    nodes: [],
    edges: [],
    adj: null,
    sim: null,
    tx: 0,
    ty: 0,
    k: 1,
    hover: null,
    drag: null,
    needsDraw: false,
    colors: null,
    colorsKey: "",
  };

  function graphMapColors() {
    // Colours are sampled from the live theme so the map repaints correctly
    // across light/dark/EVA-blue/EVA-red without any per-theme JS.
    const themeKey = `${document.documentElement.dataset.theme || ""}/${document.documentElement.dataset.eva || ""}`;
    if (graphMap.colors && graphMap.colorsKey === themeKey) return graphMap.colors;
    const cs = getComputedStyle(document.documentElement);
    const v = (name, fb) => cs.getPropertyValue(name).trim() || fb;
    graphMap.colorsKey = themeKey;
    graphMap.colors = {
      concept: v("--accent-primary", "#34597E"),
      reference: v("--accent-blue", "#3E7CB1"),
      topic: v("--accent-sage", "#6A8E5A"),
      thesis: v("--accent-sage", "#6A8E5A"),
      claim: v("--accent-amber", "#B98A2F"),
      tag: v("--text-subtle", "#9A968C"),
      ghost: v("--text-subtle", "#9A968C"),
      label: v("--text-secondary", "#4A463E"),
      edge: v("--text-subtle", "#C8C4B8"),
      family: getComputedStyle(document.body).fontFamily || "sans-serif",
    };
    return graphMap.colors;
  }

  function graphNodeRadius(n) {
    const r = Math.min(15, 3.5 + Math.sqrt(n.degree || 0) * 1.6);
    return n.type === "ghost" || n.type === "tag" ? Math.min(r, 9) * 0.8 : r;
  }

  function stopGraphMap() {
    if (graphMap.sim) graphMap.sim.stop();
  }

  function graphMapDPRSize() {
    const c = els.graphMapCanvas;
    const dpr = window.devicePixelRatio || 1;
    const w = els.graphMapWrap.clientWidth;
    const h = els.graphMapWrap.clientHeight;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) {
      c.width = Math.round(w * dpr);
      c.height = Math.round(h * dpr);
    }
    return { w, h, dpr };
  }

  function scheduleGraphMapDraw() {
    if (graphMap.needsDraw) return;
    graphMap.needsDraw = true;
    requestAnimationFrame(drawGraphMap);
  }

  function drawGraphMap() {
    graphMap.needsDraw = false;
    const c = els.graphMapCanvas;
    if (!c || !els.graphMapWrap || els.graphMapWrap.style.display === "none") return;
    const { w, h, dpr } = graphMapDPRSize();
    const ctx = c.getContext("2d");
    const col = graphMapColors();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.setTransform(dpr * graphMap.k, 0, 0, dpr * graphMap.k,
      dpr * (w / 2 + graphMap.tx), dpr * (h / 2 + graphMap.ty));
    const hover = graphMap.hover;
    const neigh = hover && graphMap.adj ? graphMap.adj.get(hover.id) : null;

    ctx.lineWidth = 1 / graphMap.k;
    for (const e of graphMap.edges) {
      const active = hover && (e.source.id === hover.id || e.target.id === hover.id);
      ctx.globalAlpha = hover ? (active ? 0.75 : 0.06) : e.type === "has_tag" ? 0.22 : 0.4;
      ctx.strokeStyle = col.edge;
      ctx.beginPath();
      ctx.moveTo(e.source.x, e.source.y);
      ctx.lineTo(e.target.x, e.target.y);
      ctx.stroke();
    }

    for (const n of graphMap.nodes) {
      const r = graphNodeRadius(n);
      const isHover = hover && n.id === hover.id;
      const isNeigh = neigh && neigh.has(n.id);
      ctx.globalAlpha = hover ? (isHover || isNeigh ? 1 : 0.14) : n.type === "ghost" ? 0.55 : 0.92;
      ctx.fillStyle = col[n.type] || col.concept;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      if (n.type === "ghost") {
        ctx.setLineDash([3 / graphMap.k, 3 / graphMap.k]);
        ctx.strokeStyle = col.ghost;
        ctx.stroke();
        ctx.setLineDash([]);
      } else {
        ctx.fill();
      }
      if (isHover) {
        ctx.lineWidth = 2 / graphMap.k;
        ctx.strokeStyle = col[n.type] || col.concept;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r + 3 / graphMap.k, 0, Math.PI * 2);
        ctx.stroke();
        ctx.lineWidth = 1 / graphMap.k;
      }
    }

    // Labels: the hovered neighbourhood always; otherwise only what stays
    // legible — well-connected nodes, or everything once zoomed in.
    ctx.font = `${11 / graphMap.k}px ${col.family}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    for (const n of graphMap.nodes) {
      const isHover = hover && n.id === hover.id;
      const isNeigh = neigh && neigh.has(n.id);
      const show = isHover || isNeigh || (!hover && (graphMap.k >= 1.25 || (n.degree || 0) >= 4));
      if (!show) continue;
      const label = n.title || n.id;
      ctx.globalAlpha = isHover ? 1 : 0.72;
      ctx.fillStyle = col.label;
      ctx.fillText(label.length > 30 ? label.slice(0, 29) + "…" : label,
        n.x, n.y + graphNodeRadius(n) + 3 / graphMap.k);
    }
    ctx.globalAlpha = 1;
  }

  async function loadGraphMap() {
    if (!els.graphMapCanvas) return;
    if (!window.d3 || !window.d3.forceSimulation) {
      if (els.graphMapNote) {
        els.graphMapNote.textContent = t("graph_map_no_d3");
        els.graphMapNote.style.display = "";
      }
      return;
    }
    const tags = !!(els.graphMapTags && els.graphMapTags.checked);
    const key = `${state.workspace}|${tags ? 1 : 0}`;
    if (graphMap.key === key && graphMap.nodes.length) {
      // stopGraphMap may have frozen a mid-settle layout on tab leave —
      // resume unless the simulation had already cooled down.
      if (graphMap.sim && graphMap.sim.alpha() > graphMap.sim.alphaMin()) {
        graphMap.sim.restart();
      }
      renderGraphMapNote();
      scheduleGraphMapDraw();
      return;
    }
    const params = new URLSearchParams({ view: "map", workspace: state.workspace });
    if (tags) params.set("tags", "true");
    try {
      const data = await apiFetch(`/api/workspace/graph/browse?${params.toString()}`);
      // The workspace selector may have moved on while this fetch ran —
      // a stale response must not overwrite the newer dataset.
      const nowKey = `${state.workspace}|${els.graphMapTags && els.graphMapTags.checked ? 1 : 0}`;
      if (nowKey !== key) return;
      buildGraphMap(data.results || {}, key);
    } catch (err) {
      if (els.graphMapNote) {
        els.graphMapNote.textContent = err.message;
        els.graphMapNote.style.display = "";
      }
    }
  }

  // Derives the corner note from graphMap state, so a language switch on a
  // cached dataset re-renders it in the new language instead of keeping the
  // old string.
  function renderGraphMapNote() {
    if (!els.graphMapNote) return;
    if (!graphMap.key) return;
    if (!graphMap.nodes.length) {
      els.graphMapNote.textContent = t("graph_map_empty");
      els.graphMapNote.style.display = "";
    } else if (graphMap.truncated) {
      els.graphMapNote.textContent = t("graph_map_truncated", { n: graphMap.nodes.length });
      els.graphMapNote.style.display = "";
    } else {
      els.graphMapNote.style.display = "none";
    }
  }

  function buildGraphMap(res, key) {
    stopGraphMap();
    graphMap.key = key;
    graphMap.nodes = (res.nodes || []).map((n) => ({ ...n }));
    const byId = new Map(graphMap.nodes.map((n) => [n.id, n]));
    graphMap.edges = (res.edges || [])
      .filter((e) => byId.has(e.source) && byId.has(e.target))
      .map((e) => ({ ...e }));
    graphMap.adj = new Map(graphMap.nodes.map((n) => [n.id, new Set()]));
    for (const e of graphMap.edges) {
      graphMap.adj.get(e.source).add(e.target);
      graphMap.adj.get(e.target).add(e.source);
    }
    graphMap.tx = 0;
    graphMap.ty = 0;
    graphMap.k = 1;
    graphMap.hover = null;
    graphMap.truncated = !!res.truncated;
    renderGraphMapNote();
    if (!graphMap.nodes.length) {
      scheduleGraphMapDraw();
      return;
    }
    // Deterministic golden-angle spiral seed keeps the first frames calm
    // instead of the default random burst.
    graphMap.nodes.forEach((n, i) => {
      const a = i * 2.399963;
      const r = 14 * Math.sqrt(i);
      n.x = Math.cos(a) * r;
      n.y = Math.sin(a) * r;
    });
    graphMap.sim = d3.forceSimulation(graphMap.nodes)
      .force("link", d3.forceLink(graphMap.edges).id((d) => d.id)
        .distance((e) => 40 + 6 * Math.sqrt((e.source.degree || 1) + (e.target.degree || 1)))
        .strength(0.5))
      .force("charge", d3.forceManyBody().strength(-130).distanceMax(400))
      .force("center", d3.forceCenter(0, 0))
      .force("collide", d3.forceCollide().radius((d) => graphNodeRadius(d) + 2.5))
      .alphaDecay(0.028)
      .on("tick", scheduleGraphMapDraw);
  }

  function graphMapPoint(ev) {
    const rect = els.graphMapCanvas.getBoundingClientRect();
    const sx = ev.clientX - rect.left;
    const sy = ev.clientY - rect.top;
    return {
      sx,
      sy,
      w: rect.width,
      h: rect.height,
      x: (sx - rect.width / 2 - graphMap.tx) / graphMap.k,
      y: (sy - rect.height / 2 - graphMap.ty) / graphMap.k,
    };
  }

  function graphMapHit(p) {
    let best = null;
    let bestD = Infinity;
    for (const n of graphMap.nodes) {
      const d = Math.hypot(n.x - p.x, n.y - p.y);
      if (d <= graphNodeRadius(n) + 4 / graphMap.k && d < bestD) {
        best = n;
        bestD = d;
      }
    }
    return best;
  }

  function bindGraphMapEvents() {
    const c = els.graphMapCanvas;
    if (!c) return;
    c.addEventListener("mousedown", (ev) => {
      if (!graphMap.nodes.length) return;
      const p = graphMapPoint(ev);
      const n = graphMapHit(p);
      if (n) {
        graphMap.drag = { node: n, moved: false };
        n.fx = n.x;
        n.fy = n.y;
        if (graphMap.sim) graphMap.sim.alphaTarget(0.25).restart();
      } else {
        graphMap.drag = { pan: true, sx: ev.clientX, sy: ev.clientY };
        c.style.cursor = "grabbing";
      }
      ev.preventDefault();
    });
    window.addEventListener("mousemove", (ev) => {
      if (graphMap.drag) {
        if (graphMap.drag.node) {
          const p = graphMapPoint(ev);
          graphMap.drag.node.fx = p.x;
          graphMap.drag.node.fy = p.y;
          graphMap.drag.moved = true;
        } else {
          graphMap.tx += ev.clientX - graphMap.drag.sx;
          graphMap.ty += ev.clientY - graphMap.drag.sy;
          graphMap.drag.sx = ev.clientX;
          graphMap.drag.sy = ev.clientY;
          scheduleGraphMapDraw();
        }
        return;
      }
      if (ev.target !== c || !graphMap.nodes.length) return;
      const n = graphMapHit(graphMapPoint(ev));
      if (n !== graphMap.hover) {
        graphMap.hover = n;
        c.style.cursor = n ? "pointer" : "grab";
        scheduleGraphMapDraw();
      }
    });
    window.addEventListener("mouseup", () => {
      if (!graphMap.drag) return;
      const d = graphMap.drag;
      graphMap.drag = null;
      c.style.cursor = "grab";
      if (d.node) {
        if (graphMap.sim) graphMap.sim.alphaTarget(0);
        d.node.fx = null;
        d.node.fy = null;
        // A press that never moved is a click: drill into that node's links.
        if (!d.moved && d.node.type !== "ghost") openGraphNode(d.node.id);
      }
    });
    c.addEventListener("mouseleave", () => {
      if (graphMap.hover && !graphMap.drag) {
        graphMap.hover = null;
        c.style.cursor = "grab";
        scheduleGraphMapDraw();
      }
    });
    c.addEventListener("wheel", (ev) => {
      if (!graphMap.nodes.length) return;
      ev.preventDefault();
      const p = graphMapPoint(ev);
      const k2 = Math.min(6, Math.max(0.2, graphMap.k * Math.exp(-ev.deltaY * 0.0016)));
      // Keep the world point under the cursor fixed while zooming.
      graphMap.tx = p.sx - p.w / 2 - p.x * k2;
      graphMap.ty = p.sy - p.h / 2 - p.y * k2;
      graphMap.k = k2;
      scheduleGraphMapDraw();
    }, { passive: false });
    if (els.graphMapTags) {
      els.graphMapTags.addEventListener("change", () => {
        graphMap.key = "";
        loadGraphMap();
      });
    }
    if (window.ResizeObserver && els.graphMapWrap) {
      new ResizeObserver(() => scheduleGraphMapDraw()).observe(els.graphMapWrap);
    }
  }

  bindGraphMapEvents();

  // ------------------------------------------------------------------------
  // References & citations (magi bib), drafts, workspace config
  // ------------------------------------------------------------------------

  async function copyToClipboard(text, count) {
    try {
      await navigator.clipboard.writeText(text);
      showToast(t("toast_bib_copied", { n: count }), "success");
    } catch (_) {
      showToast("clipboard unavailable", "error");
    }
  }

  async function loadBibList() {
    const list = document.getElementById("bib-list");
    if (!list || !state.workspace) return;
    list.innerHTML = `<p class="empty-note">${t("bib_loading")}</p>`;
    let data = null;
    try {
      const res = await fetch(`/api/workspace/bib?all=1&workspace=${encodeURIComponent(state.workspace)}`);
      if (res.ok) data = await res.json();
    } catch (_) {}
    state.bibEntries = (data && data.entries) || [];
    if (!state.bibEntries.length) {
      list.innerHTML = `<p class="empty-note">${t("bib_none")}</p>`;
      return;
    }
    list.innerHTML = "";
    state.bibEntries.forEach((e) => {
      const row = document.createElement("div");
      row.className = "list-row";
      const left = document.createElement("div");
      left.className = "row-main";
      const tl = document.createElement("div");
      tl.className = "row-title trunc";
      tl.textContent = (e.title || e.card) + (e.year ? ` (${e.year})` : "");
      left.appendChild(tl);
      const sub = document.createElement("code");
      sub.className = "row-code";
      sub.textContent = e.bibtex ? e.card : `${e.card} — ${t("bib_no_entry")}`;
      left.appendChild(sub);
      row.appendChild(left);
      if (e.bibtex) {
        const btn = document.createElement("button");
        btn.className = "btn btn-secondary btn-sm";
        btn.textContent = t("btn_copy_bibtex");
        btn.addEventListener("click", () => copyToClipboard(e.bibtex, 1));
        row.appendChild(btn);
      }
      list.appendChild(row);
    });
  }

  async function loadDraftsList() {
    const ul = document.getElementById("drafts-list");
    if (!ul || !state.workspace) return;
    try {
      const data = await apiFetch(`/api/workspace/drafts?workspace=${encodeURIComponent(state.workspace)}`);
      const drafts = data.drafts || [];
      if (!drafts.length) {
        ul.innerHTML = `<li class="file-li muted">${t("drafts_none")}</li>`;
        return;
      }
      ul.innerHTML = drafts
        .map((d) => `<li class="file-li">${escapeHtml(d.path)}${d.title ? ` — <span class="row-sub">${escapeHtml(d.title)}</span>` : ""}</li>`)
        .join("");
    } catch (_) {}
  }

  const CFG_LABEL_KEYS = {
    "radar.min_relevance": "cfg_f_radar_min_relevance",
    "radar.days": "cfg_f_radar_days",
    "radar.max_candidates": "cfg_f_radar_max_candidates",
    "radar.arxiv_categories": "cfg_f_radar_arxiv_categories",
    "radar.seed_arxiv_ids": "cfg_f_radar_seed_arxiv_ids",
    "radar.own_arxiv_ids": "cfg_f_radar_own_arxiv_ids",
    "ocr.use_mineru": "cfg_f_ocr_use_mineru",
    "models.embedding": "cfg_f_models_embedding",
  };

  async function loadConfigCard() {
    const box = document.getElementById("config-fields");
    if (!box || !state.workspace) return;
    try {
      const data = await apiFetch(`/api/workspace/config?workspace=${encodeURIComponent(state.workspace)}`);
      box.innerHTML = "";
      (data.fields || []).forEach((f) => {
        const row = document.createElement("div");
        row.className = "cfg-row";
        const label = document.createElement("div");
        label.className = "cfg-label";
        const name = document.createElement("code");
        name.className = "cfg-key";
        name.textContent = f.key;
        const desc = document.createElement("div");
        desc.className = "cfg-desc";
        desc.textContent = t(CFG_LABEL_KEYS[f.key] || f.key);
        label.appendChild(name);
        label.appendChild(desc);
        row.appendChild(label);

        let input;
        if (f.type === "bool") {
          input = document.createElement("input");
          input.type = "checkbox";
          input.checked = !!f.value;
        } else {
          input = document.createElement("input");
          input.type = "text";
          input.className = "text-input cfg-input";
          if (f.type === "list") {
            input.value = (f.value || []).join(", ");
            input.placeholder = t("cfg_list_hint");
          } else {
            input.value = (f.value === null || f.value === undefined) ? "" : String(f.value);
          }
        }
        row.appendChild(input);

        const save = document.createElement("button");
        save.className = "btn btn-secondary btn-sm";
        save.textContent = t("btn_cfg_save");
        save.addEventListener("click", async () => {
          let value;
          if (f.type === "bool") {
            value = input.checked;
          } else if (f.type === "list") {
            value = input.value.split(",").map((s) => s.trim()).filter(Boolean);
          } else if (f.type === "int") {
            value = parseInt(input.value, 10);
            if (isNaN(value)) { showToast(`${f.key}: invalid integer`, "error"); return; }
          } else if (f.type === "number") {
            value = input.value.trim() === "" ? null : parseFloat(input.value);
            if (value !== null && isNaN(value)) { showToast(`${f.key}: invalid number`, "error"); return; }
          } else {
            value = input.value.trim();
          }
          try {
            await apiFetch("/api/workspace/config", {
              method: "POST",
              body: JSON.stringify({ key: f.key, value, workspace: state.workspace }),
            });
            showToast(t("toast_cfg_saved", { key: f.key }), "success");
          } catch (_) {}
        });
        row.appendChild(save);
        box.appendChild(row);
      });
    } catch (_) {}
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
          <div class="banner-pill warning">
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
          <div class="banner-pill info">
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
    els.searchResultsList.innerHTML = `<p class="empty-note search-empty">${t("searching_text")}</p>`;
    els.searchInfoBar.textContent = "";

    const scopeSel = document.getElementById("search-scope-select");
    const collSel = document.getElementById("search-collection-select");
    const pathInput = document.getElementById("search-path-input");
    let qs = `q=${encodeURIComponent(query)}&mode=${mode}&limit=${limit}&workspace=${encodeURIComponent(state.workspace)}`;
    qs += `&scope=${(scopeSel && scopeSel.value) || "auto"}`;
    if (collSel && collSel.value) qs += `&collection=${encodeURIComponent(collSel.value)}`;
    if (pathInput && pathInput.value.trim()) qs += `&path=${encodeURIComponent(pathInput.value.trim())}`;

    try {
      const data = await apiFetch(`/api/workspace/search?${qs}`);

      if (data.error) {
        const hintLine = data.hint ? `<div class="hint-note">${escapeHtml(data.hint)}</div>` : "";
        els.searchResultsList.innerHTML = `<div class="banner-pill warning">${escapeHtml(localizeApiError(data.error))}</div>${hintLine}`;
        return;
      }

      const vecStatus = data.vector_available ? t("vec_avail_yes") : t("vec_avail_no");
      els.searchInfoBar.textContent = t("search_summary", {
        total: data.results.length,
        bm25: data.bm25_hits || 0,
        vec: vecStatus,
      });
      if (!data.vector_available) {
        const note = document.createElement("div");
        note.className = "hint-note";
        note.textContent = t("vec_unavailable_hint");
        els.searchInfoBar.appendChild(note);
      }

      if (!data.results.length) {
        els.searchResultsList.innerHTML =
          `<p class="empty-note search-empty" style="padding-bottom: 0.5rem;">${t("search_no_results")}</p>` +
          `<p class="empty-note center" style="padding-bottom: 2rem;">${t("search_no_results_hint")}</p>`;
        return;
      }

      els.searchResultsList.innerHTML = data.results
        .map((hit) => {
          const lineStart = hit.lines ? hit.lines[0] : hit.start_line;
          const lineEnd = hit.lines ? hit.lines[1] : hit.end_line;
          const kbBadge = hit.kb && hit.kb !== "local"
            ? `<span class="badge badge-blue">kb:${escapeHtml(hit.kb)}</span>` : "";
          const collBadge = hit.collection
            ? `<span class="badge badge-muted">${escapeHtml(hit.collection)}</span>` : "";
          return `
            <div class="search-hit-card">
              <div class="search-hit-header">
                <div class="search-hit-title">${escapeHtml(hit.heading || hit.path)}</div>
                <div class="search-hit-badges">
                  ${kbBadge}${collBadge}
                  <span class="badge badge-terracotta">RRF ${hit.score}</span>
                  ${hit.bm25_rank ? `<span class="badge badge-blue">BM25 #${hit.bm25_rank}</span>` : ""}
                  ${hit.vector_rank ? `<span class="badge badge-sage">Vec #${hit.vector_rank}</span>` : ""}
                </div>
              </div>
              <div class="search-hit-path">
                ${escapeHtml(hit.path)} (${t("search_lines", { start: lineStart, end: lineEnd })})
              </div>
              <div class="search-hit-snippet">${escapeHtml(hit.snippet || hit.content || "")}</div>
            </div>
          `;
        })
        .join("");
    } catch (err) {
      els.searchResultsList.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
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
      const radarPendingN = (radar.pending_digests ? radar.pending_digests.length : 0)
        + (radar.pending_citation_gaps ? radar.pending_citation_gaps.length : 0);
      els.radarPendingCount.textContent = radarPendingN;
      els.radarPendingCount.classList.toggle("eva-alert", radarPendingN > 0);

      const digests = radar.digests || [];
      if (!digests.length) {
        els.digestFilesList.innerHTML = `<p class="empty-note pad-1">${t("no_digests")}</p>`;
        els.digestViewer.innerHTML = `<p class="empty-note center mt-3">${t("digest_viewer_prompt")}</p>`;
        return;
      }

      els.digestFilesList.innerHTML = digests
        .map((d, idx) => {
          const isPending = d.status === "pending-review";
          const badgeClass = isPending ? "badge-terracotta" : "badge-sage";
          const badgeText = isPending ? t("status_pending_review") : t("status_reviewed");
          const kindBadge = d.kind === "citation-gap"
            ? `<span class="badge badge-blue" style="margin-left: 0.3rem;">${t("badge_kind_citation_gap")}</span>`
            : "";
          const isSelected = state.activeDigest ? (d.name === state.activeDigest) : (idx === 0);
          return `
            <div class="pane-item ${isSelected ? "active" : ""}" data-file="${escapeHtml(d.name)}">
              <div class="pane-item-name">${escapeHtml(d.name)}</div>
              <div class="pane-item-meta">
                <span class="badge ${badgeClass}">${escapeHtml(badgeText)}</span>${kindBadge}
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
    els.digestViewer.innerHTML = `<p class="empty-note">${t("digest_loading", { file: escapeHtml(filename) })}</p>`;
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
      renderDigestActions(data);
    } catch (err) {
      els.digestViewer.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // Review actions: mark-reviewed footer + per-candidate accept/task buttons
  function renderDigestActions(data) {
    const viewer = els.digestViewer;
    if (!viewer) return;

    const cands = data.candidates || [];
    if (cands.length && data.kind === "digest") {
      const box = document.createElement("div");
      box.className = "digest-actions";
      const title = document.createElement("div");
      title.className = "digest-actions-title";
      title.textContent = t("radar_actions_title");
      box.appendChild(title);

      const filterRow = document.createElement("div");
      filterRow.className = "digest-filter-row";
      const filterInput = document.createElement("input");
      filterInput.type = "text";
      filterInput.id = "radar-author-filter";
      filterInput.className = "text-input";
      filterInput.placeholder = t("radar_filter_ph");
      filterInput.setAttribute("data-i18n-placeholder", "radar_filter_ph");
      const filterCount = document.createElement("span");
      filterCount.id = "radar-filter-count";
      filterCount.className = "empty-note";
      filterRow.appendChild(filterInput);
      filterRow.appendChild(filterCount);
      box.appendChild(filterRow);

      cands.forEach((c) => {
        const row = document.createElement("div");
        row.className = "action-row";
        const authors = Array.isArray(c.authors) ? c.authors : [];
        row.dataset.search = `${c.title || ""} ${authors.join(" ")}`.toLowerCase();
        const left = document.createElement("div");
        left.className = "row-main";
        const label = document.createElement("div");
        label.className = "row-title trunc";
        const rel = (c.relevance !== null && c.relevance !== undefined) ? `[${c.relevance}] ` : "";
        label.textContent = rel + c.title;
        label.title = c.title;
        left.appendChild(label);
        if (authors.length) {
          const authorLine = document.createElement("div");
          authorLine.className = "row-authors";
          authorLine.textContent = authors.join(", ");
          authorLine.title = authors.join(", ");
          left.appendChild(authorLine);
        }
        row.appendChild(left);
        const btns = document.createElement("div");
        btns.className = "row-btns";
        [["accept-to-inbox", "btn_accept_inbox"], ["create-issue", "btn_create_issue"]].forEach(([action, key]) => {
          const b = document.createElement("button");
          b.className = "btn btn-secondary btn-sm";
          b.textContent = t(key);
          b.addEventListener("click", () => radarCandidateAction(data.file, c.index, action, b));
          btns.appendChild(b);
        });
        row.appendChild(btns);
        box.appendChild(row);
      });

      const applyCandidateFilter = () => {
        const q = filterInput.value.trim().toLowerCase();
        const rows = box.querySelectorAll(".action-row");
        let shown = 0;
        rows.forEach((r) => {
          const hit = !q || (r.dataset.search || "").includes(q);
          r.style.display = hit ? "" : "none";
          if (hit) shown++;
        });
        filterCount.textContent = t("radar_filter_count", { shown, total: rows.length });
      };
      filterInput.addEventListener("input", applyCandidateFilter);
      applyCandidateFilter();

      viewer.appendChild(box);
    }

    if (data.status === "pending-review") {
      const foot = document.createElement("div");
      foot.className = "digest-foot";
      const btn = document.createElement("button");
      btn.className = "btn btn-primary";
      btn.textContent = t("btn_mark_reviewed");
      btn.addEventListener("click", async () => {
        try {
          await apiFetch("/api/workspace/radar/review", {
            method: "POST",
            body: JSON.stringify({ file: data.file, action: "mark-reviewed", workspace: state.workspace }),
          });
          showToast(t("toast_marked_reviewed", { file: data.file }), "success");
          loadRadar();
        } catch (_) {}
      });
      foot.appendChild(btn);
      viewer.appendChild(foot);
    }
  }

  async function radarCandidateAction(file, index, action, btn) {
    btn.disabled = true;
    try {
      const res = await apiFetch("/api/workspace/radar/candidate", {
        method: "POST",
        body: JSON.stringify({ file, index, action, workspace: state.workspace }),
      });
      if (action === "accept-to-inbox") {
        showToast(t("toast_accepted", { path: res.created }), "success");
      } else {
        showToast(t("toast_issue_created"), "success");
      }
    } catch (_) {
      btn.disabled = false;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 6: Operations & SSE Terminal
  // ------------------------------------------------------------------------

  // Launch a whitelisted operation (see GET /api/ops). Raw argv is not a
  // thing anymore — the server rejects anything outside the catalog.
  async function launchJob(opId, displayName, confirmToken) {
    if (!state.workspace) {
      showToast(t("toast_select_ws_first"), "error");
      return;
    }

    try {
      const res = await apiFetch("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          op: opId,
          kb: state.workspace,
          confirm: confirmToken || null,
        }),
      });

      showToast(t("toast_job_started", { name: displayName || opId }), "info");
      switchTab("operations");
      startLogStream(res.job_id, displayName || opId);
    } catch (err) {
      showToast(t("toast_job_fail", { error: err.message }), "error");
    }
  }

  // ------------------------------------------------------------------------
  // Ops catalog (server-driven operation buttons)
  // ------------------------------------------------------------------------

  let OPS_CATALOG = [];
  let pendingDangerOp = null;

  async function loadOpsCatalog() {
    try {
      const data = await apiFetch("/api/ops");
      OPS_CATALOG = data.ops || [];
      renderOpsPanels();
    } catch (_) {}
  }

  function renderOpsPanels() {
    const common = document.getElementById("ops-common-grid");
    const danger = document.getElementById("ops-danger-grid");
    if (!common || !danger) return;
    common.innerHTML = "";
    danger.innerHTML = "";
    OPS_CATALOG.forEach((entry) => {
      const btn = document.createElement("button");
      btn.setAttribute("data-i18n", entry.label_i18n);
      btn.textContent = t(entry.label_i18n);
      btn.title = entry.argv.join(" ");
      if (entry.danger) {
        btn.className = "btn btn-danger danger-action-btn";
        btn.addEventListener("click", () => openDangerConfirm(entry));
        danger.appendChild(btn);
      } else {
        // radar ops already have dedicated buttons on the radar tab
        if (entry.op === "radar-harvest" || entry.op === "radar-citation-gap") return;
        btn.className = "btn btn-secondary op-task-btn";
        btn.addEventListener("click", () => launchJob(entry.op, t(entry.label_i18n)));
        common.appendChild(btn);
      }
    });
  }

  function openDangerConfirm(entry) {
    pendingDangerOp = entry;
    els.dangerModalTitle.textContent = `${t("danger_modal_prefix")}: ${t(entry.label_i18n)}`;
    const desc = entry.desc_i18n ? t(entry.desc_i18n) : "";
    els.dangerModalDesc.innerHTML = `
      <strong style="color: var(--accent-danger);">${t("warning_label")}:</strong> ${escapeHtml(desc)}
      <br><br>
      ${t("cmd_to_execute")}: <code>${escapeHtml(entry.argv.join(" "))}</code>
      <br><br>
      ${escapeHtml(t("danger_type_to_confirm", { op: entry.op }))}
    `;
    const input = document.getElementById("danger-confirm-input");
    if (input) input.value = "";
    els.dangerModal.classList.add("open");
    if (input) input.focus();
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
    const termContainer = els.terminalOutput ? els.terminalOutput.closest(".terminal-container") : null;
    if (termContainer) termContainer.classList.add("is-running");
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
            if (termContainer) termContainer.classList.remove("is-running");
            els.termCancelBtn.style.display = "none";
            showToast(t("toast_job_success", { name: jobName }), "success");
            source.close();
            state.activeJobId = null;
            els.termJobName.textContent = t("term_idle");
            loadSyncRatio();
          } else if (payload.status === "failed" || payload.status === "cancelled") {
            els.termStatusDot.className = "status-dot error";
            if (termContainer) termContainer.classList.remove("is-running");
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
      if (termContainer) termContainer.classList.remove("is-running");
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

    els.docsContent.innerHTML = `<p class="empty-note">${t("loading_docs")}</p>`;
    try {
      if (docKey === "commands") {
        const data = await apiFetch("/api/docs/commands");
        const cmds = data.commands || [];
        let html = `<h1>${t("docs_cmd_title")}</h1>`;
        html += `<p>${t("docs_cmd_sub")}</p>`;
        html += `<table class="data-table"><thead><tr><th>${t("th_cmd_command")}</th><th>${t("th_cmd_group")}</th><th>${t("th_cmd_desc")}</th></tr></thead><tbody>`;
        cmds.forEach((c) => {
          const desc = state.lang === "zh" ? (c.help_zh || c.help) : c.help;
          const groupTitle = (state.lang === "zh" && c.group_help_zh)
            ? ` title="${escapeHtml(c.group_help_zh)}"` : "";
          html += `<tr><td><code>${escapeHtml(c.command)}</code></td><td><span class="badge badge-muted"${groupTitle}>${escapeHtml(c.group || "core")}</span></td><td>${escapeHtml(desc)}</td></tr>`;
        });
        html += `</tbody></table>`;
        els.docsContent.innerHTML = html;
      } else {
        const langParam = docKey === "readme-en" ? "en" : "zh";
        const data = await apiFetch(`/api/docs/readme?lang=${langParam}`);
        // Installed (non-repo) deployments may only have the zh README from
        // package metadata — hide the EN toggle instead of showing a blank tab.
        const enBtn = document.querySelector('.doc-switch-btn[data-doc="readme-en"]');
        if (enBtn) enBtn.style.display = data.readme_en ? "" : "none";
        const mdText = data.content || (langParam === "en" ? data.readme_en : data.readme_zh) || t("no_docs_found");
        if (window.marked && mdText) {
          els.docsContent.innerHTML = window.marked.parse(mdText);
          // README references repo-relative images the local server does not
          // host — resolve them against the GitHub repo and hide any that
          // still fail (e.g. offline).
          els.docsContent.querySelectorAll("img").forEach((img) => {
            const src = img.getAttribute("src") || "";
            if (src && !/^(https?:|data:)/i.test(src)) {
              img.src = "https://raw.githubusercontent.com/Misaka16384/magi/main/" + src.replace(/^\.?\//, "");
            }
            img.addEventListener("error", () => { img.style.display = "none"; });
            img.style.maxWidth = "100%";
          });
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
    els.doctorModalBody.innerHTML = `<p class="empty-note">${t("doctor_running")}</p>`;
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
        // Inside MAGI MODE the toggle switches the alert state (blue/red)
        // by flipping the remembered base theme — it does not exit the mode.
        const currentBase = safeStorageGet("magi-base-theme") || "dark";
        safeStorageSet("magi-base-theme", currentBase === "dark" ? "light" : "dark");
        applyTheme("eva");
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

  // Workspace selector change (browsing choice — persisted per browser)
  els.workspaceSelect.addEventListener("change", (e) => {
    state.workspace = e.target.value;
    safeStorageSet("magi-view-workspace", state.workspace);
    updateBrowsingBadge();
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

  // Copy all BibTeX
  const copyAllBibBtn = document.getElementById("btn-copy-all-bib");
  if (copyAllBibBtn) {
    copyAllBibBtn.addEventListener("click", () => {
      const entries = (state.bibEntries || []).filter((e) => e.bibtex);
      if (!entries.length) {
        showToast(t("bib_none"), "info");
        return;
      }
      copyToClipboard(entries.map((e) => e.bibtex).join("\n\n") + "\n", entries.length);
    });
  }

  // Graph SQL Console
  els.runSqlBtn.addEventListener("click", () => executeGraphSql(els.sqlQueryInput.value));
  els.presetSqlBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      els.sqlQueryInput.value = btn.dataset.sql;
      executeGraphSql(btn.dataset.sql);
    });
  });

  // Knowledge graph browser
  els.graphViewBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      // Chip navigation always starts fresh; node drill-down keeps its own path.
      state.graphNode = null;
      loadGraphBrowse(btn.dataset.view);
    });
  });
  let graphFilterTimer = null;
  if (els.graphQ) {
    els.graphQ.addEventListener("input", () => {
      if (!GRAPH_FILTERED_VIEWS.includes(state.graphView)) return;
      if (graphFilterTimer) clearTimeout(graphFilterTimer);
      graphFilterTimer = setTimeout(() => loadGraphBrowse(state.graphView), 300);
    });
  }
  if (els.graphType) {
    els.graphType.addEventListener("change", () => {
      if (state.graphView === "nodes") loadGraphBrowse(state.graphView);
    });
  }

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
    launchJob("backlog-sync", t("btn_backlog_sync"));
  });

  // Radar actions
  els.btnRadarHarvest.addEventListener("click", () => {
    launchJob("radar-harvest", t("btn_radar_harvest"));
  });
  els.btnRadarCitationGap.addEventListener("click", () => {
    launchJob("radar-citation-gap", t("btn_radar_citation_gap"));
  });

  // Operations & danger buttons are rendered by renderOpsPanels() from the
  // server's ops catalog — only the modal chrome is wired here.
  els.dangerModalCancel.addEventListener("click", () => {
    els.dangerModal.classList.remove("open");
    pendingDangerOp = null;
  });

  els.dangerModalConfirm.addEventListener("click", () => {
    if (pendingDangerOp) {
      const input = document.getElementById("danger-confirm-input");
      const typed = input ? input.value.trim() : "";
      if (typed !== pendingDangerOp.op) {
        showToast(t("danger_confirm_mismatch", { op: pendingDangerOp.op }), "error");
        return;
      }
      launchJob(pendingDangerOp.op, t(pendingDangerOp.label_i18n), pendingDangerOp.op);
    }
    els.dangerModal.classList.remove("open");
    pendingDangerOp = null;
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
  loadInitialStatus();
  loadOpsCatalog();
  initBackgrounds();
  applyGlassSettings();

  // Deep-link override: ?tab=melchior|operations|...
  try {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && document.getElementById(`tab-${urlTab}`)) {
      switchTab(urlTab);
    }
  } catch (_) {}
})();
