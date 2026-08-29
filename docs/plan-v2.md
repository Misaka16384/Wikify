# MAGI v2 实施计划

> 配套 [`design-v2.md`](design-v2.md)（共识）；本文只讲顺序、交付物、验收。
> 完成一步：勾选此处 + 在 `ROADMAP.md` 当日条目记录。发现与 design-v2 冲突：先改 design-v2 并写明原因，再改代码。
> 约定：小步 checkpoint；commit 前缀 feat/fix/refactor/chore/docs；子 agent 用便宜模型；重大决策才停下来问人；每个里程碑结束 `tests/` 全绿 + 三宿主冒烟 + 发一个版本（beta 也发）。
> 起点：v1.16.3，1685 tests passed。

## 总览与依赖

```
M0 地基 → M1 结构与迁移 → M2 状态与入口 → M3 命令面/skills/托管块
                                                    ↓
                        M4 审核与人环 → M5 WebUI v2 → M6 慢环与成本 → M7 发表环与发布
```

- **MVP 线**：M0–M3 完成即可日常使用，发 `v2.0.0-beta`。
- M4 起人环真正成立；M5–M7 是完整 `v2.0.0`。
- M5 可与 M4 并行（不同文件）；M6 依赖 M4 的决策队列。

---

## M0 — 地基：规约、棘轮、threads 解析

**目标**：把共识变成可执行的规约和测试，不动现有功能。

- [x] `docs/design-v2.md` 入库
- [x] `core/vocab.py`：kind / status / key_move / coaching 词表冻结；状态跃迁表（合法转移 + 谁能写）
- [x] `threads/` frontmatter schema（公共字段 + 各 kind 字段）；解析与序列化
- [x] 跟帖格式与原子 append 原语（Windows/macOS 均原子）
- [x] `magi lint` 新增 threads 校验：schema、非法跃迁、一文件一温度、跃迁无跟帖
- [x] 派生函数：`tier_of(note)`（温度）、冷层背书率（evidence 必须指向 raw）
- [x] durability 把 `threads/`、`drafts/`、`decisions.md` 记为 ORIGINAL（格式定义在哪，持久性归类就在哪；否则 classify 对它答 unknown）
- [x] 三条棘轮测试（允许先失败，M3 达标）：porcelain `--help` ≤ 20 行；每个 SKILL.md ≤ 40 行；托管块 ≤ 40 行

**验收**：新测试全绿；现有 1685 不退化；一个示例 project 的 `threads/` 能 lint 通过并算出温度。
**已定**：`construction` kind 暂不预留——多一个 kind 就要多一张状态表、一组跃迁和一组测试，而「存在……的构造」写成存在性命题目前不别扭；真别扭时按 design-v2 §4 补。

---

## M1 — project / line 结构与 `magi migrate` v2

**目标**：新目录布局落地，旧 topic 无损迁移，hub 退场。

- [x] `magi init` 生成 v2 布局（`threads/`、`drafts/`、`inbox/notes.md`、`decisions.md`、AGENTS.md 托管块 + `CLAUDE.md = @AGENTS.md`）；`wiki/theses/` 不再创建也不再必需（老库里有就照常索引）
- [x] ~~`init` 吸收 `pm init`~~ **改为不吸收**：实测 `bd init` 要 2.5 秒，而且会自己写 `AGENTS.md` / `CLAUDE.md` / `.claude/` / `.codex/`——跟托管块正面冲突，还会给每个测试工作区加 2.5 秒（全套 ~30 处，等于把测试时间加一半）。合并的目的是「人少记一条命令」，而这个目的由 M3 的 porcelain/plumbing 拆分完全达成：`pm init` 降为 plumbing，`magi sync` 该提示时会提示，人本来就不用打它
- [x] note 创建改为 `magi thread new --kind line|proposition|question`，不单开 `line new`——三种 kind 一个 schema，命令面也该是一个。另加 `thread post` / `thread status`（后者把改状态和写跟帖绑成一次调用），否则 M0 那把锁形同虚设：agent 会用编辑器直接改文件
- [x] durability：`output/MAP.md`、`output/.locks/` = DERIVED（ORIGINAL 那半已在 M0 落地）
- [x] 检索：collection 增 `threads`（`drafts` 早就有）；threads 在未指定 collection 时降权 0.6；`threads/` **不进** `CORPUS_DIRS`——那个元组喂的是会重写文件的维护流程，帖子不能被重排
- [x] 线内 `focus` 从 wikilink 派生并加权：`magi search --line X` 把该线的 note 一跳内引用到的文件加权 1.5——是加权不是过滤，因为线内提问的答案常常在这条线从没引过的论文里
- [x] beads 迁到项目根（`pm init` 不再往上找 hub）；新增 `line:` 标签与 `--line` 过滤，`topic:` 保留以便读旧的 hub 库；任务行多一个 `line` 字段
- [ ] `pm status` 并入 `sync`（挪到 M3 的命令面收缩一起做，那里才决定哪些命令消失）
- [→ M3] hub 退场**挪到 M3**：`test_docs_in_sync` 会拦下「文档里写了已经不存在的命令」，所以删 `hub *` 就必须同时重写 guide 的「先跑通一遍」「建立文献库」两章和两个 README——而 M3 本来就要把 README 改成 2 条命令、把 guide 对应章节更新。分两次写等于同一批文档改两遍。跨项目检索的替代物早就在了（registry + `retrieval.run_search` 的联邦检索），所以推迟不阻塞任何东西
- [x] `magi migrate` v2 第一半：`wiki/theses/*` → `drafts/`（重名就原地不动并报出来，不猜）；`CLAUDE.md` 收成 `@AGENTS.md`（人写过的内容进 `.backup/` 并告诉他在哪）；重跑零改动有测试守着
- [→ M3] `magi migrate` v2 第二半：`hub/topics/*` → 多个 project（跟 hub 退场一起）；`log.md` 停写保留
- [x] 根发现：该用项目根的调用方都已经在用 `find_workspace_root`（`pm` 这次改掉了最后一个偏好 hub 的；`skills_cmd` 早就是「项目优先、hub 兜底」）。剩下的 `find_hub_root` 调用点全部属于 hub 功能本身，跟着 hub 一起在 M3 退场

**验收**：迁移后 `magi sync` 三核全绿；旧 `raw/`、`wiki/` 字节不变；跨项目 `search` 有 `[kb:]` 标记；重跑 migrate 零改动（有测试）。
**待定**：多个 topic 合并为一个 project 是否提供交互选择（默认不合并）——跟 hub 退场一起在 M3 定。

---

## M2 — 状态与入口：`next`、`--close`、硬触发、MAP、feed

**目标**：快环成立——文件变 → 派生变 → `next` 变 → 执行 → 文件变。

- [x] `magi next`（裸 `magi` 等价）：派生 → 候选清单（`--json` + 人读）；项目级 / 线级投影；安静阈值；记账债为第一条；只提议不执行
- [x] `magi sync --close`：本会话改动扫描（git diff / mtime）→ 缺 status / 跟帖 / line STATUS 则失败并列出；Claude Code Stop hook 脚本（阻止停机并回传原因）
- [x] 硬触发：跃迁检测 → 决策队列条目（MAP + bd review issue）；`conflict` 检测（5 分钟双翻）
- [x] **跃迁权限的强制**：`vocab.writers()` 在 M0 只是政策——帖子签名写的是宿主不是"谁的决定"，而 AI 誊写人的决定是常态。`--close` 校验：离开 `disputed` / `conflict` / `closed` 必须有对应的 `decisions.md` 条目或人的跟帖，否则拦下
- [x] `output/MAP.md` 渲染（两节：各线 + 决策队列）
- [x] `magi feed`（`--since / --line / --author`）；帖子进索引
- [x] WIP 上限提示（默认 7）
- [x] `sync` 三核显示按 §14 重映射

**验收**：示例 project 走完"开命题 → testing → supported"后 MAP 出现队列条目；未记账停机被 Stop hook 拦下（Claude Code）；`feed` 能检索到帖子；无变化时 `next` 只报开放问题；agent 擅自把 `disputed` 翻回 `supported` 被 `--close` 拦下。
**已定**：决策队列**不写 bd**。队列是派生的，会随 note 变；bd issue 是存下来的副本，note 一动就要有人去关它——正是「第二个答案会跟第一个打架」那个问题。beads 只放机械活，等人拍板的事不是机械活。队列住在 MAP 和 `magi next` 里。

---

## M3 — 命令面收缩、skills 精简、托管块、install

**目标**：人上手 = 2 条命令；AI 入口 = 托管块 + `next`。

- [x] porcelain / plumbing 分离：`magi --help` 只列 7 条（next / init / install / ui / search / feed / guide），**13 行**；`--help --all` 仍列全部 71 条。隐藏不是删除，有测试守着
- [ ] 合并落地：`sync --fix` 吸收 graph build / index / wiki reindex / lint --fix / ingest finalize / pm backlog-sync；`ingest` → auto / review / url（rung 变 `--via`）；`lint` 吸收 verify / claims verify / validate / math check；`install` 吸收 setup / skills *；`radar` → radar / radar schedule
- [x] 20 → 8 skills（`magi` / `ingest` / `compile` / `tidy` / `ask` / `research` / `draft` / `radar_review`），每个 ≤ 40 行；样板（工具能力、谁能问人、无人值守）移入托管块；纯包装的七个删掉（建库、修复、建图、连边、查手册本来就是一条确定性命令）。顺带删掉 `wiki_lint` 带的 700 个 fixture 文件——没有任何测试在跑它们
- [x] `research` 吸收 `audit`：找茬只是换一套子 agent 提示词，产物统一为 threads 命题 + 至多一篇 `wiki/topics` synthesis
- [ ] `validate` 收成单 schema（跟命令面合并一起做）
- [x] 托管块内容（`core/managed.py` 的 `body()`，33 行 / 预算 40）：入口一行、目录含义各一行、五条不变量、收工一行、强制输出按档位、手册指针。理由一律不进块——块每个会话都在付费。幂等重写与 `CLAUDE.md = @AGENTS.md` 在 M1 已落地
- [x] `magi install [--host …]`：skills + 托管块 + Claude Code 的 Stop hook（跑 `magi sync --close --hook`）。settings.json 解析-合并-写回并备份，认自己的那条 hook 靠命令字符串所以重装是更新不是追加；别人写的 Stop hook 原样保留。**宿主强制力不对称照实说**：只有 Claude Code 有文档化的 Stop hook，其余宿主同一条规则只以托管块指令存在
- [ ] PreToolUse 计数 / SessionStart hook（成本治理那半在 M6 一起做）
- [ ] **hub 退场**（从 M1 挪来）：删 `hub *` / `each`；`hub/init_workspace.py` 移出 `hub/` 包；sync / ui / llmwiki 的 hub 分支清掉；`find_hub_root` 只留给 migrate 认旧库
- [ ] **migrate 第二半**（从 M1 挪来）：`hub/topics/*` → 多个 project（就地迁 + 注册进 registry，不搬目录）；`log.md` 停写保留
- [ ] `pm status` 并入 `sync`（从 M1 挪来）
- [ ] README「先跑起来」改为 2 条命令；guide 对应章节更新；WebUI Operations 面板对齐新 plumbing——hub 那两章要一起重写，这是把 hub 退场挪到本里程碑的原因
- [x] 三条棘轮测试达标：`--help` 13 行（≤20）、8 个 skill 全部 ≤40 行、托管块 33 行（≤40）。xfail 标记全部摘掉——从现在起超标就是真失败，修法是拿掉东西不是抬高数字

**验收**：棘轮全绿；`magi --help` 一屏；三宿主各跑一次冒烟（install → next → compile 一篇 → --close）；现有 README/guide 与 `--help` 一致性测试通过。
**待定**：`each` 去留；plumbing 是否再压缩。

**→ 发 `v2.0.0-beta`。**

---

## M4 — 审核与人环

**目标**：人只在三类事件被叫，且被叫时必须写字。

- [ ] `magi review`：四宿主无头适配器（`claude -p` / `codex exec` / `gemini -p` / `qwen -p`）；固定提示词；只给读 + 冷层检索；便宜模型
- [ ] 跨厂商默认（PATH 探测，选异宿主）；同宿主回退；config 可指定
- [ ] 批量触发于 `--close`；裁决跟帖写回；`disputed` 进决策队列
- [ ] 强制输出协议进托管块（`coaching: off | light | strict`）；strict 档 Claude Code hook 验证"无 bet 不推导"
- [ ] `magi post`（plumbing）供 AI 誊写预测 / 决定；`decisions.md` 条目格式；命题 `bet:` 字段
- [ ] 堆放区分类：`next` 第一步；五写入面路由；拿不准 → question；原文留链接
- [ ] MAP 回溯：预测命中率、旧决定对账行

**验收**：一个 supported 命题被另一宿主驳回后出现在 MAP 队列且状态为 disputed；strict 档位下无 bet 不开始推导；堆放区三条杂项被分到三处并留链接；`decisions.md` 由 AI 誊写、人未开过文件。
**待定**：审核提示词的证据边界细则；bet 记分规则最小版。

---

## M5 — WebUI v2（可与 M4 并行）

- [ ] MAP 视图 + 决策队列操作（accept / reject / 翻状态需跟帖）
- [ ] feed tab；thread 视图（论坛渲染）
- [ ] 一张图：按 kind / status / 温度着色，按 line / kind / 层过滤，骨架缩放（度数 top-k / `skeleton: true`）
- [ ] 堆放区文本框（写 `inbox/notes.md`）
- [ ] 配置：预算、模型分配、coaching 档位、审核宿主
- [ ] Operations 面板对齐新 plumbing

**验收**：API 与 `--json` 契约逐字段一致（沿用现有测试风格）；`tests/test_ui_api.py` 覆盖新端点；JS 只渲染不判断（D4 判据）。

---

## M6 — 慢环与成本

- [ ] `output/llm-ledger.jsonl` + 周预算门 + 总开关；超预算时 review / reflect 拒绝启动并在 MAP 说明
- [ ] `magi reflect`：四宿主 transcript 适配器（golden fixture、fail-soft、Windows 路径）；MAGI 结构化 loss；gap 账本；≥ 2 会话；≤ 5 / 周；逐字引用；拒绝记忆；90 天过期
- [ ] 提案进 MAP / WebUI；三按钮 ACCEPT / REJECT / PROMOTE→CODE（生成 hook / 测试骨架并删 prose）
- [ ] 事实类提案路由到 wiki；托管块 hash 守护（永不改）

**验收**：用真实 transcript 跑一轮产出 ≤ 5 条带引用的提案；超预算时拒绝启动；托管块 hash 不变；PROMOTE→CODE 产出的测试可运行。

---

## M7 — 发表环、收尾、发布

- [ ] `magi close <line>`（人用面）：线归档、open 命题处置提示
- [ ] `magi publish`：我方论文进 `raw/`；相关命题批量 `superseded_by`；线关闭
- [ ] 骨架钉住（`skeleton: true`）与 MAP 静态渲染对齐
- [ ] guide 全书按 v2 重写；`docs/degradation.md` 增审核 / 无头调用 / transcript 适配行
- [ ] 三宿主 + 双平台冒烟；`RELEASING.md` 流程

**验收**：全测试绿；smoke 三宿主；README / guide 与 `--help` 无冲突。
**→ 发 `v2.0.0`。**

---

## 每个里程碑的固定收尾

1. `tests/` 全绿，把数字写进 ROADMAP 头部。
2. ROADMAP 当日条目 + 勾选本文对应项。
3. 与 design-v2 冲突：先改 design-v2（写明原因），再改代码。
4. 发版本（beta 也发）。
