"""Chinese descriptions for the CLI command catalogue.

Kept as a sidecar rather than a fourth slot in ``magi.cli._COMMANDS`` because
those English strings are what ``magi --help`` prints; the terminal stays
English, only the WebUI's command reference is translated.

Keys mirror ``_COMMANDS`` / ``_GROUP_HELP`` exactly. ``tests/test_cli_i18n.py``
fails if a command is added upstream without a translation here, so the table
cannot silently drift.
"""

from __future__ import annotations

COMMAND_HELP_ZH: dict[tuple[str, ...], str] = {
    # 工作区 / 中枢
    ("init",): "初始化课题工作区（raw/ wiki/ inbox/ output/ 目录骨架）",
    ("hub", "init"): "初始化多课题中枢（生成 wikis.json 注册表）",
    ("hub", "resolve"): "把课题标识解析成实际路径",
    ("hub", "list"): "列出进行中与已归档的课题",
    ("hub", "archive"): "归档一个进行中的课题",
    ("hub", "restore"): "恢复一个已归档的课题",
    ("hub", "register"): "把已存在的课题目录登记进中枢",
    ("sync",): "工作区体检：同步率与三核状态",
    ("ui",): "启动本地 MAGI 网页控制台",
    ("guide",): "阅读内置使用指南（分章阅读、--search 全文检索、--symptoms 故障索引）",
    ("each",): "在 hub 的每个课题里跑同一条命令（省掉 cd 循环）",
    ("skills", "list"): "列出随 magi 一起分发的 agent 技能",
    ("skills", "where"): "查看各个 agent CLI 从哪里加载技能，以及当前装了哪些",
    ("skills", "install"): "把技能装进你的 agent CLI（--scope global 全局 / project 仅当前目录）",
    ("skills", "uninstall"): "从某个 agent CLI 卸载 magi 的技能",
    ("setup",): "一键配置环境（beads、模型、插件）并做体检",
    ("migrate",): "迁移 magi 之前的 Wikify 工作区（中枢或单课题）",
    # 任务状态（Beads 桥接）
    ("pm", "init"): "初始化 beads 并写入科研专用的议题类型",
    ("pm", "status"): "查看 beads 是否可用及各类议题数量",
    ("pm", "backlog-sync"): "把尚未编译的原始文献转成 bd 议题",
    # 文献摄入
    ("ingest", "auto"): "自动选路摄入（按文件类型选转换器并自动收尾；不给路径就处理整个 inbox/）",
    ("ingest", "add"): "规范化收件箱文档并归档进 raw/",
    ("ingest", "assemble"): "把逐页转写结果拼接成一份完整文档",
    ("ingest", "mineru"): "用 MinerU 云端 OCR 把 PDF 转成 Markdown",
    ("ingest", "url"): "把 URL / DOI / arXiv 号排进摄入队列（不联网、不落库）",
    ("ingest", "batch-run"): "跑队列：获取、转换、跑验收检查，产物进暂存区待审",
    ("ingest", "batch-list"): "查看待人工审批的批次",
    ("ingest", "batch-decide"): "对某一条批次条目通过 / 拒绝 / 撤销",
    ("ingest", "batch-commit"): "把已全部决定的批次落进 raw/",
    ("ingest", "arxiv-html"): "抓 arXiv 官方 LaTeXML HTML 转 Markdown（保真度最高）",
    ("ingest", "tex"): "用 pandoc 把 LaTeX / arXiv 源码转成 Markdown",
    ("ingest", "ocr"): "用本地 Ollama OCR 把 PDF 转成 Markdown",
    ("ingest", "crop"): "裁剪 PDF 区域为 PNG，便于人工核对公式",
    ("ingest", "finalize"): "摄入收尾：清理 + 规范检查 + 建图 + 建索引",
    # 知识库
    ("wiki", "add-concept"): "新建或追加一张概念卡片",
    ("wiki", "refactor-concept"): "全库范围内合并或重命名一个概念",
    ("wiki", "context"): "抽取提到某个概念的所有段落",
    ("wiki", "chunk"): "把长文件切成适合模型窗口的片段",
    ("wiki", "placeholders"): "检测文档里残留的占位符与半成品文字",
    ("wiki", "uncompiled"): "列出还没编译成文献卡片的原始资料",
    ("wiki", "reindex"): "重新生成各目录的 _index.md 索引表",
    # 知识图谱
    ("graph", "build"): "构建或刷新 SQLite 知识图谱",
    ("graph", "browse"): "结构化浏览知识图谱（词条/链接/命题/标签/断链）",
    ("graph", "query"): "对知识图谱执行只读 SQL 查询",
    # 质量与校验
    ("lint",): "结构规范检查，并自动修复可修复的问题",
    ("stats",): "确定性的知识库统计",
    ("map",): "输出标题层级与公式块的结构地图",
    ("math", "format"): "整库自动修复 LaTeX 定界符与转义问题",
    ("math", "check"): "整库检出坏掉的公式，--json 出可逐条处理的工单",
    ("validate",): "按 schema 校验生成的论文/研究文档",
    ("verify",): "核验 CLAIM/FINDING 证据块",
    ("claims", "verify"): "magi verify 的别名（命题与证据核验）",
    ("bib",): "从文献卡片导出 BibTeX（--fetch 会抓取 arXiv 官方条目）",
    # 检索
    ("index",): "构建或刷新混合检索索引",
    ("search",): "混合检索：本地工作区 + 已启用的全局知识库",
    ("kb", "register"): "把一个工作区注册进全局知识库registry",
    ("kb", "list"): "列出已注册的知识库",
    ("kb", "enable"): "把某个知识库纳入全局检索",
    ("kb", "disable"): "把某个知识库移出全局检索",
    ("kb", "unregister"): "从注册表中移除一个知识库",
    ("grep",): "对指定文件做正则搜索",
    ("link",): "基于向量的概念关联与去重",
    # 文献雷达
    ("radar", "harvest"): "抓取并去重新的候选论文",
    ("radar", "citation-gap"): "侦察应当引用我们却没有引用的论文",
    ("radar", "status"): "查看雷达台账与待审阅简报",
    ("radar", "install-schedule"): "注册每日自动扫描任务",
    # 标签
    ("tags", "extract"): "抽取标签/别名倒排索引",
    ("tags", "apply"): "套用一份规范化的标签/别名映射",
}

GROUP_HELP_ZH: dict[str, str] = {
    "hub": "多课题中枢管理",
    "kb": "全局知识库注册表（跨工作区检索）",
    "ingest": "文献摄入（PDF/LaTeX → Markdown）",
    "wiki": "概念卡片与文献卡片操作",
    "graph": "SQLite 知识图谱",
    "math": "LaTeX 公式格式化与校验",
    "pm": "对接 Beads (bd) 的任务状态桥",
    "claims": "命题与证据溯源",
    "radar": "文献雷达（定时发现）",
    "tags": "标签本体规范化",
    "skills": "按 CLI 宿主安装 agent 技能",
}


def command_help_zh(key: tuple[str, ...]) -> str:
    """Chinese help for a command key, or '' when untranslated."""
    return COMMAND_HELP_ZH.get(tuple(key), "")


def group_help_zh(group: str | None) -> str:
    """Chinese help for a command group, or '' when there is no group."""
    return GROUP_HELP_ZH.get(group, "") if group else ""
