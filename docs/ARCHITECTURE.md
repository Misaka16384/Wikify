# 代码架构

`design-v2.md` 说这个产品是什么。这份说**代码放在哪一层**——它是在一轮全量 review 之后写的，那轮的 25 个缺陷里大部分能追到"没人说过新代码该放哪"。

---

## 分层

```
core/        无状态基础设施。不 import 上面任何一层。
             project · workspace · config_loader · vocab · rules
             wiki_common · managed · ledger · worklock · trace · http

kb/          知识库的读写：threads · llmwiki · graph · math · link · claims
ingest/      外部世界进来：auto · batch · ocr · zotero · arxiv
reflect/     慢环：signals · patterns · propose · proposals
retrieval    检索索引与搜索
state        派生视图（magi next 的输入），只读地看整个项目

cli.py       argparse 与分发。薄。
ui/          WebUI；调 kb/ingest/state 的函数，不重新实现它们
skills/      给 agent 读的散文；只调 CLI，不 import Python
```

**依赖只能向下。** `core/rules.py` 目前反向 import 了 `..kb`（函数内），那是债，不是范例。全仓 142 处函数内 import 大多是为了躲循环依赖——每加一处都该问一句"是不是这一层放错了"。

---

## 三条硬规则

### 1. 项目是 `Project`，不是 `Path`

```python
from magi.core.project import Project

project = Project.at()          # 从 cwd 找；找不到返回 None
project = Project.of(root)      # 就是这个根
```

拿到的东西**自带配置**、**自带目录表**、**自带边界**。

```python
project.drafts                       # 而不是 root / "drafts"
project.markdown(searchable=True)    # 而不是自己写一遍该走哪几个目录
project.resolve(untrusted_ref)       # 越出项目就抛，调用方不必记得检查
```

为什么是硬规则：拿裸 `Path` 的代价这个项目付过三次。配置要手工穿过调用链——`magi reflect` 因为六个调用点漏传 `config=`，整个功能对声明了自己 CLI 的项目不存在。边界要调用方自觉——两个路径穿越漏洞都是"某处忘了 `is_under`"。目录要各写各的——见下条。

### 2. "哪些目录算数"只有一个答案：`core/project.LAYOUT`

需要一组目录时，**说出你问的是哪个问题**，不要重抄答案：

```python
dirs(rewritten=True)     # 维护类改写可以动的
dirs(searchable=True)    # 检索索引要走的
dirs(documents=True)     # lint 的通用文档加载器要读的
wikilink_dirs()          # [[链接]] 可以落在哪，按优先级
```

加一个目录 = 在 `LAYOUT` 加一行，而**一行加不完整就过不了 `test_project_layout.py`**——每个问题都必须回答。

这条规则是被一个真实缺陷买来的：曾经有八个手写的目录集合互不知情，其中 `magi lint` 走的是 `("raw", "wiki", "inventory", "datasets")`——两个 v1 就不再存在的目录，而 v2 新增的 `drafts/`（所有推导所在）和 `threads/` 一个没有。同一个过时元组在同一个文件里有两份，改了一份行为毫无变化。没有任何测试能发现，因为那份清单只存在于那一行。

### 3. 命令逻辑是函数，不是子进程

新代码**不要** shell out 到 `python -m magi ...`。要另一个命令做的事，import 它的 `main(argv)` 或它下面的函数。

现存 24 处自我子进程调用是历史包袱，代价是记录在案的：`core/worklock.py` 的文档解释了为什么锁的归属必须**通过环境变量**传给子进程——因为 `ingest batch-commit -> ingest finalize -> lint --fix` 是三层进程深，而文件锁属于句柄不属于进程树。同一个结构还产出过：被捕获输出的子进程仍继承终端 tty，于是 `magi pm init` 把确认问题写进没人读的管道、自己拒绝了自己。

真正需要进程隔离的只有三处（自更新重启、WebUI 服务重启、WebUI 任务隔离）。那三处走 `core.trace.run()`，由它统一处理空管道 stdin（**不要用 `DEVNULL`**：Windows 上它打开 `NUL`，是字符设备，`isatty()` 返回 True）、捕获、以及把子进程的全部输出交给 trace 通道。

---

## 出错与汇报

- 面向人的输出用 `print()`。这是设计的一部分，不要改成日志级别。
- 面向开发者的输出用 `core.trace`：`trace.say()` / `trace.step()` / `trace.run()`。默认全静音，`--verbose` 或 `MAGI_DEBUG=1` 打开，并且**会传给子进程**——所以最外层加一个 `--verbose`，能看到最里层。
- 每个命令的失败都要经过一个地方。`cli.main` 有兜底，会按 `--json` 与否统一格式化，并把 traceback 送到 trace 通道。**不要**在子命令里自己 `except Exception` 然后打散文——那会绕过契约。
- `--json` 的成功和失败必须是同一种形状。`reflect._decide` 曾经七个拒绝分支打散文、成功路径打 JSON，而 WebUI 正是传 `--json` 的那个调用方。

---

## 测试的房规

测试数量不是问题（33k 行测试 / 26k 行源码）。**测试查错层**才是——本轮 8 个假绿全是这个形状。

1. **检查写在会出错的那一层。** 每个测试都自己把 `config` 递给表函数，于是表被证明能用，而六个没接线的调用点一次都没跑到。
2. **期望不要从被测对象里取。** 从 `CORPUS_DIRS` 读期望值的守卫，在常量被改坏时期望跟着改，照绿。写死。
3. **豁免按形式或位置划，不按词划。** 按词豁免的 allowlist 会把最该查的那处一起豁免掉。剪掉豁免跨度再扫剩下的，不要整行跳过。
4. **计数型断言会被改写绕过。** `count("X") >= 2` 的守卫，把 X 整串删掉反而变绿——从 fail 掉进 skip。查形状，不查出现次数。
5. **加一个守卫就加一个变异用例**（`tests/mutations/cases.py`）。没被人看着红过的守卫，价值未知。

```
python -m tests.mutations           # 全部
python -m tests.mutations layout    # 某个领域
```

---

## 已知的债（按顺序）

| # | 债 | 证据 |
|---|---|---|
| 1 | 24 处自我子进程；`worklock` 的环境变量变通 | `core/worklock.py:19-26` |
| 2 | `kb/llmwiki.py` 2679 行，24 处按目录划范围（其中 6 处仍判 `inventory`/`datasets`，全文 35 处提及这两个不存在的目录） | 本轮 5 个缺陷提交里它占 3 个 |
| 3 | 6 种失败约定并存；`ui/api.py` 22 处兜底 vs CLI 侧几乎没有 | 同一个 `run_search` 两个界面表现不同 |
| 4 | `config_loader._DEFAULTS` 的默认值在 5+ 处重复 | `ollama.base_url` 写在 5 个文件里 |
| 5 | lint 的各项检查各自划范围，`drafts/` 只进了链接类检查 | 哪些卡片形状的检查该有草稿版本，是产品决定 |
| 6 | 两个 frontmatter 解析器、两个 `slugify`（一个截断一个不截断） | `wiki_common` vs `llmwiki` |
