# MAGI

*[中文](README.md) | [English](README_en.md)*

**MAGI** 是一个 agent-native 的科研工作环境：人是驾驶员，LLM agent 是机体，确定性的 `magi` CLI 是拘束具——三者同步率越高，科研越快。它把学术论文（PDF/LaTeX）摄入、编译为 Obsidian 兼容的概念卡片知识库，并用三核架构管理完整的科研状态：

| 核 | 状态 | 由谁承载 | 回答的问题 |
|---|---|---|---|
| **MELCHIOR** | 认知状态（知识） | 概念/文献卡片 + SQLite 知识图谱 + claim/证据溯源 | 我们知道什么？为什么可信？ |
| **BALTHASAR** | 意图状态（工作） | [Beads](https://github.com/gastownhall/beads)（`bd`）科研任务图 | 我们在做什么？下一步是什么？ |
| **CASPER** | 检索状态 | 本地混合检索（FTS5 BM25 + sqlite-vec 向量 + RRF） | 此刻该读什么？ |

进入任意工作区先跑 **`magi sync`**——它输出**同步率**、三核状态和逐条可执行的修复提示。`magi radar` 是文献雷达：定时发现相关新论文，并侦察"知识上应引用我方论文却未引用"的候选。同一份 skills 通吃 Claude Code / Codex / Antigravity 等 CLI agent 宿主。

任何命令的完整语法：`magi <command> --help`；全景：`magi --help`。

---

## 🌟 项目展示

![知识图谱可视化](./graph.png)
*自动生成的密集语义图谱，展示物理与数学概念。*

![编译出的文献卡片](./note1.png)
*从排版混乱的 PDF 编译出的整洁文献卡片。*

![数学与概念提取](./note2.png)
*从 LaTeX 源码提取并格式化的数学证明与引理。*

---

## 1. 架构：CLI、Skills 与宿主的分工

```text
你（驾驶员）
  └─ Claude Code / Codex / Antigravity（机体：负责推理、写作、判断）
       ├─ skills/*/SKILL.md   —— 教 agent「何时、为何」执行各条流水线
       └─ magi CLI（拘束具）  —— 所有确定性操作：摄入、图谱、检索、校验、任务、雷达
            └─ 持久状态在文件与数据库里：raw/ wiki/ output/ .beads/
```

- **CLI 负责语法**且自描述（`--help`）；**skills 只讲方法论**，不复制参数清单。
- 持久状态永远落盘；agent 的上下文是一次性的（fresh-context worker 模式）。
- JSON 输出（`--json`）的形状即未来 `magi mcp` 的工具契约。

---

## 2. 安装

### 2.1 `magi` CLI（必装）

需要 **Python 3.10+** 和 [uv](https://docs.astral.sh/uv/)（或 pipx）：

```powershell
git clone https://github.com/Misaka16384/magi.git
cd magi
uv tool install .            # 或: pipx install .
magi --version               # magi 0.1.0
```

升级：

```powershell
git pull && uv tool install . --force --reinstall
```

> 包名为 `magi-research`，命令名为 `magi`。暂未发布 PyPI，从仓库安装即可。

### 2.2 Beads（`bd`，强烈推荐）

任务/工作状态由 [Beads](https://github.com/gastownhall/beads) 承载（`magi pm init` 会配置六种科研 issue 类型：question / survey / derivation / computation / experiment / review）。

- **Windows**：`irm https://raw.githubusercontent.com/gastownhall/beads/main/install.ps1 | iex`（或从 [Releases](https://github.com/gastownhall/beads/releases) 下载 `beads_*_windows_amd64.zip`，把 `bd.exe` 放进 PATH）
- **macOS / Linux**：见[官方安装文档](https://github.com/gastownhall/beads/blob/main/docs/getting-started/installation.md)（Homebrew / npm / go install 均支持）

没有 `bd` 时 MAGI 相关功能优雅降级（sync 会提示安装）。

### 2.3 Ollama（推荐）

向量检索（`magi index` / `magi search` 的混合模式、`magi link` 语义双链）与本地 OCR 依赖本地 Ollama：

```powershell
ollama pull qwen3-embedding:0.6b   # 向量嵌入
ollama pull glm-ocr                # 本地 OCR（可选；也可用 MinerU 云端）
```

Ollama 不可达时检索自动降级为 BM25-only，索引可事后补向量。

### 2.4 系统级外部工具（按需）

| 工具 | 用途 | 说明 |
|---|---|---|
| **Pandoc** | `magi ingest tex`（LaTeX → Markdown） | Windows 的 `pandoc-crossref.exe` 已内置于 `vendor/windows/`（加入 PATH 或在 config.yaml 的 `tools.pandoc_crossref_path` 指定） |
| **Poppler**（`pdftoppm`/`pdfimages`） | 本地 OCR 管线渲染 PDF 页面 | `scoop/choco/brew/apt install poppler` |
| **pdflatex**（可选） | 数学公式深度校验 | 缺失时自动回退 `pylatexenc` 轻量校验 |

（历史依赖 ripgrep 已不再需要。）

### 2.5 Skills 安装（教 agent 用 MAGI）

所有宿主共享仓库里同一份 `skills/*/SKILL.md`：

- **Claude Code**（推荐走 plugin，附带 SessionStart hook 自动跑 `magi sync`）：
  ```bash
  claude plugin marketplace add Misaka16384/magi
  claude plugin install magi
  ```
  skills 以 `/magi:wiki_ingest` 这样的命名空间出现；本地开发模式可 `claude plugin install <仓库目录>`。
- **Codex 及其他 Agent Plugins 1.0 宿主**：仓库根部自带 `plugin.json`，按宿主的插件安装流程指向本仓库。
- **Gemini / Antigravity**：把 `skills/` 复制（或链接）到 `<project>/.agents/skills/`。

---

## 3. 快速上手（5 分钟）

```powershell
mkdir KnowledgeHub ; cd KnowledgeHub
magi hub init                # 中央枢纽（wikis.json 注册表）
magi pm init                 # beads + 六种科研 issue 类型（会 git-init 本目录）

mkdir topics\quantum-toys ; cd topics\quantum-toys
magi init --name "Quantum Toys" --scope "玩具模型中的量子现象"
# ↑ 自动注册进 hub；生成 CLAUDE.md / AGENTS.md（agent 入场协议）、config.yaml、scratch/

magi sync                    # 同步率 + 三核状态 + 下一步提示
```

```text
MAGI SYSTEM ONLINE — sync ratio 90.0%
|- MELCHIOR  (knowledge)  0 concepts · 0 refs · graph empty-wiki · backlog 0
|- BALTHASAR (intent)     0 ready · 0 in progress · 0 blocked
`- CASPER    (retrieval)  index fresh · 0 chunks · vectors 0/0
  -> drop sources in inbox/ and run the wiki_ingest skill to start building the library
```

然后把 PDF / LaTeX / 笔记丢进 `inbox/`，在你的 agent 里说一句"摄入 inbox 里的论文"（或直接 `/magi:wiki_ingest`），流水线就开始了。

---

## 4. 研究生命周期（skills 总览）

在 agent 聊天框里以斜杠命令触发（Claude Code plugin 下带 `magi:` 前缀），或直接用自然语言描述需求：

| 阶段 | Skill | 作用 |
|---|---|---|
| 基建 | `wiki_hub_init` / `wiki_init` | 建 hub / 建主题工作区 |
| 摄入 | `wiki_ingest` | PDF/LaTeX/URL → Markdown（MinerU 云端或原生视觉转录；MinerU Token 填入工作区 `config.yaml` 的 `ocr.mineru_api_token`） |
| 摄入 | `wiki_ingest_ocr` | 完全本地离线 OCR 路线（Ollama `glm-ocr`） |
| 编译 | `wiki_compile` | raw 文献 → 文献卡片 + 概念卡片（与 bd 任务闭环：`magi pm backlog-sync` 的 `magi-compile` 标签） |
| 编译 | `wiki_enrich` | 深扫已编译文献，补挖遗漏的定理/概念 |
| 关联 | `wiki_semantic_link` | Ollama 向量语义双链 + 高相似度自动去重合并（`magi link`） |
| 规范 | `wiki_tag_sync` / `wiki_concept_sync` | 标签本体论清洗 / 同义概念物理归并 |
| 质量 | `wiki_lint` | 死链自愈、frontmatter 修复、LaTeX 校验（`magi lint --fix`） |
| 图谱 | `wiki_graph_index` | 重建 SQLite 图谱（`magi graph build` / `magi graph query`） |
| 问答 | `wiki_ask` | 混合检索 + 图遍历 + 严格引用的零幻觉问答 |
| 审查 | `wiki_audit` | 跨论文矛盾审计（claim/证据验证 + 溯源落库） |
| 综述 | `wiki_research` | 多 subagent 并行调研 → 带 provenance 的综述报告 |
| 雷达 | `radar_review` | 对 radar 摘要做 triage：评分 → bd survey issues → 标记已审 |
| 维护 | `wiki_hub_manager` | 主题归档 / 恢复（`magi hub archive/restore`） |

### 文献雷达（`magi radar`）

工作区 `config.yaml` 的 `radar:` 段配置 arXiv 分类、种子论文与我方论文后：

```powershell
magi radar harvest              # 手动收割：S2 推荐 ∪ arXiv 新文 → inbox/radar/日期-digest.md
magi radar install-schedule     # 注册每日定时收割（Windows 任务计划程序 / macOS launchd；--uninstall 卸载）
magi radar citation-gap         # 侦察"该引我方论文却未引"的近期文献（四层漏斗，人工审核队列）
```

夜间确定性收割 + 下次会话由 `radar_review` skill 做 LLM triage——`magi sync` 会提示待审摘要。

---

## 5. 从 Wikify 迁移（老用户指引）

MAGI 是 Wikify 的全面重构：脚本集升级为统一 CLI，任务状态外接 Beads，新增混合检索、claim 溯源与文献雷达。**你的数据完全兼容**——`raw/`、`wiki/`、`inbox/` 格式未变。

### 5.1 迁移步骤

```powershell
# 1. 删除旧安装拷贝（重要：旧 SKILL.md 会误导 agent 调用已不存在的脚本路径）
#    删除 ~/.claude（或项目 .claude / .agents）下由 install.ps1 复制进去的 skills/wiki_* 和 bin/

# 2. 安装新版（见上文 §2）：magi CLI + 宿主 plugin

# 3. 在每个旧的主题工作区里执行（非破坏性）：
cd <你的旧topic目录>
magi migrate
#    ↳ 补齐 CLAUDE.md / AGENTS.md / config.yaml / scratch/（沿用 config.md 里的旧标题与 scope）
#      重建 output/graph.db（新增 claims/evidence 表）与 _index.md；raw/ wiki/ 内容一字不动

# 4. 在 hub 根部启用任务状态，在各 topic 建检索索引：
magi pm init
magi index

# 5. 验收：
magi sync
```

### 5.2 变化对照

| 旧（Wikify） | 新（MAGI） |
|---|---|
| `install.ps1` / `install.sh` 复制 `skills/`+`bin/` | `uv tool install .` + 宿主 plugin（§2.5） |
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
