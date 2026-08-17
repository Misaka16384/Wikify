# MAGI 开发路线图（动态文档）

> **本文档是活的交接文档。** 任何 agent 接手工作前必读；完成一步就更新对应条目（勾选 checkbox、追加 Status 注记）。架构定案见下方"锁定决策"，不要重新讨论已锁定项。
>
> 最后更新：2026-08-17 · 当前阶段：**M0 进行中** · 工作分支：`magi-rebuild`

## 项目一句话

**MAGI** = agent-native 科研工作环境。三态架构：Beads 管 work state（在做什么），Wikify 子系统管 epistemic state（知道什么、为何可信），自建检索层管 retrieval state（该读什么）。人是驾驶员，LLM 是机体，确定性 CLI 是拘束具，`magi sync` 输出同步率。

## 锁定决策（勿重新讨论）

| # | 决策 |
|---|---|
| D1 | 伞级 CLI 叫 `magi`；原 Wikify 降级为 KB 子系统。GitHub repo 已改名 `Misaka16384/magi` |
| D2 | CLI-first：一个 pip/uv 可安装的 Python 包（种子 = `bin/llm-wiki.py`）。SKILL.md 变薄只讲方法论，语法交给 `--help` 自描述。宿主壳（Claude Code plugin / Agent Plugins 1.0 / `.agents/skills`）只是指针，不含可执行物 |
| D3 | 检索层自建：stdlib FTS5 BM25 + sqlite-vec + Ollama embedding（复用 semantic_linker 的哈希缓存）+ RRF 融合。QMD 已否决（Windows 原生 not-planned） |
| D4 | Work state 用 Beads（`gastownhall/beads`），hub 级一个库 + topic label，单机模式。科研 issue types：question/survey/derivation/computation/experiment/review |
| D5 | `magi sync` = onboarding 命令，输出计算的同步率（索引新鲜度+bd 队列+backlog+claim 覆盖率）|
| D6 | Radar：夜间确定性 harvest（Task Scheduler/launchd）+ 会话内 LLM triage。功能 B（该引未引）是侦察兵不是法官，人工审核队列，排在 claim 层后 |
| D7 | 跨平台硬约束：Windows + macOS。`pandoc-crossref.exe` 改 PATH 查找；macOS 注意 sqlite loadable extension（需 Homebrew/uv Python）|
| D8 | 三 host 都支持且冒烟测试：Claude Code（主）、Codex、Antigravity。v1 不做 MCP；JSON 接口按未来 `magi mcp` 一比一映射设计 |
| D9 | 旧数据干净切换，一次性 `magi migrate`，不做兼容层 |
| D10 | 不做：capability IR/host compiler、AutoResearchClaw 式 control plane、自研 UI、OpenCode/dsh 适配 |

## Radar 配置（M3 用）

- 组：叶鹏教授组，中山大学物理学院。主页 https://yepengcmt.github.io/yepcmt/ （单页，71 篇论文几乎全带 arXiv ID）
- arXiv 分类：核心 `cond-mat.str-el` + `hep-th`；次级 `quant-ph` + `cond-mat.mes-hall`
- 作者监控：`au:Ye_Peng_1` + 组内高频合作者（Meng-Yuan Li, Yao Zhou, Shuai A. Chen, Jie-Yu Zhang, Zhi-Feng Zhang, Qing-Rui Wang, Yizhou Huang, Han-Xie Wang, Bo-Xi Li, Xiang-You Huang, Li-Mei Chen, Yu-Tao Hu 等）
- 种子锚点：arXiv:2606.25340, 2606.03582, 2605.13379, 2601.01523
- 数据源：S2 Recommendations（多种子）+ arXiv OAI-PMH（1req/3s）+ OpenAlex（`filter=cites:`，**API key 强制，待用户注册**）+ Crossref `query.bibliographic`（DOI 解析）+ Unpaywall（OA PDF）
- 已知事实：S2 限流数字各处矛盾，接入时实测；功能 B 学界确认误报高，必须四层漏斗（近邻−引用者 ∩ 共引信号 → LLM 论证 → bd 人审队列）

## `magi` 子命令树（M0 设计定案）

```text
magi init / hub init|resolve|list|archive|restore|register
magi sync                    # M1: 同步率 onboarding（M0 先占位）
magi migrate                 # 占位，工作区格式变更时实装
magi ingest add|assemble|mineru|tex|ocr|crop|finalize
magi wiki add-concept|refactor-concept|context|chunk|placeholders|uncompiled|reindex
magi graph build|query
magi lint [--fix]            # ← llm-wiki.py lint
magi stats <dir> <mode>      # ← llm-wiki.py stats
magi math format|check
magi validate <file> --schema
magi verify <claims-file>    # verify_claims，兼容 CLAIM:/FINDING:
magi grep                    # ← search-wiki.py（M2 后仍保留，精确正则用）
magi search / index          # M2: FTS5+sqlite-vec+RRF 混合检索
magi link [--dedup-only]     # ← skills/wiki_semantic_link/semantic_linker.py
magi tags extract|apply
magi radar ...               # M3
```

## 里程碑

### M0 — `magi` 包 + 改名 + 修复（进行中）

- [x] GitHub repo 改名 `Wikify` → `magi`，remote 更新，分支 `magi-rebuild`
- [x] ROADMAP.md 落地（本文件）
- [x] pyproject.toml + `src/magi/` 骨架 + `magi` entry point（`.venv` editable 安装验证通过）
- [x] `core/`：wiki_common、config_loader 收编；统一 workspace 发现落在 `core/workspace.py`（config_loader 和 validate_output 已接入；llmwiki 的 resolve_wiki_root 保留原逻辑，后续清理时接入）
- [x] 25 个 bin 脚本 git mv 收编（100% 相似度 rename，历史干净）；样板转换完成 4 个（verify_claims/config_loader/validate_output/llmwiki）
- [ ] 其余 ~20 模块转换（imports/main(argv)/subprocess 重写）— workflow `magi-module-conversion` 进行中
- [x] semantic_linker.py 从 skills/ 收编进包（`magi link` 注册）
- [x] **修 bug**：verify_claims 现兼容 `FINDING:`/`CLAIM:` 双格式（已实测）
- [x] pandoc-crossref.exe 移至 `vendor/windows/`；tex2md 查找顺序 env → config → PATH（转换 agent 落实）
- [ ] 15 个 SKILL.md 重写 — workflow `magi-skills-rewrite` 进行中
- [x] 宿主薄壳：`.claude-plugin/plugin.json` + `marketplace.json` + Agent Plugins 1.0 `plugin.json`
- [x] install.ps1/install.sh/requirements.txt 退役（依赖归入 pyproject）
- [ ] `.agents/`、`output/` 历史残留删除 —— **权限分类器拦截递归删除，需用户手动删**（均已 gitignore，无害）
- [ ] 冒烟测试：沙盒 workspace 走 init → lint → graph build → graph query 全链
- [ ] README 安装节更新（完整重写可推后）
- [ ] 本地文件夹改名 `gemini-wiki-skills` → `magi`（**会话结束时做**，进程占用工作目录）

### M1 — Beads + workspace 协议（✅ 完成，可实际使用）

- [x] bd 1.2.2 已装（`~/.local/bin/bd.exe`）；`magi pm init` 幂等初始化 beads + 六个科研 issue types（已实测 `bd types` 生效）
- [x] `magi sync` 实装：同步率（Melchior 0.7·graph 新鲜度+0.3·backlog；Balthasar 0.6·db 可达+0.4·status 可读；Casper 离线不计入分母）+ 三核输出 + 可执行 hints
- [x] `magi init` 生成 workspace 级 CLAUDE.md / AGENTS.md（同体，含三核说明和 ground rules）
- [x] Claude Code SessionStart hook（`hooks/hooks.json` → `magi sync`）
- [x] 6 个生成型 skills 插入 "Task Tracking (Beads)" 节；wiki_init/wiki_hub_init 增加 `magi pm init` 步骤
- [x] `magi pm backlog-sync`：uncompiled 源 → bd issues（label `magi-compile`，幂等）
- 备注：`bd ready --json` / `bd status --json` 为 sync 的数据源；beads 库开在 hub 级（决策 D4）

### M2 — 检索层（✅ 代码完成，macOS 冒烟待做）

- [x] `magi index`：标题分块（≤250 行）+ sha1 增量 + FTS5（触发器同步）+ sqlite-vec（Ollama 不可达时优雅降级 BM25-only，向量事后可补）
- [x] `magi search --json`：BM25 + 向量 + RRF(k=60)；collections = concepts/references/topics/theses/raw；`--mode hybrid|bm25|vector`
- [x] Casper 核接入 `magi sync` 同步率（0.7·索引新鲜度 + 0.3·向量覆盖率；索引缺失记 0 分）
- [x] wiki_ask（Strategy 0）/ wiki_audit / wiki_research 接入 `magi search` + "必须读原文再引用"规则
- [x] 已在 Windows 实测：sqlite-vec 0.1.9 wheel + FTS5 + qwen3-embedding:0.6b（1024 维）真实向量命中验证
- [x] 修复：`find_beads_root` 误把 bd 用户级 `~/.beads` 数据目录当 workspace 库（改查 metadata.json marker）
- [ ] macOS 冒烟（sqlite extension 加载验证）— 需在 mac 机器上跑 `tests/smoke_test.py`
- 发现：本机已有 `dengcao/Qwen3-Reranker-0.6B` Ollama 模型，将来给 search 加重排是现成弹药

### M3 — Radar 功能 A（✅ 完成）

- [x] fingerprint：config 种子 + wiki/references 里的 arXiv ID 自动并入（≤50 seeds）；DOI/Crossref 解析推迟到功能 B 需要时
- [x] `magi radar harvest`：S2 Recommendations（多种子，留一半配额）∪ arXiv 新文（1req/3s 礼貌限速，7 天窗口）→ `output/radar/seen.jsonl` 累积台账去重 → `candidates.jsonl` + `inbox/radar/日期-digest.md`（已用组内真种子实测：40 条高度对口的 2026 候选）
- [x] `magi radar status [--json]`；pending digest 提示接入 `magi sync`
- [x] `magi radar install-schedule`：Windows schtasks 已做创建→查询→删除往返验证；macOS launchd plist 生成（待 mac 实测）
- [x] `radar_review` skill：读 digest → `magi search` 对照 wiki 评分 → read-now/relevant/skip 三分类 → bd survey issues（防重复）→ digest 标记 reviewed
- [x] config.yaml `radar:` 段（组内四分类 + 四篇 2026 种子已填）；`magi init` 生成 workspace 级起始 config.yaml
- 备注：OpenAlex 引用扩展留待功能 B（需要用户注册的 API key）；S2 未用 key，量级内免费额度够用

### M4 — Claim/Provenance 层

- [ ] verify_claims v2：JSON 输出、空白归一化模糊匹配、web source 真实抓取
- [ ] graph.db 增 claims/evidence 表 + 新 edge types + claim markdown 落地约定
- [ ] wiki_research / wiki_audit 产出落库

### M5 — Radar 功能 B（依赖 M4）

- [ ] 四层漏斗实现 + bd citation-check 人审队列

## 交接须知（给接手的 agent）

- 原始代码盘点结论：检索现状是纯 regex grep（无向量）；graph.db schema 在 `llm-wiki.py:2468-2493`（nodes/edges/tags/aliases，全量重建式）；embedding 只在 semantic_linker（Ollama + 独立缓存 db）。
- 提交规范：小步 checkpoint，`git commit` 带清晰前缀（feat/fix/refactor/chore/docs）。
- 环境：Windows 11 + Python 3.10.11 + uv 0.11.2；Ollama 本地服务（qwen3-embedding:0.6b, glm-ocr）。
- 用户要求：重大决策才停下来问；其余持续推进。
