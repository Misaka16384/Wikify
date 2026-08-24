"""
Markdown Builder Module
构建和优化 Markdown 输出
"""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from magi.core.md_blocks import map_prose, normalize_newlines


@dataclass
class Section:
    """文档章节"""
    level: int
    title: str
    content: List[str] = field(default_factory=list)


class MarkdownBuilder:
    """Markdown 构建器"""

    def __init__(self, title: str = ""):
        """
        初始化 Markdown 构建器

        Args:
            title: 文档标题
        """
        self.title = title
        self.sections: List[Section] = []
        self.metadata: Dict[str, Any] = {}

    def add_metadata(self, key: str, value: Any) -> None:
        """添加元数据"""
        self.metadata[key] = value

    def add_page_content(self, page_number: int, content: str) -> None:
        """
        添加页面内容

        Args:
            page_number: 页码
            content: Markdown 内容
        """
        # 添加页面分隔注释
        if page_number > 1:
            self.sections.append(Section(
                level=0,
                title=f"<!-- Page {page_number} -->",
                content=[content]
            ))
        else:
            self.sections.append(Section(
                level=0,
                title="",
                content=[content]
            ))

    def build(self, include_metadata: bool = True) -> str:
        """
        构建完整的 Markdown 文档

        Args:
            include_metadata: 是否包含 YAML front matter

        Returns:
            Markdown 文本
        """
        parts = []

        # 添加 YAML front matter
        if include_metadata and self.metadata:
            parts.append("---")
            for key, value in self.metadata.items():
                parts.append(f"{key}: {value}")
            parts.append("---")
            parts.append("")

        # 添加标题
        if self.title:
            parts.append(f"# {self.title}")
            parts.append("")

        # 添加内容
        for section in self.sections:
            if section.title and not section.title.startswith("<!--"):
                parts.append(f"{'#' * section.level} {section.title}")
                parts.append("")
            for content in section.content:
                parts.append(content)
                parts.append("")

        return "\n".join(parts)


class MarkdownCleaner:
    """Markdown 清理和优化器"""

    def clean(self, markdown: str) -> str:
        """
        清理和优化 Markdown 文本

        Args:
            markdown: 原始 Markdown 文本

        Returns:
            清理后的 Markdown 文本
        """
        # 先统一换行符：下面每一条规则都按 `\n` 推理，而 Windows 上的 `\r`
        # 正好落在"一行最后一个字符"和换行之间——`([^\n])\s*\$\$` 这类模式
        # 找的就是那个位置。
        text = normalize_newlines(markdown)

        # 移除多余的空行（超过2个连续空行）
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 修复常见的 LaTeX 公式问题
        text = self._fix_latex(text)

        # 修复图片链接
        text = self._fix_image_links(text)

        # 清理特殊字符
        text = self._clean_special_chars(text)

        return text.strip()

    def _fix_latex(self, text: str) -> str:
        """给行间公式前后补空行——但绝不在表格行或代码块里。

        `$$` 到处都是行间公式的定界符，唯独在表格单元格里不是（单元格装不下
        一个行间公式块），在 fenced code block 里也不是（那里的字面意思就是
        字面意思）。在这两处插空行都是**把一行劈成两行**。

        实测：模型吐出的 49 行表有 53 个 pipe 行，进到文件里变成 **72** 个——
        19 行单元格里带着一个多余 `$$` 的表格行，每一行都被劈开了。出来是一张
        读着很整齐、而且带着文档里根本不存在的行的表。**这正是本管线存在的
        理由所指的那种失败**，而且它在最后一步、在所有门后面发生。

        受保护块的切分交给 `core.md_blocks`：这个判断本来在这里和
        `format_math` 各写了一份，而**这一份认表格不认代码块，那一份反过来**——
        各自漏掉的正好是对方有的。

        逐块处理而不是逐行：非表格的连续行仍然当成一整块，`$$` 跨行的匹配
        因此保持原来的行为。
        """
        def fix(block: str) -> str:
            block = re.sub(r'([^\n])\s*\$\$', r'\1\n\n$$', block)
            return re.sub(r'\$\$\s*([^\n])', r'$$\n\n\1', block)

        # 修复常见的 LaTeX 错误
        # Note: removed aggressive \int_N heuristic — it corrupts legitimate text like "int 10"

        return map_prose(text, fix)

    def _fix_image_links(self, text: str) -> str:
        """修复图片链接"""
        # 确保图片链接格式正确
        text = re.sub(r'!\[\s*\]', '![Figure]', text)

        return text

    def _clean_special_chars(self, text: str) -> str:
        """清理特殊字符"""
        # 移除零宽字符
        text = text.replace('\u200b', '')
        text = text.replace('\ufeff', '')

        return text


class FormulaFormatter:
    """公式格式化器"""

    def format_inline_formula(self, formula: str) -> str:
        """格式化行内公式"""
        formula = formula.strip()
        # 确保使用单个美元符号
        if formula.startswith('$$') and formula.endswith('$$'):
            formula = formula[1:-1]
        elif not formula.startswith('$'):
            formula = f'${formula}$'
        return formula

    def format_display_formula(self, formula: str) -> str:
        """格式化独立公式"""
        formula = formula.strip()
        # 确保使用双美元符号
        if not formula.startswith('$$'):
            formula = f'$${formula}$$'
        if not formula.endswith('$$'):
            formula = f'{formula}$$'
        return formula

    def extract_formulas(self, markdown: str) -> List[Dict[str, str]]:
        """
        从 Markdown 中提取所有公式

        Args:
            markdown: Markdown 文本

        Returns:
            公式列表，每个包含 type 和 content
        """
        formulas = []

        # 提取独立公式
        display_pattern = r'\$\$(.*?)\$\$'
        for match in re.finditer(display_pattern, markdown, re.DOTALL):
            formulas.append({
                "type": "display",
                "content": match.group(1).strip(),
                "full_match": match.group(0)
            })

        # 提取行内公式（排除已经在独立公式中的）
        inline_pattern = r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)'
        for match in re.finditer(inline_pattern, markdown):
            # 检查是否在独立公式中
            in_display = False
            for f in formulas:
                if match.start() >= markdown.find(f["full_match"]) and \
                   match.end() <= markdown.find(f["full_match"]) + len(f["full_match"]):
                    in_display = True
                    break

            if not in_display:
                formulas.append({
                    "type": "inline",
                    "content": match.group(1).strip(),
                    "full_match": match.group(0)
                })

        return formulas


class TableFormatter:
    """表格格式化器"""

    def format_table(self, table_data: List[List[str]]) -> str:
        """
        将二维数据格式化为 Markdown 表格

        Args:
            table_data: 表格数据，第一行为表头

        Returns:
            Markdown 表格字符串
        """
        if not table_data:
            return ""

        # 计算每列最大宽度
        col_count = max(len(row) for row in table_data)
        widths = [0] * col_count

        for row in table_data:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))

        # 构建表格
        lines = []

        # 表头
        header = table_data[0]
        header_line = "| " + " | ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(header)) + " |"
        lines.append(header_line)

        # 分隔线
        separator = "|" + "|".join("-" * (w + 2) for w in widths) + "|"
        lines.append(separator)

        # 数据行
        for row in table_data[1:]:
            row_line = "| " + " | ".join(str(cell).ljust(widths[i]) if i < len(row) else "".ljust(widths[i])
                                         for i in range(col_count)) + " |"
            lines.append(row_line)

        return "\n".join(lines)


if __name__ == "__main__":
    builder = MarkdownBuilder("Test Document")
    builder.add_page_content(1, "# Introduction\n\nThis is a test.")
    print(builder.build())
