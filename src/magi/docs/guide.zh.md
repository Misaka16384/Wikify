# MAGI 使用指南

从零安装，到跑出一个能查、能引、能写的文献库。

每章按同一个节奏：**做什么 → 怎么做 → 应该看到什么 → 没看到该怎么办**。左侧目录可随时跳转；页面内 `Ctrl+F` 直接全文搜索；每段命令右上角可一键复制。

---

## 先跑通一遍 {#start}

MAGI 由三层组成，分工不重叠：

| 层 | 是什么 | 你怎么用 |
|---|---|---|
| **magi CLI** | 所有确定性操作：摄入、建图、检索、校验、任务、雷达 | 终端里敲，或让 agent 替你敲 |
| **skills** | 教 agent「何时、为何」调用哪条流水线 | 在 Claude Code / Codex 里说一句话触发 |
| **工作区** | 落盘的知识：`raw/` `wiki/` `output/` `drafts/` | 用 Obsidian、编辑器、本看板直接看 |

agent 的上下文是一次性的，**状态永远在磁盘上**。所以任何一步中断都能原地续跑。

> [!WARN]
> **agent 不是可选项。** 从 `raw/` 原始文献到 `wiki/` 概念卡这一步是理解与综合，没有对应的 CLI 命令——它只能由 `wiki_compile` 技能驱动 LLM 完成。只装 CLI 不接 agent 宿主，你可以摄入文献、做关键词检索，但永远得不到概念卡、知识图谱和带引用的问答。第 2.4 节讲怎么接。

### 三条起步路线

**① 全新用户**——按第 2 章装好，然后：

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init                # 中央枢纽（wikis.json 注册表）
magi pm init                 # 任务系统（会 git-init 本目录）

mkdir topics\quantum-toys ; cd topics\quantum-toys
magi init --name "Quantum Toys" --scope "玩具模型中的量子现象"
magi skills install          # 把技能装进这个工作区（见 2.4）

magi sync                    # 验收：同步率 + 三核状态 + 下一步提示
```

**② Wikify 老用户**——数据不用动，直接看第 3 章，三条命令迁移。

**③ 只想先试试**——不建 hub，随便找个空目录 `magi init` 就能用，之后 `magi hub register <slug>` 再收编。

### 这份手册怎么读 {#howto-read}

同一份内容有三个入口，挑顺手的：

| 入口 | 适合 | 怎么用 |
|---|---|---|
| **看板** | 坐下来通读、边看边操作 | `magi ui` → 文档与指引 → 使用指南 |
| **终端** | 手上正卡着一条命令 | `magi guide` 列章节；`magi guide ingest` 读某章 |
| **问 agent** | 懒得自己找 | 直接把报错贴给 agent，让它查 |

终端里最有用的三条：

```powershell
magi guide                          # 列出全部章节（编号 + 锚点 + 一句话简介）
magi guide graph                    # 按编号 7、锚点 graph 或标题片段读某一章
magi guide --search "no workspace found"   # 全文检索：把报错原文贴进去
magi guide --symptoms               # 全书的「症状 → 原因 → 怎么修」索引
```

`--json` 是给 agent 用的机器格式，`--lang en` 切英文。

**让 agent 直接排查**：仓库自带 `magi_guide` 技能，随插件一起装好。你只要把报错原样贴进对话，或者说一句「用 magi_guide 查一下」，它会先在手册里检索症状、读相关章节、再跑 `magi sync` / `magi setup --check` 确认现状，最后给你手册里那条确切的命令——而不是凭记忆编一个参数。

> [!NOTE]
> 手册里的每条命令都对着真实 CLI 校验过，测试会保证它不漂移。所以 agent 引用手册比它凭印象作答可靠得多——遇到 MAGI 相关的问题，值得明确要求它「查手册再回答」。

### 怎么读 `magi sync`

`magi sync` 是每次进场的第一条命令，也是每次卡住时的第一条命令：

```text
MAGI SYSTEM ONLINE — sync ratio 33.3%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     beads offline
`- CASPER    (retrieval)  no index yet
  -> magi pm init   # initialize beads at the hub root
```

三核分别是知识、任务、检索。**最后一行 `->` 就是下一步该干什么**，照做即可。

同步率是三核就绪度的加权平均（只计算「当前适用」的核）：

- **MELCHIOR** = 0.55 图谱新鲜度 + 0.25 待编译积压 + 0.20 命题健康度
- **BALTHASAR** = 0.6 任务库可达 + 0.4 状态可读（`--kb-only` 模式下整核不计入）
- **CASPER** = 0.7 索引新鲜度 + 0.3 向量覆盖率

> [!NOTE]
> 同步率不是「知识量」评分。空库照样能拿 MELCHIOR 满分——它只惩罚**过期、积压、未核验**，不惩罚「还没开始」。所以刚建的库显示 33.3% 很正常：那是「三核里只有知识核在线」。跑完 `magi pm init` 和 `magi index` 就会跳上去。
> 不在任何工作区里跑时，同步率显示为空而不是 0——它不会编一个数字给你。

---

## 安装 {#install}

### 一键安装（推荐）{#install-oneline}

**先决条件：`git` 必须在 PATH 上**（安装脚本要用它拉仓库）。没有的话 Windows 用 `winget install Git.Git`，其他平台用包管理器。

**Windows（PowerShell）**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
```

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
```

脚本按顺序做三件事：

1. 缺 [uv](https://docs.astral.sh/uv/) 就先装 uv；
2. `uv tool install --force --python 3.12 magi-research`——从 PyPI 装，uv 自带 Python 3.12，**你不需要预装 Python**；
3. 执行 `magi setup`：装 Beads（`bd`）、拉 Ollama 嵌入模型、注册 Claude Code 插件、检测旧版 Wikify 残留，最后打印体检表。

**幂等**：重跑同一条命令就是升级。

> [!EXPECT]
> 终端出现 `=== MAGI environment ===` 体检表，`magi --version` 打印版本号。

> [!FIX]
> - **`magi` 找不到**：`uv tool update-shell` 只改了配置文件，当前窗口的 PATH 还是旧的。**开一个新终端**（两个安装脚本最后都会提醒这句）。仍然不行就手动把 `~/.local/bin`（Windows：`%USERPROFILE%\.local\bin`）加进 PATH。
> - **提示 `git is required`**：装 git 后重跑。
> - **提示 `magi setup reported issues`**：安装本体成功了，只是配套组件某一步失败。单独跑 `magi setup` 看具体是哪一项，或 `magi setup --check` 只看现状。
> - **公司网络拦 GitHub**：走下面的手动安装，或先配好代理再跑。

### 手动安装、升级、卸载 {#install-manual}

```powershell
uv tool install magi-research           # 安装（pipx install magi-research 也行）
uv tool install --force magi-research   # 升级
uv tool uninstall magi-research         # 卸载
uv tool list                            # 看装了什么版本

# 想试还没发版的改动：
uv tool install --force git+https://github.com/Misaka16384/magi
```

装完随时体检：

```powershell
magi setup --check
```

`magi setup` 的开关：

| 开关 | 作用 |
|---|---|
| `--check` | 只体检，不装任何东西、不删任何东西 |
| `--no-beads` | 跳过 Beads 安装 |
| `--no-models` | 跳过 Ollama 模型拉取 |
| `--no-plugin` | 跳过 Claude Code 插件注册 |
| `--remove-legacy` | 删除检测到的旧版 Wikify 拷贝（唯一的破坏性开关） |
| `--kb-only` / `--full` | 切换「纯知识库」与「完整」档位 |

> [!TIP]
> 只想要纯知识库、不要任务管理？`magi setup --kb-only`：跳过 Beads，`magi sync` 里 BALTHASAR 核显示 disabled 且不计入同步率。档位存在 `~/.config/magi/settings.json`，随时 `magi setup --full` 恢复。

### 全局装还是按项目装 {#install-scope}

这是最常问反的一件事。**CLI 全局装一份就够，工作区才是「按项目」的。**

| 东西 | 装在哪 | 数量 |
|---|---|---|
| `magi` CLI | 用户级（`uv tool install`），在 PATH 上 | 全机一份 |
| skills | 每个 agent 宿主各自的插件目录 | 每个宿主一份 |
| 工作区 | 你的课题目录 | 每个课题一个 |
| 全局配置与注册表 | `~/.config/magi/`（Windows 是 `C:\Users\<你>\.config\magi\`，**不是** AppData） | 全机一份 |

装一次 CLI，之后每开一个新课题只需要 `magi init`。

> [!WARN]
> 真·项目内安装（`uv venv && uv pip install -e .`）只推荐给要改 MAGI 源码的人。这样装出来的 `magi` **不在 PATH 上**，只能用 `.venv\Scripts\python.exe -m magi.cli ...` 调用；而 skills、Claude Code 的 SessionStart 钩子、雷达定时任务全都是按裸命令名 `magi` 去 PATH 里找的，它们会找不到。日常使用请用 `uv tool install`。

### 让你的 CLI agent 学会用 MAGI {#install-hosts}

这一步不是锦上添花：**知识库的编译环节只在 agent 里跑**（见第 6 章）。

**在工作区里跑一条命令**，你机器上所有 agent CLI 就都学会了：

```powershell
cd <你的主题工作区>
magi skills install              # 装进这个工作区（默认，推荐）
magi skills where                # 看每个 CLI 从哪读、现在装了几个
magi skills install --dry-run    # 只看会写哪些文件，不动手
magi skills uninstall            # 撤掉
```

技能文件随 CLI 一起分发，**不需要 clone 仓库、不需要联网**。

> [!WARN]
> **默认只装进当前工作区，不装全局。** 这 18 个技能都是围着某个研究工作区转的（往 `raw/` 摄入、编译进 `wiki/`、查这个库的图谱），装到全局意味着你打开任何一个无关项目，agent 都要背着它们。真想全机可用：`magi skills install --scope global`（命令会提醒你一次）。
> 装在工作区里还有个好处：这些文件跟着仓库走，同事 clone 下来就有。

| 宿主 | 全局位置 | 项目位置 | 怎么触发 |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/技能名`，也会按描述自动触发 |
| **Codex** | `~/.agents/skills/`（外加 `~/.codex/skills/`） | `<仓库根>/.agents/skills/` | `$技能名`，或让它按描述自选 |
| **Antigravity（agy）** | `~/.gemini/config/skills/` | `<仓库根>/.agents/skills/` | 说出名字，或按描述自动触发；`/skills` 可浏览 |
| **opencode** | `~/.config/opencode/commands/` + `skills/` | `.opencode/commands/` + `skills/` | `/技能名` |

> [!NOTE]
> **不是每个 CLI 都有斜杠命令。** Claude Code 和 opencode 有；Codex 用 `$技能名`；agy 只按描述自动触发（`/skills` 只是个浏览面板）。所以最稳的用法在哪都一样：**把你要做的事说出来**——「摄入 inbox 里的论文」「查一下这个报错」——描述匹配上就会自动加载对应技能。
> `.agents/skills/` 是跨 agent 的公共约定：Codex、agy、opencode 都会读它，所以项目级安装一份就能同时喂饱三个。

**Claude Code 还可以走插件**（一键脚本已自动执行）：技能带 `magi:` 命名空间出现，还附带一个 SessionStart 钩子每次自动跑 `magi sync`：

```powershell
claude plugin marketplace add Misaka16384/magi
claude plugin install magi
claude plugin install <本地仓库目录>      # 本地开发模式
```

插件和 `magi skills install` 可以共存——前者给你 `/magi:技能名`，后者给你 `/技能名`。

**任何其他 agent**——工作区里的 `CLAUDE.md` 和 `AGENTS.md`（两份内容完全一致）就是入场协议：它告诉 agent 进场先跑 `magi sync`、三核对应哪些命令、卡住时用 `magi guide --search` 查手册，以及「不许凭记忆回答研究问题」。只要宿主会读其中之一就能开工；实在不认，把 `magi --help` 贴给它也行。

> [!EXPECT]
> `magi skills where` 里 project 那几行显示 18/18；在**这个工作区目录里**重开一个 agent 会话，输入 `/` 能看到技能（Claude Code / opencode），或者直接说「摄入 inbox 里的论文」它就动手。`magi setup --check` 的体检表也会显示当前工作区各 CLI 的技能数。

> [!FIX]
> - **装完看不到**：技能是启动时扫描的——**在工作区目录里重开一个会话**（项目级技能只在从该目录启动时可见）。
> - **不确定装到哪了**：`magi skills where` 会打印每个 CLI 的真实路径与数量。
> - **提示 skipped**：目标位置已有同名文件且不像我们写的，出于安全没覆盖。确认后 `magi skills install --force`。
> - **agent 调用了不存在的脚本路径**（`python bin/llm-wiki.py ...`）：旧版 Wikify 的 SKILL.md 还在，跑 `magi setup --remove-legacy`。
> - **想卸载**：`magi skills uninstall [--host X] [--scope project]`。
> - `magi setup`、`magi migrate`、`magi ui` **没有对应技能**——纯 CLI 命令，直接敲。

### 外部工具（按需）{#install-tools}

| 工具 | 谁需要它 | 缺了会怎样 |
|---|---|---|
| **Beads**（`bd`） | 任务待办 | 任务功能降级，其余不受影响 |
| **Ollama** + `qwen3-embedding:0.6b` | 语义检索、语义连边、雷达相关度打分 | 检索自动退回关键词匹配；`magi link` 直接报错退出 |
| **Ollama** + `glm-ocr` | 全本地 OCR 摄入 | 只能走云端 OCR 或 LaTeX 路线 |
| **Pandoc** | `magi ingest tex` | 无法处理 arXiv 源码包 |
| **Poppler**（`pdftoppm`） | 本地 OCR 渲染页面 | 本地 OCR 直接报错 |
| **pdflatex** | 数学公式深度校验 | 自动回退 `pylatexenc` 轻量校验 |
| **Ghostscript** | LaTeX 源码里的 EPS 插图转位图 | EPS 原样拷贝，markdown 里不显示 |

```powershell
ollama pull qwen3-embedding:0.6b     # 向量检索（约 640MB）
ollama pull glm-ocr                  # 本地 OCR（可选）
```

Windows 的 `pandoc-crossref.exe` 已内置于仓库 `vendor/windows/`：加入 PATH，或在工作区 `config.yaml` 的 `tools.pandoc_crossref_path` 里指路。

体检表最后四行是你机器上的 agent CLI（claude / codex / agy / opencode）：装没装、技能装了几个。缺技能时它会直接给出补装命令。

> [!WARN]
> `magi setup --check` 的体检只查 PATH，**不读** `config.yaml` 里的 `tools.*` 路径。所以体检表显示 `[-] pdftoppm`、而你已经在 config 里配好了绝对路径时，实际摄入是能跑的——以实跑为准。

---

## 从 Wikify 迁移 {#migrate}

MAGI 是 Wikify 的重构版：脚本集变成统一 CLI，任务状态外接 Beads，新增混合检索、命题溯源与文献雷达。**`raw/`、`wiki/`、`inbox/` 的格式没有变，你的数据完全兼容。**

### 三条命令 {#migrate-steps}

```powershell
# 1. 装新版（第 2 章的一键脚本）
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. 删掉旧安装拷贝——旧 SKILL.md 会指挥 agent 去调已经不存在的脚本
magi setup --remove-legacy

# 3. 在 Hub 根目录一键迁移全部主题（非破坏性）
cd <你的 KnowledgeHub>
magi migrate
```

`magi migrate` 会自动判断你给的路径是 hub 还是单个主题：hub 模式一次迁移 `topics/` 下所有**未归档**主题；单主题模式只迁移当前这个。

**它只做加法**：补齐缺失的 `CLAUDE.md` / `AGENTS.md` / `config.yaml` / `scratch/` 和各级 `_index.md`，然后重建 `output/graph.db`（新增 claims/evidence 表）和 `wiki/{concepts,references}/_index.md`。已存在的文件一律跳过——`raw/`、`wiki/` 内容、`config.md`、`log.md` 一个字都不会改。

> [!NOTE]
> `magi migrate` **没有** `--dry-run`，也**没有** `--force`。非破坏性是写死在实现里的，不靠开关保证：它调用脚手架时从不传 `--force`，所以只可能新建缺失文件。重复跑是安全的，第二次会走「刷新索引」分支。

收尾三步：

```powershell
magi pm init      # 在 hub 根目录：启用任务系统（一个 hub 一个任务库）
magi index        # 在每个主题目录：建检索索引
magi sync         # 验收
```

> [!EXPECT]
> 每个主题打印一段 `Migrating workspace: <path>`，随后 `magi graph build: ok` / `magi wiki reindex: ok`，最后给出「Recommended next steps」。

> [!FIX]
> - **hub 模式最后说 `N/N topics migrated` 但中间有 `FAILED`**：这个汇总行和退出码不反映子步骤失败（已知缺陷）。**自己在输出里搜 `FAILED`**，对报错的主题单独进目录重跑 `magi migrate`。
> - **hub 模式没提醒建索引**：hub 模式只提示 `magi pm init`，不会提醒每个主题跑 `magi index` / `magi sync`。手动补上。
> - **迁移后 agent 还在提旧命令**：`magi setup --remove-legacy` 没跑，或宿主技能缓存没刷新——重启 agent 会话。
> - **某个主题没被迁移**：hub 模式跳过 `topics/.archive/` 和既没有 `wiki/` 也没有 `raw/` 的目录。进那个目录单独跑 `magi migrate`，再 `magi hub register <slug>`。
> - **直接抛 Python 异常**：脚手架步骤没有异常保护，常见原因是文件被占用/权限不足（Windows 上编辑器锁了 `CLAUDE.md`）。关掉占用程序重跑即可，不会有半成品。

> [!WARN]
> `magi setup --remove-legacy` 删的不只是那个 `llm-wiki.py`：一旦在 `~/.claude/bin`（或 `~/.gemini/bin`）里发现它，**整个 bin 目录会被递归删除**，没有二次确认。跑之前先看一眼那个目录里有没有你自己放的东西。

### 命令对照表 {#migrate-map}

| 旧（Wikify） | 新（MAGI） |
|---|---|
| `python <BIN>/llm-wiki.py lint --fix <dir>` | `magi lint --fix <dir>` |
| `python <BIN>/llm-wiki.py graph <dir>` | `magi graph build <dir>` |
| `python <BIN>/query-graph.py "<SQL>"` | `magi graph query "<SQL>"`（或免 SQL 的 `magi graph browse`） |
| `python <BIN>/search-wiki.py <regex> <files>` | `magi grep <regex> <files>` |
| `python <BIN>/ingest_helper.py --file ...` | `magi ingest add --file ...` |
| `semantic_linker.py` | `magi link` |
| `verify_claims.py` | `magi verify` |
| `requirements.txt` 手动装依赖 | 随 CLI 自动安装 |
| 进度记在 `log.md` | Beads 任务图；`log.md` 降级为人读叙事 |
| `~/.config/llm-wiki/config.json` | `~/.config/magi/config.json`（旧路径永久保留自动回退，不需要手工搬） |
| 依赖 ripgrep | 不再需要 |

---

## 建立文献库 {#workspace}

### Hub 还是单主题 {#workspace-shape}

- **单主题**：一个课题、一个目录，`magi init` 就完事。
- **Hub**：多个课题共用一个根目录，共享**同一个任务库**和主题注册表。跨课题检索、统一任务视图靠它。

推荐一开始就建 Hub——多一条命令，以后加课题零成本。

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init          # 生成 topics/、topics/.archive/、wikis.json、_index.md、log.md
magi pm init           # 任务系统装在 hub 根（会 git-init）

mkdir topics\my-topic ; cd topics\my-topic
magi init --name "显示名" --scope "一句话说清这个库收什么、不收什么"
```

主题目录建在 `<hub>/topics/` 下面时，`magi init` 会**自动注册进 hub**。建在别处就手动 `magi hub register <slug> --path <相对路径>`。

`--scope` 不是装饰：它会写进 `CLAUDE.md`，成为 agent 判断「这篇该不该收、这个概念算不算本库范围」的依据。**写得越具体，后面自动化的判断越准。**

### `magi init` 生成了什么 {#workspace-layout}

```text
my-topic/
├─ CLAUDE.md / AGENTS.md   agent 入场协议（两份内容相同）
├─ config.md               本库的人读说明（标题 + 研究范围）
├─ config.yaml             本工作区配置（OCR、模型、雷达……见第 5 章）
├─ log.md                  人读的流水叙事
├─ inbox/                  待处理投喂区（PDF 丢这里）· .processed/ 存已处理原件
├─ raw/                    摄入后的原始文献 Markdown
│   articles/ papers/ repos/ notes/ data/
├─ wiki/                   编译产物
│   concepts/  概念卡    references/ 文献卡    topics/  专题    theses/ 论断报告
├─ output/                 graph.db、index.db、雷达账本
└─ scratch/                agent 的草稿纸，可随时清空
```

除 `inbox/` 和 `scratch/` 外每个目录都会生成 `_index.md` 目录表。

> [!NOTE]
> **`drafts/` 不在这个列表里**——`magi init` 不创建它。第一次写 `drafts/xxx.md` 时它自然出现，工具链（检索、lint）已经认得这个目录。见第 9 章。

> [!TIP]
> 用 Obsidian 打开**主题目录**（不要打开 Hub 根）。在 设置 → 档案与链接 → 排除档案 里加两条正则，图谱就只剩纯知识卡片：
> ```regex
> /(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
> ```
> ```regex
> /^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
> ```

### 主题管理 {#workspace-hub}

```powershell
magi hub list                     # 全部主题；--archived 连归档的一起列；--json 机器可读
magi hub resolve <hub路径> <slug>  # 主题 slug → 绝对路径（脚本里 cd 用）
magi hub register <slug> --path topics/<slug>   # 收编一个已初始化的目录
magi hub archive <slug> --reason "结题"          # 归档：移进 topics/.archive/，不删文件
magi hub restore <slug>           # 恢复
```

`magi hub list` 会自我修复：磁盘上有、注册表里没有的主题会被列出来并标注 `registry repair needed`，按提示 `register` 一下即可。

### MAGI 怎么找到「当前工作区」{#workspace-discovery}

所有命令都靠**从当前目录向上走**（最多 30 层）来定位工作区：

- **主题根**的判定：目录里既有 `wiki/` 或 `raw/`，又有 `config.md` / `log.md` / `config.yaml` 三者之一。
- **Hub 根**的判定：既有 `wikis.json` 又有 `topics/`。

**没有任何环境变量能改这个行为**——不存在 `MAGI_HOME`。要跨目录操作就用 `--topic-dir` / `--hub` / `--db` 这类显式参数。

> [!FIX]
> - **报 `no workspace found`**：你站在 hub 根或更上层。`cd` 进具体主题目录，或加 `--topic-dir <路径>`。
> - **`magi init` 重跑说 `Skipping existing ...`**：这不是错误。默认不覆盖已有文件；真想按新的 `--name/--scope` 重新生成，加 `--force`（会丢掉你对这些文件的手工修改）。

> [!WARN]
> **别把工作区套娃**。`magi init` 不检查父目录是不是已经是工作区。如果你在某个主题的 `raw/` 里面又 init 了一个工作区，外层的待编译积压计数会把内层的 `raw/*.md` 全算进来，同步率会莫名其妙地掉。已经套了就把内层挪到外层的 `raw/ wiki/ inbox/ output/` 之外。

---

## 摄入文献 {#ingest}

### 四条路线，怎么选 {#ingest-routes}

| 命令 | 适用 | 依赖 | 质量 |
|---|---|---|---|
| `magi ingest tex` | arXiv 源码包（`.tar.gz`）或 `.tex` | Pandoc | **最好**——公式、引文、编号原生保真 |
| `magi ingest mineru` | 一般 PDF（含扫描件） | MinerU 云端 token | 好，版面/公式识别强 |
| `magi ingest ocr` | 一般 PDF，要求全离线 | Ollama + poppler | 中等，逐页视觉转录 |
| `magi ingest add` | 已经是 Markdown/文本的材料 | 无 | 只做归档与 frontmatter 注入 |

**能拿到 arXiv 源码包就优先走 `tex`**——它保留 `.bib`/`.bbl` 到 markdown 旁边，还会把 arXiv ID 写进 frontmatter 供雷达和 `magi bib` 使用。

另外两条辅助路线：`magi ingest assemble` 把 agent 自己逐页转录出来的 `page_1.md, page_2.md…` 按页码拼成一篇；`magi ingest crop` 把 PDF 的某一块裁成 PNG，用来肉眼核对公式。

### 需要配置什么 {#ingest-config}

配置写在**工作区根目录的 `config.yaml`**（找不到才回退 `~/.config/magi/config.yaml`；两者不合并，就近的那份完全覆盖全局那份）。

```yaml
ocr:
  mineru_api_token: ""      # ← MinerU 云端 OCR 必填，从 https://mineru.net 拿
  dpi: 130                  # 本地 OCR 渲染精度；低于 110 会认错密集下标
  timeout: 180              # 单页 OCR 超时（秒）

models:
  ocr: glm-ocr                    # 本地 OCR 模型（glm-ocr / qwen3-vl / qwen3-vl:4b ...）
  embedding: qwen3-embedding:0.6b # 语义检索与语义连边共用

ollama:
  base_url: http://127.0.0.1:11434

tools:                      # 只有在这些程序不在 PATH 上时才需要填
  pandoc_path: ""
  pandoc_crossref_path: ""
  pdftoppm_path: ""
```

`OLLAMA_HOST` / `PANDOC_PATH` / `PANDOC_CROSSREF_PATH` / `PDFTOPPM_PATH` / `PDFIMAGES_PATH` 这五个环境变量**优先级高于 config.yaml**，其余所有键都只能改文件。

> [!WARN]
> **YAML 写错不会报错。** 自动发现的 `config.yaml` 解析失败时，程序静默回退到内置默认值，一个字都不提示。改完拿这条验一下：
> ```bash
> python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"
> ```

> [!NOTE]
> `ocr.use_mineru` 这个键**只对 agent 有效**——是给 `wiki_ingest` 技能读的路由提示。你在终端直接敲 `magi ingest mineru` 时它不看这个键，只看 token 有没有配。同理 `pdf.quality` 和 `output.encoding` 目前是空转的，改了没有任何效果。
> 还有一批键 `magi init` 生成的模板里没有、但代码确实会读：整个 `tools:`、`pdf:`、`output:` 段，以及 `radar.min_relevance` / `radar.own_arxiv_ids` / `radar.citation_gap.*`。需要时自己加进去就行。

### 跑一遍 {#ingest-run}

最省事的方式：把 PDF 丢进 `inbox/`，然后对 agent 说「摄入 inbox 里的论文」（或 `/magi:wiki_ingest`）。它会选路线、转格式、收尾。想手工跑：

```powershell
# arXiv 源码包（最推荐）
magi ingest tex 2401.12345.tar.gz -o raw/papers

# 云端 OCR
magi ingest mineru paper.pdf -o raw/papers

# 本地 OCR（可只跑一段页码）
magi ingest ocr paper.pdf -o raw/papers --pages 1-12

# 已经是 markdown
magi ingest add --file inbox/notes.md --type notes --move
```

**每一条路线跑完都必须收尾**：

```powershell
magi ingest finalize inbox/paper.pdf --topic-dir . --md-file raw/papers/2026-08-20-paper.md
```

`finalize` 才是真正把文件接进知识库的那一步：把原件归档到 `inbox/.processed/`、清理 frontmatter、把图片链接转成 Obsidian 双链、跑公式格式化与校验，最后 `magi lint --fix` + `magi graph build` + `magi wiki reindex`。

> [!WARN]
> 最后那三条是**对整个工作区**跑的，不只是这一篇；而且**任何一条失败都只打印一行 warning，不中断、不改退出码**。第一次摄入时留意终端里有没有 `Warning: 'magi lint' failed` 这类行——它会在之后每次摄入时静默重复。看到了就单独把那条命令跑一遍看真实报错。

> [!TIP]
> 批量摄入时别每篇都重建图谱：每篇加 `--skip-lint`，全部结束后再跑一次 `magi ingest finalize none --topic-dir . --lint-only`。

> [!EXPECT]
> `raw/<type>/YYYY-MM-DD-<slug>.md` 出现，插图在同级 `images/`；终端最后一行是 `Successfully converted and saved to ...` 或本地 OCR 的 `✓ 转换完成！`。

### 摄入质量不达标怎么办 {#ingest-trouble}

| 症状 | 原因 | 处理 |
|---|---|---|
| `Error: mineru_api_token not configured` | token 没配（报错信息里不会告诉你去哪拿） | 去 [mineru.net](https://mineru.net) 注册取 token，填进 `ocr.mineru_api_token` |
| `MinerU extraction timed out after 30 minutes` | 云端排队/文档太大；**超时时长写死，无法调** | 拆分 PDF，或改走 `magi ingest ocr` |
| `MinerU Processing failed` | 这个 PDF 云端解析不了 | 换本地 OCR 路线 |
| `Pandoc conversion failed` | LaTeX 里有 pandoc 不认的宏，或 pandoc 没装 | 看它打印的 stderr 定位到具体命令；确认 `tools.pandoc_path` |
| `pandoc-crossref not found` | 交叉引用不渲染 | 非致命；装上或配 `tools.pandoc_crossref_path` |
| `TeX source references N figure(s) but only M survived` | pandoc 丢了 subfigure/wrapfigure | 对照原 PDF 手工补图 |
| `EPS not rasterized (install Ghostscript)` | 缺 Ghostscript | 装上后重跑，或接受插图不内联 |
| `OCR 模型 X 不可用` | 模型没拉 | `ollama pull glm-ocr` |
| `pdftoppm 未找到` | 缺 poppler | 装 poppler，或配 `tools.pdftoppm_path` |
| `第 N 页 OCR 失败` | 单页重试两次仍失败 | **直接重跑一模一样的命令**：成功页缓存在 `.temp/`，只会重做失败页 |
| 公式乱码、下标粘连 | 渲染精度太低 | 把 `ocr.dpi` 提到 150 再重跑 |
| 摄入后 `Warning: 'magi math check' failed` | 公式校验发现问题 | `finalize` 不会因此中断；单独跑 `magi math check <文件>` 看详情，见第 6 章 |

> [!NOTE]
> `magi ingest ocr` **没有** `--resume` 开关——续跑是自动的：只要输出目录还在，重跑同一条命令就会复用 `.temp/page_N.json` 里已完成的页。有失败页时 `.temp/` 会被特意保留。确认全部做完后可以手动删掉它。

---

## 编译成知识库 {#compile}

摄入只是把文献变成 Markdown。**编译**才是把它变成互链的卡片：读懂一篇论文、拆出概念、判断哪些属于本库范围、写成结构化卡片。

**这一步没有 CLI 命令**——不存在 `magi compile`。它是纯粹的理解工作，只能由 agent 执行 `wiki_compile` 技能完成。CLI 在这一层只负责确定性的检查与修补。

> [!WARN]
> `magi graph build` 在 `wiki/` 空着的时候**照样返回成功**，只是建了一张空图。所以「图谱是空的」往往不是图谱坏了，而是还没编译。用这条确认：
> ```powershell
> magi graph query "SELECT COUNT(*) FROM nodes"
> ```

### 主线 {#compile-main}

在 agent 里依次说（或用斜杠命令）：

| 说什么 | 技能 | 做什么 |
|---|---|---|
| 「编译 raw 里的新文献」 | `wiki_compile` | 每篇 raw 源 → 一张 `wiki/references/` 文献卡，顺手抽出概念卡 |
| 「深挖这篇的概念」 | `wiki_enrich` | 对已编译的卡片二次扫描，补挖第一遍漏掉的定理/引理 |
| 「合并重复概念」 | `wiki_concept_sync` | 同义概念物理归并、过宽概念拆分、多源定义重写 |
| 「清理标签」 | `wiki_tag_sync` | 标签/别名本体论归一（见第 7 章） |
| 「体检并修复」 | `wiki_lint` | 死链、frontmatter、公式的自动修补 |

对应的确定性命令：

```powershell
magi wiki uncompiled                      # 还有哪些 raw 源没编译（编译进度就看它）
magi lint --fix                           # 结构自愈：补 frontmatter、归位文件、重建目录表
magi wiki reindex .                       # 只重建 concepts/ 与 references/ 的 _index.md
magi stats . wiki-summary                 # 全库结构统计
magi map wiki/concepts                    # 某个目录里每个文件的章节与公式块分布
magi wiki placeholders wiki/concepts/x.md # 找出没写完的占位段落
```

### 卡片长什么样 {#compile-cards}

`magi lint` 是按下面这套规则判卷的，写卡片时照着来：

**frontmatter 必填**——文献卡/概念卡：`title`、`category`、`created`、`updated`、`tags`、`summary`；`category` 只能是 `concept` / `topic` / `reference`，并且**决定文件该待在哪个目录**（放错了 `--fix` 会把它移过去）。raw 源必填 `title`、`source`、`type`、`ingested`。

**正文必需小节**——文献卡要有 `## 1. Key Contributions` 和 `## 2. Theoretical Framework`；概念卡要有 `## 1. Core Definition` 和 `## 2. Mathematical Formalism`。确实不适用的卡片可以在 frontmatter 里写 `exclude_structure_check: true` 豁免。

**溯源**——`sources:` 列表必须能解析到真实文件；纯对话产出的卡片写 `compiled-from: conversation` 豁免。

**新鲜度**——`volatility` 取 `hot`/`warm`/`cold`，对应 30/180/365 天。超期会提示 stale，重新核对后把 `verified` 或 `updated` 改成今天。

> [!EXPECT]
> `magi lint` 末尾打印 `Summary: N critical, N warnings, ...` 与 `Result: PASS`。**只有 critical 才会让它 FAIL**，warning 属于待办清单，不阻塞。

> [!FIX]
> - `Markdown file is missing YAML frontmatter` / 字段缺失：按上面清单补齐。
> - `File is in the wrong directory` → `magi lint --fix` 自动归位；若目标已存在同名文件它会拒绝移动，需手工处理。
> - `Wikily [[...]] contains Windows-illegal filename character(s)`：双链里出现了 `\ / : * ? " < > |`，改名。
> - `Wikilink appears to contain a raw mathematical equation`：双链里塞了 LaTeX，换成干净的概念名，公式另起一行写。
> - `Master _index.md is missing` / `config.md is missing`：这两条 **`--fix` 修不了**（尽管它标着 fixable），手工建。
> - **在 hub 根跑 lint 几乎什么都不查**：hub 根只做最外层结构检查。真正的质量闸门要进主题目录跑。

> [!WARN]
> `magi lint --json` 里的 `status` 字段和退出码**判定标准不同**：JSON 的 status 只要有任何 warning/suggestion 就是 `fail`，而退出码和文本版 `Result:` 只看 critical。CI 里请以退出码为准。

### 公式 {#compile-math}

```powershell
magi math format raw/papers/x.md    # 机械修复：$$ 配对、\tag 位置、eqnarray→align、OCR 粘连
magi math check raw/papers/x.md     # 只报错不改：pylatexenc 结构检查（有 pdflatex 时再深一层）
```

顺序永远是**先 format 再 check**。

> [!NOTE]
> `Undefined control sequence` 多半是**误报**——校验器不认识某个宏包的宏而已。抽一个对照原 PDF 确认后，其余同类可以忽略。真正要改的是 `Double subscript`、`Missing }`、`Unexpected end of stream` 这类结构错误：用 `magi ingest crop <pdf> --text "<附近文字>" --out scratch/crop.png` 把原文裁出来对着改。
> `[WARNING] Orphaned $$ remains on line L` 是 format 自己也判断不了的边界，必须手工配对。

---

## 知识图谱 {#graph}

### 建图与浏览 {#graph-build}

```powershell
magi graph build .                 # 从 wiki/ 全量重建 output/graph.db
magi graph browse overview         # 总览：节点/边计数、标签数、命题状态、断链数
magi graph browse nodes --q 拓扑    # 按标题/ID 模糊找节点（按度数降序）
magi graph browse links --node <id> # 某节点的出入边
magi graph browse tags             # 标签词频（降序）
magi graph browse broken           # 所有断链：谁指向了不存在的页面
magi graph browse claims --status unverified
magi graph browse map --tags       # 全图快照（本看板的图谱视图用的就是它）
```

每个视图都支持 `--limit N` 和 `--json`。

需要更自由的查询时用只读 SQL（只允许 `SELECT` / `WITH` / `PRAGMA`）：

```powershell
magi graph query "SELECT type, COUNT(*) FROM nodes GROUP BY type"
```

表结构：`nodes(id, path, title, type, category, summary, created, updated)`、`edges(source_id, target_id, type)`、`tags(node_id, tag)`、`aliases(node_id, alias)`、`claims(id, doc_id, text, status)`、`evidence(claim_id, source_type, source, quote)`。

> [!NOTE]
> **每次 `graph build` 都是全量重建**，没有增量模式，也没有文件监听。**任何批量编辑之后都要重跑一次**，否则你看到的是旧图。
> `graph build` 只扫 `wiki/`——`raw/` 里的东西永远不进图谱。

### 图谱效果不好：对症下药 {#graph-tuning}

| 你看到的 | 真正的原因 | 怎么修 |
|---|---|---|
| **节点太少** | 文献还没编译成卡片；或者图是旧的 | `magi wiki uncompiled` 看积压 → 用 `wiki_compile` 编译 → `magi graph build` |
| **一堆孤立点** | 卡片正文里没写双链，也没跑过语义连边 | `magi link .`（见下）；系统性补链用 `wiki_enrich` |
| **毛球，全连在一起** | 连边阈值太低；或某个标签太宽泛，所有卡片都挂在它下面 | 提高 `magi link --threshold`；先做标签归一，再重跑连边 |
| **概念重复** | 没有任何东西会自动合并概念 | `magi link . --dedup-only` 列出候选，人工确认后合并 |
| **标签一地鸡毛** | 每篇各写各的 | `magi tags extract` → 人工/LLM 写映射 → `magi tags apply` |
| **断链一堆** | 双链文字对不上任何标题/文件名/别名 | `magi graph browse broken` 逐条看：改写法、给目标加 `aliases:`、或 `magi wiki add-concept` 把缺的概念建出来 |
| **看不出主题分区** | 用了 `--tags` 视图，标签节点成了万能枢纽 | 去掉 `--tags` 看纯双链拓扑；再看 `magi lint` 有没有报文件放错目录 |

**语义连边**（需要 Ollama）：

```powershell
magi link .                       # 相似度过线就互相插入 [[双链]]
magi link . --dedup-only          # 只列重复候选，不改文件
magi link . --dedup-only --auto-merge   # 自动合并极高相似度的一对
```

三个阈值可在 `config.yaml` 里长期设定，也可用同名参数临时覆盖：

```yaml
semantic_link:
  threshold: 0.75          # 高于它 → 插入双链
  merge_threshold: 0.85    # 高于它 → 列为合并候选
  auto_merge_threshold: 0.95   # 高于它 → --auto-merge 时真的合并
```

> [!WARN]
> `--auto-merge` 选**名字更短**的那个作为规范名，不是内容更完整的那个。合并前先用 `--dedup-only` 看一遍名单。
> 另外：共享标签会给相似度加分（每个共享标签 +0.05，别名撞名 +0.10）。所以**标签越乱，连边越容易过线**——先清标签再连边，效果差别很大。

**标签归一**是三段式的：

```powershell
magi tags extract .                  # → scratch/raw_tags.json、raw_aliases.json（倒排索引）
#   ↑ 由你或 agent 据此写出 scratch/tag_mapping.json {"tags": {"旧":"新"}}
#     和 scratch/alias_mapping.json {"aliases": {"旧":"新"}}
magi tags apply . scratch/tag_mapping.json scratch/alias_mapping.json
```

`apply` 会改写全部 frontmatter、把规范标签清单写进 `output/ontology.txt`，并自动重建图谱与索引（`--no-rebuild` 可跳过后半段）。**没有 dry-run**，改的是真文件——跑之前建议先 git commit。

> [!FIX]
> - `[Error] Cannot reach Ollama` / `Embedding model ... is not installed`：`ollama serve` 起来，`ollama pull qwen3-embedding:0.6b`。
> - `[Info] Not enough concepts to analyze`：少于两张非 stub 概念卡，正常退出，不是错误。
> - `magi graph browse links --node X` 说 `node not found`：X 既不是节点 ID，标题也不唯一。先用 `browse nodes --q X` 拿到确切 ID。
> - 某个文件的标签死活进不了图：frontmatter 的列表写法不规范。`magi lint --fix` 之后重建。

### 在 Obsidian 里看 {#graph-obsidian}

MAGI 的双链就是 Obsidian 的双链，两边可以同时用：Obsidian 负责肉眼浏览与手工编辑，`magi graph` 负责结构化查询。排除规则见 4.2 的提示框。本看板的 **Melchior → 图谱视图** 是同一份数据的力导向渲染，指向不存在页面的链接会显示成「幽灵节点」——和 Obsidian 的表现一致。

---

## 检索 {#search}

### 建索引 {#search-index}

```powershell
magi index                # 建/刷新 output/index.db
magi index --no-vectors   # 只建关键词索引（没有 Ollama 时）
```

索引覆盖 `wiki/`、`raw/`、`drafts/` 下所有 `.md`，按一到三级标题切块，单块上限 250 行。**增量更新**：内容哈希没变的文件跳过，删掉的文件自动清理。

> [!EXPECT]
> `index: 42 chunks (5 files updated, 37 unchanged, 0 pruned) · vectors 42/42`
> 结尾若是 `· BM25-only (Ollama unavailable)`，说明向量那一半没建起来。

`magi index` 还会把当前工作区**自动注册**进全局知识库表（`~/.config/magi/registry.json`），这样别的工作区也能搜到它。

### 搜索 {#search-query}

```powershell
magi search "任意子统计"                     # 默认：本库 + 所有启用的注册库
magi search "anyon" -k 20 --mode vector      # 只走语义
magi search "BM25 关键词" --mode bm25        # 只走关键词
magi search "..." --collection concepts      # 只搜概念卡
magi search "..." --path 'raw/papers/2026-*fracton*'   # 锁定到某一篇论文里搜
magi search "..." --scope local              # 只搜当前工作区
magi search "..." --kb <名字>                # 只搜某个注册库
magi search "..." --json                     # 机器可读
```

默认的 `hybrid` 模式把关键词与语义两路结果用 RRF 融合排序，中英文都支持（中文按二元组切分进关键词索引，语义那侧由嵌入模型天然跨语言）。

**跨库检索**：

```powershell
magi kb list                  # 所有注册库及其可搜状态
magi kb disable <名字>         # 排除出全局检索（enable 恢复）
magi kb register <路径>        # 手动注册（默认按目录名命名，重名自动加 -2）
magi kb unregister <名字>      # 只删注册项，不动文件
```

> [!FIX]
> - `no index at output/index.db` → 先 `magi index`。
> - `no workspace here and no searchable registered KBs` → 你不在工作区里，且没有可搜的注册库。`cd` 进去，或 `magi kb register` + `enable`。
> - **搜不到刚写的内容** → 索引是按哈希增量的，但**不会自动触发**。编辑后重跑 `magi index`。
> - **结果全是关键词命中，没有语义** → 结尾会提示 `BM25-only`。启动 Ollama 后重跑 `magi index` 补向量。
> - **中文搜不出东西** → 提示 `this index predates CJK-aware tokenization` 时，重跑 `magi index` 即可（会自动重建分词层）。
> - `index dims mismatch current embedding model` → 换过嵌入模型。改回去，或重跑 `magi index` 全量重嵌。
> - `sqlite-vec unavailable` → 向量扩展加载失败（macOS 上常见于系统 Python 不支持加载扩展）。用 uv/Homebrew 的 Python，或接受关键词检索。

> [!NOTE]
> `magi index` 没有 `--force` / `--rebuild`，也没有清库命令；真要重来就删掉 `output/index.db` 再跑。
> `magi grep "<正则>" <文件...> [-i]` 是另一回事——它不读索引，就是对指定文件做正则行匹配（Python 正则语法，输出 JSON，最多 200 条，带 5 秒防卡死保护）。文件很少、要精确匹配字面量时用它；要「找相关内容」用 `magi search`。

---

## 写论文 {#writing}

### 任务待办怎么用 {#writing-tasks}

MAGI 不自己实现任务系统，它对接 [Beads](https://github.com/gastownhall/beads)（`bd`）。**一个 hub 一个任务库**，各主题的 issue 用 `topic:<名字>` 标签区分。

```powershell
magi pm init          # 在 hub 根跑一次：建库 + 注册六种科研 issue 类型
magi pm status        # 当前 ready / in progress / blocked / open 计数
magi pm backlog-sync  # 把「还没编译的 raw 源」变成待办
```

> [!NOTE]
> 单主题用户不用建 hub。`magi pm status` 找不到任务库时会提示「run 'magi pm init' at the hub root」，这句话在没有 hub 的情况下是误导的——直接在主题目录里跑 `magi pm init` 就行，它会就地建库。

六种科研类型：`question`、`survey`、`derivation`、`computation`、`experiment`、`review`（外加 bd 自带的 `task`/`bug`/`feature`/`epic`/`chore`/`decision`）。

日常你实际会敲的是 bd 自己的命令：

```powershell
bd ready                                   # 现在能干什么（开工前先看这个）
bd create -t derivation "推导 3.2 节的对偶变换" -d "..."
bd close <id> --reason "已完成，结论见 drafts/paper.md#3.2"
bd list --label magi-compile --all         # 看编译积压
```

写论文时的用法很朴素：**每个小节开一个 issue**，写完 close 掉并在 reason 里留一句结论。审计发现的矛盾、雷达筛出的必读文献，也都落成 issue 而不是 TODO 注释——这样下次换个会话进来，`bd ready` 就是完整的交接。

> [!WARN]
> 别用 `-t thesis`——它不是合法类型（`thesis` 只是 `wiki/theses/` 这个目录名）。写作类任务用 `derivation` / `review` / `question`。

> [!NOTE]
> `magi pm backlog-sync` 只**创建** issue，永远不会自动关闭。编译完一篇后由你（或 agent）`bd list --label magi-compile` 找到对应项手动 close。
> 没装 `bd` 也能用 MAGI：所有技能遇到 `bd` 缺失都只提示一次然后继续，任务追踪从来不是硬门槛。

### 起草 {#writing-draft}

草稿放在 `drafts/<slug>.md`。这个目录 `magi init` 不会建，第一次写文件时自然出现。它**进检索**（collection 叫 `drafts`）、**不进图谱**、**不计同步率**——它是在写的东西，不是已经确立的知识。

写作循环（技能 `wiki_draft` 会带着你走，手工也一样）：

```powershell
magi search "这一段要讲的东西" -k 5           # 1. 先取证
magi wiki context --name "某概念"             # 　 把所有提到该概念的段落抽到 scratch/
#                                             # 2. 写 drafts/paper.md，引用处写 [[文献卡]]
magi bib --all -o drafts/refs.bib             # 3. 导出参考文献
magi bib pretko-2020 --fetch                  # 　 有 arxiv_id 时拉 arXiv 官方条目
magi stats . verify-refs drafts/paper.md      # 4. 检查双链是否都指向真实文件
magi verify drafts/paper.md --topic-dir .     # 　 检查命题的引文是否真的存在
magi math check drafts/paper.md
```

> [!FIX]
> - `magi bib` 说 `has no citable frontmatter ... skipped`：那张文献卡的 frontmatter 缺 `title`/`authors`/`year`/`doi`/`arxiv_id`/`url`，补一个就行。
> - `magi bib` 说 `matches several cards`：slug 太模糊，给全名或完整路径。

### 命题与核验 {#writing-claims}

需要被追责的论断，写成命题块（可以嵌在正文里，用 `<!-- magi:claims -->` 注释包起来，`magi graph build` 会把它们收进图谱）：

```text
CLAIM: 分数化激发在该模型中携带 1/3 电荷。
EVIDENCE: "the fractionalized excitations carry charge e/3"
SOURCE_TYPE: local_wiki
SOURCE: wiki/references/laughlin-1983.md
```

`FINDING:` 是 `CLAIM:` 的同义词。四个字段缺一不可。然后：

```powershell
magi verify drafts/paper.md --topic-dir .            # 退出码 0=全部通过，1=有未核验
magi verify drafts/paper.md --topic-dir . --fetch-web  # 网页来源也真的抓取比对
magi validate wiki/theses/x.md --schema thesis       # 论断报告的结构校验
```

> [!NOTE]
> `verified` 的含义是**引文存在性**——那句话确实逐字出现在来源文件里（空白、全角标点、连字符差异都能容忍）。它**不判断**你的论断和这句引文在语义上是否成立，那一层归人和 LLM 审查（`wiki_audit` 技能）。`magi claims verify` 是同一条命令的别名。
> 引文必须是单行引号内容；多行引文不被支持。

> [!WARN]
> `magi validate --schema research` 里那条「有 N 个段落没有引用」的提示措辞很温和，但它**会让退出码变成 1**。写 CI 时注意。

---

## 文献雷达 {#radar}

雷达做的事：每天确定性地收割新论文候选 → 写成简报 → 下次会话由 `radar_review` 技能做 LLM 判分 → 保留的进任务库和摄入队列。

### 配置 {#radar-config}

写在工作区 `config.yaml`：

```yaml
radar:
  arxiv_categories: [cond-mat.str-el, hep-th]   # 每天扫哪些分区
  seed_arxiv_ids: ["2301.01234"]                # 种子论文（推荐算法的正样本）
  days: 7                    # arXiv 回溯窗口
  max_candidates: 40         # 每次最多留几条
  min_relevance: 0.35        # 相关度阈值（可选；不写=不过滤）
  own_arxiv_ids: ["2402.05678"]     # 「我方论文」，citation-gap 用
  citation_gap:
    min_shared_refs: 2       # 共引门槛
    years: 2                 # 只看近几年
```

`min_relevance`、`own_arxiv_ids`、`citation_gap.*` 这三组**不在 `magi init` 生成的模板里**，需要时自己加。

相关度是「候选摘要与本库嵌入质心的余弦相似度」，所以它依赖 `magi index` 建好的向量索引 + 可用的 Ollama；没有的话候选按来源顺序排列，不打分。

### 收割与审阅 {#radar-run}

```powershell
magi radar harvest                # 收割：S2 推荐 ∪ arXiv 新文 → inbox/radar/日期-digest.md
magi radar harvest --days 14      # 临时放宽窗口
magi radar status                 # 账本规模 + 还有几份简报没审
magi radar citation-gap           # 找「该引我方论文却没引」的近期文献
```

简报里每条候选长这样：

```text
## 论文标题
- id: `2408.01234` · 2026 · source: arxiv · relevance: 0.71
- authors: A Name, B Name, et al.
- https://arxiv.org/abs/2408.01234
- abstract: ...
```

审阅有两条路：对 agent 说「审一下雷达简报」（`radar_review` 技能），或在本看板的 **文献雷达** 面板里逐条「收入 inbox / 建阅读任务 / 标记已审」。两条路写的是同一份状态。

> [!NOTE]
> 无论哪条路，**MAGI 都不会替你下载 PDF**。「收入 inbox」只是写一张待办卡片（`inbox/radar-accept-*.md`），拿到 PDF 之后仍然走第 5 章的摄入流程。

### 定时收割 {#radar-schedule}

```powershell
magi radar install-schedule --time 03:00     # 注册每日任务
magi radar install-schedule --uninstall      # 卸载
```

- **Windows**：注册进任务计划程序，任务名形如 `magi-radar-<目录名>-<哈希>`，可用 `schtasks /Query /TN <名字>` 核对。
- **macOS**：写入 `~/Library/LaunchAgents/com.magi.radar.*.plist`，用 `launchctl list | grep com.magi.radar` 核对。
- **Linux**：**什么都不会装**——只打印一行建议的 crontab，而且那行**忽略你传的 `--time`，永远写 3 点**。自己 `crontab -e` 加进去。

> [!WARN]
> 任务名里含工作区路径的哈希。**移动或改名工作区之后，`--uninstall` 就找不到旧任务了**，得手动删（`schtasks /Delete /TN <名字> /F` 或删 plist）。

### 噪声调优 {#radar-tuning}

| 症状 | 处理 |
|---|---|
| `harvest: no new candidates` | 种子和分区是不是空的？窗口太窄？`--days 30` 试试。也可能真的都收过了——账本在 `output/radar/seen.jsonl`，**没有命令能重置它**，要重刷得手动删行 |
| 候选太多太杂 | 调高 `min_relevance`、调低 `max_candidates`、精简 `arxiv_categories` |
| 相关度全是空的 | 提示 `relevance scoring unavailable`——先 `magi index` 建向量索引并启动 Ollama |
| `warning: S2 recommendations failed` | Semantic Scholar 限流或网络问题；调用是匿名的，没有 API key 可配，过一会儿重跑 |
| `arXiv query failed for <分区>` | 简报 frontmatter 会记 `sources_failed`，`magi radar status` 也会提示；重跑补齐 |
| `citation-gap: no candidates survived` | 漏斗太严：降 `min_shared_refs`、升 `years` |
| `has no reference data on S2 yet` | 论文太新，S2 还没索引它的参考文献，等几天 |
| 简报越积越多 | 只有审阅动作会把 `status: pending-review` 改成 `reviewed`；同一天重复收割会生成 `-2`、`-3` 的副本，越积越乱。定期审 |

---

## 本地看板 {#webui}

```powershell
magi ui                          # 默认 http://127.0.0.1:8737，自动开浏览器
magi ui --port 8080 --no-open    # 指定端口且不自启
magi ui --check                  # 只做结构自检，不监听端口
magi ui --host 0.0.0.0           # 改绑定地址（默认只监听本机，见下方安全说明）
magi ui --reload                 # 改代码自动重载（开发用）
```

不指定端口时会自动探测 8737→8746；**显式指定的端口被占用则直接报错**，不会顺延。

七个面板：

| 面板 | 能干什么 |
|---|---|
| **课题总览** | 同步率、可一键执行的修复建议、注册库管理、`config.yaml` 关键字段编辑 |
| **Melchior（认知）** | 概念/文献计数、命题与证据表、待编译积压、图谱七视图 + 只读 SQL 台、BibTeX 复制、草稿列表 |
| **Balthasar（任务）** | Beads 计数 + 一键「把积压同步成任务」 |
| **Casper（文献检索）** | 检索实验台：模式/范围/集合/路径过滤，与 `magi search --json` 完全同构 |
| **文献雷达** | 简报阅读 + 逐条审阅动作 |
| **运维与危险区** | 服务端操作白名单 + 输入操作 ID 二次确认 + 实时终端，任务历史落盘 |
| **文档与指引** | 就是你现在看的这份，外加 README 与 CLI 命令参考 |

**看板能触发的后台任务只有 14 个**：建索引、建图谱、重建目录表、语义连边、lint 修复、统计、积压同步、雷达收割、引用缺口，以及需要二次确认的 setup / migrate / pm init / 删除旧版拷贝 / 雷达定时任务。

> [!NOTE]
> **摄入不在其中**——`magi ingest *` 全系列只能在终端或经由 agent 调用。同理 `magi init`、`hub *`、`sync`、`validate`、`verify`、`tags *`、`math *` 也没有按钮。

顶栏的 **⚡ MAGI 模式** 切换战术主题：红色为战斗态（深色），蓝色为静默值守（浅色），☀︎/☽ 在两者间切换。右下角的 ◐ 可调玻璃模糊度、不透明度与 CRT 扫描线。

> [!FIX]
> - **端口被占**：换 `--port`，或先关掉上一个实例。
> - **改了代码/升级后界面没变**：静态文件是即时生效的，但**后端改动需要重启 `magi ui`**。样式不更新则是浏览器缓存，硬刷新一次。
> - **图谱是空的**：先 `magi graph build`。
> - **看板打不开或显示无工作区**：顶栏切换工作区；看板只监听 `127.0.0.1` 并带 Host 白名单，**默认不能从别的机器访问**（远程用 SSH 端口转发）。

---

## 疑难速查 {#troubleshoot}

按症状找，不用记命令归属。也可以直接在终端里查同一张表：

```powershell
magi guide --symptoms                       # 全书症状索引（84 条左右）
magi guide --symptoms --search "ollama"     # 按关键词过滤
```

或者把报错贴给 agent，让 `magi_guide` 技能替你查（见 [1.2](#howto-read)）。

| 症状 | 先跑这个 |
|---|---|
| 完全不知道下一步做什么 | `magi sync` —— 看最后一行 `->` |
| 装完了但 `magi` 找不到 | 开**新终端**；仍不行把 `~/.local/bin` 加进 PATH |
| 某个功能报缺依赖 | `magi setup --check` |
| 命令说 `no workspace found` | `cd` 进主题目录，或加 `--topic-dir` |
| 不知道某个主题在哪 | `magi hub list` / `magi hub resolve <hub> <slug>` |
| 摄入完了但库里没有 | 忘了 `magi ingest finalize` |
| 图谱是旧的 | `magi graph build` —— 它没有增量模式 |
| 搜不到刚写的东西 | `magi index` —— 它不会自动触发 |
| 检索没有语义结果 | 启动 Ollama → `magi index` 补向量 |
| 双链点不开 / 断链多 | `magi graph browse broken` |
| 概念重复、标签发散 | `magi link . --dedup-only`；`magi tags extract` |
| 卡片格式报错 | `magi lint --fix` |
| 公式渲染不对 | `magi math format` → `magi math check` |
| 引用导不出来 | 检查文献卡 frontmatter 的 `title/authors/year/arxiv_id` |
| 论断被标 unverified | 引文要与来源逐字一致，且必须单行 |
| 雷达没有新东西 | 检查 `arxiv_categories` / `seed_arxiv_ids`；`--days` 放宽 |
| 定时任务不触发 | Windows `schtasks /Query`；Linux 上它根本没装，自己写 crontab |
| 配置改了没效果 | 用 `python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"` 验一遍——YAML 解析失败是静默的 |
| 想看某条命令到底有什么参数 | `magi <命令> --help`，或本页顶部的 **CLI 命令参考手册** |
| 不知道该读哪一章 | `magi guide --search "<报错原文>"` |

> [!TIP]
> 所有命令的完整参数以 `magi <命令> --help` 为准——这份指南讲的是**何时用、期望什么、出错怎么办**，参数清单不重复维护。
