# Wikify v0.4 — 安全加固 · 鲁棒性重构 · 性能优化

> 本版本基于对全部 15 个 bin 脚本和 14 个 SKILL.md 的全面审计结果，修复了 **3 个安全漏洞**、**12 个鲁棒性缺陷**和 **6 个性能瓶颈**。同时完成了代码源统一，消除了长期存在的 `.agents/` 副本漂移问题。

## ⚠️ 破坏性变更

- **`install.ps1` 不再硬编码部署目标**。现在需要用户通过参数指定目标目录：
  ```powershell
  .\install.ps1 -Target "D:\文档\MindPalace\.agents"
  ```
- **`.agents/` 子目录已从仓库中移除**。根目录 `bin/` 和 `skills/` 现在是唯一代码源。
- **`requirements.txt` 移除了未使用的依赖** `pydantic` 和 `pdf2image`。如果你的环境依赖它们，请手动安装。
- **graph 数据库的 `node_id` 格式已变更**：从文件名 stem（如 `foo`）改为相对路径（如 `wiki/concepts/foo`），避免跨子目录的 ID 碰撞。使用 `query-graph.py` 查询的 SQL 可能需要更新。

---

## 🔒 安全修复

| 文件 | 漏洞 | 修复方式 |
|------|------|----------|
| `tex2md.py` | tar 路径穿越攻击 (CVE-2007-4559) | 提取前逐成员校验路径 + Python 3.12 `filter='data'` |
| `ingest_pipeline.py` | `shell=True` 命令注入 | 改为列表形式 `subprocess.run`，消除 shell 解释 |
| `query-graph.py` | SQLite 数据库可被任意写入 | `file:?mode=ro` 只读 URI + `PRAGMA query_only=ON` |

## 🛡️ 鲁棒性改进

### 核心引擎 (`llm-wiki.py`)
- **CRLF 兼容**：`read_document()` 和 `split_markdown_frontmatter()` 现在自动处理 Windows 行尾
- **YAML 解析升级**：`yaml.safe_load` 作为主解析器（处理嵌套对象、多行字符串），自定义解析器降级为兜底方案
- **Unicode slug**：`slugify()` 现在保留中日韩字符（`\w` + `re.UNICODE`）
- **模糊标题匹配**：`check_body_structure()` 使用正则匹配，容忍 `## Key Contributions` 与 `## 1. Key Contributions` 的差异
- **误报抑制**：`check_wikilinks_formatting()` 收窄 LaTeX 检测条件，不再对含 `=` 或 `+` 的合法链接报警

### 辅助脚本
- `format_math.py`：修复 LaTeX 环境正则替换中的反斜杠转义错误，使用原始反向引用
- `tag_reducer.py`：删除死代码（无用的 `sys.path.append`），`re.escape()` 防止字段名被误解释为正则
- `validate-output.py`：`split_frontmatter()` 添加 CRLF 规范化
- `verify_claims.py`：删除未使用的 `urllib` 导入；web 类型来源诚实标记为 `[URL-FORMAT-OK]` 而非 `[VERIFIED]`
- `search-wiki.py`：`errors='replace'` 替代 `errors='ignore'`；新增 `MAX_RESULTS=200` 防止内存溢出
- `index_builder.py`：`fm.get('tags') or []` 防御 YAML null 覆盖默认值
- `extract_concept_context.py`：`os.listdir` 前添加目录存在性检查
- `refactor_concept.py`：`os.walk` 跳过 `.backup`、`.obsidian` 等点目录
- `add_concept.py`：模板替换从 `str.replace("Concept Name")` 改为 `re.sub('^# Concept Name$')`，避免贪婪替换正文内容
- `tex2md.py`：`exit(1)` → `sys.exit(1)`

### pdf2md-agent
- **修复双重 frontmatter**：`builder.build(include_metadata=False)` + agent 注入自己的 YAML，不再产生两套 frontmatter
- `ocr_engine.py`：`size_gb` 在模型信息缺失时返回 `0` 而非字符串 `"未知"`（修复 `.1f` 格式化崩溃）
- `pdf_processor.py`：所有 `subprocess.run` 添加 `timeout=300`；`pdfinfo` 路径推导改为 basename 替换
- `markdown_builder.py`：移除误伤正常文本的 `\int_N` 启发式规则

## ⚡ 性能优化

- **靶向目录遍历**：`content_markdown_files()` 只扫描 `raw/`、`wiki/`、`inventory/`、`datasets/`，跳过 `.git/`、`.obsidian/` 等无关目录
- **减少冗余加载**：`run_lint()` 中第二次 `load_documents()` 仅在 `--fix` 模式下执行
- **消除重复读盘**：`Document.raw_text` 字段缓存已读内容，`check_links` 和 `check_wikilinks` 不再重新读文件
- **批量 SQL 写入**：`run_graph()` 使用 `executemany` 批量插入替代逐行 `execute`
- **索引检查范围收窄**：`check_index_consistency()` 只遍历已知根目录下的子目录

## 📝 SKILL.md 标准化

- 6 个缺少错误处理指导的 Skill 新增 `## Error Handling` 段落
- `wiki_graph_index`：添加 `<TOPIC_DIR>` 参数，将 `sqlite3` 直接查询替换为 `query-graph.py`
- `wiki_lint`：添加 `<TOPIC_DIR>` 参数
- `wiki_ingest_ocr`：修复反斜杠路径 `pdf2md-agent\agent.py` → `pdf2md-agent/agent.py`
- `wiki_enrich`：修复过时引用 `concept_builder.py` → `index_builder.py`
- `wiki_semantic_link`：新增前置条件说明（`ollama pull`、`numpy`、`scikit-learn`）
- 删除 3 个空的 `scripts/` 占位目录

## 🏗️ 部署体系

- `install.ps1`：接受用户参数指定目标目录，支持项目级部署
- `requirements.txt`：每个依赖标注用途，移除未使用的 `pydantic` 和 `pdf2image`
- `.gitignore`：添加 `.agents/` 和 `*.lock` 规则
- 仓库内 `.agents/` 副本已删除，部署目录中嵌套的 `.agents/.agents/`（103MB）已清理

---

**完整变更统计**：46 个文件变更，+1742 / -507 行
