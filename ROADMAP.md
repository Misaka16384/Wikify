# MAGI 开发路线图（动态文档）

> **本文档是活的交接文档。** 任何 agent 接手工作前必读；完成一步就更新对应条目（勾选 checkbox、追加 Status 注记）。架构定案见下方"锁定决策"，不要重新讨论已锁定项。**手上没活时，先看"待修问题"那一节**——那里每条都有复现证据。
>
> 最后更新：2026-08-22 · 当前阶段：**v1.12.2 已发布**（tag `v1.12.2`；版本号同步 ×5）。此前：M0–M9 全部完成。
>
> 2026-08-22 「在哪儿启动 magi ui 影响什么」——一个问题问出两个真 bug (v1.12.2)：用户随口一问，查下去发现启动目录管了两件它不该管的事。
>
> **先说不影响的，因为我一开始怀疑错了。** 我 grep `workspace=` 没搜到 graph/browse 和 doc 的调用，以为面板会串库。**是 grep 写错了**——那几处用 `URLSearchParams` 拼参数，字面量里当然没有 `workspace=`。实际六个 workspace 端点（graph/browse、doc、search、tasks、pm、radar）**全都显式传 workspace**；`launchJob` 永远发 `kb: state.workspace`，没选工作区直接拒绝；任务库是从**选中的**工作区往上走找的。所以面板数据和操作落点只认顶栏选择器，跟启动目录无关。合法影响的只有两件便利性：首次加载预选哪个工作区，以及「Browsing」徽章亮不亮（它比的就是这个字段）。
>
> **① 装了 MAGI 的人，Docs 里「README (English)」是空白的。** `/api/docs/readme` 的回退链最后落到 wheel 的 `long_description`——而那**只有 README.md**（中文那份），`README_en.md` 根本没进包。实测：从仓库检出目录启动 en=25614 字符，从真实工作区启动 **en=0**。也就是说除了从 git 检出起服务的开发者，**所有用户看到的第二个标签页都是空的**。修法：两份 README 复制进 `src/magi/docs/`（`package-data` 本来就收 `docs/*.md`），端点优先读打包副本。**构建 wheel 验证过**——`magi/docs/readme.en.md`（26,173 B）和 `readme.zh.md`（25,210 B）确实在里面；现在从仓库和从任意目录启动返回内容完全一致。加了逐字节比对测试盯着副本和原件，因为没有构建期生成，两份文档一旦改一份就会漂移。
>
> **② 不指定 library 的 enqueue，会把论文归档到启动目录。** `_resolve_workspace(None)` 最后落到裸 `Path.cwd()`。而浏览器插件发的是 `$("library").value`——**picker 没加载出来时它就是空字符串**，于是静默塞进 `magi ui` 恰好启动的那个目录。论文进错库比没进更糟：它没丢，它在别处，而没人会去那儿找。
>
> **这里我第一版改过头了：** 直接要求"必须指定 library"，结果打挂两条既有测试——它们 `chdir` 到真工作区再省略 library，那种情况**完全无歧义**。收窄成：启动于工作区内 → 照常允许（和其他所有端点对未指定 workspace 的处理一致）；启动于工作区外 → 400 并列出可用库名。插件也在本地先拦一道，报的是真问题（端口不对 / 服务没起 / 一个库都没注册），而不是白跑一趟再看服务端脸色。
>
> 新增 `tests/test_launch_directory.py`（9 条），其中一条静态扫 app.js，确保每个 workspace 端点都点名了工作区——防的正是"某个面板悄悄读启动目录"这一类。
>
> 测试 793 → **802**。
>
> 2026-08-22 发布流程自证其伪，以及文档一致性 (v1.12.1)：纯文档修正——但手册是**打包进 wheel 里**的（`magi guide` 读的就是它），所以不发版用户拿不到。
>
> **① `RELEASING.md` 里两条写着的东西，被真发一次版当场推翻。**
>
> 其一，**`pipx install --force` 在这台机器上根本不干活**。pipx 的 uv 后端拒绝清理一个不是本次会话建的 venv：先报 `A virtual environment already exists ... Use --clear`，再报 `Not removing existing venv ... because it was not created in this session`，然后打印 `Installing to existing venv`——**旧版本原地不动**。它 exit 1，但那句话读起来像成功。在隔离的 `PIPX_HOME` 里复现过：对着已装的 `cowsay==6.0` 跑 `pipx install --force "cowsay==6.1"`，装完还是 6.0。文档改成明确警告不要用，并给出两条**实测可用**的：要最新用 `pipx upgrade`，要精确钉版本先 `pipx uninstall` 再 `pipx install "pkg==X.Y.Z"`。
>
> 其二，**"刚发完版解析到旧版本"不是本地缓存**。原文归因于 index cache，开的药方是 `--force` / `--refresh`。真实原因是 `pypi.org/simple/<pkg>/`（**所有解析器实际读的那个**）比 JSON API 慢好几分钟——所以 `pipx upgrade` 报 "already at latest 1.11.0" 是**对的**，本地加什么 flag 都没用。当时轮询 simple index 约 5 分钟后 1.12.0 才出现，出现之后一次就升上去了。文档改成"先看 simple index 再升"。
>
> 另外补了一条 Windows 细节：shim、venv 里的 python、以及拉起它的那个 python **三者都持有 magi.exe**，所以半失败的安装要杀**进程树**（`taskkill /PID <pid> /T /F`），只杀那个在监听端口的不够。
>
> **② 审计翻出两处自相矛盾，都比这次发布更老。**
> - 两份手册都先教 `magi index --rebuild`，**350 行之后**又白纸黑字写"`magi index` 没有 `--force` / `--rebuild`"。这个 flag 是真的（v1.12.0 加的）。此前那条测试只检查"提到了这个 flag"——而一个同时否认它的页面，照样满足这个检查。
> - **三处硬编码的技能数，三个不同的数字，没一个对**：英文手册写 19/19，中文写 18/18，`skills_cmd.py` 的 docstring 写 18。实际是 **20**。
>
> **③ `tests/test_doc_consistency.py`（21 条）把线钉住**：所有面向用户的文档只给同一条安装命令；那条坏掉的写法只允许出现在维护者文档里、且只能作为警告；中英两份手册**指令集合必须一致**——比较的是"命令骨架"（动词 + flag 名），因为 `magi search "anyon statistics"` 和 `magi search "任意子统计"` 是同一条指令的正确本地化，不是漂移（这条测试我前两版写错了，错的是测试不是文档）；安装脚本必须真的跑手册宣称它跑的那条命令；技能数**对着代码查**而不是对着散文查。两条新守卫都先注入真 bug 看着它们失败，再留下。
>
> 测试 772 → **793**。用户决定：`radar-stress-ws` 保留在注册表里，留作以后的测试库。
>
> 2026-08-21 云端向量、任务可见可管、玻璃材质塌成一块灰 (v1.12.0)：用户一次提了六条，全部落地。
>
> **① 图谱把 reference 画成了 concept——67/87。** `nodes.type` 取的是 frontmatter 的 `type:`，但那个字段在文献卡上回答的是**来源种类**（papers / articles / book），不是**节点种类**。这些值都不在图谱的调色板里，而画布上写的是 `col[n.type] || col.concept`，于是全部按概念蓝画出来。实测三个真实库：`radar-stress-ws` **67/87**、`Algebra+Duality+Defect` 17 个、`homology-kw-duality` 15 个。目录本来就知道正确答案，只是以前 frontmatter 优先。改成目录说了算、frontmatter 只有在写的是真节点种类时才赢；拿一份拷贝重建验证过，67 个全部从 `papers` 变成 `reference`。**已有的 graph.db 要跑一次 `magi graph build` 才会变。** 那个 `|| col.concept` 的兜底是这个 bug 的另一半：不认识的类型渲染成一个自信的概念，现在有自己的颜色，图例还会把产生它的原始 type 字符串一起列出来。顺带：`topic` 和 `thesis` 共用 `--accent-sage`，图例里两个条目画一模一样的点——语义色板里没有第五个能给 thesis 的，因为那几个色编码的是含义不是类别，所以图谱现在有自己的六个色相（每主题一套）。
>
> **② 浅色 MAGI 的玻璃在任何不透明度下都是同一块灰。** 这条查出来最漂亮。`max(--glass-floor, k * --glass-alpha)` 是**逐面**夹的，而浅色主题 floor=0.5，卡片渐变的两个端点（0.30、0.44）、顶栏（0.42）、终端体（0.42）全在 floor 以下——于是**在每一个滑杆位置上，这四个面都精确等于 0.50**。设计了三种不同权重的四个面，渲染出来是一块平灰；而且拖滑杆时它们纹丝不动、别的面在动，所以"不同不透明度下不统一"。改成 `k * max(floor, alpha)`：floor 变成对**滑杆**的下限，不再是对每个面的下限，相对权重在任何位置都成立。恢复层次之后整体密度掉了，浅色扛不住（深色文字压在浅色照片上的对比余量远小于反过来），所以加了 `--glass-weight`，浅色 1.35、其余 1；最浓的面在满滑杆时落在 0.97，刚好不到不透明，顶端也不会拍平。另外两个面根本没参加这套材质：**终端**在自己那层玻璃体后面刷了一块不透明的 `--term-bg`（这就是"终端背景是纯色"的原因），次级按钮是平的 90% 白、没有 blur 也没有 brightness，坐在三样都有的卡片里，所以那些格子看着是死的。搜索结果卡固定在 0.88，完全无视滑杆。
>
> **③ 17 条任务看不见也管不了。** 面板只有四个数字，而任务库是整个 Hub 共用的，所以"17 ready"既打不开也说不清是谁的；那行说明还写着"这些数字不只是当前工作区"——真话，但把"那到底哪几条是我的"留给了读者。MAGI 开的每条 issue 本来就带 `topic:<workspace>` 标签，所以共用的库完全可以按库回答。现在列出来了，带 Start / Close / Reopen，并且直说归属：这台机器上 17 条**全部**属于 `Algebra+Duality+Topology`，面板就写"17 条，全在这个工作区"，而不是去警告一个并不存在的歧义；从兄弟课题看则是"这里 0 条，Hub 下另有 17 条"——两个数字都给，因为光一个"0"看着像面板坏了。四个计数改成从列表自己那份数组算，此前来自 `bd status`（Hub 范围），于是一个一条都不拥有的工作区会在空列表上方显示 READY 17。**Hub / 工作区 / 知识库是三个词对应两个半东西**，而这行说明正是读者一次撞上全部三个的地方，所以挂了个解释：工作区 = 一个课题的目录；Hub = 装着若干工作区的上级目录，任务库在它根上；知识库不是第四种东西，就是**已注册进检索**的工作区。
>
> **④ 不装 Ollama 也能有语义检索。** `embedding.provider: openai` 指向任何说 OpenAI `/v1/embeddings` 的接口——一条代码路径同时覆盖 SiliconFlow、Jina、Gemini 的兼容层、DeepInfra 和 OpenAI 自己。**Cohere / Voyage / 智谱故意没做**：它们的 API 不是这个形状，每家都得单写一个客户端。四家的接口形状都对着各自官方文档实际查过；免费额度写成"以各家页面为准"，因为有几个数字无法从静态页面确认——宁可标注不确定，也不写看起来很确定的过期数字。两个坑：响应按 `index` 重排而不是信到达顺序（OpenAI 不保证顺序，弄错的话每个向量都挂到错误的 chunk 上，而形状还对得上，静默出错）；换模型会改变向量宽度，旧索引装不下，`ensure_schema` 现在直接拒绝，而不是往里写塞不进去的行。remediation 提示里的 `magi index --rebuild` 是**真加了这个 flag** 才敢写——上一版我差点发出一条指向不存在参数的提示。
>
> **⑤ 配置里的 token 现在能在 WebUI 填。** `ocr.mineru_api_token` 和 `embedding.api_key` 是 `secret` 类型：GET 只回答"有没有"，从不回答"是什么"；raw 配置转储里对应行被打码；把遮罩本身提交回来会被拒绝；空输入不会清掉已存的 key；每个都带一条"去哪儿拿"的链接。provider 是下拉，取值在服务端按 choices 校验——否则那个下拉只是装饰。
>
> **⑥ 危险操作区只提 Claude。** 派了一轮全仓审计，结论是**后端本来就是厂商中立的**——`magi setup` 里跑的是 `report_agent_skills()`，遍历 `skills_cmd.HOSTS` 的四个宿主（claude / codex / agy / opencode），doctor 表也是"要么全列要么都不列"。是 WebUI 的文案把唯一一个 Claude 专有的步骤（插件市场注册，别家确实没有这个机制）描述得像是整个操作。两条危险操作说明现在都点名四个宿主，并说清哪一步只属于 Claude Code、为什么。清理旧版那条确实只扫 `~/.claude` 和 `~/.gemini`——因为旧版 Wikify 早于其余三家的支持——现在把这个理由写出来了，否则读起来像偏袒。还有一处潜在的：`guide.py` 的 `_CMD_TOOLS` 认得 `claude` 却不认得 `codex` / `agy` / `opencode`，为别家写的示例命令会被静默丢掉。新增 `tests/test_vendor_neutral.py` 盯住这些，其中一条断言"清理旧版"的文案和实际扫描的目录始终一致。
>
> **发布流程踩到自己文档里写的那个坑。** 用户自己跑了 `pipx install magi-research`，pipx 覆盖了 `~/.local/bin/magi.exe`——那是 uv 的入口。此后机器上两个管理器各持一份。清理时 `uv tool uninstall` 删掉了自己的 venv 和注册，然后**试图删掉 pipx 的那个入口**、被用户正在跑的三个 `magi ui` 进程锁住而失败——纯属走运。这正是 v1.11.0 文档里新写的那条警告，它自己应验了一次。
>
> 测试 730 → **772**。未做/已知：`radar-stress-ws` 还在注册表里；用户那三个 `magi ui` 进程还跑着 1.11.0 之前的代码，需要重启；`magi graph build` 需要用户自己跑一次才能看到图谱配色修复。
>
> 2026-08-21 确定性摄入、批量审批闸门、可关闭的功能 (v1.11.0)：这一版的起点是一次真实事故——一位客户用 codex 的 goal 模式跑 `magi radar harvest`，一次把周额度跑完了。
>
> **事故根因（两轮只读调查 + 16 个 subagent，客户日志佐证）**：radar harvest 本身几乎不花 token，但它产出的 accept 卡片正文是一句写给 agent 的祈使句「下载 PDF/源码到 inbox/ 并运行 wiki_ingest 技能」。agent 照做，然后连撞三次静默降级：MinerU 默认关闭（`ocr.use_mineru: false` 出现在每一个新工作区）→ 本地 OCR 需要 `ollama pull glm-ocr`，网络失败并反复重试 → 最后自己上手 Native Vision，**一页一个 subagent**。实测一篇 99 页的论文烧掉约 134,000 orchestrator token，而走本地 OCR 只需要一次 shell 调用。三次降级，零次提问。
>
> **真正的根因不是视觉路线贵，而是 MAGI 能转换文档却从来不会获取文档。** `src/magi/ingest/` 里唯一有网络代码的是 `mineru.py` 和 `ocr_engine.py`，没有任何东西负责把源文件取回来。没有确定性的获取路径，agent 只能即兴发挥。
>
> **① 阶梯，测过才定的。** 新的 rung 1 是 **arXiv 自己的 LaTeXML HTML**（`arxiv.org/html/{id}` → `ar5iv` 回退）。37 个 id 实测：ar5iv 在本用户库占多数的 2023 年前切片上 **14/15 = 93%**，1992–2019 全覆盖，**每一条命中都带 `alttext`**（每篇 107–2381 处）；原始 TeX 逐字写在属性里，读它不是识别，是读一段本来就写好的 TeX。`2608.20333` 上 767 个 `<math>` / 767 个 `alttext` / 767 个 `<annotation encoding="application/x-tex">`，1:1:1。原生 `/html` 也**不像官方文档说的那样卡在 2023-12**，2000 年的论文照样命中。
>
> 两次头对头比较直接暴露了旧 tarball 路线的实伤：`2401.00506` 上 `tex2md` **静默丢掉全部 6 张图**（它自己的日志写着 "references 6 figure(s) but only 0 survived"），而图片文件就在主 `.tex` 旁边；`cond-mat/0001002` 上 pandoc 直接死在 `\vskip 0.3truein` 这个 plain-TeX 原语上，什么都没产出。唯一还赢的一项是 `align` 分组，那是个后处理问题，不是保留 tarball 的理由——tarball 依然是 rung 2，因为 rung 1 是 beta，没有 SLA。
>
> **② 阶梯上跑的是闸门，不是偏好。** `arxiv-html → tex → textlayer → mineru → ocr`，**`vision` 不在阶梯里**，永远掉不到它上面。纯文本层那一级由 PyMuPDF 的两个正交判断决定：有没有可用文本层、里面有没有数学。顺带纠正一条我自己先前写错的判断：**真实 arXiv PDF 上根本没有 U+FFFD**——CM/AMS 字体的 `/Encoding /Differences` 里有规范字形名，MuPDF 已经解开了。字符是好的，**活不下来的是二维结构**（从一个横线字形加上下两坨内容里还原 `\frac{a}{b}`）。结论没变，但理由是结构性的，不是编码性的。
>
> **③ 没有人批准过的东西进不了库。** 新的 `output/ingest/` 走 append-only JSONL + last-write-wins（`seen.jsonl` 已经验证过的那套），`queue.jsonl` 一行一个请求，`<batch_id>.jsonl` 一行一个条目。`batch-run` 在开始时对队列做快照，只处理严格早于该次读取的条目——否则一条"拒绝并重试"会被卷进它本来要跟在后面的那一批。闸门在 commit，不在 review：一条转换完就能审，但没有全部决定完谁也进不了 `raw/`。拒绝会**自动降到下一级并出现在下一批**，用户不用手动重投。
>
> **④ Zotero 导入，在用户真实的 758 条库上量过。** 直接带 arXiv id 的有 221 条；**批量 DOI→Semantic Scholar 把它抬到 370 条（48.8%）**。用 `POST /graph/v1/paper/batch`——官方 OpenAPI 写 500 个 id 一次，**匿名限额实测拒绝 295，100 可以**，所以按 100 切。标题守卫是**比例**不是固定下限（固定下限 3 会把 "Fractons" 对 "Fractons" 判成不匹配）。SQLite 一律**先复制再只读打开**，绝不碰用户正在跑的库；`extensions.zotero.dataDir` 从 prefs.js 读，这是跨平台唯一权威来源。
>
> **⑤ 浏览器按钮，故意做得什么都不会。** `browser-extension/` 只有 manifest + popup，不抓取、不下载、不解析，只发一个 URL 和一个库名。`POST /api/ingest/enqueue` 的全部能力就是往 `queue.jsonl` 追加一行；它不 import `subprocess`、不碰 `pipeline.py`、不调 `task_manager.create_job()`，有测试盯着这条边界。**没有 auth token 是明确的决策**，安全性靠的是这个端点的爆炸半径，不是认证。
>
> **⑥ 从技能层把事故关掉。** 重写了 `wiki_ingest/SKILL.md` 的 PDF 分支——原来的 MUST 步骤写着 *MinerU 优先 → Native Vision 回退 → 本地 OCR 只在"用户明确要求"时*，而**无人值守的 agent 没有用户可以提出要求，所以它永远够不着便宜那条路**。所有技能的工具映射表加了 **ask-user** 这一行：此前只有 read-file / sub-agent / shell / web-search，**没有提问原语，所以沉默是结构性的，不是疏忽**。技能改成语义软路由（描述能力，不写死宿主工具名），所有问题汇总到主 agent。radar accept 卡片正文从祈使句改成一条可以直接跑的命令。
>
> **⑦ 安装：一条命令，装和升都归它。** `pipx upgrade --install magi-research` —— 在隔离的 `PIPX_HOME` 里实测：没装就装，装了就升，已经最新就什么都不做；而裸 `pipx upgrade` 在没装时直接报错。pipx 全面提到前面，uv 降为备选（没有 Python 3.10+ 时用，它自带 3.12）。doctor 加了 `pipx` 行——此前这个问题只在 "uv: not installed" 那行里顺带回答。
>
> **⑧ 文献雷达和任务待办变成可以关掉的功能。** `magi setup` 先问 MAGI 自己的功能、再问外部工具，因为**只有前者是它能动手的**：雷达是纯 MAGI，任务待办要 `bd` 而 setup 自己会装。默认全开，且**没有记录 = 开**——升级上来的用户不能因为版本号变了就丢掉天天在用的面板；旧的 `profile: kb-only` 依然优先。**关掉的功能不是故障**：它在同步率里不占权重（关掉任务待办让一个测试工作区从 57.6% 升到 86.3%，而不是永远封顶在三分之二）。WebUI 里对应面板变灰、保留标签页、顶上一张卡说明它是什么、打开能得到什么、已有数据不会被删。
>
> **⑨ 「一键安装」只在诚实的地方给。** MAGI 真正能自己装的只有 `bd`。Ollama / Pandoc / Poppler / LaTeX 是别人的安装器，MinerU 是在线服务——所以这些行只给官网链接和「我装好了，重新检测」，**不给一个点了会开浏览器的"安装"按钮**。Ollama 装好之后才出现「拉取 Ollama 模型」，因为那一件 MAGI 确实能做。
>
> **⑩ WebUI 全页复查，抓到的两个是真 bug，不是措辞问题。**
> - **`ReferenceError: on is not defined` —— 整个仪表盘是死的。** 我自己写了四次 `on(el, "click", …)`，而这个代码库里根本没有这个 helper（其余 84 处全是 `addEventListener`）。语法合法，`node --check` 绿，692 个 Python 测试全绿（没有一个执行 JavaScript），**而页面打不开**。这是同一个文件第二次栽在"语法对、跑不起来"上。加了 `tests/app_js_smoke.js`：在 Node 里用桩 DOM 真加载一遍，再加一个测试**把这个 bug 重新注入**，确认 `node --check` 依然放行而冒烟测试当场拦下。
> - **任务面板显示 0，而它正上方的核心卡写着 17。** `bd status --json` 的字段叫 `ready_issues`，`sync.py` 把它改名成 `ready`，而面板拿改名后的名字去读原始 payload——四个数全是 `undefined`，`|| 0` 把它变成一个自信的零。归一化下沉到 API，并加了静态守卫：app.js 第三次伸手去拿 `pm.summary.ready` 会直接构建失败。
> - 检索「Found 10 hit(s)」却不说**当前工作区根本没被搜**（响应里 `kbs_skipped: ["local"]` 一直都在，面板从来没显示过）；Doctor 报的是服务进程 cwd 那个工作区、不是顶栏点名的那个；同一个 op 在两个页面挂着两个不同的作用域词。
>
> **⑪ 两个我自己制造又抓回来的坑，都补了守卫。** 重复的 JS 对象键（`radar_settings_title`）静默覆盖了一个全局标题——**重复键在 JS 里完全合法**，而现有的对称性测试比的是集合，`{"a","a"} == {"a"}` 干净通过；新测试改成计数，并且我注入过一个重复键看着它失败。`FeatureRequest` 定义在 `create_app()` 内部——`from __future__ import annotations` 让注解变成字符串，FastAPI 拿**模块**全局去解析，于是 POST body 静默降级成 query 参数。
>
> **测试 302 → 730。** 未做/已知：`radar-stress-ws` 还留在注册表里；rung 2 的 pandoc 成功率只在两篇老论文上试过（都暴露了缺陷），完整样本等 rung 1 上线后看 rung 2 真实流量再说；pre-2000 的原生 HTML 桶和非物理学科桶没取到样。
>
> 2026-08-21 pipx 与 uv 并列，且 uv 不再是必需项 (v1.10.3)：用户问「现在 uv 是我们的必须项吗？只用 pipx 可以装吗？可以的话就用 pipx 分发」。
>
> **查证结果：uv 从来就不是运行时依赖——代码里没有任何一处执行它。** 它只出现在三个地方：安装说明、几条"重装/升级"的错误提示文案、以及 doctor 的一行。**pipx 实测可用**：用隔离的 `PIPX_HOME` 装了一遍 `magi-research 1.10.2`（系统 Python 3.10.11），CLI 正常，而且关键的那一环也过了——`sqlite-vec v0.1.9` 能加载、`vec0` 虚拟表能建，也就是**向量检索在 pipx + 系统 Python 下完整可用**（这原本是唯一的风险点：pipx 用系统 Python，而 macOS 的系统 Python 常常不支持加载 sqlite 扩展）。测完即卸，没碰用户的现有安装。
>
> 两个 README 与两份手册的安装章都改成 **pipx 在前、uv 在后**，并说清怎么选：机器上已有 Python 3.10+ 就用 pipx；不想操心 Python 就用 uv（它自带 3.12）。
>
> **顺带修掉一个由这次改动直接引出的矛盾**：`doctor_rows` 把 `uv` 当成受检工具，没装就是红色 `[-]`。既然现在推荐 pipx，一个纯 pipx 用户打开 doctor 会被告知自己的环境缺东西——而实际上什么都不缺。改成永远绿色，文案说明它只是个安装器：`not installed — only ever used to install magi (pipx works too)`。用 monkeypatch 模拟无 uv 的机器验证过。

>
> 2026-08-21 相关度下限的真实基线、图谱可读性、输出瘦身、手册重写 (v1.10.2)：用户「向量那个用真实场景做基线，防重叠要做，瘦身要做，后面也都做。全面检查不要引入新bug，文档和readme同步改。特别是给人读的那个文档，之前写得太细碎了，每个场景重点不突出，不像是给人看的像是给机器看的。先把高频重点、最省心的操作交代清楚。」
>
> **① 相关度下限：基线做完之后决定不做。** 先在真实的 mature 库（1371 段）上用 7 条好查询 + 5 条垃圾查询量了一轮，**分得干干净净**：真实查询的最佳命中全部 ≤0.823，垃圾全部 ≥0.883，中间有 0.06 的空档——看上去在 0.85 卡一刀就行。**把基线扩到 40 条真实查询之后这个空档没了**：真实那边最差的是 `tensor network renormalization`（0.912）、`Importance in Physical Theories`（0.880，**这是本库自己的一个小标题**）、`spin liquid`（0.852）；垃圾那边最好的是 `🙂🙂🙂`（0.843）。**重叠 −0.070，不存在能把两者分开的阈值**。任何能拦住垃圾的线，同时会砍掉那些"还不熟悉这个库的词汇、所以问得很宽"的真实查询——而那恰恰是最需要检索帮忙的时候。所以**不上过滤器**，改成**把远近显示出来**：每条向量命中带 `distance` 和 `closeness`（高度契合/相关/较远），整批都远时结果区直接说"这次查询没有语义上贴近的内容，下面只是相对最接近的"。与雷达那个分数得出的是同一个结论：在决策边界附近，这个数不够格拿来卡线，但够格拿来看。基线全文留在 `C:\Users\Jerry\.claude\jobs\6d94bc3e\tmp\vector_baseline.md`。
>
> **② 图谱**：加了图例（概念/文献/专题/论点/断言/断链/标签 + "点越大 = 连接越多"），颜色直接取自画布用的同一份色表，所以不可能和实际画出来的东西对不上；标签改成**按度数从高到低排、盖住已画标签的就跳过**——此前最密的区域（也就是最重要的那片）标签会叠成一坨糊掉，而那正是最需要看清的地方。悬停的邻域永远优先画。
>
> **③ `magi stats wiki-summary` 瘦身**：默认从 **759 行**降到 **9 行**——卡片数、按目录分布、wikilink 总数与密度、以及没有 `sources:` 的那几个文件（直接点名，最多 10 个）。完整的 per-file 数组挪到 `--json`。此前它把整个数组灌进 WebUI 的终端，人想看的那六个数字瞬间被冲到屏幕外。
>
> **④ 剩下那几件**：工作区选择改成 **per-tab**（`sessionStorage`，用 `localStorage` 里的上次选择做种子）——徽章的 tooltip 一直说这是"会话级"选择，实际却是全局共享的，开第二个标签页会静默继承第一个的选择；卡片预览的 **Links 按钮**改成滚到卡片自己的链接区（那份链接本来就在侧栏里），不再关掉预览跳去另一个标签页把阅读位置和下钻栈全丢掉——没有本地图谱的跨库卡片仍然回退到图谱页。
>
> **⑤ 全面回归检查，抓到三个真 bug——其中两个是我自己刚引入的。** 都是同一个坏习惯：插入一个新 helper 之后做全局字符串替换，结果把 helper **自己体内**的那次调用也替掉了，变成无限递归。`renderGraphMapChrome()` 调自己（图谱标签页直接 `Maximum call stack size exceeded`，图例空白），`viewWorkspaceGet()` 调自己（`loadInitialStatus` 整个炸掉 → 同步率显示 `--%`、三核全是"未连接"，而下面的面板却有真实数据）。`node --check` 对这两个都是绿的——语法没错，是逻辑错。补了一个自递归扫描器过了一遍 app.js，确认只有这两处（`renderBgPicker` 从点击回调里重画自己，是有意的）。第三个是真实世界的产物：**`fresh` 工作区里有一个 4096 字节、零对象的 `index.db`**，是被打断的 `magi index` 留下的（SQLite 连接时就建文件，表要到第一次 commit 才落盘）。它看上去是个健康的索引，直到第一次查询——而检索是联邦的，**registry 里有这么一个文件，全机器所有库的检索都会挂**，报一句生的 `no such table: chunks_fts`。`open_db` 现在把"有文件但没有 `chunks` 表"当成"没有索引"，走调用方已有的跳过分支。加了回归测试。
>
> **⑥ 手册重写：每一章都从"你实际要敲的那条命令"开头。** 用户的原话是"每个场景重点不突出，像是给机器看的"。证据在 `magi guide` 自己的章节预览里——它取每章第一句，而那第一句以前是：graph「每个视图都支持 `--limit N` 和 `--json`」、search「索引覆盖 wiki/、raw/、drafts/ 下所有 .md，按一到三级标题切块」、ingest「需要指定页码、强制某条路线、或者对付难搞的扫描件时……」。**全是细节、开关和例外，没有一个是"这一章你主要干什么"**。12 章全部重开头（中英各一遍），格式统一成：一句话说清是几条命令 → 命令块 → "下面是……"。现在的目录长这样：安装「安装就一条命令」、摄入「摄入就一条命令」、编译「编译是唯一没有命令的一步——你对 agent 说」、检索「检索是两条命令」、雷达「设一次，之后每周分流」、疑难「两条命令能解决大部分问题」。ingest 那章尤其典型：以前要先读完一张四行的路线对比表，才轮到「不想选？用 `magi ingest auto`」——而 auto 就是绝大多数人的答案，现在它在最前面。两个 README 也加了 **Start here** 块：`uv tool install` 从第 116 行提到第 22 行，四条命令 + 一句给 agent 的话就能跑通。
>
> 测试 301 → **302**。注意：全量 `pytest tests/` 在这台机器上会被 OpenBLAS 的分配失败直接 abort（进程死掉、没有 traceback、没有汇总行）——那是内存压力，不是测试失败；按文件逐个跑全部通过。

>
> 2026-08-20 WebUI 人类模拟压测 (v1.10.1)：用户「对 webui 其他功能也做这种端到端真实压测，模拟人类用户，看看哪里会让人觉得 confuse / 重点不突出」。**造了三档成熟度的真实场景**：`fresh`（刚 `magi init` 出来、彻底空的）、`mature`（真实库的副本：100 concepts / 19 references / 图谱已建 / 1371 段全部向量化）、`radar-stress-ws`（67 references、零 concepts 的半成品），从 hub 根起一个服务，配置目录隔离到独立 `MAGI_CONFIG_HOME`，全程没碰用户真实数据。10 个维度 × 64 个 agent（三个"人格"任务：新手带着 20 篇 PDF 从零上手、老用户日常一轮、踩坑用户找回路径；外加逐面板与跨面板审计），53 条上报、**38 条通过对抗式复核**。
>
> **① 头号问题：工作区下拉框会说谎。** 从 hub 根启动时服务端没有 active workspace，`renderWorkspaceSelect()` 里 `els.workspaceSelect.value || state.workspace` 让空的 select 落到字母序第一个选项上，而后面每一次取数用的都是真正的 `state.workspace`——于是**下拉框显示的库和屏幕上所有数字属于的库不是同一个**。而专门为了暴露这种分歧而做的 `#browsing-badge`，判据是 `state.workspace !== state.serverWorkspace`，在 hub 根启动时 `serverWorkspace` 是 null，**永远不会亮**。这不是众多 bug 里的一个，是"页面上任何数字都不能信"的原因。改：`state.workspace` 优先于 DOM 值；`loadInitialStatus` 里工作区确定之后再渲染一次下拉框；badge 判据改成"服务端没有 active workspace = 一直在浏览别人"。
>
> **② 空 ≠ 坏。** 一个刚建了九十秒的工作区，三核状态是 Melchior「需要注意」、Balthasar「需要注意」、Casper「**故障**」——什么都没坏，用户只是还没开始。新人打开就是一片红黄，先被告知自己装坏了。新增 `state-new` 状态（「尚未设置」，中性灰点），用于 empty-wiki / 未初始化 beads / 未建索引三处。**同一个问题的另一面**：`claimsData.total ? … : 100` 让零断言的工作区显示「100% verified」——空的东西不该报满分，改成「还没有断言」。
>
> **③ 同步率用行话解释行话。** `Sync: 33.3%` 挂在每一个屏幕的顶栏，唯一的 tooltip 是「Three-core sync ratio (Melchior + Balthasar + Casper)」——把缩写展开了一遍，没说这个百分比是**什么的**百分比、怎么才能涨、33.3% 算不算糟。而且 tooltip 挂在小药丸上，旁边那条**全宽的** THREE-CORE SYNC 长条反而什么都没有。现在 tooltip 讲人话（"工作区就绪度：知识/任务/检索三块的加权平均，把上面标记的项处理掉就会涨"），并且挂到了那个大的元素上——最需要解释的数字应该由最显眼的元素带解释。
>
> **④ 最该点的那一步没有按钮。** 「Suggested Actions」卡片副标题写着「click to run」，三行里两行有 Open/Run，而**第一行——"把 PDF 丢进 inbox/ 然后跑 wiki_ingest 技能"，也就是新用户唯一真正要做的第一件事——是唯一没有任何控件的那行**（`HINT_ACTIONS['ingest-start'].action` 写死 `null`）。它是个 agent 技能步骤、不是 job，所以现在给它一个「怎么做」按钮跳到手册对应章节；`beads-missing` 同理。
>
> **⑤ 任务追踪的启动路径整条是断的（三条 finding 一个根因）。** Balthasar 空状态横幅写着「点击下方初始化任务工作流」——**下方没有任何可点的东西**，真正的入口在另一个标签页且从未被提及；而那个入口 `pm-init` 待在**危险区**里，和 `migrate`、`setup --remove-legacy` 共用"输入操作 ID 二次确认"的仪式——可它是 additive 且幂等的（`cmd_init` 见到 `.beads/metadata.json` 就直接 no-op，已核实），还是 Dashboard 建议新用户做的第二步。三处一起修：`pm-init` 移出危险区；横幅自带按钮就地执行；文案改成「这一步是可选的——不想用任务追踪就不必初始化」（**它本来就是可选的，而产品的核心指标却把不用它当成永久扣分**：一个 99 concepts、1371 段全向量化的成熟库照样只有 66.7%，`magi setup --kb-only` 能把 Balthasar 整个摘出比例，但 WebUI 里从来没提过）。
>
> **⑥ 「自动滚动」在运维页什么也不做，跑完的任务看起来像卡死。** `styles.css` 里 `#tab-operations .terminal-body { max-height: none }` 覆盖掉了可滚动规则，元素没有内部溢出，于是默认勾着的自动滚动**无处可滚**——任务输出落在视口下方一万多像素处，而可见的那块永远停在「Connecting to log stream…」。改回可滚动（这一页留高一点，55vh）。
>
> **⑦ 频率与重量不匹配**（用户点名的那类）：知识库表格每一行结尾都是 `[切换] [移除]`，而**移除是 `btn-danger` 红色**、切换是次要按钮——切换是天天做的，移除几乎不做，红的却是罕见且不可逆的那个，每一行都红一次；改成安静按钮。首屏第一个指标位是「REGISTERED KBS 3 / 全局知识联合」——一个数配置文件条目数的计数，配一句没人天生认识的行话；改成「知识库 / 本机可检索的库，当前正在看的那个见顶栏」。「Pending Digests」在新用户还没见过"简报"这个词的时候就出现了 → 「待分流文献」。「Active Task State: 0 ready」把值和单位焊在一起而所有兄弟格子都是裸数字 → 标签改成「可开始的任务」、值就是数字。副标题「全局注册表位于 ~/.config/magi/registry.json」——GUI 里摆文件系统路径，占的是本该说明这张表是干什么的那一行。
>
> **⑧ 其余死路与泄漏**：Melchior 图谱缺失时把后端原句（带 `D:\...\graph.db` 路径和 `Run 'magi graph build' first`）当成呆文本显示，而**同一个条件在 Dashboard 上是有 Run 按钮的**——同一个事实两套界面，现在也给按钮；顶栏「Running Jobs」药丸只在开机时写一次、之后永不更新（开机后启动的任务整个运行期间在顶栏都是隐形的），也不可点、也没说清是哪个工作区的——改成随任务启停实时更新、可点击跳到日志、tooltip 说明是本机全部工作区；切换工作区时 Casper 的检索结果不会清空，上方状态条已经翻成"没有索引"而下方还挂着上一个库的完整评分结果——现在切换时清掉检索结果与打开的卡片预览；用户主动选了"纯关键词"模式，界面却还是弹「语义检索未启用：需要本机 Ollama 模型…」这种排障文案——现在区分"你自己选的"和"坏了"；检索结果上的 `RRF 0.029 / BM25 #1 / Vec #12` 三个徽章全无解释，加了 tooltip；`opt_scope_auto` 的「联邦检索（本库 + 启用的注册库）」一句话三个行话 → 「本库 + 其它已启用的库」。
>
> **刻意没在这一版做的**（都写进了简报的风险项）：向量检索的相关度下限（会影响真实查询的结果数，需要先拿 mature 库做基线）、图谱 map 的图例与标签防重叠（工作量更大）、`magi stats` 输出瘦身（要改 CLI）、`localStorage` → `sessionStorage`（行为变更）、卡片预览「Links view」的返回栈。测试 301 项全绿（两条断言 `pm-init` 属于危险区的测试按新意图改写：危险区只放会破坏或重构的操作，把必做的首次设置放进去，等于把用户的警惕心花在错的地方，久了他们就不看那个弹窗了）。
>
> 压测场景留在 `D:\AI_Playground\ui-stress-hub`（mature + fresh 两个 topic、独立配置目录），随时可以再起服务复跑。
>
> 2026-08-20 文献雷达压测 (v1.10.0)：用户要求「用 homepage 里的论文单独建一个工作区，从头真实模拟使用场景，测试所有功能」，并追加「webui 上不方便操作的、按钮设计重点不突出的也要一起优化」。**建了真库**：从叶鹏组主页抓下全部 **67 篇**论文，逐篇从 arXiv API 取回真实摘要（67/67），写成 reference 卡，`magi index` 建索引（**268/268 chunk 全部向量化**），radar 分类按该组实际投稿分布配置（42 篇 cond-mat.str-el、11 quant-ph、4 mes-hall、3 hep-th）。然后真跑：**harvest 拿到 40 个候选**（S2 推荐 20 + arXiv 新文 20，字段无一残缺），**citation-gap 跑完四层漏斗**拿到 1 条。8 维度 × 41 个 agent 的对抗式审计：32 条上报、**26 条通过复核**。
>
> **① 最严重的一条是静默降级：定时扫描一直在用错的配置。** `cmd_harvest` 用 `load_config()` 取配置——而它是**从进程 cwd 往上找** `config.yaml` 的，跟 `--topic-dir` 毫无关系。而 `install-schedule` 注册的正是 `magi radar harvest --topic-dir <ws>`，**三个平台都没设工作目录**：Windows 计划任务从 `System32` 起、launchd 从 `/` 起、cron 从 `$HOME` 起。于是每晚的自动扫描找不到任何 config，退回 `_DEFAULTS`——而 `_DEFAULTS` **根本没有 radar 段**，`arxiv_categories` 是 `None`。**整个 arXiv 新文那一半被无声丢掉**，但digest 照样生成（S2 推荐那半还在，因为种子是从 `--topic-dir` 的库里读的），看上去一切正常。修法是给 `load_config` 加 `start=` 参数（`find_config_yaml` 本来就支持），radar 四个子命令全部改成 `load_config(start=topic)`；再给三个平台的计划任务都补上工作目录（Windows 用 `cmd /c cd /d`、launchd 加 `WorkingDirectory`、cron 加 `cd`——顺带修好了 crontab 那行一直忽略 `--time` 永远写 3 点的老毛病）。另外 config 解析失败此前被 `except Exception: pass` 整个吞掉，一个 YAML 手误就等于"今天没扫到东西"且 exit 0——现在会 warning。
>
> **② 相关度分数不是坏，是量程用错了地方。** 实测这套 cosine-vs-质心 的真实标尺：核心话题 0.75、**40 个候选全在 0.55–0.70**、普通凝聚态论文 0.45、机器学习论文 0.37、**随机字符 0.315**、菜谱 0.117。估计器本身没问题（物理 vs 非物理分得很开），问题是**能进 digest 的候选本来就已经被 arXiv 分类和自家种子筛过一遍**，全都落在量程最顶端那 20%，分辨率最低的地方——最好和最差只差 0.147。于是 `radar_review` 技能里写的「低于 ~0.3 通常是噪声」**比随机字符还低**，永远不会触发；手册示例 `min_relevance: 0.35` 同理，照着配等于没配。技能与中英手册全部按实测重写：**当排名读，不当概率读**，`min_relevance` 只是防"分类填错把别的领域拉进来"的底线（0.50 左右），不是精度旋钮。界面里也不再裸显 `[0.697]`，改成同批内部的**高相关/中等/偏低**三档，原始余弦放悬停提示。域内 agent 独立盲评 40 篇后比对：2 篇明显跑题的（moiré-Hofstadter 能带、自旋链可积性 no-go）分数高于中位数，3 篇明显对口的（非厄米体边对应、拓扑码解码器、DQCP 自旋子）低于中位数——**极端有效、中段是噪声**，与实测量程一致。
>
> **③ arXiv 那一半的预留被排序抵消了。** `cmd_harvest` 注释写着"留一半预算给 arXiv 新文，免得被 S2 推荐挤掉"，但预留发生在**抓取时**，抓完合并后按分数排序再截断——真实一轮下来 **top10 里 9 个是 S2**。改成 `_apply_budget()`：截断时按来源各留一半，谁有富余给谁，组内仍按分数排。
>
> **其余修的**：质心改成**每篇论文一个向量**再平均（原本按 chunk 平均，长论文靠篇幅超权），并去掉 `LIMIT 400` 无 `ORDER BY` 的静默截断（合成语料上实测会整整漏掉 32% 的论文且毫无日志）——在真实语料上 `cosine(新旧质心)=1.000000`，无回归；`--days 0` 此前被 `args.days or ...` 当成未设置；`max_candidates: 0` 此前照样发一次 S2 请求和每个分类一轮 arXiv 才把结果全丢掉，现在直接短路；`--topic-dir` 此前完全不校验（不存在的路径会被凭空造出 `output/radar/` 然后报成功，指向文件则抛裸 traceback）；S2 摘要没做空白归一（arXiv 那边一直有），摘要里一个换行加一行像 `- id:` 的文本就能在 digest 里伪造出一个候选并顶掉真 id；id 里的反引号会截断（S2 没有 arXiv id 时回退 DOI，而 DOI 是自由格式）；空标题；`status: pending-review` 此前是**全文**子串匹配，正文里的摘要引用到这句就会被改写而真正的 frontmatter 一直 pending——改成只认 frontmatter（兼容 CRLF）；ledger 与 candidates.jsonl 的写入顺序对调（先写 ledger，否则中途失败会留下"已收割但未标记已见"的候选，之后每轮都重复推送）；`citation-gaps.jsonl` 此前无条件覆写而 `.md` 只在有结果时才写，一轮空跑就会把上一轮的结果抹掉只留下一份描述着不存在结果的报告。**citation-gap 的两处误导**：S2 返回 **429** 之后紧跟着打印"该论文在 S2 上还没有引用数据"——把限流说成了关于论文的事实，现在分开报；以及先说"scanning 30 neighbors"然后数到 `20/20` 就停——那是个没写在任何地方的内部预算，10 个邻居根本没被检查过，现在按"N 个邻居 → M 个合格 → 检查 K 个（预算所限，X 个未检查）"如实报。`own_arxiv_ids` 未设时会静默回退到 `seed_arxiv_ids`，而种子往往是**别人**的论文，报告却管它叫"我方论文"并问谁没引用它——现在会明说。
>
> **④ WebUI：分流列表一直存在，只是够不着。** 实测真实的 40 候选 digest：viewer 滚动高度 **12 813px**，可视区 714px——**17.9 屏**；而"候选操作"那块从 **10 162px（79%）**才开始，**要滚 14 屏**。它是同样 40 篇论文的**第二份列表**：上面那份 markdown 每篇占约 230px（H2 标题 + 5 行元数据 + 两条裸 URL + 摘要），一屏只放得下 1.5 篇。**判断所需的信息在顶部，操作所需的按钮在底部，两边永远碰不上**——而这就是每周要做的那件事本身。列表本身其实做得不错（紧凑行、分数前缀、作者行、可用的筛选框），纯粹是位置问题。改成**分流列表在最前**，每行自带摘要（两行截断、点开展开）、标题直接链到 arXiv、分数变成三档 chip；渲染后的 digest 收进折叠的"查看原始简报"。**第一个可交互元素从 10 162px 变成 188px。**
>
> 还有 **没有"跳过"**：只有 accept 和 create-task，而分流最常见的结果——"不相关"——没有任何按钮，40 篇里只能记下留用的那五篇，其余三十五个决定全在脑子里，关掉标签页就没了。新增 `dismiss`/`reset` 动作，决定落盘到 `output/radar/triage.jsonl`（accept 和 create-task 也一并记），刷新后完整恢复，配"已处理 N/M"进度与"隐藏已处理"。**citation-gap 报告此前一个候选操作都没有**（`kind === "digest"` 的前端闸门），而后端一直支持——那可以说是整个功能最有价值的产物，界面上却只给了一个"标记已审阅"；现在两种报告走同一套。为此让 citation-gap 的写入也发 `- id:` 行，并让解析器兼容旧格式的 `- candidate: … arXiv:xxx`。
>
> **按钮层级**（用户点名的那条）：**「安装/卸载定时扫描」此前在危险区**——它可逆、幂等、不碰任何数据，却和 `migrate`、`setup --remove-legacy` 共用同一个"输入操作 ID 二次确认"的模态框，而且在另一个标签页、从雷达面板完全够不到，`danger` 改成 `False`；**「运行文献雷达扫描」此前会把你踢出雷达标签页**（`launchJob` 结尾 `switchTab("operations")`），面板自己的主操作导航离开自己的面板，任务跑完还得再点回来看结果——加了 `stay` 选项，并在任务结束时刷新面板;**「已跟踪文献记录 40」占着第一个指标位**——一个只增不减、没有任何动作的累计计数，而"上次扫描是什么时候、是不是该扫了"却哪儿都没有：新增 `last_harvest`/`harvest_age_days`（从 ledger 的 `first_seen` 推，无新状态），超期时变琥珀色，并加了 `radar-harvest-overdue` 的 sync hint（与 `graph-stale`/`index-stale` 同款）；**「待审阅简报 2」数的是文件**，改成数**论文**（"37 篇待分流 · 分布在 2 份简报中"）；**雷达配置此前在 Dashboard 标签页**，在雷达面板上发现阈值不对却没有任何就地入口——`loadConfigCard(box, only)` 加了过滤，六个 `radar.*` 字段搬到雷达面板的折叠设置区，其余留在 Dashboard。**accept-to-inbox 给错了链接**：卡片正文写着"去下载 PDF"，给的却是 Semantic Scholar 落地页，而 arXiv id 就在同一份 frontmatter 里——改成有 arXiv id 就优先给 arXiv。
>
> 新增 `tests/test_radar_contracts.py` 18 项（配置解析跟随 `--topic-dir`、计划任务的工作目录、install-schedule 不再是危险操作、`--topic-dir` 校验、`max_candidates=0` 不发请求、`--days 0`、来源预算、digest 往返的四种畸形输入、frontmatter 状态、triage 记录与撤销、harvest 时效）。测试 283 → **301**。
>
> 压测工作区留在 `D:\AI_Playground
adar-stress-ws`（67 篇真实论文 + 索引 + 真实 harvest/citation-gap 产物），已从全局注册表注销以免污染仪表盘。
>
> 2026-08-20 性能：卡死的那三件事 (v1.9.3)：用户在做语义检索时被告知没有 Ollama，去运维点了「重建索引」，然后整个 WebUI 卡住。**三件事，互相独立，只有一件是它看上去的样子。**
>
> **① 仪表盘不是崩了，是每次都在等 `/api/kb`。** 该端点为每个注册库跑一遍 `build_report()`，而 `build_report → balthasar_status → bd_status_summary` 会 **spawn 一次 `bd status --json`**——Windows 上 ~330ms。六个库就是六次 spawn，而**一个 hub 下的所有课题共用同一个 beads 库**，六次问的是同一个问题。加上四次重复的 `wiki/` 全树 rglob（最新 mtime 一次、三个目录计数各一次），单次请求 **2.5 秒**，且在首屏路径上。改法：`bd_status_summary` 按 **beads 根**（不是按目录）做 2 秒 TTL 缓存，并用 per-key 锁把「查—没有—去跑」整段圈起来（否则并发的六个调用会一起 miss、一起 spawn，省不掉）；`bd_available` 的 `shutil.which` 用 `lru_cache` 钉死；`wiki/` 改成**走一遍拿全部答案**（`_scan_wiki` 返回最新 mtime + 各目录卡片数，melchior/casper 共用同一份）；`/api/kb` 的多库扇出改线程池并发。**2.5s → 0.17s。**
>
> **② `/api/status` 花 450ms 算一个恒为 True 的常量。** 它调 `doctor_rows()`（六个外部工具 `which` + 19 个技能 × 4 个 agent CLI × 2 个 scope 的安装态逐文件比对）**只为读其中两行**——而那两行在 `doctor_rows` 里就是写死的 `True`：进程能回这个请求，magi 和 Python 当然在。前端从来没读过这个字段。真正的体检在 `/api/doctor`，诊断面板按需拉。**0.45s → 0.007s。**
>
> **③ 索引不是挂了，是 22 分钟一声不吭。** `magi index` 的向量回填对**每个 chunk 单独发一次 HTTP**（旧的 `/api/embeddings`，一次一段），1371 段、**全程零输出**、**只在循环结束后 commit 一次**——中途取消，二十分钟全丢。而 Ollama 早就有 `/api/embed` 批量接口：实测同机 qwen3-embedding:0.6b，逐条 7.65s/段、批 8 是 2.11s/段、批 32 是 1.04s/段，**~7 倍**，开销几乎全在每请求的固定成本上。改成批量 + **每批 commit** + 限流的进度行（`index: backfill: 320/1371 chunks`）。批大小取 **16 而不是最快的 32**：批是服务端的内存乘数，跑到一半被 OOM 掉的代价远大于最后那 20% 吞吐（这不是假设——验证时 Ollama 就真的挂了一次）；`ollama.embed_batch` 可调。
>
> **顺着 ③ 挖出来的三个**：**(a) 自启只在开头跑过一次**——`_preflight` 每进程一次，所以 Ollama 中途死掉时后面几百段静默无向量。现在连接类失败会重跑一次 autostart 并重试一次。**(b) 但超时不能重试**：超时意味着服务在、只是忙，重试等于把上限等两遍——交互检索 8 秒的预算变成了 17 秒。加 `_wrap_transport` 区分「连接被拒」（值得重启重试）和「超时」（立刻放弃）。**(c) 中途失败此前完全静默**：`_disable` 只在 `available is None` 时说话，所以「跑着跑着挂了」这种最需要说清楚的情况反而一个字都没有，命令还 exit 0。现在分成两句话，跑挂了那句直接告诉你「已嵌入的都已提交，重跑 `magi index` 补剩下的」。
>
> **检索与索引抢同一个 Ollama。** Ollama 串行处理请求，所以索引任务在跑时，搜索框里的查询要排在它后面——实测 **7–33 秒**的假死，界面上只写「语义检索：未启用」，配的还是「去装 Ollama」这种当时毫无意义的提示。现在查询嵌入有 **8 秒上限**，超时就返回 BM25 那一半并带上 `vector_degraded`，界面据此说人话：「Ollama 没有及时响应，通常是索引任务占着它，等它跑完再搜一次」。另外查询用的 Embedder 改成**进程级共用**（此前每次搜索都新建一个、于是每次搜索前都要往 `/api/tags` 跑一趟预检），并给 `available=False` 加了 30 秒冷却后自动复活——`magi ui` 一开好几天，一次抖动就让向量检索到重启为止都不可用，这不对。
>
> **前端**：首屏此前打三次 `/api/kb`、两次 `/api/workspace/sync`（`loadInitialStatus` 和 `loadDashboard` 各来一遍）。加 `coalesce()`：并发的合并，且带一个 **1.5 秒**的落定窗口——两个调用是**先后**发生的，只合并并发的还是会漏掉第二次。它不是缓存：人能做的任何动作（点刷新、切走再切回来）都远超这个窗口，照常重新取；任何写操作直接 `invalidateCoalesced()` 作废。**8 次请求，首屏 169ms。**
> 任务终端此前每来一行日志就 `textContent +=` 重建一次整串（第 n 行的代价随 n 增长），紧接着读 `scrollHeight` 强制同步布局，而自动滚动**默认开着**；客户端还没有行数上限（服务端有 2000）。改成按帧攒批 flush，一帧一次 DOM 写、一次布局，并裁到和服务端一样的 2000 行；任务结束时 `settle()` 保证最后几行不会卡在帧之间。实测 768 行 / 22.5KB 流下来，**长任务 0 个**。
>
> **顺手修的两处数据风险**：`_persist_job` 的「追加，然后可能压缩」是个 read-modify-write，**没有锁**——两个任务同时结束时可以交错到第二次重写把第一次的记录吞掉（审计脚本在高并发下复现出记录全丢、文件塌成几个字节）。现在整段走专用写锁（不是 `_lock`，那把锁还管着 SSE 扇出，压在磁盘 I/O 上会拖住所有流式客户端），压缩写临时文件再 `os.replace`，读者要么看到旧文件要么看到新文件。SSE 每个监听者的队列此前**无上限**，后台标签页停止消费就会一直涨；现在封顶 2000 并**丢最旧的**——因为 `stream_logs` 等的那条终止状态消息永远是最新的那条，丢掉它连接就永远关不掉了。
>
> **还发现测试在往用户真实数据里写**：`ui-jobs.jsonl` 里躺着 **83 条 `pytest-of-Jerry/...` 的记录**。测试确实 monkeypatch 了 `MAGI_CONFIG_HOME`，但任务是在后台线程里结束并自己归档的，而 `_persist_job` 到那时才去解析配置目录——fixture 早已还原环境变量。现在**归档路径在 create_job 时就定死**在 Job 上；那条测试也补了 drain。已清掉 90KB → 9.4KB（保留 10 条真实记录）。顺带把历次测试自动注册进用户全局注册表的 6 个临时工作区注销掉（`magi index` 会自动注册，所以每个被索引过的一次性工作区都留在了用户的仪表盘上）。
>
> **其余**：`graph.db` 补上 `PRAGMA journal_mode=WAL`（`index.db` 一直有；默认回滚日志下建图会把所有读者挡住整场）；frontmatter 解析改用 `yaml.CSafeLoader`（PyYAML 的 `safe_load` 总是挑纯 Python 那个慢的，实测 **6.4×**，`find_uncompiled` 从 45–61ms 降到 22–31ms）；`--mode bm25` 不再加载 sqlite-vec（它背后拖着 numpy）；`magi index --quiet`。**`build_report` 单库 450ms → 41ms。**
>
> 排查过程中还在用户机器上找到一个**孤儿 `llama-server`**（父进程是那个已经死掉的 Ollama），占着 2.9GB 和 GPU 缓冲，导致新的模型加载直接 `cudaMalloc failed: out of memory`——**这才是「提示我没有 Ollama」的真正原因**：Ollama 进程活着、模型也拉了，但它加载不了。清掉之后单次嵌入从 7.65s 回到 0.24s。用户那个课题的索引已经补完：**vectors 1371/1371**，混合检索 0.7 秒返回、20 条向量命中。
>
> 派了 8 维度 × 28 个 agent 的性能审计（每条结论都要求附上自己量到的数字，再逐条对抗式复核）：19 条上报、**15 条通过复核**。刻意没做的两条：给每个面板加 TTL 缓存（缓存失效语义在补丁版里做容易出静默的错，留给功能版），以及把 `magi search` 的默认 `--scope` 从 auto 改成 local（那是行为变更，会打断依赖跨库检索的脚本）。测试 262 → 283。
>
> 2026-08-20 GitHub Release 自动化 + 文档同步锁 (v1.9.2)：用户「最近几次你都没发 github release…之前没发的补上」「新功能记得同步进各种文档」。**v1.8.0 / 1.8.1 / 1.8.2 / 1.9.0 / 1.9.1 五个 tag 只发了 PyPI、没有 GitHub Release**——对不盯 PyPI 的人等于不存在：没有 changelog、没有通知、没有可以引用的链接。五篇已补写发布说明。**根因是 workflow 里压根没有这一步**（test → build → publish 三个 job），现在加了 `github-release`：从 tag 的 annotation 取标题与正文（写 `git tag -a` 就等于写发布说明，单行 tag 回退到 commit body）、带上 wheel 与 sdist 作为附件、已存在则跳过（可重跑）。`docs/RELEASING.md` 据此改写，并把「装回本机要 pin 精确版本号」写进去——`--refresh` 有时仍会从索引缓存拿到上一版。**文档漂移改成 CI 拦**：新增 `tests/test_docs_in_sync.py`——两份 README 必须列全所有随包技能（它们承载完整技能表），两份手册**互相**列同一批（手册是按场景组织的，本就只挑一部分讲），两份手册覆盖 CLI 全部命令组，中英双向不许出现只有一边有的命令/技能，「共 N 个技能」这句话里的数字必须等于实际数量，以及反向：文档里不许留下已经不随包发布的技能。顺带把 v1.9.1 的新功能补进此前漏掉的地方：手册公式章整节重写（整库默认、`--json` 工单、`confidence` 两档的含义、「同一文件连续多条通常是同一个缺陷」那条 TIP、指向 `wiki_math_fix`），中英对齐；`wiki_ingest`/`wiki_ingest_ocr` 两个技能加了「批量摄入后别逐文件查，整库出工单」；工作区入场协议（`magi init` 写的 CLAUDE.md/AGENTS.md）加了同一条；`cli_i18n` 与 `cli.py` 里 `math format`/`math check` 的一句话描述改成整库语义。**发出去当场发现的坑**：tag message 默认 `--cleanup=strip`，会把所有以 `#` 开头的行当注释删掉——v1.9.2 自己的三个 `###` 小标题就这么无声消失了。已补回发布页，`RELEASING.md` 把 `--cleanup=verbatim` 写成硬要求，workflow 里也加了一条 notice 提醒。测试 250 → 262。
>
> 2026-08-20 公式修复清单 + wiki_math_fix (v1.9.1)：用户：「加一个快速处理摄入的公式语法格式不对的skill…全部抓出来然后一个一个处理…类似lint一样是全局处理」。**`magi math check` 与 `magi math format` 都改成整库默认**（`target` 变可选、缺省取所在工作区，与 `lint`/`index` 一致），范围收到 `wiki/ raw/ drafts/`（`magi.core.wiki_common.corpus_files`，与检索索引同一套定义）——此前 format 会连 `scratch/concept_backups/` 一起改写，那正是修坏了要拿回来的副本。`math check --json` 输出**可寻址的工单**：每条一个公式，带 `id`（`路径:行`，可勾掉）、行范围、`kind`、`error`、**原始 TeX**（超长截断并标 `tex_clipped`）、`collection`，以及 `confidence`——`likely-macro` 表示 pdflatex 不认得这个宏，十有八九是它没加载的宏包而不是错字，照着改会把对的公式改坏。**新增第三个探测器**：pylatexenc 和 pdflatex 都看不见最常见的那种损坏——`$$` 少了闭合符，把后面一整段散文吞进公式里，而散文在 LaTeX 眼里是合法的（单词就是字母序列），所以它躲过了此前所有检查、然后在页面上渲染成一大片斜体单字母。判据是公式永远不会有的东西：一串不带任何数学记号的普通单词。在真实库的 8 208 个行间公式上量过——**7 999 个的最长纯词串是 0**，尾巴全是「Proof. We replace the ground field with its algebraic closure」这种；阈值取 6，避开了「最长 1 个词」那 113 个（`where` 之类的连接词），命中 1.4%。实测用户三个课题：Defect 的 `raw/` 有 128 条（其中 115 条正是被吞掉的散文），另外两个课题的 `wiki/` 干净。**新技能 `wiki_math_fix`**（18 → 19 个）把这张单子交给 agent 逐条处理：先跑确定性的 `math format`，再按 `wiki/` 优先的顺序读原文、必要时 `magi ingest crop` 对着源 PDF 核对、改完单文件复验。技能里写死了两条判断：**别改看不懂的宏**（`likely-macro`），以及**同一文件里连续多条通常是同一个缺陷**——`$$` 是顺序配对的，少一个闭合符会让后面每一对都错位并各报一条，所以修第一条再复验，115 条常常塌成十几处真实改动，绝不能自底向上改。`magi lint` 发现公式问题时也会指向这条路（它报得出、修不了）。测试 231 → 250。
>
> 2026-08-20 看得见内容 + Ollama 自启 (v1.9.0)：两件用户直接点名的事。**① Ollama 不用手动开了**——新模块 `core/ollama.py`（`probe`/`start`/`ensure`/`ensure_model`/`hint`）：本机 Ollama 只是没启动就直接拉起来（Windows 用 `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`，服务器活得比命令久；`base_url` 非默认端口时把 `OLLAMA_HOST` 一并传进去），**每进程只试一次**（否则每个向量调用点都要赔上一次 spawn + 连接超时），远端地址不试（起本机守护进程救不了远端）。真正需要人管的只有两件：没装、模型没拉——这两条才打印，且 hint 直接给出 `ollama pull <model>`。模型匹配是**精确**的（裸名视作 `:latest`），因为 `/api/embeddings` 对没有的 tag 直接 404，"差不多"只会把失败推后。接线：`retrieval.Embedder._preflight`、`kb/semantic_link.check_model_available`、`ingest/ocr/ocr_engine.check_model_available`、`setup_ollama_models`；`magi doctor` 的 ollama 行从"二进制在哪"改成报**服务端状态**（停着 / 起着但模型没拉 / 就绪）。开关：`ollama.autostart`（默认 true）与 `MAGI_NO_OLLAMA_AUTOSTART`。**② 图谱和检索现在能看到内容**——此前点节点只能跳到它的链接表，检索结果只有一段掐头去尾的 snippet，**卡片正文根本没有入口**（用户："我只能看图谱但是看不到内容"）。新增卡片预览：`GET /api/workspace/doc`（`path=` 或 `node=`，外加 `workspace=` 或 `kb=`）与 `GET /api/workspace/asset`（卡片里的插图）；所有路径经 `_safe_workspace_file` 一道门（拒绝 `..`、绝对路径、前导斜杠、非文本后缀，2MB 截断）。`graph_browse.resolve_node_id` 复刻建图时的解析规则（id / 标题 / 文件名 / 别名四选一），否则卡片里一半的 `[[链接]]` 会被当成断链。前端：**先把数学从 markdown 里摘出来**再交给 marked（否则 `a_1 \ldots b_2` 会被读成斜体），KaTeX 渲染（`\label`/`\nonumber` 剥掉、`eqnarray` 就地改写成 `aligned`，KaTeX 不认它）；`[[wikilink]]` 变成可点的链，图片走 asset 端点（markdown 里的路径本身是百分号编码的，再编一次会变成 `%2520`）；```mermaid 围栏由**懒加载**的 mermaid 画成图（2.7MB，只有真有图的卡片才付这个钱；折叠在 `<details>` 里的等展开再画，否则零宽度布局），图固定用浅色主题并坐在浅色板上——论文自带的 `style A fill:#f9f` 遇上深色主题会变成浅字压浅底。侧栏是**目录大纲 + 图谱出入链**（滚动高亮当前节；跨库卡片没有本库图谱，就只剩目录，且整条侧栏收起）。**检索结果直接落到命中段落**：渲染时按 token 逐块给每个顶层元素盖 `data-src-line`（`$$` 折成占位符会吃掉行数，得补回来；front matter 不参与渲染但参与行号），点卡片就滚到那一段并高亮，实测 281→281、47→47。检索是联邦的，所以预览也跨库（`kb=` 经注册表解析路径，浏览器不碰文件系统布局）。**排版**：预览正文钉死一套衬线（`--font-reading`），**不随主题变**——MAGI 模式把 markdown 标题设成等宽，一页公式加散文用等宽读不下去（用户："markdown正文预览还是用有衬线字体…颜色可以和主题挂钩，字体就不要挂钩了"）；选择器写成三个类才压得过 `[data-theme="eva"] .markdown-body h1` 的 (0,2,1)。HTML 一律转义，只放行**不带属性**的 `<details>/<summary>/<br>/<sub>/<sup>` 等结构标签（属性正是事件处理器藏身的地方）。**公式按需排版**——一篇 764KB 的论文有近五千个公式，全排一遍是 15MB DOM、开卡片要 13 秒；现在占位符自带 TeX 源码（大小差不多，排不到也还能读），只排视口附近的（±1500px），滚动时补排：**1.08 秒、1.5MB**，落点仍然精确（第 5028 行→第 5028 行）；小于 400 个公式的普通卡片仍旧一次排完，不闪。刻意**没用 IntersectionObserver**——它只在标签页正在渲染时才回调，后台标签页里打开的预览会永远停在原始 TeX。vendored：katex.min.js + 精简到 woff2 的 20 个字体（woff/ttf 剥掉）+ mermaid.min.js。**发布前用真实文献库跑了一轮多 agent 审计**（四路探针 + 逐条对抗式复核，30 个 agent），改掉八处，其中一处是真漏洞：**卡片预览的 HTML 消毒可以被撬开**——`raw.replace(/<[^<>]*>/g, …)` 那种「扫出标签再决定留不留」的写法看不见 `<img src=x onerror=… <br>>`：正则咬住里面那个白名单里的 `<br>`，外面两截根本凑不成一对尖括号、于是原样输出，浏览器就拿到了一个活的 `<img onerror>`。卡片是别人的 PDF 编译出来的，这条路走得通。改成**先整段转义、再把白名单里那几个不带属性的标签放回去**（十条攻击载荷全部拦下，`<details>`/`<br>`/`<sub>` 照常工作）。其余七处：`workspace=` 此前不受限——其它端点返回的是派生数据，这两个返回的是文件字节，所以现在要求那个目录**确实是**一个 MAGI 工作区/hub/已注册库；`data-src-line` 一加上去，"独占一段的行间公式要脱出 `<p>`" 那条规则就失效了（正则还在匹配裸 `<p>`），全语料 103 处退化为 7 处（剩下的是作者本来就把公式和文字写在同一段）；未闭合的 `$$` 会跟几百行之后的另一个 `$$` 配对、把中间整段吞掉——现在按 6000 字符封顶失败（全语料 34 738 个公式里最长的是 1 940 字符）；`\tag` 在行内数学里被 KaTeX 整条拒绝，是它唯一的主要失败原因，全语料报错 26 → **3**（剩下三条是源文件本身括号不配对）；`eqnarray` 三列并两列时中间那列若是命令（`a &\overset{def}{=}& b`）会漏掉；围栏的闭合此前写成 `
```[^
]*`，于是块内一个 ```` ```mermaid ```` 会被当成闭合符提前收尾——CommonMark 说闭合围栏不带 info string，改成只允许尾随空白。**顺带被这条改动咬了一口**：语料是 CRLF，`[ 	]*` 停在 `
` 上，闭合符谁也匹配不上，围栏一路吃到文件尾，全语料公式从 34 735 掉到 26 869——所有行尾锚点都补上 `
` 才修好。另外 `$$` 三条候选的**顺序**也要紧：行锚定那条若排在前面，会跨过 `$$egin{array}…\end{array}$$` 真正的闭合符去够后面的，报错从 3 涨到 24。最终全语料（402 文件 / 5.75MB / 34 954 个公式）：KaTeX 报错 3、占位符残留 0、`$$` 残留 0、行号误差 0。另外发现一个**文档自身**的问题：`Breuckmann和Eberhardt - 2021` 那篇摄入结果在第 281–282 行有一对重复的闭合围栏，27KB 正文被 markdown 当成代码块——不是渲染器的锅（与 marked 裸跑结果逐字节一致），但那篇需要重新摄入。测试 165 → 230。
>
> 2026-08-20 运维按钮修复 (v1.8.2)：用户报「在 WebUI 给 Algebra+Duality+Topology 构建图谱失败」。查 `ui-jobs.jsonl` 发现真正红的是**重建维基索引**：`magi wiki reindex` 要求位置参数 `topic_dir`，而 OPS 表里的 argv 只有 `["wiki","reindex"]`，argparse 直接 exit 2，日志里只有一行 usage。同类问题还有两个：`magi link` 同样要求 `topic_dir`（语义概念链接按钮），`magi stats` 要求三选一的子命令（工作区统计按钮）。**修法**：`wiki reindex` 与 `link` 的 `topic_dir` 改为可选、默认取所在工作区（与 `index`/`graph`/`lint` 等命令一致，CLI 用户在课题目录里直接敲也能用了）；`stats` 的按钮明确成 `stats wiki-summary`。**防复发**：`test_contracts.py` 对 OPS 表逐条参数化，把每个 op 的 argv 喂给真实解析器，比对 usage 里还剩几个必填位置参数——14 个 op 全部覆盖。顺带查清用户那个课题：18 篇论文躺在 `raw/papers/`，`wiki/concepts/` 一张卡都没有（0 concepts / 1 refs，那 1 张还是自动生成的 uncompiled-source-coverage），所以 `graph build` 只索引到 1 个节点 0 条边——图谱不是构建失败，是没东西可建；beads 里 17 条 `Compile raw source:` 就是待办。测试 151 → 165。
>
> 2026-08-20 首屏空仪表盘 (v1.8.1)：在 hub 根目录起 `magi ui`（用户就是这么用的）时，`/api/status` 的 `active_workspace` 是 null，而下拉框照样显示着一个已注册的库——两边不一致，`state.workspace` 为空导致 `loadSyncRatio()` 直接 return，HUD 一直停在 `--%` / NO LINK，非得手动把下拉框里已经显示着的那一项再选一次才活。现在初始化时若仍无工作区，就采用下拉框实际显示的那一项并存进 `magi-view-workspace`。在真实 hub（3 课题、6 个注册库）上验证：冷启动直接出 90% 与三核 NOMINAL。测试 150 → 151。
>
> 2026-08-20 命令合并 + 统一切角 (v1.8.0)：用户在真实迁移之后提的"命令有点太多了"。**四条合并全部落地**：`magi migrate` 不再只搬文件——迁完自动搬旧配置、检测项目内旧技能、在 hub 根 `magi pm init`、每个课题 `magi sync --fix`（`--minimal` 退回旧行为）；**`magi sync --fix`** 把报告里确定性的那几步直接跑掉（graph build / index / backlog-sync / pm init，`--dry-run` 先看计划），需要判断的（装 Beads、摄入、审雷达）仍然只列出来；**`magi each <命令>`** 在 hub 根对每个未归档课题跑同一条命令（`--stop-on-error`/`--json`）；**`magi ingest auto`** 按文件类型选路线（源码包→tex、PDF→有 token 走 mineru 否则本地 ocr、文本→add）并自动 finalize，整个 `inbox/` 也能一把梭。**`magi skills install` 加宿主选择**（用户："不要默认全部都装"）：检测到多个 CLI 时 TTY 下交互勾选，非交互直接报错并列出 `--host <名字>`；`--host auto` 才是全装。AI 侧同步：`wiki_ingest`/`wiki_ingest_ocr`/`magi_guide` 三个 SKILL.md 与工作区入场协议（CLAUDE.md/AGENTS.md）都改指新命令。**界面**：HUD 六边形里的 `SYNC RATIO` 此前比图形还宽、直接穿框而出（用户截图），字号/字距收紧并上移到六边形最宽处；**MAGI 模式统一为一套切角语言**——此前只有按钮是切角矩形、面板/输入框/徽章/时钟/终端全是直角甚至 2–3px 圆角（用户："要统一一下视觉风格"），现按面板 14px / 控件 8px / 徽章 5px 三档统一切掉左上与右下角，卡片角标移到剩下的两个直角上，被 clip-path 吃掉的外阴影改用 `drop-shadow` 滤镜补回（缩略图选中环改 inset）。README 四张截图按新界面重拍，并补上 ◐ 校准器特写。测试 128 → 150（`test_consolidation.py` 19 项 + 形状语言三项设计锁）。
>
> 2026-08-20 迁移无损化 (v1.7.2)：在用户的真实 Wikify 仓库（`D:\文档\MindPalace`，hub + 3 课题）上验收迁移后暴露的两个缺口。**旧配置现在默认搬过来**（用户："设计上各种旧的token当然默认要迁移啊，追求的是迁移之后无损体验"）——`magi migrate` 会在 `<课题>/.agents/`、`<hub>/.agents/`、`~/.claude`、`~/.gemini` 找旧 config.yaml，把 token/模型/dpi/阈值填进新配置，只填仍是默认值的项（迁移后的手动修改绝不覆盖），打印搬运的键名但不回显 token。此前那个 402 字符的 MinerU token 就这样丢在旧文件里，`magi ingest mineru` 直接报未配置。**项目内旧 skills 会被检测**——`.agents/skills/` 正是 Codex/agy/opencode 都读的目录，而 `setup --remove-legacy` 只扫 `~/.claude`、`~/.gemini`，够不着；migrate 现在检测 `<BIN>`/`llm-wiki.py` 特征并给出改名命令。**检索质量**——`magi link` 自己生成的「语义关联 (Semantic Links)」小节全是概念名，BM25 下压过真正的定义段（在真实库上复现），已加入 boilerplate 抑制表。手册迁移章同步。测试 127 → 128。
>
> 2026-08-20 文档对齐代码 (v1.7.1)：v1.5.0→v1.7.0 四连发之后对 README ×2 与内置手册 ×2 做了一次逐条核对（4 个 agent 分头把每条安装/命令声明对着实现验证）。**改正**：一键脚本装的是 PyPI 的 `magi-research` 而非「从 GitHub 装 CLI」（脚本自己的 echo 也写错了）；**`git` 不再是硬前置**——从 PyPI 装根本不需要它，两个安装脚本此前会直接 abort，现降级为提示（git 只在注册 Claude Code 插件和 `magi pm init` 时才用得上）；手册链接指向搬家前的 `ui/static/docs/`；`.agents/skills/` 被说成 Codex/agy/opencode 共读（opencode 实际走自己的 `.opencode/{commands,skills}/`）；「技能装在各宿主插件目录」是工作区化之前的说法；lint 两条不可修复项被说成都标了 fixable（只有 `_index.md` 标了）；ch1 的 `magi sync` 样例输出是手写的、与真实输出不符（现按实跑结果替换）；`magi setup reported issues` 的解释错误——setup 永远返回 0，组件失败只体现在结果表里。**补全**：`magi guide` 作为手册的终端入口、skills 表里的 `magi_guide`、`--no-skills` 开关与「setup 只报告不安装技能」、展示区的背景选择器、opencode 的双触发机制、快速上手里的 `magi skills install`、宿主列表里的 opencode、以及「十二章」却只列了十一章。
>
> 2026-08-20 三项界面修复 (v1.7.0)：**标签条不再藏页签**——原来是单行 `overflow-x:auto` 且隐藏滚动条，822px 下有 3 个页签在视口外、桌面滚轮又推不动（用户："横向容易超宽，但是又不能横向滑动"）；改成 `flex-wrap: wrap`，窄窗口折成两三行，任何宽度下都是零个页签越界。实测：全 7 个页签 × 两套主题 × 560/822/1280 三种宽度，越界元素只剩 `<pre>` 内部的代码行（本身就可横滑），其余布局（顶栏/核心带/ops 网格）v1.3.1 起就已自适应。**危险区补玻璃**——EVA 下 `.danger-card` 此前只有一层 `rgba(255,74,87,0.07)` 平涂、没有 backdrop-filter，是唯一漏掉液态玻璃的面板；现改为「红色身份层 + 与 `.card` 同款玻璃配方」双层背景，跟随 `--glass-*` 校准。**背景可选**——◐ 面板新增缩略图选择器：点一张=固定，点多张=只在这几张轮换，不选=按窗口比例自动（红/蓝各存各的 `magi-bg-pick-*`）；显式选择优先于宽高比匹配，失效条目自动回落自动模式；SHUFFLE 手动换一张，Reset 一并清空。为此新增 13 张 200px 缩略图（共 69KB，`thumbs/<variant>/`，manifest 加 `thumb` 字段），避免选择器解码 3.4MB 原图。中英手册同步。测试 123 → 127（四条设计锁：标签折行、危险区玻璃配方、选择器接线、每张背景都有小图且总量受限）。
>
> 2026-08-20 上架 PyPI (v1.6.2)：`pip install magi-research` / `pipx install magi-research` / `uv tool install magi-research` 三条路径打通（pipx 不是仓库，它从 PyPI 装，所以只要发一次就都成立）。补齐发布前缺口：**仓库此前没有 LICENSE 文件**（元数据声称 MIT 却没有许可证正文）——补 MIT 全文并列明捆绑三方许可（d3-force ISC / marked MIT / Archivo OFL）；`license` 字段从已弃用的 `{ text = "MIT" }` 换成 PEP 639 的 SPDX 表达式 + `license-files`；补 keywords / 11 条 classifiers / Homepage·Issues·Changelog；README 的 7 张相对路径图改绝对 raw URL（相对路径在 PyPI 上是碎图）；两个 plugin.json 的描述停止宣称当时并不存在的 `pip install magi-research`。CI：`.github/workflows/release.yml` 打 `v*` tag 触发 → 跑测试 → `uv build` → `twine check` → **Trusted Publishing (OIDC)** 发布，全程无 token 落盘；action 版本按各仓库最新 release 对齐（checkout v7 / setup-uv v10 / upload v7 / download v8 / gh-action-pypi-publish release/v1）。`docs/RELEASING.md` 记录两条路线与 TestPyPI 演练。发布前验证：wheel 3.9MB 含 18 个 skill + 中英双份手册 + WebUI 资源，`twine check` 双产物 PASSED，装进干净 venv 后 `magi --version`/`guide`/`skills` 全部正常。
>
> 2026-08-20 技能改为工作区级安装 (v1.6.1)：用户反馈「随便开个目录点开 agy 都带着这些 skill——不要默认全局安装」。**默认 scope 从 global 翻转为 project**，锚点是 MAGI 工作区根（topic → hub → cwd，从 raw/ 深处跑也落在工作区根，不再用 .git 走查）；`--scope global` 保留但会打印一次提醒；不在工作区里跑 project 安装也会提示「这里不是工作区」。`magi setup` **不再自动装技能**，改为只报告检测到哪些 agent CLI 并给出 `cd <topic> && magi skills install`；体检行随处境切换：在工作区里报该工作区的技能数，否则报「按工作区安装」。`magi init` 结尾提示一键安装。理由写进文档：18 个技能都围着某个研究工作区转（摄入 raw/、编译 wiki/、查该库图谱），装全局等于让每个无关项目白背它们；装工作区还能随仓库分发给同事。已在本机清理掉先前写入四个宿主全局目录的 108 个文件（他人技能 agent-browser/pptx/humanizer 未动）。新增 3 项测试锁住策略（默认 scope、工作区锚点、setup 不写文件），120 → 123。
>
> 2026-08-20 手册可查询 + 跨 CLI 技能安装 (v1.6.0)：**`magi guide`**——手册从「只能读」变成「可被查询」：`magi guide` 列章节、`magi guide <编号|锚点|标题片段>` 读一章（TTY 下用 rich 渲染，管道/`--plain` 出原始 markdown）、`--search "<报错原文>"` 全文检索并附带该节的可执行命令、`--symptoms` 从手册的症状表与 `[!FIX]` 提示框**运行时派生**出 84 条「症状 → 原因 → 修法」索引（不另存文件，永不漂移）、`--json` 为 agent 契约、`--lang` 切语言。解析器 `magi/guide.py` 是单实现，WebUI 的 `/api/docs/guide` 直接复用（章节锚点三处一致）。手册本体移到 `magi/docs/`（随 wheel 分发），新增 1.2 节讲三个入口。**`magi_guide` 技能**——把「查手册再回答」变成 agent 的默认动作：先按症状检索、再读相关章节、跑 `magi sync`/`magi setup --check` 确认现状、最后给出手册里的确切命令；含破坏性命令清单（`setup --remove-legacy` / `tags apply` / `link --auto-merge` / `refactor-concept` / `init --force`）需先确认，以及「没查到就说没查到，不要编」的硬规则。**跨 CLI 技能分发**——技能目录移进包内（`magi/skills/`，wheel 携带 18 个 SKILL.md + 3 个模板；Claude 插件清单改指 `./src/magi/skills`，`claude plugin validate --strict` 通过），新增 `magi skills list/where/install/uninstall`：按宿主查表安装，**区分 global 与 project 两个 scope**，`--dry-run`/`--force`/`--only`/`--dir`/`--json` 齐全，幂等（内容一致→unchanged，陌生同名文件→skipped 不覆盖）。宿主表逐条实测：Claude Code `~/.claude/skills` ↔ `.claude/skills`（`/技能名`）；Codex `~/.agents/skills` + `~/.codex/skills` ↔ `<repo>/.agents/skills`（`$技能名`，无斜杠命令）；Antigravity `~/.gemini/config/skills` ↔ `<repo>/.agents/skills`（仅按描述触发，`/skills` 浏览）；opencode `~/.config/opencode/{commands,skills}` ↔ `.opencode/{commands,skills}`（commands 才是斜杠命令，故为其单独渲染 `$ARGUMENTS` 包装文件）。`magi setup` 自动为检测到的宿主安装（`--no-skills` 关闭，Claude 插件成功时跳过以免重复）。工作区入场协议（CLAUDE.md/AGENTS.md）新增「卡住就 `magi guide --search`」一条。实测：`codex debug prompt-input` 与 `opencode debug skill` 均已列出 magi 技能。**环境体检**——原来只查 `claude` 一个宿主（用户反馈「要不四个都检测，要不都不检测」），现按 HOSTS 表逐个输出 claude/codex/agy/opencode 的安装位置与技能数（缺则直接给补装命令）；`/api/docs/readme` 的 repo 探测标记从 `skills/` 改为 `src/magi/`（技能目录搬家后失效）。**测试** 98 → 120（新增 `test_guide_cli.py` 10 项、`test_skills_cmd.py` 12 项）。
>
> 2026-08-20 内置使用指南 (v1.5.0)：**场景式操作手册**——`static/docs/guide.{zh,en}.md`（各 ~900 行、12 章：先跑通/安装/迁移/建库/摄入/编译/图谱/检索/写作/雷达/看板/疑难速查），每节按「做什么 → 怎么做 → 预期效果 → 不达预期怎么办」四段式写，覆盖全局 vs 按项目安装、四类 agent 宿主接入、Wikify 迁移、四条摄入路线与全部配置键、图谱质量七症状诊断表、检索降级链、beads 写作循环、雷达调噪与三平台定时任务差异。**指南阅读器**——Docs 面板新增默认视图：章节轨（h2 自动编号 + h3 随滚动展开 + scroll-spy）、`{#anchor}` 稳定锚点（供他处深链）、`> [!EXPECT|FIX|WARN|NOTE|TIP]` 提示框（marked 后处理为带主题色的 callout）、代码块一键复制（clipboard API + 非安全上下文 textarea 回退 + 1.2s 超时兜底，保证按钮永远给反馈）、52rem 阅读宽度上限；四主题态全覆盖。**后端**——`GET /api/docs/guide?lang=`（zh/en，缺失语言互为回退，随包分发走既有 package-data glob）。**内容可信度**——13-agent 侦察工作流逐子系统读源码取证（命令/flag/配置键/真实错误串/失败分支），再由 completeness critic 找缺口（补上「raw→wiki 编译无 CLI、必须接 agent」这条第一要务、`magi grep`、`setup --no-models/--no-plugin`、`ui --host/--port`、`pm init` 无需 hub）；47 条命令的全部 flag 与 live `--help` 逐一对照通过。**测试**——新增 4 项（端点契约与语言回退、markdown 结构不变量、中英章节锚点一致、指南只引用真实命令）+ 阅读器 wiring 锁，94 → 98 全绿。**边缘内发光加强 (v1.5.0)**——三层 inset 光晕（深晕 clamp(120px,15vw,260px) + 紧贴 46px/14px 光环 + 1px 发丝边框），呼吸区间 0.66→1，新增 `--eva-glow-boost` per-variant 强度（红 1 / 蓝 0.86，浅底不发浑）。
>
> 2026-08-19 品牌 + 排印 + 文案 (v1.4.5)：**三贤者徽记**——顶栏原创 SVG mark（六边形壳 + 红/绿/青三核节点 + 总线），颜色走 per-core token 四主题态自动换装，EVA 下三核序列脉冲（bm-pulse，reduced-motion 门控）；**字号层级**——卡片标题 1.04→1.18rem、metric 数值 clamp 上限 2.5rem、副标题 0.75/标签 0.66 加字距、品牌 1.32rem；**去术语化**——BM25/向量/RRF 等引擎词从界面清除（cas_title/subtitle、opt_* 三项、search_summary、vec_unavailable_hint、cfg 嵌入模型、tab_casper、core_role_cas、HUD 明细行），中英同步。README 双语新增 MAGI MODE 展示区（docs/webui-*.jpg ×4）。
>
> 2026-08-19 视口边缘内发光 (v1.4.4)：MAGI 模式专属 `body::after` inset 光晕（`--eva-glow-rgb`：红琥珀 255,148,33 / 蓝青 10,158,215），5.5s opacity 呼吸（合成器友好、reduced-motion 门控），z-index 与 CRT 层同级、pointer-events:none。
>
> 2026-08-19 CRT 可选 + 对抗式加固 (v1.4.3)：CRT 扫描线改为校准面板开关（`html.crt-on` 门控、默认关、localStorage `magi-crt`、闪烁关键帧随 `--crt-opacity` token 缩放）。30-agent 对抗审查确认 26 缺陷全修：蓝态残余霓虹 literal 全部路由到变体 token（核心带/徽章/状态点/HUD SVG/终端控件/metric 标签）；程序化 WCAG 驱动的双态对比度调优（蓝 muted #54657A、accent/贤者墨加深；红 muted 提亮 #97A1B3）；玻璃透明度 `max(var(--glass-floor),…)` 地板（蓝 0.5）；boot 动画与变体解耦（固定琥珀）；浅色去紫色光池；校准器数值钳制 + CRT 行独立布局 + toast `pointer-events:none`；图谱缓存回访 sim 恢复、注记语言重渲染、背景 onerror 重试/降级。测试 94 全绿（CRT 设计锁更新为 opt-in 契约）。
>
> 2026-08-19 EVA 蓝态真·浅色模式 (v1.4.2)：蓝·静默值守翻转为浅色语义——白霜玻璃 + 浅纸面板 + 深青墨水 ramp（#0A7295 系）+ 三贤者 ink 色（#0B7C9E/#148A4E/#C22834），`--eva-bg-rgb` 换近白后纱幕自动变白纱提亮；EVA 皮肤残余深底 literal（输入框/次级按钮/建议行条/表头/toast/markdown/弹窗遮罩/终端按钮）全部 token 化，两变体共享一套皮肤。纱幕按用户反馈收敛为灰阶目标：红 0.72/0.32/0.12/0.45（深灰）、蓝 0.7/0.42/0.26/0.5（浅灰），照片 opacity 0.6→0.72；玻璃 brightness/saturate 变 per-variant token（红 0.8/1.8，蓝 1.08/1.25），`--glass-saturate` 加入调节体系。
>
> 2026-08-19 液态玻璃网页可调 (v1.4.1)：MAGI 模式右下角 ◐ 材质校准部件——模糊（0–30px）与不透明度（40%–170%）滑杆实时驱动 `--glass-blur`/`--glass-alpha` 两个 CSS 变量（EVA 全部玻璃面板消费），localStorage 持久化（magi-glass-blur / magi-glass-alpha），默认值时移除内联覆盖保持样式表权威；重置按钮回 10px/100%。
>
> 2026-08-19 图谱视图 + EVA 双模 (v1.4.0)：**知识图谱去 SQL 化**——新 CLI `magi graph browse`（overview/nodes/links/claims/tags/broken/map 七视图，`src/magi/kb/graph_browse.py` 纯函数层 = CLI 与 `/api/workspace/graph/browse` 单实现）；WebUI Melchior 卡改结构化浏览器（词条钻取链接、断链高亮、标签点击回填筛选），原 SQL 控制台降级为折叠「高级」项（端点与守卫不变）。**Obsidian 式图谱视图**——`view=map` 全图 dump（默认剔除 tag 节点、`--tags` 开关、未解析 wikilink 合成 ghost 节点复刻 Obsidian 行为、>800 节点按连接度截取），前端 vendored d3-force 微件（dispatch/quadtree/timer/force ×4 ≈17KB，ISC，`vendor/d3-force-LICENSE.txt`）+ 自绘 canvas（类型着色取自 CSS 主题 token、金角螺线种子、拖拽/滚轮缩放/悬停邻域聚焦/点击钻取 links 视图、DPR 感知、ResizeObserver）。**雷达作者管线**——S2 fields 加 authors、arXiv Atom 解析 `<author><name>`、digest 新增 `- authors:` 行（≤6 名 + et al.，`_candidate_lines` 提取为纯函数）、`parse_digest_candidates` 回传 authors（旧 digest 兼容）、UI 候选行作者显示 + 客户端作者/标题筛选（计数徽标）。**EVA 双模**——MAGI 模式与深浅轴独立作用：`data-eva="blue|red"`（浅→蓝·静默值守：靛蓝面板 + 冰青 #4FC3F0 + UNIT-00 原型机图解；深→红·战斗配置：原琥珀系）；EVA 段 125 处琥珀硬编码 token 化为 `--eva-p` 色阶（monolith 三色与 #FFB000 危险条纹为典章色不随变体）；模式内 ☀︎/☽ 切换警戒态不退出。**背景引擎**——EVA_pics 原图（116MB，gitignored）经 Pillow 一次性压为 WebP ×13 共 3.4MB 入包（`static/backgrounds/` + manifest.json 含宽高），`/api/ui/backgrounds` 三级解析（config-home `ui-backgrounds/` 用户覆盖挂 `/ui-bg/` → 打包 manifest → 空），前端双层交叉淡入 + 宽高比 log 距离匹配（±0.28 池内切页随机轮换、resize 仅出池换图）+ 画布色渐变遮罩；`.webp` MIME 显式注册。**液态玻璃**——iOS 材质配方（rgba(--eva-bg-rgb) 低 α + blur 10px + saturate 1.8 + 白色高光边）覆盖 card/topbar/core-band/tabs/pane/HUD/modal/terminal，背景画透出可辨。**CLI 中文参考**——`core/cli_i18n.py`（55 命令 + 10 组）、`/api/docs/commands` 附 help_zh/groups_zh、Docs 表按语言渲染、`tests/test_cli_i18n.py` 双向奇偶锁防漂移。**杂项**——静态资源 Cache-Control 改 no-cache,must-revalidate（升级后不再吃陈旧缓存）。测试 52 → 94 全绿。
> 2026-08-18 WebUI 视觉重构 (v1.3.1)：三主题设计系统整体重写（styles.css 全量、index.html 语义化、app.js 生成标记类化）。**基础双主题「Institute」**——制图纸底 + 毫米格水印 + 普鲁士蓝墨水主色、书卷衬线标题（Iowan/Palatino 栈）、Cascadia 等宽数据、metric 卡「测量值」排印 + 角标注册记号；暗色版为同语言的天文台蓝黑。**EVA MAGI MODE 深度打磨**——全屏背景插画层（初号机头部技术图解线稿：紫罗兰描线 + 绿色单眼 + 尺寸标注；左上 AT 力场同心六边形呼吸动画；右缘竖排「三賢者統合思考体・同調率監視中」），卡片改半透明 + backdrop-blur 保文字可读，琥珀色阶收纪律（#FF9421 系），tab 频道编号 00-06，全部动画尊重 prefers-reduced-motion。**缩放/响应加固**——rem 化、`minmax(min(100%,…))` 网格、topbar flex-wrap 三级换行、表格 .table-scroll + 粘性表头、split-pane 900px 折叠、iframe 视口矩阵实测 320/390/640/768/1024 × 7 tab 零横向溢出。**杂项**——i18n 按钮 emoji 清退（58 处）、原生控件 color-scheme 跟随主题、自定义 select 箭头、细滚动条、:focus-visible 焦点环、markdown 表格样式补齐。契约零改动（纯前端静态资源 + i18n 字符串）。
>
> 2026-08-18 M9 逻辑⇄WebUI 对齐 (v1.3.0)：**契约统一**——`retrieval.run_search()` 单实现（CLI `--json` 与 `/api/workspace/search` 逐字段一致 = 未来 mcp 契约，UI 免费获得联邦 scope/collection/`--path` 过滤，连接不再泄漏）、`build_report` 新增 `hints_structured`（code+text 双轨，前端按 code 渲染按钮，删正则）、`radar.scan_reports()` 单一事实源，`tests/test_contracts.py` 契约锁。**jobs 收权**——OPS 白名单（不再收 raw argv）、danger 服务端 confirm==op、并发闸门（同库 1 活跃/全局 3/global 独占）、`GET /api/ops` 驱动全部操作按钮（危险区补 install-schedule）、任务历史落盘 ui-jobs.jsonl（256KB/40 条上限，跨重启回放 20 条）。**radar 审阅写路径**——mark-reviewed / accept-to-inbox / create-issue 三端点 + digest 阅读器按钮。**新能力上 UI**——BibTeX 复制导出、检索过滤器（scope/collection/path + kb/collection badge）、drafts 区块、config.yaml 白名单字段编辑器（`core.config_edit` 手术式改行，保注释，safe_load 回验防腐蚀）。**语义收口**——「查看工作空间」+ Browsing 徽标 + localStorage 恢复；README 三级回退（repo→wheel metadata→GitHub raw，装态不再空白）；端口默认改 8737（忙时探测 8738-8746，显式指定忙则报错）。
>
> 2026-08-18 M8 全周期加固 (v1.2.0)：真实科研用户全周期模拟（建库→摄入→编译→检索→任务→雷达→写论文，23 个摩擦点全部修复）+ WebUI 浏览器点击审计。准确率侧：FTS5 CJK 二元组分词（中文 BM25 从 0 命中修到可用，旧索引自动迁移 fts_version=2）、claims 宽松匹配层（连字/断词/全角/CJK 空格）、radar 嵌入质心相关度排序（`radar.min_relevance`）、检索剔除 See Also/Sources boilerplate、`--path` glob 过滤。摄入侧：ingest tex 相对路径崩溃修复、.bbl-only 自动内联（引用不再全灭）、HTML `<img>`/`<embed>` 图片抽取 + 丢图安全网、`.bib/.bbl` sidecar 保留、arXiv ID 入 frontmatter、OCR `--pages`/ETA/断点续跑提示/非 TTY 静默、pymupdf 弃用告警消除。工具链一致性：add-concept 标题源 lint 可解析（title/aliases 回退）、lint 仅 critical 判 FAIL（exit 同步）、raw tags/summary 降为 warning、math check 预置物理宏包 + 误报注记、finalize 透传 stdout、verify 幽灵 malformed 块修复。新能力：`magi bib`（BibTeX 导出，--fetch 拉 arXiv 官方条目）、`drafts/` 写作约定 + `wiki_draft` skill、`magi claims verify` 别名。WebUI：可执行 hints 卡、检索空态指引、常见错误中文化、README 图片走 GitHub raw、citation-gap 报告可见（badge + 计数）。
>
> 2026-08-18 M7 EVA 主题 (v1.1.2)：MAGI MODE 战术主题完成——三贤者三体阵列 HUD（MELCHIOR·1 科学者 / BALTHASAR·2 母親 / CASPER·3 女性，实时核状态 + 中央六角同调率）、CRT 扫描线/蜂窝网格/斜切控件/警示条纹 Danger Zone/启动同步序列（全部动画尊重 prefers-reduced-motion）。安全加固：移除通配 CORS（设计红线回归）、新增 Trusted Host 白名单（防 DNS rebinding）、非环回绑定告警。
> 2026-08-18 M7 WebUI 润色 (v1.1.1)：去底层框架术语（全面抽象为科研任务流/知识网络概念）+ 原生中英双语国际化（`中 / EN` 切换与持久化，全站卡片/模态框/诊断与中英文 README 联动）。
> 2026-08-18 M6：全局知识库注册表 + 联邦检索（`magi kb register/list/enable/disable/unregister`，注册表在 `~/.config/magi/registry.json`，`magi index` 自动注册；`magi search` 默认联邦当前工作区+启用库，结果带 kb 标记，`--scope local`/`--kb` 收窄；跨库 RRF 融合）+ kb-only profile（`magi setup --kb-only` 还原经典 Wikify 体验，Balthasar 停用且不计入同步率）。测试经 MAGI_CONFIG_HOME 隔离，冒烟含联邦回归锁。
>
> 2026-08-18 安装体验升级：一键安装脚本（install.ps1/install.sh，uv/rustup 引导模式）+ `magi setup`（bd/模型/plugin 自动装配 + 环境体检 + 旧版检测/清除）+ `magi migrate` hub 模式（一键全主题迁移）。真实一键命令已在本机端到端验证（含 GitHub git+ 源安装与 Claude Code plugin 注册）。
>
> 用户模拟结论：六个画像（新手/逐字执行 skill 的 agent/radar 首用/claims 研究流/双主题任务管理/中文+空格路径）全部走完全程 40/40 步。修复亮点：lint 不再隔离 init 生成的协议文件；wikilink 边解析为真实节点 id（文档中的 join/路径查询恢复有效）；radar 同日二次 harvest 不再覆盖已审 digest（编号并列 + 台账追加）；hub 命令就地向上发现；search/lint 退出码与 --json 错误信封统一；CJK 目录名自动 slug 化 bd 前缀；graph query/grep 输出中文不再转义；citation-gap 报告含我方论文元数据与共享文献名。
>
> 剩余人工事项：① 本地文件夹改名 `gemini-wiki-skills` → `magi`（会话占用目录，需会话外执行）；② 删除 gitignored 的 `.agents/`、`output/` 历史残留；③ macOS 上跑一次 `tests/smoke_test.py`（sqlite extension 验证）；④ 在真实 hub 上 `magi pm init` + `magi radar install-schedule` 投产

## 项目一句话

**MAGI** = agent-native 科研工作环境。三态架构：Beads 管 work state（在做什么），Wikify 子系统管 epistemic state（知道什么、为何可信），自建检索层管 retrieval state（该读什么）。人是驾驶员，LLM 是机体，确定性 CLI 是拘束具，`magi sync` 输出同步率。

## 待修问题（已确认，未动手）

> 最后整理：2026-08-22（v1.12.2 之后）。**都有复现证据**，不是猜测；每条注明证据、位置和建议改法。
> 修掉一条就从这里删掉，并在当天的 dated entry 里写清楚。

### A. 已确认的 bug

| # | 问题 | 证据 | 位置 | 建议 |
|---|---|---|---|---|
| A1 | **arXiv-HTML 路线的图片会跨论文互相覆盖** | 实测：论文 A(2401.00506) 与 B(2502.11111) 各有一张 `fig1.png`，改写后**两篇的 markdown 都指向 `images/fig1.png`**；commit 按 basename 平铺进 `raw/papers/images/`，后者覆盖前者 → A 显示 B 的图 | `arxiv_html.py:_rewrite_image_paths` 用 `os.path.basename(target)`；`batch.py` commit 段平铺复制 | 加 `{slug}-` 前缀，`tex2md.py:242` 和 `mineru.py:181` 已经是这么做的。**这是 rung 1，最优先的路线** |
| A2 | **textlayer 产出的图片链接是绝对临时路径，commit 后全断** | 实测：`pymupdf4llm` 吐出 `![](C:/Users/.../Temp/tmpXXX/images/xxx.png)`；commit 只复制文件、**不改写路径**，staging 一清链接全死（图片文件在 `raw/` 里，没人指得着） | `batch.py:108` 调 `to_markdown(write_images=True, image_path=…)` 后直接落盘，无改写 | 改写成 `images/<basename>`，与其余四条路线的产出形状一致 |
| A3 | **专门防 A2 的关口结构上看不见 A2** | 实测：绝对路径喂进去，`check_broken_image_links` 返回**"干净，没问题"** | `gates.py:126` 正则只匹配 `](images/…)` 相对路径 | 同时匹配绝对路径与裸 `<img src>`。**这条比 A2 更值得先修**——修好它，A2 会自己变成可见的 finding，下一个我们没想到的路线它也接得住 |
| A4 | **本地 PDF 永远走不到 textlayer** | 实测：真实存在的本地 PDF → `source_type='file'` → 起始 rung `mineru`；`next_rung('mineru')='ocr'`，而 textlayer 在阶梯上位于 mineru **上方**，掉不上去。完整链：`mineru → ocr → None` | `batch.py:_starting_route` 只有三条规则，其余一律 `mineru` | `source_type='file'` 且后缀 `.pdf` 时返回 `textlayer`，让闸门自己判；判不过正常掉 `mineru`。代价只有一次 PyMuPDF 打开文件。**影响面：用户 758 条 Zotero 里 567 条带 PDF** |
| A5 | **两条 PDF 入口对同一份文件给出不同路线** | `magi ingest auto` 走 `classify()`，**会**用 textlayer；`magi ingest batch-run` 走阶梯，**跳过** textlayer | `auto.py:classify` vs `batch.py:_starting_route` | 同一个决策实现了两次。A4 修完顺手合并成一处 |
| A6 | **`except ImportError` 太窄，会让整个 `ingest auto` 崩掉** | 实测：`pymupdf4llm` 在 onnxruntime 1.15.1 上抛 `onnxruntime.capi.…Fail: Unsupported model IR version: 10`，**不是 ImportError** → 逃出 `classify()` | `auto.py:52`、`batch.py:98` | 改成接住任何异常并给出可操作提示（"升级 onnxruntime"）。顺带给 `[textlayer]` extra 的 onnxruntime 写版本下限 |
| A7 | **拒绝重排队时硬编码 `source_type="arxiv"`** | 一份本地 PDF 被拒绝降级后，以 `source_type="arxiv"` 重新入队，`value` 却是文件路径 | `batch.py:279` | 目前不炸（`route=nxt` 显式给了，不走 `_starting_route`），但账本记的是假的，将来任何按 source_type 分流的逻辑都会踩到 |

### B. 质量问题（不是 bug，是选择）

| # | 问题 | 证据 | 建议 |
|---|---|---|---|
| B1 | **`pymupdf4llm` 的 `write_images=True` 导出的是"每个嵌入图像对象"，不是"图"** | 实测一篇 55 页论文吐出 **403 张**（约每页 7 张）——TeX 论文里每个矢量片段都被单独导出 | 这条路本来就是给"无数学的散文文档"用的，图不是重点。建议默认 `write_images=False`；真要图，本地 OCR 那条（按图标题锚定裁剪，4 篇实测 85/86）好得多 |
| B2 | **`pymupdf4llm` 把表格塌成一行** | 实测：`Category Kept Excluded heightCorrespondence 412 38 …`，`\hline` 还漏成字面量 `height` | `to_markdown` 签名是 `(*args, **kwargs)`，试过的 table 参数都无效。暂时接受，或在 finding 里提示"本文含表格，textlayer 路线会丢结构" |

### C. 已实测否定的方案（别再重复调研）

| 方案 | 结论 | 证据 |
|---|---|---|
| **阿里 DocMind V2**（免鉴权端点） | **不建议进阶梯。** 端点是真的、无需 AccessKey、可达；但公式回来是扁平化字符汤**并且被套进 `$$`**——看起来像 LaTeX、实际是坏的，正是本管线要绕开的失败模式 | 实测（自造 PDF，未发用户文件）：`\hat{H}=\sum_i J_i\sigma^z_i\sigma^z_{i+1}` → `H=[Joo1`；`\frac{1}{n}\sum…=\int_0^1 f dx` → `$$ 1lim f(x) dx(1) n→oo n2()-[ $$`；矩阵 → `$$ M=(aprγγ66), $$`。`enhancementMode: VLM` **输出逐字节相同**，免费端点上被忽略 |
| 同上，无数学文档 | 也比 pymupdf4llm 差：标题层级全塌成 `#`、列表是字面 `●`、表格被**当成公式**包进 `$$` | 同一份对照文档 |
| 同上，其他障碍 | 输出是临时签名 OSS 链接、默认 `http://` 明文；**16% 的用户 PDF 超过 3.75 MB 上限**（626 个里 99 个，90 分位 6.1 MB）；官方文档查不到"10 万 credits/天 / 50 credits/页"这三个数字 | 实测 + 官方文档核查 |
| **未测**：DocMind 在**扫描件**上的表现 | 唯一还可能有价值的场景。若明显强过本地 `glm-ocr`，有资格做 rung 5 的替代 | 手头没有合适的扫描 PDF |

### D. 架构债（判断，不是 bug）

| # | 观察 | 为什么要紧 |
|---|---|---|
| D1 | **Hub / 工作区 / 知识库 = 三个词对两个半东西** | 作者本人说"我都晕了"。而且它一直在漏：为它加了作用域徽章、hub-level 徽章、解释弹窗、任务归属句、检索范围行。**当你为一个概念加解释性 UI 时，通常是概念错了。** 可考虑：知识库不是第三种东西（=已注册的工作区）；Hub 目前唯一实质作用是放共享任务库 |
| D2 | **配置有两套表示，需要代码同步** | 关任务追踪有 `profile: kb-only` 和 `optional_features.tasks` 两处，`set_feature()` 里专门写了同步逻辑还配了测试。**需要代码维持一致的两份状态迟早会不一致。** 现在动成本最低 |
| D3 | **派生数据 vs 原创数据没有统一标记** | `graph.db`/`index.db` 可再生，`raw/`/`wiki/` 不可，`output/ingest/` 是事务日志。每次要动什么都得逐个推理。一条明确约定（"`output/` 下除 `ingest/` 全部可再生"）能让"重建吧"变成零风险、备份建议变成一句话 |
| D4 | **WebUI 在用 JS 重新实现后端逻辑** | `countTasks()` vs `bd_status_summary()`、功能开关判断两处、i18n 抄了一遍 CLI 文案。任务面板显示 0 那个 bug 本质就是这种漂移。判据：**一段 JS 在做判断而不是渲染，它大概率该在 Python 里** |
| D5 | **Skill 是没有测试的代码，而且单位字符代价最高** | 那次烧掉用户周额度的事故，起点是 `wiki_ingest/SKILL.md` 里一句话。`test_skill_conventions.py` 只检查**形式**（不许写死宿主工具名、必须有提问原语），检查不了**行为**。可行起点：给每个 skill 写下"绝不应该做的三件事"，至少让它们在文本层面可检测 |
| D6 | **上游依赖承重且无版本承诺，但没有降级表** | arXiv HTML 是 beta、ar5iv 是 2024-02 冻结快照、S2 匿名限额无文档（实测拒绝 295、100 可以）、PyPI simple index 比 JSON API 慢几分钟。建议显式写一张「每个上游挂掉时产品退化成什么样、用户看到什么」的表——既是设计文档也是测试清单 |

### E. 测量缺口（知道自己没测）

- rung 2（tex/pandoc）的成功率只在**两篇老论文**上试过，两篇都暴露了缺陷（一篇静默丢 6 张图，一篇 pandoc 直接死在 `\vskip`）。完整样本等 rung 1 上线后看 rung 2 真实流量再说
- arXiv 覆盖率测量**没取到** pre-2000 的原生 HTML 桶和非物理学科桶
- 本地 OCR（rung 5）在数学上的质量**从未测过**——`glm-ocr` 没有公式专项，也不在任何 benchmark 里。原计划的 0c 一直没做
- DocMind 在扫描件上的表现（见 C）

---

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
| D10 | 不做：capability IR/host compiler、AutoResearchClaw 式 control plane、OpenCode/dsh 适配（注：自研 UI 作为轻量 inspection/ops WebUI 看板已在 M7 里程碑纳入） |

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
magi verify <claims-file>    # verify_claims，兼容 CLAIM:/FINDING:（别名 magi claims verify）
magi bib [card|--all]        # v1.2.0: 参考卡 frontmatter → BibTeX（--fetch 拉 arXiv 官方条目）
magi grep                    # ← search-wiki.py（M2 后仍保留，精确正则用）
magi search / index          # M2: FTS5+sqlite-vec+RRF 混合检索（v1.2.0: CJK 二元组分词 + --path + drafts/）
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

### M4 — Claim/Provenance 层（✅ 完成）

- [x] `magi verify` v2：`--json`、空白归一化匹配（OCR/重排漂移免疫）、`--fetch-web` 真实抓取比对（状态：verified / web-verified / url-format-ok / unverified，均已实测）
- [x] claim markdown 落地约定：输出文档内 `<!-- magi:claims ... -->` HTML 注释块（Obsidian 渲染零污染）
- [x] graph.db：claims + evidence 表；claim 是一等节点（type='claim'）；新 edge types `has_claim` / `supported_by`；全量重建模式不变
- [x] `magi sync` Melchior 加 claim 维度（0.55 新鲜度 + 0.25 backlog + 0.20 claim 验证率；无 claim 记中性 1.0）+ 未验证 claim 提示
- [x] wiki_research / wiki_audit：verify 步骤加 `--json`/`--fetch-web` 说明 + 输出文档嵌入 claims 块的指引

### M5 — Radar 功能 B（✅ 完成）

- [x] `magi radar citation-gap`：四层漏斗（S2 推荐近邻 − 实际引用者 ∩ 近 2 年 ∩ 共引 ≥2 篇）；**完全用 S2 免 key 端点实现，OpenAlex 依赖解除**
- [x] 输出 `inbox/radar/日期-citation-gaps.md`（明示"侦察报告非判决"）+ `citation-gaps.jsonl`
- [x] radar_review skill 增 citation-gap triage 节：判断真实引用义务 → `bd create -t review`，明确禁止自动起草 outreach
- [x] config：`radar.own_arxiv_ids`（含 2401.00505）+ `citation_gap.min_shared_refs/years`
- [x] live 实测（锚点 2401.00505）：30 推荐 → 4 幸存，含共享 13 篇参考文献的强信号候选

### M7 — WebUI 看板（✅ 完成）

- [x] 后端基础设施：`fastapi>=0.100.0` + `uvicorn>=0.22.0` 依赖写入 `pyproject.toml`，配置 `magi.ui` 的 package-data。
- [x] CLI 入口：在 `src/magi/cli.py` 注册 `magi ui` 命令，支持 `--host`、`--port`、`--no-open`、`--check`。
- [x] 任务管理器：`src/magi/ui/jobs.py` 实现 `TaskManager`，支持后台子进程调度、环形日志缓冲区、SSE 日志长连接流式推送与优雅取消。
- [x] API 路由：`src/magi/ui/api.py` 暴露全局状态、KB 注册表管理、工作区内省（三核同步率、Claims 验证、Casper 检索、Radar digests、只读 Graph SQL 白名单守卫）与异步任务调度。
- [x] 前端界面：`src/magi/ui/static/` 零构建 Anthropic/Claude 纸墨美学 SPA（陶土暖橙点缀、深浅主题自适应、7 个核心功能 Tab、实时终端输出、Danger Zone 二次确认对话框）。
- [x] 自动化测试与冒烟测试：`tests/test_ui_api.py` 完整覆盖核心端点与安全白名单；`tests/smoke_test.py` 集成 WebUI 冒烟检验。

## 交接须知（给接手的 agent）

- 原始代码盘点结论：检索现状是纯 regex grep（无向量）；graph.db schema 在 `llm-wiki.py:2468-2493`（nodes/edges/tags/aliases，全量重建式）；embedding 只在 semantic_linker（Ollama + 独立缓存 db）。
- 提交规范：小步 checkpoint，`git commit` 带清晰前缀（feat/fix/refactor/chore/docs）。
- 环境：Windows 11 + Python 3.10.11 + uv 0.11.2；Ollama 本地服务（qwen3-embedding:0.6b, glm-ocr）。
- 用户要求：重大决策才停下来问；其余持续推进。
