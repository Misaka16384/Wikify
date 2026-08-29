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
- [x] `ingest` → auto / **review** / url：`batch-list` + `batch-decide` + `batch-commit` 合成一条 `magi ingest review`（裸跑＝列出待审，`--item/--decision`＝判一条，`--commit`＝落盘）。这三步本来就是一件事，拆成三条命令让中间那步像是另一个工具
- [x] `pm status` 删除：`magi sync` 的 Balthasar 行已经把 ready / in progress / blocked 说完了，同一个数字两个地方读是让它们开始打架的第一步
- [x] `sync --fix` 吸收确定性修复：`FIXABLE` 早就把 graph build / index / backlog-sync / pm init 挂在对应 hint 上，porcelain 拆分之后那些命令本来就不在人看的那一屏里
- [→ 不做] `lint` 吸收 `verify`：`verify --fetch-web` 会发网络请求，而 lint 必须离线且快——一个跑不动的 lint 就是没人跑的 lint。两条命令回答的是不同代价的问题
- [→ 不做] `lint` 吸收 `validate` / `math check`：作用域不同（一篇文档 vs 整个工作区）。合了以后 `lint` 得长出参数来说明你指的是哪一种，那正是合并想消除的东西
- [→ 不做] `radar` 收成 radar / radar schedule：porcelain 拆分之后 radar 整组都是 plumbing，人看不见；改名只会打断 `radar_review` skill 和 WebUI 的 ops 面板，换不到任何人能看见的收益
- [→ 不做] `install` 吸收 `setup`：`install` 已经在调 `skills install`；而 `setup` 是环境体检（装 bd、拉模型、查插件），跟「把工作区装进宿主」不是一件事，合并会让一条命令同时改工作区和机器
- [x] 20 → 8 skills（`magi` / `ingest` / `compile` / `tidy` / `ask` / `research` / `draft` / `radar_review`），每个 ≤ 40 行；样板（工具能力、谁能问人、无人值守）移入托管块；纯包装的七个删掉（建库、修复、建图、连边、查手册本来就是一条确定性命令）。顺带删掉 `wiki_lint` 带的 700 个 fixture 文件——没有任何测试在跑它们
- [x] `research` 吸收 `audit`：找茬只是换一套子 agent 提示词，产物统一为 threads 命题 + 至多一篇 `wiki/topics` synthesis
- [ ] `validate` 收成单 schema（跟命令面合并一起做）
- [x] 托管块内容（`core/managed.py` 的 `body()`，33 行 / 预算 40）：入口一行、目录含义各一行、五条不变量、收工一行、强制输出按档位、手册指针。理由一律不进块——块每个会话都在付费。幂等重写与 `CLAUDE.md = @AGENTS.md` 在 M1 已落地
- [x] `magi install [--host …]`：skills + 托管块 + Claude Code 的 Stop hook（跑 `magi sync --close --hook`）。settings.json 解析-合并-写回并备份，认自己的那条 hook 靠命令字符串所以重装是更新不是追加；别人写的 Stop hook 原样保留。**宿主强制力不对称照实说**：只有 Claude Code 有文档化的 Stop hook，其余宿主同一条规则只以托管块指令存在
- [ ] PreToolUse 计数 / SessionStart hook（成本治理那半在 M6 一起做）
- [x] **hub 退场**：`hub *` / `each` 全删；`hub/` 包没了，`init_workspace.py` 升到 `magi/`；llmwiki 的注册表机器（archive / restore / register / resolve_hub / wikis.json 读写）连同 `--hub`、`--include-archived` 一起删；sync 的 hub 模式、WebUI 把 hub 根当工作区都清掉。`find_hub_root` / `is_hub_root` 留着，只有一个读者——`magi migrate` 要认得旧形状才能转换
- [x] **migrate 第二半**：hub 下每个 topic 就地迁并登记进用户级 registry，**目录一个不搬**——搬目录是这次变更里唯一破坏性的一半，而有用的那一半不花钱。迁完告诉人 hub 自己的 `wikis.json` / `topics/` / `log.md` 已经不起作用，删不删由他
- [x] `log.md` 停写：lint 和 ingest 都不再往里追加，`magi init` 也不再创建。记录就是 `threads/` 里的跟帖，按时间读用 `magi feed`——同一批事件写两个地方，第一次有人只改一个就开始打架。老库里的 `log.md` 原样留着
- [ ] `pm status` 并入 `sync`（从 M1 挪来）
- [ ] README「先跑起来」改为 2 条命令；guide 对应章节更新；WebUI Operations 面板对齐新 plumbing——hub 那两章要一起重写，这是把 hub 退场挪到本里程碑的原因
- [x] 三条棘轮测试达标：`--help` 13 行（≤20）、8 个 skill 全部 ≤40 行、托管块 33 行（≤40）。xfail 标记全部摘掉——从现在起超标就是真失败，修法是拿掉东西不是抬高数字

**验收**：棘轮全绿；`magi --help` 一屏；三宿主各跑一次冒烟（install → next → compile 一篇 → --close）；现有 README/guide 与 `--help` 一致性测试通过。
**待定**：`each` 去留；plumbing 是否再压缩。

**→ 发 `v2.0.0-beta`。**

---

## M4 — 审核与人环

**目标**：人只在三类事件被叫，且被叫时必须写字。

- [x] `magi review`：四宿主无头适配器（`claude -p` / `codex exec` / `gemini -p` / `qwen -p`，都是各家文档化的非交互模式，不猜内部参数）；固定提示词；只看命题 + `derivation:` + 它引的 `raw/`，不看对话也不看线的自我叙述；`--model` 不给就不传，免得在本来能跑的宿主上冒出 unknown model
- [x] 跨厂商默认（PATH 探测选一个不是作者的）；同宿主回退（干净会话仍有价值，结论里写明是哪种）；一个都没装时**什么也不算通过**——宁可留着没复核
- [x] 裁决以跟帖写回；驳回打到 `disputed` 进决策队列，不是 `refuted`（那会是结论），也不会下次运行自己翻回去
- [→ 改法] `--close` **只列出不执行**：一次无头调用是几分钟延迟加真金白银，放进 stop hook 里，而在 M6 的预算闸门之前两样都没有护栏。列出来照样闭环——`magi next` 会提议它，还在干活的 agent 会去跑；而一个要等五分钟的 stop hook 是会被卸掉的 stop hook
- [x] 强制输出协议进托管块（`coaching: off | light | strict`，M3 落地）
- [→ 改法] strict 档不用 `PreToolUse` hook：hook 看到的是一次工具调用，不知道这次调用是关于哪条命题的，只能全拦或全放。真能分辨的是读 note 的那道闸门——所以 strict 档把「在 testing 却没有 bet」记成欠账，拦的是收工而不是下一次读文件。「不知道」照样算数
- [x] `magi decide`（比 `post` 更说得清，且 `thread post` 已经占了那个名字）：agent 把人刚说的话**原样**誊写——同时写 `decisions.md`、给命题打 `bet:`、在讨论区留一条署名 `human` 的帖。摘要会让记录变成 agent 对人话的转述，而记录本来就该独立于那个
- [x] 堆放区分类：`next` 的**第一条**（人的话排在机器记账后面，是关于谁的时间更稀缺的错误信号）；五个写入面；拿不准开成 question；原文引进产物里，然后把那行删掉——剩下的就正好是还没分类的
- [x] MAP 回溯：命中率 + 最近的决定，不等人去翻——一个人永远看不到的命中率训练不了任何东西。`unknown` 不计分：它是诚实的先验，把它算成猜错会教人去猜
- [x] **没跑成的复核什么都不写**（复核轮加的）：一条 reviewer 的帖会让命题永远退出复核队列，
  所以只有真的读过才写。`unclear` 照写帖子（原文附在里面）但不算答案，命题回队列；`--host`
  过安装探测——指定一个没装的宿主是报错，不是逐条通过
- [x] **誊写不会被格式吃掉**（复核轮加的）：人说的话里长得像 `status:` / 帖子签名 / `## ` 的
  部分用围栏引起来。被吃掉会变成一条**签着说话人名字**的状态迁移，伪造签名比丢一行更糟
- [x] **事后补的 bet 不计分**（复核轮加的）：设字段在讨论区留痕（`set: bet = …`），所以
  「事先还是事后」从文件本身就能看出来。赛前才叫下注
- [x] **strict 写进 `config.yaml`**（复核轮加的）：以前它只进了给 agent 看的协议文本，闸门
  读的是 config——"告诉 agent 严格、闸门按宽松算"正是它出厂的样子

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
