# MAGI v2 设计共识

> **状态**：2026-08-28 与作者对齐并锁定。v2 是破坏性变更（一次性 `magi migrate`）。
> 本文只记共识，不记进度；实施顺序见 [`plan-v2.md`](plan-v2.md)，日常记录仍在 [`ROADMAP.md`](../ROADMAP.md)。
> 与 v1「锁定决策」冲突处以本文为准；本文未涉及处 v1 决策仍有效。
> 实现中发现与本文冲突：**先改本文并写明原因，再改代码。**

## 0. 一句话

MAGI v2 = 人指挥、AI 执行、产物人机共读的科研工作环境。约束条件是**人的认知带宽远小于 AI 的产出速度**。设计目标：人只接触（a）课题整体状态、（b）只有人能做的决定；其余一律不出现在人面前。

## 1. 设计原则（优先级从高到低，冲突时按此裁决）

1. **越少越简洁越好。** 多一个目录、字段、命令、skill 都要付出理由。
2. **记账靠近，评判远离。** 状态由离它最近的主体写下；质量由不共享上下文的主体评判。
3. **派生不存储。** 能从文件算出来的不落盘为真相；派生函数只负责发现"谁没记账"。
4. **确定性 CLI 是拘束具。** 能写成命令/门/测试的规则不写成 prose；prose 规则是硬化候选。检查的**例外按形式或位置划范围，不按词划**（M7 收尾时定）：按词豁免的 allowlist 看起来在查，实际把最该查的那处豁免掉；写完的测试自己是绿的，只有「把 bug 放回去跑一遍」才知道它有没有睡着。
5. **人的输入面只有一个（对话）。** 人被要求写字的时刻 = 人必须读的时刻，是同一组事件。
6. **仪式性动作留给人。** 关线、发表只有人调用，AI 永不调用。
7. **硬约束**：Windows 冒烟 + macOS **CI 跑 pytest**（2026-08-29 作者定：手边没有 Mac；v2 自 M0 起没在 Mac 上冒烟过，CI 矩阵是唯一能给的保证，RELEASING 如实写「macOS 未冒烟」）；Claude Code / Codex / Antigravity 三宿主冒烟。Gemini CLI 已废弃，不再是宿主；其余宿主（Qwen Code、opencode、用户自加的）是**第二梯队**：best-effort、fail-soft、不进冒烟（2026-08-29 作者定）。

## 2. 结构：project / line

- **project** = 一个知识库 = 一个目录。承载冷层和温·共享层。`AGENTS.md` 托管块、`config.yaml`、`decisions.md`、beads 都在项目根。
- **line**（研究线）= 共享 KB 上的一个视图 + 自己的热层，**不是独立 KB**。用 `threads/` 里一个 `kind: line` 的 note 表示；命题、问题、草稿用 `line:` 字段（可多值）指向它。
- 一个模糊大方向开一个 project，下面几条 line。线可以零条起步（隐式一条），子方向清晰后再开。开/合/并线 = 改字段，知识一字不动。
- **hub 退场。** 跨 project 检索走用户级 registry（`~/.config/magi/registry.json`，已有）。beads 从 hub 搬到 project 根，label = line，**只管机械任务**（编译积压、review 队列、radar 待审）；研究状态不进 beads。
- 现有 topic 工作区 = 没有 line 的 project；`magi migrate` 一次性转换，`raw/`、`wiki/` 字节不变。

```
<project>/
  AGENTS.md            托管块 + 用户自定义          CLAUDE.md 只含 "@AGENTS.md"
  config.yaml
  decisions.md         只有人写（AI 誊写）
  raw/                 冷：唯一真相（papers/articles/notes/data/repos）
  wiki/references/     冷的派生视图：只能从 raw 重编译，不手改
  wiki/concepts/       温·共享：概念卡，永远共享，不分线
  wiki/topics/         温·共享：综述（research skill 的唯一长文产物）
  drafts/              温·线内：草稿、推导（line:、supports: 字段）
  threads/             命题 / 问题 / 线（论坛式跟帖）
  inbox/               待摄入论文 + notes.md（人的堆放区）
  output/              派生物与账本：graph.db index.db MAP.md ingest 账本 llm-ledger.jsonl
  scratch/             废纸篓
```

退役：`wiki/theses/`（含义并入 `drafts/` 与 `threads/`）、`journal/`（不存在，见 §5）、`log.md`（停止写入，迁移时保留原文件）、hub 目录层。

## 3. 温度模型

| 层 | 位置 | 可变性 | 谁写 |
|---|---|---|---|
| 冷 | `raw/` | 不可改 | 摄入管线 |
| 冷·派生 | `wiki/references/` | 只重编译 | compile skill |
| 温·共享 | `wiki/concepts/`、`wiki/topics/` | 可改；改**定义**要标 `definition_changed: <date>`（追加不标） | AI，人偶尔 |
| 温·线内 | `drafts/`；`threads/` 中 `supported` 的命题 | 可改 | AI |
| 热 | `threads/` 中 `open / conjectured / testing` | 高频 | AI |

- 温度是**文件级**性质。目录决定冷与温·共享；`threads/` 内温度由 `kind + status` **派生**，文件不移动。
- 上表只列了典型状态；**全表**（M0 实现时补全，原文未覆盖）：`threads/` 里结案态算温·线内（命题 `supported / refuted / superseded`、问题 `answered / abandoned`、线 `dormant / closed`），其余包括 `disputed` 与 `conflict` 算热。`inbox/`、`scratch/` 算热；`output/` 无温度（派生物）。读不到 status 时按**热**处理——热承诺最少，不会让下游把没定的东西当已定。
- **一文件一温度**（lint 规则）：概念卡里冒出的猜想拆成 `threads/` 命题，原地留 wikilink。
- claim 的证据（`evidence.source`）必须指向 `raw/`，不能指向 reference 卡（卡可能错）。**冷层背书率** = 一个温文件中 evidence 指向 raw 且 verified 的 claim 比例；派生指标，不存。

## 4. 对象模型（`threads/`）

一个目录、一个 schema。公共字段：`kind`、`status`、`line`（列表）、`created`、`purpose`（一句，创建者写）。**slug 即 ID，创建后不改**；文件可搬，`lint --fix` 修链接。

| kind | 含义 | status |
|---|---|---|
| `proposition` | 有真值的命题；研究的基本单元 | `open → conjectured → testing → supported \| refuted → superseded`；旁路 `disputed`（审核驳回 / 证据冲突）、`conflict`（多写者双翻） |
| `question` | 开放式问题，无真值；子节点是命题 | `open → answered \| abandoned` |
| `line` | 研究线；body 即 STATUS（到哪了、卡点、下一步、交接话） | `exploring → active → writing → dormant → closed`；相位由项目级 `next` 提示、人确认；`closed` 只有人写 |

命题附加字段：`depends_on: [[概念]]`、`answers: [[question]]`、`bet:`（人的预测：`supported | refuted | unknown`）、`derivation: [[drafts/…]]`、`superseded_by:`；结案时 `key_move: new-method | known-method-new-setting | reduction-to-known | brute-force | lucky-observation`（词表由人维护）。**结果卡不是独立对象**，是命题结案时写入的一节。

非命题式研究单元的归属：

| 单元 | 归属 |
|---|---|
| 猜想、定理、对偶、"模型 A 实现相 B" | proposition |
| 计算、分类、刻画（"X 的序参量是什么"） | question，答案是命题 |
| 构造（"造一个有性质 P 的模型"） | 存在性命题；模型本身进概念卡 |
| 方法 | 概念卡（方法卡）；"方法对 X 有效"是命题 |
| 读论文、跑数值、整理文献 | beads 任务，结果回填命题 |

若"存在……"日后别扭，加 `kind: construction`，不影响其他结构。

跃迁表**按生命周期顺序放行，但不强制逐级**（M0 实现时明确）：越级前进合法——文献里直接找到答案就是 `open → supported`；回退只允许 `supported / refuted / disputed → testing` 与 `testing → conjectured`；`superseded` 是终态（要重开就是新命题、新 slug，否则等于偷改已经发表出去的东西）；`conflict` 只有 CLI 写得进、只有人走得出。这张表抓的是记账错误，不是管科研该怎么做。

## 5. 论坛模型（多写者规则）

- 每个 note = 正文（创建者所有）+ `## Discussion`（append-only）。帖子头 `### <ISO 时间> · <host>/<line>`；不改、不删他人帖子。
- **状态跃迁必须伴随一条跟帖**（审计）。审核器裁决、人的预测与决定、跨线评论都是跟帖。
- 唯一可变字段是 `status`：last-writer-wins；5 分钟内被不同写者翻两次 → `conflict`，进决策队列。
- 追加**要加锁**（M0 实测修正）：每篇 note 一把 `filelock`，只在一次"读+追加"期间持有。原本的理由是"追加模式下一次小写入由操作系统串行化"——POSIX 成立，Windows 不成立（MSVCRT 把 `O_APPEND` 实现成 seek-to-end 再 write 两步）。8 线程并发追加实测丢 2 条帖子。锁是每篇 note 的，不同命题之间互不等待。
- 派生物（graph.db、index.db、MAP.md）幂等重建，重建期间短锁（沿用 worklock）。
- **feed** = 全部帖子（含 `decisions.md` 条目）按时间的派生视图，可检索（collection `threads`），不落盘。journal 不存在。

## 6. 状态原则与硬触发

- **最近者写状态。** 会话内改了文件的 agent 负责在停机前把 status / 跟帖 / line STATUS 写完；`magi sync --close` 检查。Claude Code 用 Stop hook 阻止未记账的停机；其他宿主尽力。
- **CLI 对跃迁做硬反应，不对叙述做反应。** `testing → supported` 触发审核；`→ disputed / conflict`、线相位提议 → 决策队列。不看 AI 在跟帖里怎么说。
- **派生只查记账债**（有改动、无状态更新）。异常终止后由下次 `next` 第一条还债。
- **只有三类事件叫人**：命题被宣称解决且审核后仍 `disputed`、温层与冷层矛盾、线的方向变化。其余永不打断人。
- `magi close <line>` / `magi publish` 只有人调用。两者的正事是翻转**之前的勘察**（M7 实现时定）：线是视图，关掉它不动文件、动的是注意力——`candidates()` 从此整条跳过，线上还开着的命题再没有东西会举手。所以默认**拒绝**并把每条连同 settle 它的命令列出来；`--anyway` 照做，但关闭帖写下每一个被留下的 slug——路由器不再说了，那条帖是唯一还能说的地方。publish 在两件事上分开拒绝：`disputed`（发论文盖过异议不是回答它，是删掉它）和还开着的活；论文进 `raw/` 成冷层，线上命题 `superseded_by: [[raw/papers/…]]` 并转 `superseded`（question 走 `answered`，`superseded` 不在它词表里）；字段先写、状态后写——中途崩溃留下「指向论文但没退休」的 note 人能收尾，反过来是一个没出口的终态却不知被什么替代。
- **WIP 上限**：一条线 open 命题 > N（默认 7）→ `next` 提示先关，不做打分排序。
- **人的决定怎么留痕**（M2 实现时定）：`vocab.writers()` 说清了离开 `disputed` / `conflict` / `closed` 是人的决定，但帖子签名写的是宿主而不是「谁的决定」——AI 誊写人的决定本来就是常态。所以 `--close` 查的不是谁敲的字，而是决定有没有留痕：帖子签 `--host human`，或者 slug 出现在 `decisions.md`。两者都不是证明，也不打算是；目的是让「把命题从 disputed 走出来」留下可审计的痕迹，而不是让异议在两次运行之间蒸发。
- **会话范围用 mtime**（M2 实现时定）：`--close` 拦近 12 小时的欠账，更早的只列出来。不用 git diff（工作区不一定是 git 库），也不用会话日志（那是又一件要维持为真的东西）。非要等整个库的历史都干净才放人走的闸门会被关掉，而关掉的闸门什么也不强制。
- **Balthasar 的分数是记账干净度，不是进度**（M2 实现时定）：六个开放命题零欠账完全健康；两个开放命题三个没人解释的状态不健康，因为所有投影都是错的。等人拍板的事不扣分——队列存在本身就是系统在正常工作。

## 7. 入口与命令面

- **`magi next`**（裸 `magi` 等价）：派生状态 → 排序的候选动作清单，每条带三样：为什么（哪个信号）、跑什么（命令或 skill 名）、代价（确定性 / 要 LLM / 要人）。**硬菜单软选择**：菜单由代码算，AI 结合用户当次的话选；无人在场只执行确定性项。**安静阈值**：无实质变化则只报开放问题。**只提议，不做事。** 项目级投影 = 哪条线该推；线级投影 = 这条线下一步。
- **porcelain**（人可见；`--help` 默认只列这些，≤ 20 行）：`magi` / `init` / `ui` / `search` / `feed` / `close` / `publish` / `install` / `guide`。
- **plumbing**：全部保留、`--json`、`--help --all` 才列。熟练者可用，不会用不影响。
  - `thread new / post / status`（M1 新增）是写 `threads/` 的**唯一正路**，不是可选糖：追加要拿锁，而 agent 手里的编辑器不拿锁；`thread status` 把改状态和写跟帖绑成一次调用，拆开就是「命题带着一个没人解释的状态」的由来。slug 必须已经是 `slugify` 的不动点（否则 `../x` 会写到 `threads/` 外面，空 slug 会生成没人看得见的 `.md`）。
  - 合并：
  - `sync --fix` 吸收 `graph build` / `index` / `wiki reindex` / `lint --fix` / `ingest finalize` / `pm backlog-sync`（顺序知识进代码，不进 prose）
  - `ingest` 收成 `auto` / `review`（batch-list/decide/commit 三合一）/ `url`；各 rung 变 `--via`
  - `lint` 吸收 `verify` / `claims verify` / `validate` / `math check`
  - `install` 吸收 `setup` / `skills *`
  - ~~`init` 吸收 `pm init`~~ **不合并**（M1 实测推翻）：`bd init` 要 2.5 秒，而且会自己写 `AGENTS.md` / `CLAUDE.md` / `.claude/` / `.codex/`——跟托管块正面冲突。合并的目的是「人少记一条命令」，而 `pm init` 降为 plumbing 后人本来就不会打它：`magi sync` 该提示时会提示，打字的是 agent
  - `hub *` 删；`radar` 收成 `radar` / `radar schedule`
- 后台调度：除 radar 外一律在会话开始时做，无常驻进程。

## 8. Skills

- 判据：**没有 LLM 判断的 skill 不存在。** 单命令包装类（init / hub_init / hub_manager / graph_index / lint / semantic_link / guide）删除，一行写进托管块或由 `next` 提议。
- 清单（8）：`magi`（入口，薄：跑 `next`、照做、见 skill 名就调）、`ingest`（含 ocr、inbox）、`compile`（含 enrich）、`tidy`（math_fix / tag_sync / concept_sync 中需判断的部分）、`ask`、`research`（含 audit：语义触发，找茬只是子 agent 提示词不同）、`draft`、`radar_review`。
- 结构固定：frontmatter → 何时用（≤ 2 行）→ 方法（≤ 10 步）→ 本 skill 特有 Rules。**≤ 40 行。** 工具能力说明、NEEDS-DECISION、beads 记账等样板只在托管块出现一次。事后解释不写（变成命令行为或进 guide）。
- research 产物统一：finding → `threads/` 命题（矛盾 = `disputed` 命题带两条冲突证据帖，进决策队列）+ 至多一篇 `wiki/topics/` 综述（`type: synthesis`，单一 schema）。audit 本质是对整个库跑一遍审核器。
- **官方与自有**（2026-08-29 定）：包里的 8 个是官方 skill，frontmatter 标 `origin: magi`。用户可以有自己的 skill——fork 官方或从头写——放 `~/.config/magi/skills/<name>/`（用户级：skill 是跟人磨合的，不是跟项目；与 registry.json 同处）。`magi install` 从包和这个目录各装一遍，**同名用户的优先**，且**只覆盖带 `origin: magi` 的已有文件**，没有标记的一律不碰（替换现在「正文含 magi 就覆盖」的启发式——用户 fork 的官方 skill 必然含 magi）。40 行棘轮只管官方：那是出厂纪律，不是对用户的要求。

## 9. AGENTS.md 托管块与宿主安装

- `<!-- magi:begin -->…<!-- magi:end -->` 由 CLI 拥有、幂等重写；块外用户所有。`CLAUDE.md` 只含 `@AGENTS.md`。project 一块，line 不单独放。
- 块 ≤ 40 行：入口一行（先跑 `magi next`）、目录含义各一行、五条不变量（不改 `raw/`、一文件一温度、翻状态必跟帖、子 agent 不问人、fan-out 必报数）、强制输出协议（按档位）、guide 指针。**理由不进块**——块每个会话都在付费。
- **规则区**（2026-08-29 定，见 §12）：块内最后一节，由 CLI 从 `output/reflect/ledger.jsonl` 渲染——ACCEPT 且未 PROMOTE、未退出的规则各一行。它是派生物：块的真相 = 模板 + 账本，LLM 永不写块。行数上限 `research.rule_budget`（config，WebUI 可改；默认 7，使默认总长仍 ≤ 40）；满了 ACCEPT 拒绝，先退一条或 PROMOTE 一条。棘轮测试守模板的 40 行，规则区由 ACCEPT 闸门守。**谁改了账本谁重渲染**（`reflect accept | promote`、退出、`sync`），不等下次 `install`；渲染**从不截断**——预算只拦新的 ACCEPT，已渲染的留着，超预算时 `sync` 报一行。块仍是幂等的：同样的模板 + 账本 → 同样的块，只是输入里多了账本。块与账本的**漂移**由 `sync --close` 检查：账本里 accepted 的规则块里没有 → 阻塞并提示 `magi install` 能修（M6 复核加：「记了裁决但没重渲染」以前没有任何东西会发现）。
- `magi install --host <claude|codex|antigravity|qwen|opencode>`：一条幂等命令写 skills + hooks + 托管块。三个 hook（Stop / PreToolUse / SessionStart）一张表、一个合并函数（认出自己的所以重装不重复追加，别人的不动）。**hook 不能弄坏一次会话**（M7 实现时定）：所有路径以 exit 0 + 可解析 JSON 结束，包括工作区不存在、payload 不是 JSON、文件写不进去——报错的 hook 是会被人关掉的 hook，它守的闸门也一起没了。SessionStart 打印 `magi next` 前三条，无事时整个不输出。opencode 是完整宿主但**低优先级**（2026-08-29 定：作者暂不用它）——install 侧已有；无头复核适配器与冒烟做得简单就做，做不成就算，不进 §1.7 的硬约束。**宿主词表对外只有这一个**（2026-08-29 定）：第一梯队 `claude | codex | antigravity`，第二梯队 `qwen | opencode` 及用户自加的。`gemini` 不再是宿主名，也不留别名——Gemini CLI 已废弃，Gemini 家只有 Antigravity（二进制 `agy`）。**宿主是数据不是代码**（2026-08-29 作者定：世上 CLI 太多，能通用最好）：一个宿主 = 一条声明——二进制名、skill 落点（默认走 `.agents/skills/` 跨宿主约定）、无头调用模板与模型参数（`model_flag`；effort 是 argv **模板**不是 flag——codex 是 `-c model_reasoning_effort=low`，claude / agy 是 `--effort low`，一个字段装不下两种形状）、模型列表来源（`list_models` argv 模板，或静态 `models:` 别名表）、`cheap` 默认模型、可选的 `model` / `effort` 覆盖、transcript reader 名——三张表（装到哪 / 无头跑哪个二进制 / 谁的记录读得懂）合成一张注册表 `core/hosts.py`，用户可在 `config.yaml` 的 `research.hosts` 里加同形记录。加一个宿主 = 加一条记录；唯一要写代码的是 transcript reader，没有 reader 就是读不到，不报错；qwen 的 install 目标等查清 qwen-code 的 skill 目录约定再加，不猜；宿主配置用解析-合并-写回并备份，不做文本追加。宿主强制力不对称按文档声明。
- 宿主自带 auto-memory 视为私有缓存；项目状态只以 MAGI 文件为准，冲突以文件为准（写进块）。

## 10. 人机界面

- **输入面只有对话。** 事件触发强制输出：命题开出（预测）、结案（"你预期到了吗"）、线转向（二选一 + 理由）。只允许三种问题：**预测 / 选择 / 证伪条件**；能用"好"回答的一律不问；"不知道"合法且记录。AI 誊写进 `decisions.md` 或命题 `bet:`，人不开文件。档位 `coaching: off | light | strict`（strict：无预测不开始推导）；config 设定，会话内可覆盖。
- **堆放区** `inbox/notes.md`（WebUI 文本框直写）：append-only 带时间戳；下次 `next` 第一件事分类进五个写入面——question / proposition / decision / 跟帖（观察）/ beads；拿不准放 question；原文留链接。
- **MAP**（`output/MAP.md` 派生 + WebUI）两节：各线（状态词、一句到哪了、open 命题数、最后跃迁日期、停滞标记）+ 决策队列（disputed、conflict、待转向、待预测、规则提案）。维护项不上 MAP。字段先做着不行再改。**回溯**：MAP 主动把旧决定和预测命中率拉出来对账，不等人去翻。
- **一张图**：WebUI 认知网络按 kind / status / 温度着色，按 line / kind / 层过滤，默认只画骨架（度数 top-k 或 `skeleton: true`）点开再展；MAP.md 是它过滤到"lines + 队列"的静态渲染，外加 `## Pinned`（`skeleton: true` 的节点；没钉任何东西时整节不出现）——钉住是人说「不管丢什么都留着」，只有开了骨架开关的人看得见的话，就是第三样东西在冒充第一样（M7 实现时补）。`skeleton: true` 是 tag 不是新列（图已经按 tag 过滤，第二套过滤是同一个问题的第二个答案），钉住在排序之后生效：钉住的先留，剩下的预算给最连通的，否则一个够大的钉住集合会静默挤掉所有真 hub。一个数据源两种渲染。

## 11. 审核契约（`magi review`）

- 无头调用：命令由宿主注册表（§9）的模板生成，不在 `review.py` 里逐宿主写死；内置 `claude -p` / `codex exec` / `agy -p`，第二梯队 `qwen -p`、opencode 按其文档化的非交互模式各一条记录，做不成就算。Antigravity 的非交互模式：`agy -p`，模型用 `--model`（不是 `-m`），`--print-timeout` 默认 5 分钟，`--json-schema` 可强制结构化输出——裁决走结构化输出比正则扫文本可靠（2026-08-29 补）。**不做 `gemini -p` 适配器**：Gemini CLI 已废弃。argv[0] 用 `shutil.which` 的解析结果而不是裸名字：Windows 只自动补 `.exe`，npm 装的 `.cmd` shim 裸名字起不来；固定提示词；只给读文件 + 冷层检索；**模型钉便宜档**——每条宿主记录带 `cheap` 默认模型（claude → `haiku` 别名，antigravity → `gemini-3.7-flash-low`；**codex 留空**：它不列模型、id 带日期，写死的名字迟早变成 unknown model 而失败调用照样扣预算——不拿一个会烂的名字换「看起来配全了」），`review_model` 空时用它而不是宿主默认，宿主默认往往是最贵档（2026-08-29 补：实现之前一直是「空 = 宿主默认」，等于没钉）。模型和 effort **按宿主配**（`research.hosts[].model / .effort`），全局 `review_model` / `review_effort` 只作兜底——一个字符串对所有厂商没有意义。模型名能从 CLI 读的就读（agy 有 `models` 子命令，输出 `id 	 标签`；claude / codex 没有列表命令，用记录里的静态别名表），读不到退回自由文本；填错模型名是一次失败调用且扣预算，所以选择器不是装饰。agy 的模型 id 自带档位（`-low/-medium/-high`），模型名已含档位时不再追加 effort，否则一条命令里两个互相矛盾的东西。WebUI：host → model → effort 三级下拉；`magi review --dry-run` 打印三者。
- 触发：`magi sync --close` **列出**本会话翻到 `supported` 的命题；`magi next` 提议，实际调用手动或由还在干活的 agent 发起。不在每次写文件时审。（M4 实现时改：一次无头调用是几分钟延迟加真金白银，塞进 stop hook 而预算闸门在 M6，两样都没有护栏；而要等五分钟的 stop hook 是会被卸掉的 stop hook。）
- 看什么：命题 + 推导（`derivation`）+ 冷层。**不看对话、不看 line 叙述**——"远"指不共享上下文，不指不给证据。
- 默认跨厂商：探测 PATH 上的 CLI，选与作者宿主不同的；没有则同宿主便宜模型；零配置，config 可指定。
- 裁决以跟帖写回；驳回 → `disputed`，不自动翻回；进决策队列。
- **没跑成的复核什么都不写**（M4 实现时补）：一条 reviewer 的跟帖会让命题不再排队，所以只有真读过才写——CLI 没装、超时、进程崩了都不动 note。读不懂的回答写帖（原文附在里面）但不算答案，命题回队列。否则一个坏掉的适配器就是一枚橡皮图章，比没有复核更糟。

## 12. 慢环（`magi reflect`，backpass 式）

- 输入：四宿主本地 transcript + MAGI 结构化 loss（`supported → refuted`、记账债、审核驳回、`next` 同一建议连续被忽略）**+ 结构化 win**（命题一次过审）。每次运行抽样 ≤ 8 个会话（≤ 5 带 loss、≤ 3 带 win），每份 transcript 截 15k 字符。（2026-08-29 补：只喂 loss 的慢环只会长出禁令；skill 方法步骤的改进只能来自成功会话。数字抄 WikiSkill，不行再改。）
- **两段，中间落盘**（2026-08-29 对照 WikiSkill 后改）：transcript → `output/reflect/patterns/*.md`（一模式一页：现象、根因、逐字引用、出现的会话与宿主）→ 提案。不是「派生不存储」的例外：transcript 是宿主私有缓存（§9），不在项目里、会轮转、四种格式，从它算出的东西不可重算，是真相不是派生物；「≥ 2 个独立会话」这道门也只有第一次观察有处落脚时才可执行。模式页**只有 reflect 读写**：不进托管块、不进 `next`、不进任何 skill 的读取面——工作 agent 直接读模式库会按模式防御而不按规则行事，慢环就再也分不清硬化的规则有没有起作用（WikiSkill 消融：给工作 agent 开 wiki 反而掉分）。
- 门：同一 gap ≥ 2 个独立会话；每周 ≤ 5 条提案；**一条提案一个目标**（一行 prose / 一个 hook / 一个测试）；逐字引用；被拒不再提；90 天未再现过期。
- **提案账本** `output/reflect/ledger.jsonl`（2026-08-29 补）：每条提案的目标、证据（模式页 + 引用）、来源宿主、裁决、日期，**由 CLI 在按钮按下时写**，AI 不写。被拒的留全文——被拒不是过滤条件，是下一条提案的输入。「被拒不再提」「90 天过期」由此从 prose 变成对文件的查询。不进 `decisions.md`（那是研究决定）；与 `output/llm-ledger.jsonl`（§13）是两个文件：一个记提了什么，一个记花了什么。
- **溯源与退出**（2026-08-29 补）：ACCEPT / PROMOTE 的账本条目指回催生它的模式页；模式 90 天未再现 → 由它产生的规则进决策队列问「还要吗」。没有退出，prose 和 hook 只会累加。
- **证据分路**（2026-08-29 补）：gap 在 ≥ 2 个宿主出现 → 共享层（块外 prose / 门 / 测试）；只在一个宿主出现 → 该宿主自己的配置（如 Claude 的 hook）。只捕捉某宿主 workaround 的规则不迁移，放进共享层是让另外三个宿主每个会话付费读没用的东西。
- **skill 方法类提案**（2026-08-29 定：出）：从成功会话提炼的「先 X 再 Y」是 skill 的 Method 步骤，不是块规则。目标是官方 skill → 提案标「包级」，ACCEPT 的含义是「这是对 `src/magi/skills/…` 的 diff，去 repo 里应用」——人手动上游，reflect 不写包；目标是用户自有 skill（§8）→ ACCEPT 时 CLI 直接打补丁（patch 词表同模式页）并提示重装。提案必须自带「加哪行、删哪行」。计入每周 5 条。
- 输出进 MAP 决策队列；三按钮 **ACCEPT / REJECT / PROMOTE→CODE**，都是人用面（§1.6），CLI 写账本。ACCEPT → 规则一行进账本，下次渲染出现在托管块规则区（§9）；REJECT → 账本留全文；PROMOTE→CODE → 从**封闭的声明式规则词表**里选一条实例写进 `config.yaml` 的 `research.rules`（带 `from:` 指回账本条目；放 `research` 节下而非顶层，因为配置写入器是外科式的、只认 `section.key`——顶层键要么整文件重写丢掉人的注释，要么第二个写入器），`lint` / `--close` 即刻执行；或装成宿主 hook（走 `install`）。词表装不下的规则**不能 promote**——留 prose，或变成「包级」提案给 MAGI 加一种规则。账本标 promoted，规则区下次渲染自动消失。**RETIRE 是独立动词**（`magi reflect retire`，M6 复核加）：回答「这条规则还要吗」的「不要了」——写 `RETIRED`、删 `research.rules` 实例、**不进**「被拒不再提」清单。退休一条原因已消失的好规则和否掉一个坏主意不是同一件事，用 reject 记它会让好规则永远回不来。`reject` 一条已 promoted 的提案同样删实例——两者都撤规则，区别只在进不进「不再提」清单。（2026-08-29 定；否决工作区 `checks/` 可执行骨架，见 §16。）事实类提案路由到 wiki。**LLM 永不写托管块**：人是唯一的门，CLI 是唯一的笔；hash 守护的是模板与渲染函数，不是渲染结果。（2026-08-29 定：C 方案。否决块外专属区——多一个 CLI 拥有的区和一条上限规则；否决 skill Rules 节——skill 真相在包里、`magi install` 会覆盖工作区拷贝、8 个 skill 余 0–1 行、而 reflect 的证据是项目级的。）
- 自研实现（backpass 只验证过 macOS/Linux 路径），借循环不借代码。transcript 适配器读**装了的每个宿主**（2026-08-29 实测：claude / codex / antigravity / qwen / opencode，五个宿主四种格式。`~/.gemini/tmp/<project>/chats/` 那个 reader 是探这台机器上的实际文件写的，须确认那是 agy 写的——Gemini CLI 已废弃，若是它的格式就改指 agy 的记录位置；qwen-code 是 Gemini CLI 的 fork，同一 reader 指向 `~/.qwen`，**未实测**、形状不同就返回空；opencode 是 sqlite 库不是文件），按「读一个会话」抽象不按「读一个路径」；一个宿主读不了记进 sweep 不抛。**读 transcript 不等于是 §9 的安装 / 复核宿主**——opencode 要不要成为完整宿主见 §15。

## 13. 成本治理

- MAGI 只硬管**它自己发起的**调用（review、reflect、堆放区分类）：`output/llm-ledger.jsonl` 记账；周预算 + 每类工作用哪个模型 + 总开关；超预算拒绝启动并在 MAP 说明。WebUI 配置。
- 会话内 fan-out 只有软约束：skill Rules + Claude Code PreToolUse hook 计数；其他宿主无。计数**只数不拦**（M7 实现时定：子 agent 是 agent 在人自己账号上干自己的活，拦它不是 MAGI 该做的决定），每第 25 次 `systemMessage` 报一次累计数并指回不变量，其余静默；按 session 分开。**软约束的阈值必须高于本系统自己规定的正常批量**（M7 实现时改：skill 把 fan-out 并发压在 10 并要求先报数，阈值定 10 时唯一会触发的正是已经照做了的那个工作流——一个只在误报时才响的钩子；过了 25 要么没人报数、要么报的数是错的）。计数**不进 `llm-ledger.jsonl`**，单开 `output/fanout.jsonl`——账本是周预算读的那个数，掺进 MAGI 没发起的调用会弄脏唯一能拒绝的数字。

## 14. 三核重映射

Melchior = 知识（冷 + 温·共享）；Balthasar = 意图（`threads/` + `decisions.md`，不再是 beads）；Casper = 检索（含 feed）。`magi sync` 三行显示相应改写。这三行是**对外的架构声明**：README / guide 里的示例输出必须是真跑出来照抄的、和 `build_report` 对得上——`test_docs_in_sync` 只查命令存不存在，查不了示例；示例比散文更容易被当真（M7 实现时补：README 那段 v1 的 `0 ready · 0 in progress · 0 blocked` 就印在刚把 Balthasar 改成 `threads/` 的表下面，两个一起读拿到的正是这次发布要替换掉的架构）。

## 15. 实现时再定（第三梯队）

稳定 ID 细则、bet / decision 记分规则、`construction` kind、线级规则作用域（先全项目级）。已定：词表在 M0 冻结；threads 在知识型查询降权 0.6（M1）；决策队列不写 bd（M2）；`each` 随 hub 一起删掉（M3）——跨库批跑的替代物是 shell 里对 `magi kb list --json` 的路径做循环，不值得为它保留一条命令和一套 hub 语义；ACCEPT 的规则从账本渲染进托管块规则区、预算单列（2026-08-29，C 方案，见 §9 / §12）；reflect 出 skill 方法类提案——官方 skill 走包级人手动上游、用户自有 skill 由 CLI 打补丁（2026-08-29，§8 / §12）；opencode 是完整宿主但低优先级（2026-08-29，§9 / §11）；Qwen Code 同为第二梯队——它是我在 v2 设计时作为 Gemini CLI 的 fork「顺带」带进来的，作者未要求；宿主注册表合一、宿主可由用户声明（2026-08-29，§9）。

## 16. 已否决（不再讨论）

打分自动晋升（OpenClaw 式）；逐项人工审批晋升；claim 级温度；`threads/` 内目录级温度；独立 journal 文件；audit 与 research 分开的产物类型；独立的审核 UI；GEPA / ACE 类 benchmark 优化；直接安装 backpass；AI 调用 close / publish；概念卡分线；常驻调度进程；工作区内的可执行 check 文件作为 PROMOTE 产物（数据目录里跑代码，且等人补全的失败骨架是橡皮图章，2026-08-29）。

## 17. 对照过的外部方案

Claude Code auto memory（MEMORY.md 索引上限 → 借"有界索引"）、Codex memories（空闲触发两阶段 → 借"批量后台"）、Qwen Code（`pinned/` + team-memory → 借"人工条目免清理"）、OpenClaw（dreaming 打分门 → 否决）、agentmemory / ai-memory（markdown 为真相源、SQLite 为派生索引 → 与 MAGI 同路线）、backpass（慢环）、A-MEM（note 互链）、MemoryOS（分级晋升）、CoALA（记忆分类学）、WikiSkill（2026-08-29；trace → 模式 wiki → 一条原子 skill 提案，wiki 不回滚、账本由 harness 写 → 借「慢环中间层 + 程序写的提案账本 + 工作 agent 不读模式库」；它的验证集门控不借，科研没有 ground truth，人是门）。
