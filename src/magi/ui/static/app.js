// MAGI WebUI Dashboard Frontend Controller & i18n Engine

(function () {
  "use strict";

  // ------------------------------------------------------------------------
  // I18N Translation Dictionary
  // ------------------------------------------------------------------------

  const I18N = {
    zh: {
      // Page & Brand
      page_title: "MAGI — 科研项目控制台",

      // Topbar
      workspace_label: "查看项目:",
      loading_workspaces: "加载项目中...",
      browsing_badge: "浏览中",
      browsing_badge_title: "面板正在浏览另一个项目（会话级选择，服务器启动位置不变）",
      term_retention_note: "任务历史跨重启保留（最近 40 条，magi 配置目录下 ui-jobs.jsonl）。",
      sync_label: "三核同步:",
      running_jobs_label: "运行中任务:",
      core_sync_note: "这是就绪度,不是「你有多少知识」的分数。新项目起步就低,把上面三核里标红标黄的项清掉它就涨。",
      sync_ratio_tooltip: "项目就绪度：知识（图谱是否最新、待编译源、断言覆盖）、任务追踪、检索索引三块的加权平均。把上方三核里标红/标黄的项处理掉，这个数就会涨。",
      doctor_btn: "环境体检",
      doctor_btn_title: "环境依赖与规范体检",
      theme_btn_title: "切换深浅配色主题",
      magi_mode_btn: "MAGI 模式",
      magi_mode_btn_title: "开启/关闭 EVA NERV MAGI 战术主题",

      // Navigation Tabs
      tab_dashboard: "项目总览",
      tab_melchior: "Melchior (认知状态)",
      tab_balthasar: "Balthasar (任务追踪)",
      tab_casper: "Casper (文献检索)",
      tab_radar: "文献雷达",
      tab_operations: "运维与操作",
      tab_docs: "文档与指引",

      // v2: the map, the dump box, threads, the feed
      dump_title: "想到什么就写在这",
      dump_subtitle: "不用管格式，也不用想它属于哪条线——在想到的那一刻决定归属，正是这个框要省掉的成本。分类是 agent 的活。",
      dump_ph: "无序那条路大概是死胡同",
      dump_btn: "扔进堆放区",
      dump_saved: "记下了（还有 {n} 条没分类）",
      queue_title: "等你拍板的决定",
      queue_subtitle: "只有这几类事允许打断你",
      queue_none: "没有。每个开着的问题都轮到别人了。",
      proposal_accept: "采纳",
      proposal_reject: "否掉",
      proposal_promote: "变成代码",
      proposal_retire: "退掉这条规则",
      proposal_done: "已{verb}",
      lines_title: "研究线",
      lines_subtitle: "相位、线上开着几条、上次动是什么时候",
      lines_none: "还没有线。",
      map_loading: "正在读 threads/…",
      flag_over_wip: "超 WIP",
      flag_quiet: "安静",
      back_title: "回头看",
      back_right: "条预测猜对",
      back_bet_line: "你赌 {bet}，结果是 {outcome}",
      back_unknown: "条记为「不知道」",
      back_unknown_only: "条预测记为「不知道」——诚实的先验，不计分。",
      back_late: "条 bet 是答案出来之后才补的——不计分，那不算预测。",
      back_decisions: "最近的决定：",
      threads_title: "Threads",
      threads_subtitle: "命题、问题、线——正文归开它的人，讨论区只追加",
      threads_none: "还没有 note。",
      filter_all_kinds: "全部种类",
      filter_all_statuses: "全部状态",
      th_thread: "note",
      th_kind: "种类",
      th_status: "状态",
      th_line: "线",
      th_tier: "温层",
      th_phase: "相位",
      th_open: "开着",
      th_last_move: "上次动",
      th_flags: "标记",
      thread_say_ph: "发生了什么，用你自己的话",
      btn_post: "发帖",
      btn_close: "收起",
      need_words: "先写点什么——空帖子记不下任何事",
      need_reason: "改状态要写理由：翻状态和说明为什么是一件事，不是两件",
      moves_need_reason_first: "先在上面写一句为什么,这些才能按——翻状态和说明理由是一件事。",
      need_workspace: "先在顶栏选一个项目——不然这行字会写进服务器启动的那个目录",
      badge_kb_gone: "目录不在了",
      btn_review: "找人复核这条",
      btn_cancel: "算了",
      btn_save_draft: "存成草稿",
      draft_title_ph: "这篇写的是什么",
      draft_body_ph: "把正文粘进来——存进 drafts/,然后就能发表了",
      draft_needs_both: "标题和正文都要有",
      draft_saved: "草稿存好了",
      btn_publish_preview: "看看会埋掉什么",
      close_why_ph: "为什么结束这条线（会记进结案帖）",
      review_only_when_supported: "这条还没有声称被解决,所以还没到找人复核的时候。等它走到 supported 再说。",
      line_set: "所属的线改好了",
      line_needs_reason: "先在上面那栏写一句为什么它属于这条线",
      btn_thread_new: "开一条新的",
      btn_decide: "记下这是我的决定",
      decide_needs_words: "先在上面写下你的原话——decisions.md 记的是你说的,不是摘要",
      decided: "已写进 decisions.md",
      bet_none: "不带预测",
      bet_supported: "我赌它成立",
      bet_refuted: "我赌它不成立",
      bet_unknown: "不知道(合法,也会记下来)",
      btn_open_it: "开",
      kind_proposition: "命题（一个可以被证伪的说法）",
      kind_question: "问题（还不知道答案）",
      kind_line: "研究线（一组相关的命题）",
      new_title_ph: "标题——它到底主张什么",
      new_purpose_ph: "为什么现在值得开这一条",
      new_line_ph: "属于哪条线（可留空）",
      new_hint: "标题会变成它的永久 id。命题是能被证伪的说法;问题是还不知道答案;线是一组相关命题的视图。",
      new_needs_both: "标题和「为什么现在」都要填",
      new_opened: "{slug} 开好了",
      line_field_ph: "属于哪些线,逗号分隔",
      btn_set_line: "改所属的线",
      btn_close_line: "结束这条线",
      btn_publish: "发表并归档",
      close_would_silence: "关掉之后这 {n} 条会永远没人再提起：",
      close_nothing_open: "这条线上没有还开着的东西。",
      close_why_prompt: "结束 {line}——为什么？（这句会记进结案帖）",
      closed_line: "{line} 已结束",
      publish_no_papers: "drafts/ 和 output/ 里没有 .md,先把稿子放进去。",
      publish_which: "发表哪一篇？",
      publish_would_bury: "这 {n} 条会被标成「已被论文取代」：",
      publish_why: "这篇论文报告的是什么？（这句会记进归档帖）",
      publish_loose_ends: "还有没收尾的：{slugs}。仍要发表就说明为什么——这句会写进记录。",
      published: "已归档,相关工作已退役",
      btn_review_running: "正在问…",
      review_hint: "让另一个厂商的 CLI 读这条命题——它没有你这段对话的上下文。要花一次周预算。",
      review_confirm: "要问 {host}（模型 {model}）复核这条命题吗？\n\n这会花掉本周预算的一次:还剩 {left}/{limit}。\n一般十几秒。",
      review_running: "已经在问 {host} 了,通常十几秒。",
      review_switched_off: "MAGI 自己的模型调用被关掉了(research.llm_calls)。开了才能复核。",
      review_by: "{host} 判的（{model}）",
      review_unclear: "「说不清」既不是通过也不是否决——复核方说它按现有证据判不了。命题还在待复核队列里。",
      review_budget_left: "本周还剩 {left}/{limit} 次调用。",
      dash_spending: "本周 MAGI 自己发起的调用",
      dash_spending_line: "{spent}/{limit} 次,还剩 {left}",
      kb_hide_gone: "隐藏目录已不存在的 ({n})",
      cfg_review_host_auto: "自动（探测 PATH，选一个不是作者的）",
      cfg_f_review_host: "复核跑在哪个 CLI 上。留空 = 自动挑一个不是作者的——跨厂商是「独立」最便宜的近似。",
      cfg_f_coaching: "结束会话时这道门推得多紧。off = 不拦；light = 缺记账就提醒；strict = 没写下预测就不许开始推导。",
      cfg_f_wip_limit: "一条线上同时开着几个命题算多。七是工作记忆的数字,不是测量值:再多人就抓不住这条线上到底有什么没结。",
      cfg_f_stall_days: "多少天没动静就把一条线标成安静。久到休一周不算,短到被忘掉的线一个月内会浮上来。",
      cfg_f_weekly_calls: "MAGI 自己每周能发起多少次模型调用(复核、慢环、堆放区分类)。数的是次数不是钱——无头 CLI 不告诉我们一次要多少。失败的也算:超时同样花了墙钟时间。用完就拒绝启动,不会偷偷少做。",
      cfg_f_llm_calls: "MAGI 自己那些调用的总开关。关掉之后它一次也不发起,而不是安静地少做几次。你自己让 agent 干的活不受这个影响。",
      cfg_f_rule_budget: "AGENTS.md 里规则那一节最多几行。每次会话、每个宿主都要读这一段,所以一条规则进去,后面每一次会话都在为读它付钱。",
      cfg_f_rules: "这个项目自己挣来的规则,用一套封闭词汇写成,每次运行都真的被检查。`magi reflect promote` 往里加,这里可以退役。",
      cfg_f_search_projects: "这个项目的搜索还会读哪几个已注册的项目。留空 = 只搜本项目。注册表里的「可搜索」勾是全机的,说的是某个库允不允许被别处读到;这里说的是本项目实际读哪几个。",
      cfg_f_hosts: "内建那几个之外,这个项目还认识哪些 agent CLI。世界上的 CLI 太多了,所以宿主是一条记录:二进制名、skill 装到哪、怎么无头调用。",
      cfg_f_review_model: "复核用哪个模型。留空 = 那个宿主的便宜档。",
      cfg_f_review_effort: "推理档位。留空 = 那个宿主自己的默认；模型 id 往往已经带了档位。",
      cfg_model_cheap: "便宜档（{id}）",
      cfg_model_default: "那个宿主自己的默认",
      cfg_model_pin_host: "先钉住 review_host 才能挑模型——模型名各家不通用",
      cfg_model_typed: "这个宿主不列出模型，自己填",
      cfg_model_stale: "列表来自缓存（最多一天前）",
      cfg_effort_default: "那个宿主自己的默认",
      moves_human_only: "带 * 的只有人能做",
      feed_title: "时间线",
      feed_subtitle: "所有跟帖，最新在前——它是 note 的一个视图，不是第二份日志",
      feed_none: "这段时间没有跟帖。",
      feed_window_24: "最近 24 小时",
      feed_window_72: "最近 3 天",
      feed_window_168: "最近 7 天",
      feed_window_0: "全部",

      // Dashboard Metrics
      dash_sync_label: "三核同步率",
      dash_sync_subtitle: "认知 + 任务 + 检索协同",
      dash_kb_label: "项目",
      dash_kb_subtitle: "本机可检索的项目；当前正在看的那个见顶栏",
      dash_radar_label: "待分流文献",
      dash_radar_subtitle: "文献雷达 · 仅本项目",
      dash_task_label: "可开始的任务",
      dash_task_subtitle: "没有被依赖挡住的任务 · 统计范围是所属 Hub，非单个项目",

      // Three-core status band
      core_role_mel: "认知状态",
      core_role_bal: "任务追踪",
      core_role_cas: "文献检索",
      core_sync_label: "三核同步率",
      core_state_ok: "正常",
      graph_legend_concept: "概念",
      graph_legend_reference: "文献",
      graph_legend_topic: "专题",
      graph_legend_thesis: "论点",
      graph_legend_claim: "断言",
      graph_legend_proposition: "命题",
      graph_legend_question: "问题",
      graph_legend_line: "研究线",
      graph_legend_ghost: "断链（指向不存在的卡片）",
      graph_legend_tag: "标签",
      graph_legend_other: "未分类（{kinds}）",
      graph_legend_size: "点越大 = 连接越多",
      graph_needs_build: "这个项目还没建知识图谱。建完之后才能浏览概念之间的连接。",
      running_jobs_tooltip: "正在运行的后台任务（本机全部项目）——点击查看实时日志。",
      claims_none_yet: "还没有断言",
      btn_hint_howto: "怎么做",
      kb_table_sub: "本机上 magi 知道的所有项目；切换后所有面板都会指向它。",
      core_state_notset: "尚未设置",
      core_state_attention: "待处理",
      core_state_fault: "故障",
      core_state_offline: "未接入",
      core_detail_nolink: "尚未选择项目",
      core_detail_mel: "{c} 概念 · {r} 文献 · 命题 {v}/{n} 已核验",
      core_detail_bal: "就绪 {r} · 进行中 {p} · 阻塞 {b}",
      core_detail_bal_kbonly: "纯项目模式，未启用任务追踪",
      core_detail_bal_noengine: "未安装 beads，请运行 magi setup",
      core_detail_bal_uninit: "任务库尚未初始化",
      core_detail_cas: "{c} 条内容索引 · {v} 条语义索引",
      core_detail_cas_noindex: "尚未建立检索索引",

      // Dashboard KB Table
      dash_kb_table_title: "已注册项目",
      dash_kb_table_subtitle: "本机上 magi 知道的所有项目；切换之后所有面板都指向它。",
      btn_refresh: "刷新",
      th_kb_name: "项目名称",
      th_path: "路径",
      th_searchable: "联合检索",
      th_indexed: "检索索引",
      th_graph: "关系图谱",
      th_sync_ratio: "同步率",
      th_actions: "操作",
      loading_kbs: "正在加载项目列表...",
      no_kbs_registered: "当前尚未注册任何项目。",
      badge_current: "当前",
      badge_indexed: "已索引",
      badge_no_index: "无索引",
      badge_graph_built: "已构建",
      badge_graph_missing: "未构建",
      btn_switch_ws: "切换",
      btn_unreg_kb: "移除",
      unreg_confirm: "确定要注销项目 '{name}' 吗？（不会删除物理文件）",

      // Register Form
      reg_kb_title: "注册新项目",
      reg_kb_subtitle: "将项目目录加入全局注册表",
      reg_kb_path_ph: "绝对或相对目录路径...",
      reg_kb_name_ph: "自定义名称（可选）...",
      reg_kb_enable_label: "启用联合检索",
      btn_reg_kb: "注册项目",

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
      bal_no_db_initialized: "本项目（或所属 Hub）还没有任务追踪库。这一步是可选的——不想用任务追踪就不必初始化。",
      bal_backlog_sync_desc: "扫描 raw/ 里还没编译成参考卡片的原始文献，为每一篇建一条任务",
      bal_store_at: "任务库文件位于 {root}（该 Hub 下各课题共用一份；下面的数字只算当前项目）。",
      bal_store_shared: "任务库位于 Hub：{root} —— 下面这四个数字属于该 Hub 下的全部课题，不只是当前项目。",
      bal_store_local: "任务库位于本项目：{root}",
      scope_badge_hub: "Hub 级",
      bal_init_writes_hub: "在 Hub 根目录建库，该 Hub 下所有课题共用",
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
      searching_text: "正在检索中...",
      search_no_results: "未找到匹配的段落内容。",
      search_summary: "找到 {total} 条结果 · 关键词命中 {bm25} · 语义检索{vec}",
      search_lines: "行 {start}-{end}",
      vec_avail_yes: "已启用",
      close_strong: "高度契合",
      close_related: "相关",
      close_weak: "较远",
      badge_close_tip: "语义距离 {d}（越小越接近）。这只是提示，不会因此丢结果。",
      search_scope_searched: "检索范围：{names}",
      search_scope_skipped_here: "当前项目「{name}」未被检索：它还没有建索引，下面没有一条结果来自这里。",
      search_scope_skipped: "已跳过：{names}",
      search_scope_this_one: "当前项目",
      search_all_weak: "这次查询没有语义上贴近的内容——下面的结果都只是相对最接近的，未必真的相关。换个说法或用项目里的术语再试试。",
      badge_rrf_tip: "综合排名分：把关键词排名和语义排名融合后的结果，越大越靠前。",
      badge_bm25_tip: "按关键词匹配，这条排第 {n}",
      badge_vec_tip: "按语义相近，这条排第 {n}",
      vec_avail_bychoice: "本次未使用（你选了纯关键词）",
      vec_avail_no: "未启用",

      // Literature Radar
      radar_seen_label: "已跟踪文献记录",
      radar_waiting_label: "待分流文献",
      radar_last_label: "上次扫描",
      radar_never: "从未",
      radar_today: "今天",
      radar_days_ago: "{days} 天前",
      radar_seen_sub_n: "累计已跟踪 {n} 篇",
      radar_pending_sub_n: "分布在 {files} 份简报中",
      radar_pending_sub_clear: "没有待审阅的简报",
      radar_hide_decided: "隐藏已处理",
      radar_triage_progress: "已处理 {done} / {total}",
      radar_rel_top: "高相关",
      radar_rel_mid: "中等",
      radar_rel_low: "偏低",
      radar_rel_tooltip: "与本项目中心向量的余弦相似度 {score}（同批候选内的相对排名）",
      radar_settings_title: "雷达设置",
      btn_radar_settings: "设置…",
      btn_dismiss: "跳过",
      tip_dismiss: "只记一条「不感兴趣」的决定，不动任何文件。可用 Undo 撤销。",
      tip_accept_inbox: "把这篇加进本项目的摄入队列。此刻不下载任何东西——跑一次队列才会抓取和转换，进库前仍要你审批。",
      tip_create_issue: "在 Hub 的任务库里建一条 survey 任务（该 Hub 下所有项目共用）。不下载、也不写 inbox/。",
      tip_create_issue_no_store: "本项目所属 Hub 还没有任务库——先到 Balthasar 标签页初始化。",
      btn_undo: "撤销",
      digest_source_title: "查看原始简报（{file}）",
      btn_radar_schedule: "定时扫描…",
      radar_schedule_on: "每日 {time} 自动扫描",
      radar_schedule_off: "未设置定时扫描",
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
      op_rebuild_index: "让搜索找得到新内容",
      tab_ingest: "摄入队列",
      loading: "加载中…",
      ingest_waiting_label: "队列中等待",
      ingest_waiting_sub: "已排队，尚未抓取",
      ingest_undecided_label: "等你审批",
      ingest_undecided_sub: "已转换，但还没进库",
      btn_ingest_run: "跑队列",
      btn_ingest_commit: "提交已批准的",
      btn_ingest_upload: "上传",
      zotero_label: "或者,从 Zotero 导入",
      zotero_loading: "正在读取你的 Zotero 库……",
      zotero_pick: "选一个分类",
      zotero_whole_library: "整个库",
      zotero_tag_ph: "标签(可选)",
      zotero_hint: "选中一个分类会连同它下面的所有子分类一起。入队不抓取任何东西——下面的队列负责转换,你负责审批。",
      zotero_pick_something: "先选一个分类,或者填一个标签。",
      zotero_working: "正在读取并入队……",
      zotero_queued: "已入队 {n} 篇（{already} 篇本来就在队列里,{skipped} 篇没有可抓取的标识符）",
      btn_zotero_import: "加入队列",
      ingest_upload_label: "或者,从这台电脑上传一个文件",
      ingest_upload_hint: "先落进 inbox/,再汇入下面的队列——和其他来源走同一道审批。",
      ingest_upload_working: "正在上传 {name}……",
      ingest_upload_queued: "{name} 已上传并入队,跑一次队列就会转换。",
      ingest_upload_text_done: "{name} 已放进 inbox/。它已经是文本,不用转换——下次 magi ingest auto 会把它归档。",
      btn_ingest_add: "排队",
      ingest_add_label: "按链接 / DOI / arXiv 号加一篇",
      ingest_add_hint: "排队不会抓任何东西。跑完队列，再审批转出来的结果。",
      ingest_batches_title: "批次",
      ingest_hide_decided: "隐藏已决定的",
      ingest_empty: "队列里还没有东西。",
      ingest_no_workspace: "先在上方选一个项目，才能看它的摄入队列。",
      ingest_scope: "本项目：{name}",
      ops_badge_global: "全机生效",
      feature_off_quiet: "这个功能已关闭。",
      cfg_get_one: "去哪儿拿 ↗",
      cfg_secret_set: "已保存（不回显；填新的可覆盖）",
      cfg_secret_unset: "尚未设置",
      cfg_secret_empty: "空的不保存——留空不会清除已存的 key。",
      cfg_provider_ollama: "Ollama（本机）",
      cfg_provider_openai: "云端（OpenAI 兼容接口）",
      cfg_f_s2_api_key: "Semantic Scholar 的 key(免费,可不填)。不带 key 是和所有人共享一个匿名配额。环境变量 SEMANTIC_SCHOLAR_API_KEY 优先",
      cfg_f_mineru_token: "MinerU 的 API token，云端 PDF 转换要用",
      cfg_f_embedding_provider: "向量从哪儿来：本机 Ollama，还是任何 OpenAI 兼容的云端接口",
      cfg_f_embedding_base_url: "云端接口地址，要带 /v1（例：https://api.siliconflow.com/v1）",
      cfg_f_embedding_model: "云端的模型名（例：BAAI/bge-m3）。留空则沿用 models.embedding",
      cfg_f_embedding_api_key: "云端接口的 key。也可以放进环境变量 MAGI_EMBEDDING_API_KEY——环境变量优先",
      embed_help_open: "不想装 Ollama？",
      embed_help_title: "不装 Ollama 也能做语义检索",
      embed_help_body: "语义检索需要一个「嵌入模型」把文字变成向量。默认走本机 Ollama，但任何**OpenAI 兼容**的 `/v1/embeddings` 接口都可以，改 `embedding.provider` 为 `openai` 即可。\n\n下面几家都实测过接口形状，也都有免费额度或极低价格。具体额度以各家页面为准——它们变得很勤。\n\n| 服务 | base_url | 模型 | 备注 |\n|---|---|---|---|\n| 硅基流动 SiliconFlow | `https://api.siliconflow.com/v1` | `BAAI/bge-m3`、`Qwen/Qwen3-Embedding-0.6B` | 中英都强，有免费模型；注册可能需要国内手机号 |\n| Jina AI | `https://api.jina.ai/v1` | `jina-embeddings-v3` | 接口就是照 OpenAI 抄的，多语言，注册送额度 |\n| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-embedding-001` | 用 Google 账号，免费额度在 AI Studio 里看 |\n| DeepInfra | `https://api.deepinfra.com/v1/openai` | `BAAI/bge-m3` | 没有免费额度，但每百万 token 只要几分钱 |\n\n**Cohere、Voyage、智谱**的接口不是 OpenAI 形状，现在还接不了。\n\n> 换模型会改变向量维度，旧索引装不下。换完要跑 `magi index --rebuild`。",
      cfg_f_ocr_mineru_token: "MinerU token",
      tasks_title: "任务清单",
      tasks_loading: "正在读取任务…",
      tasks_show_hub: "显示该 Hub 下所有项目的任务",
      tasks_show_closed: "包含已关闭",
      tasks_no_store: "还没有任务库。",
      tasks_all_here: "{here} 条任务，全部属于「{name}」。",
      tasks_split: "「{name}」有 {here} 条；同一个任务库里另有 {elsewhere} 条属于 {root} 下的其它项目。",
      tasks_none: "没有待办任务。",
      tasks_none_here: "这个项目没有任务。勾上上面那个可以看其它项目的。",
      task_status_open: "待办",
      task_status_in_progress: "进行中",
      task_status_blocked: "被阻塞",
      task_status_closed: "已关闭",
      task_blocked_by: "被 {n} 条挡住",
      task_blocks: "挡住 {n} 条",
      task_start: "开始",
      task_start_tip: "认领这条任务并标为进行中。",
      task_close: "关闭",
      task_close_tip: "标记完成。可以再打开，不会删除。",
      task_reopen: "重新打开",
      task_reopen_tip: "把这条已关闭的任务放回待办。",
      task_done_start: "已开始 {id}。",
      task_done_close: "已关闭 {id}。",
      task_done_reopen: "已重新打开 {id}。",
      scope_help_open: "这三个词是什么关系？",
      scope_help_title: "项目、注册表——到底是什么关系",
      scope_help_body: "一个**项目**就是一个研究方向的目录，里面有 wiki/、raw/、output/，用 `magi init` 建。这个面板上说的「项目」「库」「工作区」都是它，只是以前有好几个叫法。\n\n**注册表**（`~/.config/magi/registry.json`）记着这台机器上都有哪些项目。注册进去有两个用处：顶栏的下拉框能切到它，以及别的项目可以搜到它——后者还要那个项目自己在 `research.search_projects` 里点名，默认谁也不读谁。\n\n注销一个项目只是把它从这张表里拿掉，目录和文件一个字不动。",
      opt_title: "可选组件",
      opt_sub: "这一整块都是全机生效的，缺哪个 MAGI 都能跑，只是少一项能力。不想要的取消勾选，它就不再被提起。",
      opt_unknown: "读不到组件状态。",
      feature_label_radar: "文献雷达",
      feature_label_tasks: "任务追踪",
      opt_unlocks_ollama: "语义（向量）检索，以及本地离线 PDF OCR",
      opt_unlocks_pandoc: "LaTeX 与 arXiv-HTML 摄入路线——保真度最高的入库方式",
      opt_unlocks_poppler: "本地 OCR 的页面渲染（要和 Ollama 一起用）",
      opt_unlocks_latex: "深度数学校验——真去编译一遍公式看它成不成立",
      opt_unlocks_mineru: "云端 PDF 转换，公式和版面都很强",
      opt_hint_ollama: "装好之后，magi setup 会帮你把嵌入模型拉下来",
      opt_hint_poppler: "Windows 构建：https://github.com/oschwartz10612/poppler-windows/releases",
      opt_hint_mineru: "注册后把 token 填进 config.yaml 的 ocr.mineru_api_token",
      feature_what_radar: "会盯着 arXiv 和 Semantic Scholar 找你这个方向的新论文，排好队等你分诊",
      feature_what_tasks: "把你的待读、待编译变成一张带依赖关系的任务图",
      opt_unlocks: "解锁：{unlocks}",
      opt_present: "已安装",
      opt_absent: "未安装",
      opt_service: "在线服务",
      opt_want_tip: "勾上表示你想要 {name}；取消勾选后体检表不再把它列成待办。这不会安装或卸载任何东西。",
      opt_wanted_toast: "已记下：你想要 {name}。",
      opt_declined_toast: "已记下：不需要 {name}，之后不再提。",
      metric_feature_off: "已关闭",
      feature_off_title: "「{name}」已关闭",
      feature_off_body: "打开之后：{what}。关着的时候这一页不会有任何动作，已有数据也不会被删。",
      feature_turn_on: "打开{name}",
      feature_turn_on_plain: "只改一个全机开关，不装任何东西，也不动项目里的文件。",
      feature_turn_on_installs: "打开开关，并安装它依赖的 {needs}（联网，约一分钟）。",
      feature_will_install: "需要 {needs}——MAGI 会自己装，不用你操心。",
      feature_on_toast: "「{name}」已打开。",
      tool_open_site: "打开 {name} 官网 ↗",
      tool_recheck: "我装好了，重新检测",
      tool_recheck_tip: "重新在这台机器上找 {name}。MAGI 装不了它——它是另一个项目的安装器。",
      tool_found: "找到 {name} 了。",
      tool_still_missing: "还是没找到 {name}。装完可能要开一个新终端，或者重启 MAGI 服务。",
      op_install_tasks: "安装任务库",
      op_pull_models: "拉取 Ollama 模型",
      op_desc_install_tasks: "打开任务追踪，并安装它用的 bd 任务库",
      op_desc_pull_models: "拉取 MAGI 用到的 Ollama 模型（需要先装好 Ollama）",
      btn_install_tasks: "安装任务库",
      btn_pull_models: "拉取 Ollama 模型",
      ingest_run_caption: "把队列里的全部抓下来、转换、跑校验 · 此步不会写入项目",
      ingest_commit_caption: "把已批准的条目移入 raw/,刷新目录表和图谱 · 编译成参考卡片、以及让搜索找得到,是之后各自独立的一步",
      doctor_scope: "工具与路径是全机的；「本项目」相关的几行说的是：{name}",
      metric_not_applicable: "未建库",
      hint_dest_tab: "点击跳转到「{name}」标签页 · 不执行任何命令",
      hint_dest_docs: "点击跳转到「{name}」中对应的章节 · 不执行任何命令",
      op_desc_index: "重建搜索索引 · 要向量化,全量几分钟(没有 Ollama 则退化为关键词)",
      op_desc_graph_build: "重扫 wikilink 和标签 · 很快,不用模型",
      op_desc_wiki_reindex: "重新生成各 wiki 目录的 _index.md 清单 · 秒级",
      op_desc_link: "用向量相似度给概念卡片之间建语义双链（需要 Ollama）",
      op_desc_lint_fix: "就地修复死链和 frontmatter 问题",
      op_desc_stats: "统计本项目的卡片数、链接密度和缺口",
      op_desc_close: "列出做了但没写下来的事，判定被两个人同时翻过的状态，并重画 MAP.md",
      op_desc_install: "把 skills、AGENTS.md 协议块和收工闸门装进检测到的 agent CLI（可重复运行）",
      op_desc_backlog_sync: "为 raw/ 里每一篇还没编译成参考卡片的原始文献建一条任务",
      op_desc_radar_harvest: "从 arXiv 和 Semantic Scholar 抓新的候选论文",
      radar_harvest_caption: "联网从 arXiv 和 Semantic Scholar 拉新候选，写入本项目 inbox/radar/ · 耗时数分钟",
      radar_gap_caption: "引用缺口：找那些理应引用你却没引的新论文 · 设置：改雷达盯的关键词和作者",
      radar_settings_tip: "编辑本项目 config.yaml 里的 radar 配置",
      op_desc_radar_citation_gap: "侦察那些理应引用你却没引的新论文",
      op_desc_ingest_batch_run: "抓取并转换队列里的所有条目——转完等你审批，不会进库",
      op_desc_ingest_batch_commit: "把已批准的文档移进 raw/；只要还有没决定的就拒绝执行",
      ingest_preview: "看看转出来的内容",
      ingest_cannot_approve: "这条转换失败了，没有产物可批准——拒绝它，会自动改走下一档路线。",
      ingest_approve: "通过",
      ingest_reject: "拒绝",
      ingest_undo: "撤销",
      ingest_badge_undecided: "{n} 条待决定",
      ingest_badge_ready: "可提交",
      ingest_requeued: "已拒绝，自动改走下一档：{route}（会出现在下一批）",
      ingest_queued: "已排队（识别为 {kind}）：{value}",
      op_ingest_batch_run: "跑摄入队列",
      op_ingest_auto: "收下 inbox/ 里的文件",
      op_desc_ingest_auto: "把 inbox/ 里散着的文件各自送去合适的摄入路线并归档。",
      inbox_title: "inbox/ 里还躺着 {n} 个文件",
      inbox_sub: "面板上那句「把 PDF 丢进 inbox/」说的就是这里。它们还没有进队列——队列只装从上面几个框加进来的东西。",
      inbox_pickup: "收下这些",
      op_ingest_batch_commit: "提交已审批批次",
      op_build_graph: "重建概念图谱",
      op_reindex_wiki: "刷新目录清单",
      op_semantic_link: "语义概念链接",
      op_lint_fix: "规范检查与修复",
      op_backlog_sync: "待办文献转任务",
      op_index: "重建检索索引",
      op_graph_build: "构建知识图谱",
      op_wiki_reindex: "重建维基索引",
      op_link: "语义概念链接",
      danger_title: "危险操作区",
      danger_sub: "这些操作将修改项目结构、重置状态或清理历史文件。每项操作均需二次确认。",
      btn_danger_setup: "环境一键配置",
      btn_danger_migrate: "项目结构迁移",
      btn_danger_pm_init: "初始化任务工作流",
      btn_danger_legacy: "清理旧版历史文件",

      // Danger Actions Meta & Modals
      danger_modal_title: "确认操作",
      danger_modal_default_desc: "确定要继续执行此操作吗？",
      danger_setup_title: "环境一键配置",
      danger_setup_desc: "为当前环境重新配置：任务引擎、Ollama 模型，检测已装的 agent CLI（Claude Code / Codex / Antigravity / opencode），并注册 Claude Code 插件（这一步只有 Claude Code 有对应机制）。",
      danger_migrate_title: "项目结构迁移",
      danger_migrate_desc: "将旧版项目布局迁移至 MAGI 标准规范。",
      danger_pm_init_title: "初始化任务工作流",
      danger_pm_init_desc: "在 Hub 目录初始化科研任务追踪数据库。",
      danger_remove_legacy_title: "清理旧版历史文件",
      danger_remove_legacy_desc: "永久删除 ~/.claude/skills 与 ~/.gemini/skills 里的旧版 Wikify 脚本。只有这两个目录，因为旧版 Wikify 早于 Codex / Antigravity / opencode 支持——不是偏袒某一家。",
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
      doc_guide: "使用指南",
      docs_toc_title: "章节",
      copy_code: "复制",
      copied: "已复制",
      copy_failed: "复制失败",
      cal_expect: "预期效果",
      cal_fix: "不达预期怎么办",
      cal_warn: "注意",
      cal_note: "说明",
      cal_tip: "提示",
      bg_pick_label: "背景",
      bg_shuffle: "换一张",
      bg_shuffle_title: "在当前可选范围内换一张",
      bg_pick_auto: "未选 — 按窗口比例自动轮换",
      bg_pick_one: "已固定这一张",
      bg_pick_many: "只在选中的 {n} 张里轮换",
      bg_pick_none: "这个模式没有可用图片。把图片放进 ~/.config/magi/ui-backgrounds/ 即可自定义。",
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
      badge_optional: "可选",
      badge_declined: "已跳过",
      doctor_all_good: "没有任何问题。{count} 个可选组件未安装 —— MAGI 不装它们也能用。",
      doctor_get_it: "下载",
      doctor_legacy_found: "检测到旧版冲突文件 ({count}):",
      doctor_legacy_hint: "您可在「运维与操作」>「危险操作区」>「清理旧版历史文件」中安全清理。",
      doctor_clean: "✓ 未检测到旧版冲突文件，环境处于良好状态。",
      btn_doc_close: "关闭",

      // Toasts & Alerts
      toast_select_ws_first: "请先选择一个有效的项目。",
      toast_job_started: "已启动后台任务: {name}",
      toast_job_success: "任务 '{name}' 执行成功。",
      toast_job_ended: "任务 '{name}' 已结束 ({status})。",
      toast_job_cancel_req: "已请求中止任务。",
      toast_job_fail: "启动任务失败: {error}",
      toast_kb_registered: "项目注册成功。",
      toast_kb_status_updated: "项目 '{name}' 检索状态已更新。",
      toast_ws_switched: "已切换当前项目。",
      toast_kb_unregistered: "已注销项目 '{name}'。",

      // Sync Hints (actionable)
      hints_title: "建议操作",
      hints_subtitle: "同步报告给出的下一步建议——点按钮直接执行",
      hint_graph_build: "知识图谱落后于卡片内容，需要重建",
      hint_index: "检索索引缺失或已过期，需要重建",
      hint_backlog_sync: "有未编译文献尚未纳入任务追踪",
      hint_pm_init: "还没有任务追踪库（可选，不用任务追踪就可以忽略）",
      hint_radar_review: "{pending} 份文献雷达简报等待审阅",
      hint_radar_gaps: "{pending} 份引用缺口报告等待审阅",
      hint_radar_overdue: "文献雷达上次收割是 {days} 天前（窗口 {window} 天）——跑一次,或检查定时任务",
      hint_compile_pending: "{backlog} 篇原始文献还没编译成参考卡片",
      hint_claims_unverified: "有学术命题尚未验证（到 Melchior 面板查看）",
      hint_bd_ready: "有可直接开工的任务（到 Balthasar 面板查看）",
      hint_install_beads: "任务引擎 (beads) 未安装——见安装指引",
      hint_ingest_start: "把论文 PDF / 源文件放进 inbox/，用 ingest 技能开始建库",
      btn_hint_run: "执行",
      btn_hint_goto: "前往",

      // Search guidance
      vec_unavailable_hint: "语义检索未启用：需要本机 Ollama 语义模型，且在运行 magi index 建立索引时可用。当前仅按关键词匹配。",
      vec_degraded_hint: "语义检索暂时降级：Ollama 正忙（通常是索引任务在占用），本次只按关键词匹配。等任务结束后重搜即可。",
      search_no_results_hint: "建议：改用 2-3 个关键词（而非整句）、切换检索模式，或确认当前项目已运行过「重建检索索引」。",

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
      mel_drafts_subtitle: "drafts/ 下的草稿——进检索、不进图谱（draft skill）",
      drafts_none: "还没有草稿——用 draft skill 开始写作流程。",

      // Workspace config
      cfg_title: "项目配置",
      cfg_subtitle: "config.yaml 的科研旋钮——修改只动对应行，注释与其余内容原样保留",
      cfg_loading: "正在加载配置...",
      btn_cfg_save: "保存",
      toast_cfg_saved: "已写入 {key}",
      cfg_list_hint: "多个值用逗号分隔",
      cfg_f_radar_min_relevance: "雷达相关度阈值（低于此分的候选被丢弃；留空 = 不过滤）",
      cfg_f_radar_days: "雷达回溯天数（只影响 arXiv 那条腿；Semantic Scholar 的推荐固定只覆盖最近 60 天）",
      cfg_f_radar_max_candidates: "每次收割的候选上限",
      cfg_f_radar_arxiv_categories: "arXiv 分类（如 cond-mat.str-el）",
      cfg_f_radar_seed_arxiv_ids: "口味样本 arXiv ID（可留空 —— 文库里参考卡片上的会自动并入）",
      cfg_f_radar_own_arxiv_ids: "我方论文 arXiv ID（留空会退回用上面那组,可能把别人的论文当成你的）",
      cfg_f_ocr_use_mineru: "使用 MinerU 云端 OCR（需在 config 中配 token）",
      cfg_f_models_embedding: "语义模型（Ollama 模型名）",

      // Search filters
      opt_scope_auto: "本项目 + 其它已启用的库",
      opt_scope_auto_n: "本项目 + 另外 {n} 个已启用的库",
      opt_scope_local: "仅当前项目",
      opt_coll_all: "全部集合",
      opt_coll_concepts: "concepts 概念卡",
      opt_coll_references: "references 文献卡",
      opt_coll_topics: "topics 主题卡",
      opt_coll_raw: "raw 原始文献",
      opt_coll_drafts: "drafts 草稿",
      search_path_ph: "路径 glob 过滤，如 raw/papers/2026-*",

      // Radar review actions
      radar_actions_title: "候选操作",
      btn_accept_inbox: "加入摄入队列",
      btn_create_issue: "建阅读任务",
      btn_mark_reviewed: "✓ 标记本报告已审",
      toast_marked_reviewed: "已标记为已审：{file}",
      toast_accepted: "已入队，识别为{kind}：{value}",
      toast_already_queued: "已经在队列里了，识别为{kind}：{value}",
      toast_issue_created: "已创建阅读任务 (bd survey)",

      // Update check. The WebUI reports; it never upgrades the package it is
      // itself running from.
      update_badge: "有新版本 {v}",
      update_title: "有新版本可用",
      update_current: "当前版本",
      update_latest: "最新版本",
      update_method: "安装方式",
      update_run_it: "在终端里运行这条命令来升级：",
      update_why_not_button:
        "这里没有\"一键升级\"按钮，是有意的：这个面板正跑在要被替换的那个包里面。"
        + "Windows 上运行中的 `magi ui` 会占住自己的文件，升级会中途失败并让 CLI 处于损坏状态——"
        + "而那时服务器已经死了，你连错误都看不到。",
      update_source_checkout: "这是源码检出，不要用包管理器升级。",
      update_unknown: "认不出这是怎么装的，请用你当初用的工具升级（pipx / uv / pip）。",
      update_windows_hint: "升级前先关掉所有 `magi ui` 进程，否则会因为文件被占用而失败。",
      update_recheck: "重新检查",
      update_apply: "立即升级",
      update_confirm:
        "升级会先关掉这个面板，因为运行中的 magi ui 占着自己要被替换的文件。"
        + "升级完成后它会自动重新启动，这个页面会自己回来。继续？",
      update_started: "已开始升级：面板正在关闭，升级完成后会自动重启。",
      update_waiting_back: "正在等待面板重新启动…",
      update_done: "已升级到 {v}。",
      update_done_unchanged: "升级命令跑完了，但版本还是 {v}——升级没有生效。",
      update_failed: "升级失败：{err}",
      update_cannot_apply: "这个安装方式不能自动升级。",
      update_checking: "正在检查…",
      update_latest_already: "已经是最新版本 {v}。",
      update_unreachable: "连不上 PyPI，查不到版本。这是网络问题，不是\"没有新版本\"。",
      // Ops catalog & danger confirm
      ops_none_here: "这个面板的操作都在别处了。",
      ops_here_dashboard: "项目维护",
      ops_here_dashboard_sub: "关于这个项目的报表",
      ops_here_melchior: "重建这个面板读的东西",
      ops_here_melchior_sub: "图谱、概念链接,以及 wiki 目录表",
      ops_here_casper: "重建搜索读的东西",
      ops_here_casper_sub: "刚加的东西搜不到时,跑这个",
      ops_here_radar: "定时收割",
      ops_here_radar_sub: "在本机的任务计划里注册每日运行",
      ops_loading: "正在加载操作目录...",
      op_stats: "项目统计",
      ops_setup_title: "项目安装",
      ops_setup_sub: "都可以重复运行，也都不删任何东西",
      op_close: "收工检查",
      op_install: "装进 agent CLI",
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
      graph_type_topic: "项目",
      graph_type_thesis: "论点",
      graph_type_claim: "命题",
      graph_type_tag: "标签",
      graph_loading: "正在加载图谱视图…",
      graph_empty: "没有匹配的记录。",
      graph_back: "返回词条列表",
      graph_out: "出链",
      graph_in: "入链",
      graph_hubs_hint: "连接最多的词条，点击阅读卡片",
      graph_broken_empty: "没有断链，链接网络完整。",
      graph_view_map: "图谱",
      graph_map_tags: "显示标签节点",
      map_kinds_all: "全部",
      map_kinds_library: "只看库",
      map_kinds_research: "只看研究状态",
      map_skeleton: "只看骨架",
      graph_map_hint: "拖拽节点 · 滚轮缩放 · 点击节点阅读卡片",
      graph_map_empty: "图谱为空——先运行 magi graph build 构建知识图谱。",
      graph_map_truncated: "节点较多，已按连接度显示前 {n} 个",
      graph_map_no_d3: "图谱物理引擎未加载——请检查 /vendor/d3-*.min.js 是否可访问",

      // Liquid-glass tuner & toggle
      glass_toggle_btn: "GLASS",
      glass_toggle_title: "切换苹果液态玻璃效果 (VisionOS 空间拟态材质)",
      glass_enabled_toast: "💎 苹果液态玻璃效果已开启",
      glass_disabled_toast: "⚪ 经典无透光实体卡片模式已切换",
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

      // Card preview
      preview_loading: "正在读取…",
      preview_back: "返回上一张",
      preview_close: "关闭",
      preview_copy_path: "复制路径",
      preview_fullscreen: "全屏（Esc 退出全屏）",
      preview_fullscreen_exit: "退出全屏",
      preview_copied: "路径已复制：{path}",
      preview_open_links: "链接视图",
      preview_out: "出链",
      preview_in: "入链",
      preview_no_links: "这张卡片还没有链接。",
      preview_truncated: "文件较大，仅显示前 2 MB。",
      preview_hint_graph: "点击节点查看卡片内容",
      preview_hint_search: "点击结果查看整张卡片",
      preview_math_off: "公式渲染引擎未加载——请检查 /vendor/katex.min.js 是否可访问",
      preview_read_card: "阅读卡片",
      preview_contents: "目录",
      preview_unresolved: "这条链接还没有对应的卡片",
    },

    en: {
      // Page & Brand
      page_title: "MAGI — Research Project WebUI",

      // Topbar
      workspace_label: "Viewing:",
      loading_workspaces: "Loading projects...",
      browsing_badge: "Browsing",
      browsing_badge_title: "The panel is browsing a different project (session-level choice; the server's launch location is unchanged)",
      term_retention_note: "Job history persists across restarts (last 40 records, ui-jobs.jsonl in the magi config directory).",
      sync_label: "Sync:",
      running_jobs_label: "Running Jobs:",
      core_sync_note: "Readiness, not a score for how much you know. A new project starts low; it rises as you clear what the three cores flag.",
      sync_ratio_tooltip: "How ready this project is: a weighted average over knowledge (graph freshness, uncompiled backlog, claim coverage), task tracking, and the retrieval index. Clear whatever the three cores above flag and this goes up.",
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

      // v2: the map, the dump box, threads, the feed
      dump_title: "Say it here",
      dump_subtitle: "No format and no category — deciding where a thought goes at the moment you have it is the cost this box removes. Filing is the agent's job.",
      dump_ph: "the disorder angle is probably a dead end",
      dump_btn: "Add to the pile",
      dump_saved: "Written down ({n} still unfiled)",
      queue_title: "Decisions waiting on you",
      queue_subtitle: "The only events allowed to interrupt you",
      queue_none: "Nothing. Every open question is somebody else's turn.",
      proposal_accept: "Accept",
      proposal_reject: "Turn down",
      proposal_promote: "Make it code",
      proposal_retire: "Retire this rule",
      proposal_done: "Done: {verb}",
      lines_title: "Research lines",
      lines_subtitle: "Phase, what is open on it, and when it last moved",
      lines_none: "No lines yet.",
      map_loading: "Reading the notes…",
      flag_over_wip: "over WIP",
      flag_quiet: "quiet",
      back_title: "Looking back",
      back_right: "predictions right",
      back_bet_line: "you said {bet}, it came out {outcome}",
      back_unknown: "recorded as \"don't know\"",
      back_unknown_only: "prediction(s) recorded as \"don't know\" — an honest prior, and not scored.",
      back_late: "bet(s) written down after the answer was already in — not scored, and not a prediction.",
      back_decisions: "Decisions, most recent last:",
      threads_title: "Threads",
      threads_subtitle: "Propositions, questions and lines — body owned by whoever opened it, discussion append-only",
      threads_none: "No notes yet.",
      filter_all_kinds: "All kinds",
      filter_all_statuses: "All statuses",
      th_thread: "Note",
      th_kind: "Kind",
      th_status: "Status",
      th_line: "Line",
      th_tier: "Tier",
      th_phase: "Phase",
      th_open: "Open",
      th_last_move: "Last move",
      th_flags: "Flags",
      thread_say_ph: "what happened, in your words",
      btn_post: "Post",
      btn_close: "Close",
      need_words: "Write something first — an empty post records nothing",
      need_reason: "A status change needs a reason: the flip and the sentence saying why are one action, not two",
      moves_need_reason_first: "Write a sentence above first — the flip and the reason are one action.",
      need_workspace: "Pick a project in the top bar first — otherwise this lands in whichever directory the server was started in",
      badge_kb_gone: "directory gone",
      btn_review: "Have this reviewed",
      btn_cancel: "Never mind",
      btn_save_draft: "Save as a draft",
      draft_title_ph: "What this write-up is about",
      draft_body_ph: "Paste the text — it lands in drafts/, and then it can be published",
      draft_needs_both: "A title and some text are both needed",
      draft_saved: "Draft saved",
      btn_publish_preview: "Show me what it buries",
      close_why_ph: "Why this line is ending (goes into the closing post)",
      review_only_when_supported: "This does not claim to be solved yet, so there is nothing for a second reader to check. It becomes reviewable at `supported`.",
      line_set: "Its lines are set",
      line_needs_reason: "Write a sentence above saying why it belongs there",
      btn_thread_new: "Open a new one",
      btn_decide: "Record this as my decision",
      decide_needs_words: "Write it in your own words above — decisions.md keeps what you said, not a summary",
      decided: "Written into decisions.md",
      bet_none: "no prediction",
      bet_supported: "I bet it holds",
      bet_refuted: "I bet it does not",
      bet_unknown: "don't know (legitimate, and recorded)",
      btn_open_it: "Open it",
      kind_proposition: "Proposition (a claim that could be wrong)",
      kind_question: "Question (nobody knows yet)",
      kind_line: "Research line (a view over related claims)",
      new_title_ph: "Title — what it actually claims",
      new_purpose_ph: "Why this is worth opening now",
      new_line_ph: "Which line it belongs to (optional)",
      new_hint: "The title becomes its permanent id. A proposition is a claim that could be wrong; a question is one nobody has answered; a line is a view over related claims.",
      new_needs_both: "A title and a why-now are both required",
      new_opened: "{slug} is open",
      line_field_ph: "Lines it belongs to, comma separated",
      btn_set_line: "Set its lines",
      btn_close_line: "End this line",
      btn_publish: "Publish and file",
      close_would_silence: "Closing it means these {n} are never mentioned again:",
      close_nothing_open: "Nothing is still open on this line.",
      close_why_prompt: "Ending {line} — why? (this goes into the closing post)",
      closed_line: "{line} is closed",
      publish_no_papers: "No .md in drafts/ or output/ — put the write-up there first.",
      publish_which: "Which paper?",
      publish_would_bury: "These {n} will be marked superseded by the paper:",
      publish_why: "What does this paper report? (this goes into the record)",
      publish_loose_ends: "Loose ends: {slugs}. Publishing anyway — say why; it goes into the record.",
      published: "Filed, and the work it reports is retired",
      btn_review_running: "asking…",
      review_hint: "Asks another vendor's CLI to read this claim — one that does not share your conversation. Costs one call from the week's budget.",
      review_confirm: "Ask {host} (model {model}) to review this claim?\n\nThis spends one call from this week's budget: {left}/{limit} left.\nUsually about fifteen seconds.",
      review_running: "Asking {host} — usually about fifteen seconds.",
      review_switched_off: "MAGI's own model calls are switched off (research.llm_calls). Turn them on to review.",
      review_by: "{host} decided ({model})",
      review_unclear: "\"Unclear\" is neither a pass nor a rejection — the reviewer is saying it could not tell from the evidence it was given. The claim stays on the list.",
      review_budget_left: "{left}/{limit} calls left this week.",
      dash_spending: "MAGI's own calls this week",
      dash_spending_line: "{spent}/{limit} used, {left} left",
      kb_hide_gone: "Hide the {n} whose directory is gone",
      cfg_review_host_auto: "auto (probe PATH for one that is not the author)",
      cfg_f_review_host: "Which CLI reviews a claim. Empty picks one that is not the author — a different vendor is the cheapest approximation of independence.",
      cfg_f_coaching: "How hard the end-of-session gate pushes. off = never blocks; light = asks for missing bookkeeping; strict = no derivation starts without a written prediction.",
      cfg_f_wip_limit: "How many propositions may be open on one line at once. Seven is a working-memory number, not a measurement: past it nobody can hold what is still unsettled on that line.",
      cfg_f_stall_days: "Days of silence before a line is called quiet. Long enough that a week off is not a flag, short enough that a forgotten line surfaces within a month.",
      cfg_f_weekly_calls: "How many model calls MAGI may make on its own initiative each week (review, the slow loop, sorting the pile). Counted in calls, not money — a headless CLI does not say what a request cost. Failed ones count: a timeout spent the wall clock too. Once spent it refuses to start rather than quietly doing less.",
      cfg_f_llm_calls: "The master switch for MAGI's own calls. Off means it makes none at all, rather than silently making fewer. Work you ask your agent to do is unaffected.",
      cfg_f_rule_budget: "How many lines the rules section in AGENTS.md may hold. Every session on every host reads that block, so a rule that goes in is paid for by every session afterwards.",
      cfg_f_rules: "The rules this project has earned, written in a closed vocabulary so that each one is actually checked on every run. `magi reflect promote` adds them; this is where one is retired.",
      cfg_f_search_projects: "Which other registered projects this project's searches reach. Empty means just this one. The registry's Searchable tick is machine-wide and says whether a library may be read at all; this says which ones this project actually reads.",
      cfg_f_hosts: "Agent CLIs this project knows about beyond the built-in ones. There are too many CLIs in the world to enumerate, so a host is a record: its binary, where its skills go, how to call it headless.",
      cfg_f_review_model: "Which model reviews. Empty means that host's cheap tier.",
      cfg_f_review_effort: "How hard it thinks. Empty means that host's own default; the model id often carries the level already.",
      cfg_model_cheap: "the cheap tier ({id})",
      cfg_model_default: "that host's own default",
      cfg_model_pin_host: "pin review_host first — model names are not portable between vendors",
      cfg_model_typed: "this host does not list its models; type one",
      cfg_model_stale: "listed from cache (up to a day old)",
      cfg_effort_default: "that host's own default",
      moves_human_only: "* only a person can make this move",
      feed_title: "Feed",
      feed_subtitle: "Every post, newest first — a view over the notes, not a second log",
      feed_none: "Nothing posted in this window.",
      feed_window_24: "Last 24 hours",
      feed_window_72: "Last 3 days",
      feed_window_168: "Last 7 days",
      feed_window_0: "Everything",

      // Dashboard Metrics
      dash_sync_label: "Sync Ratio",
      dash_sync_subtitle: "Melchior + Balthasar + Casper",
      dash_kb_label: "Projects",
      dash_kb_subtitle: "Searchable on this machine — the one you are viewing is named in the topbar",
      dash_radar_label: "Papers to Triage",
      dash_radar_subtitle: "Literature radar · this project only",
      dash_task_label: "Tasks Ready",
      dash_task_subtitle: "Not blocked by anything else · counted across the hub, not this project alone",

      // Three-core status band
      core_role_mel: "Cognitive state",
      core_role_bal: "Task state",
      core_role_cas: "Retrieval",
      core_sync_label: "Three-core sync",
      core_state_ok: "Nominal",
      graph_legend_concept: "concept",
      graph_legend_reference: "reference",
      graph_legend_topic: "topic",
      graph_legend_thesis: "thesis",
      graph_legend_claim: "claim",
      graph_legend_proposition: "proposition",
      graph_legend_question: "question",
      graph_legend_line: "line",
      graph_legend_ghost: "dangling link",
      graph_legend_tag: "tag",
      graph_legend_other: "unclassified ({kinds})",
      graph_legend_size: "bigger dot = more links",
      graph_needs_build: "No knowledge graph for this project yet. Build it to browse how concepts connect.",
      running_jobs_tooltip: "Background jobs running right now, across every project on this machine. Click to watch the log.",
      claims_none_yet: "No claims recorded yet",
      btn_hint_howto: "How",
      kb_table_sub: "Every project magi knows about on this machine. Switching points every panel at it.",
      core_state_notset: "Not set up yet",
      core_state_attention: "Needs attention",
      core_state_fault: "Fault",
      core_state_offline: "Not linked",
      core_detail_nolink: "No project selected",
      core_detail_mel: "{c} concepts · {r} references · {v}/{n} claims verified",
      core_detail_bal: "{r} ready · {p} in progress · {b} blocked",
      core_detail_bal_kbonly: "Knowledge-base only, task tracking off",
      core_detail_bal_noengine: "beads not installed — run magi setup",
      core_detail_bal_uninit: "Task store not initialized",
      core_detail_cas: "{c} indexed passages · {v} with semantic index",
      core_detail_cas_noindex: "No retrieval index built",

      // Dashboard KB Table
      dash_kb_table_title: "Registered Projects",
      dash_kb_table_subtitle: "Every project magi knows about on this machine. Switching points every panel at it.",
      btn_refresh: "Refresh",
      th_kb_name: "Project",
      th_path: "Path",
      th_searchable: "Searchable",
      th_indexed: "Indexed",
      th_graph: "Graph",
      th_sync_ratio: "Sync Ratio",
      th_actions: "Actions",
      loading_kbs: "Loading projects...",
      no_kbs_registered: "No projects registered yet.",
      badge_current: "current",
      badge_indexed: "Indexed",
      badge_no_index: "No Index",
      badge_graph_built: "Built",
      badge_graph_missing: "Missing",
      btn_switch_ws: "Switch",
      btn_unreg_kb: "Remove",
      unreg_confirm: "Unregister project '{name}'? (Project files will remain untouched)",

      // Register Form
      reg_kb_title: "Register New Project",
      reg_kb_subtitle: "Add a project directory to the global registry",
      reg_kb_path_ph: "Absolute or relative path...",
      reg_kb_name_ph: "Custom name (optional)...",
      reg_kb_enable_label: "Enable in search",
      btn_reg_kb: "Register a project",

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
      bal_no_db_initialized: "No task-tracking database in this project or its hub. This step is optional — skip it if you do not want task tracking.",
      bal_backlog_sync_desc: "Scan raw/ for sources with no compiled reference card yet, and open one task per source",
      bal_store_at: "The task store file lives at {root}, shared by the topics under it — the counts and list below are just this project's.",
      bal_store_shared: "Task store lives at the hub: {root} — the four numbers below cover every topic under it, not just this project.",
      bal_store_local: "Task store lives in this project: {root}",
      scope_badge_hub: "hub-level",
      bal_init_writes_hub: "Creates the store at the hub root, shared by every topic under it",
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
      close_strong: "close",
      close_related: "related",
      close_weak: "distant",
      badge_close_tip: "Semantic distance {d} — lower is closer. This is a hint, not a filter; nothing is dropped.",
      search_scope_searched: "Searched: {names}",
      search_scope_skipped_here: "The project you are viewing, {name}, was NOT searched — it has no retrieval index, so none of these hits come from it.",
      search_scope_skipped: "Skipped: {names}",
      search_scope_this_one: "this project",
      search_all_weak: "Nothing in this project is semantically close to that query. The results below are only the nearest available, and may not be relevant — try different wording, or a term the library actually uses.",
      badge_rrf_tip: "Combined rank score: the keyword ranking and the meaning ranking fused into one. Higher is more relevant.",
      badge_bm25_tip: "Ranked #{n} by keyword match",
      badge_vec_tip: "Ranked #{n} by meaning similarity",
      vec_avail_bychoice: "not used (you chose keyword-only)",
      vec_avail_no: "off",

      // Literature Radar
      radar_seen_label: "Seen Papers Ledger",
      radar_waiting_label: "Papers Awaiting Triage",
      radar_last_label: "Last Harvest",
      radar_never: "never",
      radar_today: "today",
      radar_days_ago: "{days}d ago",
      radar_seen_sub_n: "{n} papers seen in total",
      radar_pending_sub_n: "across {files} report(s)",
      radar_pending_sub_clear: "nothing pending review",
      radar_hide_decided: "Hide decided",
      radar_triage_progress: "{done} of {total} triaged",
      radar_rel_top: "strong",
      radar_rel_mid: "related",
      radar_rel_low: "weak",
      radar_rel_tooltip: "cosine {score} against this project's centroid (ranked within this harvest)",
      radar_settings_title: "Radar settings",
      btn_radar_settings: "Settings…",
      btn_dismiss: "Skip",
      tip_dismiss: "Records a 'not interested' decision. Touches no files, and Undo reverses it.",
      tip_accept_inbox: "Adds this paper to the project's ingest queue. Downloads nothing now — running the queue fetches and converts it, and it still needs your approval before entering the library.",
      tip_create_issue: "Opens a survey task in the task store at the hub, shared by every topic under it. No download, nothing written to inbox/.",
      tip_create_issue_no_store: "The hub for this project has no task store yet — initialize it on the Balthasar tab.",
      btn_undo: "Undo",
      digest_source_title: "View digest source ({file})",
      btn_radar_schedule: "Schedule…",
      radar_schedule_on: "Daily at {time}",
      radar_schedule_off: "No daily harvest scheduled",
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
      op_rebuild_index: "Make search find new content",
      tab_ingest: "Ingest Queue",
      loading: "Loading…",
      ingest_waiting_label: "Waiting in Queue",
      ingest_waiting_sub: "Queued, not yet fetched",
      ingest_undecided_label: "Awaiting Your Approval",
      ingest_undecided_sub: "Converted, nothing in the project yet",
      btn_ingest_run: "Run the Queue",
      btn_ingest_commit: "Commit Approved",
      btn_ingest_upload: "Upload",
      zotero_label: "Or import from Zotero",
      zotero_loading: "Reading your Zotero library…",
      zotero_pick: "Pick a collection",
      zotero_whole_library: "The whole library",
      zotero_tag_ph: "tag (optional)",
      zotero_hint: "A folder includes everything filed beneath it. Queuing fetches nothing — the queue below converts, and you approve.",
      zotero_pick_something: "Pick a collection, or type a tag.",
      zotero_working: "Reading and queuing…",
      zotero_queued: "Queued {n} ({already} were already waiting, {skipped} had nothing to fetch them by)",
      btn_zotero_import: "Queue them",
      ingest_upload_label: "Or upload a file from this computer",
      ingest_upload_hint: "Lands in inbox/ and joins the queue below, so it goes through the same review as everything else.",
      ingest_upload_working: "Uploading {name}…",
      ingest_upload_queued: "{name} uploaded and queued — run the queue to convert it.",
      ingest_upload_text_done: "{name} is in inbox/. It is already text, so there is nothing to convert — the next 'magi ingest auto' files it.",
      btn_ingest_add: "Queue it",
      ingest_add_label: "Add a paper by link, DOI, or arXiv id",
      ingest_add_hint: "Queuing fetches nothing. Run the queue, then approve what came out.",
      ingest_batches_title: "Batches",
      ingest_hide_decided: "Hide decided",
      ingest_empty: "Nothing queued yet.",
      ingest_no_workspace: "Pick a project above to see its ingest queue.",
      ingest_scope: "This project: {name}",
      ops_badge_global: "machine-wide",
      feature_off_quiet: "This feature is turned off.",
      cfg_get_one: "where to get one \u2197",
      cfg_secret_set: "saved (never shown again; type a new one to replace)",
      cfg_secret_unset: "not set",
      cfg_secret_empty: "Nothing to save — leaving it blank does not clear a stored key.",
      cfg_provider_ollama: "Ollama (this machine)",
      cfg_provider_openai: "Cloud (any OpenAI-compatible endpoint)",
      cfg_f_s2_api_key: "Semantic Scholar key (free, optional). Without one the radar shares an anonymous quota with everybody. $SEMANTIC_SCHOLAR_API_KEY wins over this",
      cfg_f_mineru_token: "MinerU API token, for cloud PDF conversion",
      cfg_f_embedding_provider: "Where vectors come from: local Ollama, or any OpenAI-compatible cloud endpoint",
      cfg_f_embedding_base_url: "Cloud endpoint, including /v1 (e.g. https://api.siliconflow.com/v1)",
      cfg_f_embedding_model: "Model id at that endpoint (e.g. BAAI/bge-m3). Blank falls back to models.embedding",
      cfg_f_embedding_api_key: "Key for the cloud endpoint. $MAGI_EMBEDDING_API_KEY works too and wins over this",
      embed_help_open: "Would rather not install Ollama?",
      embed_help_title: "Semantic search without installing Ollama",
      embed_help_body: "Semantic search needs an embedding model to turn text into vectors. The default is a local Ollama, but any **OpenAI-compatible** `/v1/embeddings` endpoint works — set `embedding.provider` to `openai`.\n\nThese four were checked against their own live docs for endpoint shape, and each has a free tier or is very cheap. Treat the specific allowances as provisional; providers change them often.\n\n| Service | base_url | Model | Notes |\n|---|---|---|---|\n| SiliconFlow | `https://api.siliconflow.com/v1` | `BAAI/bge-m3`, `Qwen/Qwen3-Embedding-0.6B` | Strong on both English and Chinese, several free models; signup may want a Chinese phone number |\n| Jina AI | `https://api.jina.ai/v1` | `jina-embeddings-v3` | Schema is modelled on OpenAI's, multilingual, free trial tokens |\n| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-embedding-001` | Ordinary Google account; free allowance shown in AI Studio |\n| DeepInfra | `https://api.deepinfra.com/v1/openai` | `BAAI/bge-m3` | No free tier, but cents per million tokens |\n\n**Cohere, Voyage and Zhipu** are not OpenAI-shaped and are not supported yet.\n\n> Changing model changes the vector width, which an existing index cannot hold. Run `magi index --rebuild` afterwards.",
      cfg_f_ocr_mineru_token: "MinerU token",
      tasks_title: "Tasks",
      tasks_loading: "Reading tasks…",
      tasks_show_hub: "Show every topic under the hub",
      tasks_show_closed: "Include closed",
      tasks_no_store: "No task store yet.",
      tasks_all_here: "{here} task(s), all of them in {name}.",
      tasks_split: "{here} in {name}; the same store holds {elsewhere} more belonging to other topics under {root}.",
      tasks_none: "No open tasks.",
      tasks_none_here: "No tasks in this project. Tick the box above to see the other topics'.",
      task_status_open: "open",
      task_status_in_progress: "in progress",
      task_status_blocked: "blocked",
      task_status_closed: "closed",
      task_blocked_by: "blocked by {n}",
      task_blocks: "blocks {n}",
      task_start: "Start",
      task_start_tip: "Claim this task and mark it in progress.",
      task_close: "Close",
      task_close_tip: "Mark it done. Reopenable, and nothing is deleted.",
      task_reopen: "Reopen",
      task_reopen_tip: "Put this closed task back on the list.",
      task_done_start: "Started {id}.",
      task_done_close: "Closed {id}.",
      task_done_reopen: "Reopened {id}.",
      scope_help_open: "What are these three words?",
      scope_help_title: "Projects and the registry — how they relate",
      scope_help_body: "A **project** is one research subject's directory, holding wiki/, raw/ and output/. You make one with `magi init`. Everything this dashboard calls a project — it used to also say workspace, topic and knowledge base — is this.\n\nThe **registry** (`~/.config/magi/registry.json`) is the list of projects on this machine. Registering one does two things: the picker in the top bar can switch to it, and other projects are allowed to search it — which they still only do if they name it in `research.search_projects`, since by default a search stops at its own project.\n\nUnregistering removes a project from that list and touches no files.",
      opt_title: "Optional components",
      opt_sub: "All of this is machine-wide, and MAGI runs without any of it — each one just turns on a specific capability. Untick what you do not want and it stops being mentioned.",
      opt_unknown: "Could not read component status.",
      feature_label_radar: "Literature radar",
      feature_label_tasks: "Task tracking",
      opt_unlocks_ollama: "semantic (vector) search, and local offline OCR for PDFs",
      opt_unlocks_pandoc: "the LaTeX and arXiv-HTML ingest routes — the best-fidelity way in",
      opt_unlocks_poppler: "local OCR page rendering (needed alongside Ollama)",
      opt_unlocks_latex: "deep math validation — checks a formula actually compiles",
      opt_unlocks_mineru: "cloud PDF conversion, strong on formulas and layout",
      opt_hint_ollama: "after installing, magi setup pulls the embedding model for you",
      opt_hint_poppler: "Windows builds: https://github.com/oschwartz10612/poppler-windows/releases",
      opt_hint_mineru: "sign up, then put the token in config.yaml under ocr.mineru_api_token",
      feature_what_radar: "watches arXiv and Semantic Scholar for new papers in your area, and queues them for you to triage",
      feature_what_tasks: "turns your reading and compiling backlog into a dependency-aware task graph",
      opt_unlocks: "Unlocks: {unlocks}",
      opt_present: "installed",
      opt_absent: "not installed",
      opt_service: "hosted service",
      opt_want_tip: "Ticked means you want {name}; unticking stops the doctor listing it as outstanding. This installs and uninstalls nothing.",
      opt_wanted_toast: "Noted: you want {name}.",
      opt_declined_toast: "Noted: {name} is not wanted, and will not be raised again.",
      metric_feature_off: "off",
      feature_off_title: "{name} is turned off",
      feature_off_body: "Turned on it {what}. While it is off this tab does nothing, and nothing already on disk is deleted.",
      feature_turn_on: "Turn on {name}",
      feature_turn_on_plain: "Flips one machine-wide switch. Installs nothing and touches no project files.",
      feature_turn_on_installs: "Flips the switch and installs {needs}, which it needs (network, about a minute).",
      feature_will_install: "Needs {needs} — MAGI installs that one itself.",
      feature_on_toast: "{name} is on.",
      tool_open_site: "Open the {name} site \u2197",
      tool_recheck: "I installed it — check again",
      tool_recheck_tip: "Look for {name} on this machine again. MAGI cannot install it — it is another project's installer.",
      tool_found: "Found {name}.",
      tool_still_missing: "Still cannot find {name}. A fresh install may need a new terminal, or a restart of the MAGI server.",
      op_install_tasks: "Install the task store",
      op_pull_models: "Pull Ollama models",
      op_desc_install_tasks: "Turn task tracking on and install the bd task store it uses",
      op_desc_pull_models: "Pull the Ollama models MAGI uses (needs Ollama installed first)",
      btn_install_tasks: "Install the task store",
      btn_pull_models: "Pull Ollama models",
      ingest_run_caption: "Fetches and converts everything queued, then gate-checks it · nothing reaches the project yet",
      ingest_commit_caption: "Moves approved items into raw/ and refreshes the tables and graph · compiling them into reference cards, and making them searchable, are separate steps after this",
      doctor_scope: "Tools and paths are machine-wide. Rows that say \"this project\" mean: {name}",
      metric_not_applicable: "no store",
      hint_dest_tab: "Opens the {name} tab · runs nothing",
      hint_dest_docs: "Opens the matching chapter in {name} · runs nothing",
      op_desc_index: "Rebuilds the search index · embeds every changed document, minutes for a full pass (keyword-only without Ollama)",
      op_desc_graph_build: "Re-scans wikilinks and tags · fast, no model involved",
      op_desc_wiki_reindex: "Regenerates the _index.md list in each wiki folder · seconds",
      op_desc_link: "Link semantically related concept cards by vector similarity (needs Ollama)",
      op_desc_lint_fix: "Repair broken links and frontmatter in place",
      op_desc_stats: "Count this project’s cards, link density and gaps",
      op_desc_close: "List what happened that nobody wrote down, settle a status two writers contended, and rewrite MAP.md",
      op_desc_install: "Put the skills, the AGENTS.md protocol block and the stop gate into every detected agent CLI (safe to re-run)",
      op_desc_backlog_sync: "Open one task per raw source that has no compiled reference card yet",
      op_desc_radar_harvest: "Fetch new candidate papers from arXiv and Semantic Scholar",
      radar_harvest_caption: "Fetches new candidates from arXiv and Semantic Scholar into this project's inbox/radar/ · minutes, network",
      radar_gap_caption: "Citation Gaps: recent papers that arguably should cite yours · Settings: which queries and authors the radar watches",
      radar_settings_tip: "Edit this project's radar block in config.yaml",
      op_desc_radar_citation_gap: "Scout recent papers that arguably should cite yours",
      op_desc_ingest_batch_run: "Fetch and convert everything queued — output waits for your approval, nothing enters the library",
      op_desc_ingest_batch_commit: "Move approved documents into raw/; refuses while anything is still undecided",
      ingest_preview: "Look at what came out",
      ingest_cannot_approve: "This conversion failed — there is nothing to approve. Reject it and it retries on the next route down.",
      ingest_approve: "Approve",
      ingest_reject: "Reject",
      ingest_undo: "Undo",
      ingest_badge_undecided: "{n} undecided",
      ingest_badge_ready: "ready to commit",
      ingest_requeued: "Rejected — retrying on the next route down: {route} (it appears in the next batch)",
      ingest_queued: "Queued as {kind}: {value}",
      op_ingest_batch_run: "Run ingest queue",
      op_ingest_auto: "Pick up what is in inbox/",
      op_desc_ingest_auto: "Routes each loose file in inbox/ to the right ingester and files it.",
      inbox_title: "{n} file(s) sitting in inbox/",
      inbox_sub: "This is where the dashboard's \"drop paper PDFs into inbox/\" puts them. They are not in the queue — the queue only holds what was added through the boxes below.",
      inbox_pickup: "Pick these up",
      op_ingest_batch_commit: "Commit approved batches",
      op_build_graph: "Rebuild the concept graph",
      op_reindex_wiki: "Refresh the contents lists",
      op_semantic_link: "Semantic Link",
      op_lint_fix: "Lint & Auto-Fix",
      op_backlog_sync: "Backlog to Tasks",
      op_index: "Rebuild Index",
      op_graph_build: "Build Graph",
      op_wiki_reindex: "Reindex Wiki Tables",
      op_link: "Semantic Link",
      danger_title: "Danger Zone",
      danger_sub: "These operations alter project structure, reset state, or delete legacy files. Each action requires explicit confirmation.",
      btn_danger_setup: "Provision Setup",
      btn_danger_migrate: "Migrate Project",
      btn_danger_pm_init: "Initialize Task Tracking",
      btn_danger_legacy: "Remove Legacy Copies",

      // Danger Actions Meta & Modals
      danger_modal_title: "Confirm Action",
      danger_modal_default_desc: "Are you sure you want to proceed with this operation?",
      danger_setup_title: "Environment Setup",
      danger_setup_desc: "Re-provisions this environment: the task engine, Ollama models, a scan for installed agent CLIs (Claude Code / Codex / Antigravity / opencode), and Claude Code plugin registration — that last step exists only for Claude Code.",
      danger_migrate_title: "Migrate Project",
      danger_migrate_desc: "Migrate old project layouts and files to the MAGI standard.",
      danger_pm_init_title: "Initialize Task Tracking",
      danger_pm_init_desc: "Initialize the task tracking database in the hub directory.",
      danger_remove_legacy_title: "Remove Legacy Copies",
      danger_remove_legacy_desc: "Permanently deletes pre-MAGI Wikify scripts from ~/.claude/skills and ~/.gemini/skills. Only those two, because legacy Wikify predates Codex / Antigravity / opencode support — not a preference for one vendor.",
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
      doc_guide: "User Guide",
      docs_toc_title: "Contents",
      copy_code: "Copy",
      copied: "Copied",
      copy_failed: "Copy failed",
      cal_expect: "What you should see",
      cal_fix: "If it doesn't",
      cal_warn: "Careful",
      cal_note: "Note",
      cal_tip: "Tip",
      bg_pick_label: "Backdrop",
      bg_shuffle: "Shuffle",
      bg_shuffle_title: "Swap to another image from the current pool",
      bg_pick_auto: "Nothing picked — rotating by window shape",
      bg_pick_one: "Pinned to this one",
      bg_pick_many: "Rotating among the {n} picked",
      bg_pick_none: "No artwork for this mode. Drop images in ~/.config/magi/ui-backgrounds/ to use your own.",
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
      badge_optional: "Optional",
      badge_declined: "Skipped",
      doctor_all_good: "Nothing is broken. {count} optional component(s) are not installed — MAGI works without them.",
      doctor_get_it: "Get it",
      doctor_legacy_found: "Legacy copies detected ({count}):",
      doctor_legacy_hint: "You can safely remove them in Operations > Danger Zone > Remove Legacy Copies.",
      doctor_clean: "✓ No legacy copies detected. Environment is healthy.",
      btn_doc_close: "Close",

      // Toasts & Alerts
      toast_select_ws_first: "Please select an active project first.",
      toast_job_started: "Started background job: {name}",
      toast_job_success: "Job '{name}' completed successfully.",
      toast_job_ended: "Job '{name}' ended ({status}).",
      toast_job_cancel_req: "Job cancellation requested.",
      toast_job_fail: "Failed to dispatch job: {error}",
      toast_kb_registered: "Project registered successfully.",
      toast_kb_status_updated: "project '{name}' search status updated.",
      toast_ws_switched: "Switched active project.",
      toast_kb_unregistered: "Unregistered project '{name}'.",

      // Sync Hints (actionable)
      hints_title: "Suggested Actions",
      hints_subtitle: "What the sync report recommends next — click to run",
      hint_graph_build: "Knowledge graph is behind the cards and needs a rebuild",
      hint_index: "Retrieval index is missing or stale and needs a rebuild",
      hint_backlog_sync: "Uncompiled sources are not yet tracked as tasks",
      hint_pm_init: "No task-tracking database yet (optional — skip it if you do not want task tracking)",
      hint_radar_review: "{pending} literature radar digest(s) waiting for review",
      hint_radar_gaps: "{pending} citation-gap report(s) waiting for review",
      hint_radar_overdue: "Last radar harvest was {days}d ago (the window is {window}d) — run one, or check the scheduled task",
      hint_compile_pending: "{backlog} raw source(s) are not compiled into reference cards yet",
      hint_claims_unverified: "Some claims are still unverified (see Melchior)",
      hint_bd_ready: "There is actionable work ready (see Balthasar)",
      hint_install_beads: "Task engine (beads) is not installed — see install guide",
      hint_ingest_start: "Drop paper PDFs / sources into inbox/ and run the ingest skill",
      btn_hint_run: "Run",
      btn_hint_goto: "Open",

      // Search guidance
      vec_unavailable_hint: "Semantic search is off: it needs a local Ollama model available when 'magi index' builds the index. Keyword matching only for now.",
      vec_degraded_hint: "Semantic search fell back to keywords: Ollama did not answer in time, usually because an indexing job is holding it. Search again once that finishes.",
      search_no_results_hint: "Try 2-3 keywords instead of a full sentence, switch the search mode, or make sure this project has a built index (Rebuild Index).",

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
      mel_drafts_subtitle: "Paper drafts under drafts/ — indexed for search, outside the graph (draft skill)",
      drafts_none: "No drafts yet — the draft skill sets up the writing workflow.",

      // Workspace config
      cfg_title: "Project Config",
      cfg_subtitle: "Research knobs from config.yaml — edits touch only the target line, comments preserved",
      cfg_loading: "Loading config...",
      btn_cfg_save: "Save",
      toast_cfg_saved: "Saved {key}",
      cfg_list_hint: "separate multiple values with commas",
      cfg_f_radar_min_relevance: "Radar relevance threshold (candidates below are dropped; empty = keep all)",
      cfg_f_radar_days: "Radar lookback in days (the arXiv leg only — Semantic Scholar recommends within a fixed 60-day window)",
      cfg_f_radar_max_candidates: "Max candidates per harvest",
      cfg_f_radar_arxiv_categories: "arXiv categories (e.g. cond-mat.str-el)",
      cfg_f_radar_seed_arxiv_ids: "Papers that describe what you care about (may be empty — the ones on your reference cards are merged in automatically)",
      cfg_f_radar_own_arxiv_ids: "Your own papers' arXiv IDs (empty falls back to the list above, which may not be yours)",
      cfg_f_ocr_use_mineru: "Use MinerU cloud OCR (token configured in config)",
      cfg_f_models_embedding: "Semantic model (Ollama model name)",

      // Search filters
      opt_scope_auto: "This library + other enabled projects",
      opt_scope_auto_n: "This library + {n} other enabled",
      opt_scope_local: "This project only",
      opt_coll_all: "All collections",
      opt_coll_concepts: "concepts",
      opt_coll_references: "references",
      opt_coll_topics: "topics",
      opt_coll_raw: "raw",
      opt_coll_drafts: "drafts",
      search_path_ph: "path glob filter, e.g. raw/papers/2026-*",

      // Radar review actions
      radar_actions_title: "Candidate Actions",
      btn_accept_inbox: "Queue for ingest",
      btn_create_issue: "Create reading task",
      btn_mark_reviewed: "✓ Mark report reviewed",
      toast_marked_reviewed: "Marked reviewed: {file}",
      toast_accepted: "Queued as {kind}: {value}",
      toast_already_queued: "Already waiting as {kind}: {value}",
      toast_issue_created: "Reading task created (bd survey)",

      // Update check. The WebUI reports; it never upgrades the package it is
      // itself running from.
      update_badge: "{v} available",
      update_title: "A newer release is available",
      update_current: "Installed",
      update_latest: "Latest",
      update_method: "Install method",
      update_run_it: "Run this in a terminal to upgrade:",
      update_why_not_button:
        "There is deliberately no upgrade button here: this dashboard is running "
        + "from the package that would be replaced. On Windows a live `magi ui` "
        + "holds its own files open, so the upgrade fails halfway and leaves the "
        + "CLI broken — in front of somebody who cannot see the error, because "
        + "the server just died.",
      update_source_checkout: "This is a source checkout — do not upgrade it with a package manager.",
      update_unknown: "Could not tell how this was installed; upgrade with the tool you used (pipx / uv / pip).",
      update_windows_hint: "Stop every `magi ui` process first, or the upgrade fails on locked files.",
      update_recheck: "Check again",
      update_apply: "Upgrade now",
      update_confirm:
        "Upgrading closes this dashboard first, because a running magi ui holds "
        + "open the very files being replaced. It restarts itself when the "
        + "upgrade finishes and this page will come back on its own. Continue?",
      update_started: "Upgrade started: the dashboard is shutting down and will restart itself.",
      update_waiting_back: "Waiting for the dashboard to come back…",
      update_done: "Upgraded to {v}.",
      update_done_unchanged: "The upgrade command finished but the version is still {v} — it did not take effect.",
      update_failed: "Upgrade failed: {err}",
      update_cannot_apply: "This install cannot be upgraded automatically.",
      update_checking: "Checking…",
      update_latest_already: "You are on the latest release ({v}).",
      update_unreachable: "Could not reach PyPI. That is a network problem, not an answer about versions.",
      // Ops catalog & danger confirm
      ops_none_here: "Everything this panel used to hold now lives where it belongs.",
      ops_here_dashboard: "Project maintenance",
      ops_here_dashboard_sub: "Reports about this project",
      ops_here_melchior: "Rebuild what this panel reads",
      ops_here_melchior_sub: "The graph, the concept links and the wiki tables",
      ops_here_casper: "Rebuild what search reads",
      ops_here_casper_sub: "Run this when something you just added cannot be found",
      ops_here_radar: "Scheduled harvesting",
      ops_here_radar_sub: "Registers a daily run with this machine's scheduler",
      ops_loading: "Loading operations…",
      op_stats: "Project Stats",
      ops_setup_title: "Project setup",
      ops_setup_sub: "Re-runnable, and none of it deletes anything",
      op_close: "Close the session",
      op_install: "Install into your agent CLIs",
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
      graph_hubs_hint: "Most-connected entries — click one to read its card",
      graph_broken_empty: "No broken links — the link network is intact.",
      graph_view_map: "Graph",
      graph_map_tags: "Show tag nodes",
      map_kinds_all: "Everything",
      map_kinds_library: "The project",
      map_kinds_research: "The research state",
      map_skeleton: "Skeleton only",
      graph_map_hint: "Drag nodes · scroll to zoom · click a node to read its card",
      graph_map_empty: "The graph is empty — run magi graph build first.",
      graph_map_truncated: "Large graph — showing the top {n} nodes by degree",
      graph_map_no_d3: "Graph physics library failed to load — check /vendor/d3-*.min.js",

      // Liquid-glass tuner & toggle
      glass_toggle_btn: "GLASS",
      glass_toggle_title: "Toggle Apple Liquid Glass Material (VisionOS optical texture)",
      glass_enabled_toast: "💎 Apple Liquid Glass Enabled",
      glass_disabled_toast: "⚪ Classical Solid Card Mode Enabled",
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

      // Card preview
      preview_loading: "Reading…",
      preview_back: "Back",
      preview_close: "Close",
      preview_copy_path: "Copy path",
      preview_fullscreen: "Full screen (Esc to leave)",
      preview_fullscreen_exit: "Leave full screen",
      preview_copied: "Path copied: {path}",
      preview_open_links: "Links view",
      preview_out: "Outgoing",
      preview_in: "Incoming",
      preview_no_links: "This card has no links yet.",
      preview_truncated: "Large file — showing the first 2 MB.",
      preview_hint_graph: "Click a node to read its card",
      preview_hint_search: "Click a result to read the whole card",
      preview_math_off: "Math renderer failed to load — check /vendor/katex.min.js",
      preview_read_card: "Read card",
      preview_contents: "Contents",
      preview_unresolved: "No card behind this link yet",
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

  // Which library you are LOOKING at is per-tab. The badge tooltip has always
  // called it a session-level choice, but it lived in localStorage, so opening
  // a second tab silently inherited whatever the first tab last picked — and
  // changing it in one moved the other on its next reload.
  //
  // sessionStorage gives each tab its own, seeded once from the last choice
  // this browser made, so reopening still lands where you left off.
  function viewWorkspaceGet() {
    try {
      const s = window.sessionStorage && window.sessionStorage.getItem("magi-view-workspace");
      if (s) return s;
    } catch (_) {}
    return safeStorageGet("magi-view-workspace");
  }

  function viewWorkspaceSet(value) {
    try {
      if (window.sessionStorage) window.sessionStorage.setItem("magi-view-workspace", value);
    } catch (_) {}
    safeStorageSet("magi-view-workspace", value);   // the default for a new tab
  }

  function safeStorageRemove(key) {
    try {
      if (typeof window !== "undefined" && window.localStorage) {
        window.localStorage.removeItem(key);
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

  // Whether the liquid-glass material starts on. An explicit choice from the
  // GLASS control always wins; with no stored choice we follow the OS. Both
  // Windows and macOS expose a "reduce transparency" setting, and Windows 11
  // ships it off in several states, so this has to be a *default* rather than
  // the hard gate it used to be: the previous build force-killed --glass-blur
  // to 0 with !important from both a media query and an html.reduced-transparency
  // class, which left the entire material system dead and unreachable on any
  // machine with that setting on -- and silently overrode the tuner's blur
  // slider, so dragging it did nothing.
  function initialLiquidGlass() {
    const stored = safeStorageGet("magi-liquid-glass");
    if (stored === "true") return true;
    if (stored === "false") return false;
    try {
      return !window.matchMedia("(prefers-reduced-transparency: reduce)").matches;
    } catch (_) {
      return true;
    }
  }

  const state = {
    workspace: "",
    serverWorkspace: "",
    kbs: [],
    // Machine-wide, not per-workspace: which optional features are on, and
    // which external tools are present. null means "not read yet", which is
    // deliberately different from "off" — an unread answer must never grey a
    // working panel out.
    features: null,
    activeTab: "dashboard",
    activeDoc: "guide",
    graphView: "map",
    graphNode: null,
    activeJobId: null,
    activeJobName: "",
    eventSource: null,
    logSink: null,
    theme: detectInitialTheme(),
    lang: detectInitialLanguage(),
    liquidGlass: initialLiquidGlass(),
  };

  // ------------------------------------------------------------------------
  // DOM Elements
  // ------------------------------------------------------------------------

  const els = {
    themeToggleBtn: document.getElementById("theme-toggle-btn"),
    magiModeBtn: document.getElementById("magi-mode-btn"),
    glassToggleBtn: document.getElementById("glass-toggle-btn"),
    evaClock: document.getElementById("eva-clock"),
    evaBoot: document.getElementById("eva-boot"),
    langToggle: document.getElementById("lang-toggle"),
    langBtnZh: document.getElementById("lang-btn-zh"),
    langBtnEn: document.getElementById("lang-btn-en"),
    workspaceSelect: document.getElementById("workspace-select"),
    appVersion: document.getElementById("app-version"),
    updateBadge: document.getElementById("update-badge"),
    syncRatioBadge: document.getElementById("sync-ratio-badge"),
    syncRatioVal: document.getElementById("sync-ratio-val"),
    activeJobsBadge: document.getElementById("active-jobs-badge"),
    activeJobsCount: document.getElementById("active-jobs-count"),
    doctorBtn: document.getElementById("doctor-btn"),

    // Tabs
    tabBtns: document.querySelectorAll(".tab-btn"),
    ingestPendingCount: document.getElementById("ingest-pending-count"),
    ingestUndecidedCount: document.getElementById("ingest-undecided-count"),
    ingestBatches: document.getElementById("ingest-batches"),
    ingestScope: document.getElementById("ingest-scope"),
    ingestHideDecided: document.getElementById("ingest-hide-decided"),
    ingestAddUrl: document.getElementById("ingest-add-url"),
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
    radarPendingCount: document.getElementById("radar-pending-count"),
    radarPendingSub: document.getElementById("radar-pending-sub"),
    radarLastHarvest: document.getElementById("radar-last-harvest"),
    radarSeenCountSub: document.getElementById("radar-seen-count-sub"),
    radarSettings: document.getElementById("radar-settings"),
    radarSettingsBody: document.getElementById("radar-settings-body"),
    btnRadarSettings: document.getElementById("btn-radar-settings"),
    digestTriage: document.getElementById("digest-triage"),
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
    docsShell: document.getElementById("docs-shell"),
    docsToc: document.getElementById("docs-toc"),
    docsTocList: document.getElementById("docs-toc-list"),

    // Modals
    dangerModal: document.getElementById("danger-modal"),
    dangerModalTitle: document.getElementById("danger-modal-title"),
    dangerModalDesc: document.getElementById("danger-modal-desc"),
    dangerModalCancel: document.getElementById("danger-modal-cancel"),
    dangerModalConfirm: document.getElementById("danger-modal-confirm"),
    doctorModal: document.getElementById("doctor-modal"),
    doctorModalBody: document.getElementById("doctor-modal-body"),
    doctorModalClose: document.getElementById("doctor-modal-close"),
    docPreviewModal: document.getElementById("doc-preview-modal"),
    docPreviewTitle: document.getElementById("doc-preview-title"),
    docPreviewMeta: document.getElementById("doc-preview-meta"),
    docPreviewContent: document.getElementById("doc-preview-content"),
    docPreviewSide: document.getElementById("doc-preview-side"),
    docPreviewBack: document.getElementById("doc-preview-back"),
    docPreviewCopy: document.getElementById("doc-preview-copy"),
    docPreviewClose: document.getElementById("doc-preview-close"),
    docPreviewFullscreen: document.getElementById("doc-preview-fullscreen"),
    docPreviewLinksBtn: document.getElementById("doc-preview-links-btn"),

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
      [/^Node '?(.+?)'? has no file behind it.*$/, "「$1」还没有对应的卡片（它是标签，或一条尚未写出的链接）"],
      [/^No graph node with id '?(.+?)'?$/, "图谱里没有「$1」这个节点——可能是还没写的卡片"],
      [/^No such file: (.+)$/, "文件不存在：$1"],
      [/^path escapes the workspace$/, "路径越出了工作区"],
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

  // Two callers legitimately want the same panel data at startup — the initial
  // status read and the panel's own loader — and they fire microseconds apart,
  // so both used to issue the same request. Page load paid for /api/kb three
  // times and /api/workspace/sync twice, and /api/kb is the most expensive
  // request the dashboard makes.
  //
  // This coalesces only calls that overlap in flight; it is deliberately not a
  // cache. A call made after this one settles still hits the network, so
  // switching back to a tab later shows fresh data and no invalidation rule
  // has to be maintained.
  // The window is sized to cover one page-load sequence, not to cache: the
  // two callers run one after the other, not at the same time, so merging
  // only concurrent calls still left the second request to fire. Anything a
  // person could do — click refresh, switch tabs and come back — takes far
  // longer than this and refetches normally.
  const SETTLE_MS = 1500;
  const inFlight = new Map();
  const settledAt = new Map();

  function coalesce(key, run) {
    const running = inFlight.get(key);
    if (running) return running;
    const done = settledAt.get(key);
    if (done && performance.now() - done < SETTLE_MS) return Promise.resolve();
    const p = Promise.resolve()
      .then(run)
      .finally(() => {
        if (inFlight.get(key) === p) inFlight.delete(key);
        settledAt.set(key, performance.now());
      });
    inFlight.set(key, p);
    return p;
  }

  // Any mutation invalidates it outright — no waiting out the window.
  function invalidateCoalesced() {
    settledAt.clear();
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
    // With nothing stored the tuner reports the theme's own --glass-blur, so a
    // theme flip has to refresh it or it keeps showing the previous theme's.
    applyGlassSettings();
    // A settled graph map never re-ticks on its own, so a theme flip must
    // trigger one repaint to resample the token colours.
    scheduleGraphMapDraw();
  }

  function applyLiquidGlass(enabled) {
    state.liquidGlass = !!enabled;
    safeStorageSet("magi-liquid-glass", state.liquidGlass ? "true" : "false");
    document.documentElement.classList.toggle("liquid-glass-on", state.liquidGlass);
    document.documentElement.classList.toggle("no-glass", !state.liquidGlass);
    if (els.glassToggleBtn) {
      els.glassToggleBtn.classList.toggle("active", state.liquidGlass);
    }
    // Blur and opacity tune a material that is switched off in this mode, so
    // the knobs are disabled rather than left live-looking and inert. CRT
    // scanlines and the backdrop picker are unrelated to the material and stay
    // usable.
    [els.glassBlurRange, els.glassAlphaRange].forEach((el) => {
      if (el) el.disabled = !state.liquidGlass;
    });
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

  function renderBgPicker() {
    const wrap = document.getElementById("bg-thumbs");
    const note = document.getElementById("bg-picker-note");
    if (!wrap || !note) return;

    const variant = currentEvaVariant();
    const entries = (variant && bgEngine.manifest && bgEngine.manifest[variant]) || [];
    wrap.innerHTML = "";
    if (!entries.length) {
      note.textContent = t("bg_pick_none");
      return;
    }

    const picks = bgPicks(variant) || [];
    entries.forEach((entry) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "bg-thumb";
      if (entry.file === bgEngine.shown) btn.classList.add("is-showing");
      btn.setAttribute("aria-pressed", picks.indexOf(entry.file) !== -1 ? "true" : "false");
      btn.title = entry.file;
      btn.style.backgroundImage = `url("${bgEngine.baseUrl}${entry.thumb || entry.file}")`;
      btn.addEventListener("click", () => {
        const cur = bgPicks(variant) || [];
        const idx = cur.indexOf(entry.file);
        if (idx === -1) cur.push(entry.file);
        else cur.splice(idx, 1);
        setBgPicks(variant, cur);
        applyBackground("state");
        renderBgPicker();
      });
      wrap.appendChild(btn);
    });

    const n = (bgPicks(variant) || []).length;
    note.textContent = n === 0 ? t("bg_pick_auto")
      : n === 1 ? t("bg_pick_one")
      : t("bg_pick_many", { n: n });
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

  // Which artwork the user pinned for a variant, or null for "decide for me".
  // An explicit pick beats aspect matching: they asked for this image.
  function bgPicks(variant) {
    const raw = safeStorageGet("magi-bg-pick-" + variant);
    if (!raw) return null;
    try {
      const arr = JSON.parse(raw);
      return Array.isArray(arr) && arr.length ? arr : null;
    } catch (_) {
      return null;
    }
  }

  function setBgPicks(variant, files) {
    if (!files || !files.length) safeStorageRemove("magi-bg-pick-" + variant);
    else safeStorageSet("magi-bg-pick-" + variant, JSON.stringify(files));
  }

  // |log(image aspect / viewport aspect)| — 0 is a perfect fit. Anything
  // within 0.28 of the best fit competes, so similarly-cropped images
  // rotate instead of one image monopolising a viewport shape. Entries
  // without dimensions (user-supplied, no manifest) are always eligible.
  function bgEligible(variant) {
    const entries = (bgEngine.manifest && bgEngine.manifest[variant]) || [];
    if (!entries.length) return [];
    const picks = bgPicks(variant);
    if (picks) {
      // Stale picks (artwork removed from the manifest) fall through to auto
      // rather than leaving the deck blank.
      const chosen = entries.filter((e) => picks.indexOf(e.file) !== -1);
      if (chosen.length) return chosen;
    }
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
      renderBgPicker();
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

  // Returns null when the knob has never been moved, so the caller can tell
  // "unset" from "set to a value that happens to equal a default". Clamped to
  // the slider bounds: a stale or hand-edited localStorage value must never
  // drive the CSS outside what the UI can express.
  function glassSetting(key, min, max) {
    const v = parseInt(safeStorageGet(key), 10);
    if (!Number.isFinite(v)) return null;
    return Math.min(max, Math.max(min, v));
  }

  // What the CSS would use if nothing were overridden. Read back rather than
  // hardcoded because it differs per theme.
  function themeGlassBlur() {
    const v = parseInt(
      getComputedStyle(document.documentElement).getPropertyValue("--glass-blur"),
      10
    );
    return Number.isFinite(v) ? v : GLASS_DEFAULTS.blur;
  }

  function applyGlassSettings() {
    const blur = glassSetting("magi-glass-blur", 0, 30);
    const alpha = glassSetting("magi-glass-alpha", 40, 170);
    const crt = safeStorageGet("magi-crt") === "on";
    const root = document.documentElement.style;

    // Unset leaves the theme's own CSS value in place; anything stored is an
    // explicit override. No value of the slider is treated specially, so the
    // knob never moves on its own while it is being dragged.
    if (blur === null) root.removeProperty("--glass-blur");
    else root.setProperty("--glass-blur", `${blur}px`);
    if (alpha === null) root.removeProperty("--glass-alpha");
    else root.setProperty("--glass-alpha", String(alpha / 100));
    document.documentElement.classList.toggle("crt-on", crt);

    // Read the inline override back through the computed value so the readout
    // reports what is actually in force in this theme.
    const shownBlur = blur === null ? themeGlassBlur() : blur;
    const shownAlpha = alpha === null ? GLASS_DEFAULTS.alpha : alpha;
    if (els.glassBlurRange) els.glassBlurRange.value = shownBlur;
    if (els.glassAlphaRange) els.glassAlphaRange.value = shownAlpha;
    if (els.glassBlurVal) els.glassBlurVal.textContent = `${shownBlur}px`;
    if (els.glassAlphaVal) els.glassAlphaVal.textContent = `${shownAlpha}%`;
    if (els.glassCrtToggle) els.glassCrtToggle.checked = crt;
  }

  if (els.glassTunerBtn) {
    els.glassTunerBtn.addEventListener("click", () => {
      const opened = els.glassTunerPanel.classList.toggle("open");
      if (opened) renderBgPicker();
    });
  }
  const bgShuffleBtn = document.getElementById("bg-shuffle-btn");
  if (bgShuffleBtn) {
    bgShuffleBtn.addEventListener("click", () => {
      applyBackground("rotate");
      renderBgPicker();
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
      safeStorageRemove("magi-glass-blur");
      safeStorageRemove("magi-glass-alpha");
      safeStorageRemove("magi-crt");
      applyGlassSettings();
      ["blue", "red"].forEach((v) => setBgPicks(v, null));
      applyBackground("state");
      renderBgPicker();
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
      // Empty is not broken. A workspace made ninety seconds ago has nothing
      // in it because nobody has put anything in it yet, and reporting that as
      // "needs attention" told every new user their install was damaged
      // before they had a chance to do anything right.
      if (core.graph === "empty-wiki") return { cls: "state-new", stat: "STANDBY", detail };
      if (core.graph === "stale") return { cls: "state-warn", stat: "STALE", detail };
      return { cls: "state-warn", stat: "NO GRAPH", detail };
    }
    if (kind === "bal") {
      if (core.state === "disabled") return { cls: "state-off", stat: "OFFLINE", detail: "KB-ONLY PROFILE" };
      if (!core.bd_installed) return { cls: "state-err", stat: "NO ENGINE", detail: "RUN MAGI SETUP" };
      if (!core.beads_root) return { cls: "state-new", stat: "STANDBY", detail: "PM NOT INITIALIZED" };
      return {
        cls: "state-ok",
        stat: "NOMINAL",
        detail: `RDY ${core.ready ?? 0} / ACT ${core.in_progress ?? 0} / BLK ${core.blocked ?? 0}`,
      };
    }
    // casper
    if (core.state === "missing" || core.state === "offline") {
      // Same reasoning as Melchior above: an index you have not built yet is
      // a step outstanding, not a fault.
      return { cls: "state-new", stat: "NO INDEX", detail: "RUN MAGI INDEX" };
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
    "state-new": "core_state_notset",
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
      loadDocs(currentDocKey());
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
        applyFeatureGates();
        loadBalthasar();
        break;
      case "casper":
        // Search is on-demand, but the scope label is not: the KB list loads
        // before state.workspace settles, so rendering it once left "+ 4 other
        // enabled" under a picker whose library was one of the four. Same
        // shape of bug as the operations scope line.
        refreshSearchScopeLabel();
        break;
      case "radar":
        applyFeatureGates();
        loadRadar();
        break;
      case "ingest":
        loadIngest();
        break;
      case "operations":
        // Terminal stays persistent; the scope line is not — it has to follow
        // the picker like everything else.
            renderOptionalComponents();
        break;
      case "docs":
        loadDocs(currentDocKey());
        break;
    }
  }

  // ------------------------------------------------------------------------
  // Workspace & Global Status
  // ------------------------------------------------------------------------

  // Anything on screen that belongs to a specific library has to go when the
  // library changes. Search results were the loud case: the status band above
  // them flipped to "no retrieval index built" while the list below kept
  // showing the previous workspace's fully-scored hits, with nothing marking
  // them stale.
  function clearWorkspaceScopedViews() {
    state.taskStore = null;
    if (els.searchResultsList) {
      els.searchResultsList.innerHTML =
        `<p class="empty-note center mt-3">${t("search_prompt")}</p>`;
    }
    if (els.searchInfoBar) els.searchInfoBar.textContent = "";
    state.activeDigest = null;
    const preview = document.querySelector(".doc-preview-window");
    if (preview && preview.classList.contains("open")) {
      const close = document.getElementById("doc-preview-close");
      if (close) close.click();
    }
  }

  function renderWorkspaceSelect() {
    if (!els.workspaceSelect) return;
    // state.workspace wins over whatever the <select> happens to hold. Read
    // the other way round, a hub-root launch (no server-side active workspace)
    // let the empty select fall to its first alphabetical option, and the
    // dropdown then stayed on that name while every number on the page came
    // from the workspace state actually points at — the label quietly
    // describing a different library than the one on screen.
    const currentVal = state.workspace || els.workspaceSelect.value;
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

  // Written once at boot and never again, this said "Running Jobs: 1" for a
  // job that had long finished, and stayed silent for one you started
  // afterwards. It is also the only place a running job is visible from
  // another tab, so it needs to be both live and clickable.
  function setActiveJobs(n) {
    if (!els.activeJobsBadge || !els.activeJobsCount) return;
    els.activeJobsBadge.style.display = n > 0 ? "flex" : "none";
    els.activeJobsCount.textContent = n;
  }

  function updateBrowsingBadge() {
    const badge = document.getElementById("browsing-badge");
    if (!badge) return;
    // Started at a hub root, the server has no active workspace at all — so
    // whatever you are looking at, you are looking at it by choice. Requiring
    // serverWorkspace to be set meant the badge could never fire in exactly
    // the launch mode where it matters most.
    const browsing = !!state.workspace && (
      !state.serverWorkspace ||
      _normPath(state.workspace) !== _normPath(state.serverWorkspace));
    badge.style.display = browsing ? "" : "none";
  }


  // ------------------------------------------------------------------
  // Update check
  //
  // The badge is hidden unless there is something to say. `Upgrade now` is a
  // real upgrade, but it does not happen inside this server: a running
  // `magi ui` holds its own venv's python and loaded extension modules open,
  // and on Windows a package manager simply cannot replace them. So the server
  // hands the job to a detached helper that waits for it to exit, upgrades,
  // and starts the dashboard again on the same address. This page then waits
  // for it to answer and reads what happened.
  // ------------------------------------------------------------------

  let updateInfo = null;

  async function loadUpdateStatus(refresh = false) {
    try {
      updateInfo = await apiFetch("/api/update" + (refresh ? "?refresh=1" : ""));
    } catch (err) {
      updateInfo = null;
      return;
    }
    renderUpdateBadge();
  }

  function renderUpdateBadge() {
    if (!els.updateBadge) return;
    const show = !!(updateInfo && updateInfo.update_available);
    els.updateBadge.hidden = !show;
    if (show) {
      els.updateBadge.textContent = t("update_badge").replace("{v}", "v" + updateInfo.latest);
      els.updateBadge.title = t("update_title");
    }
  }

  function updateModalBody(info, extraHtml) {
    const rows = [
      [t("update_current"), "v" + escapeHtml(info.installed || "?")],
      [t("update_latest"), info.latest ? "v" + escapeHtml(info.latest) : "—"],
      [t("update_method"), escapeHtml(info.install_method || "?")],
    ];
    let html = '<table class="kv-table">' + rows.map(
      ([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${v}</td></tr>`).join("") + "</table>";

    if (!info.checked) {
      html += `<p class="muted">${escapeHtml(t("update_unreachable"))}</p>`;
    } else if (!info.update_available) {
      html += `<p>${escapeHtml(t("update_latest_already").replace("{v}", "v" + info.installed))}</p>`;
    }

    if (info.note) html += `<p class="muted">${escapeHtml(info.note)}</p>`;
    if (info.command) {
      html += `<p>${escapeHtml(t("update_run_it"))}</p>`;
      html += `<div class="update-command">${escapeHtml(info.command)}</div>`;
    }
    if (extraHtml) html += extraHtml;
    return html;
  }

  function openUpdateModal() {
    const modal = document.getElementById("update-modal");
    const body = document.getElementById("update-modal-body");
    const apply = document.getElementById("update-apply-btn");
    if (!modal || !body || !updateInfo) return;
    body.innerHTML = updateModalBody(updateInfo, "");
    if (apply) {
      const can = !!(updateInfo.can_apply && updateInfo.update_available);
      apply.hidden = !can;
      apply.disabled = false;
    }
    modal.classList.add("open");
  }

  async function recheckUpdate() {
    const body = document.getElementById("update-modal-body");
    if (body) body.innerHTML = `<p>${escapeHtml(t("update_checking"))}</p>`;
    await loadUpdateStatus(true);
    openUpdateModal();
  }

  async function applyUpdate() {
    if (!updateInfo || !updateInfo.can_apply) return;
    if (!window.confirm(t("update_confirm"))) return;

    const body = document.getElementById("update-modal-body");
    const apply = document.getElementById("update-apply-btn");
    const recheck = document.getElementById("update-recheck-btn");
    if (apply) apply.disabled = true;
    if (recheck) recheck.disabled = true;

    // Raw fetch, not apiFetch: the server shuts itself down a beat after
    // replying, so the connection dropping is the expected outcome here and
    // apiFetch would both raise it as an error and toast it at the reader. A
    // refusal that arrives *before* the shutdown is the only real failure, and
    // it needs the status code to be told apart from the drop.
    try {
      const res = await fetch("/api/update/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const data = await res.json();
          detail = data.detail || data.error || detail;
        } catch (parseErr) { /* keep the status */ }
        if (body) body.innerHTML = `<p class="error">${escapeHtml(String(detail))}</p>`;
        if (apply) apply.disabled = false;
        if (recheck) recheck.disabled = false;
        return;
      }
    } catch (err) {
      // Connection dropped: the server is going down, which is what we asked
      // for. Fall through to waiting for it to come back.
    }
    if (body) {
      body.innerHTML = `<p>${escapeHtml(t("update_started"))}</p>`
        + `<p class="muted">${escapeHtml(t("update_waiting_back"))}</p>`;
    }
    waitForServerBack();
  }

  function waitForServerBack() {
    // Poll until the relaunched dashboard answers. Deliberately long: pipx and
    // uv resolve and download before they install anything, and giving up early
    // would report a failure that has not happened.
    const deadline = Date.now() + 5 * 60 * 1000;
    const tick = async () => {
      if (Date.now() > deadline) {
        const body = document.getElementById("update-modal-body");
        if (body) {
          body.innerHTML += `<p class="error">${escapeHtml(
            t("update_failed").replace("{err}", "timeout"))}</p>`;
        }
        return;
      }
      try {
        const res = await fetch("/api/update/result", { cache: "no-store" });
        if (res.ok) {
          const data = await res.json();
          if (data && (data.state === "done" || data.state === "failed")) {
            showUpdateResult(data);
            return;
          }
        }
      } catch (err) { /* still down */ }
      setTimeout(tick, 2000);
    };
    setTimeout(tick, 3000);
  }

  function showUpdateResult(data) {
    const body = document.getElementById("update-modal-body");
    const modal = document.getElementById("update-modal");
    if (!body || !modal) return;
    modal.classList.add("open");

    let html = "";
    if (data.state === "failed") {
      html = `<p class="error">${escapeHtml(
        t("update_failed").replace("{err}", String(data.error || "")))}</p>`;
    } else if (data.changed) {
      html = `<p>${escapeHtml(t("update_done").replace("{v}", "v" + (data.now || "?")))}</p>`;
    } else {
      // A command that exits 0 is not proof: `pipx install --force` is
      // documented to print "Installing to existing venv" and keep the old
      // version. The helper re-reads the version from disk, so this branch is
      // a real outcome and not a formality.
      html = `<p class="error">${escapeHtml(
        t("update_done_unchanged").replace("{v}", "v" + (data.now || data.installed || "?")))}</p>`;
    }
    if (data.output) {
      html += `<div class="update-command">${escapeHtml(String(data.output))}</div>`;
    }
    body.innerHTML = html;
    const apply = document.getElementById("update-apply-btn");
    const recheck = document.getElementById("update-recheck-btn");
    if (apply) apply.hidden = true;
    if (recheck) recheck.disabled = false;
    fetch("/api/update/result/clear", { method: "POST" }).catch(() => {});
  }

  async function reportPreviousUpgrade() {
    // A helper that ran while this page was gone has no other way to speak.
    try {
      const res = await fetch("/api/update/result", { cache: "no-store" });
      if (!res.ok) return;
      const data = await res.json();
      if (data && (data.state === "done" || data.state === "failed")) {
        showUpdateResult(data);
      }
    } catch (err) { /* nothing to report */ }
  }

  async function loadInitialStatus() {
    try {
      const status = await apiFetch("/api/status");
      els.appVersion.textContent = `v${status.version}`;
      loadUpdateStatus();
      reportPreviousUpgrade();
      state.workspace = status.active_workspace || "";
      state.serverWorkspace = status.active_workspace || "";

      await loadKBRegistry();
      // Before any tab renders: a panel that is switched off has to come up
      // grey, not come up live and grey itself a moment later.
      await loadFeatures();

      // Restore this browser's last viewed workspace — but only when the
      // server did not answer the question itself. `magi ui` run inside a
      // workspace reports that directory as `active_workspace`, and that is
      // a deliberate act: somebody stood in a workspace and started a server
      // there. A path remembered in this browser from some previous session
      // used to win anyway, so from the second workspace onward the dashboard
      // opened on the wrong one — with notes the person had never written,
      // and a 138-row picker to find their own again.
      const savedView = viewWorkspaceGet();
      if (!state.serverWorkspace && savedView &&
          savedView !== state.workspace &&
          state.kbs.some((kb) => kb.path === savedView)) {
        state.workspace = savedView;
        renderWorkspaceSelect();
      }
      // Started at a hub root, the server reports no active workspace — but the
      // dropdown still displays a registered one. Adopt what it shows, or the
      // dashboard sits at --% / NO LINK until you re-pick the entry already on
      // screen.
      if (!state.workspace && els.workspaceSelect && els.workspaceSelect.value) {
        state.workspace = els.workspaceSelect.value;
        viewWorkspaceSet(state.workspace);
      }
      // Re-render once state.workspace has settled, so the dropdown's selected
      // option is guaranteed to name the library the rest of the page is
      // about to load. Every panel below reads state.workspace, so this is the
      // one place the label and the data can be reconciled.
      renderWorkspaceSelect();
      updateBrowsingBadge();
      setActiveJobs(status.active_jobs_count || 0);
      loadSyncRatio();
      loadTabData(state.activeTab);
    } catch (err) {
      console.error("Init status failed:", err);
    }
  }

  function loadKBRegistry() {
    return coalesce("kb", async () => {
      try {
        const data = await apiFetch("/api/kb");
        state.kbs = data.kbs || [];
        els.dashKbCount.textContent = state.kbs.length;

        renderWorkspaceSelect();
        renderKBTable(state.kbs);
        refreshSearchScopeLabel();
      } catch (err) {
        console.error("Load KBs failed:", err);
      }
    });
  }

  function loadSyncRatio() {
    if (!state.workspace) return Promise.resolve();
    return coalesce(`sync:${state.workspace}`, () => loadSyncRatioNow());
  }

  async function loadSyncRatioNow() {
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
    "pm-uninit": { i18n: "hint_pm_init", action: { type: "job", op: "pm-init", nameKey: "btn_danger_pm_init" } },
    // Two distinct codes carrying distinct counts, both rendered through one
    // generic sentence: the panel showed the same row twice, identically
    // worded, with identical buttons, and nothing to tell them apart.
    "radar-digests-pending": { i18n: "hint_radar_review", action: { type: "tab", tab: "radar" } },
    "radar-gaps-pending": { i18n: "hint_radar_gaps", action: { type: "tab", tab: "radar" } },
    // `magi radar harvest` is a whitelisted op, so there was never a reason
    // for this row to be the one that rendered raw untranslated English prose
    // in a <code> element with nothing to click. The code was simply missing
    // from this table, and from the test that is supposed to catch that.
    "radar-harvest-overdue": { i18n: "hint_radar_overdue", action: { type: "job", op: "radar-harvest", nameKey: "btn_radar_harvest" } },
    "claims-unverified": { i18n: "hint_claims_unverified", action: { type: "tab", tab: "melchior" } },
    "bd-ready": { i18n: "hint_bd_ready", action: { type: "tab", tab: "balthasar" } },
    // The panel says "click to run" and this was the one inert row — and the
    // only row a brand-new user with an inbox full of PDFs actually needs.
    // It is an agent-skill step, not a job, so it opens the chapter that
    // explains how to trigger one.
    "ingest-start": { i18n: "hint_ingest_start", action: { type: "docs", anchor: "ingest" } },
    // The step the panel never mentioned. Like ingest-start it is an
    // agent-skill step rather than a job, so it opens the chapter that
    // explains how to run one.
    "compile-pending": { i18n: "hint_compile_pending", action: { type: "docs", anchor: "compile" } },
    "beads-missing": { i18n: "hint_install_beads", action: { type: "docs", anchor: "pm" } },
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
      let labelEl = null;
      if (rule && rule.i18n) {
        labelEl = document.createElement("div");
        labelEl.className = "row-title";
        // The backend ships a count in `params`; the label used to drop it.
        labelEl.textContent = t(rule.i18n, item.params || {});
        left.appendChild(labelEl);
      }
      // The second line has to be what the button does, not what a terminal
      // user would type. These hints are written once and serve both `magi
      // sync` and this panel, so a navigation row was printing `bd ready`
      // under a button that opens a tab — reading as "press Open to run
      // this". Only a row whose button really runs a command shows one, and
      // it shows the argv the button dispatches rather than the prose.
      const runs = rule && rule.action && rule.action.type === "job";
      if (runs || !rule || !rule.action) {
        const entry = runs ? OPS_CATALOG.find((e) => e.op === rule.action.op) : null;
        const code = document.createElement("code");
        code.className = "row-code";
        code.textContent = entry ? entry.argv.join(" ") : raw;
        left.appendChild(code);
        // The same op is badged machine-wide on the operations tab. `magi pm
        // init` writes at the hub root, not in the workspace the topbar names,
        // and this row is where most people meet it first.
        if (entry && entry.scope === "global" && labelEl) {
          labelEl.insertAdjacentHTML("beforeend",
            ` <span class="badge badge-muted op-scope-badge">${escapeHtml(
              t(entry.badge_i18n || "ops_badge_global"))}</span>`);
        }
      } else {
        const dest = document.createElement("div");
        dest.className = "row-dest";
        dest.textContent = rule.action.type === "docs"
          ? t("hint_dest_docs", { name: t("tab_docs") })
          : t("hint_dest_tab", { name: t(`tab_${rule.action.tab}`) });
        left.appendChild(dest);
      }
      row.appendChild(left);
      if (rule && rule.action) {
        const btn = document.createElement("button");
        btn.className = "btn btn-secondary btn-sm";
        if (rule.action.type === "job") {
          btn.textContent = t("btn_hint_run");
          btn.addEventListener("click", () => launchJob(rule.action.op, t(rule.action.nameKey)));
        } else if (rule.action.type === "docs") {
          // Some steps are done by talking to your agent, not by pressing a
          // button here. Those get taken to the chapter that explains how,
          // rather than being left as the one row you cannot click.
          btn.textContent = t("btn_hint_howto");
          btn.addEventListener("click", () => {
            switchTab("docs");
            state.pendingDocAnchor = rule.action.anchor;
          });
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
    loadMap();
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
        // Same wrong key as the Balthasar panel had: `summary` carries the
        // engine's own `ready_issues`, so `.ready` was undefined and this card
        // read 0 on a workspace with 17 ready tasks. `counts` is normalised.
        const ready = pm.counts ? pm.counts.ready : undefined;
        if (ready !== null && ready !== undefined) {
          els.dashTaskReady.textContent = String(ready);
        } else {
          els.dashTaskReady.textContent = engineReady ? "0" : t("task_engine_offline");
        }
      } catch (_) {}

      loadConfigCard(null, "general");
    }
  }


  // ------------------------------------------------------------------------
  // v2: the map, the threads, the feed, the dump box
  //
  // These renderers draw what the server already worked out. Nothing here
  // decides anything — not which statuses a note may reach, not who may set
  // them, not what counts as stalled. All of that arrives as data from the
  // same `vocab` and `state` the CLI reads, so the dashboard and the terminal
  // cannot come to different conclusions (design-v2 D4).
  // ------------------------------------------------------------------------

  function wsQuery() {
    return `workspace=${encodeURIComponent(state.workspace || "")}`;
  }

  async function loadMap() {
    const queue = document.getElementById("queue-list");
    const lines = document.getElementById("lines-body");
    const back = document.getElementById("looking-back");
    const unfiled = document.getElementById("dump-unfiled");
    if (!queue || !lines) return;
    if (!state.workspace) return;

    let data;
    try {
      data = await apiFetch(`/api/workspace/map?${wsQuery()}`);
    } catch (err) {
      queue.innerHTML = `<p class="empty-note">${escapeHtml(err.message)}</p>`;
      return;
    }
    state.map = data;

    if (unfiled) {
      const n = (data.unfiled || []).length;
      unfiled.textContent = String(n);
      unfiled.classList.toggle("badge-terracotta", n > 0);
    }

    renderQueue(queue, data);
    renderLines(lines, data);
    renderLookingBack(back, data.retrospective || {});
    renderSpending(data.budget || {});
  }

  //: What a person can do with each kind of queue item the slow loop raises.
  //: A table rather than a key built at runtime: a concatenated key is one no
  //: checker can see. `retire` gets one verb because there is only one action
  //: — leaving the rule alone is what happens if you never press anything, and
  //: a button for that would be a button that does nothing.
  const QUEUE_VERBS = {
    proposal: [
      { verb: "accept", key: "proposal_accept" },
      { verb: "reject", key: "proposal_reject" },
      { verb: "promote", key: "proposal_promote" },
    ],
    retire: [
      { verb: "retire", key: "proposal_retire" },
    ],
  };
  const PROPOSAL_VERBS = QUEUE_VERBS.proposal;

  function renderQueue(box, data) {
    // `decisions` is the queue with WIP already dropped — that rule lives in
    // Python, where `MAP.md` applies it too. Filtering here as well would be a
    // second copy of it, and the two would disagree the first time one moved.
    const items = data.decisions || [];
    if (!items.length) {
      box.innerHTML = `<p class="empty-note">${escapeHtml(t("queue_none"))}</p>`;
      return;
    }
    box.innerHTML = "";
    items.forEach((item) => {
      const row = document.createElement("div");
      row.className = "stack-row";
      // Neither a proposal nor a retire question is a note: both carry a
      // ledger id, so rendering one as a thread link gives a person a link
      // that opens nothing. Everything else in this list is a slug.
      const verbs = QUEUE_VERBS[item.kind] || null;
      const name = verbs
        ? `<code>${escapeHtml(item.slug)}</code>`
        : `<a href="#" class="thread-link" data-slug="${escapeHtml(item.slug)}">`
          + `${escapeHtml(item.slug)}</a>`;
      const buttons = verbs
        ? `<div class="form-row">`
          + verbs.map((verb) =>
            `<button class="btn btn-secondary btn-sm proposal-btn" `
            + `data-id="${escapeHtml(item.slug)}" data-verb="${verb.verb}">`
            + `${escapeHtml(t(verb.key))}</button>`).join("")
          + `</div>`
        : "";
      row.innerHTML =
        `<div><span class="badge badge-terracotta">${escapeHtml(item.kind)}</span> `
        + name
        + `<p class="card-subtitle">${escapeHtml(item.why)}</p>${buttons}</div>`;
      box.appendChild(row);
    });
    box.querySelectorAll(".thread-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        switchTab("melchior");
        openThread(a.dataset.slug);
      });
    });
    box.querySelectorAll(".proposal-btn").forEach((btn) => {
      btn.addEventListener("click", () => decideProposal(btn.dataset.id,
                                                         btn.dataset.verb));
    });
  }

  async function decideProposal(id, verb) {
    try {
      await apiFetch("/api/workspace/proposal", {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace, id, verb }),
      });
      const named = Object.values(QUEUE_VERBS).flat()
        .find((row) => row.verb === verb);
      showToast(t("proposal_done", { verb: t(named ? named.key : "proposal_accept") }),
                "success");
      loadMap();
    } catch (err) {
      // The rule budget refuses here, and what it says names the rule to
      // retire first — so the message is the useful part.
      showToast(err.message, "error");
    }
  }

  function renderLines(body, data) {
    const rows = data.lines || [];
    if (!rows.length) {
      body.innerHTML = `<tr><td colspan="5" class="empty-cell">${escapeHtml(t("lines_none"))}</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((view) => {
      // `over_wip` and `stalled` are the server's verdicts, not ours.
      const flags = [
        view.over_wip ? `<span class="badge badge-danger">${escapeHtml(t("flag_over_wip"))}</span>` : "",
        view.stalled ? `<span class="badge badge-muted">${escapeHtml(t("flag_quiet"))}</span>` : "",
      ].filter(Boolean).join(" ");
      return `<tr>
        <td><a href="#" class="thread-link" data-slug="${escapeHtml(view.slug)}"><strong>${escapeHtml(view.slug)}</strong></a></td>
        <td>${escapeHtml(view.status || "")}</td>
        <td>${view.open_count} / ${view.total}</td>
        <td>${escapeHtml((view.last_move || "").slice(0, 10))}</td>
        <td>${flags}</td>
      </tr>`;
    }).join("");
    body.querySelectorAll(".thread-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        switchTab("melchior");
        openThread(a.dataset.slug);
      });
    });
  }

  function renderSpending(b) {
    // design-v2 §13 asks for the weekly budget to be configured in the
    // WebUI and explained when it runs out. It was configurable and never
    // shown, so the one number the configuration governs could only be
    // read by opening MAP.md or the ledger by hand.
    const box = document.getElementById("spending");
    if (!box) return;
    if (b.limit === undefined || b.limit === null) { box.innerHTML = ""; return; }
    const tone = b.over ? "badge-danger" : "badge-muted";
    box.innerHTML = `<div class="stack-row"><div>`
      + `<strong>${escapeHtml(t("dash_spending"))}</strong> `
      + `<span class="badge ${tone}">`
      + escapeHtml(t("dash_spending_line", { spent: b.spent, limit: b.limit, left: b.left }))
      + `</span></div></div>`;
  }

  function renderLookingBack(box, back) {
    if (!box) return;
    const parts = [];
    if (back.rate !== null && back.rate !== undefined) {
      parts.push(`<p><strong>${back.hits}/${back.scored}</strong> ${escapeHtml(t("back_right"))}`
        + (back.unknown ? ` · ${back.unknown} ${escapeHtml(t("back_unknown"))}` : "") + "</p>");
      parts.push("<ul>" + (back.bets || []).map((row) =>
        `<li>${row.hit ? "✓" : "✗"} <a href="#" class="thread-link" data-slug="${escapeHtml(row.slug)}">`
        + `${escapeHtml(row.slug)}</a> — `
        + escapeHtml(t("back_bet_line", { bet: row.bet, outcome: row.outcome }))
        + "</li>"
      ).join("") + "</ul>");
    } else if (back.unknown) {
      parts.push(`<p>${back.unknown} ${escapeHtml(t("back_unknown_only"))}</p>`);
    }
    if (back.late) {
      parts.push(`<p class="card-subtitle">${back.late} ${escapeHtml(t("back_late"))}</p>`);
    }
    if ((back.decisions || []).length) {
      parts.push(`<p class="card-subtitle">${escapeHtml(t("back_decisions"))}</p><ul>`
        + back.decisions.map((h) => `<li>${escapeHtml(h.replace(/^##\s*/, ""))}</li>`).join("")
        + "</ul>");
    }
    box.innerHTML = parts.length
      ? `<h4 class="card-title">${escapeHtml(t("back_title"))}</h4>` + parts.join("")
      : "";
    box.querySelectorAll(".thread-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        switchTab("melchior");
        openThread(a.dataset.slug);
      });
    });
  }

  async function submitDump() {
    const box = document.getElementById("dump-text");
    if (!box || !box.value.trim()) return;
    // Without this the post carries an empty workspace, the server falls back
    // to its own working directory, and the toast says "written down" about a
    // file on a dashboard the person is not looking at.
    if (!state.workspace) { showToast(t("need_workspace"), "error"); return; }
    try {
      const res = await apiFetch(`/api/workspace/dump`, {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace, text: box.value }),
      });
      box.value = "";
      showToast(t("dump_saved", { n: res.unfiled }), "success");
      loadMap();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // ---------------------------------------------------------------- threads

  async function loadThreads() {
    wireNewThread();
    const body = document.getElementById("threads-body");
    if (!body || !state.workspace) return;
    const kind = document.getElementById("threads-kind");
    const status = document.getElementById("threads-status");
    let qs = wsQuery();
    if (kind && kind.value) qs += `&kind=${encodeURIComponent(kind.value)}`;
    if (status && status.value) qs += `&status=${encodeURIComponent(status.value)}`;

    let data;
    try {
      data = await apiFetch(`/api/workspace/threads?${qs}`);
    } catch (err) {
      body.innerHTML = `<tr><td colspan="6" class="empty-cell">${escapeHtml(err.message)}</td></tr>`;
      return;
    }
    // The filter options are the vocabulary's, fetched with the rows, so the
    // dropdown cannot offer a status the lifecycle does not have.
    fillFilter(kind, data.kinds, "filter_all_kinds");
    const statuses = [];
    Object.keys(data.statuses || {}).forEach((k) => {
      (data.statuses[k] || []).forEach((s) => {
        if (statuses.indexOf(s) === -1) statuses.push(s);
      });
    });
    fillFilter(status, statuses, "filter_all_statuses");

    if (!data.threads.length) {
      body.innerHTML = `<tr><td colspan="6" class="empty-cell">${escapeHtml(t("threads_none"))}</td></tr>`;
      return;
    }
    body.innerHTML = data.threads.map((row) => `<tr>
      <td><a href="#" class="thread-link" data-slug="${escapeHtml(row.slug)}">
        <strong>${escapeHtml(row.title || row.slug)}</strong></a>
        <p class="card-subtitle">${escapeHtml(row.slug)}</p></td>
      <td>${escapeHtml(row.kind || "")}</td>
      <td>${escapeHtml(row.status || "")}${row.bet ? ` <span class="badge badge-muted">${escapeHtml(row.bet)}</span>` : ""}</td>
      <td>${escapeHtml((row.lines || []).join(", "))}</td>
      <td>${escapeHtml(row.tier || "")}</td>
      <td>${escapeHtml((row.last || "").slice(0, 16).replace("T", " "))}</td>
    </tr>`).join("");
    body.querySelectorAll(".thread-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        openThread(a.dataset.slug);
      });
    });
  }

  function fillFilter(select, values, allKey) {
    if (!select) return;
    const current = select.value;
    select.innerHTML = `<option value="">${escapeHtml(t(allKey))}</option>`
      + (values || []).map((v) => `<option value="${escapeHtml(v)}">${escapeHtml(v)}</option>`).join("");
    if (current) select.value = current;
  }

  async function openThread(slug) {
    const view = document.getElementById("thread-view");
    if (!view || !state.workspace) return;
    let data;
    try {
      data = await apiFetch(`/api/workspace/thread?${wsQuery()}&slug=${encodeURIComponent(slug)}`);
    } catch (err) {
      showToast(err.message, "error");
      return;
    }
    state.thread = data;
    view.style.display = "";
    document.getElementById("thread-title").textContent = data.title || data.slug;
    // `data.lines` and not `frontmatter.line`: YAML lets the author write
    // either a scalar or a list, and only the server normalises it. Joining
    // the raw field threw on every note whose `line:` was a plain string.
    document.getElementById("thread-meta").textContent =
      `${data.kind} · ${data.status} · ${data.tier || "—"} · ${(data.lines || []).join(", ")}`;
    document.getElementById("thread-body").innerHTML = renderCardMarkdown(data.body || "");

    const posts = document.getElementById("thread-posts");
    posts.innerHTML = (data.posts || []).map((post) => {
      const move = post.src && post.dst
        ? ` <span class="badge badge-terracotta">${escapeHtml(post.src)} → ${escapeHtml(post.dst)}</span>` : "";
      const set = post.field
        ? ` <span class="badge badge-muted">${escapeHtml(post.field)} = ${escapeHtml(String(post.value))}</span>` : "";
      return `<div class="stack-row"><div>
        <code>${escapeHtml(post.at)}</code> · <strong>${escapeHtml(post.host)}</strong>`
        + `${post.line ? "/" + escapeHtml(post.line) : ""}${move}${set}
        <p>${escapeHtml(post.text || "").replace(/\n/g, "<br>")}</p>
      </div></div>`;
    }).join("");

    // One button per legal move, labelled with who may make it. The list is
    // the server's; a note whose lifecycle has no exit shows no buttons.
    const moves = document.getElementById("thread-moves");
    moves.innerHTML = (data.moves || []).map((move) =>
      `<button class="btn btn-secondary btn-sm move-btn" data-dst="${escapeHtml(move.dst)}"`
      + ` title="${escapeHtml((move.writers || []).join(", "))}">`
      + `→ ${escapeHtml(move.dst)}${move.human_only ? " *" : ""}</button>`).join("");
    // The star is the server's `human_only`, and it has to say so on screen:
    // a mark whose meaning is not on the page is a mark nobody reads.
    if ((data.moves || []).some((move) => move.human_only)) {
      const note = document.createElement("span");
      note.className = "card-subtitle";
      note.textContent = t("moves_human_only");
      moves.appendChild(note);
    }
    moves.querySelectorAll(".move-btn").forEach((btn) => {
      btn.addEventListener("click", () => moveThread(data.slug, btn.dataset.dst));
    });
    // Visibly not ready, rather than pressable and inert. `moveThread`
    // refuses an empty reason and says so in a toast, but the click looks
    // dead: nothing moves, no request goes out, and a toast that has already
    // faded is indistinguishable from a broken button. The flip and the
    // sentence saying why are one action, so the control for it is not
    // available until there is a sentence.
    wireMoveGate();
    renderReviewRow(data);
    renderLineRow(data);
    renderDecideRow(data);
    view.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ---------------------------------------------------------------- review

  //: Only a proposition claiming to be solved can be reviewed — `pending()`
  //: offers nothing else, and the prompt asks whether a claim holds. Showing
  //: the button anywhere else would be a control that always refuses.
  function reviewable(data) {
    return data && data.kind === "proposition" && data.status === "supported";
  }

  function renderReviewRow(data) {
    const row = document.getElementById("thread-review-row");
    const out = document.getElementById("thread-review-out");
    if (!row) return;
    if (out) out.innerHTML = "";
    // Shown with an explanation rather than hidden. A control that is simply
    // absent reads as "this feature does not exist" — the retest concluded
    // exactly that and reported there was no way to have a claim reviewed.
    row.hidden = data.kind !== "proposition";
    if (row.hidden) return;
    const why = document.getElementById("thread-review-note");
    const button = document.getElementById("thread-review-btn");
    if (!reviewable(data)) {
      button.disabled = true;
      button.textContent = t("btn_review");
      why.textContent = t("review_only_when_supported");
      return;
    }

    const btn = document.getElementById("thread-review-btn");
    const note = document.getElementById("thread-review-note");
    btn.textContent = t("btn_review");
    btn.disabled = false;
    note.textContent = t("review_hint");
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", () => askForReview());
    }
  }

  async function askForReview() {
    if (!state.thread) return;
    const slug = state.thread.slug;
    const btn = document.getElementById("thread-review-btn");
    const out = document.getElementById("thread-review-out");

    // The plan first, always. This is the browser's `--dry-run`: a button that
    // spends money must not look like every other button, and the answer to
    // "who is this asking, and what is left of the week" has to arrive before
    // the press, not in a log afterwards.
    let plan;
    try {
      plan = await apiFetch(`/api/workspace/review/plan?workspace=`
        + encodeURIComponent(state.workspace) + `&slug=` + encodeURIComponent(slug));
    } catch (err) {
      showToast(err.message, "error");
      return;
    }
    if ((plan.refused || []).length) {
      out.innerHTML = `<p class="card-subtitle">${escapeHtml(plan.refused[0].why)}</p>`;
      return;
    }
    if (plan.enabled === false) {
      out.innerHTML = `<p class="card-subtitle">${escapeHtml(t("review_switched_off"))}</p>`;
      return;
    }
    const b = plan.budget || {};
    inlineConfirm(out, {
      body: `<p class="card-subtitle">${escapeHtml(t("review_confirm", {
        host: plan.host, model: plan.model || t("cfg_model_default"),
        left: b.left, limit: b.limit }))}</p>`,
      askReason: false,
      go: t("btn_review"),
      onGo: () => runReview(slug, plan, btn, out),
    });
  }

  async function runReview(slug, plan, btn, out) {
    btn.disabled = true;
    btn.textContent = t("btn_review_running");
    out.innerHTML = `<p class="card-subtitle">${escapeHtml(t("review_running", { host: plan.host }))}</p>`;
    try {
      const res = await apiFetch(`/api/workspace/review`, {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace, slug }),
      });
      renderVerdict(res);
      openThread(slug);
      loadMap();
      loadFeed();
    } catch (err) {
      out.innerHTML = `<p class="card-subtitle">${escapeHtml(err.message)}</p>`;
    } finally {
      btn.disabled = false;
      btn.textContent = t("btn_review");
    }
  }

  //: An in-page confirmation. `window.confirm`/`prompt` block the render
  //: thread, are invisible to anything driving the page, and — the reason
  //: that matters even when they work — cover the survey the person is
  //: supposed to be reading while they answer.
  //:
  //: `body` is trusted HTML built by the caller; `onGo` receives the typed
  //: reason, or "" when `askReason` is false.
  function inlineConfirm(box, { body, askReason, placeholder, go, onGo }) {
    box.innerHTML = body
      + (askReason
        ? `<div class="form-row"><input type="text" class="text-input grow-2"
             id="inline-why" placeholder="${escapeHtml(placeholder || "")}"></div>`
        : "")
      + `<div class="form-row">
           <button class="btn btn-primary btn-sm" id="inline-go">${escapeHtml(go)}</button>
           <button class="btn btn-quiet btn-sm" id="inline-cancel">${escapeHtml(t("btn_cancel"))}</button>
         </div>`;
    const why = box.querySelector("#inline-why");
    if (why) why.focus();
    box.querySelector("#inline-cancel").addEventListener("click", () => {
      box.innerHTML = "";
    });
    box.querySelector("#inline-go").addEventListener("click", () => {
      const text = why ? why.value.trim() : "";
      if (askReason && !text) { showToast(t("need_reason"), "error"); return; }
      onGo(text);
    });
  }

  function renderVerdict(res) {
    const out = document.getElementById("thread-review-out");
    if (!out) return;
    const tone = res.verdict === "stands" ? "badge-sage"
      : res.verdict === "refuted" ? "badge-danger" : "badge-muted";
    // `unclear` is spelled out. On the CLI it printed as one word and told the
    // reader neither what was decided nor what to do about it.
    const gloss = res.verdict === "unclear" ? `<p class="card-subtitle">${escapeHtml(t("review_unclear"))}</p>` : "";
    const b = res.budget || {};
    out.innerHTML = `
      <div class="stack-row"><div>
        <span class="badge ${tone}">${escapeHtml(res.verdict)}</span>
        <span class="card-subtitle">${escapeHtml(t("review_by", { host: res.host, model: res.model || "" }))}</span>
        ${gloss}
        <p>${escapeHtml(res.reason || "").replace(/\n/g, "<br>")}</p>
        <p class="card-subtitle">${escapeHtml(t("review_budget_left", { left: b.left, limit: b.limit }))}</p>
      </div></div>`;
  }

  function wireMoveGate() {
    const box = document.getElementById("thread-say");
    const moves = document.getElementById("thread-moves");
    if (!box || !moves) return;
    const sync = () => {
      const ready = !!box.value.trim();
      moves.querySelectorAll(".move-btn").forEach((b) => { b.disabled = !ready; });
      const hint = document.getElementById("thread-move-hint");
      if (hint) hint.textContent = ready ? "" : t("moves_need_reason_first");
    };
    if (!box.dataset.gateWired) {
      box.dataset.gateWired = "1";
      box.addEventListener("input", sync);
    }
    sync();
  }

  // ------------------------------------------------------- opening a note

  function wireNewThread() {
    const toggle = document.getElementById("thread-new-toggle");
    const form = document.getElementById("thread-new-form");
    if (!toggle || !form || toggle.dataset.wired) return;
    toggle.dataset.wired = "1";
    toggle.textContent = t("btn_thread_new");
    document.getElementById("new-submit").textContent = t("btn_open_it");
    document.getElementById("new-title").placeholder = t("new_title_ph");
    document.getElementById("new-purpose").placeholder = t("new_purpose_ph");
    document.getElementById("new-line").placeholder = t("new_line_ph");
    document.getElementById("new-hint").textContent = t("new_hint");
    const kind = document.getElementById("new-kind");
    // Written out rather than built from a prefix: a key assembled at
    // runtime cannot be checked against the dictionary, and the check exists
    // because a missing key renders as the key.
    kind.innerHTML = [
      ["proposition", t("kind_proposition")],
      ["question", t("kind_question")],
      ["line", t("kind_line")],
    ].map(([v, label]) => `<option value="${v}">${escapeHtml(label)}</option>`)
      .join("");
    toggle.addEventListener("click", () => { form.hidden = !form.hidden; });
    document.getElementById("new-submit").addEventListener("click", openNote);
  }

  async function openNote() {
    const title = document.getElementById("new-title").value.trim();
    const purpose = document.getElementById("new-purpose").value.trim();
    const line = document.getElementById("new-line").value.trim();
    if (!title || !purpose) { showToast(t("new_needs_both"), "error"); return; }
    try {
      const res = await apiFetch("/api/workspace/thread/new", {
        method: "POST",
        body: JSON.stringify({
          workspace: state.workspace,
          kind: document.getElementById("new-kind").value,
          title, purpose, lines: line ? [line] : [],
        }),
      });
      document.getElementById("new-title").value = "";
      document.getElementById("new-purpose").value = "";
      document.getElementById("thread-new-form").hidden = true;
      showToast(t("new_opened", { slug: res.slug }), "success");
      loadThreads();
      loadMap();
      openThread(res.slug);
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // ------------------------------------------- the line, and the ceremonies

  function renderLineRow(data) {
    const input = document.getElementById("thread-line-input");
    const btn = document.getElementById("thread-line-btn");
    const row = document.getElementById("thread-ceremony-row");
    if (!input || !btn) return;
    input.value = (data.lines || []).join(", ");
    input.placeholder = t("line_field_ph");
    btn.textContent = t("btn_set_line");
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", () => setThreadLines(input.value));
    }
    // Closing and publishing are about a line, so they appear on one.
    if (row) {
      row.hidden = data.kind !== "line";
      if (!row.hidden) {
        const cb = document.getElementById("thread-close-line-btn");
        const pb = document.getElementById("thread-publish-btn");
        cb.textContent = t("btn_close_line");
        pb.textContent = t("btn_publish");
        if (!cb.dataset.wired) {
          cb.dataset.wired = "1";
          cb.addEventListener("click", () => closeLineFlow(data.slug));
          pb.addEventListener("click", () => publishFlow(data.slug));
        }
      }
    }
    const out = document.getElementById("thread-ceremony-out");
    if (out) out.innerHTML = "";
  }

  function renderDecideRow(data) {
    // `/api/workspace/decide` has existed with nothing in the browser calling
    // it. An endpoint with no button is the same wall as a missing endpoint,
    // with extra steps — and this is the action that clears the debt the
    // close gate reports as "a person's call and nothing records that they
    // made it".
    const sel = document.getElementById("thread-bet");
    const btn = document.getElementById("thread-decide-btn");
    const row = document.getElementById("thread-decide-row");
    if (!sel || !btn || !row) return;
    row.hidden = data.kind === "line";
    if (row.hidden) return;
    if (!sel.options.length) {
      sel.innerHTML = [
        ["", t("bet_none")],
        ["supported", t("bet_supported")],
        ["refuted", t("bet_refuted")],
        ["unknown", t("bet_unknown")],
      ].map(([v, label]) => `<option value="${v}">${escapeHtml(label)}</option>`)
        .join("");
    }
    btn.textContent = t("btn_decide");
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", () => recordDecision(data.slug));
    }
  }

  async function recordDecision(slug) {
    const text = saidText();
    if (!text) { showToast(t("decide_needs_words"), "error"); return; }
    try {
      await apiFetch("/api/workspace/decide", {
        method: "POST",
        body: JSON.stringify({
          workspace: state.workspace, about: slug, text,
          bet: document.getElementById("thread-bet").value || null,
        }),
      });
      document.getElementById("thread-say").value = "";
      showToast(t("decided"), "success");
      openThread(slug);
      loadMap();
    } catch (err) { showToast(err.message, "error"); }
  }

  async function setThreadLines(raw) {
    const why = saidText();
    // Its own message. It used to borrow the status one — "a status change
    // needs a reason" — on a control that has nothing to do with status.
    if (!why) { showToast(t("line_needs_reason"), "error"); return; }
    const lines = raw.split(",").map((s) => s.trim()).filter(Boolean);
    try {
      await apiFetch("/api/workspace/thread/line", {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace,
                               slug: state.thread.slug, lines, text: why }),
      });
      document.getElementById("thread-say").value = "";
      // It said nothing on success, so a field that had worked and one that
      // had silently failed looked exactly the same.
      showToast(t("line_set"), "success");
      openThread(state.thread.slug);
      loadMap();
      loadThreads();
    } catch (err) { showToast(err.message, "error"); }
  }

  async function closeLineFlow(line) {
    const out = document.getElementById("thread-ceremony-out");
    let found;
    try {
      found = await apiFetch(`/api/workspace/line/close?workspace=`
        + encodeURIComponent(state.workspace) + `&line=` + encodeURIComponent(line));
    } catch (err) { showToast(err.message, "error"); return; }

    // The survey, shown before the flip. `close_cmd` exists for this: closing
    // a line with three open propositions is a decision about those three,
    // and somebody who has not been shown them has not made it.
    // The survey and the field that acts on it, on screen together. It used
    // to render this and then open a modal over it, so the list of what would
    // go quiet was behind the dialog asking whether to silence it.
    const open = found.open || [];
    inlineConfirm(out, {
      body: open.length
        ? `<p class="card-subtitle">${escapeHtml(t("close_would_silence", { n: open.length }))}</p>`
          + `<ul>${open.map((i) => `<li><code>${escapeHtml(i.slug)}</code> — ${escapeHtml(i.status)}</li>`).join("")}</ul>`
        : `<p class="card-subtitle">${escapeHtml(t("close_nothing_open"))}</p>`,
      askReason: true,
      placeholder: t("close_why_ph"),
      go: t("btn_close_line"),
      onGo: async (why) => {
        try {
          await apiFetch("/api/workspace/line/close", {
            method: "POST",
            body: JSON.stringify({ workspace: state.workspace, line,
                                   text: why, anyway: open.length > 0 }),
          });
          out.innerHTML = "";
          showToast(t("closed_line", { line }), "success");
          openThread(line);
          loadMap();
          loadThreads();
        } catch (err) {
          out.innerHTML = `<p class="card-subtitle">${escapeHtml(err.message)}</p>`;
        }
      },
    });
  }

  async function publishFlow(line) {
    const out = document.getElementById("thread-ceremony-out");
    let papers;
    try {
      papers = await apiFetch(`/api/workspace/papers?workspace=`
        + encodeURIComponent(state.workspace));
    } catch (err) { showToast(err.message, "error"); return; }
    if (!(papers.papers || []).length) {
      // Offering the way out here rather than naming a directory. Telling
      // somebody to "put the write-up in drafts/ first" is a terminal
      // instruction wearing a button.
      out.innerHTML = `<p class="card-subtitle">${escapeHtml(t("publish_no_papers"))}</p>`
        + `<div class="form-row"><input type="text" class="text-input grow-2"
             id="draft-title" placeholder="${escapeHtml(t("draft_title_ph"))}"></div>`
        + `<div class="form-row"><textarea class="text-input grow-2" rows="6"
             id="draft-body" placeholder="${escapeHtml(t("draft_body_ph"))}"></textarea></div>`
        + `<div class="form-row"><button class="btn btn-primary btn-sm"
             id="draft-save">${escapeHtml(t("btn_save_draft"))}</button></div>`;
      out.querySelector("#draft-save").addEventListener("click", async () => {
        const title = out.querySelector("#draft-title").value.trim();
        const body = out.querySelector("#draft-body").value;
        if (!title || !body.trim()) { showToast(t("draft_needs_both"), "error"); return; }
        try {
          await apiFetch("/api/workspace/draft", {
            method: "POST",
            body: JSON.stringify({ workspace: state.workspace, title, body }),
          });
          showToast(t("draft_saved"), "success");
          publishFlow(line);
        } catch (err) { showToast(err.message, "error"); }
      });
      return;
    }
    // A list, not a typed path. The browser already knows what is publishable
    // and asking somebody to spell one back is a text box standing in for it.
    inlineConfirm(out, {
      body: `<p class="card-subtitle">${escapeHtml(t("publish_which"))}</p>`
        + `<div class="form-row"><select id="publish-paper" class="text-input grow-2">`
        + papers.papers.map((p) =>
            `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("")
        + `</select></div>`,
      askReason: false,
      go: t("btn_publish_preview"),
      onGo: () => {
        const chosen = out.querySelector("#publish-paper").value;
        publishPreview(line, chosen, out);
      },
    });
  }

  async function publishPreview(line, paper, out) {
    let found;
    try {
      found = await apiFetch(`/api/workspace/publish?workspace=`
        + encodeURIComponent(state.workspace) + `&paper=` + encodeURIComponent(paper)
        + `&line=` + encodeURIComponent(line));
    } catch (err) { showToast(err.message, "error"); return; }

    const burying = found.supersede || [];
    const loose = (found.disputed || []).concat(found.unfinished || []);
    inlineConfirm(out, {
      body: `<p class="card-subtitle">${escapeHtml(t("publish_would_bury", { n: burying.length }))}</p>`
        + `<ul>${burying.map((i) => `<li><code>${escapeHtml(i.slug)}</code> — ${escapeHtml(i.status)}</li>`).join("")}</ul>`
        + (loose.length
          ? `<p class="card-subtitle">${escapeHtml(t("publish_loose_ends", { slugs: loose.join(", ") }))}</p>`
          : ""),
      askReason: true,
      placeholder: t("publish_why"),
      go: t("btn_publish"),
      onGo: async (why) => {
        try {
          await apiFetch("/api/workspace/publish", {
            method: "POST",
            body: JSON.stringify({ workspace: state.workspace, paper, lines: [line],
                                   text: why, anyway: loose.length > 0 }),
          });
          out.innerHTML = "";
          showToast(t("published"), "success");
          openThread(line);
          loadMap();
          loadThreads();
        } catch (err) {
          out.innerHTML = `<p class="card-subtitle">${escapeHtml(err.message)}</p>`;
        }
      },
    });
  }

  function saidText() {
    const box = document.getElementById("thread-say");
    return box ? box.value.trim() : "";
  }

  async function postToThread() {
    if (!state.thread) return;
    const text = saidText();
    if (!text) { showToast(t("need_words"), "error"); return; }
    try {
      await apiFetch(`/api/workspace/thread/post`, {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace, slug: state.thread.slug, text }),
      });
      document.getElementById("thread-say").value = "";
      openThread(state.thread.slug);
      loadMap();
      loadFeed();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  async function moveThread(slug, dst) {
    const text = saidText();
    if (!text) { showToast(t("need_reason"), "error"); return; }
    try {
      await apiFetch(`/api/workspace/thread/status`, {
        method: "POST",
        body: JSON.stringify({ workspace: state.workspace, slug, dst, text }),
      });
      document.getElementById("thread-say").value = "";
      openThread(slug);
      loadMap();
      loadFeed();
    } catch (err) {
      showToast(err.message, "error");
    }
  }

  // ------------------------------------------------------------------- feed

  //: How far back the feed looks. `0` means everything.
  const FEED_WINDOWS = [
    { hours: 24, key: "feed_window_24" },
    { hours: 72, key: "feed_window_72" },
    { hours: 168, key: "feed_window_168" },
    { hours: 0, key: "feed_window_0" },
  ];

  async function loadFeed() {
    const box = document.getElementById("feed-list");
    if (!box || !state.workspace) return;
    const picker = document.getElementById("feed-window");
    if (picker && !picker.options.length) {
      picker.innerHTML = FEED_WINDOWS.map((w) =>
        `<option value="${w.hours}">${escapeHtml(t(w.key))}</option>`).join("");
    }
    const window_ = picker && picker.value ? Number(picker.value) : 24;
    let data;
    try {
      data = await apiFetch(`/api/workspace/feed?${wsQuery()}`
        + (window_ ? `&window=${window_}` : "") + "&limit=100");
    } catch (err) {
      box.innerHTML = `<p class="empty-note">${escapeHtml(err.message)}</p>`;
      return;
    }
    if (!data.entries.length) {
      box.innerHTML = `<p class="empty-note">${escapeHtml(t("feed_none"))}</p>`;
      return;
    }
    box.innerHTML = data.entries.map((entry) => {
      const move = entry.src && entry.dst
        ? ` <span class="badge badge-terracotta">${escapeHtml(entry.src)} → ${escapeHtml(entry.dst)}</span>` : "";
      const first = (entry.text || "").split("\n")[0].slice(0, 160);
      return `<div class="stack-row"><div>
        <code>${escapeHtml(entry.at.slice(0, 16).replace("T", " "))}</code>
        <a href="#" class="thread-link" data-slug="${escapeHtml(entry.slug)}">${escapeHtml(entry.slug)}</a>
        · ${escapeHtml(entry.host)}${entry.line ? "/" + escapeHtml(entry.line) : ""}${move}
        <p class="card-subtitle">${escapeHtml(first)}</p>
      </div></div>`;
    }).join("");
    box.querySelectorAll(".thread-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        openThread(a.dataset.slug);
      });
    });
  }

  function bindV2() {
    const on = (id, event, fn) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener(event, fn);
    };
    on("dump-btn", "click", submitDump);
    on("dump-text", "keydown", (e) => {
      // Ctrl/Cmd+Enter files it. A thought that needs a mouse to land is a
      // thought that stays unwritten.
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") submitDump();
    });
    on("map-refresh-btn", "click", loadMap);
    on("threads-refresh-btn", "click", loadThreads);
    on("threads-kind", "change", loadThreads);
    on("threads-status", "change", loadThreads);
    on("thread-post-btn", "click", postToThread);
    on("thread-close-btn", "click", () => {
      const view = document.getElementById("thread-view");
      if (view) view.style.display = "none";
      state.thread = null;
    });
    on("feed-refresh-btn", "click", loadFeed);
    on("feed-window", "change", loadFeed);
    on("graph-map-kinds", "change", loadGraphMap);
    on("graph-map-skeleton", "change", loadGraphMap);
  }

  function renderKBTable(allKbs) {
    // Hidden, not dropped: `unregister` is a real action with its own button,
    // and a filter that removed rows for good would be a worse version of the
    // problem it exists to fix. The box only appears when it has work to do.
    const gone = allKbs.filter((kb) => kb.exists === false);
    const wrap = document.getElementById("kb-hide-gone-wrap");
    const box = document.getElementById("kb-hide-gone");
    if (wrap && box) {
      wrap.hidden = gone.length === 0;
      const label = document.getElementById("kb-hide-gone-label");
      if (label) label.textContent = t("kb_hide_gone", { n: gone.length });
    }
    const kbs = (box && box.checked && gone.length)
      ? allKbs.filter((kb) => kb.exists !== false)
      : allKbs;

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

        // `/api/kb` has always returned this and nothing read it, so a
        // directory deleted months ago drew exactly like a real workspace
        // that simply has no index yet — in the one table that is supposed
        // to answer "what is on this machine".
        const gone = kb.exists === false;

        return `
          <tr${gone ? ` class="kb-row-gone"` : ""}>
            <td>
              <strong>${escapeHtml(kb.name)}</strong>
              ${gone ? `<span class="badge badge-danger" style="margin-left: 0.4rem;">${t("badge_kb_gone")}</span>` : ""}
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
              <button class="btn btn-quiet btn-sm unreg-kb-btn" data-name="${escapeHtml(kb.name)}">${t("btn_unreg_kb")}</button>
            </td>
          </tr>
        `;
      })
      .join("");

    const hideBox = document.getElementById("kb-hide-gone");
    if (hideBox && !hideBox.dataset.wired) {
      hideBox.dataset.wired = "1";
      hideBox.addEventListener("change", () => renderKBTable(state.kbs || []));
    }

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
        viewWorkspaceSet(state.workspace);
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
          invalidateCoalesced();
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
    loadThreads();
    loadFeed();
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
      // 0/0 used to render as "100% verified", which is vacuously true and
      // reads as a lie — and it is the one place a newcomer meets the word
      // "claim" at all.
      if (!claimsData.total) {
        els.melchiorClaimsRate.textContent = t("claims_none_yet");
      } else {
        const pct = Math.round((claimsData.verified / claimsData.total) * 100);
        els.melchiorClaimsRate.textContent = t("claims_verified_rate", { rate: pct });
      }

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

  function openGraphNode(nodeId, title) {
    // Clicking a node used to swap in its link table — useful, but it answered
    // "what does this connect to" when the question is "what does it say".
    // The card opens; its links ride along in the preview sidebar.
    openDocPreview({ node: nodeId }, { title });
  }

  function openGraphLinks(nodeId) {
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
      els.graphBrowseContainer.innerHTML = "";
      els.graphBrowseContainer.appendChild(graphMissingBox(err.message));
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
      tr.title = t("preview_hint_graph");
      tr.addEventListener("click", () =>
        openGraphNode(tr.dataset.nodeId, tr.dataset.nodeTitle || ""));
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
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.id)}" ` +
        `data-node-title="${escapeHtml(r.title || r.id)}">` +
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
      (node ? `<button type="button" class="btn btn-secondary btn-sm" data-graph-read ` +
              `data-node-id="${escapeHtml(node.id)}">${t("preview_read_card")}</button>` : "") +
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
        s += `<tr class="graph-row-click" data-node-id="${escapeHtml(id)}" ` +
          `data-node-title="${escapeHtml(r.title || id)}">` +
          `<td>${escapeHtml(r.title || id)}</td>` +
          `<td><code>${escapeHtml(r.type || "")}</code></td></tr>`;
      });
      s += `</tbody></table>`;
      return s;
    };
    html += linkTable(t("graph_out"), res.outgoing || [], "out");
    html += linkTable(t("graph_in"), res.incoming || [], "in");
    els.graphBrowseContainer.innerHTML = html;
    const read = els.graphBrowseContainer.querySelector("[data-graph-read]");
    if (read) {
      read.addEventListener("click", (ev) => {
        ev.stopPropagation();
        openGraphNode(read.dataset.nodeId, nodeTitle);
      });
    }
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
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.id)}" ` +
        `data-node-title="${escapeHtml(r.title || r.id)}">` +
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
      const doc = c.doc_id
        ? `<code class="graph-row-click" data-node-id="${escapeHtml(c.doc_id)}">${escapeHtml(c.doc_id)}</code>`
        : "";
      html += `<tr><td><span class="badge ${badgeClass}">${escapeHtml(graphClaimStatusLabel(c.status))}</span></td>` +
        `<td>${escapeHtml(c.text || "")}</td>` +
        `<td>${doc}</td></tr>`;
    });
    html += `</tbody></table>`;
    els.graphBrowseContainer.innerHTML = html;
    attachGraphRowClicks();
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
      html += `<tr class="graph-row-click" data-node-id="${escapeHtml(r.source_id)}" ` +
        `data-node-title="${escapeHtml(r.source_title || r.source_id)}">` +
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
    // Its own palette, not the semantic accents. `topic` and `thesis` both
    // resolved to --accent-sage, so two legend entries drew the identical dot
    // — and there is no spare semantic accent to give thesis, because those
    // encode meaning (danger is destructive) rather than category.
    graphMap.colors = {
      concept: v("--graph-concept", "#2F5D8C"),
      reference: v("--graph-reference", "#1F7A6E"),
      topic: v("--graph-topic", "#5C7C34"),
      thesis: v("--graph-thesis", "#7A4A9E"),
      claim: v("--graph-claim", "#B5761B"),
      // `threads/` is on this map too: a proposition names the concepts it is
      // stated in terms of, so drawing the library without them draws half
      // the picture.
      proposition: v("--graph-proposition", "#C2410C"),
      question: v("--graph-question", "#4B5C6B"),
      line: v("--graph-line", "#A21C6B"),
      tag: v("--graph-tag", "#9AA0A8"),
      ghost: v("--graph-tag", "#9AA0A8"),
      // Anything the graph does not have a kind for. It used to fall back to
      // the concept colour, so 67 of 87 nodes in one real library drew as
      // concepts; a node whose kind we do not know must look unknown.
      other: v("--graph-other", "#C0554A"),
      label: v("--text-secondary", "#4A463E"),
      edge: v("--text-subtle", "#C8C4B8"),
      family: getComputedStyle(document.body).fontFamily || "sans-serif",
    };
    return graphMap.colors;
  }

  // Built from the same colour map the canvas draws with, so it can never drift
  // out of sync with what is actually on screen, and re-rendered on theme or
  // language change like everything else.
  function renderGraphLegend() {
    const box = document.getElementById("graph-map-legend");
    if (!box) return;
    const col = graphMapColors();
    const kinds = ["concept", "reference", "topic", "thesis", "claim",
                   "proposition", "question", "line", "ghost"];
    // A node kind the palette does not have. Nothing should land here now
    // that the directory decides the type, but if something does, the legend
    // has to name it rather than let it pass as whatever colour it landed on.
    const known = new Set([...kinds, "tag"]);
    const strays = graphMap.nodes.filter((n) => !known.has(n.type));
    box.innerHTML = "";
    kinds.forEach((k) => {
      if (k === "ghost" && !graphMap.nodes.some((n) => n.type === "ghost")) return;
      if (k !== "ghost" && !graphMap.nodes.some((n) => n.type === k)) return;
      const item = document.createElement("span");
      item.className = "legend-item";
      const dot = document.createElement("i");
      dot.style.background = col[k];
      item.appendChild(dot);
      item.appendChild(document.createTextNode(t(`graph_legend_${k}`)));
      box.appendChild(item);
    });
    if (graphMap.nodes.some((n) => n.type === "tag")) {
      const item = document.createElement("span");
      item.className = "legend-item";
      const dot = document.createElement("i");
      dot.style.background = col.tag;
      item.appendChild(dot);
      item.appendChild(document.createTextNode(t("graph_legend_tag")));
      box.appendChild(item);
    }
    if (strays.length) {
      const item = document.createElement("span");
      item.className = "legend-item";
      const dot = document.createElement("i");
      dot.style.background = col.other;
      item.appendChild(dot);
      const kinds_ = [...new Set(strays.map((n) => n.type))].sort().join(", ");
      item.appendChild(document.createTextNode(
        t("graph_legend_other", { kinds: kinds_ })));
      box.appendChild(item);
    }
    const size = document.createElement("span");
    size.className = "legend-item legend-note";
    size.textContent = t("graph_legend_size");
    box.appendChild(size);
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
      ctx.fillStyle = col[n.type] || col.other;
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
        ctx.strokeStyle = col[n.type] || col.other;
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
    // Draw the most-connected first and skip any label whose box would land on
    // one already drawn. Without this the densest region — which is precisely
    // the important one — stacked into an unreadable pile, so the view meant
    // to orient you failed hardest exactly where orientation matters.
    const placed = [];
    const pad = 2 / graphMap.k;
    const lineH = 12 / graphMap.k;
    const ordered = graphMap.nodes.slice().sort((a, b) => {
      const ah = hover && a.id === hover.id ? 2 : (neigh && neigh.has(a.id) ? 1 : 0);
      const bh = hover && b.id === hover.id ? 2 : (neigh && neigh.has(b.id) ? 1 : 0);
      if (ah !== bh) return bh - ah;
      return (b.degree || 0) - (a.degree || 0);
    });
    for (const n of ordered) {
      const isHover = hover && n.id === hover.id;
      const isNeigh = neigh && neigh.has(n.id);
      const show = isHover || isNeigh || (!hover && (graphMap.k >= 1.25 || (n.degree || 0) >= 4));
      if (!show) continue;
      const label = (n.title || n.id).length > 30
        ? (n.title || n.id).slice(0, 29) + "…" : (n.title || n.id);
      const w = ctx.measureText(label).width;
      const x = n.x - w / 2;
      const y = n.y + graphNodeRadius(n) + 3 / graphMap.k;
      // The hovered neighbourhood is what you asked to see — it always wins.
      const priority = isHover || isNeigh;
      if (!priority) {
        const clash = placed.some((b) =>
          x < b.x + b.w + pad && x + w + pad > b.x && y < b.y + b.h + pad && y + lineH + pad > b.y);
        if (clash) continue;
      }
      placed.push({ x, y, w, h: lineH });
      ctx.globalAlpha = isHover ? 1 : 0.72;
      ctx.fillStyle = col.label;
      ctx.fillText(label, n.x, y);
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
    const kindsEl = document.getElementById("graph-map-kinds");
    const skeletonEl = document.getElementById("graph-map-skeleton");
    const kinds = kindsEl ? kindsEl.value : "";
    const skeleton = !!(skeletonEl && skeletonEl.checked);
    const key = `${state.workspace}|${tags ? 1 : 0}|${kinds}|${skeleton ? 1 : 0}`;
    if (graphMap.key === key && graphMap.nodes.length) {
      // stopGraphMap may have frozen a mid-settle layout on tab leave —
      // resume unless the simulation had already cooled down.
      if (graphMap.sim && graphMap.sim.alpha() > graphMap.sim.alphaMin()) {
        graphMap.sim.restart();
      }
      renderGraphMapChrome();
      scheduleGraphMapDraw();
      return;
    }
    const params = new URLSearchParams({ view: "map", workspace: state.workspace });
    if (tags) params.set("tags", "true");
    if (kinds) params.set("kinds", kinds);
    if (skeleton) params.set("skeleton", "true");
    try {
      const data = await apiFetch(`/api/workspace/graph/browse?${params.toString()}`);
      // The workspace selector may have moved on while this fetch ran —
      // a stale response must not overwrite the newer dataset.
      const nowKey = `${state.workspace}|${els.graphMapTags && els.graphMapTags.checked ? 1 : 0}`
        + `|${kindsEl ? kindsEl.value : ""}|${skeletonEl && skeletonEl.checked ? 1 : 0}`;
      if (nowKey !== key) return;
      buildGraphMap(data.results || {}, key);
    } catch (err) {
      if (els.graphMapNote) {
        // The same condition, the same box. `graphMissingBox` already puts a
        // build button under this sentence elsewhere; here it was inert text,
        // so which tab you were standing on decided whether the thing the
        // sentence tells you to do was something you could do. The comment
        // above `graphMissingBox` says this was fixed once — this was the
        // third place.
        els.graphMapNote.textContent = "";
        els.graphMapNote.appendChild(graphMissingBox(err.message || ""));
        els.graphMapNote.style.display = "";
      }
    }
  }

  // Derives the corner note from graphMap state, so a language switch on a
  // cached dataset re-renders it in the new language instead of keeping the
  // old string.
  // The same condition the Dashboard offers a "Run" button for. Melchior used
  // to print the backend's own sentence — "Knowledge graph database not found
  // at D:\...\graph.db. Run 'magi graph build' first." — as inert text, so
  // one fact had two interfaces depending on which tab you happened to be on.
  function graphMissingBox(message) {
    const box = document.createElement("div");
    const missing = /graph\.db|graph build/i.test(message || "");
    box.className = missing ? "empty-note pad-1" : "error-box";
    const line = document.createElement("div");
    line.textContent = missing ? t("graph_needs_build") : message;
    box.appendChild(line);
    if (missing) {
      const btn = document.createElement("button");
      btn.className = "btn btn-primary btn-sm mt-1";
      btn.textContent = t("op_build_graph");
      btn.addEventListener("click", () =>
        launchJob("graph-build", t("op_build_graph"), null, { stay: true }));
      box.appendChild(btn);
    }
    return box;
  }

  function renderGraphMapChrome() {
    renderGraphLegend();
    renderGraphMapNote();
  }

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
    renderGraphMapChrome();
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
        if (!d.moved && d.node.type !== "ghost") openGraphNode(d.node.id, d.node.title);
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
    "ocr.mineru_api_token": "cfg_f_mineru_token",
    "radar.s2_api_key": "cfg_f_s2_api_key",
    "models.embedding": "cfg_f_models_embedding",
    "embedding.provider": "cfg_f_embedding_provider",
    "embedding.base_url": "cfg_f_embedding_base_url",
    "embedding.model": "cfg_f_embedding_model",
    "embedding.api_key": "cfg_f_embedding_api_key",
    "research.coaching": "cfg_f_coaching",
    "research.wip_limit": "cfg_f_wip_limit",
    "research.stall_days": "cfg_f_stall_days",
    "research.weekly_calls": "cfg_f_weekly_calls",
    "research.llm_calls": "cfg_f_llm_calls",
    "research.rule_budget": "cfg_f_rule_budget",
    "research.rules": "cfg_f_rules",
    "research.hosts": "cfg_f_hosts",
    "research.search_projects": "cfg_f_search_projects",
    "research.review_host": "cfg_f_review_host",
    "research.review_model": "cfg_f_review_model",
    "research.review_effort": "cfg_f_review_effort",
  };

  // `only` picks which keys a card shows: the Dashboard keeps the general
  // settings, and the radar keys render on the Literature Radar tab instead —
  // next to the numbers that make you want to change them. Noticing that the
  // relevance threshold is wrong and then hunting for it on another tab is
  // how a knob stays untouched forever.
  // Where a token comes from. Verified against each provider's own live page.
  const CFG_SIGNUP = {
    "ocr.mineru_api_token": "https://mineru.net/",
    "radar.s2_api_key": "https://www.semanticscholar.org/product/api",
    "embedding.api_key": "https://docs.siliconflow.com/",
  };

  const CFG_CHOICE_LABEL = {
    "embedding.provider=ollama": "cfg_provider_ollama",
    "embedding.provider=openai": "cfg_provider_openai",
    // Empty means "probe PATH for a CLI that is not the author", which is the
    // default and usually the right answer. An unnamed blank row in a dropdown
    // is a row nobody picks on purpose.
    "research.review_host=": "cfg_review_host_auto",
  };

  //: What each reviewer host offers, once asked. Keyed by host so switching
  //: `review_host` and switching back does not ask twice.
  const modelLists = {};

  async function hostModels(host) {
    if (!host) return null;
    if (modelLists[host]) return modelLists[host];
    try {
      const data = await apiFetch(`/api/workspace/models?host=${encodeURIComponent(host)}`);
      modelLists[host] = (data.hosts || {})[host] || null;
    } catch (err) {
      // A listing that will not load is a text box, not a broken panel.
      modelLists[host] = null;
    }
    return modelLists[host];
  }

  //: The model row, which is a dropdown only when there is something real to
  //: put in it: a pinned host that can name its models. With the host on auto
  //: the reviewer could be any vendor, and a list from one of them would be
  //: three ways to write a name the next one rejects.
  async function fillModelChoices(input, note, host) {
    const listed = host ? await hostModels(host) : null;
    if (!listed || !listed.models || !listed.models.length) {
      note.textContent = t(host ? "cfg_model_typed" : "cfg_model_pin_host");
      return;
    }
    const current = input.value;
    const select = document.createElement("select");
    select.className = "select-input cfg-input";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = listed.cheap
      ? t("cfg_model_cheap", { id: listed.cheap })
      : t("cfg_model_default");
    select.appendChild(blank);
    listed.models.forEach((m) => {
      const opt = document.createElement("option");
      opt.value = m.id;
      opt.textContent = m.label && m.label !== m.id ? `${m.label} — ${m.id}` : m.id;
      select.appendChild(opt);
    });
    // A name already in the config that the host no longer lists still has to
    // be selectable, or opening the panel would silently change the setting.
    if (current && !listed.models.some((m) => m.id === current)) {
      const kept = document.createElement("option");
      kept.value = current;
      kept.textContent = current;
      select.appendChild(kept);
    }
    select.value = current || "";
    note.textContent = listed.source === "cache" ? t("cfg_model_stale") : "";
    input.replaceWith(select);
    return select;
  }

  async function loadConfigCard(box, only) {
    box = box || document.getElementById("config-fields");
    if (!box || !state.workspace) return;
    try {
      const data = await apiFetch(`/api/workspace/config?workspace=${encodeURIComponent(state.workspace)}`);
      box.innerHTML = "";
      let fields = data.fields || [];
      if (only === "radar") fields = fields.filter((f) => f.key.startsWith("radar."));
      else if (only === "general") fields = fields.filter((f) => !f.key.startsWith("radar."));
      // Remember the lookback window so the radar tab can say "overdue".
      const daysField = (data.fields || []).find((f) => f.key === "radar.days");
      if (daysField && daysField.value) state.radarDays = daysField.value;
      fields.forEach((f) => {
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

        // Where to go and get one. A token field with no link is a dead end:
        // the reader knows what to paste and not where it comes from.
        if (CFG_SIGNUP[f.key]) {
          const link = document.createElement("a");
          link.className = "cfg-signup";
          link.href = CFG_SIGNUP[f.key];
          link.target = "_blank";
          link.rel = "noopener noreferrer";
          link.textContent = t("cfg_get_one");
          desc.appendChild(document.createTextNode(" "));
          desc.appendChild(link);
        }

        let input;
        if (f.type === "bool") {
          input = document.createElement("input");
          input.type = "checkbox";
          input.checked = !!f.value;
        } else if (f.choices) {
          input = document.createElement("select");
          input.className = "select-input cfg-input";
          f.choices.forEach((c) => {
            const opt = document.createElement("option");
            opt.value = c;
            opt.textContent = t(CFG_CHOICE_LABEL[`${f.key}=${c}`] || c) || c;
            // `String(null)` is "null", so an unset field used to match none
            // of its own options and the dropdown opened on whatever came
            // first. Unset means the empty choice, where there is one.
            if ((f.value === null || f.value === undefined ? "" : String(f.value)) === c) {
              opt.selected = true;
            }
            input.appendChild(opt);
          });
        } else {
          input = document.createElement("input");
          input.type = f.type === "secret" ? "password" : "text";
          input.className = "text-input cfg-input";
          if (f.type === "list") {
            input.value = (f.value || []).join(", ");
            input.placeholder = t("cfg_list_hint");
          } else if (f.type === "secret") {
            // The server never sends a key back, so there is nothing to
            // prefill. Say whether one is stored instead — an empty box that
            // means "already set" and an empty box that means "not set" have
            // to look different.
            input.value = "";
            input.placeholder = t(f.is_set ? "cfg_secret_set" : "cfg_secret_unset");
            input.autocomplete = "off";
          } else {
            input.value = (f.value === null || f.value === undefined) ? "" : String(f.value);
          }
        }
        row.appendChild(input);

        // Host, model, effort are one decision made in that order. The model
        // becomes a list once the host is pinned and can name its models; the
        // note under it says why it is not one when it is not.
        if (f.key === "research.review_model") {
          const note = document.createElement("div");
          note.className = "cfg-desc cfg-model-note";
          label.appendChild(note);
          const hostField = (data.fields || []).find(
            (x) => x.key === "research.review_host");
          const pinned = hostField && hostField.value ? String(hostField.value) : "";
          fillModelChoices(input, note, pinned).then((select) => {
            // Reassign, or the save button below would still be reading the
            // text box this replaced.
            if (select) input = select;
          });
        }

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
            // Saving an untouched password box would blank a stored key.
            if (f.type === "secret" && value === "") {
              showToast(t("cfg_secret_empty"), "warn");
              return;
            }
          }
          try {
            await apiFetch("/api/workspace/config", {
              method: "POST",
              body: JSON.stringify({ key: f.key, value, workspace: state.workspace }),
            });
            showToast(t("toast_cfg_saved", { key: f.key }), "success");
            if (f.type === "secret") {
              input.value = "";
              input.placeholder = t("cfg_secret_set");
            }
            // Both of these change what the rows below them may contain:
            // the provider decides which embedding fields apply, and the host
            // decides which model names are even valid.
            if (f.key === "embedding.provider" || f.key === "research.review_host") {
              loadConfigCard(box, only);
            }
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

  // Where the four numbers come from. `bd` walks up to find its database, so
  // every topic under one hub reports the same counts — three sibling topics
  // here all read 17/17 off one store at the hub root. Under a picker naming a
  // single workspace, that is a number the reader would otherwise attribute to
  // the workspace they are looking at.
  function renderTaskScope(pm) {
    const note = document.getElementById("task-scope");
    if (!note) return;
    if (!pm.store_root) {
      note.textContent = "";
      note.classList.remove("scope-shared");
      return;
    }
    note.textContent = t("bal_store_at", { root: pm.store_root });
    // Not a warning any more. The counts and the list below are both scoped
    // to this workspace, so there is nothing to warn about — only a fact
    // about where the file lives, and three words worth explaining.
    note.classList.remove("scope-shared");
    // Three words for two-and-a-half things is genuinely confusing, and this
    // line is where a reader meets all three at once.
    const help = document.createElement("button");
    help.className = "btn btn-quiet btn-sm scope-help-btn";
    help.textContent = t("scope_help_open");
    help.addEventListener("click", () => openScopeHelp());
    note.appendChild(document.createTextNode(" "));
    note.appendChild(help);
  }

  // With no task store there is nothing to count, which is not the same as
  // counting and finding none — the panel used to print a confident 0. An
  // em-dash at metric size in a tone colour reads as a decorative rule, so the
  // placeholder drops the colour and the display size along with the number.
  function setTaskCounts(counts) {
    [[els.taskReadyVal, counts.ready],
     [els.taskProgressVal, counts.in_progress],
     [els.taskBlockedVal, counts.blocked],
     [els.taskOpenVal, counts.open]].forEach(([el, v]) => {
      if (!el) return;
      const absent = (v === null || v === undefined);
      el.textContent = absent ? t("metric_not_applicable") : String(v);
      el.classList.toggle("metric-empty", absent);
    });
  }


  // ------------------------------------------------------------------------
  // The task list
  //
  // The panel used to show four numbers over a store shared by every topic
  // under the hub, so "17 ready" was a count the reader could neither open
  // nor attribute. Every issue MAGI opens carries a `topic:<workspace>`
  // label, which is what lets one shared store answer per library — and the
  // answer is usually unambiguous: all 17 here belong to one workspace.
  // ------------------------------------------------------------------------

  // A short prose explainer in a modal. The body is markdown because these
  // texts want bold and paragraphs; renderMarkdown is what the doc preview
  // already uses, so the styling is the one readers have seen.
  function showInfoModal(title, markdown) {
    const modal = document.getElementById("info-modal");
    const head = document.getElementById("info-modal-title");
    const body = document.getElementById("info-modal-body");
    if (!modal || !head || !body) return;
    head.textContent = title;
    // marked.parse, the same renderer the docs tab uses. These strings are
    // ours, from the i18n dictionary — never user input — so there is nothing
    // to sanitise beyond what marked already does.
    body.innerHTML = window.marked ? window.marked.parse(markdown)
                                   : escapeHtml(markdown);
    modal.classList.add("open");
  }

  function openScopeHelp() {
    showInfoModal(t("scope_help_title"), t("scope_help_body"));
  }

  async function loadTasks() {
    const list = document.getElementById("task-list");
    const note = document.getElementById("tasks-scope-note");
    if (!list) return;
    if (!state.workspace) { list.innerHTML = ""; return; }

    const hub = document.getElementById("tasks-show-hub");
    const closed = document.getElementById("tasks-show-closed");
    const scope = hub && hub.checked ? "hub" : "workspace";
    const qs = `workspace=${encodeURIComponent(state.workspace)}&scope=${scope}`
      + `&include_closed=${closed && closed.checked ? "true" : "false"}`;

    list.innerHTML = `<p class="empty-note">${escapeHtml(t("tasks_loading"))}</p>`;
    let data;
    try {
      data = await apiFetch(`/api/workspace/tasks?${qs}`);
    } catch (err) {
      list.innerHTML = `<p class="empty-note">${escapeHtml(err.message)}</p>`;
      return;
    }
    state.tasks = data;

    // The sentence that used to read "these numbers cover every topic under
    // the hub, not just this workspace" — true, but it left the reader to
    // work out which of the 17 were theirs. Both numbers, plainly.
    if (note) {
      const kb = (state.kbs || []).find((k) => k.path === state.workspace);
      const name = kb ? kb.name : state.workspace;
      if (!data.store_root) {
        note.textContent = t("tasks_no_store");
      } else if (data.elsewhere) {
        note.textContent = t("tasks_split", {
          here: data.here, name, elsewhere: data.elsewhere, root: data.store_root,
        });
      } else {
        note.textContent = t("tasks_all_here", { here: data.here, name });
      }
    }

    setTaskCounts(countTasks(data.tasks));

    if (!data.tasks.length) {
      list.innerHTML = `<p class="empty-note">${escapeHtml(
        data.elsewhere ? t("tasks_none_here") : t("tasks_none"))}</p>`;
      return;
    }
    list.innerHTML = "";
    data.tasks.forEach((task) => list.appendChild(taskRow(task)));
  }

  // The same rows the list renders, so the numbers above it cannot disagree
  // with what is under them. `bd status` answers for the whole hub, which is
  // a different question from the one the panel is asking.
  function countTasks(tasks) {
    const live = tasks.filter((x) => x.status !== "closed");
    return {
      ready: live.filter((x) => x.status === "open" && !x.blocked_by).length,
      in_progress: live.filter((x) => x.status === "in_progress").length,
      blocked: live.filter((x) => x.blocked_by > 0).length,
      open: live.length,
    };
  }

  function taskRow(task) {
    const row = document.createElement("div");
    row.className = "task-row";
    if (task.status === "closed") row.classList.add("task-closed");

    const main = document.createElement("div");
    main.className = "task-main";

    const head = document.createElement("div");
    head.className = "task-head";
    const status = document.createElement("span");
    status.className = `badge ${TASK_STATUS_CLASS[task.status] || "badge-muted"}`;
    status.textContent = t(TASK_STATUS_LABEL[task.status] || "task_status_open");
    head.appendChild(status);
    const title = document.createElement("span");
    title.className = "task-title";
    title.textContent = task.title || task.id;
    head.appendChild(title);
    main.appendChild(head);

    const meta = document.createElement("div");
    meta.className = "task-meta";
    const bits = [task.id];
    // Only worth saying when the list is mixing libraries; on a filtered list
    // every row would repeat the name in the header above it.
    if (state.tasks && state.tasks.scope === "hub" && task.topic) bits.push(task.topic);
    if (task.blocked_by) bits.push(t("task_blocked_by", { n: task.blocked_by }));
    if (task.blocks) bits.push(t("task_blocks", { n: task.blocks }));
    meta.textContent = bits.join(" · ");
    main.appendChild(meta);

    if (task.description) {
      const desc = document.createElement("div");
      desc.className = "task-desc";
      desc.textContent = task.description;
      main.appendChild(desc);
    }
    row.appendChild(main);

    const btns = document.createElement("div");
    btns.className = "task-btns";
    const actions = task.status === "closed"
      ? [["reopen", "task_reopen", "btn-secondary", "task_reopen_tip"]]
      : [["start", "task_start", "btn-secondary", "task_start_tip"],
         ["close", "task_close", "btn-quiet", "task_close_tip"]];
    actions.forEach(([action, key, cls, tip]) => {
      const b = document.createElement("button");
      b.className = `btn ${cls} btn-sm`;
      b.textContent = t(key);
      b.title = t(tip);
      b.addEventListener("click", () => actOnTask(task, action, b));
      btns.appendChild(b);
    });
    row.appendChild(btns);
    return row;
  }

  const TASK_STATUS_CLASS = {
    open: "badge-muted", in_progress: "badge-primary",
    blocked: "badge-danger", closed: "badge-sage",
  };
  const TASK_STATUS_LABEL = {
    open: "task_status_open", in_progress: "task_status_in_progress",
    blocked: "task_status_blocked", closed: "task_status_closed",
  };

  async function actOnTask(task, action, btn) {
    btn.disabled = true;
    try {
      await apiFetch("/api/workspace/tasks/act", {
        method: "POST",
        body: JSON.stringify({
          task_id: task.id, action, workspace: state.workspace,
        }),
      });
      showToast(t(`task_done_${action}`, { id: task.id }), "success");
    } catch (err) {
      showToast(err.message, "error");
      btn.disabled = false;
      return;
    }
    invalidateCoalesced();
    await loadTasks();
    loadBalthasar();          // the counts above the list just changed
    loadSyncRatio();
  }

  async function loadBalthasar() {
    if (!state.workspace) return;
    const tasks = featureByKey("tasks");
    if (tasks && !tasks.enabled) return;
    try {
      const pm = await apiFetch(`/api/workspace/pm?workspace=${encodeURIComponent(state.workspace)}`);
      const engineReady = (pm.task_engine_ready !== undefined ? pm.task_engine_ready : pm.beads_available);
      renderTaskScope(pm);
      if (!engineReady) {
        els.taskStatusBanner.innerHTML = `
          <div class="banner-pill warning">
            ${t("bal_engine_not_ready")}
          </div>
        `;
        setTaskCounts({});
        return;
      }
      if (!pm.counts || pm.counts.open === null || pm.counts.open === undefined) {
        // The banner used to say "click below to initialize" with nothing
        // below it to click — the actual control lives on another tab and was
        // never named. Put the button in the banner and run it from here.
        els.taskStatusBanner.innerHTML = "";
        const pill = document.createElement("div");
        pill.className = "banner-pill info banner-with-action";
        const msg = document.createElement("span");
        msg.textContent = t("bal_no_db_initialized");
        pill.appendChild(msg);
        const go = document.createElement("button");
        go.className = "btn btn-primary btn-sm";
        // This button does not create anything in the workspace named in the
        // topbar — it creates the store at the hub root, for every topic under
        // it. The same op carries a machine-wide badge on the operations tab;
        // it cannot read as a local action here and a global one there.
        go.innerHTML =
          `<span>${escapeHtml(t("btn_danger_pm_init"))}</span>` +
          ` <span class="badge badge-muted op-scope-badge">${escapeHtml(t("scope_badge_hub"))}</span>`;
        go.title = t("bal_init_writes_hub");
        go.addEventListener("click", () => {
          launchJob("pm-init", t("btn_danger_pm_init"), null, { stay: true });
        });
        pill.appendChild(go);
        const why = document.createElement("span");
        why.className = "banner-sub";
        why.textContent = t("bal_init_writes_hub");
        pill.appendChild(why);
        els.taskStatusBanner.appendChild(pill);
        setTaskCounts({});
        return;
      }

      els.taskStatusBanner.innerHTML = "";
      setTaskCounts(pm.counts);
    } catch (_) {}
    loadTasks();
  }

  // ------------------------------------------------------------------------
  // Card preview — the rendered markdown behind a node or a search hit.
  // Cards are written for a wiki, not for a terminal: they carry LaTeX, wiki
  // links and extracted figures, so a preview that showed source text would
  // be a page of $$ and [[ ]]. Everything below turns one file into a page.
  // ------------------------------------------------------------------------

  // Display environments KaTeX handles unwrapped, so a card may write
  // \begin{align}…\end{align} with no surrounding $$.
  const MATH_ENVS = [
    "align", "aligned", "alignat", "equation", "gather", "gathered",
    "multline", "split", "cases", "eqnarray", "array",
    "matrix", "pmatrix", "bmatrix", "vmatrix", "Vmatrix", "Bmatrix",
  ];

  // A delimiter someone forgot to close would otherwise pair with the next
  // one hundreds of lines later and swallow the document whole. The longest
  // real formula across 35 000 slots of the corpus is 1 940 characters.
  const MATH_SPAN_CAP = 6000;

  // One pass that recognises what math must NOT be pulled out of (fenced
  // blocks, inline code) alongside what IS math or a wikilink. Alternation
  // order is precedence, and code comes first: `$x$` in a snippet is a
  // snippet. Pulling math out before marked sees it is the whole point —
  // otherwise `a_1 \ldots b_2` comes back as italics.
  const MD_TOKEN = new RegExp([
    // A closing fence carries no info string (CommonMark), so an inner
    // ```mermaid is content — treating it as the closer ended the block
    // early and disagreed with marked's own lexer about what is code.
    // \r is in the trailing class because the corpus is CRLF and a closer
    // that stops at the \r matches nothing at all.
    "(^|\\n)(```|~~~)[\\s\\S]*?(?:\\n\\2[ \\t\\r]*(?=\\n|$)|$)",
    "`[^`\\n]*`",
    // Order matters: nearest closer first (same line, then any body with no
    // paragraph break in it); only a body that spans a blank line goes hunting
    // for a closer that begins a line. Put the line-anchored form first and it
    // steps straight over the real closer of `$$\begin{array}...\end{array}$$`.
    "\\$\\$[^\\n]{1," + MATH_SPAN_CAP + "}?\\$\\$",
    "\\$\\$(?:[^\\n$]|\\n(?![ \\t\\r]*\\n)|\\$(?!\\$)){1," + MATH_SPAN_CAP + "}?\\$\\$",
    "\\$\\$[\\s\\S]{1," + MATH_SPAN_CAP + "}?\\n[ \\t\\r]*\\$\\$",
    "\\\\\\[[\\s\\S]{1," + MATH_SPAN_CAP + "}?\\\\\\]",
    "\\\\\\([\\s\\S]{1," + MATH_SPAN_CAP + "}?\\\\\\)",
    "\\\\begin\\{(" + MATH_ENVS.join("|") + ")(\\*?)\\}[\\s\\S]*?\\\\end\\{\\3\\4\\}",
    "\\$(?:[^$\\\\\\n]|\\\\.)+?\\$",
    "\\[\\[[^\\[\\]\\n]+\\]\\]",
  ].join("|"), "g");

  const SLOT_RE = /@@MAGIMD(\d+)@@/g;

  // Bare structural tags a compiled card legitimately uses — <details> wraps
  // the mermaid figures the ingest pipeline writes, and escaping those left
  // "<details> <summary>flowchart</summary>" sitting in the prose as text.
  //
  // Applied by escaping the whole fragment and then putting these back, NOT
  // by scanning it for tags to keep. A scanner cannot see `<img src=x
  // onerror=... <br>>` for what it is: it locks onto the inner <br>, the
  // surrounding pieces never form a <...> pair of their own, and a live
  // <img onerror> reaches innerHTML. Cards are compiled from other people's
  // PDFs, so that is a real path in.
  const SAFE_TAG = /&lt;(\/?)(details|summary|br|sub|sup|mark|kbd|small|u)\s*(\/?)&gt;/gi;
  // The <p> carries data-src-line by the time this runs, so it is never bare.
  const SLOT_BLOCK_RE = /<p( [^>]*)?>\s*@@MAGIMD(\d+)@@\s*<\/p>/g;

  function protectTokens(src) {
    const slots = [];
    const text = src.replace(MD_TOKEN, (m, nl, fence, env) => {
      if (fence !== undefined || m.charCodeAt(0) === 96) return m;   // code, untouched
      let entry;
      if (env !== undefined) entry = { kind: "math", tex: m, display: true };
      else if (m.startsWith("$$")) entry = { kind: "math", tex: m.slice(2, -2), display: true };
      else if (m.startsWith("\\[")) entry = { kind: "math", tex: m.slice(2, -2), display: true };
      else if (m.startsWith("\\(")) entry = { kind: "math", tex: m.slice(2, -2), display: false };
      else if (m.startsWith("[[")) {
        const body = m.slice(2, -2);
        const bar = body.indexOf("|");
        entry = {
          kind: "link",
          target: (bar < 0 ? body : body.slice(0, bar)).trim(),
          label: (bar < 0 ? body : body.slice(bar + 1)).trim(),
        };
      } else {
        const body = m.slice(1, -1);
        // "$12 and $15 each" is money, not math: real inline math never opens
        // or closes against whitespace.
        if (!body.trim() || /^\s|\s$/.test(body)) return m;
        entry = { kind: "math", tex: body, display: false };
      }
      // A five-line $$…$$ collapses to a one-line placeholder; the line
      // bookkeeping below has to add those lines back.
      entry.nl = (m.match(/\n/g) || []).length;
      slots.push(entry);
      return `@@MAGIMD${slots.length - 1}@@`;
    });
    return { text, slots };
  }

  function normalizeTex(tex, display) {
    // \label and \nonumber belong to a numbering system KaTeX does not have,
    // and eqnarray it refuses outright — both arrive constantly from OCR'd
    // papers, and both are one substitution away from rendering.
    let out = tex.replace(/\\(?:label|nonumber)\s*(?:\{[^}]*\})?/g, "");
    if (!display) {
      // \tag is a display-mode construct; KaTeX rejects the whole formula
      // when it shows up inline, which is most of what it ever rejects here.
      out = out.replace(/\\tag\*?\s*\{[^}]*\}/g, "");
    }
    if (/\\begin\{eqnarray\*?\}/.test(out)) {
      out = out
        .replace(/\\(begin|end)\{eqnarray\*?\}/g, "\\$1{aligned}")
        // a &=& b -> a &= b. The relation may itself be a command
        // (a &\overset{def}{=}& b), so backslashes have to be allowed here.
        .replace(/&\s*([^&\n]*?)\s*&/g, "&$1");
    }
    return out;
  }

  function renderTex(entry) {
    if (!window.katex) {
      const d = entry.display ? "$$" : "$";
      return `<code class="math-raw">${escapeHtml(d + entry.tex + d)}</code>`;
    }
    try {
      return window.katex.renderToString(normalizeTex(entry.tex, entry.display), {
        displayMode: entry.display,
        throwOnError: false,   // a broken formula shows in red, not as a blank card
        strict: false,
        trust: false,
      });
    } catch (_) {
      return `<code class="math-raw">${escapeHtml(entry.tex)}</code>`;
    }
  }

  function slotHtml(entry) {
    if (!entry) return "";
    if (entry.kind === "link") {
      return `<a href="#" class="wikilink" data-wikilink="${escapeHtml(entry.target)}">` +
        `${escapeHtml(entry.label || entry.target)}</a>`;
    }
    // Not typeset yet — a 760 KB paper holds five thousand formulas, and
    // KaTeX-ing all of them up front is 15 MB of DOM and thirteen seconds
    // before the reader sees anything. The slot carries its own source, so it
    // is roughly the right size while it waits and still legible if the
    // typesetting never happens.
    return `<span class="math-lazy${entry.display ? " math-lazy-block" : ""}"` +
      `${entry.display ? ' data-d="1"' : ""}>${escapeHtml(entry.tex)}</span>`;
  }

  function typesetMath(node) {
    const entry = { tex: node.textContent, display: node.dataset.d === "1" };
    node.outerHTML = renderTex(entry);
  }

  // Under this many formulas, typeset everything before the first paint: the
  // flash of raw TeX is not worth saving milliseconds an ordinary card does
  // not spend.
  const MATH_EAGER_LIMIT = 400;

  // How far outside the pane still counts as "about to be read".
  const MATH_MARGIN = 1500;

  function hydrateMath(root) {
    const slots = [...root.querySelectorAll(".math-lazy")];
    preview.pending = [];
    if (!slots.length) return false;
    if (slots.length <= MATH_EAGER_LIMIT) {
      slots.forEach(typesetMath);
      return false;
    }
    // Headings are few and their text becomes the outline, so they never
    // wait — a sidebar entry reading "\mathfrak{C}(D, p)" helps nobody.
    const inHeadings = new Set(
      root.querySelectorAll("h1 .math-lazy, h2 .math-lazy, h3 .math-lazy, h4 .math-lazy"));
    inHeadings.forEach(typesetMath);
    preview.pending = slots.filter((n) => !inHeadings.has(n));
    typesetNearViewport();
    return true;
  }

  /** Typeset the formulas near the pane, leave the rest as source.
   *
   * Deliberately not an IntersectionObserver: those only fire while the tab
   * is rendering, so a preview opened in a background tab would sit there
   * showing raw TeX forever. This runs off the scroll handler instead, which
   * is driven by something the reader actually did.
   */
  function typesetNearViewport() {
    const pending = preview.pending;
    if (!pending || !pending.length) return;
    const pane = els.docPreviewContent.getBoundingClientRect();
    const top = pane.top - MATH_MARGIN;
    const bottom = pane.bottom + MATH_MARGIN;

    // Read every rect first, then write: interleaving them would force a
    // fresh layout for each of several thousand nodes.
    const rects = pending.map((n) => (n.isConnected ? n.getBoundingClientRect() : null));
    const due = [];
    const left = [];
    pending.forEach((node, i) => {
      const r = rects[i];
      if (!r) return;
      if (r.bottom >= top && r.top <= bottom) due.push(node);
      else left.push(node);
    });
    preview.pending = left;
    due.forEach(typesetMath);
    // Typesetting moved everything below it; one more pass catches what just
    // slid into range.
    if (due.length && left.length) requestAnimationFrame(typesetNearViewport);
  }

  function splitFrontMatter(md) {
    const m = /^---\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(md || "");
    // `offset` is how many file lines the body starts below line 1. The
    // retrieval index numbers its chunks against the whole file, front matter
    // included, so every line the preview reports has to add it back.
    if (!m) return { front: "", body: md || "", offset: 0 };
    return {
      front: m[1],
      body: (md || "").slice(m[0].length),
      offset: (m[0].match(/\n/g) || []).length,
    };
  }

  function frontField(front, key) {
    const m = new RegExp(`^${key}\\s*:\\s*(.+)$`, "mi").exec(front || "");
    return m ? m[1].trim().replace(/^["']|["']$/g, "") : "";
  }

  function renderCardMarkdown(md, lineOffset = 0) {
    if (!window.marked) return `<pre>${escapeHtml(md)}</pre>`;
    const { text, slots } = protectTokens(md);
    const renderer = new window.marked.Renderer();
    // Cards are compiled from OCR'd papers: stray angle brackets are routine,
    // and real HTML has no business executing inside the dashboard.
    renderer.html = (tok) => {
      const raw = typeof tok === "string" ? tok : (tok.raw || tok.text || "");
      return escapeHtml(raw).replace(
        SAFE_TAG, (m, close, name, slash) => `<${close}${name.toLowerCase()}${slash}>`);
    };
    // The ingest pipeline writes figures as ```mermaid fences. Left as code
    // they are a wall of `style A fill:#f9f` where a diagram belongs.
    const codeRenderer = renderer.code.bind(renderer);
    renderer.code = (tok) => {
      const lang = (typeof tok === "object" && (tok.lang || "")) || "";
      if (lang.trim().split(/\s+/)[0].toLowerCase() === "mermaid") {
        return `<pre class="mermaid">${escapeHtml(tok.text || "")}</pre>\n`;
      }
      return codeRenderer(tok);
    };

    // Block by block rather than in one parse, so every top-level element can
    // carry the source line it came from. A search hit knows the lines of the
    // passage that matched, and without this map the preview could only ever
    // open at the top of a forty-page paper.
    let html = "";
    try {
      const tokens = window.marked.lexer(text);
      let line = 1 + lineOffset;
      for (const tok of tokens) {
        const start = line;
        let spans = (tok.raw.match(/\n/g) || []).length;
        for (const slot of tok.raw.matchAll(SLOT_RE)) {
          spans += (slots[+slot[1]] && slots[+slot[1]].nl) || 0;
        }
        line += spans;
        const one = [tok];
        one.links = tokens.links;   // reference-style links live on the array
        html += window.marked.parser(one, { renderer })
          .replace(/^(\s*)<([a-zA-Z][\w-]*)/, `$1<$2 data-src-line="${start}"`);
      }
    } catch (_) {
      // Any lexer surprise: a plain parse still reads, just without the map.
      html = window.marked.parse(text, { renderer });
    }
    // A display formula that owns its paragraph gets a block of its own —
    // .katex-display is block-level, and a block inside a <p> lays out with
    // the paragraph's margins fighting it. The line stamp moves across.
    html = html.replace(SLOT_BLOCK_RE, (m, attrs, i) => {
      const entry = slots[+i];
      if (!entry || entry.kind !== "math" || !entry.display) return m;
      return `<div${attrs || ""} class="math-block">${slotHtml(entry)}</div>`;
    });
    return html.replace(SLOT_RE, (m, i) => slotHtml(slots[+i]));
  }

  /** Mermaid is 2.7 MB; it loads the first time a card actually has a
      diagram in it, and never on a dashboard that only shows tables. */
  function loadMermaid() {
    if (loadMermaid._p) return loadMermaid._p;
    loadMermaid._p = new Promise((resolve) => {
      const el = document.createElement("script");
      el.src = "/vendor/mermaid.min.js";
      el.onload = () => resolve(window.mermaid || null);
      el.onerror = () => resolve(null);
      document.head.appendChild(el);
    }).then((m) => {
      if (m) {
        // A light theme in every MAGI theme, on purpose: these diagrams carry
        // their own `style A fill:#f9f` from the paper, and a dark theme puts
        // pale label text on those pale fills. The CSS gives the figure a
        // light plate to sit on, the way it sat on the page it came from.
        m.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "neutral",
        });
      }
      return m;
    });
    return loadMermaid._p;
  }

  async function renderPreviewDiagrams(root) {
    const all = [...root.querySelectorAll("pre.mermaid")];
    if (!all.length) return;
    // A diagram inside a collapsed <details> would lay out at zero width, so
    // it waits for the reader to open it.
    const ready = [];
    all.forEach((node) => {
      const box = node.closest("details");
      if (box && !box.open) {
        box.addEventListener("toggle", function once() {
          box.removeEventListener("toggle", once);
          if (box.open) drawDiagrams([node]);
        });
        return;
      }
      ready.push(node);
    });
    drawDiagrams(ready);
  }

  async function drawDiagrams(nodes) {
    if (!nodes.length) return;
    const m = await loadMermaid();
    if (!m) return;
    try {
      await m.run({ nodes, suppressErrors: true });
    } catch (_) {
      // Leave the source visible; a diagram that will not parse is still
      // readable as text.
    }
  }

  function resolveCardAssets(root, docPath, kb) {
    const dir = docPath.includes("/") ? docPath.slice(0, docPath.lastIndexOf("/")) : "";
    const owner = kb && kb !== "local"
      ? `&kb=${encodeURIComponent(kb)}`
      : `&workspace=${encodeURIComponent(state.workspace)}`;
    root.querySelectorAll("img").forEach((img) => {
      const src = img.getAttribute("src") || "";
      if (!src || /^(https?:|data:|\/)/i.test(src)) return;
      let rel = (dir ? dir + "/" : "") + src.replace(/^\.\//, "");
      // Markdown escapes spaces in image paths; encoding that again turns
      // %20 into %2520 and every figure 404s.
      try { rel = decodeURIComponent(rel); } catch (_) { /* literal % */ }
      img.src = `/api/workspace/asset?path=${encodeURIComponent(rel)}` + owner;
      img.addEventListener("error", () => { img.classList.add("img-missing"); });
    });
  }

  // ---- the modal ---------------------------------------------------------

  const preview = {
    stack: [], current: null, tocHtml: "", headings: [],
    scrollTarget: null, pending: [],
  };

  const PREVIEW_FULLSCREEN_KEY = "magi.preview.fullscreen";

  function previewWindow() {
    return els.docPreviewModal
      ? els.docPreviewModal.querySelector(".doc-preview-window") : null;
  }

  function isPreviewFullscreen() {
    const win = previewWindow();
    return !!(win && win.classList.contains("fullscreen"));
  }

  function setPreviewFullscreen(on, remember = true) {
    const win = previewWindow();
    if (!win) return;
    win.classList.toggle("fullscreen", !!on);
    const btn = els.docPreviewFullscreen;
    if (btn) {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      // The glyph changes with the state, so the button says what it will do
      // next rather than what is currently true.
      btn.innerHTML = on ? "&#11034;" : "&#11036;";
      // Swap the i18n *key*, not just the rendered string: the language
      // switcher re-reads `data-i18n-title` for every element, so setting only
      // `title` would put the wrong label back the moment somebody changes
      // language while full screen is on.
      const key = on ? "preview_fullscreen_exit" : "preview_fullscreen";
      btn.setAttribute("data-i18n-title", key);
      btn.title = t(key);
    }
    if (!remember) return;
    // A per-viewer convenience, so it survives a reload. Wrapped because a
    // browser with site data blocked throws on access rather than returning
    // nothing, and a reading pane must not fail to open over a preference.
    try {
      localStorage.setItem(PREVIEW_FULLSCREEN_KEY, on ? "1" : "0");
    } catch (err) { /* not important enough to report */ }
  }

  function preferredPreviewFullscreen() {
    try {
      return localStorage.getItem(PREVIEW_FULLSCREEN_KEY) === "1";
    } catch (err) {
      return false;
    }
  }

  function closeDocPreview() {
    if (!els.docPreviewModal) return;
    els.docPreviewModal.classList.remove("open");
    els.docPreviewContent.innerHTML = "";
    preview.stack = [];
    preview.current = null;
  }

  /** ref: {node} or {path}. opts: {title, heading, push} */
  function openDocPreview(ref, opts = {}) {
    if (!els.docPreviewModal || !state.workspace) return;
    if (opts.push && preview.current) preview.stack.push(preview.current);
    else if (!opts.keepStack) preview.stack = [];
    preview.current = { ref, opts };
    els.docPreviewModal.classList.add("open");
    // Reopening honours the last choice: somebody who reads cards full screen
    // is not asking to be put back in a box on the next card.
    setPreviewFullscreen(preferredPreviewFullscreen(), false);
    // A class, not style.display: the base rule hides the button, so clearing
    // the inline style would put it right back to hidden.
    els.docPreviewBack.classList.toggle("show", preview.stack.length > 0);
    els.docPreviewLinksBtn.style.display = ref.node ? "" : "none";
    els.docPreviewTitle.textContent = opts.title || ref.node || ref.path || "";
    els.docPreviewMeta.textContent = "";
    els.docPreviewSide.innerHTML = "";
    preview.tocHtml = "";
    preview.headings = [];
    preview.scrollTarget = null;
    preview.pending = [];
    setPreviewSideVisible(false);
    els.docPreviewContent.innerHTML = `<p class="empty-note">${t("preview_loading")}</p>`;
    els.docPreviewContent.scrollTop = 0;
    loadDocPreview(ref, opts);
  }

  async function loadDocPreview(ref, opts) {
    const token = ++loadDocPreview._req;
    const qs = new URLSearchParams({ workspace: state.workspace });
    if (ref.kb && ref.kb !== "local") qs.set("kb", ref.kb);
    if (ref.node) qs.set("node", ref.node);
    else qs.set("path", ref.path);

    let data;
    try {
      data = await apiFetch(`/api/workspace/doc?${qs.toString()}`);
    } catch (err) {
      if (token !== loadDocPreview._req) return;
      els.docPreviewContent.innerHTML =
        `<div class="error-box">${escapeHtml(localizeApiError(err.message))}</div>`;
      return;
    }
    if (token !== loadDocPreview._req) return;

    const node = data.node || {};
    const { front, body, offset } = splitFrontMatter(data.content || "");
    const title = node.title || frontField(front, "title") || opts.title || data.path;
    els.docPreviewTitle.textContent = title;

    const bits = [];
    const type = node.type || frontField(front, "type");
    if (type) bits.push(`<span class="badge badge-muted">${escapeHtml(graphTypeLabel(type))}</span>`);
    bits.push(`<code class="doc-preview-path">${escapeHtml(data.path)}</code>`);
    if (data.modified) bits.push(`<span>${escapeHtml(data.modified.replace("T", " "))}</span>`);
    if (data.truncated) bits.push(`<span class="badge badge-terracotta">${t("preview_truncated")}</span>`);
    els.docPreviewMeta.innerHTML = bits.join("");

    els.docPreviewContent.innerHTML = renderCardMarkdown(body, offset);
    if (!window.katex) {
      // Without KaTeX the formulas stay as source; say so rather than let the
      // reader think the card is written that way.
      els.docPreviewContent.insertAdjacentHTML(
        "afterbegin", `<div class="hint-note">${t("preview_math_off")}</div>`);
    }
    resolveCardAssets(els.docPreviewContent, data.path, ref.kb);
    decorateCodeBlocks(els.docPreviewContent);
    renderPreviewDiagrams(els.docPreviewContent);
    els.docPreviewContent.scrollTop = 0;
    // Hydration first: the outline is read out of the headings, and a heading
    // still holding raw TeX would put "\mathfrak{C}(D, p)" in the sidebar.
    const lazy = hydrateMath(els.docPreviewContent);
    preview.tocHtml = buildPreviewToc();
    els.docPreviewSide.innerHTML = preview.tocHtml;
    setPreviewSideVisible(Boolean(preview.tocHtml));
    // Lines are exact; a heading match is the fallback for a hit whose chunk
    // began mid-section, or a document with no line map.
    if (!(opts.line && scrollPreviewToLine(opts.line)) && opts.heading) {
      highlightPreviewHeading(opts.heading);
    }
    if (lazy) settlePreviewScroll();
    syncPreviewSpy();

    // Remember what the server actually resolved: a wikilink opened by title
    // becomes a node id here, and `path` is what relative links resolve from.
    const nodeId = (ref.kb && ref.kb !== "local") ? null : (node.id || ref.node);
    preview.current = {
      ref: { ...ref, ...(nodeId ? { node: nodeId } : {}), path: data.path },
      opts: { ...opts, title },
    };
    if (nodeId) loadPreviewLinks(nodeId, token);
  }
  loadDocPreview._req = 0;

  /** A heading's text as a reader sees it.
      KaTeX renders each formula twice — MathML for screen readers plus the
      visual HTML — so textContent on a heading with inline math comes back
      tripled ("C(D,p)\mathfrak{C}(D,p)C(D,p)"). */
  function headingText(h) {
    const clone = h.cloneNode(true);
    clone.querySelectorAll(".katex-mathml").forEach((n) => n.remove());
    return clone.textContent.replace(/\s+/g, " ").trim();
  }

  function scrollPreviewTo(el) {
    // scrollIntoView would move the modal inside the viewport; the content
    // pane is the only thing that should scroll.
    els.docPreviewContent.scrollTop =
      el.offsetTop - els.docPreviewContent.offsetTop - 8;
  }

  /** Land on the passage the search matched, not on line 1. */
  function scrollPreviewToLine(line) {
    const blocks = [...els.docPreviewContent.querySelectorAll("[data-src-line]")];
    if (!blocks.length) return false;
    let target = blocks[0];
    for (const b of blocks) {
      if (Number(b.dataset.srcLine) <= line) target = b;
      else break;
    }
    target.classList.add("doc-preview-hit");
    preview.scrollTarget = target;
    scrollPreviewTo(target);
    return true;
  }

  /** Typesetting changes the height of everything above the target, so the
      first scroll only lands approximately. Re-apply it as the page settles. */
  function settlePreviewScroll() {
    const target = preview.scrollTarget;
    if (!target) return;
    let left = 6;
    const again = () => {
      if (!preview.scrollTarget || preview.scrollTarget !== target) return;
      if (!target.isConnected) return;
      typesetNearViewport();
      scrollPreviewTo(target);
      if (--left > 0) setTimeout(again, 120);
    };
    setTimeout(again, 60);
  }

  function highlightPreviewHeading(heading) {
    const want = String(heading).trim().toLowerCase();
    const hs = els.docPreviewContent.querySelectorAll("h1, h2, h3, h4, h5, h6");
    for (const h of hs) {
      if (headingText(h).toLowerCase() === want) {
        h.classList.add("doc-preview-hit");
        preview.scrollTarget = h;
        scrollPreviewTo(h);
        return;
      }
    }
  }

  /** The card's own headings, as a navigable outline. Papers run to dozens of
      screens; scrolling blind through one is not reading it. */
  function buildPreviewToc() {
    preview.headings = [];
    const hs = [...els.docPreviewContent.querySelectorAll("h1, h2, h3, h4")];
    // One heading is a title, not an outline.
    if (hs.length < 2) return "";
    let html = `<div class="doc-preview-side-head">${escapeHtml(t("preview_contents"))}</div>` +
      `<ul class="doc-preview-toc">`;
    hs.forEach((h, i) => {
      const id = `magi-h${i}`;
      h.id = id;
      html += `<li><button type="button" class="doc-preview-toc-link lv${h.tagName[1]}" ` +
        `data-toc="${id}">${escapeHtml(headingText(h))}</button></li>`;
      preview.headings.push({ el: h, id });
    });
    return html + `</ul>`;
  }

  function syncPreviewSpy() {
    if (!preview.headings.length) return;
    const top = els.docPreviewContent.scrollTop + els.docPreviewContent.offsetTop + 16;
    let active = preview.headings[0];
    for (const h of preview.headings) {
      if (h.el.offsetTop <= top) active = h;
      else break;
    }
    els.docPreviewSide.querySelectorAll("[data-toc]").forEach((b) =>
      b.classList.toggle("active", b.dataset.toc === active.id));
  }

  function onPreviewScroll() {
    if (onPreviewScroll._q) return;
    onPreviewScroll._q = true;
    requestAnimationFrame(() => {
      onPreviewScroll._q = false;
      typesetNearViewport();
      syncPreviewSpy();
    });
  }

  async function loadPreviewLinks(nodeId, token) {
    const qs = new URLSearchParams({
      view: "links", node: nodeId, workspace: state.workspace,
    });
    let res;
    try {
      res = await apiFetch(`/api/workspace/graph/browse?${qs.toString()}`);
    } catch (_) {
      return;   // no graph, no sidebar — the card still reads fine
    }
    if (token !== loadDocPreview._req) return;
    const data = res.results || {};
    const group = (label, rows, key) => {
      if (!rows || !rows.length) return "";
      let s = `<div class="doc-preview-side-head">${escapeHtml(label)}</div><ul class="doc-preview-side-list">`;
      rows.forEach((r) => {
        const id = r[key];
        const dangling = key === "target_id" && (r.title === null || r.title === undefined);
        // A dangling target gets the same type as its siblings — it is the
        // colour that says "nothing behind this yet", not a change of face.
        s += dangling
          ? `<li><span class="doc-preview-jump is-dangling" ` +
            `title="${escapeHtml(t("preview_unresolved"))}">${escapeHtml(id)}</span></li>`
          : `<li><button type="button" class="doc-preview-jump" data-node="${escapeHtml(id)}">` +
            `${escapeHtml(r.title || id)}</button></li>`;
      });
      return s + `</ul>`;
    };
    const links = group(t("preview_out"), data.outgoing, "target_id") +
      group(t("preview_in"), data.incoming, "source_id");
    els.docPreviewSide.innerHTML = preview.tocHtml +
      (links || `<p class="empty-note">${t("preview_no_links")}</p>`);
    setPreviewSideVisible(true);
    syncPreviewSpy();
  }

  function setPreviewSideVisible(on) {
    const body = els.docPreviewSide && els.docPreviewSide.parentElement;
    if (body) body.classList.toggle("no-side", !on);
  }

  function previewGoBack() {
    const prev = preview.stack.pop();
    if (!prev) return;
    preview.current = null;
    openDocPreview(prev.ref, { ...prev.opts, push: false, keepStack: true });
  }

  function bindDocPreview() {
    if (!els.docPreviewModal) return;
    els.docPreviewClose.addEventListener("click", closeDocPreview);
    els.docPreviewBack.addEventListener("click", previewGoBack);
    if (els.docPreviewFullscreen) {
      els.docPreviewFullscreen.addEventListener("click", () =>
        setPreviewFullscreen(!isPreviewFullscreen()));
    }
    els.docPreviewModal.addEventListener("click", (ev) => {
      if (ev.target === els.docPreviewModal) closeDocPreview();
    });
    els.docPreviewCopy.addEventListener("click", async () => {
      const path = els.docPreviewMeta.querySelector(".doc-preview-path");
      if (!path) return;
      const text = path.textContent;
      let ok = false;
      try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
          await navigator.clipboard.writeText(text);
          ok = true;
        }
      } catch (_) { ok = false; }
      if (!ok) ok = legacyCopy(text);
      showToast(ok ? t("preview_copied", { path: text }) : "clipboard unavailable",
                ok ? "success" : "error");
    });
    els.docPreviewLinksBtn.addEventListener("click", () => {
      const ref = preview.current && preview.current.ref;
      if (!ref || !ref.node) return;
      // The card's own links are already in its sidebar. Closing the preview
      // and jumping to another tab threw away the reading position and the
      // drill-down stack to show something that was on screen the whole time.
      const side = els.docPreviewSide;
      const heading = side && [...side.querySelectorAll(".doc-preview-side-head")]
        .find((h) => h.textContent === t("preview_out") || h.textContent === t("preview_in"));
      if (heading) {
        setPreviewSideVisible(true);
        heading.scrollIntoView({ block: "start", behavior: "smooth" });
        heading.classList.add("side-flash");
        setTimeout(() => heading.classList.remove("side-flash"), 1200);
        return;
      }
      // No links section (a cross-library card has no local graph) — the full
      // browser is still the right destination.
      closeDocPreview();
      switchTab("melchior");
      openGraphLinks(ref.node);
    });
    els.docPreviewContent.addEventListener("click", (ev) => {
      const a = ev.target.closest("a[data-wikilink]");
      if (a) {
        ev.preventDefault();
        openDocPreview({ node: a.dataset.wikilink },
                       { push: true, title: a.textContent });
        return;
      }
      const link = ev.target.closest("a[href]");
      // Cards link to each other by relative path too; keep those inside.
      if (link && /\.md(#.*)?$/i.test(link.getAttribute("href") || "")) {
        ev.preventDefault();
        const href = link.getAttribute("href").split("#")[0];
        const cur = preview.current && preview.current.ref;
        const base = cur && cur.path ? cur.path : "";
        const dir = base.includes("/") ? base.slice(0, base.lastIndexOf("/")) : "";
        openDocPreview({ path: (dir ? dir + "/" : "") + href.replace(/^\.\//, "") },
                       { push: true, title: link.textContent });
      }
    });
    els.docPreviewContent.addEventListener("scroll", onPreviewScroll, { passive: true });
    els.docPreviewSide.addEventListener("click", (ev) => {
      const jump = ev.target.closest("[data-toc]");
      if (jump) {
        const target = document.getElementById(jump.dataset.toc);
        if (target) {
          preview.scrollTarget = target;
          scrollPreviewTo(target);
          settlePreviewScroll();
        }
        return;
      }
      const btn = ev.target.closest("[data-node]");
      if (!btn) return;
      openDocPreview({ node: btn.dataset.node },
                     { push: true, title: btn.textContent });
    });
  }

  // ------------------------------------------------------------------------
  // Tab 4: Casper (Retrieval)
  // ------------------------------------------------------------------------

  // "This library + other enabled ones" names a set the reader cannot see from
  // this tab — which ones are enabled lives in the SEARCHABLE column on the
  // dashboard. Count them here so the default scope at least says how far it
  // reaches before anyone presses Search.
  function refreshSearchScopeLabel() {
    const sel = document.getElementById("search-scope-select");
    if (!sel) return;
    const auto = [...sel.options].find((o) => o.value === "auto");
    if (!auto) return;
    // Match retrieval.searchable_kbs, which requires output/index.db to exist:
    // counting merely-enabled libraries promised four and reached three, with
    // the un-indexed one dropped without a trace.
    const others = (state.kbs || [])
      .filter((k) => k.enabled && k.exists && k.indexed && k.path !== state.workspace);
    auto.textContent = others.length
      ? t("opt_scope_auto_n", { n: others.length })
      : t("opt_scope_auto");
    auto.title = others.map((k) => k.name).join(", ");
  }

  // The response has always carried `kbs_searched` and `kbs_skipped`, and the
  // panel showed neither. Searching UI-Check returned ten confident rows from
  // four *other* libraries with `kbs_skipped: ["local"]` — the workspace named
  // in the topbar was not searched at all, and the only trace of that was an
  // absence the reader had to notice among four `kb:` badges. A silent skip
  // presented as a clean result is the failure mode this whole release exists
  // to remove.
  function renderSearchScope(data) {
    const searched = Array.isArray(data.kbs_searched) ? data.kbs_searched : [];
    const skipped = Array.isArray(data.kbs_skipped) ? data.kbs_skipped : [];
    if (!searched.length && !skipped.length) return;

    const here = (state.kbs || []).find((k) => k.path === state.workspace);
    const hereName = here ? here.name : null;
    // `local` is how the backend names the workspace it was pointed at. That
    // is an internal name; on screen it has to be the library the topbar is
    // already naming, or the reader is left mapping one to the other.
    const namesLocal = (n) => n === "local" || (hereName && n === hereName);
    const display = (n) => (n === "local" && hereName ? hereName : n);
    const skippedHere = skipped.some(namesLocal);

    const line = document.createElement("div");
    line.className = skippedHere ? "hint-note scope-shared" : "hint-note";
    const parts = [];
    if (searched.length) {
      // The names are the count; "4 librar(ies)" is a plural nobody writes.
      parts.push(t("search_scope_searched", { names: searched.map(display).join(", ") }));
    }
    if (skippedHere) {
      parts.push(t("search_scope_skipped_here", { name: hereName || t("search_scope_this_one") }));
    }
    const others = skipped.filter((n) => !namesLocal(n));
    if (others.length) {
      parts.push(t("search_scope_skipped", { names: others.map(display).join(", ") }));
    }
    line.textContent = parts.join(" · ");
    els.searchInfoBar.appendChild(line);
  }

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

      const vecStatus = data.vector_available ? t("vec_avail_yes")
        : data.mode === "bm25" ? t("vec_avail_bychoice")
          : t("vec_avail_no");
      els.searchInfoBar.textContent = t("search_summary", {
        total: data.results.length,
        bm25: data.bm25_hits || 0,
        vec: vecStatus,
      });
      renderSearchScope(data);
      // Three different reasons land here as "no vectors", and they need three
      // different responses: you chose keyword-only, Ollama is busy, or it is
      // not set up. Telling a user who picked bm25 to go install Ollama is
      // troubleshooting copy applied to a deliberate choice.
      // Ten uniformly-confident-looking rows for a query that matched nothing
      // was the complaint. No cutoff can separate real from junk here (the
      // baseline overlaps), so say it plainly instead of dropping results.
      if (data.weak_semantic_match) {
        const weak = document.createElement("div");
        weak.className = "hint-note";
        weak.textContent = t("search_all_weak");
        els.searchInfoBar.appendChild(weak);
      }
      if (!data.vector_available && data.mode !== "bm25") {
        const note = document.createElement("div");
        note.className = "hint-note";
        note.textContent = data.vector_degraded
          ? t("vec_degraded_hint")
          : t("vec_unavailable_hint");
        els.searchInfoBar.appendChild(note);
        // Missing Ollama is felt here, so the way to fix it belongs here —
        // not three tabs away in a list the reader has no reason to open.
        // MAGI cannot install it, so the offer is the page and a re-check.
        const ollama = toolByKey("ollama");
        if (ollama && !ollama.installed) {
          const row = toolActions("ollama", () => executeSearch(query, mode, limit));
          // Installing Ollama is not the only way out of this, and for a lot
          // of people it is the one they least want. Any OpenAI-compatible
          // endpoint does the same job with nothing to install.
          const alt = document.createElement("button");
          alt.className = "btn btn-quiet btn-sm";
          alt.textContent = t("embed_help_open");
          alt.addEventListener("click", () =>
            showInfoModal(t("embed_help_title"), t("embed_help_body")));
          row.appendChild(alt);
          els.searchInfoBar.appendChild(row);
        }
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
            <div class="search-hit-card" data-hit-path="${escapeHtml(hit.path)}"
                 data-hit-heading="${escapeHtml(hit.heading || "")}"
                 data-hit-line="${escapeHtml(String(lineStart || ""))}"
                 data-hit-kb="${escapeHtml(hit.kb || "local")}">
              <div class="search-hit-header">
                <div class="search-hit-title">${escapeHtml(hit.heading || hit.path)}</div>
                <div class="search-hit-badges">
                  ${kbBadge}${collBadge}
                  ${hit.closeness ? `<span class="badge close-${hit.closeness}" title="${escapeHtml(t("badge_close_tip", { d: hit.distance }))}">${escapeHtml(closenessLabel(hit.closeness))}</span>` : ""}
                  <span class="badge badge-terracotta" title="${escapeHtml(t("badge_rrf_tip"))}">RRF ${hit.score}</span>
                  ${hit.bm25_rank ? `<span class="badge badge-blue" title="${escapeHtml(t("badge_bm25_tip", { n: hit.bm25_rank }))}">BM25 #${hit.bm25_rank}</span>` : ""}
                  ${hit.vector_rank ? `<span class="badge badge-sage" title="${escapeHtml(t("badge_vec_tip", { n: hit.vector_rank }))}">Vec #${hit.vector_rank}</span>` : ""}
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
      // A snippet is a few lines out of the middle of a card; the card itself
      // is one click away.
      els.searchResultsList.querySelectorAll("[data-hit-path]").forEach((card) => {
        card.classList.add("search-hit-clickable");
        card.title = t("preview_hint_search");
        card.addEventListener("click", () => {
          // Search is federated: a hit may belong to another registered KB,
          // and the server resolves that name to a root for us.
          openDocPreview({ path: card.dataset.hitPath, kb: card.dataset.hitKb },
                         { heading: card.dataset.hitHeading,
                           line: Number(card.dataset.hitLine) || 0 });
        });
      });
    } catch (err) {
      els.searchResultsList.innerHTML = `<div class="error-box">${escapeHtml(err.message)}</div>`;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 5: Literature Radar
  // ------------------------------------------------------------------------

  // Whether this workspace's hub has a task store. The radar rows offer
  // "Create reading task", which writes there; without it the click returns a
  // 409 the reader can do nothing about from this tab.
  async function refreshTaskStoreState() {
    if (!state.workspace) { state.taskStore = null; return; }
    try {
      const pm = await apiFetch(`/api/workspace/pm?workspace=${encodeURIComponent(state.workspace)}`);
      state.taskStore = { ready: !!pm.store_root, root: pm.store_root || null };
    } catch (_) {
      state.taskStore = null;   // unknown, so do not disable anything
    }
  }


  // ------------------------------------------------------------------------
  // Optional features
  //
  // Two of MAGI's workflows can be switched off — the literature radar and
  // task tracking. Off is a choice, not a fault, so the panel greys out with
  // a way back rather than disappearing from the tab bar: a tab that vanishes
  // is a tab you cannot find again.
  //
  // Everything here is machine-wide. None of it varies by workspace, which is
  // why the gate says so out loud next to a topbar that names one.
  // ------------------------------------------------------------------------


  // The CLI has one language and the WebUI has two, so these strings are
  // translated here and the API text is only the fallback. Spelled out as a
  // map rather than built as "opt_unlocks_" + key: a concatenated key is
  // invisible to the test that checks every t() key exists.
  const TOOL_UNLOCKS = {
    ollama: "opt_unlocks_ollama", pandoc: "opt_unlocks_pandoc",
    poppler: "opt_unlocks_poppler", latex: "opt_unlocks_latex",
    mineru: "opt_unlocks_mineru",
  };
  const TOOL_HINTS = {
    ollama: "opt_hint_ollama", poppler: "opt_hint_poppler",
    mineru: "opt_hint_mineru",
  };
  const FEATURE_WHAT = {
    radar: "feature_what_radar", tasks: "feature_what_tasks",
  };
  const FEATURE_LABEL = {
    radar: "feature_label_radar", tasks: "feature_label_tasks",
  };

  function toolUnlocks(tool) {
    return TOOL_UNLOCKS[tool.key] ? t(TOOL_UNLOCKS[tool.key]) : tool.unlocks;
  }

  function toolHint(tool) {
    if (TOOL_HINTS[tool.key]) return t(TOOL_HINTS[tool.key]);
    return tool.hint || "";
  }

  function featureWhat(feat) {
    return FEATURE_WHAT[feat.key] ? t(FEATURE_WHAT[feat.key]) : feat.what;
  }

  // The label lands inside a translated sentence ("「{name}」已关闭"), so an
  // English label there is not a proper noun left alone, it is a sentence in
  // two languages.
  function featureLabel(feat) {
    return FEATURE_LABEL[feat.key] ? t(FEATURE_LABEL[feat.key]) : feat.label;
  }

  async function loadFeatures() {
    try {
      state.features = await apiFetch("/api/features");
    } catch (_) {
      // Unknown is not off. A failed read must never grey out a working panel.
      state.features = null;
    }
    applyFeatureGates();
  }

  function featureByKey(key) {
    if (!state.features || !Array.isArray(state.features.features)) return null;
    return state.features.features.find((f) => f.key === key) || null;
  }

  function toolByKey(key) {
    if (!state.features || !Array.isArray(state.features.tools)) return null;
    return state.features.tools.find((t) => t.key === key) || null;
  }

  function applyFeatureGates() {
    renderFeatureGate("radar", "gate-radar", "tab-radar");
    renderFeatureGate("tasks", "gate-balthasar", "tab-balthasar");
  }

  function renderFeatureGate(key, gateId, panelId) {
    const gate = document.getElementById(gateId);
    const panel = document.getElementById(panelId);
    if (!gate || !panel) return;
    const feat = featureByKey(key);

    // No answer yet, or the feature is on: nothing to say.
    if (!feat || feat.enabled) {
      gate.hidden = true;
      gate.innerHTML = "";
      panel.classList.remove("feature-off");
      return;
    }

    panel.classList.add("feature-off");
    gate.hidden = false;
    gate.innerHTML = "";
    // The loaders below the gate return early, which leaves whatever
    // placeholder the markup shipped with — a permanent "Loading digests..."
    // behind a panel that has explicitly stopped. Dimmed or not, a panel must
    // not claim to be doing something it is not.
    quietPanel(panelId);

    const title = document.createElement("div");
    title.className = "gate-title";
    title.textContent = t("feature_off_title", { name: featureLabel(feat) });
    gate.appendChild(title);

    const body = document.createElement("div");
    body.className = "gate-body";
    body.textContent = t("feature_off_body", { what: featureWhat(feat) });
    gate.appendChild(body);

    const row = document.createElement("div");
    row.className = "gate-actions";

    const on = document.createElement("button");
    on.className = "btn btn-primary btn-sm";
    on.innerHTML =
      `<span>${escapeHtml(t("feature_turn_on", { name: featureLabel(feat) }))}</span>` +
      ` <span class="badge badge-muted op-scope-badge">${escapeHtml(t("ops_badge_global"))}</span>`;
    // Says what the click will do before it does it, including the install,
    // which is the part that takes a minute and touches the machine.
    on.title = feat.can_install && !feat.needs_installed
      ? t("feature_turn_on_installs", { needs: feat.needs })
      : t("feature_turn_on_plain");
    on.addEventListener("click", () => turnFeatureOn(feat));
    row.appendChild(on);
    gate.appendChild(row);

    if (feat.can_install && !feat.needs_installed) {
      const note = document.createElement("div");
      note.className = "gate-note";
      note.textContent = t("feature_will_install", { needs: feat.needs });
      gate.appendChild(note);
    }
  }

  // What a switched-off panel would otherwise keep claiming. `blocks` are
  // regions whose markup ships a "Loading…" placeholder that nothing will ever
  // replace once the loader returns early; `metrics` are display numbers whose
  // markup default is 0 — a confident zero for a count nobody took.
  const QUIET_TARGETS = {
    "tab-radar": {
      blocks: ["digest-files-list", "digest-viewer", "digest-triage"],
      metrics: ["radar-pending-count", "radar-last-harvest"],
    },
    "tab-balthasar": {
      blocks: [],
      metrics: ["task-ready-val", "task-progress-val", "task-blocked-val", "task-open-val"],
    },
  };

  function quietPanel(panelId) {
    const targets = QUIET_TARGETS[panelId] || { blocks: [], metrics: [] };
    (targets.blocks || []).forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<p class="empty-note pad-1">${escapeHtml(t("feature_off_quiet"))}</p>`;
    });
    (targets.metrics || []).forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.textContent = t("metric_feature_off");
      el.classList.add("metric-empty");
    });
  }


  // One row per optional component: what it unlocks, whether this machine has
  // it, a tick for whether you want it at all, and the only action that is
  // honest for it. MAGI installs none of these, so no row offers to — the
  // exception is Ollama, where MAGI can pull the models once Ollama itself is
  // there, and that button only appears when it is.
  function renderOptionalComponents() {
    const list = document.getElementById("optional-list");
    if (!list) return;
    list.innerHTML = "";
    const tools = (state.features && state.features.tools) || [];
    if (!tools.length) {
      list.innerHTML = `<p class="empty-note">${escapeHtml(t("opt_unknown"))}</p>`;
      return;
    }

    tools.forEach((tool) => {
      const row = document.createElement("div");
      row.className = "opt-row";

      const head = document.createElement("div");
      head.className = "opt-head";

      const tick = document.createElement("label");
      tick.className = "inline-check";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = !!tool.wanted;
      box.title = t("opt_want_tip", { name: tool.label });
      box.addEventListener("change", async () => {
        try {
          await apiFetch("/api/features", {
            method: "POST",
            body: JSON.stringify({ key: tool.key, enabled: box.checked, kind: "tool" }),
          });
          showToast(box.checked ? t("opt_wanted_toast", { name: tool.label })
                                : t("opt_declined_toast", { name: tool.label }), "success");
          await loadFeatures();
          renderOptionalComponents();
        } catch (err) {
          box.checked = !box.checked;      // put the tick back where it was
          showToast(err.message, "error");
        }
      });
      tick.appendChild(box);
      const name = document.createElement("span");
      name.className = "opt-name";
      name.textContent = tool.label;
      tick.appendChild(name);
      head.appendChild(tick);

      // `installed: null` is MinerU: a hosted service, where "installed" is
      // not a question with an answer.
      const badge = document.createElement("span");
      if (tool.installed === null) {
        badge.className = "badge badge-muted";
        badge.textContent = t("opt_service");
      } else if (tool.installed) {
        badge.className = "badge badge-sage";
        badge.textContent = t("opt_present");
      } else {
        badge.className = "badge badge-muted";
        badge.textContent = t("opt_absent");
      }
      head.appendChild(badge);
      row.appendChild(head);

      const what = document.createElement("div");
      what.className = "opt-what";
      what.textContent = t("opt_unlocks", { unlocks: toolUnlocks(tool) });
      row.appendChild(what);

      const hintText = toolHint(tool);
      if (hintText) {
        const hint = document.createElement("div");
        hint.className = "opt-hint";
        hint.textContent = hintText;
        row.appendChild(hint);
      }

      // Only attach the strip if it actually holds a control — an empty
      // flex row still takes vertical space and reads as a missing button.
      const actions = toolActions(tool.key, () => renderOptionalComponents());
      if (actions.childElementCount) row.appendChild(actions);
      list.appendChild(row);
    });
  }

  async function turnFeatureOn(feat) {
    try {
      await apiFetch("/api/features", {
        method: "POST",
        body: JSON.stringify({ key: feat.key, enabled: true, kind: "feature" }),
      });
    } catch (err) {
      showToast(err.message, "error");
      return;
    }
    // The switch is the whole job for the radar. Task tracking also needs its
    // store on disk, and that is a job with output worth watching.
    if (feat.op && feat.can_install && !feat.needs_installed) {
      launchJob(feat.op, t("feature_turn_on", { name: featureLabel(feat) }), null, { stay: true });
    } else {
      showToast(t("feature_on_toast", { name: featureLabel(feat) }), "success");
    }
    invalidateCoalesced();
    await loadFeatures();
    loadSyncRatio();
    loadTabData(state.activeTab);
  }

  // A tool MAGI cannot install. The only honest offer is the page it lives on
  // and a way to look again afterwards — a button labelled "install" that
  // opens a browser tab is a button that lied.
  function toolActions(key, onRecheck) {
    const tool = toolByKey(key);
    const row = document.createElement("div");
    row.className = "gate-actions";
    if (!tool) return row;

    // Already here: the download page and a re-check are both answers to a
    // question nobody is asking. Only the follow-up action below is useful.
    if (tool.installed !== true) {
      const open = document.createElement("a");
      open.className = "btn btn-secondary btn-sm";
      open.href = tool.url;
      open.target = "_blank";
      open.rel = "noopener noreferrer";
      open.textContent = t("tool_open_site", { name: tool.label });
      row.appendChild(open);
    }

    // `installed === null` is a hosted service. "I installed it" is not a
    // thing you can do to a website, and there is nothing on this machine to
    // look for — its readiness is a token in config.yaml, not a binary.
    if (tool.installed === false) {
      const again = document.createElement("button");
      again.className = "btn btn-quiet btn-sm";
      again.textContent = t("tool_recheck");
      again.title = t("tool_recheck_tip", { name: tool.label });
      again.addEventListener("click", async () => {
        await loadFeatures();
        const now = toolByKey(key);
        if (now && now.installed) {
          showToast(t("tool_found", { name: tool.label }), "success");
          if (typeof onRecheck === "function") onRecheck(now);
        } else {
          showToast(t("tool_still_missing", { name: tool.label }), "warn");
        }
      });
      row.appendChild(again);
    }

    // The one thing MAGI *can* do once the tool itself is present.
    // Spelled out rather than built as "op_" + id: a concatenated key is
    // invisible to the test that checks every t() key exists, which is how a
    // typo here would reach the browser as the literal word "undefined".
    const OP_LABELS = { "pull-models": "op_pull_models",
                        "install-tasks": "op_install_tasks" };
    if (tool.op && tool.installed && OP_LABELS[tool.op]) {
      const run = document.createElement("button");
      run.className = "btn btn-secondary btn-sm";
      run.textContent = t(OP_LABELS[tool.op]);
      run.addEventListener("click", () =>
        launchJob(tool.op, t(OP_LABELS[tool.op]), null, { stay: true }));
      row.appendChild(run);
    }
    return row;
  }

  async function loadRadar() {
    if (!state.workspace) return;
    // The gate is drawn from cached state; the fetches below are what would
    // otherwise repopulate a panel the user switched off.
    const radar = featureByKey("radar");
    if (radar && !radar.enabled) return;
    try {
      await refreshTaskStoreState();
      if (els.radarSettingsBody) loadConfigCard(els.radarSettingsBody, "radar");
      const radar = await apiFetch(`/api/workspace/radar?workspace=${encodeURIComponent(state.workspace)}`);
      const files = (radar.pending_digests ? radar.pending_digests.length : 0)
        + (radar.pending_citation_gaps ? radar.pending_citation_gaps.length : 0);
      // Papers, not files: "2 pending" told you how many documents existed,
      // never how much work was in them.
      const waiting = radar.pending_candidates || 0;
      els.radarPendingCount.textContent = waiting || files;
      els.radarPendingCount.classList.toggle("eva-alert", files > 0);
      if (els.radarPendingSub) {
        els.radarPendingSub.textContent = files
          ? t("radar_pending_sub_n", { files })
          : t("radar_pending_sub_clear");
      }

      const age = radar.harvest_age_days;
      if (els.radarLastHarvest) {
        els.radarLastHarvest.textContent =
          age === null || age === undefined ? t("radar_never")
            : age === 0 ? t("radar_today")
              : t("radar_days_ago", { days: age });
        // Overdue is judged against the configured window, the same way a
        // stale index is — a radar that quietly stopped should look wrong.
        const window = Number(state.radarDays || 7);
        els.radarLastHarvest.classList.toggle(
          "tone-amber", age !== null && age !== undefined && age > Math.max(window, 1) * 2);
      }
      if (els.radarSeenCountSub) {
        els.radarSeenCountSub.textContent = t("radar_seen_sub_n", { n: radar.seen_total || 0 });
      }

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
      // Triage list first — that is the job. The rendered digest below is the
      // same 40 papers again in prose; it used to be the only thing on screen
      // for the first fourteen screens of scrolling, with the controls after.
      renderDigestTriage(data);

      const src = document.createElement("details");
      src.className = "digest-source";
      const cap = document.createElement("summary");
      cap.textContent = t("digest_source_title", { file: data.file });
      src.appendChild(cap);
      const body = document.createElement("div");
      body.className = "markdown-body";
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
        body.innerHTML = window.marked.parse(safeMd);
      } else {
        body.textContent = data.content;
      }
      src.appendChild(body);
      els.digestViewer.innerHTML = "";
      els.digestViewer.appendChild(src);
      renderDigestFooter(data);
    } catch (err) {
      els.digestViewer.innerHTML = `<p style="color: var(--accent-danger);">${escapeHtml(err.message)}</p>`;
    }
  }

  // Review actions: mark-reviewed footer + per-candidate accept/task buttons
  // The weekly job, as one list. Every candidate carries what you need to
  // decide (score, authors, abstract) and the controls to act, in the same
  // row — they used to be two separate lists fourteen screens apart.
  function renderDigestTriage(data) {
    const host = els.digestTriage;
    if (!host) return;
    host.innerHTML = "";
    const cands = data.candidates || [];
    if (!cands.length) return;

    const box = document.createElement("div");
    box.className = "digest-actions";

    const head = document.createElement("div");
    head.className = "digest-actions-head";
    const title = document.createElement("div");
    title.className = "digest-actions-title";
    title.textContent = t("radar_actions_title");
    const progress = document.createElement("span");
    progress.className = "digest-progress";
    head.appendChild(title);
    head.appendChild(progress);
    box.appendChild(head);

    const filterRow = document.createElement("div");
    filterRow.className = "digest-filter-row";
    const filterInput = document.createElement("input");
    filterInput.type = "text";
    filterInput.id = "radar-author-filter";
    filterInput.className = "text-input";
    filterInput.placeholder = t("radar_filter_ph");
    filterInput.setAttribute("data-i18n-placeholder", "radar_filter_ph");
    const hideDone = document.createElement("label");
    hideDone.className = "digest-hide-done";
    const hideBox = document.createElement("input");
    hideBox.type = "checkbox";
    hideBox.id = "radar-hide-decided";
    hideDone.appendChild(hideBox);
    hideDone.appendChild(document.createTextNode(" " + t("radar_hide_decided")));
    const filterCount = document.createElement("span");
    filterCount.id = "radar-filter-count";
    filterCount.className = "empty-note";
    filterRow.appendChild(filterInput);
    filterRow.appendChild(hideDone);
    filterRow.appendChild(filterCount);
    box.appendChild(filterRow);

    const applyFilter = () => {
      const q = filterInput.value.trim().toLowerCase();
      const rows = box.querySelectorAll(".action-row");
      let shown = 0;
      let decided = 0;
      rows.forEach((r) => {
        if (r.dataset.decision) decided++;
        const matches = !q || (r.dataset.search || "").includes(q);
        const hit = matches && !(hideBox.checked && r.dataset.decision);
        r.style.display = hit ? "" : "none";
        if (hit) shown++;
      });
      filterCount.textContent = t("radar_filter_count", { shown, total: rows.length });
      progress.textContent = t("radar_triage_progress", { done: decided, total: rows.length });
      progress.classList.toggle("is-complete", decided === rows.length && rows.length > 0);
    };

    cands.forEach((c) => {
      box.appendChild(buildCandidateRow(data, c, applyFilter));
    });

    filterInput.addEventListener("input", applyFilter);
    hideBox.addEventListener("change", applyFilter);
    applyFilter();
    host.appendChild(box);
  }

  // Relevance is a cosine against the library centroid. The raw number means
  // nothing without calibration — on a real harvest every candidate scores
  // between 0.55 and 0.70 because they all arrived pre-filtered as physics —
  // so rank it within this harvest instead of showing the float bare.
  // Written out rather than assembled from a prefix and a variable: i18n keys
  // are never concatenated in this file, so the dictionary-completeness test
  // can see every key that is actually used. (It scans comments too — a
  // concatenated key quoted in prose trips it just as a real one would.)
  function closenessLabel(kind) {
    if (kind === "strong") return t("close_strong");
    if (kind === "related") return t("close_related");
    if (kind === "weak") return t("close_weak");
    return "";
  }

  function relevanceChip(c, all) {
    if (c.relevance === null || c.relevance === undefined) return null;
    const scores = all.map((x) => x.relevance).filter((v) => v !== null && v !== undefined);
    const chip = document.createElement("span");
    chip.className = "rel-chip";
    chip.title = t("radar_rel_tooltip", { score: c.relevance });
    if (scores.length >= 4) {
      const sorted = [...scores].sort((a, b) => a - b);
      const rank = sorted.filter((v) => v < c.relevance).length / sorted.length;
      const tier = rank >= 0.75 ? "top" : rank >= 0.4 ? "mid" : "low";
      chip.classList.add(`rel-${tier}`);
      chip.textContent = t(`radar_rel_${tier}`);
    } else {
      chip.textContent = String(c.relevance);
    }
    return chip;
  }

  function buildCandidateRow(data, c, applyFilter) {
    const cands = data.candidates || [];
    const row = document.createElement("div");
    row.className = "action-row";
    const authors = Array.isArray(c.authors) ? c.authors : [];
    row.dataset.search = `${c.title || ""} ${authors.join(" ")}`.toLowerCase();
    if (c.decision) row.dataset.decision = c.decision;

    const left = document.createElement("div");
    left.className = "row-main";

    const label = document.createElement("div");
    label.className = "row-title";
    const chip = relevanceChip(c, cands);
    if (chip) label.appendChild(chip);
    const link = c.arxiv_id ? `https://arxiv.org/abs/${c.arxiv_id}` : c.url;
    if (link) {
      const a = document.createElement("a");
      a.href = link;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = c.title;
      label.appendChild(a);
    } else {
      label.appendChild(document.createTextNode(c.title));
    }
    left.appendChild(label);

    if (authors.length) {
      const authorLine = document.createElement("div");
      authorLine.className = "row-authors";
      authorLine.textContent = authors.join(", ");
      authorLine.title = authors.join(", ");
      left.appendChild(authorLine);
    }
    // The abstract is the thing you actually judge on, so it belongs in the
    // row — clamped to two lines, expanded by clicking.
    if (c.abstract) {
      const abs = document.createElement("div");
      abs.className = "row-abstract";
      abs.textContent = c.abstract;
      abs.addEventListener("click", () => abs.classList.toggle("expanded"));
      left.appendChild(abs);
    }
    row.appendChild(left);

    const btns = document.createElement("div");
    btns.className = "row-btns";
    // Three verbs with three different blast radii, and nothing on screen
    // separated them: Skip only records a decision, Accept writes a file into
    // this workspace, and Create reading task writes into the task store at
    // the hub — shared by every topic under it. The tooltip carries the full
    // sentence; the badge carries the part you must not miss.
    const actions = [
      ["dismiss", "btn_dismiss", "btn-quiet", "tip_dismiss", false],
      ["accept-to-inbox", "btn_accept_inbox", "btn-secondary", "tip_accept_inbox", false],
      ["create-issue", "btn_create_issue", "btn-secondary", "tip_create_issue", true],
    ];
    actions.forEach(([action, key, cls, tipKey, hubLevel]) => {
      const b = document.createElement("button");
      b.className = `btn ${cls} btn-sm`;
      b.textContent = t(key);
      b.dataset.action = action;
      b.title = t(tipKey);
      if (hubLevel) {
        b.insertAdjacentHTML("beforeend",
          ` <span class="badge badge-muted op-scope-badge">${escapeHtml(t("scope_badge_hub"))}</span>`);
      }
      // A decision restored from the server disables its row's actions the
      // same way a fresh one does — otherwise reloading mid-triage makes every
      // decided row look actionable again.
      b.disabled = !!c.decision;
      // Clicking this with no task store returns a 409 the reader can do
      // nothing about from here. Say why it is off instead of failing later.
      if (hubLevel && state.taskStore && !state.taskStore.ready) {
        b.disabled = true;
        b.title = t("tip_create_issue_no_store");
      }
      b.addEventListener("click", () =>
        radarCandidateAction(data.file, c.index, action, b, row, applyFilter));
      btns.appendChild(b);
    });
    // Undo, so a mis-click is not permanent.
    const undo = document.createElement("button");
    undo.className = "btn btn-quiet btn-sm row-undo";
    undo.textContent = t("btn_undo");
    undo.addEventListener("click", () =>
      radarCandidateAction(data.file, c.index, "reset", undo, row, applyFilter));
    btns.appendChild(undo);
    row.appendChild(btns);
    return row;
  }

  function renderDigestFooter(data) {
    if (data.status !== "pending-review") return;
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
        invalidateCoalesced();
        loadRadar();
      } catch (_) {}
    });
    foot.appendChild(btn);
    els.digestViewer.appendChild(foot);
  }

  async function radarCandidateAction(file, index, action, btn, row, applyFilter) {
    btn.disabled = true;
    try {
      const res = await apiFetch("/api/workspace/radar/candidate", {
        method: "POST",
        body: JSON.stringify({ file, index, action, workspace: state.workspace }),
      });
      if (action === "accept-to-inbox") {
        showToast(t(res.status === "already-queued" ? "toast_already_queued" : "toast_accepted",
                    { kind: res.source_type, value: res.value }), "success");
      } else if (action === "create-issue") {
        showToast(t("toast_issue_created"), "success");
      }
      // The decision is server state now, so the row shows it and the
      // progress counter moves — triage you can put down and pick up again.
      if (row) {
        if (res.decision) row.dataset.decision = res.decision;
        else delete row.dataset.decision;
        // Including the button that was just clicked — leaving it live is how
        // you get a second "Already accepted" 409 from a double tap.
        row.querySelectorAll("button[data-action]").forEach((b) => {
          b.disabled = !!res.decision;
        });
      } else {
        btn.disabled = false;
      }
      if (applyFilter) applyFilter();
    } catch (_) {
      // Leave the row alone on failure — the server said no, so the decision
      // did not happen and pretending otherwise would lose it.
      btn.disabled = false;
    }
  }

  // ------------------------------------------------------------------------
  // Tab 5: Ingest queue — the gate between "converted" and "in my library"
  //
  // Borrows the radar triage shape (a row per item, hide-decided, undo) because
  // it is the same job: look at many things quickly and decide each. What is
  // new is that these decisions are staged. Radar acts the instant you click;
  // here nothing reaches raw/ until Commit, and Commit refuses while anything
  // is undecided.
  // ------------------------------------------------------------------------

  async function loadInbox() {
    // The panel counted only what its own widgets had queued, so a directory
    // holding two papers read as "WAITING IN QUEUE 0" — under a dashboard
    // whose own advice is to put papers exactly there.
    const card = document.getElementById("inbox-card");
    if (!card) return;
    if (!state.workspace) { card.hidden = true; return; }
    let data;
    try {
      data = await apiFetch(`/api/workspace/inbox?workspace=`
        + encodeURIComponent(state.workspace));
    } catch (_) { card.hidden = true; return; }

    card.hidden = !(data.count > 0);
    if (card.hidden) return;
    document.getElementById("inbox-title").textContent =
      t("inbox_title", { n: data.count });
    document.getElementById("inbox-sub").textContent = t("inbox_sub");
    document.getElementById("inbox-files").innerHTML = (data.files || [])
      .map((f) => `<div class="stack-row"><div><code>${escapeHtml(f.name)}</code>`
        + ` <span class="badge badge-muted">${Math.max(1, Math.round(f.bytes / 1024))} KB</span>`
        + `</div></div>`).join("");
    const btn = document.getElementById("btn-inbox-pickup");
    btn.textContent = t("inbox_pickup");
    if (!btn.dataset.wired) {
      btn.dataset.wired = "1";
      btn.addEventListener("click", () =>
        launchJob("ingest-auto", t("op_ingest_auto")));
    }
  }

  async function loadIngest() {
    loadInbox();
    // Reading the Zotero tree is a SQLite copy of a file that can be 80 MB, so
    // it happens the first time this panel is looked at rather than on page
    // load. Deliberately not awaited: a slow or absent Zotero must not hold up
    // the queue the panel is actually about.
    loadZoteroCollections();
    // "0 waiting, nothing queued yet" is a confident answer, and with no
    // workspace chosen it is not the true one — the truth is that we do not
    // know which library to look at. This panel showed a reassuring zero over a
    // workspace holding three items, which is the same shape of lie the sync
    // ratio and the empty-workspace fault were fixed for in v1.10.1.
    if (!state.workspace) {
      els.ingestPendingCount.textContent = "—";
      els.ingestUndecidedCount.textContent = "—";
      els.ingestUndecidedCount.classList.remove("tone-amber");
      els.ingestBatches.innerHTML =
        `<p class="empty-note">${t("ingest_no_workspace")}</p>`;
      return;
    }
    try {
      const data = await apiFetch(
        `/api/workspace/ingest/queue?workspace=${encodeURIComponent(state.workspace)}`
      );
      state.ingest = data;
      // Say which library these numbers are for. Everything on this page is
      // scoped to the picker at the top, and a count with no owner is exactly
      // how a number gets read against the wrong workspace.
      if (els.ingestScope) {
        const kb = (state.kbs || []).find((k) => k.path === state.workspace);
        els.ingestScope.textContent = t("ingest_scope", {
          name: kb ? kb.name : state.workspace,
        });
      }
      els.ingestPendingCount.textContent = (data.pending || []).length;
      const undecided = (data.batches || []).reduce((n, b) => n + b.undecided, 0);
      els.ingestUndecidedCount.textContent = undecided;
      els.ingestUndecidedCount.classList.toggle("tone-amber", undecided > 0);
      renderIngestBatches(data.batches || []);
    } catch (err) {
      els.ingestBatches.innerHTML = `<p class="empty-note">${escapeHtml(err.message)}</p>`;
    }
  }

  function renderIngestBatches(batches) {
    if (!batches.length) {
      els.ingestBatches.innerHTML = `<p class="empty-note">${t("ingest_empty")}</p>`;
      return;
    }
    els.ingestBatches.innerHTML = batches
      .map((b) => {
        const state_ = b.undecided
          ? `<span class="badge badge-terracotta">${t("ingest_badge_undecided", { n: b.undecided })}</span>`
          : `<span class="badge badge-sage">${t("ingest_badge_ready")}</span>`;
        return `<details class="ingest-batch" data-batch="${escapeHtml(b.batch_id)}">
          <summary><strong>${escapeHtml(b.batch_id)}</strong> — ${b.items} ${state_}</summary>
          <div class="ingest-items"><p class="empty-note">${t("loading")}</p></div>
        </details>`;
      })
      .join("");

    els.ingestBatches.querySelectorAll("details.ingest-batch").forEach((el) => {
      el.addEventListener("toggle", () => {
        if (el.open) loadIngestBatch(el.dataset.batch, el.querySelector(".ingest-items"));
      });
    });
  }

  async function loadIngestBatch(batchId, host) {
    try {
      const data = await apiFetch(
        `/api/workspace/ingest/batch?batch=${encodeURIComponent(batchId)}` +
          `&workspace=${encodeURIComponent(state.workspace)}`
      );
      host.innerHTML = data.items.map((it) => ingestRow(batchId, it)).join("");
      wireIngestRows(host, batchId);
      applyIngestFilter(host);
    } catch (err) {
      host.innerHTML = `<p class="empty-note">${escapeHtml(err.message)}</p>`;
    }
  }

  function ingestRow(batchId, item) {
    const decided = !!item.decision;
    const title = item.title || item.source_value || item.item_id;
    const flags = (item.findings || []).filter((f) => f.severity !== "info");
    // A conversion that produced nothing cannot be approved, so Approve must
    // not look like the thing to do. Three states, three different defaults:
    // failed -> reject; flagged -> read it first; clean -> wave it through.
    const state = item.error ? "failed" : flags.length ? "flagged" : "clean";

    // The code alone is jargon. "6 figures dropped" is what a reviewer decides
    // on, and burying it in a title attribute means nobody reads it.
    const findings = (item.findings || [])
      .map((f) => {
        const tone = f.severity === "info" ? "badge-muted" : "badge-terracotta";
        return `<div class="ingest-finding"><span class="badge ${tone}">${escapeHtml(f.code)}</span>` +
          `<span class="ingest-finding-detail">${escapeHtml(f.detail || "")}</span></div>`;
      })
      .join("");
    const err = item.error
      ? `<div class="ingest-error">${escapeHtml(item.error)}</div>`
      : "";
    const preview = item.preview
      ? `<details class="ingest-preview"><summary>${t("ingest_preview")}</summary>` +
        `<pre>${escapeHtml(item.preview.slice(0, 4000))}</pre></details>`
      : "";

    const approveClass = state === "clean" ? "btn-primary" : "btn-secondary";
    const rejectClass = state === "failed" ? "btn-primary" : "btn-secondary";
    return `<div class="action-row ingest-item ingest-${state}" data-item="${escapeHtml(item.item_id)}" data-decision="${escapeHtml(item.decision || "")}">
      <div class="row-main">
        <div class="row-title">${escapeHtml(title)}</div>
        <div class="row-meta"><code>${escapeHtml(item.route || "")}</code></div>
        ${findings}
        ${err}
        ${preview}
      </div>
      <div class="row-btns">
        <button class="btn btn-sm ${approveClass}" data-act="approve"${decided || item.error ? " disabled" : ""} title="${item.error ? escapeHtml(t("ingest_cannot_approve")) : ""}">${t("ingest_approve")}</button>
        <button class="btn btn-sm ${rejectClass}" data-act="reject"${decided ? " disabled" : ""}>${t("ingest_reject")}</button>
        <button class="btn btn-sm btn-ghost" data-act="reset">${t("ingest_undo")}</button>
      </div>
    </div>`;
  }

  function wireIngestRows(host, batchId) {
    host.querySelectorAll(".ingest-item").forEach((row) => {
      row.querySelectorAll("[data-act]").forEach((btn) => {
        btn.addEventListener("click", () =>
          decideIngestItem(batchId, row, btn, btn.dataset.act)
        );
      });
    });
  }

  async function decideIngestItem(batchId, row, btn, decision) {
    btn.disabled = true;
    try {
      const res = await apiFetch("/api/workspace/ingest/decide", {
        method: "POST",
        body: JSON.stringify({
          batch_id: batchId,
          item_id: row.dataset.item,
          decision,
          workspace: state.workspace,
        }),
      });
      row.dataset.decision = decision === "reset" ? "" : decision;
      row.querySelectorAll('[data-act="approve"],[data-act="reject"]').forEach((b) => {
        b.disabled = decision !== "reset";
      });
      // Rejecting is not discarding. Say where it went, or the user reasonably
      // assumes the paper is gone.
      if (res.requeued_on) {
        showToast(t("ingest_requeued", { route: res.requeued_on }), "info");
      }
      applyIngestFilter(row.closest(".ingest-items"));
      loadIngest();
    } catch (err) {
      showToast(err.message, "error");
      btn.disabled = false;
    }
  }

  function applyIngestFilter(host) {
    if (!host) return;
    const hide = els.ingestHideDecided && els.ingestHideDecided.checked;
    host.querySelectorAll(".ingest-item").forEach((row) => {
      row.style.display = hide && row.dataset.decision ? "none" : "";
    });
  }

  // ------------------------------------------------------------------------
  // Tab 6: Operations & SSE Terminal
  // ------------------------------------------------------------------------

  // Launch a whitelisted operation (see GET /api/ops). Raw argv is not a
  // thing anymore — the server rejects anything outside the catalog.
  async function launchJob(opId, displayName, confirmToken, opts) {
    if (!state.workspace) {
      showToast(t("toast_select_ws_first"), "error");
      return;
    }
    const stay = !!(opts && opts.stay);

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
      setActiveJobs(1);
      if (!stay) switchTab("operations");
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

  // Which library the workspace-scoped operations will act on. Every other
  // panel follows the picker at the top, and a grid of verbs with no stated
  // target is the one place you can run something against a library you are
  // not looking at.
  //
  // Its own function because the ops catalog loads before the workspace is
  // known: rendering the grid once left this reading "pick a knowledge base"
  // under a topbar that was already naming one.
  // Where a generic op button goes is the server catalog's answer, not this
  // file's. Each panel that hosts any declares one mount; an op whose `home`
  // is null has a better-contextualised control on its own tab already and
  // must not get a second, blander copy of itself.
  const OPS_MOUNTS = {
    dashboard: "ops-mount-dashboard",
    melchior: "ops-mount-melchior",
    casper: "ops-mount-casper",
    radar: "ops-mount-radar",
    operations: "ops-mount-operations",
    danger: "ops-danger-grid",
  };

  function opButton(entry) {
    const btn = document.createElement("button");
    btn.setAttribute("data-i18n", entry.label_i18n);
    // Label, what it does, and the exact command it runs. A three-word verb
    // asks the reader to infer "Reindex Wiki Tables" from three words; the
    // Suggested Actions panel already shows the command and is the clearest
    // thing on the dashboard, so do the same here.
    btn.innerHTML =
      `<span class="op-label">${escapeHtml(t(entry.label_i18n))}</span>` +
      (entry.desc_i18n
        ? `<span class="op-desc">${escapeHtml(t(entry.desc_i18n))}</span>` : "") +
      // /api/ops already prepends "magi" to argv — see api.py's ops handler.
      `<code class="op-cmd">${escapeHtml(entry.argv.join(" "))}</code>`;
    // A global op does not touch the selected workspace — it touches the
    // machine. `pm-init` reads as "set up tasks here" and is not; setup and
    // migrate sit beside workspace-scoped actions looking identical.
    const badge = entry.scope === "global"
      ? t(entry.badge_i18n || "ops_badge_global")
      : (entry.badge_i18n ? t(entry.badge_i18n) : null);
    if (badge) {
      btn.classList.add("op-global");
      const label = btn.querySelector(".op-label");
      if (label) {
        label.insertAdjacentHTML("beforeend",
          ` <span class="badge badge-muted op-scope-badge">${escapeHtml(badge)}</span>`);
      }
    }
    btn.title = badge ? `${badge} — ${entry.argv.join(" ")}` : entry.argv.join(" ");
    if (entry.danger) {
      btn.className = "btn btn-danger danger-action-btn";
      btn.addEventListener("click", () => openDangerConfirm(entry));
    } else {
      btn.className = "btn btn-secondary op-task-btn";
      btn.addEventListener("click", () => launchJob(entry.op, t(entry.label_i18n), null, { stay: true }));
    }
    return btn;
  }

  function renderOpsPanels() {
    const mounts = {};
    Object.entries(OPS_MOUNTS).forEach(([home, id]) => {
      const el = document.getElementById(id);
      if (el) {
        el.innerHTML = "";
        mounts[home] = el;
      }
    });
    if (!Object.keys(mounts).length) return;

    OPS_CATALOG.forEach((entry) => {
      const mount = entry.home ? mounts[entry.home] : null;
      if (!mount) return;
      mount.appendChild(opButton(entry));
    });

    // A mount whose ops all went elsewhere should say so rather than sit
    // blank looking broken.
    Object.values(mounts).forEach((el) => {
      if (!el.children.length) {
        el.innerHTML = `<span class="empty-note">${escapeHtml(t("ops_none_here"))}</span>`;
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

  // The server keeps the last 2000 log lines; the terminal used to keep every
  // line it had ever been sent, in one text node, rebuilt from scratch on each
  // arrival — `textContent +=` reads the whole string, allocates a new one, and
  // replaces the node, so the cost of line n grows with n. Reading
  // scrollHeight immediately after forced a synchronous layout on top of that,
  // once per line, with autoscroll on by default.
  //
  // Lines are queued and flushed once per animation frame instead: one DOM
  // write and one layout per frame no matter how fast the job talks, and the
  // buffer is trimmed to the same bound the server uses.
  const TERM_MAX_LINES = 2000;

  function makeLogSink(el, autoscrollEl) {
    let lines = [];
    let queued = [];
    let frame = 0;

    function flush() {
      frame = 0;
      if (!queued.length) return;
      lines = lines.concat(queued);
      queued = [];
      if (lines.length > TERM_MAX_LINES) lines = lines.slice(-TERM_MAX_LINES);
      el.textContent = lines.join("\n") + "\n";
      if (autoscrollEl && autoscrollEl.checked) el.scrollTop = el.scrollHeight;
    }

    return {
      reset(text) {
        lines = text ? [text] : [];
        queued = [];
        if (frame) { cancelAnimationFrame(frame); frame = 0; }
        el.textContent = text ? text + "\n" : "";
      },
      push(line) {
        queued.push(line);
        if (!frame) frame = requestAnimationFrame(flush);
      },
      // A job that ends between frames must not lose its last lines.
      settle() { if (frame) cancelAnimationFrame(frame); flush(); },
    };
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
    const sink = makeLogSink(els.terminalOutput, els.termAutoscroll);
    sink.reset(t("term_connecting", { id: jobId }));
    state.logSink = sink;

    const source = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/stream`);
    state.eventSource = source;

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "log") {
          sink.push(payload.line);
        } else if (payload.type === "status") {
          sink.settle();
          if (payload.status === "completed") {
            els.termStatusDot.className = "status-dot";
            if (termContainer) termContainer.classList.remove("is-running");
            els.termCancelBtn.style.display = "none";
            showToast(t("toast_job_success", { name: jobName }), "success");
            source.close();
            state.activeJobId = null;
            els.termJobName.textContent = t("term_idle");
            invalidateCoalesced();
            setActiveJobs(0);
            loadSyncRatio();
            // A job that ran without leaving its own panel should leave that
            // panel showing what it produced. Without this the graph build
            // was the worst case of all: you clicked "Rebuild the concept
            // graph", stayed on the tab, and every visible thing — including
            // the "no knowledge graph yet" line and the freshness card — said
            // exactly what it had said before. The job had finished.
            if (state.activeTab === "radar") loadRadar();
            if (jobName && /graph/i.test(jobName)) {
              loadGraphMap();
              loadMelchior();
            }
          } else if (payload.status === "failed" || payload.status === "cancelled") {
            els.termStatusDot.className = "status-dot error";
            if (termContainer) termContainer.classList.remove("is-running");
            els.termCancelBtn.style.display = "none";
            setActiveJobs(0);
            showToast(t("toast_job_ended", { name: jobName, status: payload.status }), "error");
            source.close();
            state.activeJobId = null;
            els.termJobName.textContent = t("term_idle");
          }
        }
      } catch (_) {}
    };

    source.onerror = () => {
      sink.settle();
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

  // Which doc the tab should show right now: the user's pick, with the two
  // README variants following the interface language.
  function currentDocKey() {
    if (state.activeDoc === "commands" || state.activeDoc === "guide") return state.activeDoc;
    return state.lang === "zh" ? "readme-zh" : "readme-en";
  }

  // Guide reader ------------------------------------------------------------
  // The guide is a numbered path (install -> library -> graph -> writing), so
  // the rail numbers its chapters and unfolds only the one being read.

  // Full i18n keys, not built by concatenation: the dictionary-completeness
  // test scans for literal t("...") keys, and a computed key is invisible to it.
  const CALLOUT_KINDS = {
    EXPECT: { cls: "expect", label: () => t("cal_expect") },
    FIX: { cls: "fix", label: () => t("cal_fix") },
    WARN: { cls: "warn", label: () => t("cal_warn") },
    NOTE: { cls: "note", label: () => t("cal_note") },
    TIP: { cls: "tip", label: () => t("cal_tip") },
  };

  let guideHeadings = [];
  let guideSpyQueued = false;

  function decorateCallouts(root) {
    root.querySelectorAll("blockquote").forEach((bq) => {
      const first = bq.firstElementChild;
      if (!first) return;
      const m = first.innerHTML.match(/^\s*\[!([A-Z]+)\]\s*/);
      if (!m) return;
      const kind = CALLOUT_KINDS[m[1]];
      if (!kind) return;
      first.innerHTML = first.innerHTML.slice(m[0].length);
      const box = document.createElement("div");
      box.className = "doc-callout cal-" + kind.cls;
      const label = document.createElement("div");
      label.className = "doc-callout-label";
      label.textContent = kind.label();
      box.appendChild(label);
      while (bq.firstChild) box.appendChild(bq.firstChild);
      bq.replaceWith(box);
    });
  }

  function legacyCopy(text) {
    // Served over a LAN IP the page is not a secure context and
    // navigator.clipboard is undefined - fall back to the textarea trick.
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.top = "-1000px";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (_) {
      return false;
    }
  }

  function decorateCodeBlocks(root) {
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement && pre.parentElement.classList.contains("code-wrap")) return;
      const wrap = document.createElement("div");
      wrap.className = "code-wrap";
      pre.replaceWith(wrap);
      wrap.appendChild(pre);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "copy-btn";
      btn.textContent = t("copy_code");
      btn.addEventListener("click", async () => {
        const text = pre.innerText;
        let ok = false;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          // The promise can hang indefinitely when the page lacks focus or a
          // permission decision never arrives — race it so the button always
          // reports something instead of sitting silent.
          ok = await Promise.race([
            navigator.clipboard.writeText(text).then(() => true, () => false),
            new Promise((resolve) => setTimeout(() => resolve(null), 1200)),
          ]);
          if (ok === null || ok === false) ok = legacyCopy(text);
        } else {
          ok = legacyCopy(text);
        }
        btn.textContent = t(ok ? "copied" : "copy_failed");
        btn.classList.toggle("copied", ok);
        setTimeout(() => {
          btn.textContent = t("copy_code");
          btn.classList.remove("copied");
        }, 1600);
      });
      wrap.appendChild(btn);
    });
  }

  function buildGuideNav(root) {
    guideHeadings = [];
    const list = els.docsTocList;
    if (!list) return;
    list.innerHTML = "";

    let chapter = 0;
    let section = 0;
    root.querySelectorAll("h2, h3").forEach((h) => {
      // `{#anchor}` at the end of a heading pins a stable id so other parts of
      // the dashboard can deep-link into a chapter.
      const explicit = h.innerHTML.match(/\s*\{#([A-Za-z0-9_-]+)\}\s*$/);
      let id = "";
      if (explicit) {
        id = explicit[1];
        h.innerHTML = h.innerHTML.slice(0, h.innerHTML.length - explicit[0].length);
      }
      const lv2 = h.tagName === "H2";
      if (lv2) {
        chapter += 1;
        section = 0;
      } else {
        section += 1;
      }
      if (!chapter) return; // an h3 before any chapter has nothing to belong to
      if (!id) id = lv2 ? "ch-" + chapter : "ch-" + chapter + "-" + section;
      h.id = id;

      const title = h.textContent.trim();
      const num = lv2 ? String(chapter).padStart(2, "0") : chapter + "." + section;

      if (lv2) {
        const numEl = document.createElement("span");
        numEl.className = "h-num";
        numEl.textContent = num;
        h.insertBefore(numEl, h.firstChild);
      }

      const li = document.createElement("li");
      if (!lv2) {
        li.className = "toc-sub";
        li.dataset.chapter = String(chapter);
      }
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "docs-toc-link " + (lv2 ? "lv2" : "lv3");
      btn.dataset.target = id;
      const numSpan = document.createElement("span");
      numSpan.className = "docs-toc-num";
      numSpan.textContent = num;
      const textSpan = document.createElement("span");
      textSpan.textContent = title;
      btn.appendChild(numSpan);
      btn.appendChild(textSpan);
      btn.addEventListener("click", () => scrollToGuideHeading(id));
      li.appendChild(btn);
      list.appendChild(li);

      guideHeadings.push({ el: h, id: id, chapter: chapter, lv2: lv2 });
    });

    if (els.docsToc) els.docsToc.hidden = guideHeadings.length === 0;
    if (els.docsShell) els.docsShell.classList.toggle("no-toc", guideHeadings.length === 0);
    syncGuideSpy();
  }

  function scrollToGuideHeading(id) {
    const entry = guideHeadings.find((h) => h.id === id);
    if (!entry) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    entry.el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  }

  function syncGuideSpy() {
    if (!guideHeadings.length || !els.docsContent || !els.docsTocList) return;
    const top = els.docsContent.getBoundingClientRect().top;
    let active = guideHeadings[0];
    guideHeadings.forEach((h) => {
      if (h.el.getBoundingClientRect().top - top <= 28) active = h;
    });
    els.docsTocList.querySelectorAll(".docs-toc-link").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.target === active.id);
    });
    els.docsTocList.querySelectorAll("li.toc-sub").forEach((li) => {
      li.classList.toggle("open", li.dataset.chapter === String(active.chapter));
    });
  }

  function onGuideScroll() {
    if (state.activeDoc !== "guide" || guideSpyQueued) return;
    guideSpyQueued = true;
    requestAnimationFrame(() => {
      guideSpyQueued = false;
      syncGuideSpy();
    });
  }

  async function loadDocs(docKey) {
    state.activeDoc = docKey;

    // Update active button state
    els.docSwitchBtns.forEach((b) => {
      b.classList.toggle("active", b.dataset.doc === docKey);
    });

    const isGuide = docKey === "guide";
    if (!isGuide) {
      guideHeadings = [];
      if (els.docsToc) els.docsToc.hidden = true;
      if (els.docsTocList) els.docsTocList.innerHTML = "";
      if (els.docsShell) els.docsShell.classList.add("no-toc");
    }

    els.docsContent.innerHTML = '<p class="empty-note">' + t("loading_docs") + "</p>";
    try {
      if (docKey === "commands") {
        const data = await apiFetch("/api/docs/commands");
        const cmds = data.commands || [];
        let html = "<h1>" + t("docs_cmd_title") + "</h1>";
        html += "<p>" + t("docs_cmd_sub") + "</p>";
        html += '<table class="data-table"><thead><tr><th>' + t("th_cmd_command") + "</th><th>" + t("th_cmd_group") + "</th><th>" + t("th_cmd_desc") + "</th></tr></thead><tbody>";
        cmds.forEach((c) => {
          const desc = state.lang === "zh" ? (c.help_zh || c.help) : c.help;
          const groupTitle = (state.lang === "zh" && c.group_help_zh)
            ? ' title="' + escapeHtml(c.group_help_zh) + '"' : "";
          html += "<tr><td><code>" + escapeHtml(c.command) + '</code></td><td><span class="badge badge-muted"' + groupTitle + ">" + escapeHtml(c.group || "core") + "</span></td><td>" + escapeHtml(desc) + "</td></tr>";
        });
        html += "</tbody></table>";
        els.docsContent.innerHTML = html;
      } else if (isGuide) {
        const data = await apiFetch("/api/docs/guide?lang=" + (state.lang === "zh" ? "zh" : "en"));
        const mdText = data.content || "";
        if (!mdText) {
          els.docsContent.innerHTML = '<p class="empty-note">' + t("no_docs_found") + "</p>";
          return;
        }
        if (window.marked) {
          els.docsContent.innerHTML = window.marked.parse(mdText);
          decorateCallouts(els.docsContent);
          decorateCodeBlocks(els.docsContent);
          buildGuideNav(els.docsContent);
          if (els.docsShell) els.docsShell.classList.remove("no-toc");
        } else {
          els.docsContent.textContent = mdText;
        }
        els.docsContent.scrollTop = 0;
      } else {
        const langParam = docKey === "readme-en" ? "en" : "zh";
        const data = await apiFetch("/api/docs/readme?lang=" + langParam);
        // Installed (non-repo) deployments may only have the zh README from
        // package metadata - hide the EN toggle instead of showing a blank tab.
        const enBtn = document.querySelector('.doc-switch-btn[data-doc="readme-en"]');
        if (enBtn) enBtn.style.display = data.readme_en ? "" : "none";
        const mdText = data.content || (langParam === "en" ? data.readme_en : data.readme_zh) || t("no_docs_found");
        if (window.marked && mdText) {
          els.docsContent.innerHTML = window.marked.parse(mdText);
          // README references repo-relative images the local server does not
          // host - resolve them against the GitHub repo and hide any that
          // still fail (e.g. offline).
          els.docsContent.querySelectorAll("img").forEach((img) => {
            const src = img.getAttribute("src") || "";
            if (src && !/^(https?:|data:)/i.test(src)) {
              img.src = "https://raw.githubusercontent.com/Misaka16384/magi/main/" + src.replace(/^\.?\//, "");
            }
            img.addEventListener("error", () => { img.style.display = "none"; });
            img.style.maxWidth = "100%";
          });
          decorateCodeBlocks(els.docsContent);
        } else {
          els.docsContent.textContent = mdText;
        }
      }
    } catch (err) {
      els.docsContent.innerHTML = '<p style="color: var(--accent-danger);">' + escapeHtml(err.message) + "</p>";
    }
  }

  // ------------------------------------------------------------------------
  // Doctor Check Modal
  // ------------------------------------------------------------------------

  async function openDoctorModal() {
    els.doctorModal.classList.add("open");
    els.doctorModalBody.innerHTML = `<p class="empty-note">${t("doctor_running")}</p>`;
    try {
      const data = await apiFetch(
        `/api/doctor?workspace=${encodeURIComponent(state.workspace || "")}`);
      const doc = data.doctor || [];
      const legacy = data.legacy || [];

      // Most of this table is about the machine; the agent-CLI rows are about
      // one workspace, and they say "in this workspace" without naming it.
      // Say which, up front, since the two scopes sit in one table.
      const here = (state.kbs || []).find((k) => k.path === state.workspace);
      let html = `<p class="scope-note">${escapeHtml(
        t("doctor_scope", { name: here ? here.name : (state.workspace || "—") }))}</p>`;
      html += `<table class="data-table" style="margin-bottom: 1rem;"><thead><tr><th>${t("doctor_th_comp")}</th><th>${t("doctor_th_status")}</th><th>${t("doctor_th_detail")}</th></tr></thead><tbody>`;
      // Only "missing" is a fault. An optional component nobody installed is
      // not a broken environment, and painting it red said otherwise.
      const BADGES = {
        ok: ["badge-sage", "badge_ok"],
        missing: ["badge-danger", "badge_missing"],
        optional: ["badge-muted", "badge_optional"],
        declined: ["badge-muted", "badge_declined"],
      };
      let optionalCount = 0;
      doc.forEach((row) => {
        const status = row.status || (row.ok ? "ok" : "missing");
        if (status === "optional" || status === "declined") optionalCount += 1;
        const [cls, key] = BADGES[status] || BADGES.missing;
        const mark = `<span class="badge ${cls}">${t(key)}</span>`;
        const link = row.url
          ? ` <a href="${escapeHtml(row.url)}" target="_blank" rel="noopener noreferrer">${t("doctor_get_it")} &rarr;</a>`
          : "";
        html += `<tr><td><strong>${escapeHtml(row.tool)}</strong></td><td>${mark}</td><td><code style="font-size: 0.8rem;">${escapeHtml(row.detail)}</code>${link}</td></tr>`;
      });
      html += `</tbody></table>`;

      if (!doc.some((r) => (r.status || (r.ok ? "ok" : "missing")) === "missing") && optionalCount) {
        html += `<p style="color: var(--text-secondary); font-size: 0.85rem; margin-bottom: 0.75rem;">${t("doctor_all_good", { count: optionalCount })}</p>`;
      }

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

  // Liquid Glass Toggle Button
  if (els.glassToggleBtn) {
    els.glassToggleBtn.addEventListener("click", () => {
      const next = !state.liquidGlass;
      applyLiquidGlass(next);
      showToast(t(next ? "glass_enabled_toast" : "glass_disabled_toast"), "info");
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

  // Ingest tab actions. Both long operations go through the job machinery, so
  // they stream into the terminal like every other one; `stay: true` keeps the
  // user on this tab, because the thing they are about to review is here.
  els.ingestAdd = document.getElementById("btn-ingest-add");
  if (els.ingestAdd) {
    els.ingestAdd.addEventListener("click", async () => {
      const value = (els.ingestAddUrl.value || "").trim();
      if (!value) return;
      // Queue into the library the picker is showing, not whichever directory
      // the server happens to have been started in. Everything else on this
      // page is scoped to the selected workspace; a queue that quietly went
      // somewhere else would be the "label names a different library than the
      // numbers" bug all over again.
      const kb = (state.kbs || []).find((k) => k.path === state.workspace);
      if (!kb) {
        showToast(t("ingest_no_workspace"), "error");
        return;
      }
      try {
        const res = await apiFetch("/api/ingest/enqueue", {
          method: "POST",
          body: JSON.stringify({ value, library: kb.name }),
        });
        els.ingestAddUrl.value = "";
        showToast(t("ingest_queued", { kind: res.source_type, value: res.value }), "success");
        loadIngest();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
    els.ingestAddUrl.addEventListener("keydown", (e) => {
      // Enter in a one-field form should submit it.
      if (e.key === "Enter") els.ingestAdd.click();
    });
  }

  // Upload a document off this machine. Every other door on this page takes
  // an identifier — a link, a DOI, an arXiv id — so a PDF that is not on
  // arXiv, which is most PDFs, had no way in without a terminal.
  //
  // Two steps on purpose, both reusing what is already here: the file goes
  // into inbox/, then the same enqueue call the link field makes puts it in
  // the queue below. It reaches the library through the same convert →
  // approve → commit gate as everything else rather than a second path with
  // its own rules.
  const uploadBtn = document.getElementById("btn-ingest-upload");
  const uploadInput = document.getElementById("ingest-upload-file");
  const uploadStatus = document.getElementById("ingest-upload-status");
  if (uploadBtn && uploadInput) {
    // Text is filed, not converted — the conversion ladder has nothing to do
    // with a Markdown file and says so by failing. Say it here instead.
    const TEXT_RE = /\.(md|markdown|txt)$/i;
    uploadBtn.addEventListener("click", async () => {
      const file = uploadInput.files && uploadInput.files[0];
      if (!file) return;
      const kb = (state.kbs || []).find((k) => k.path === state.workspace);
      if (!kb) {
        showToast(t("ingest_no_workspace"), "error");
        return;
      }
      uploadBtn.disabled = true;
      if (uploadStatus) uploadStatus.textContent = t("ingest_upload_working", { name: file.name });
      try {
        const up = await apiFetch(
          `/api/ingest/upload?name=${encodeURIComponent(file.name)}` +
          `&workspace=${encodeURIComponent(state.workspace)}`,
          { method: "POST", body: file, headers: {} });
        if (TEXT_RE.test(up.name)) {
          if (uploadStatus) uploadStatus.textContent = t("ingest_upload_text_done", { name: up.name });
        } else {
          await apiFetch("/api/ingest/enqueue", {
            method: "POST",
            body: JSON.stringify({ value: up.path, library: kb.name }),
          });
          if (uploadStatus) uploadStatus.textContent = t("ingest_upload_queued", { name: up.name });
        }
        uploadInput.value = "";
        loadIngest();
      } catch (err) {
        // apiFetch has already shown the toast and re-thrown; a second one
        // here would just say the same thing twice.
        if (uploadStatus) uploadStatus.textContent = "";
      } finally {
        uploadBtn.disabled = false;
      }
    });
  }

  // Zotero. The tree is read once when the panel first needs it; a library
  // with no chosen data directory answers 409 with the command that chooses
  // one, and that sentence is more useful than an empty dropdown.
  const zoteroSelect = document.getElementById("zotero-collection");
  const zoteroTag = document.getElementById("zotero-tag");
  const zoteroBtn = document.getElementById("btn-zotero-import");
  const zoteroStatus = document.getElementById("zotero-status");
  let zoteroLoaded = false;

  async function loadZoteroCollections() {
    if (zoteroLoaded || !zoteroSelect) return;
    zoteroLoaded = true;
    try {
      const res = await fetch("/api/zotero/collections");
      const data = await res.json();
      if (!res.ok) {
        zoteroSelect.innerHTML = "";
        if (zoteroStatus) zoteroStatus.textContent = data.detail || `HTTP ${res.status}`;
        return;
      }
      // Depth-first with indentation, so "Fractons / 2024" reads as nested
      // rather than as two unrelated folders that happen to sort together.
      const byParent = new Map();
      (data.collections || []).forEach((c) => {
        const k = c.parentCollectionID == null ? "root" : String(c.parentCollectionID);
        if (!byParent.has(k)) byParent.set(k, []);
        byParent.get(k).push(c);
      });
      const opts = [`<option value="">${escapeHtml(t("zotero_pick"))}</option>`];
      const walk = (key, depth) => {
        (byParent.get(key) || []).forEach((c) => {
          const pad = "  ".repeat(depth);
          opts.push(`<option value="${c.collectionID}">${pad}${escapeHtml(c.collectionName)}` +
                    ` (${c.n})</option>`);
          walk(String(c.collectionID), depth + 1);
        });
      };
      walk("root", 0);
      opts.push(`<option value="__all__">${escapeHtml(t("zotero_whole_library"))}</option>`);
      zoteroSelect.innerHTML = opts.join("");
      if (zoteroBtn) zoteroBtn.disabled = false;
    } catch (err) {
      if (zoteroStatus) zoteroStatus.textContent = err.message;
    }
  }

  if (zoteroBtn) {
    zoteroBtn.addEventListener("click", async () => {
      const pick = zoteroSelect ? zoteroSelect.value : "";
      const tag = zoteroTag ? zoteroTag.value.trim() : "";
      if (!pick && !tag) {
        if (zoteroStatus) zoteroStatus.textContent = t("zotero_pick_something");
        return;
      }
      const body = { workspace: state.workspace };
      if (pick === "__all__") body.all = true;
      else if (pick) body.collection_id = Number(pick);
      if (tag) body.tag = tag;

      zoteroBtn.disabled = true;
      if (zoteroStatus) zoteroStatus.textContent = t("zotero_working");
      try {
        const res = await apiFetch("/api/zotero/import", {
          method: "POST", body: JSON.stringify(body),
        });
        const fresh = (res.queued || []).filter((q) => q.status !== "already-queued").length;
        if (zoteroStatus) {
          zoteroStatus.textContent = t("zotero_queued", {
            n: fresh, already: (res.queued || []).length - fresh,
            skipped: (res.skipped || []).length,
          });
        }
        loadIngest();
      } catch (err) {
        if (zoteroStatus) zoteroStatus.textContent = "";
      } finally {
        zoteroBtn.disabled = false;
      }
    });
  }

  const ingestRunBtn = document.getElementById("btn-ingest-run");
  if (ingestRunBtn) {
    ingestRunBtn.addEventListener("click", () =>
      launchJob("ingest-batch-run", t("btn_ingest_run"), null, { stay: true })
    );
  }

  const ingestCommitBtn = document.getElementById("btn-ingest-commit");
  if (ingestCommitBtn) {
    ingestCommitBtn.addEventListener("click", () =>
      launchJob("ingest-batch-commit", t("btn_ingest_commit"), null, { stay: true })
    );
  }

  if (els.ingestHideDecided) {
    els.ingestHideDecided.addEventListener("change", () => {
      document.querySelectorAll(".ingest-items").forEach(applyIngestFilter);
    });
  }

  ["tasks-show-hub", "tasks-show-closed"].forEach((id) => {
    const box = document.getElementById(id);
    if (box) box.addEventListener("change", () => loadTasks());
  });

  // Workspace selector change (browsing choice — persisted per browser)
  els.workspaceSelect.addEventListener("change", (e) => {
    state.workspace = e.target.value;
    viewWorkspaceSet(state.workspace);
    updateBrowsingBadge();
    clearWorkspaceScopedViews();
    refreshSearchScopeLabel();
    loadSyncRatio();
    loadTabData(state.activeTab);
  });

  // Refresh KB button
  // A count you cannot click is a notification you cannot act on.
  if (els.activeJobsBadge) {
    els.activeJobsBadge.style.cursor = "pointer";
    els.activeJobsBadge.setAttribute("title", "");
    els.activeJobsBadge.setAttribute("data-i18n-title", "running_jobs_tooltip");
    els.activeJobsBadge.addEventListener("click", () => {
      switchTab("operations");
      const term = document.querySelector("#tab-operations .terminal-container");
      if (term) term.scrollIntoView({ block: "nearest" });
    });
  }

  els.refreshKbBtn.addEventListener("click", () => {
    invalidateCoalesced();
    loadKBRegistry();
  });

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
      invalidateCoalesced();
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
  // stay:true — a panel's own primary action should not navigate away from
  // the panel. Harvest used to switch you to Operations to watch the log and
  // leave you there, so the digest it had just produced was two clicks away.
  els.btnRadarHarvest.addEventListener("click", () => {
    launchJob("radar-harvest", t("btn_radar_harvest"), null, { stay: true });
  });
  els.btnRadarCitationGap.addEventListener("click", () => {
    launchJob("radar-citation-gap", t("btn_radar_citation_gap"), null, { stay: true });
  });
  if (els.btnRadarSettings) {
    els.btnRadarSettings.addEventListener("click", () => {
      if (!els.radarSettings) return;
      els.radarSettings.open = !els.radarSettings.open;
      if (els.radarSettings.open) els.radarSettings.scrollIntoView({ block: "nearest" });
    });
  }

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
    // Through the sink, not straight at the element: the sink owns the line
    // buffer, and clearing only the DOM would let the next frame paint every
    // cleared line straight back.
    if (state.logSink) state.logSink.reset("");
    else els.terminalOutput.textContent = "";
  });

  els.termCancelBtn.addEventListener("click", async () => {
    if (!state.activeJobId) return;
    try {
      await apiFetch(`/api/jobs/${encodeURIComponent(state.activeJobId)}/cancel`, { method: "POST" });
      showToast(t("toast_job_cancel_req"), "info");
    } catch (_) {}
  });

  // Docs switcher
  if (els.docsContent) els.docsContent.addEventListener("scroll", onGuideScroll, { passive: true });

  els.docSwitchBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      loadDocs(btn.dataset.doc);
    });
  });

  // Doctor check modal
  els.doctorBtn.addEventListener("click", openDoctorModal);
  if (els.updateBadge) els.updateBadge.addEventListener("click", openUpdateModal);
  const updateClose = document.getElementById("update-modal-close");
  if (updateClose) {
    updateClose.addEventListener("click", () =>
      document.getElementById("update-modal").classList.remove("open"));
  }
  const updateRecheck = document.getElementById("update-recheck-btn");
  if (updateRecheck) updateRecheck.addEventListener("click", recheckUpdate);
  const updateApply = document.getElementById("update-apply-btn");
  if (updateApply) updateApply.addEventListener("click", applyUpdate);

  const infoClose = document.getElementById("info-modal-close");
  if (infoClose) {
    infoClose.addEventListener("click", () =>
      document.getElementById("info-modal").classList.remove("open"));
  }

  els.doctorModalClose.addEventListener("click", () => {
    els.doctorModal.classList.remove("open");
  });

  bindV2();

  // Card preview
  bindDocPreview();
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    if (els.docPreviewModal && els.docPreviewModal.classList.contains("open")) {
      // One Escape, one thing undone. Closing the card straight out of full
      // screen loses your place as well as the frame, and the frame is the
      // one you just changed.
      if (isPreviewFullscreen()) setPreviewFullscreen(false);
      else closeDocPreview();
    } else if (els.doctorModal && els.doctorModal.classList.contains("open")) {
      els.doctorModal.classList.remove("open");
    }
  });

  // ------------------------------------------------------------------------
  // Pointer specular engine
  //
  // Writes --specular-x/--specular-y, as percentages of the element's own box,
  // onto the single glass surface under the pointer (SPECULAR_SURFACES) and
  // clears them when the pointer leaves it. rAF-throttled, paused during scroll
  // and while the tab is hidden, and off entirely under prefers-reduced-motion.
  //
  // Nothing is published on :root. Custom properties inherit, so a root-level
  // pointer position is read by every .card simultaneously, which is what made
  // the whole dashboard light up in unison instead of the one card being
  // pointed at. The CSS defaults the position to -999px for the same reason:
  // that off-canvas fallback is what keeps an un-hovered surface dark.
  // ------------------------------------------------------------------------

  // Only surfaces whose CSS actually paints a pointer specular belong here.
  // Icon buttons and stat pills are deliberately absent: they have no specular
  // layer, so tracking them was pure work for no pixels. The top bar, the core
  // band and the MAGI HUD monolith do paint one, on their own background rather
  // than a pseudo-element so it stays underneath their contents.
  // Must stay in step with the surfaces whose CSS actually paints
  // var(--glass-specular-layer). Listing one that does not is invisible work;
  // omitting one that does leaves a dead patch the pointer skates over.
  // .toast is deliberately absent -- it is small, transient and auto-dismisses,
  // so it keeps the fixed sheen and nothing tracks it.
  const SPECULAR_SURFACES =
    ".card, .modal-window, .modal-content, .glass-tuner-panel, .doc-preview-side, " +
    ".pane-list, .pane-view, .topbar, .core-band, .eva-hud-frame";

  function initLiquidGlassEngine() {
    if (typeof window === "undefined" || typeof document === "undefined") return;

    let isReducedMotion = false;
    let isReducedTransparency = false;
    let isScrolling = false;
    let scrollTimer = null;
    let rafId = null;
    let pendingPointerEvent = null;
    let activeTarget = null;

    function checkMediaPreferences() {
      if (window.matchMedia) {
        try {
          const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
          isReducedMotion = motionQuery.matches;
          const onMotionChange = (e) => {
            isReducedMotion = e.matches;
            if (isReducedMotion) resetGlassProperties();
          };
          if (motionQuery.addEventListener) {
            motionQuery.addEventListener("change", onMotionChange);
          } else if (motionQuery.addListener) {
            motionQuery.addListener(onMotionChange);
          }
        } catch (_) {}

        try {
          // Read only. Whether the material is on is decided by
          // state.liquidGlass (see initialLiquidGlass) so an explicit GLASS
          // choice is not stamped over by the OS setting on every change.
          isReducedTransparency = window
            .matchMedia("(prefers-reduced-transparency: reduce)")
            .matches;
        } catch (_) {}
      }
    }

    function clearTargetSpecular(el) {
      if (el && el.style) {
        el.style.removeProperty("--specular-x");
        el.style.removeProperty("--specular-y");
      }
    }

    function resetGlassProperties() {
      if (rafId && typeof cancelAnimationFrame === "function") {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      pendingPointerEvent = null;
      clearTargetSpecular(activeTarget);
      activeTarget = null;
    }

    function updateSpecularLighting() {
      rafId = null;
      if (!pendingPointerEvent || isReducedMotion || isScrolling) return;

      const ev = pendingPointerEvent;
      const clientX = ev.clientX || 0;
      const clientY = ev.clientY || 0;

      // Exactly one surface is lit: the one under the pointer, and nothing is
      // written to :root. Custom properties inherit, so the previous version --
      // which published --mouse-x/--mouse-y on documentElement as viewport
      // percentages -- was read by every .card on the page at once. Each card
      // painted its specular at the same relative position and the whole
      // dashboard lit up in unison, while the per-element override only ever
      // landed on the single card actually being hovered.
      const target = ev.target && typeof ev.target.closest === "function"
        ? ev.target.closest(SPECULAR_SURFACES)
        : null;

      if (target !== activeTarget) {
        clearTargetSpecular(activeTarget);
        activeTarget = target;
      }
      if (!activeTarget || typeof activeTarget.getBoundingClientRect !== "function" || !activeTarget.style) {
        return;
      }

      const rect = activeTarget.getBoundingClientRect();
      if (!rect || rect.width <= 0 || rect.height <= 0) return;
      const px = (((clientX - rect.left) / rect.width) * 100).toFixed(1);
      const py = (((clientY - rect.top) / rect.height) * 100).toFixed(1);
      activeTarget.style.setProperty("--specular-x", px + "%");
      activeTarget.style.setProperty("--specular-y", py + "%");
    }

    function onPointerMove(ev) {
      if (isReducedMotion || isScrolling) return;
      pendingPointerEvent = ev;
      if (!rafId && typeof requestAnimationFrame === "function") {
        rafId = requestAnimationFrame(updateSpecularLighting);
      }
    }

    function onPointerLeave() {
      resetGlassProperties();
    }

    function onScroll() {
      isScrolling = true;
      if (scrollTimer) clearTimeout(scrollTimer);
      scrollTimer = setTimeout(() => {
        isScrolling = false;
      }, 100);
    }

    checkMediaPreferences();

    document.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("pointerleave", onPointerLeave, { passive: true });
    document.addEventListener("pointercancel", onPointerLeave, { passive: true });
    document.addEventListener("pointerup", (e) => {
      if (e.pointerType === "touch") resetGlassProperties();
    }, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("blur", resetGlassProperties, { passive: true });
    window.addEventListener("resize", resetGlassProperties, { passive: true });
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) resetGlassProperties();
    }, { passive: true });
  }

  // Init
  applyTheme(state.theme);
  setLanguage(state.lang);
  loadInitialStatus();
  loadOpsCatalog();
  initBackgrounds();
  applyGlassSettings();
  applyLiquidGlass(state.liquidGlass);
  initLiquidGlassEngine();

  // Deep-link override: ?tab=melchior|operations|...
  try {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab && document.getElementById(`tab-${urlTab}`)) {
      switchTab(urlTab);
    }
  } catch (_) {}
})();
