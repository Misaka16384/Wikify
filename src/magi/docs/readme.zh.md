# MAGI

*[中文](README.md) | [English](README_en.md)*

**MAGI** 是一个 agent-native 的科研工作环境：人是驾驶员，LLM agent 是机体，确定性的 `magi` CLI 是拘束具——三者同步率越高，科研越快。它把学术论文（PDF/LaTeX）摄入、编译为 Obsidian 兼容的概念卡片知识库，并用三核架构管理完整的科研状态：

| 核 | 状态 | 由谁承载 | 回答的问题 |
|---|---|---|---|
| **MELCHIOR** | 认知状态（知识） | 概念/文献卡片 + SQLite 知识图谱 + claim/证据溯源 | 我们知道什么？为什么可信？ |
| **BALTHASAR** | 意图状态（工作） | [Beads](https://github.com/gastownhall/beads)（`bd`）科研任务图 | 我们在做什么？下一步是什么？ |
| **CASPER** | 检索状态 | 本地混合检索（FTS5 BM25 + sqlite-vec 向量 + RRF） | 此刻该读什么？ |

进入任意工作区先跑 **`magi sync`**——它输出**同步率**、三核状态和逐条可执行的修复提示。`magi radar` 是文献雷达：定时发现相关新论文，并侦察"知识上应引用我方论文却未引用"的候选。同一份 skills 通吃 Claude Code / Codex / Antigravity / opencode 等 CLI agent 宿主——`magi skills install` 会把它们放到各家各自找的地方。

任何命令的完整语法：`magi <command> --help`；全景：`magi --help`。

---

## 先跑起来

```powershell
pipx upgrade --install magi-research # 装或升级，重复跑没副作用
magi hub init                        # 在将来放所有课题的那个目录
cd topics/my-topic && magi init      # 建一个课题
magi ingest auto                     # 把 PDF 丢进 inbox/ 之后
```

然后在 Claude Code / Codex 里对 agent 说：**「把待编译的都编译了」**。这是唯一没有命令的一步——它要读论文、写卡片。跑完之后：

```powershell
magi index                           # 让它可检索
magi search "你想找的东西"
magi ui                              # 或者直接在 http://127.0.0.1:8737 里翻
```

任何时候卡住：**`magi sync`** 会告诉你这个工作区接下来该做什么，并把修复命令一起给出。**`magi guide`** 是完整手册，就在终端里。

---

## 🌟 项目展示

### MAGI MODE —— WebUI 战术主题

`magi ui` 打开本地网页控制台（默认 `http://127.0.0.1:8737`），自带三套主题：Institute 浅色 / 深色，以及压轴的 **EVA「MAGI MODE」**——一整套 NERV 驾驶舱视觉系统，分**红·战斗配置**与**蓝·静默值守**两个警戒态：

![MAGI MODE · 红·战斗配置](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-magi-red.jpg)
*红·战斗配置：三贤者 HUD、全屏 EVA 背景画、液态玻璃面板、视口边缘琥珀呼吸光。*

![MAGI MODE · 蓝·静默值守](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-magi-blue.jpg)
*蓝·静默值守：同一套 HUD 的真·浅色模式——白霜玻璃、深青墨水、青色边缘光。*

![液态玻璃](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-glass.jpg)
*iOS 材质液态玻璃：背景画透过每一块面板仍保持文字可读；右下角 ◐ 校准器实时调节模糊 / 不透明度 / CRT 扫描线。*

![知识图谱视图](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-graph.jpg)
*Obsidian 式力导向知识图谱：拖拽布局、滚轮缩放、悬停邻域聚焦、点击节点直接读卡片，未解析的 wikilink 渲染为幽灵节点。*

![卡片预览](https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-preview.jpg)
*点图谱里的任一节点，或检索结果里的任一条，卡片就地展开：公式由 KaTeX 排版、`[[链接]]` 可点、插图与 mermaid 图跟着一起画，左边正文右边目录与出入链。检索命中会直接滚到匹配的那一段。*

<img src="https://raw.githubusercontent.com/Misaka16384/magi/main/docs/webui-tuner.jpg" width="340" alt="◐ 材质校准器">

*◐ 校准器：模糊、不透明度、CRT 扫描线三个滑杆当场生效；下半是背景画选择器——点缩略图钉住你要的那几张，不选就按窗口比例自动轮换。*

- 深浅切换与 MAGI MODE **独立作用**：浅色基底 → 蓝态，深色基底 → 红态，模式内 ☀︎/☽ 直接切换警戒态
- 背景画默认按屏幕宽高比选图、切页随机轮换、平滑交叉淡入；也可以在 ◐ 面板的缩略图里**钉住某一张或几张**；把自己的图放进 `~/.config/magi/ui-backgrounds/{blue,red}/` 即可替换整套艺术
- 全部动画尊重 `prefers-reduced-motion`；界面中英双语一键切换

### 知识库成品

![知识图谱可视化](https://raw.githubusercontent.com/Misaka16384/magi/main/graph.png)
*自动生成的密集语义图谱，展示物理与数学概念。*

![编译出的文献卡片](https://raw.githubusercontent.com/Misaka16384/magi/main/note1.png)
*从排版混乱的 PDF 编译出的整洁文献卡片。*

![数学与概念提取](https://raw.githubusercontent.com/Misaka16384/magi/main/note2.png)
*从 LaTeX 源码提取并格式化的数学证明与引理。*

---

## 1. 架构：CLI、Skills 与宿主的分工

```text
你（驾驶员）
  └─ Claude Code / Codex / Antigravity / opencode（机体：负责推理、写作、判断）
       ├─ skills（随 CLI 分发）—— 教 agent「何时、为何」执行各条流水线
       └─ magi CLI（拘束具）  —— 所有确定性操作：摄入、图谱、检索、校验、任务、雷达
            └─ 持久状态在文件与数据库里：raw/ wiki/ output/ .beads/
```

- **CLI 负责语法**且自描述（`--help`）；**skills 只讲方法论**，不复制参数清单。
- 持久状态永远落盘；agent 的上下文是一次性的（fresh-context worker 模式）。
- JSON 输出（`--json`）的形状即未来 `magi mcp` 的工具契约。

---

## 2. 安装

### 2.1 一键安装（推荐）

**Windows（PowerShell）：**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
```

**macOS / Linux：**

```bash
curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
```

脚本会自动完成：装 [uv](https://docs.astral.sh/uv/)（如缺）→ 从 PyPI 安装 `magi-research`（自带 Python，无需预装）→ 执行 **`magi setup`**：安装 [Beads](https://github.com/gastownhall/beads)（`bd`）、拉取 Ollama 嵌入模型（如 Ollama 在场）、注册 Claude Code plugin（如 `claude` 在场）、报告检测到的 agent CLI、检测旧版 Wikify 残留 → 输出环境体检表。**幂等，重跑即升级。**

随时体检环境：

```powershell
magi setup --check
```

`magi setup` 的可选开关：`--no-beads` / `--no-models` / `--no-plugin` / `--no-skills`（不报告 agent CLI）/ `--remove-legacy`（删除检测到的旧版拷贝）。

体检表最后四行是你机器上的 agent CLI（claude / codex / agy / opencode）：装没装、当前工作区各装了几个技能。**`magi setup` 不会替你安装技能**——技能是按工作区装的，见 §2.4。

**只想要经典 Wikify 体验（纯知识库，不要任务管理）？** 用 `magi setup --kb-only`：跳过 Beads 安装，`magi sync` 不再提示任务相关内容（BALTHASAR 核显示 disabled 且不计入同步率）。随时 `magi setup --full` 恢复完整体验。雷达等其余功能均为按需调用，不用即无感。

### 2.2 手动安装（备选）

<details>
<summary>展开手动步骤</summary>

**CLI**（pipx 优先；没有 Python 3.10+ 就用 uv，它自带一个。装完之后 MAGI 再也不会调用它们）：

```powershell
# 一条命令管装和升级，幂等——已经是最新就什么都不做
pipx upgrade --install magi-research    # 需要机器上已有 Python 3.10+
                                        # （--install 需要 pipx ≥ 1.5；更老的版本用
                                        #   pipx install magi-research 首装、
                                        #   pipx upgrade magi-research 升级）

# 备选：uv，自带 Python 3.12，同样一条命令管装和升级
uv tool install --force magi-research

# 尝鲜未发布的改动: uv tool install --force git+https://github.com/Misaka16384/magi
# 本地开发: git clone … && cd magi && uv tool install .
```

**Beads**：Windows 用 `irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex`，macOS/Linux 见[官方文档](https://github.com/gastownhall/beads/blob/main/docs/getting-started/installation.md)。没有 `bd` 时 MAGI 优雅降级。

**Ollama 模型**：`ollama pull qwen3-embedding:0.6b`（向量检索）；`ollama pull glm-ocr`（本地 OCR，可选）。**不用自己 `ollama serve`**——本机 Ollama 只是没启动的话，MAGI 第一次用到它时会拉起来（每进程试一次；`config.yaml` 的 `ollama.autostart` 默认开，环境变量 `MAGI_NO_OLLAMA_AUTOSTART` 可关）。真没装、或配的是连不上的远端地址，检索才降级成 BM25-only。

</details>

### 2.3 可选外部工具

**一个都不装，MAGI 也能跑。** 每个只解锁一项具体功能，缺了不是故障——`magi setup --check` 不会把它们标红。

直接运行 `magi setup`，它会逐个问你要不要，并给出官网地址；说「不要」的以后就不再提。想重新选：`magi setup --optionals`。

| 工具 | 解锁什么 | 官网 |
|---|---|---|
| **Ollama** | 语义（向量）检索、本地离线 OCR | https://ollama.com/download |
| **Pandoc** | LaTeX 与 arXiv-HTML 摄入路线（保真度最高的两条） | https://pandoc.org/installing.html |
| **Poppler**（`pdftoppm`） | 本地 OCR 渲染 PDF 页面（配合 Ollama） | https://poppler.freedesktop.org/ |
| **pdflatex** | 公式深度校验（真去编译一遍）；缺失时回退 `pylatexenc` 轻量校验 | https://www.tug.org/texlive/ |
| **MinerU**（云服务，非本地程序） | 云端 PDF 转换，版面与公式识别强 | https://mineru.net/ |

`pandoc-crossref` 是可选的（缺了只是交叉引用降级，不影响转换）。从源码仓库装的话，Windows 版已放在 `vendor/windows/`——加入 PATH，或在 config.yaml 的 `tools.pandoc_crossref_path` 指定。用 pipx / uv 装的话它不在包里（一个 19MB 的 Windows 二进制不该发给所有平台），需要时从 https://github.com/lierdakil/pandoc-crossref/releases 自取。MinerU 的 token 填在工作区 config.yaml 的 `ocr.mineru_api_token`。

（历史依赖 ripgrep 已不再需要。）

### 2.4 Skills 安装（教 agent 用 MAGI）

20 个 skill 随 CLI 一起分发（`magi/skills/*/SKILL.md`，在 wheel 里），**在工作区里一条命令**装进你机器上所有 agent CLI，不需要 clone 仓库：

```powershell
cd <你的主题工作区>
magi skills install                   # 默认装进当前工作区（推荐），会列出检测到的 CLI 让你选
magi skills install --host codex      # 指定一个，跳过询问
magi skills install --host auto       # 检测到的全装
magi skills where                     # 每个 CLI 从哪读、装了几个、怎么触发
magi skills install --scope global    # 全机可用（技能只在工作区里有意义，慎用）
```

**默认不装全局**：这些技能是围着某个研究工作区转的，装进工作区还能随仓库分发给同事。

| 宿主 | 全局位置 | 项目位置 | 怎么触发 |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/技能名`（插件方式为 `/magi:技能名`），也按描述自动触发 |
| **Codex** | `~/.agents/skills/`（外加 `~/.codex/skills/`） | `<仓库根>/.agents/skills/` | `$技能名`，或按描述自选 |
| **Antigravity（agy）** | `~/.gemini/config/skills/` | `<仓库根>/.agents/skills/` | 按描述自动触发；`/skills` 浏览 |
| **opencode** | `~/.config/opencode/{commands,skills}/` | `.opencode/{commands,skills}/` | `/技能名`（commands）+ 按描述自动触发（skills），两者都装 |

> 不是每个 CLI 都有斜杠命令（Codex 用 `$`，agy 只按描述触发）。到哪都好使的用法是直接说需求：「摄入 inbox 里的论文」。`.agents/skills/` 是 Codex 和 agy 共读的跨 agent 约定，装一份两家都认；opencode 走自己的 `.opencode/{commands,skills}/`，安装器会另外给它写。

**Claude Code 插件路线**（一键脚本已自动执行，与上面的安装可共存）：

```powershell
claude plugin marketplace add Misaka16384/magi && claude plugin install magi
```

---

## 3. 快速上手（5 分钟）

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init                # 中央枢纽（wikis.json 注册表）
magi pm init                 # beads + 六种科研 issue 类型（会 git-init 本目录）

mkdir -p topics/quantum-toys && cd topics/quantum-toys
magi init --name "Quantum Toys" --scope "玩具模型中的量子现象"
# ↑ 自动注册进 hub；生成 CLAUDE.md / AGENTS.md（agent 入场协议）、config.yaml、scratch/
magi skills install          # 把技能装进这个工作区（会问装给哪个 CLI）

magi sync --fix              # 同步率 + 三核状态，并把能自动修的都跑掉
```

```text
MAGI SYSTEM ONLINE — sync ratio 90.0%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     0 ready · 0 in progress · 0 blocked
`- CASPER    (retrieval)  index fresh · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the wiki_ingest skill to start building the library
```

> 同步率随三核就绪程度浮动：上例是 beads 已初始化、索引已建的空库（90%）；如果还没跑 `magi pm init` 或 `magi index`，数字会更低——照着 hints 的提示逐条执行即可，不是配置错了。

然后把 PDF / LaTeX / 笔记丢进 `inbox/`，在你的 agent 里说一句"摄入 inbox 里的论文"（或直接 `/magi:wiki_ingest`），流水线就开始了。

> 📖 **完整使用指南随 CLI 分发**，三个入口读同一份内容：
>
> ```powershell
> magi guide                                # 列出十二章
> magi guide ingest                         # 读某一章
> magi guide --search "no workspace found"  # 把报错原文贴进去
> magi guide --symptoms                     # 全书「症状 → 原因 → 修法」索引
> ```
>
> 或 `magi ui` → **文档与指引** → **使用指南**（带章节导航），也可直接读 [`guide.zh.md`](./src/magi/docs/guide.zh.md)。按使用场景分十二章（先跑通 / 安装 / 迁移 / 建库 / 摄入 / 编译 / 图谱调优 / 检索 / 写作 / 雷达 / 看板 / 疑难速查），每一步都写清了**预期效果**和**不达预期怎么办**。卡住时也可以直接让 agent 用 `magi_guide` 技能替你查。

---

## 4. 研究生命周期（skills 总览）

在 agent 聊天框里以斜杠命令触发（Claude Code plugin 下带 `magi:` 前缀），或直接用自然语言描述需求：

| 阶段 | Skill | 作用 |
|---|---|---|
| 基建 | `wiki_hub_init` / `wiki_init` | 建 hub / 建主题工作区 |
| 摄入 | `wiki_ingest` | PDF/LaTeX/URL → Markdown。按阶梯自动选路：arXiv HTML → LaTeX 源码 → PDF 自己的文本层 → MinerU 云端 → 本地 OCR。**原生视觉转录不在阶梯上**——它按页计费、烧过用户一整周额度，只在你看过页数并明确要求后才走。MinerU Token 填入工作区 `config.yaml` 的 `ocr.mineru_api_token` |
| 摄入 | `wiki_ingest_ocr` | 完全本地离线 OCR 路线（Ollama `glm-ocr`） |
| 摄入 | `wiki_inbox` | 链接 / DOI / 引文 / 截图 → 排队走确定性管线，产物待你审批（`magi ingest url` + `batch-*`） |
| 编译 | `wiki_compile` | raw 文献 → 文献卡片 + 概念卡片（与 bd 任务闭环：`magi pm backlog-sync` 的 `magi-compile` 标签） |
| 编译 | `wiki_enrich` | 深扫已编译文献，补挖遗漏的定理/概念 |
| 关联 | `wiki_semantic_link` | Ollama 向量语义双链 + 高相似度自动去重合并（`magi link`） |
| 规范 | `wiki_tag_sync` / `wiki_concept_sync` | 标签本体论清洗 / 同义概念物理归并 |
| 质量 | `wiki_lint` | 死链自愈、frontmatter 修复、LaTeX 校验（`magi lint --fix`） |
| 质量 | `wiki_math_fix` | 把摄入弄坏的公式全抓出来，一条一条修（`magi math check --json`） |
| 图谱 | `wiki_graph_index` | 重建 SQLite 图谱（`magi graph build` / `magi graph query`） |
| 问答 | `wiki_ask` | 混合检索 + 图遍历 + 严格引用的零幻觉问答 |
| 审查 | `wiki_audit` | 跨论文矛盾审计（claim/证据验证 + 溯源落库） |
| 综述 | `wiki_research` | 多 subagent 并行调研 → 带 provenance 的综述报告 |
| 雷达 | `radar_review` | 对 radar 摘要做 triage：评分 → bd survey issues → 标记已审 |
| 写作 | `wiki_draft` | 在 `drafts/` 里写论文草稿：检索取证 → `magi bib` 导出引用 → pandoc 导出 LaTeX |
| 维护 | `wiki_hub_manager` | 主题归档 / 恢复（`magi hub archive/restore`） |
| 排查 | `magi_guide` | 按症状检索内置手册、读相关章节、给出手册里的确切命令（`magi guide`） |

### 全局知识库注册表（跨库检索）

每个工作区在 `magi index` 时自动注册进用户级注册表（`~/.config/magi/registry.json`）。**`magi search` 默认联邦检索：当前工作区 + 所有启用的已注册知识库**，结果带 `[kb:名称]` 来源标记：

```powershell
magi kb list                    # 查看全部已注册知识库及其可检索状态
magi kb disable <name>          # 把某个库排除出全局检索（enable 恢复）
magi search "..." --scope local # 只搜当前工作区（经典行为）
magi search "..." --kb <name>   # 定向搜某一个注册库
```

当前工作区永远默认可检索；其他库通过 `enable/disable` 控制。`magi kb register <path>` 可手动注册任意工作区，`unregister` 只移除注册项、不动文件。WebUI 里点开带 `[kb:名称]` 标记的命中，卡片照样就地展开、公式插图照样渲染——预览请求带着来源库名走，不用先切过去。

> 检索小抄：`--path 'raw/papers/2026-*<slug>*'` 可把语义检索限定在某一篇论文里；中英文问题都支持（中文经 CJK 二元组分词进 BM25，向量侧由嵌入模型天然跨语言）。

### 写作与引用（`drafts/` + `magi bib`）

草稿是工作区一等公民：放在 `drafts/`，被 `magi index` 收进检索（collection `drafts`），但不进图谱、不计同步率。引用直接从参考卡导出：

```powershell
magi bib pretko-2020            # 参考卡 frontmatter → BibTeX 条目
magi bib --all -o drafts/refs.bib
magi bib pretko-2020 --fetch    # 有 arxiv_id 时拉取 arXiv 官方 BibTeX
```

`magi ingest tex` 会把源码包里的 `.bib`/`.bbl` 原样保留在 markdown 旁边（`raw/papers/<slug>.bib`），文件名里的 arXiv ID 也会写入 frontmatter `arxiv_id:` 供雷达识别。完整写作流程见 `wiki_draft` skill。

> 关于 claims 的边界：`magi verify` 的 `verified` 意为**引文存在性验证**（引文确实逐字出现在来源里，含空白/连字/全角标点鲁棒匹配）——它不判断命题与引文在语义上是否一致，那一层由 LLM/人工审查负责（`magi claims verify` 是同一命令的别名）。

### 文献雷达（`magi radar`）

工作区 `config.yaml` 的 `radar:` 段配置 arXiv 分类、种子论文与我方论文后：

```powershell
magi radar harvest              # 手动收割：S2 推荐 ∪ arXiv 新文 → inbox/radar/日期-digest.md
                                # （候选按"与本库嵌入质心的余弦相关度"排序并标注 relevance 分；
                                #   config 里 radar.min_relevance 可设过滤阈值）
magi radar install-schedule     # 注册每日定时收割（Windows 任务计划程序 / macOS launchd；--uninstall 卸载）
magi radar citation-gap         # 侦察"该引我方论文却未引"的近期文献（四层漏斗，人工审核队列）
```

夜间确定性收割 + 下次会话由 `radar_review` skill 做 LLM triage——`magi sync` 会提示待审摘要。

### 本地 WebUI 看板（`magi ui`）

MAGI 内置了基于 Claude 纸墨美学的零构建本地轻量看板（FastAPI + 原生 SPA），用于直观查看三核状态、执行维护与检索实验：

```powershell
magi ui                       # 启动并在默认浏览器中打开本地看板（默认 http://127.0.0.1:8737，占用时自动探测 8738-8746）
magi ui --port 8080 --no-open # 自定义端口且不自启浏览器
```

包含 7 大面板：Dashboard（全局同步率、可一键执行的修复建议、注册库、config.yaml 关键字段编辑）、Melchior（认知网络/Claims/图谱 SQL/文献 BibTeX 复制/草稿）、Balthasar（Beads 任务）、Casper（混合检索实验台：联邦/集合/路径过滤）、Radar（简报阅读 + 审阅动作：标已审/收入 inbox/建阅读任务）、Operations & Danger Zone（服务端操作白名单 + 输入操作 ID 确认 + SSE 实时终端，任务历史落盘）与内置文档。API 与 `--json` 契约逐字段一致。

顶栏的 **⚡ MAGI MODE** 可一键切换 EVA/NERV 战术主题：三贤者三体阵列 HUD（MELCHIOR·1 / BALTHASAR·2 / CASPER·3 实时状态 + 同调率）、CRT 扫描线、蜂窝网格、警示条纹 Danger Zone 与启动同步序列。看板仅监听 `127.0.0.1`，带 Host 白名单防护，不发送任何 CORS 头。

---

## 5. 从 Wikify 迁移（老用户指引）

MAGI 是 Wikify 的全面重构：脚本集升级为统一 CLI，任务状态外接 Beads，新增混合检索、claim 溯源与文献雷达。**你的数据完全兼容**——`raw/`、`wiki/`、`inbox/` 格式未变。

### 5.1 迁移步骤（三条命令）

```powershell
# 1. 一键安装新版（§2.1 的脚本；magi setup 会顺带检测旧版拷贝并提示）
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. 删除旧安装拷贝（旧 SKILL.md 会误导 agent 调用已不存在的脚本路径）
magi setup --remove-legacy

# 3. 在 Hub 根目录跑一条命令（非破坏性，且会自动收尾）：
cd <你的KnowledgeHub>
magi migrate
#    ↳ 逐个 topic 补齐 CLAUDE.md / AGENTS.md / config.yaml / scratch/（沿用 config.md
#      里的旧标题与 scope）、把旧 config.yaml 里的 token/模型/阈值搬过来，重建
#      graph.db（新增 claims/evidence 表）与 _index.md；raw/ wiki/ 内容一字不动。
#      随后自动 magi pm init + 每个 topic 的 magi sync --fix（建索引、同步积压）。
#      --minimal 只迁移不收尾；单个 topic 目录里跑则只迁移该 topic。

# 收尾：hub 根 `magi pm init` 启用任务状态；各 topic `magi index` 建检索索引；`magi sync` 验收。
```

### 5.2 变化对照

| 旧（Wikify） | 新（MAGI） |
|---|---|
| `install.ps1` / `install.sh` **复制** `skills/`+`bin/` 到 agent 目录 | 同名脚本已改为**一键引导安装**（uv + CLI + `magi setup`，§2.1）；skills 随包分发，用 `magi skills install` 按工作区安装（§2.4） |
| `python <BIN>/llm-wiki.py lint --fix <dir>` | `magi lint --fix <dir>` |
| `python <BIN>/llm-wiki.py graph <dir>` | `magi graph build <dir>` |
| `python <BIN>/query-graph.py "<SQL>"` | `magi graph query "<SQL>"` |
| `python <BIN>/search-wiki.py <regex> <files>` | `magi grep <regex> <files>`；语义检索新增 `magi index` + `magi search` |
| `python <BIN>/ingest_helper.py --file ...` | `magi ingest add --file ...`（其余摄入脚本同理归入 `magi ingest *`） |
| `semantic_linker.py` | `magi link` |
| `verify_claims.py` | `magi verify`（v2：`--json`、空白归一化匹配、`--fetch-web`） |
| `requirements.txt` 手动装依赖 | 随 CLI 自动安装 |
| 任务/进度记在 `log.md` | Beads（`bd`）任务图；`log.md` 降级为人读叙事 |
| `~/.config/llm-wiki/config.json`（hub 路径） | `~/.config/magi/config.json`（旧路径仍被自动回退读取） |
| 依赖 ripgrep | 不再需要 |

---

## 6. Obsidian 集成

在 Obsidian 中**直接打开具体的主题工作区目录**（不要打开 Hub 根目录）。在 设置 → 档案与链接 → 排除档案 中添加两条正则，让图谱只显示纯粹的知识卡片：

```regex
/(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
```

```regex
/^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
```

---

## 7. 开发

```powershell
git clone https://github.com/Misaka16384/magi.git ; cd magi
uv venv && uv pip install -e .
.venv\Scripts\python.exe tests\smoke_test.py     # 端到端冒烟（含回归锁）
```

路线图与交接文档见 [ROADMAP.md](./ROADMAP.md)。
