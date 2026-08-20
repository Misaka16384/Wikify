# MAGI 开发路线图（动态文档）

> **本文档是活的交接文档。** 任何 agent 接手工作前必读；完成一步就更新对应条目（勾选 checkbox、追加 Status 注记）。架构定案见下方"锁定决策"，不要重新讨论已锁定项。
>
> 最后更新：2026-08-20 · 当前阶段：**v1.9.1 已发布**（tag `v1.9.1`；版本号同步 ×5）。此前：M0–M9 全部完成。
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
