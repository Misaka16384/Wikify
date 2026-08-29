# MAGI 使用指南

从零安装，到跑出一个能查、能引、能写的文献库。

每章按同一个节奏：**做什么 → 怎么做 → 应该看到什么 → 没看到该怎么办**。左侧目录可随时跳转；页面内 `Ctrl+F` 直接全文搜索；每段命令右上角可一键复制。

---

## 先跑通一遍 {#start}

从零到一个能检索的库——三条命令，加对 agent 说的一句话：

```powershell
pipx upgrade --install magi-research # 1. 装或升级（幂等，重复跑没副作用）
mkdir my-topic ; cd my-topic ; magi init   # 2. 建一个课题
magi install                         # 3. 装进你的 agent CLI（技能 + 协议 + 收工闸门）
magi ingest auto                     # 把 PDF 丢进 inbox/ 之后
```

一个课题一个目录，没有更上面的一层。**跨库检索走用户级注册表**（`magi kb list`），
`magi search` 默认就会联邦检索所有启用的库——不需要把它们收进同一个父目录。

然后在 Claude Code / Codex 里对 agent 说：**「把待编译的都编译了」**。这是唯一没有命令的一步——它要读论文、写卡片。跑完之后 `magi index`，就能检索了。

本章剩下的部分讲这几层分别是什么、以及这本手册怎么读。

MAGI 由三层组成，分工不重叠：

| 层 | 是什么 | 你怎么用 |
|---|---|---|
| **magi CLI** | 所有确定性操作：摄入、建图、检索、校验、任务、雷达 | 终端里敲，或让 agent 替你敲 |
| **skills** | 教 agent「何时、为何」调用哪条流水线 | 在 Claude Code / Codex 里说一句话触发 |
| **工作区** | 落盘的知识：`raw/` `wiki/` `output/` `drafts/` | 用 Obsidian、编辑器、本看板直接看 |

agent 的上下文是一次性的，**状态永远在磁盘上**。所以任何一步中断都能原地续跑。

> [!WARN]
> **agent 不是可选项。** 从 `raw/` 原始文献到 `wiki/` 概念卡这一步是理解与综合，没有对应的 CLI 命令——它只能由 `compile` 技能驱动 LLM 完成。只装 CLI 不接 agent 宿主，你可以摄入文献、做关键词检索，但永远得不到概念卡、知识图谱和带引用的问答。第 2.4 节讲怎么接。

### 三条起步路线

**① 全新用户**——按第 2 章装好，然后：

```powershell
mkdir quantum-toys ; cd quantum-toys
magi init --name "Quantum Toys" --scope "玩具模型中的量子现象"
magi install                 # 技能 + AGENTS.md 协议块 + 收工闸门
magi pm init                 # 可选：机械任务的任务库（会 git-init 本目录）

magi sync --fix              # 验收，并把能自动修的都修掉
```

**② Wikify 老用户**——数据不用动，直接看第 3 章，三条命令迁移。

**③ 只想先试试**——随便找个空目录 `magi init` 就能用。`magi init` 会把它注册进用户级注册表，所以以后在别的库里 `magi search` 也能搜到它。

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

**让 agent 直接排查**：手册随 CLI 一起装，不用联网也不用记。把报错原样贴进对话即可——agent 会跑 `magi guide --search "<报错>"` 检索症状、读相关章节、再用 `magi sync` / `magi setup --check` 确认现状，最后给你手册里那条确切的命令，而不是凭记忆编一个参数。

> [!NOTE]
> 手册里的每条命令都对着真实 CLI 校验过，测试会保证它不漂移。所以 agent 引用手册比它凭印象作答可靠得多——遇到 MAGI 相关的问题，值得明确要求它「查手册再回答」。

### 怎么读 `magi sync`

`magi sync` 是每次进场的第一条命令，也是每次卡住时的第一条命令：

```text
MAGI SYSTEM ONLINE — sync ratio 33.3%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     beads offline
`- CASPER    (retrieval)  index missing · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the ingest skill to start building the library
  -> magi pm init   # initialize beads at the hub root
  -> magi index   # build the retrieval index
```

三核分别是知识、任务、检索。**最后一行 `->` 就是下一步该干什么**——照做，或者直接让它自己做：

```powershell
magi sync --fix             # 建图 / 建索引 / 同步积压 / 初始化任务库，能自动的都跑掉
magi sync --fix --dry-run   # 先看会跑哪几条
```

`--fix` 只做确定性、可重复的那几步；需要判断的（装 Beads、摄入文献、审雷达简报）它只会列出来告诉你。

同步率是三核就绪度的加权平均（只计算「当前适用」的核）：

- **MELCHIOR** = 0.55 图谱新鲜度 + 0.25 待编译积压 + 0.20 命题健康度
- **BALTHASAR** = 研究状态有多可读：`1 − 欠账/note 数`，欠账指 `threads/` 里「发生了但没写下来」的事。它量的是记账干净度不是进度——六个开放命题零欠账完全健康。还没有 `threads/` 的库沿用旧口径（0.6 任务库可达 + 0.4 状态可读）；`--kb-only` 模式下整核不计入。
- **CASPER** = 0.7 索引新鲜度 + 0.3 向量覆盖率

> [!NOTE]
> 同步率不是「知识量」评分。空库照样能拿 MELCHIOR 满分——它只惩罚**过期、积压、未核验**，不惩罚「还没开始」。所以刚建的库显示 33.3% 很正常：那是「三核里只有知识核在线」。跑完 `magi pm init` 和 `magi index` 就会跳上去。
> 不在任何工作区里跑时，同步率显示为空而不是 0——它不会编一个数字给你。

---

## 安装 {#install}

安装就一条命令，而且升级用的是同一条：

```powershell
pipx upgrade --install magi-research
```

没装就装，旧了就升，已经是最新就什么都不做——所以想跑几次跑几次。（`--install` 需要 pipx 1.5 以上；更老的 pipx 首装用 `pipx install magi-research`，之后升级用 `pipx upgrade magi-research`。）

不需要 git，而且装完之后 MAGI 再也不会调用 pipx 或 uv。**pipx 是默认选择**，前提是机器上已经有 Python 3.10+；没有的话用**备选的 uv**，它自带 3.12：

```powershell
uv tool install --force magi-research   # uv 的等价写法，同样一条管装和升
```

下面是按项目安装，以及某些摄入路线才用得上的外部工具。

### 一键安装（推荐）{#install-oneline}

不需要预装 Python，也**不需要 git**（包从 PyPI 装）。`git` 只在后面两处用得上：注册 Claude Code 插件，以及 `magi pm init`（Beads 会 git-init 任务库）。没有的话 Windows 用 `winget install Git.Git`，其他平台用包管理器。

**Windows（PowerShell）**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"
```

**macOS / Linux**

```bash
curl -LsSf https://raw.githubusercontent.com/Misaka16384/magi/main/install.sh | sh
```

脚本按顺序做三件事：

1. 找一个包管理器：有 pipx 就用 pipx；没有就往它找到的 Python 3.10+ 上装一个；再没有就退回 [uv](https://docs.astral.sh/uv/)——uv 自带 Python 3.12，**你不需要预装 Python**；
2. `pipx upgrade --install magi-research`（或 uv 的等价写法）——从 PyPI 装或升，一步到位；
3. 执行 `magi setup`：问你要哪些可选功能、要任务待办就装 Beads（`bd`）、拉 Ollama 嵌入模型、注册 Claude Code 插件、报告检测到的 agent CLI、检测旧版 Wikify 残留，最后打印体检表。

**幂等**：重跑同一条命令就是升级。

> [!EXPECT]
> 终端出现 `=== MAGI environment ===` 体检表，`magi --version` 打印版本号。

> [!FIX]
> - **`magi` 找不到**：`uv tool update-shell` 只改了配置文件，当前窗口的 PATH 还是旧的。**开一个新终端**（两个安装脚本最后都会提醒这句）。仍然不行就手动把 `~/.local/bin`（Windows：`%USERPROFILE%\.local\bin`）加进 PATH。
> - **提示 `note: git not found`**：只是提醒，安装照常继续。等你要用 Claude Code 插件或任务系统时再装 git。
> - **提示 `magi setup reported issues`**：`magi setup` 整个崩了（不是某个组件失败）。CLI 本身已经装好，重跑 `magi setup` 看真实报错；只想看现状用 `magi setup --check`。
> - **组件装没装成，看体检表**：`magi setup` 永远返回成功，Beads / Ollama / 插件哪一步失败只体现在 `=== setup results ===` 那几行里，不会让命令报错。
> - **公司网络拦 GitHub**：走下面的手动安装，或先配好代理再跑。

### 手动安装、升级、卸载 {#install-manual}

```powershell
pipx upgrade --install magi-research    # 装或升级，一条命令管两件事
pipx uninstall magi-research            # 卸载
pipx list                               # 看装了什么版本

# 或者用 uv（不想自己管 Python 的话）：
uv tool install --force magi-research   # 装或升级
uv tool uninstall magi-research         # 卸载
uv tool list                            # 看装了什么版本

# 想试还没发版的改动：
uv tool install --force git+https://github.com/Misaka16384/magi
```

> [!WARN]
> pipx 和 uv 的可执行入口放在**同一个目录**（`~/.local/bin`）。两个都用来装过 MAGI、然后卸载其中一个，会把另一个还在依赖的那个入口一起删掉——`magi` 从 PATH 上消失，而 `uv tool list` 还坚称它装着。挑一个用到底；已经中招的话，`uv tool install --force magi-research`（或 pipx 的等价命令）能把入口补回来。

装完随时体检：

```powershell
magi setup --check
```

### 保持最新 {#update}

MAGI 会告诉你有没有新版本，也可以直接帮你装上。

```powershell
magi update            # 检查并升级（会先问一句）
magi update --check    # 只报告，不改任何东西
magi update --json     # 机器可读
```

任何命令跑完之后，如果有新版本，stderr 上会多一行提示。它**不会让任何命令
变慢**：这行字来自**上一次**调用在后台线程里填好的缓存，所以没有哪一次
`magi` 会等 pypi.org。用 `MAGI_NO_UPDATE_CHECK=1` 关掉，或者在全局设置里写
`update_check: false`。

检查读的是 `pypi.org/simple/`——安装器真正解析的那个索引——而不是 JSON API，
后者会早几分钟发布新版本。这个时间差正是「提示说有新版，包管理器却正确地
拒绝安装」的来源。

WebUI 里版本号旁边会出现一个徽章，点开有 **立即升级**。

> [!NOTE]
> 面板会先把自己关掉再升级，然后在同一个地址重新启动，页面自己会回来。
> 这不是谨慎：运行中的 `magi ui` 占着自己环境里的 `python.exe` 和所有已加载的
> 扩展模块，而 Windows 上包管理器**替换不了正在被打开的文件**。原地升级会
> 中途失败并留下一个坏掉的安装——而且是在一个页面刚刚变白、什么都看不到的人
> 面前。所以由一个分离出去的 helper 等服务器退出、升级、把它重新拉起来，
> 并把结果写盘；重新打开的面板会报告结果，**包括「命令成功了但版本其实没变」
> 这种情况**。

源码检出永远不会被包管理器升级——`magi update` 会说明并停下。

> [!NOTE]
> **如果你是用裸 `pip` 装的**，升级命令是
> `python -m pip install --upgrade magi-research`——关键在那个 `--upgrade`。
> pip 是这里唯一一个「install 命令不会装」的工具：对着已经装好的包再跑一次
> `pip install magi-research`，它只会打印 `Requirement already satisfied`，
> 然后**退出码 0**，什么都没改。这看起来和升级成功一模一样，只有版本号会露馅。
> `magi update` 现在能认出 pip 安装——用户 site 或者装进解释器本身——并替你跑
> 对的那条命令。如果这个 Python 被标成了「外部管理」（PEP 668：Debian、Fedora、
> Homebrew，以及 `uv` 帮你装的那个 Python），pip 两条路都会拒绝，所以 MAGI 会
> 直接说明并指向 pipx，而不是去跑一条注定失败的命令。

> [!NOTE]
> **Windows 上，挡住升级的可能就是 `magi` 自己。** pipx 有时会把
> `~/.local/bin/magi.exe` 做成指向 venv 里 `Scripts/magi.exe` 的符号链接，于是你
> 敲 `magi`，Windows 加载的正是升级要替换的那个文件——而**正在运行的程序删不掉**。
> 没有别的进程占着它，挡路的就是那条正在升级的命令本身。你不需要手动跑任何东西：
> 这种情况会把升级交给一个 helper，它等这条命令退出、把活干完、把结果写下来。
> 你的 shell 立刻就回来，下一条 `magi` 命令会告诉你结果。

`magi setup` 的开关：

| 开关 | 作用 |
|---|---|
| `--check` | 只体检，不装任何东西、不删任何东西 |
| `--no-beads` | 跳过 Beads 安装 |
| `--no-models` | 跳过 Ollama 模型拉取 |
| `--no-plugin` | 跳过 Claude Code 插件注册 |
| `--no-skills` | 不在体检里报告 agent CLI（`magi setup` 从不代你安装技能） |
| `--remove-legacy` | 删除检测到的旧版 Wikify 拷贝（唯一的破坏性开关） |
| `--kb-only` / `--full` | 切换「纯知识库」与「完整」档位 |

> [!TIP]
> 只想要纯知识库、不要任务管理？`magi setup --kb-only`：跳过 Beads，`magi sync` 里 BALTHASAR 核显示 disabled 且不计入同步率。档位存在 `~/.config/magi/settings.json`，随时 `magi setup --full` 恢复。

### 全局装还是按项目装 {#install-scope}

这是最常问反的一件事。**CLI 全局装一份就够，工作区才是「按项目」的。**

| 东西 | 装在哪 | 数量 |
|---|---|---|
| `magi` CLI | 用户级（`pipx install` / `uv tool install`），在 PATH 上 | 全机一份 |
| skills | **每个工作区**里，按宿主分目录（`magi skills install`） | 每个课题一份 |
| 工作区 | 你的课题目录 | 每个课题一个 |
| 全局配置与注册表 | `~/.config/magi/`（Windows 是 `C:\Users\<你>\.config\magi\`，**不是** AppData） | 全机一份 |

装一次 CLI，之后每开一个新课题只需要 `magi init` + `magi install`。

`magi install` 做三件事，缺一件 agent 都跑不顺：把 8 个技能放到宿主找得到的地方；把当前协议写进 `AGENTS.md` 的托管块（块外你写的东西一个字不动）；给 Claude Code 装上 Stop hook，让会话结束前必须过 `magi sync --close`。**宿主强制力不对称**：只有 Claude Code 有文档化的 Stop hook，其余宿主同一条规则只以托管块里的指令形式存在——agent 可以不听，而且有时真不听。命令会把这件事直说，而不是装成四个宿主都装好了。

> [!WARN]
> 真·项目内安装（`uv venv && uv pip install -e .`）只推荐给要改 MAGI 源码的人。这样装出来的 `magi` **不在 PATH 上**，只能用 `.venv\Scripts\python.exe -m magi.cli ...` 调用；而 skills、Claude Code 的 SessionStart 钩子、雷达定时任务全都是按裸命令名 `magi` 去 PATH 里找的，它们会找不到。日常使用请用 `pipx`（或 `uv tool install`）。

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
> **默认只装进当前工作区，不装全局。** 这 8 个技能都是围着某个研究工作区转的（往 `raw/` 摄入、编译进 `wiki/`、查这个库的图谱），装到全局意味着你打开任何一个无关项目，agent 都要背着它们。真想全机可用：`magi skills install --scope global`（命令会提醒你一次）。
> 装在工作区里还有个好处：这些文件跟着仓库走，同事 clone 下来就有。

| 宿主 | 全局位置 | 项目位置 | 怎么触发 |
|---|---|---|---|
| **Claude Code** | `~/.claude/skills/` | `.claude/skills/` | `/技能名`，也会按描述自动触发 |
| **Codex** | `~/.agents/skills/`（外加 `~/.codex/skills/`） | `<仓库根>/.agents/skills/` | `$技能名`，或让它按描述自选 |
| **Antigravity（agy）** | `~/.gemini/config/skills/` | `<仓库根>/.agents/skills/` | 说出名字，或按描述自动触发；`/skills` 可浏览 |
| **opencode** | `~/.config/opencode/commands/` + `skills/` | `.opencode/commands/` + `skills/` | `/技能名` |

> [!NOTE]
> **不是每个 CLI 都有斜杠命令。** Claude Code 和 opencode 有；Codex 用 `$技能名`；agy 只按描述自动触发（`/skills` 只是个浏览面板）。所以最稳的用法在哪都一样：**把你要做的事说出来**——「摄入 inbox 里的论文」「查一下这个报错」——描述匹配上就会自动加载对应技能。
> `.agents/skills/` 是跨 agent 的公共约定：Codex 和 agy 共用它，装一份两家都认。opencode 也会扫这个目录，但斜杠命令来自它自己的 `.opencode/commands/`，所以安装器会另外给它写一份。

**Claude Code 还可以走插件**（一键脚本已自动执行）：技能带 `magi:` 命名空间出现，还附带一个 SessionStart 钩子每次自动跑 `magi sync`：

```powershell
claude plugin marketplace add Misaka16384/magi
claude plugin install magi
claude plugin install <本地仓库目录>      # 本地开发模式
```

插件和 `magi skills install` 可以共存——前者给你 `/magi:技能名`，后者给你 `/技能名`。

**任何其他 agent**——工作区里的 `CLAUDE.md` 和 `AGENTS.md`（两份内容完全一致）就是入场协议：它告诉 agent 进场先跑 `magi sync`、三核对应哪些命令、卡住时用 `magi guide --search` 查手册，以及「不许凭记忆回答研究问题」。只要宿主会读其中之一就能开工；实在不认，把 `magi --help` 贴给它也行。

> [!EXPECT]
> `magi skills where` 里 project 那几行显示 8/8；在**这个工作区目录里**重开一个 agent 会话，输入 `/` 能看到技能（Claude Code / opencode），或者直接说「摄入 inbox 里的论文」它就动手。`magi setup --check` 的体检表也会显示当前工作区各 CLI 的技能数。

> [!FIX]
> - **装完看不到**：技能是启动时扫描的——**在工作区目录里重开一个会话**（项目级技能只在从该目录启动时可见）。
> - **不确定装到哪了**：`magi skills where` 会打印每个 CLI 的真实路径与数量。
> - **提示 skipped**：目标位置已有同名文件且不像我们写的，出于安全没覆盖。确认后 `magi skills install --force`。
> - **agent 调用了不存在的脚本路径**（`python bin/llm-wiki.py ...`）：旧版 Wikify 的 SKILL.md 还在，跑 `magi setup --remove-legacy`。
> - **想卸载**：`magi skills uninstall [--host X] [--scope project]`。
> - `magi setup`、`magi migrate`、`magi ui` **没有对应技能**——纯 CLI 命令，直接敲。

### 外部工具——全都是可选的 {#install-tools}

**先做这个：** 跑 `magi setup`。它会逐个问你要不要，说明每个解锁什么功能，并给出官网地址。
不想要的说「否」，以后就不再提——`magi setup --check` **不会把它标成问题**，因为
你主动选择不装的东西不是你机器的故障。想重新选：`magi setup --optionals`。

| 工具 | 解锁什么 | 缺了会怎样 | 官网 |
|---|---|---|---|
| **Beads**（`bd`） | 任务待办 | 任务功能降级，其余不受影响 | `magi setup` 会替你装 |
| **Ollama** + `qwen3-embedding:0.6b` | 语义检索、语义连边、雷达相关度打分 | 检索退回关键词匹配；`magi link` 报错退出 | https://ollama.com/download |
| **Ollama** + `glm-ocr:q8_0` | 全本地 OCR 摄入 | 只能走云端 OCR、LaTeX 源码或 arXiv HTML | https://ollama.com/download |
| **Pandoc** | `magi ingest arxiv-html` 和 `magi ingest tex`——保真度最高的两条路 | 无法处理 arXiv HTML 与源码包 | https://pandoc.org/installing.html |
| **Poppler**（`pdftoppm`） | 本地 OCR 渲染页面 | 本地 OCR 直接报错 | https://poppler.freedesktop.org/ |
| **pdflatex** | 数学公式深度校验 | 自动回退 `pylatexenc` 轻量校验 | https://www.tug.org/texlive/ |
| **Ghostscript** | LaTeX 源码里的 EPS 插图转位图 | EPS 原样拷贝，markdown 里不显示 | https://www.ghostscript.com/ |
| **MinerU**（云服务，不是本地程序） | 云端 PDF 转换，版面与公式识别强 | 改用本地 OCR，或走 LaTeX / HTML 路线 | https://mineru.net/ |

> [!NOTE]
> 不用自己 `ollama serve`。只要 Ollama 装了但没跑，MAGI 会在第一次要用到它时
> 自动拉起（每进程一次）。想自己管这个守护进程，就在 `config.yaml` 里设
> `ollama.autostart: false`，或者设环境变量 `MAGI_NO_OLLAMA_AUTOSTART=1`。

```powershell
ollama pull qwen3-embedding:0.6b     # 向量检索（约 640MB）
ollama pull glm-ocr:q8_0             # 本地 OCR（可选）
```

Windows 的 `pandoc-crossref.exe` 已内置于仓库 `vendor/windows/`：加入 PATH，或在工作区 `config.yaml` 的 `tools.pandoc_crossref_path` 里指路。

体检表最后四行是你机器上的 agent CLI（claude / codex / agy / opencode）：装没装、技能装了几个。缺技能时它会直接给出补装命令。

> [!WARN]
> `magi setup --check` 的体检只查 PATH，**不读** `config.yaml` 里的 `tools.*` 路径。所以体检表显示 `[-] pdftoppm`、而你已经在 config 里配好了绝对路径时，实际摄入是能跑的——以实跑为准。

---

## 从 Wikify 迁移 {#migrate}

迁移就一条命令：

```powershell
magi migrate            # 在旧仓库根目录跑
```

它会把旧配置搬过来、标出项目里过时的技能、在 hub 根初始化任务追踪，并对每个课题跑一遍 `magi sync --fix`。`raw/`、`wiki/`、`inbox/` 的格式没变，数据原样可用。下面是每一步具体动了什么，以及新旧命令对照表。

MAGI 是 Wikify 的重构版：脚本集变成统一 CLI，任务状态外接 Beads，新增混合检索、命题溯源与文献雷达。**`raw/`、`wiki/`、`inbox/` 的格式没有变，你的数据完全兼容。**

### 三条命令 {#migrate-steps}

```powershell
# 1. 装新版（第 2 章的一键脚本）
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/Misaka16384/magi/main/install.ps1 | iex"

# 2. 删掉旧安装拷贝——旧 SKILL.md 会指挥 agent 去调已经不存在的脚本
magi setup --remove-legacy

# 3. 在 Hub 根目录跑一条命令（非破坏性）
cd <你的 KnowledgeHub>
magi migrate
```

**`magi migrate` 会一路做完**：逐个主题补齐脚手架 → 搬旧配置 → 重建图谱与目录表 → 在 hub 根 `magi pm init` → 每个主题 `magi sync --fix`（建索引、同步积压）。加 `--minimal` 只迁移不收尾。

`magi migrate` 会自动判断你给的路径是 hub 还是单个主题：hub 模式一次迁移 `topics/` 下所有**未归档**主题；单主题模式只迁移当前这个。

**它只做加法**：补齐缺失的 `CLAUDE.md` / `AGENTS.md` / `config.yaml` / `scratch/` 和各级 `_index.md`，然后重建 `output/graph.db`（新增 claims/evidence 表）和 `wiki/{concepts,references}/_index.md`。已存在的文件一律跳过——`raw/`、`wiki/` 内容、`config.md`、`log.md` 一个字都不会改。

**旧配置会自动搬过来**：它会在 `<课题>/.agents/`、`<hub>/.agents/`、`~/.claude`、`~/.gemini` 里找旧的 `config.yaml`，把 MinerU token、模型名、dpi、语义连边阈值等填进新配置（只填还是默认值的项，你后来手动改过的绝不覆盖），并打印搬了哪些键——token 只报键名不回显。

> [!NOTE]
> `magi migrate` **没有** `--dry-run`，也**没有** `--force`。非破坏性是写死在实现里的，不靠开关保证：它调用脚手架时从不传 `--force`，所以只可能新建缺失文件。重复跑是安全的，第二次会走「刷新索引」分支。

剩下的一步（要选装给哪个 CLI，所以没自动做）：

```powershell
cd topics\<你的主题> && magi skills install
```

> [!EXPECT]
> 每个主题先打印 `Migrating workspace: <path>`，有旧配置可搬时打印 `config carried from ...`，然后 `magi graph build: ok` / `magi wiki reindex: ok`。最后「Finishing up」跑 `magi pm init` 和每个主题的 `magi sync --fix`，并报出新的同步率。

> [!FIX]
> - **hub 模式最后说 `N/N topics migrated` 但中间有 `FAILED`**：这个汇总行和退出码不反映子步骤失败（已知缺陷）。**自己在输出里搜 `FAILED`**，对报错的主题单独进目录重跑 `magi migrate`。
> - **hub 模式没提醒建索引**：hub 模式只提示 `magi pm init`，不会提醒每个主题跑 `magi index` / `magi sync`。手动补上。
> - **迁移后 agent 还在提旧命令**：`magi setup --remove-legacy` 没跑，或宿主技能缓存没刷新——重启 agent 会话。
> - **某个主题没被迁移**：迁移会跳过既没有 `wiki/` 也没有 `raw/` 的目录。进那个目录单独跑 `magi migrate`——它会顺手把库登记进注册表。
> - **直接抛 Python 异常**：脚手架步骤没有异常保护，常见原因是文件被占用/权限不足（Windows 上编辑器锁了 `CLAUDE.md`）。关掉占用程序重跑即可，不会有半成品。

> [!WARN]
> **项目内的旧 skills 要单独处理。** 如果你的 hub 或课题目录里有 `.agents/skills/`（Wikify 时代复制进去的），`magi setup --remove-legacy` **管不到**——它只扫 `~/.claude` 和 `~/.gemini`。而 `.agents/skills/` 恰恰是 Codex、agy、opencode 都会读的目录，里面的旧 SKILL.md 会让 agent 去调已经不存在的脚本。`magi migrate` 现在会检测并提示，改名备份即可：`mv .agents .agents.wikify-backup`。

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

两条命令就能建好：

```powershell
magi init               # 在这个课题自己的目录里
magi install            # 装进你的 agent CLI：技能 + 协议块 + 收工闸门
```

一个课题一个目录，之上没有别的层。下面是生成了什么、多个库怎么一起用、以及 MAGI 怎么判断「当前工作区」。

### 一个库还是好几个 {#workspace-shape}

一个课题、一个目录，`magi init` 就完事。第二个课题就是第二个目录——不需要共同的父目录，
也不需要先规划。`magi init` 会把它登记进用户级注册表，于是：

```powershell
mkdir my-topic ; cd my-topic
magi init --name "显示名" --scope "一句话说清这个库收什么、不收什么"
magi install
magi pm init           # 可选：机械任务的任务库（会 git-init 本目录）
```

`magi search` 默认联邦检索所有启用的库，`magi kb list` 列出它们。v1 的 hub（父目录 +
`wikis.json` + `topics/`）退场了：它存在的理由是那份注册表，而注册表现在是每台机器一份，
库住在哪里都能被找到。

`--scope` 不是装饰：它会写进 `AGENTS.md` 的托管块，成为 agent 判断「这篇该不该收、这个概念
算不算本库范围」的依据。**写得越具体，后面自动化的判断越准。**

### `magi init` 生成了什么 {#workspace-layout}

```text
my-topic/
├─ AGENTS.md               agent 入场协议（`magi:begin` 托管块 + 你自己写的部分）
├─ CLAUDE.md               只有一行 `@AGENTS.md`——协议只有一份
├─ config.md               本库的人读说明（标题 + 研究范围）
├─ config.yaml             本工作区配置（OCR、模型、雷达……见第 5 章）
├─ decisions.md            只有人做的决定；agent 誊写，别的什么都不写进来
├─ inbox/                  待处理投喂区（PDF 丢这里）· notes.md 是你的随手堆放区
├─ raw/                    摄入后的原始文献 Markdown
│   articles/ papers/ repos/ notes/ data/
├─ wiki/                   编译产物
│   concepts/  概念卡    references/ 文献卡    topics/  专题综述
├─ threads/                命题 / 问题 / 研究线（论坛式跟帖，`magi thread`）
├─ drafts/                 推导与草稿
├─ output/                 graph.db、index.db、MAP.md、雷达账本
└─ scratch/                agent 的草稿纸，可随时清空
```

除 `inbox/` 和 `scratch/` 外每个目录都会生成 `_index.md` 目录表。

> [!NOTE]
> **没有 `log.md`，也没有 `wiki/theses/`。** 记录就是 `threads/` 里的跟帖，按时间读用
> `magi feed`——同一批事件写在两个地方，第一次有人只改了其中一个就开始打架。老库里这两样
> 照旧留着：没人再往 `log.md` 写，`magi migrate` 会把 `theses/` 搬进 `drafts/`。

> [!TIP]
> 用 Obsidian 打开**主题目录**（不要打开 Hub 根）。在 设置 → 档案与链接 → 排除档案 里加两条正则，图谱就只剩纯知识卡片：
> ```regex
> /(?:^|/)(?:_index|log|config|uncompiled-source-coverage|CLAUDE|AGENTS)\.md$/
> ```
> ```regex
> /^\..*|(?:^|/)(?:scratch|inbox|raw|output|vendor)(?:/|$)/
> ```

### 跨库工作 {#workspace-hub}

工作区之上没有别的层。一个库就是一个目录；`magi init` 会把它登记进用户级列表，
而正是这个列表让好几个库变成一个可检索的整体：

```powershell
magi kb list                      # 这台机器知道的所有库
magi kb disable <name>            # 让某个库不参与联邦检索
magi search "toric code"          # 先搜本库，再搜所有启用的库
```

v1 有 **hub**：一个带 `wikis.json` 注册表的父目录，下面挂 `topics/`，外加注册、归档、
恢复、跨库批跑一整套命令。它退场了。它存在的理由——那份注册表——现在是**每台机器一份**
而不是每个父目录一份，而这才是真正干活的部分；库也不必住在某个特定位置才被找得到。
归档一个课题＝`magi kb disable` 再把目录挪到你放完结项目的地方。

原本挂在 hub 下面的工作区照常能用：`magi migrate` 会把每个都登记好，文件一个不动。
hub 自己的 `wikis.json`、`topics/`、`log.md` 从此不起作用——你想删的时候再删。

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

摄入就一条命令：

```powershell
magi ingest auto              # inbox/ 里的全部
magi ingest auto paper.pdf    # 或者指定一个文件
```

它按文件本身是什么来选路线（arXiv 源码包走 LaTeX；PDF 先看自己的文本层够不够，
不够才走云端 OCR（有 token）或本地 OCR），并自动 finalize。只有在需要指定页码、想强制走某条路线、或者对付难搞的扫描件时，才用下面那些具体命令。

### 手上是链接不是文件？排队就行 {#ingest-queue}

有 arXiv 链接、DOI 或者期刊页面，而不是本地 PDF 的时候，**不要自己去下载**。
交给它，让它自己挑路线：

```powershell
magi ingest url "https://arxiv.org/abs/2608.16520"   # 也可以是 DOI，可以一次给多个
magi ingest batch-run                                 # 抓取 + 转换，无人值守
magi ingest batch-list                                # 看看转出来什么样
magi ingest batch-decide --item <ID> --decision approve
magi ingest batch-commit                              # 到这一步才真的进 raw/
```

`--library <名字>` 可以按名字排进某个已注册的知识库，不用非得站在那个目录里
（`magi kb list` 看名字）。

两件值得知道的事：

**它先试最好的源。** arXiv 自己为绝大多数论文发布 LaTeXML 渲染的 HTML，
里面**每个公式都原样带着作者写的 LaTeX**——不涉及任何识别。这条排在源码 tar 包之前，
tar 包又排在所有 PDF 路线之前。

到了 PDF 这一层，同样的道理再往下走一格。在花掉一个 MinerU token 或一分钟 GPU 之前，
MAGI 先问这份文档是不是真需要：**没有数学的原生电子版 PDF，可以直接读它自己的文本层**
——免费、快，而且忠实，因为那是文档自己的文字，不是对它的一次识别。**带数学的不行**：
字符出得来，二维结构出不来，所以照样交给模型。这个不用你选，闸门自己判，并把判断打出来。

**不点头，什么都进不了你的库。** `batch-run` 只写进暂存区就停下；只要批次里还有
一条没决定，`batch-commit` 就**直接拒绝**。而「拒绝」不等于丢弃——它会自动落到
**下一档路线**、出现在下一批里，所以「这份转得不行，换个法子」只要一条命令。

这一整套你的 agent 可以替你跑：**ingest** 技能接受链接、引文、甚至一张截图，
自己判断每个是什么，然后执行上面这些命令。

### 路线，怎么选 {#ingest-routes}

| 命令 | 适用 | 依赖 | 质量 |
|---|---|---|---|
| `magi ingest url` → `batch-run` | 任何有链接 / DOI / arXiv 号的东西 | Pandoc | **当前可用的最好一条**——自动挑保真度最高且跑得通的 |
| `magi ingest arxiv-html` | 直接抓某一篇 arXiv 论文 | Pandoc | **最好**——原始 LaTeX 就在 HTML 里逐字带着 |
| `magi ingest tex` | arXiv 源码包（`.tar.gz`）或 `.tex` | Pandoc | **最好**——公式、引文、编号原生保真 |
| *（自动）* 文本层 | 没有数学的原生电子版 PDF | `magi-research[textlayer]` | 忠实且免费——是文档自己的文字，不是识别出来的 |
| `magi ingest mineru` | 一般 PDF（含扫描件） | MinerU 云端 token | 好，版面/公式识别强 |
| `magi ingest ocr` | 一般 PDF，要求全离线 | Ollama + poppler | 中等——逐页视觉转录；公式是它的强项，表格也能保住（含表格的页会切成两半读）|
| `magi ingest add` | 已经是 Markdown/文本的材料 | 无 | 只做归档与 frontmatter 注入 |

> [!NOTE]
> **文本层路线默认不导出图。** `pymupdf4llm` 导出的是"每个嵌入图像对象"而不是"每张图"，
> 而且每一个都内联进正文：实测一篇 23 页、只有 4 张图的论文吐出 117 个文件，最小的
> 40×24 其实是一行行间公式被渲染成了图片。真要图就在 `config.yaml` 里设
> `ingest.textlayer_images: true`。如果图很重要，本地 OCR 那条路线按图标题锚定裁剪，效果好得多。

**懒得选？** `magi ingest auto` 按文件**本身是什么**来挑——源码包 → tex；PDF → 文本层够用就用它，
不够才 MinerU（有 token）或本地 OCR（没 token）；文本 → add——并且自动收尾。
它和 `batch-run` 的结论一定一致，因为走的是同一份代码：

```powershell
magi ingest auto paper.pdf        # 单个文件
magi ingest auto                  # 整个 inbox/
magi ingest auto --dry-run        # 先看它打算怎么走
```

需要指定页码、强制某条路线、或者对付难搞的扫描件时，再手动挑下面的命令。

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
  ocr: glm-ocr:q8_0               # 本地 OCR 模型（glm-ocr:q8_0 / qwen3-vl / qwen3-vl:4b ...）
  embedding: qwen3-embedding:0.6b # 语义检索与语义连边共用

ollama:
  base_url: http://127.0.0.1:11434
  autostart: true                 # 本机 Ollama 停着时按需拉起

embedding:                  # 不想装 Ollama 才需要这一段
  provider: ollama          # ollama | openai （openai = 任何 OpenAI 兼容接口）
  base_url: ""              # 例：https://api.siliconflow.com/v1 —— 要带 /v1
  model: ""                 # 例：BAAI/bge-m3；留空则沿用 models.embedding
  api_key: ""               # 也可以放进环境变量 MAGI_EMBEDDING_API_KEY，环境变量优先

tools:                      # 只有在这些程序不在 PATH 上时才需要填
  pandoc_path: ""
  pandoc_crossref_path: ""
  pdftoppm_path: ""
```

#### 不装 Ollama 也能做语义检索 {#embedding-cloud}

语义检索需要一个嵌入模型。默认走本机 Ollama，但任何说 OpenAI `/v1/embeddings`
这套协议的接口都可以：把 `embedding.provider` 设成 `openai`，填上面三个字段即可；
也可以在 WebUI 的「工作区配置」卡片里填，key 那一栏是遮蔽输入。

下面四家的接口形状都对着各自官方文档实际查过：

| 服务 | `base_url` | 模型 | 备注 |
|---|---|---|---|
| 硅基流动 SiliconFlow | `https://api.siliconflow.com/v1` | `BAAI/bge-m3`、`Qwen/Qwen3-Embedding-0.6B` | 中英都强，有免费模型；注册可能需要国内手机号 |
| Jina AI | `https://api.jina.ai/v1` | `jina-embeddings-v3` | 接口照 OpenAI 的形状设计，多语言，注册送额度 |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-embedding-001` | 普通 Google 账号即可；免费额度在 AI Studio 里看 |
| DeepInfra | `https://api.deepinfra.com/v1/openai` | `BAAI/bge-m3` | 没有免费额度，但每百万 token 只要几分钱 |

**免费额度请以各家页面为准**——它们变得很勤，而且上面几个数字并非全都能从静态页面确认；
能确认的是接口形状。

**Cohere、Voyage AI、智谱不支持**：它们的 API 不是 OpenAI 形状，每家都得单写一个客户端。

> [!WARN]
> 换嵌入模型会改变向量维度，旧索引装不下不同宽度的向量。换完要跑
> `magi index --rebuild`——它会删掉索引重建。索引是从 `wiki/`、`raw/` 推导出来的
> 派生数据，删了不会丢你的东西。

> [!EXPECT]
> `magi index` 照常打印逐文件进度，`magi search` 报 `语义检索：已启用`。

> [!FIX]
> - **提示 `no API key is set`**：`embedding.provider` 是 `openai`，但
>   `embedding.api_key` 和环境变量 `MAGI_EMBEDDING_API_KEY` 都没有值。
> - **提示 `this index holds N-dimension vectors`**：换了模型没重建。跑 `magi index --rebuild`。
> - **接口返回 401 / 403**：key 不对，或者额度用完了。上面几家都能在自己的控制台看余额。

`OLLAMA_HOST` / `PANDOC_PATH` / `PANDOC_CROSSREF_PATH` / `PDFTOPPM_PATH` / `PDFIMAGES_PATH` / `MAGI_NO_OLLAMA_AUTOSTART` 这六个环境变量**优先级高于 config.yaml**，其余所有键都只能改文件。

> [!WARN]
> **YAML 写错不会报错。** 自动发现的 `config.yaml` 解析失败时，程序静默回退到内置默认值，一个字都不提示。改完拿这条验一下：
> ```bash
> python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"
> ```

> [!NOTE]
> `ocr.use_mineru` 这个键**只对 agent 有效**——是给 `ingest` 技能读的路由提示。你在终端直接敲 `magi ingest mineru` 时它不看这个键，只看 token 有没有配。同理 `pdf.quality` 和 `output.encoding` 目前是空转的，改了没有任何效果。
> 还有一批键 `magi init` 生成的模板里没有、但代码确实会读：整个 `tools:`、`pdf:`、`output:` 段，以及 `radar.min_relevance` / `radar.own_arxiv_ids` / `radar.citation_gap.*`。需要时自己加进去就行。

### 跑一遍 {#ingest-run}

最省事的方式：把 PDF 丢进 `inbox/`，然后对 agent 说「摄入 inbox 里的论文」（或 `/magi:ingest`）。它会选路线、转格式、收尾。想手工跑：

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
| `OCR 模型 X 不可用` | 模型没拉 | `ollama pull glm-ocr:q8_0` |
| `pdftoppm 未找到` | 缺 poppler | 装 poppler，或配 `tools.pdftoppm_path` |
| `第 N 页 OCR 失败` | 单页重试两次仍失败 | **直接重跑一模一样的命令**：成功页缓存在 `.temp/`，只会重做失败页 |
| 公式乱码、下标粘连 | 渲染精度太低 | 把 `ocr.dpi` 提到 150 再重跑 |
| 摄入后 `Warning: 'magi math check' failed` | 公式校验发现问题 | `finalize` 不会因此中断；单独跑 `magi math check <文件>` 看详情，见第 6 章 |

> [!NOTE]
> **含表格的页面会被切成左右两块分别识别。** 整页发过去,模型转到长表格一半就停
> ——实测 49 行只出 24 行,而且把上下文窗口开到四倍,输出逐字节相同。把左右两半
> 按同样分辨率分别给它,49 行全部拿到。只有 PyMuPDF 认出表格的页会切,所以代价
> (那一页约两倍时间)只花在有收益的地方。扫描件没有文本层、找不到表格,仍按整页
> 处理,和以前一样。
>
> `.temp/` 里的缓存会记下它是用哪套提示词、切没切图产生的,两者都对得上才会复用
> ——否则重新识别,而不是拿一份配方已经变了的旧答案交差。

> [!NOTE]
> `magi ingest ocr` **没有** `--resume` 开关——续跑是自动的：只要输出目录还在，重跑同一条命令就会复用 `.temp/page_N.json` 里已完成的页。有失败页时 `.temp/` 会被特意保留。确认全部做完后可以手动删掉它。

---

## 编译成知识库 {#compile}

编译是唯一没有命令的一步——你对 agent 说：

> 「把待编译的都编译了」

它会执行 `compile` 技能：读懂每篇摄入进来的论文、拆出概念、判断哪些属于本库范围、写成结构化的互链卡片。`magi compile` 不存在、以后也不会有——这是理解工作，CLI 在这一层只负责检查和修补 agent 写出来的东西。

编译完，三条命令收尾：

```powershell
magi lint --fix         # 结构问题，能自动修的直接修
magi link               # 找出该互链或该合并的概念
magi graph build        # 把新卡片刷进图谱
```

> [!WARN]
> `magi graph build` 在 `wiki/` 空着的时候**照样返回成功**，只是建了一张空图。所以「图谱是空的」往往不是图谱坏了，而是还没编译。用这条确认：
> ```powershell
> magi graph query "SELECT COUNT(*) FROM nodes"
> ```

### 主线 {#compile-main}

在 agent 里依次说（或用斜杠命令）：

| 说什么 | 技能 | 做什么 |
|---|---|---|
| 「编译 raw 里的新文献」 | `compile` | 每篇 raw 源 → 一张 `wiki/references/` 文献卡，顺手抽出概念卡 |
| 「深挖这篇的概念」 | `compile` | 对已编译的卡片二次扫描，补挖第一遍漏掉的定理/引理 |
| 「合并重复概念」 | `tidy` | 同义概念物理归并、过宽概念拆分、多源定义重写 |
| 「清理标签」 | `tidy` | 标签/别名本体论归一（见第 7 章） |
| 「体检并修复」 | `magi lint --fix` | 死链、frontmatter、公式的自动修补——确定性命令，不需要 skill |
| 「公式被摄入弄坏了」 | `tidy` | 全库把坏公式抓成一张清单，逐条读懂再改 |

对应的确定性命令：

```powershell
magi wiki uncompiled                      # 还有哪些 raw 源没编译（编译进度就看它）
magi lint --fix                           # 结构自愈：补 frontmatter、归位文件、重建目录表
magi wiki reindex .                       # 重建 concepts/、references/、topics/、theses/ 的 _index.md 目录表
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
> - `Master _index.md is missing`：标着 fixable，但 **`--fix` 并没有实现这一条**；`config.md is missing` 压根没标 fixable。两个都得手工建。
> - **在 hub 根跑 lint 几乎什么都不查**：hub 根只做最外层结构检查。真正的质量闸门要进主题目录跑。

> [!WARN]
> `magi lint --json` 里的 `status` 字段和退出码**判定标准不同**：JSON 的 status 只要有任何 warning/suggestion 就是 `fail`，而退出码和文本版 `Result:` 只看 critical。CI 里请以退出码为准。

### 公式 {#compile-math}

```powershell
magi math format                    # 机械修复：$$ 配对、\tag 位置、eqnarray→align、OCR 粘连
magi math check                     # 只报错不改：整库扫一遍，按文件列出坏在哪
magi math check --json              # 同上，但输出一张可逐条处理的工单
```

**两条命令默认都作用于整个工作区**（和 `magi lint` 一样），也可以像 `magi math check raw/papers/x.md`
这样只点一个文件或目录。范围限定在 `wiki/ raw/ drafts/`——`format` 是就地改写且没有 dry-run，
`scratch/` 里放的正是概念卡备份，不能被它碰。

顺序永远是**先 format 再 check**：能机械修的先修掉，剩下的才值得人去读。

`--fast` 跳过逐文件的 pdflatex 深检（大库能省几分钟），`--wiki-only` 只看编译好的卡片。

`--json` 每条一个公式，带 `id`（`路径:行`，可勾掉）、行范围、原始 TeX、以及 `confidence`：

| `confidence` | 含义 |
|---|---|
| `certain` | 结构确实坏了：括号不配对、环境不匹配、`$$` 没闭合 |
| `likely-macro` | pdflatex 不认得这个宏——**九成是它没加载的宏包，不是错字** |

> [!TIP]
> **同一文件里连续好几条，通常是同一个缺陷。** `$$` 是顺序配对的，少一个闭合符会让后面每一对
> 都错位、各报一条。**改第一条再复验那个文件**，一百多条常常塌成十几处真实改动——千万别自底向上改。

**逐条修不用自己扛**：`tidy` 技能就是干这个的——先跑 format，再按 `wiki/` 优先的顺序
读原文、必要时对着源 PDF 核对、改完单文件复验。在 agent 里说「把公式修一下」即可。

> [!NOTE]
> `Undefined control sequence` 多半是**误报**——校验器不认识某个宏包的宏而已。抽一个对照原 PDF 确认后，其余同类可以忽略。真正要改的是 `Double subscript`、`Missing }`、`Unexpected end of stream` 这类结构错误：用 `magi ingest crop <pdf> --text "<附近文字>" --out scratch/crop.png` 把原文裁出来对着改。
> `[WARNING] Orphaned $$ remains on line L` 是 format 自己也判断不了的边界，必须手工配对。

---

## 知识图谱 {#graph}

图谱是一条命令建、一条命令看：

```powershell
magi graph build              # 编译出新卡片之后
magi graph browse overview    # 节点/边数、标签、断言、断链
```

不想敲命令的话，看板的图谱视图看的是同一份数据。下面是全部 browse 视图、图谱不对劲时怎么办、以及在 Obsidian 里读它。

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
| **节点太少** | 文献还没编译成卡片；或者图是旧的 | `magi wiki uncompiled` 看积压 → 用 `compile` 编译 → `magi graph build` |
| **一堆孤立点** | 卡片正文里没写双链，也没跑过语义连边 | `magi link .`（见下）；系统性补链用 `compile` |
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
> - `[Error] Cannot reach Ollama`：本机 Ollama 停着会被自动拉起，所以报这个就是压根没装（或者 autostart 被关了）。去 https://ollama.com 装一个。
> - `Embedding model ... is not installed`：MAGI 只负责把服务叫醒，模型得自己拉——`ollama pull qwen3-embedding:0.6b`。
> - `[Info] Not enough concepts to analyze`：少于两张非 stub 概念卡，正常退出，不是错误。
> - `magi graph browse links --node X` 说 `node not found`：X 既不是节点 ID，标题也不唯一。先用 `browse nodes --q X` 拿到确切 ID。
> - 某个文件的标签死活进不了图：frontmatter 的列表写法不规范。`magi lint --fix` 之后重建。

### 在 Obsidian 里看 {#graph-obsidian}

MAGI 的双链就是 Obsidian 的双链，两边可以同时用：Obsidian 负责肉眼浏览与手工编辑，`magi graph` 负责结构化查询。排除规则见 4.2 的提示框。本看板的 **Melchior → 图谱视图** 是同一份数据的力导向渲染，指向不存在页面的链接会显示成「幽灵节点」——和 Obsidian 的表现一致。

---

## 检索 {#search}

检索是两条命令：

```powershell
magi index                       # 加了或改了卡片之后
magi search "kramers-wannier"    # 找东西
```

`index` 是增量的，重跑很便宜；`search` 会把关键词匹配和语义匹配融合，范围是本库加上你启用的其它库。下面是各种模式、范围，以及结果上那些徽章是什么意思。

### 建索引 {#search-index}

```powershell
magi index                # 建/刷新 output/index.db
magi index --no-vectors   # 只建关键词索引（没有 Ollama 时）
magi index --quiet        # 不打进度行（末尾汇总照常输出）
```

索引覆盖 `wiki/`、`raw/`、`drafts/` 下所有 `.md`，按一到三级标题切块，单块上限 250 行。**增量更新**：内容哈希没变的文件跳过，删掉的文件自动清理。

慢的是嵌入这一半；如果这个库当初是在没有 Ollama 的情况下建的索引，那要补的就是整个语料。过程中会持续报进度，并且**每批各自提交**——中途打断也不会丢掉已经算完的部分，下次接着补。

> [!EXPECT]
> ```
> index: backfilling vectors for 1371 chunks
> index: backfill: 320/1371 chunks
> index: 1371 chunks (0 files updated, 141 unchanged, 0 pruned) · vectors 1371/1371
> ```
> 结尾若是 `· BM25-only (Ollama unavailable)`，说明向量那一半没建起来。

每次送 16 块给 Ollama。要改就在 `config.yaml` 里设 `ollama.embed_batch`——调大更快，但 Ollama 那边内存占用也更高；嵌入服务跑到一半被杀掉，代价远大于省下的那点时间。

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
> - **结果全是关键词命中，没有语义** → 结尾会提示 `BM25-only`。MAGI 已经试过拉起本机 Ollama 了；还是 BM25-only 就说明它没装、或者嵌入模型没拉。用 `magi setup --check` 看一眼，再重跑 `magi index` 补向量。
> - **索引任务在跑的时候，搜索提示降级成了关键词** → Ollama 一次只处理一个请求，索引任务会一直占着它。搜索等 8 秒还拿不到向量就先把关键词那一半结果返回来，而不是干等着；等任务跑完再搜一次即可。
> - **`magi index` 中途停了，报 `Ollama stopped responding mid-run`** → 嵌入服务挂了（最常见是内存不够）。挂之前算完的都已经提交，重跑 `magi index` 补剩下的。要是反复出现，把 `ollama.embed_batch` 调小。
> - **中文搜不出东西** → 提示 `this index predates CJK-aware tokenization` 时，重跑 `magi index` 即可（会自动重建分词层）。
> - `index dims mismatch current embedding model` → 换过嵌入模型。改回去，或重跑 `magi index` 全量重嵌。
> - `sqlite-vec unavailable` → 向量扩展加载失败（macOS 上常见于系统 Python 不支持加载扩展）。用 uv/Homebrew 的 Python，或接受关键词检索。

> [!NOTE]
> `magi index --rebuild` 会删掉索引重建，这就是「从头来」。换嵌入模型之后必须跑一次——向量表是按固定宽度建的，装不下不同维度的向量。手动删 `output/index.db` 效果一样；索引是从 `wiki/`、`raw/` 推导出来的派生数据，两种做法都不会丢东西。
> `magi grep "<正则>" <文件...> [-i]` 是另一回事——它不读索引，就是对指定文件做正则行匹配（Python 正则语法，输出 JSON，最多 200 条，带 5 秒防卡死保护）。文件很少、要精确匹配字面量时用它；要「找相关内容」用 `magi search`。

---

## 研究状态 {#threads}

课题的状态住在文件里，不在任务追踪器里。`threads/` 下每篇 note 是一个**命题**（有真值，
研究的基本单元）、一个**问题**（开放式，答案是一批命题），或者一条**研究线**（正文就是
它的 STATUS：到哪了、卡在哪、下一步）。文件名就是它的 ID，建好不改。

```powershell
magi thread new p-gap --kind proposition --title "弱无序下能隙不闭合" `
  --purpose "决定要不要投一个月做数值" --line qec --bet supported
magi thread status p-gap testing --text "L=64 起跑"   # 改状态，顺手把原因记下
magi thread post p-gap --text "L=64 收敛，试 L=128"    # 只是说句话，不改状态
```

命题的生命周期是 `open → conjectured → testing → supported | refuted → superseded`；
审核驳回或证据冲突会把它打到 `disputed`，那是要人来判的。**改状态必须带一条跟帖**——
所以 `magi thread status` 把两件事一起做了，你没法只做一半。

每篇 note 分两半：正文归开它的人，`## Discussion` 只追加、谁都不改别人的帖子。
**用命令而不是编辑器改**：追加是带锁的，编辑器写整个文件不带锁，两个 agent 同时写会
丢帖子（Windows 上尤其会，那里的追加不是原子操作）。

`magi lint` 顺带校验这些：状态词对不对得上 kind、跃迁链合不合法、改了状态却没写跟帖。

### 下一步做什么

```powershell
magi next             # 该做什么：从 note 派生的候选清单，只提议不执行
magi next --line qec  # 只看这条线
magi feed -n 20       # 所有跟帖按时间倒序——记录本身
magi sync --close     # 收工闸门：还有没写下来的事就拦住
```

在工作区里不带任何参数运行 CLI，跑的就是 `next`——一个入口，路由自己决定。

`magi next` 的顺序是有理由的：**记账债在最前**，因为它下面每一行都是从当前不对的 note
算出来的；然后是**只有人能决定的事**（审核驳回、两个写者撞车、该不该转向），它们不能排在
机器活后面；最后才是工作本身，每条线最多提一条——把所有开放命题都列出来就等于列出整个
项目，那排序就不再有意义。没有欠账、没有待决、没有在等的东西时，它只列开放问题然后闭嘴。

### 复核与拍板

```powershell
magi review               # 让另一个厂商的 CLI 无头复核所有"声称已解决"的命题
magi review p-gap --dry-run   # 先看会问谁、问哪几条
magi decide --about p-gap --bet supported --text "我赌它在体相里成立"
```

**评判要远离。** 自己给自己打分不是复核——同一套推理已经说服过它一次，第二遍会以同样的
理由同意。所以复核跑在**另一个厂商的 CLI** 里，按 PATH 探测自动选一个不是作者的：不同的
模型、不同的系统提示、没有共享的对话。只装了一个 CLI 也照跑（干净会话仍然有价值），但结论
里会写明是哪种。一个都没装时**什么也不算通过**——宁可留着没复核，也不能让"没人可问"变成
"自动通过"。

复核只看命题、它的 `derivation:` 和它引的 `raw/`——不看聊天记录，也不看这条线自我感觉如何。
「远」指的是不共享上下文，不是不给证据。它**只能发表意见**：驳回把命题打到 `disputed`
（那是要人判的事），不是 `refuted`（那会是一个结论），也不会在下一次运行时自己翻回去。

**没跑成的复核什么都不写。** 一条命题之所以不再排队等复核，是因为帖子里有人读过它——所以
CLI 没装、超时、进程崩了，note 一个字都不动，命题继续在队列里。读不懂的回答会写帖（原文附
在里面：那是分辨"适配器坏了"和"这条真判不了"的唯一办法），但 `unclear` 也不是答案，命题
照样回队列。

`magi decide` 是 agent 替人**原样**誊写。人只在对话里说话，不开文件——一个需要人去开文件
的系统，第二周记录就是空的。誊写会同时写进 `decisions.md`、给命题打上 `bet:`、并在讨论区
留一条署名 `human` 的帖；`sync --close` 查"离开 disputed 有没有人拍过板"看的正是这条。

原样也包括"人说的话本身长得像格式"的时候。有人说「我担心的正是这个：`status: testing ->
refuted`」，这一行会被围栏引起来而不是被解析——否则它会变成一条**签着说话人名字**的状态
迁移，而伪造一个人的签名比丢一行更糟。

`magi sync --close` 是会话结束前的闸门：有"做了但没写下来"的事就拒绝通过，并列出是哪几条。
它同时会把**5 分钟内被两个不同写者翻过的状态**标成 `conflict`（那不是状态，是分歧，只有人
能判），并重画 `output/MAP.md`。**MAP.md 是渲染出来的**——改它不改变任何事，状态在 note 里。


## 写论文 {#writing}

日常就这三条，按这个顺序：

```powershell
bd ready                # 现在值得做的是什么
magi verify             # 检查每条 CLAIM 背后都有证据
magi bib --fetch        # 把引用过的导成 BibTeX
```

写作本身发生在 `drafts/` 里，由你和 agent 对着编译好的卡片写。下面是任务追踪怎么配、起草流程、以及断言是怎么被核验的。

### 任务待办怎么用 {#writing-tasks}

MAGI 不自己实现任务系统，它对接 [Beads](https://github.com/gastownhall/beads)（`bd`）。**一个 hub 一个任务库**，各主题的 issue 用 `topic:<名字>` 标签区分。

```powershell
magi pm init          # 在 hub 根跑一次：建库 + 注册六种科研 issue 类型
magi sync             # ready / in progress / blocked 计数，连同其余状态一起看
magi pm backlog-sync  # 把「还没编译的 raw 源」变成待办
```

> [!NOTE]
> `magi pm init` 就在当前项目里建库（v2 起不再往上找 hub），一个项目一个任务库。任务库只放机械活——编译积压、待读、待审；课题状态在 `threads/` 里，那里才装得下状态和论证。给某条线开的活打 `line:<线名>` 标签。

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

写作循环（技能 `draft` 会带着你走，手工也一样）：

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
SOURCE: raw/papers/laughlin-1983.md
```

`SOURCE:` 指向 `raw/`，不指向 `wiki/references/` 的卡片。参考卡是从 `raw/` 编译出来的派生视图，它可能错在恰好是这条论断要排除的地方——引卡片等于把编译错误洗成事实。`magi lint` 会把指向参考卡的证据标出来。

`FINDING:` 是 `CLAIM:` 的同义词。四个字段缺一不可。然后：

```powershell
magi verify drafts/paper.md --topic-dir .            # 退出码 0=全部通过，1=有未核验
magi verify drafts/paper.md --topic-dir . --fetch-web  # 网页来源也真的抓取比对
magi validate wiki/theses/x.md --schema thesis       # 论断报告的结构校验
```

> [!NOTE]
> `verified` 的含义是**引文存在性**——那句话确实逐字出现在来源文件里（空白、全角标点、连字符差异都能容忍）。它**不判断**你的论断和这句引文在语义上是否成立，那一层归人和 LLM 审查（`research` 技能）。`magi claims verify` 是同一条命令的别名。
> 引文必须是单行引号内容；多行引文不被支持。

> [!WARN]
> `magi validate --schema research` 里那条「有 N 个段落没有引用」的提示措辞很温和，但它**会让退出码变成 1**。写 CI 时注意。

---

## 文献雷达 {#radar}

设一次，之后每周分流：

```powershell
magi radar install-schedule     # 一次——之后每天凌晨 3 点自动收割
magi radar harvest              # 或者随时手动跑一次
```

新候选落在 `inbox/radar/<日期>-digest.md`。在看板的**文献雷达**页里分流——跳过 / 收进 inbox / 建阅读任务，一行一篇；或者对 agent 说「审一下雷达简报」，让 `radar_review` 技能去判分。

收割本身是确定性的：它只负责收，不做判断。下面全是配置和调优。

### 配置 {#radar-config}

写在工作区 `config.yaml`：

```yaml
radar:
  arxiv_categories: [cond-mat.str-el, hep-th]   # 每天扫哪些分区
  seed_arxiv_ids: ["2301.01234"]                # 种子论文（推荐算法的正样本）
  days: 7                    # arXiv 回溯窗口
  max_candidates: 40         # 每次最多留几条
  min_relevance: 0.50        # 相关度下限（可选；不写=不过滤——见下方说明）
  own_arxiv_ids: ["2402.05678"]     # 「我方论文」，citation-gap 用
  citation_gap:
    min_shared_refs: 2       # 共引门槛
    years: 2                 # 只看近几年
```

`min_relevance`、`own_arxiv_ids`、`citation_gap.*` 这三组**不在 `magi init` 生成的模板里**，需要时自己加。

相关度是「候选摘要与本库嵌入质心的余弦相似度」，所以它依赖 `magi index` 建好的向量索引 + 可用的 Ollama；没有的话候选按来源顺序排列，不打分。

> [!NOTE]
> **这个分数要当排名看，不要当概率看。** 能进简报的候选，本来就来自你配的 arXiv 分类、或者以你自己论文为种子的推荐——打分之前它们就已经是「像样的」了，所以分数会挤在量程的高端。在一个真实的 67 篇论文的库上实测：40 个候选全部落在 **0.55–0.70** 之间；而真正无关的文本分数低得多——一篇普通凝聚态论文 0.45、一篇机器学习论文 0.37、随机字符 0.31。
> 
> 也就是说 `min_relevance` 是用来兜**分类层面**的错的（比如 arXiv 分类填错了，把另一个领域的东西拉了进来），不是精度旋钮。取 0.50 左右能兜住这种情况，除此之外什么也不会拦；调到 0.60 以上就开始误杀了。排序在列表顶端是可信的、在中位数附近基本是噪声——界面里因此把它显示成每批内部的 **高相关 / 中等 / 偏低**，原始余弦值放在悬停提示里。

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
- **Linux**：**什么都不会装**——只打印一行建议的 crontab（会按你传的 `--time` 来），自己 `crontab -e` 加进去。

> [!WARN]
> 任务名里含工作区路径的哈希。**移动或改名工作区之后，`--uninstall` 就找不到旧任务了**，得手动删（`schtasks /Delete /TN <名字> /F` 或删 plist）。

### 噪声调优 {#radar-tuning}

| 症状 | 处理 |
|---|---|
| `harvest: no new candidates` | 种子和分区是不是空的？窗口太窄？`--days 30` 试试。也可能真的都收过了——账本在 `output/radar/seen.jsonl`，**没有命令能重置它**，要重刷得手动删行 |
| 候选太多太杂 | 先精简 `arxiv_categories`——噪声是从那儿进来的；再调低 `max_candidates`。`min_relevance` 在这件事上很钝（见上方说明） |
| 想暂停雷达但不想卸掉定时任务 | 把 `max_candidates` 设成 0；harvest 会直接退出，不会去调 arXiv 或 S2 |
| 相关度全是空的 | 提示 `relevance scoring unavailable`——先 `magi index` 建向量索引。停着的 Ollama 会自己起来；还是空的就是没装、或者模型没拉 |
| `warning: S2 recommendations failed` | Semantic Scholar 限流或网络问题；调用是匿名的，没有 API key 可配，过一会儿重跑 |
| `arXiv query failed for <分区>` | 简报 frontmatter 会记 `sources_failed`，`magi radar status` 也会提示；重跑补齐 |
| `citation-gap: no candidates survived` | 漏斗太严：降 `min_shared_refs`、升 `years` |
| `has no reference data on S2 yet` | 论文太新，S2 还没索引它的参考文献，等几天 |
| `Semantic Scholar did not answer (rate limit or outage)` | 这是另一回事：S2 拒绝了请求，所以这篇到底有没有参考文献数据是**未知**，不是没有。过会儿重试 |
| 简报越积越多 | 只有审阅动作会把 `status: pending-review` 改成 `reviewed`；同一天重复收割会生成 `-2`、`-3` 的副本，越积越乱。定期审 |

---

## 本地看板 {#webui}

看板就一条命令：

```powershell
magi ui                 # 打开 http://127.0.0.1:8737
```

在 hub 根跑就能在一个界面里看所有课题，在课题目录里跑就只看那一个。它读写的是 CLI 用的同一批文件——没有任何东西只存在于浏览器里。

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
| **Melchior（认知）** | 概念/文献计数、命题与证据表、待编译积压、图谱七视图 + 只读 SQL 台、BibTeX 复制、草稿列表——点任意节点即可读到那张卡片 |
| **Balthasar（任务）** | Beads 计数 + 一键「把积压同步成任务」 |
| **Casper（文献检索）** | 检索实验台：模式/范围/集合/路径过滤，与 `magi search --json` 完全同构——点一条命中就打开卡片，直接停在命中的那一段 |
| **文献雷达** | 简报阅读 + 逐条审阅动作 |
| **运维与危险区** | 服务端操作白名单 + 输入操作 ID 二次确认 + 实时终端，任务历史落盘 |
| **文档与指引** | 就是你现在看的这份，外加 README 与 CLI 命令参考 |

> [!NOTE]
> **读卡片的入口只有一个。** 图谱上的节点、侧栏里的链接、卡片正文里的 `[[双链]]`、
> Casper 里的一条检索命中——点开的都是同一个渲染视图：公式排好版的 markdown、
> 从卡片自己的 `images/` 里取出的插图、就地画出来的 mermaid 图，正文旁边是目录
> 大纲。检索命中会停在匹配的那一段而不是文件开头；命中落在哪个已注册的库里，
> 预览就去那个库里读。

**看板能触发的后台任务只有 14 个**：建索引、建图谱、重建目录表、语义连边、lint 修复、统计、积压同步、雷达收割、引用缺口，以及需要二次确认的 setup / migrate / pm init / 删除旧版拷贝 / 雷达定时任务。

> [!NOTE]
> **摄入不在其中**——`magi ingest *` 全系列只能在终端或经由 agent 调用。同理 `magi init`、`hub *`、`sync`、`validate`、`verify`、`tags *`、`math *` 也没有按钮。

顶栏的 **⚡ MAGI 模式** 切换战术主题：红色为战斗态（深色），蓝色为静默值守（浅色），☀︎/☽ 在两者间切换。

右下角的 ◐ 是材质与背景面板：玻璃模糊度、不透明度、CRT 扫描线，以及**背景选择**——缩略图里点一张就固定用它，点几张就只在这几张里换，都不选则按窗口比例自动轮换（红蓝两态各记各的）。想用自己的图：放进 `~/.config/magi/ui-backgrounds/blue|red/` 即可。

> [!FIX]
> - **端口被占**：换 `--port`，或先关掉上一个实例。
> - **改了代码/升级后界面没变**：静态文件是即时生效的，但**后端改动需要重启 `magi ui`**。样式不更新则是浏览器缓存，硬刷新一次。
> - **图谱是空的**：先 `magi graph build`。
> - **看板打不开或显示无工作区**：顶栏切换工作区；看板只监听 `127.0.0.1` 并带 Host 白名单，**默认不能从别的机器访问**（远程用 SSH 端口转发）。

---

## 疑难速查 {#troubleshoot}

两条命令能解决大部分问题：

```powershell
magi sync                          # 这个工作区接下来该做什么，连修复命令一起给出
magi guide --symptoms              # 拿你真正看到的报错去查
```

`magi sync --fix` 会把其中确定性的那些直接跑掉。下面是需要人来判断的那些症状。

按症状找，不用记命令归属。也可以直接在终端里查同一张表：

```powershell
magi guide --symptoms                       # 全书症状索引（84 条左右）
magi guide --symptoms --search "ollama"     # 按关键词过滤
```

或者把报错贴给 agent，让它跑 `magi guide --search`（见 [1.2](#howto-read)）。

| 症状 | 先跑这个 |
|---|---|
| 完全不知道下一步做什么 | `magi sync` —— 看最后一行 `->` |
| 装完了但 `magi` 找不到 | 开**新终端**；仍不行把 `~/.local/bin` 加进 PATH |
| 升级时报 `failed to remove directory ... Lib: 拒绝访问` | Windows 上 `magi ui` 正开着，占用安装目录。关掉看板再重装 |
| 某个功能报缺依赖 | `magi setup --check` |
| 命令说 `no workspace found` | `cd` 进主题目录，或加 `--topic-dir` |
| 不知道某个库在哪 | `magi kb list` |
| 摄入完了但库里没有 | 忘了 `magi ingest finalize` |
| 图谱是旧的 | `magi graph build` —— 它没有增量模式 |
| 搜不到刚写的东西 | `magi index` —— 它不会自动触发 |
| 检索没有语义结果 | `magi setup --check`——停着的 Ollama 会自己起来，所以是没装或模型没拉；然后 `magi index` 补向量 |
| 双链点不开 / 断链多 | `magi graph browse broken` |
| 概念重复、标签发散 | `magi link . --dedup-only`；`magi tags extract` |
| 卡片格式报错 | `magi lint --fix` |
| 公式渲染不对 | `magi math format` → `magi math check`（整库；`--json` 出清单交给 `tidy` 技能逐条修）|
| 引用导不出来 | 检查文献卡 frontmatter 的 `title/authors/year/arxiv_id` |
| 论断被标 unverified | 引文要与来源逐字一致，且必须单行 |
| 雷达没有新东西 | 检查 `arxiv_categories` / `seed_arxiv_ids`；`--days` 放宽 |
| 定时任务不触发 | Windows `schtasks /Query`；Linux 上它根本没装，自己写 crontab |
| 配置改了没效果 | 用 `python -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"` 验一遍——YAML 解析失败是静默的 |
| 想看某条命令到底有什么参数 | `magi <命令> --help`，或本页顶部的 **CLI 命令参考手册** |
| 不知道该读哪一章 | `magi guide --search "<报错原文>"` |

> [!TIP]
> 所有命令的完整参数以 `magi <命令> --help` 为准——这份指南讲的是**何时用、期望什么、出错怎么办**，参数清单不重复维护。
