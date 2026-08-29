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
4. **确定性 CLI 是拘束具。** 能写成命令/门/测试的规则不写成 prose；prose 规则是硬化候选。
5. **人的输入面只有一个（对话）。** 人被要求写字的时刻 = 人必须读的时刻，是同一组事件。
6. **仪式性动作留给人。** 关线、发表只有人调用，AI 永不调用。
7. **硬约束不变**：Windows + macOS；Claude Code / Codex / Gemini 三宿主冒烟（Qwen Code 顺带）。

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
- `magi close <line>` / `magi publish` 只有人调用。publish：我方论文进 `raw/` 成冷层；相关命题 `superseded_by: [[paper]]`。
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

## 9. AGENTS.md 托管块与宿主安装

- `<!-- magi:begin -->…<!-- magi:end -->` 由 CLI 拥有、幂等重写；块外用户所有。`CLAUDE.md` 只含 `@AGENTS.md`。project 一块，line 不单独放。
- 块 ≤ 40 行：入口一行（先跑 `magi next`）、目录含义各一行、五条不变量（不改 `raw/`、一文件一温度、翻状态必跟帖、子 agent 不问人、fan-out 必报数）、强制输出协议（按档位）、guide 指针。**理由不进块**——块每个会话都在付费。
- `magi install --host <claude|codex|gemini|qwen>`：一条幂等命令写 skills + hooks + 托管块；宿主配置用解析-合并-写回并备份，不做文本追加。宿主强制力不对称按文档声明。
- 宿主自带 auto-memory 视为私有缓存；项目状态只以 MAGI 文件为准，冲突以文件为准（写进块）。

## 10. 人机界面

- **输入面只有对话。** 事件触发强制输出：命题开出（预测）、结案（"你预期到了吗"）、线转向（二选一 + 理由）。只允许三种问题：**预测 / 选择 / 证伪条件**；能用"好"回答的一律不问；"不知道"合法且记录。AI 誊写进 `decisions.md` 或命题 `bet:`，人不开文件。档位 `coaching: off | light | strict`（strict：无预测不开始推导）；config 设定，会话内可覆盖。
- **堆放区** `inbox/notes.md`（WebUI 文本框直写）：append-only 带时间戳；下次 `next` 第一件事分类进五个写入面——question / proposition / decision / 跟帖（观察）/ beads；拿不准放 question；原文留链接。
- **MAP**（`output/MAP.md` 派生 + WebUI）两节：各线（状态词、一句到哪了、open 命题数、最后跃迁日期、停滞标记）+ 决策队列（disputed、conflict、待转向、待预测、规则提案）。维护项不上 MAP。字段先做着不行再改。**回溯**：MAP 主动把旧决定和预测命中率拉出来对账，不等人去翻。
- **一张图**：WebUI 认知网络按 kind / status / 温度着色，按 line / kind / 层过滤，默认只画骨架（度数 top-k 或 `skeleton: true`）点开再展；MAP.md 是它过滤到"lines + 队列"的静态渲染。一个数据源两种渲染。

## 11. 审核契约（`magi review`）

- 无头调用：`claude -p` / `codex exec` / `gemini -p` / `qwen -p` 各一适配器；固定提示词；只给读文件 + 冷层检索；模型钉便宜档。
- 触发：`magi sync --close` 批量审本会话翻到 `supported` 的命题；也可手动。不在每次写文件时审。
- 看什么：命题 + 推导（`derivation`）+ 冷层。**不看对话、不看 line 叙述**——"远"指不共享上下文，不指不给证据。
- 默认跨厂商：探测 PATH 上的 CLI，选与作者宿主不同的；没有则同宿主便宜模型；零配置，config 可指定。
- 裁决以跟帖写回；驳回 → `disputed`，不自动翻回；进决策队列。

## 12. 慢环（`magi reflect`，backpass 式）

- 输入：四宿主本地 transcript + MAGI 结构化 loss（`supported → refuted`、记账债、审核驳回、`next` 同一建议连续被忽略）。
- 门：同一 gap ≥ 2 个独立会话；每周 ≤ 5 条提案；逐字引用；被拒不再提；90 天未再现过期。
- 输出进 MAP 决策队列；三按钮 **ACCEPT / REJECT / PROMOTE→CODE**（变成 hook / 门 / 测试并删 prose）。事实类提案路由到 wiki，不进 AGENTS.md。永不改托管块。
- 自研实现（backpass 只验证过 macOS/Linux 路径），借循环不借代码。

## 13. 成本治理

- MAGI 只硬管**它自己发起的**调用（review、reflect、堆放区分类）：`output/llm-ledger.jsonl` 记账；周预算 + 每类工作用哪个模型 + 总开关；超预算拒绝启动并在 MAP 说明。WebUI 配置。
- 会话内 fan-out 只有软约束：skill Rules + Claude Code PreToolUse hook 计数；其他宿主无。

## 14. 三核重映射

Melchior = 知识（冷 + 温·共享）；Balthasar = 意图（`threads/` + `decisions.md`，不再是 beads）；Casper = 检索（含 feed）。`magi sync` 三行显示相应改写。

## 15. 实现时再定（第三梯队）

稳定 ID 细则、词表冻结、threads 在知识型查询中的降权、bet / decision 记分规则、`construction` kind、线级规则作用域（先全项目级）、`each` 去留、决策队列是否同时写 bd。

## 16. 已否决（不再讨论）

打分自动晋升（OpenClaw 式）；逐项人工审批晋升；claim 级温度；`threads/` 内目录级温度；独立 journal 文件；audit 与 research 分开的产物类型；独立的审核 UI；GEPA / ACE 类 benchmark 优化；直接安装 backpass；AI 调用 close / publish；概念卡分线；常驻调度进程。

## 17. 对照过的外部方案

Claude Code auto memory（MEMORY.md 索引上限 → 借"有界索引"）、Codex memories（空闲触发两阶段 → 借"批量后台"）、Qwen Code（`pinned/` + team-memory → 借"人工条目免清理"）、OpenClaw（dreaming 打分门 → 否决）、agentmemory / ai-memory（markdown 为真相源、SQLite 为派生索引 → 与 MAGI 同路线）、backpass（慢环）、A-MEM（note 互链）、MemoryOS（分级晋升）、CoALA（记忆分类学）。
