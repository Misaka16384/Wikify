# Original User Request

## Initial Request — 2026-06-05T05:47:41Z

本项目旨在对 `gemini-wiki-skills` 代码库中的所有 15 个 skills（位于 `skills/` 目录下）进行全面扫描，寻找设计缺陷、鲁棒性（robustness）不足以及框架/格式不一致的地方，并特别指出本应使用确定性脚本/程序来实现却依赖了 LLM Agent 的地方。最终输出一份中文详细审计报告，不做代码修改。

Working directory: d:\AI_Playground\gemini-wiki-skills
Integrity mode: development

## Requirements

### R1. 全面设计审计 (Comprehensive Design Audit)
对 `skills/` 下的 15 个 skill 进行深入的设计 and 架构审计。重点分析并记录以下问题：
1. **模型过度依赖 (Model Over-reliance)**：找出任何本可以通过确定性脚本、正则表达式、解析器或数据库查询完美处理，但在现有设计中被委托给 LLM Agent 的逻辑（例如：检测未编译文件、手动拼接/合并文件、手动解析特定语法、提取简单 metadata 键值等）。
2. **框架与格式不一致 (Framework Inconsistency)**：检查各 skill 是否严格遵守一致的规范（如 `SKILL.md` 格式、工具使用规约、配置加载 and 路径解析方式等）。
3. **鲁棒性缺陷 (Robustness Defects)**：寻找任何可能在 Windows/Linux 跨平台下由于硬编码路径分隔符、CRLF 换行符处理不当、多任务并发下的资源冲突（如临时文件/缓存覆盖）以及不完善 of 异常捕获所导致的失效隐患。

### R2. 中文详细审计报告 (Detailed Report in Chinese)
在工作目录下生成一份 `skills_audit_report.md` 的中文 Markdown 报告，必须包含：
- **总体审计评估**：技能设计缺陷的整体分类 and 缺陷数量统计。
- **逐个 Skill 详细诊断**：对 15 个 skill 逐一诊断其是否存在上述三类缺陷。凡有缺陷，必须引用具体的文件名、行号 and 关键代码片段。如果某个 skill 设计无缺陷，需说明理由。
- **改进与重构建议**：针对每个被指出的“模型过度依赖”或“鲁棒性缺陷”，给出具体的重构思路（例如：应该编写什么样的 Python/Node.js 脚本来替代 LLM 逻辑）。
- **注意**：只做审计和报告，绝不修改任何现有代码。
- **清理保障**：如果在扫描或分析过程中运行了任何测试或脚本，必须确保测试产生的临时文件和变更全部被清除，使工作区回到干净状态。

## Acceptance Criteria

### Report Completeness & Accuracy
- [ ] 报告文件 `skills_audit_report.md` 已成功生成在工作目录根目录下，且全部使用中文书写。
- [ ] 报告对 `skills/` 目录下的 15 个 skill 逐一进行了分析，未遗漏任何一个。
- [ ] 报告指出了至少 3 个具体的“模型过度依赖”或“本应使用脚本而非 LLM”的设计缺陷实例，且每个实例均指明了对应的文件 and 关键代码行。
- [ ] 报告指出了至少 2 个跨平台或多任务并发（如临时文件冲突、CRLF/LF换行符解析等）下的鲁棒性隐患，且包含代码证据。
- [ ] 工作区在审计完成后回到了完全干净的状态，没有遗留任何审计过程中产生的临时文件、备份文件或测试输出。

## Follow-up — 2026-06-05T06:03:26Z

根据 `skills_audit_report.md` 和 `implementation_plan.md` 的内容，对 `gemini-wiki-skills` 代码库进行完整的修复与重构。修复需要新建必要的高效率辅助脚本，消除模型对确定性操作的过度依赖，修复 Windows URI、CRLF 换行符解析、并发临时文件碰撞以及 Slug 重构链接失效等鲁棒性缺陷。此外，重构后必须确保所有技能在行为、配置加载和备份机制上保持高度一致（Consistent），没有不一致的现象。

Working directory: d:\AI_Playground\gemini-wiki-skills
Integrity mode: development

## Requirements

### R1. 消除过度依赖与脚本化替代 (Eliminate Over-reliance & Scripting)
1. **未编译源文件检测**：在 `bin/` 下开发或集成 `detect_uncompiled.py`。
2. **多路转录自动拼接**：开发或集成 `assemble_transcriptions.py`。
3. **入库流转及重命名**：开发或集成 `ingest_helper.py`。
4. **工作区初始化模板**：开发或集成 `init_workspace.py`。
5. **重写所有技能指令**：修改 `wiki_compile`、`wiki_ingest`、`wiki_ingest_ocr`、`wiki_init`、`wiki_concept_sync` 的 `SKILL.md`，指示 Agent 调用 these 新脚本，完全消除人工比对、手动拼接、YAML 手工读写及 verbatim 模板写入。

### R2. 鲁棒性缺陷修复 (Robustness Fixes)
1. 修复 Windows 下 SQLite URI 反斜杠报错 (在 `query-graph.py` 中)。
2. 彻底清洗 Windows CRLF `\r` 换行符，防止内容污染和大模型上下文紊乱。
3. 盘符大小写不一致导致的越界路径误判 (在 `verify_claims.py` 中使用 `normcase`)。
4. 并发 Chunker 临时分块及研究任务临时 Claims 文件冲突问题。
5. `format_math.py` 与 `refactor_concept.py` 改写物理文件时，执行原子化替换，杜绝截断和文件损坏。
6. `refactor_concept.py` 重构链接时，正则表达式同步适配中划线 Slug 格式的 Obsidian wikilinks，防止重构后语义链接悬空。
7. 对 `pdflatex` 等外部进程及 Ollama JSON 异常解析添加 try-except 容错机制。

### R3. 全局一致性检查与清理 (Consistency Check & Clean Workspace)
1. **整体一致性（Consistency）**：确保修改后所有的 `SKILL.md` 说明、新辅助脚本的行为和底座工具在接口、命名规约和备份存储位置上高度统一，没有格式或配置的不一致。
2. **清理**：任务完成后，清空所有测试产生的临时文件和变更，保持 git 树整洁。

## Acceptance Criteria

### Functionality & Consistency
- [ ] 所有技能的 `SKILL.md` 指令已被改写并使用了对应的 Python 脚本。
- [ ] 所有的脚本在 Windows/Linux 下均能顺利执行，不报 URI 错误或路径越界错误。
- [ ] 运行 `validate_math_latex.py` 对包含 CRLF 的 Markdown 文本检测时，无回车符遗留。
- [ ] 多任务并行调用 `chunker.py` 时无临时文件冲突。
- [ ] 对中划线 Slug 格式的 `[[concept-slug]]` 双链进行概念重构时，链接可以被正确更新。
- [ ] 运行 `skills/wiki_lint/tests/` 下的所有本地自动化测试用例，结果 must 全部为 `PASS`：
  - `test-structure.sh`
  - `test-local-cli-lint.sh`
- [ ] 工作区在执行完毕后无任何多余临时文件或修改残留，保持干净。
