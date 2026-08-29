# MAGI v2 实施计划

> 配套 [`design-v2.md`](design-v2.md)（共识）；本文只讲顺序、交付物、验收。
> 完成一步：勾选此处 + 在 `ROADMAP.md` 当日条目记录。发现与 design-v2 冲突：先改 design-v2 并写明原因，再改代码。
> 约定：小步 checkpoint；commit 前缀 feat/fix/refactor/chore/docs；子 agent 用便宜模型；重大决策才停下来问人；每个里程碑结束 `tests/` 全绿 + 三宿主冒烟 + 发一个版本（beta 也发）。
> 起点：v1.16.3，1685 tests passed。**终点：v2.0.0 于 2026-08-29 commit（tag + push 留给作者）**，M0–M7 一天之内从 M4 走完，v2.0.0 commit `ac888b9`，**2379 passed / 1 skipped**（裸 runner 2355 / 22，差的是 pandoc 和 bd，CI 里都装了）。

## 总览与依赖

```
M0 地基 → M1 结构与迁移 → M2 状态与入口 → M3 命令面/skills/托管块
                                                    ↓
                        M4 审核与人环 → M5 WebUI v2 → M6 慢环与成本 → M7 发表环与发布
```

- ~~**MVP 线**：M0–M3 完成即可日常使用，发 `v2.0.0-beta`~~（作者 2026-08-29 定：不发 beta，全修好直接 v2.0.0）。
- M4 起人环真正成立；M5–M7 是完整 `v2.0.0`。M6 因对照 WikiSkill 从 4 条长到 15 条；M7 吸收了 M3 的三条欠账和三批独立复核的 31 条发现。
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
- [x] ~~`pm status` 并入 `sync`~~ 在 M3 以**删除**结案：`sync` 的 Balthasar 行已经说完了同一组数字
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
- [→ M7] `validate` 收成单 schema（跟命令面合并一起做）
- [x] 托管块内容（`core/managed.py` 的 `body()`，33 行 / 预算 40）：入口一行、目录含义各一行、五条不变量、收工一行、强制输出按档位、手册指针。理由一律不进块——块每个会话都在付费。幂等重写与 `CLAUDE.md = @AGENTS.md` 在 M1 已落地
- [x] `magi install [--host …]`：skills + 托管块 + Claude Code 的 Stop hook（跑 `magi sync --close --hook`）。settings.json 解析-合并-写回并备份，认自己的那条 hook 靠命令字符串所以重装是更新不是追加；别人写的 Stop hook 原样保留。**宿主强制力不对称照实说**：只有 Claude Code 有文档化的 Stop hook，其余宿主同一条规则只以托管块指令存在
- [→ M7] PreToolUse 计数 / SessionStart hook（说好 M6 一起做，M6 没做；2026-08-29 挪 M7）
- [x] **hub 退场**：`hub *` / `each` 全删；`hub/` 包没了，`init_workspace.py` 升到 `magi/`；llmwiki 的注册表机器（archive / restore / register / resolve_hub / wikis.json 读写）连同 `--hub`、`--include-archived` 一起删；sync 的 hub 模式、WebUI 把 hub 根当工作区都清掉。`find_hub_root` / `is_hub_root` 留着，只有一个读者——`magi migrate` 要认得旧形状才能转换
- [x] **migrate 第二半**：hub 下每个 topic 就地迁并登记进用户级 registry，**目录一个不搬**——搬目录是这次变更里唯一破坏性的一半，而有用的那一半不花钱。迁完告诉人 hub 自己的 `wikis.json` / `topics/` / `log.md` 已经不起作用，删不删由他
- [x] `log.md` 停写：lint 和 ingest 都不再往里追加，`magi init` 也不再创建。记录就是 `threads/` 里的跟帖，按时间读用 `magi feed`——同一批事件写两个地方，第一次有人只改一个就开始打架。老库里的 `log.md` 原样留着
- [x] ~~`pm status` 并入 `sync`（从 M1 挪来）~~ 与上面「`pm status` 删除」是同一件事，2026-08-29 清账
- [→ M7] README「先跑起来」改为 2 条命令；guide 对应章节更新——hub 那两章要一起重写（Operations 面板那半 M5 已做；2026-08-29 挪 M7）
- [x] 三条棘轮测试达标：`--help` 13 行（≤20）、8 个 skill 全部 ≤40 行、托管块 33 行（≤40）。xfail 标记全部摘掉——从现在起超标就是真失败，修法是拿掉东西不是抬高数字

**验收**：棘轮全绿；`magi --help` 一屏；三宿主各跑一次冒烟（install → next → compile 一篇 → --close）；现有 README/guide 与 `--help` 一致性测试通过。
**待定**：`each` 去留；plumbing 是否再压缩。

**→ ~~发 `v2.0.0-beta`~~**（2026-08-29 作者定：不发 beta，M0–M7 全部修好后直接发 `v2.0.0`；M3 的三条欠账在 M6 收尾前还清）

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

- [x] MAP 视图 + 决策队列操作：翻状态和写理由是一件事，所以是一个表单——`set_status` 在一把锁下同时写迁移和跟帖，没有理由的翻状态到不了文件。按钮来自 `vocab.allowed_targets`，只有人能做的那些带 `*`；浏览器里没有第二份转移表
- [x] feed 与 thread 视图都在 Melchior（`threads/` 就是 v2 的认知状态）。单条视图给**正文**而不是整个 `body`——`body` 是 frontmatter 以下的全部，包括讨论，照着屏幕才看出来它把讨论画了两遍（于是有了 `Note.prose`）
- [x] `magi graph build` 现在索引 `threads/`：种类是节点类型、状态是 `category`、温层和线作为标签（图本来就能按标签过滤，再造一套是同一个问题的第二个答案）。三种新配色，地图可以只看库 / 只看研究状态 / 缩到骨架（度数 top-k，丢掉断链）
- [→ 改法] `skeleton: true` 的**钉住**留到 M7：那是给人往图里加一条「这条必须留下」的手段，和「按度数缩」是两件事，M7 的骨架钉住条目本来就在管它
- [x] 堆放区文本框：原样追加，保留文件自己的换行，不重排已经在里面的东西——一个会把你另外两百行重新排版的框，是一个你不会再用的框。Ctrl/Cmd+Enter 直接提交
- [x] 配置：`research.coaching` / `wip_limit` / `stall_days` / `review_host` 进白名单，同时写进出厂 `config.yaml` 和 `magi init` 模板——WebUI 能改而配置文件只字不提，就是一个打开文件的人看不出它存在的设置
- [→ 改法] 预算与模型分配留到 M6：它们要跟 `output/llm-ledger.jsonl` 一起才有意义，一个没有账本的预算数字是一个装饰
- [x] Operations 拿到一个非危险区的挂载点，`magi install` 和收工检查落在那里——一个可以反复跑的安装被放在要输入操作 ID 确认的红框里，就是没人会重跑的安装。`magi review` 刻意不给按钮：它花真钱，而一个安静花钱的按钮会被点两次

**验收**：API 与 `--json` 契约逐字段一致（沿用现有测试风格）；`tests/test_ui_api.py` 覆盖新端点；JS 只渲染不判断（D4 判据）。

---

## M6 — 慢环与成本

- [x] `output/llm-ledger.jsonl` + 周预算门 + 总开关；超预算时 review / reflect 拒绝启动并在 MAP 说明
- [x] WebUI 配置：预算、模型分配、规则区预算 `research.rule_budget`（前两项从 M5 挪来——没有账本的预算数字是装饰）；三个键同时进 config 白名单 + 出厂 `config.yaml` + `magi init` 模板
- [x] `magi reflect` 第一段：五宿主四格式 transcript 适配器（claude / codex / gemini / qwen / opencode，qwen 未实测；golden fixture 手写不拷真实 transcript、fail-soft、Windows 路径）；抽样 ≤ 8 会话（≤ 5 loss / ≤ 3 win，各截 15k）；MAGI 结构化 loss + win → `output/reflect/patterns/*.md`（一模式一页，记会话与宿主；patch 词表 append / replace / insert_after，目标须为精确子串）
- [x] `magi reflect` 第二段：读模式页 + 提案账本 → ≤ 5 条提案，一条一个目标；≥ 2 会话、被拒不再提、90 天过期全部是对模式页 + 账本的查询，不是 prose
- [x] `output/reflect/ledger.jsonl`：CLI 在三按钮时写（目标、证据、来源宿主、裁决、日期）；被拒留全文；ACCEPT / PROMOTE 指回模式页。与 `llm-ledger.jsonl` 是两个文件。写入面（CLI / HTTP）走校验过的 workspace 解析（`_reading_root`，不是 `_resolve_workspace`），签名字段同 `format_post` 的字符集规则——M5 复核出的两条安全修复在这里同样成立
- [x] 提案进 MAP / WebUI；三按钮 ACCEPT / REJECT / PROMOTE→CODE 是人用面（`magi reflect accept|reject|promote|retire`，与 `close` / `publish` 同级）：ACCEPT 写账本，PROMOTE 写一条 `research.rules` 实例（或宿主 hook）并标 promoted；队列条目 kind = `proposal`：CLI 侧加进 `state._QUEUE_ACTION`，WebUI 侧 `renderQueue` 加按 kind 的按钮块（渲染本来就按 kind 分发，`next` 的 Action.key 即 item.kind，不用改）
- [x] 证据分路：≥ 2 宿主 → 共享层；单宿主 → 该宿主配置
- [x] 退出：模式 90 天未再现 → 它产生的规则进队列问去留；「不要了」= `magi reflect retire`（独立动词，写 RETIRED、删 `research.rules` 实例、不进 rejected 清单）；`reject` 一条已 promoted 的提案同样删实例——两者都撤规则，区别只在进不进「不再提」清单；`sync --close` 比对块与账本，漂移则阻塞并指向 `magi install`
- [x] 规则词表 `core/rules.py`：封闭词表，初始 ≤ 6 种（要求字段 / 字段须指向某目录 / 禁止某跃迁 / 每线 open 上限 / 离开某状态须某签名的帖 …），每条实例 = 谓词 + 参数 + `from:`；`lint` 与 `--close` 共用一个执行器，报错带规则来源的逐字引用；`research.rules` 进 config 白名单 + WebUI；词表装不下的提案 promote 按钮灰掉并说明。已写的 `checks/` 骨架代码与测试**删除**（2026-08-29 作者定）
- [x] 事实类提案路由到 wiki
- [x] 托管块 = 模板 + 规则区：`managed.body()` 从 `output/reflect/ledger.jsonl` 渲染 ACCEPT 且未 promoted / 未退出的规则各一行；hash 守护模板与渲染函数，不守护渲染结果；规则区 > `rule_budget` 时由 `reflect accept` 拒绝并说先退哪条，渲染从不截断；`reflect accept | promote`、退出、`sync` 都重渲染，`install --dry-run` 走同一渲染函数；棘轮测试仍只量模板的 40 行
- [x] durability：`output/reflect/patterns/` = ORIGINAL（原地改、唯一副本、原子写 + 锁），`output/reflect/ledger.jsonl` 与 `output/llm-ledger.jsonl` = TRANSACTIONAL（后者现在是 unknown）；`.gitignore` 模板不改——它本来就不整体忽略 `output/`——只把这三样加进「刻意不忽略」的注释
- [x] skill 方法类提案：目标官方 skill → 队列里标「包级」，ACCEPT 只把 diff 写进账本并在 MAP 列为开发待办，不写包；目标自有 skill → ACCEPT 打补丁到 `~/.config/magi/skills/<name>/` 并提示重装；提案必须含加 / 删两行
- [x] 官方标记与不覆盖：8 个官方 skill frontmatter 加 `origin: magi`；`skills_cmd._write` 只覆盖带标记的已有文件，替换「正文含 magi 就覆盖」；`magi install` 增 `~/.config/magi/skills/` 为第二来源，同名用户优先；测试：一个无标记的同名 fork 装两次都原样。同一处统一宿主词表：~~`antigravity` 降为 `gemini` 的别名~~（2026-08-29 作者改：反过来——Gemini CLI 废弃，`antigravity` 为正名，`gemini` 删，见 M7 第一条），三张宿主表（`skills_cmd` / `review` / `transcripts`）文件头各写明答哪个问题并互指；qwen 的 install 目标不猜。同一家族的另一处：`magi install` 刷新 `CLAUDE.md` 指针时，人写的内容先备份到 `.backup/` 再改并说在哪（`install_cmd.py:155-160` 现在直接覆盖，`migrate.py:282-305` 是备份的——两条路对同一个文件两种态度）
- [x] 隔离测试：托管块、8 个 skill、`state.candidates()` 产出的 Action.run 里 grep 不到 `output/reflect`——最后那处是唯一会把路径塞进工作 agent 眼睛的地方。派生扫描（`_LINK_DIRS`、`_iter_corpus`、`graph build`）本来就不走 `output/`，不用再加排除。夹具注意 `is_topic_root` 认的是 wiki/ raw/ threads/，只有 `output/reflect` 的目录不是工作区

**验收**：用真实 transcript 跑一轮产出 ≤ 5 条带引用的提案；模式页跨两次运行存活，第二次才过 ≥ 2 门；被拒的提案第三次运行不再出现且下一条提案能引用它；超预算时拒绝启动；托管块 hash 不变；PROMOTE→CODE 产出的测试可运行。
**待定**：ACCEPT 后规则类 prose 的落点（design-v2 §15）。
**来源**：2026-08-29 对照 WikiSkill（arXiv 2608.27454）后改，见 design-v2 §12/§17。

---

## M7 — 发表环、收尾、发布

- [x] **三批独立复核的发现全部修完**（2026-08-29 当日 31/31；明细在 ROADMAP 当日条目；最后五条 low 共用一个形状「程序说了一件没发生的事」，守在 `test_reporting_honesty.py`）：M3 切片本地 opus 14 条（`pm.main` 不解析参数致 `sync --fix` 永不收敛、skills 装进 cwd、install 默认只装 claude、CLAUDE.md 指针无备份、uninstall 无归属判断 rmtree、`ingest review --commit` 忽略 `--batch`、init 仍 spawn `hub register`…）；M4+M5 本地 opus 12 条（提示词回显被读成 `VERDICT: stands`、unclear 帖里的摘录被当答案、复核器裁决被当双翻改成 conflict、npm `.cmd` 宿主起不来、`decide --about` 换行伪造条目、config 端点未校验 workspace、浏览器可写 conflict、`dump()` 无锁无时间戳…）；M6 ultrareview 5 条（`install --coaching` 默认值绕过 None 哨兵、`already_proposed` 含 RETIRED 使退休规则回不来、WebUI 无 retire 路径…）。ultrareview M1+M2 的 2 条已在 M6 修
- [x] **Gemini CLI 全面退场**（2026-08-29 作者定）：宿主正名 `antigravity`（二进制 `agy`），`skills_cmd` 删 `gemini` 别名、help 列 antigravity；`review.py` 删 `gemini -p`，加 `agy -p --model`（考虑 `--json-schema` 直接要结构化裁决）；argv[0] 用 `shutil.which` 结果（修 npm `.cmd` 起不来）；transcripts 的 `~/.gemini/tmp` reader 确认为 agy 所写，否则改指 agy 的记录位置并改名 antigravity；guide / README / 托管块 / `degradation.md` 里 Gemini CLI 字样全改；用一次真实 `agy -p` 跑通端到端——花一次调用，先问人。**同一次做宿主注册表合一** `core/hosts.py`：三张表（`skills_cmd.HOSTS` / `review.HOSTS` / `transcripts.HOSTS`）变一张，每宿主一条声明（bin、skill 落点、无头模板、模型参数、reader 名、tier）；`research.hosts` 进 config 白名单让用户加记录；qwen / opencode 标 tier 2
- [x] **模型 / effort 选择**（2026-08-29 作者定）：注册表记录加 `list_models`（argv 模板；agy = `("{bin}","models")`，解析 `id 	 标签`）或静态 `models:` 别名表（claude：`haiku / sonnet / opus`）、`effort_flag`（agy / claude `--effort`，codex `-c model_reasoning_effort=`）、`cheap` 默认模型；`headless()` 在 `review_model` 空时传 `cheap`，effort 同理；`research.hosts[].model / .effort` 覆盖全局 `review_model / review_effort`，后两者进 config 白名单；WebUI 配置面板 host → model → effort 三级下拉，agy 的列表缓存在 `~/.config/magi/models-<host>.json`（TTL 24h，取不到退回文本框）；`magi review --dry-run` 与 `magi reflect --dry-run` 打印将用的 host / model / effort；账本已记 model，再记 effort。测试：空 `review_model` 时 argv 含 cheap；per-host 覆盖优先于全局；agy 列表解析；缓存过期与失败退回。**已做**（2026-08-29，`test_model_and_effort.py` 27 条）：codex 的 `cheap` 留空并写明理由；agy 模型 id 自带档位时不追加 effort；真实 `agy -p` 冒烟通过（故意超证据范围的命题被 refuted 并逐行点名），顺带抓到 `_REASON_RE` 600 字符硬截掉定案句的 bug——只有真调用才暴露，桩永远给短回答
- [x] （从 M3 挪来）`validate` 收成单 schema
- [x] （从 M3 挪来）PreToolUse 计数 / SessionStart hook：§13 会话内 fan-out 软约束、§7 会话开始时做后台调度
- [x] （从 M3 挪来）README「先跑起来」改为 2 条命令（`init` + `install`，之后只打 `magi`；示例真跑照抄：刚 init 的空库说的是「你还没说你想搞清楚什么」，不是「跑这五条」）；guide hub 那两章重写，并入 M7 的 guide 全书重写。顺带证实「install 会问装给哪个 CLI」是假的——它装每一个探测到的、不问，因为互不冲突；会问的是 `skills install` 且仅在多宿主 + 未点名 + tty 时
- [x] `magi close <line>`（人用面）：线归档、open 命题处置提示
- [x] `magi publish`：我方论文进 `raw/`；相关命题批量 `superseded_by`；线关闭
- [x] 骨架钉住（`skeleton: true`）与 MAP 静态渲染对齐
- [x] guide 全书按 v2 重写（explorer 陈旧性审计八簇，每条带 `src/` file:line 证据，主导模式是任务库从 hub 移到项目后迁移章 / 任务章没跟）；`docs/degradation.md` 增审核 / 无头调用 / transcript 适配行。RELEASING 检查表加两行：README / guide 里每段示例输出都是本次真跑照抄的；凡描述「X 是什么」的句子对一遍 §2 / §14——两类都是 `test_docs_in_sync` 查不到的
- [x] 三宿主冒烟（Windows，已跑一次真实 `agy -p`）+ **macOS 走 CI**（2026-08-29 作者定，没有 Mac）：新增 `.github/workflows/tests.yml`，`push` / `pull_request` 触发，矩阵 `ubuntu / macos / windows` × 一个 Python 版本跑 `pytest -q`；`release.yml` 保持 ubuntu；RELEASING.md 写明 macOS 只有 CI 绿、未冒烟。**已做**（2026-08-29）：裸 runner 模拟 2355 passed / 22 skipped，翻出 README 打包副本未同步、guide 漏 `magi hook`、guide 三处 v1 残留（含一条已修掉的「已知缺陷」说明）——都修了；`pytest -rs` 让 CI 逐条列出跳过的。CI 装 pandoc（apt / brew / choco 一行，无第三方 action）。**`bd`**：装，钉 tag（`v1.2.2`）并对 release 自带的 `checksums.txt` 做 `sha256sum -c`——这是完整性不是供应链信任（release 被替换则 checksums 一起被替换）；手抄进 workflow 的 hash 是没人会重新推导的 hash，升级时会被删掉了事，所以不用；要信任锚可在此之上加 sigstore 验签或人工核对一次写进仓库。`bd version` 冒烟一步。不 `curl | sh` 最新。`-rs` 把剩余 skip 印在页面上（端到端驱动二进制的用例换桩就是另一个测试）。**`tests.yml` 在首次 push 前未经 Actions 验证**——YAML 结构、asset 名、校验流程、解包布局都对着真实 release 验过，runner 上的 `choco install pandoc`、`$GITHUB_PATH`、Windows bash step 只有第一次 push 会告诉我们
- [ ] [可选] 第二梯队宿主（qwen / opencode / 用户自加）：只要注册表一条记录 + 可选 reader；不冒烟、fail-soft；做不成就留着记录，不阻塞发布
- [ ] **两条更强的文档同步测试**（2026-08-29 定：tag 前做，不留 v2.1——guide 审计八簇里六簇是「描述对不对」，`test_docs_in_sync` 只查「提没提」；目录树错了整整一个大版本，而它是新用户第一眼看的）：(1) guide / README 里出现的每个 `magi <cmd>` 必须在 `cli._COMMANDS` 里存在，历史语境里的退役命令（迁移章提到旧 `hub`）进显式 allowlist 并写理由——测试记录例外而不是失败；(2) 文档里「`magi init` 生成什么」那棵树必须等于 `init_workspace` 实际建的顶层集合——把脚手架跑进 tmp 目录取真集合，文档里的树放在带固定首行标记的围栏块里让解析稳定；中英 + 打包副本都验

**验收**：全测试绿（本机 Windows + CI 三平台）；smoke 三宿主（Windows）；README / guide 与 `--help` 无冲突。
**→ 发 `v2.0.0`。** 2026-08-29：版本号五处改为 2.0.0（`pyproject.toml` / `__init__.py` / 两个 `plugin.json` / `index.html` 徽章），ROADMAP 头部与 M7 条目已写；**做到 commit 为止**——`git tag v2.0.0` + `git push`（含 tag，触发 `release.yml`）是作者的仪式动作，与 `close` / `publish` 同一条原则。push 之前 `tests.yml` 未经 Actions 验证。

---

## 每个里程碑的固定收尾

1. `tests/` 全绿，把数字写进 ROADMAP 头部。
2. ROADMAP 当日条目 + 勾选本文对应项。
3. 与 design-v2 冲突：先改 design-v2（写明原因），再改代码。
4. 发版本（beta 也发）。
