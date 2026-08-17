"""
PDF to Markdown Agent
学术论文 PDF 转 Markdown 的主程序

使用方法:
    python agent.py <pdf_path> [output_dir]

示例:
    python agent.py paper.pdf
    python agent.py paper.pdf ./output
"""

import os
import sys
import time
import argparse
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

# 添加当前目录和 bin/ 目录到 path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from pdf_processor import PDFProcessor, PDFPage
from ocr_engine import OCREngine, OCRResult
from image_handler import ImageHandler, ExtractedImage
from markdown_builder import MarkdownBuilder, MarkdownCleaner
from figure_extractor import extract_figures, inject_figures
from config_loader import load_config, get as cfg_get

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class ConversionResult:
    """转换结果"""
    success: bool
    markdown_path: str
    images_dir: str
    pages_processed: int
    errors: List[str]


class PDF2MarkdownAgent:
    """PDF 转 Markdown Agent"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Agent

        Args:
            config_path: 配置文件路径，默认使用同目录下的 config.yaml
        """
        self.config = self._load_config(config_path)
        self._setup_components()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """加载统一配置"""
        unified = load_config(config_path)

        # 将统一配置映射为 agent 内部期望的结构
        return {
            "ocr": {
                "model": cfg_get(unified, "models.ocr", "glm-ocr"),
                "ollama_base_url": cfg_get(unified, "ollama.base_url", "http://127.0.0.1:11434"),
                "timeout": cfg_get(unified, "ocr.timeout", 180),
                "dpi": cfg_get(unified, "ocr.dpi", 150),
            },
            "pdf": {
                "pdftoppm_path": cfg_get(unified, "tools.pdftoppm_path", ""),
                "pdfimages_path": cfg_get(unified, "tools.pdfimages_path", ""),
                "image_format": cfg_get(unified, "pdf.image_format", "png"),
                "quality": cfg_get(unified, "pdf.quality", 100),
            },
            "image": {
                "output_folder": cfg_get(unified, "output.image_folder", "images"),
                "formats": ["png", "jpg", "jpeg", "svg"],
            },
            "output": {
                "keep_temp_images": cfg_get(unified, "output.keep_temp_images", False),
                "encoding": cfg_get(unified, "output.encoding", "utf-8"),
            },
        }

    def _setup_components(self):
        """初始化各组件"""
        ocr_config = self.config.get("ocr", {})
        pdf_config = self.config.get("pdf", {})
        image_config = self.config.get("image", {})

        self.pdf_processor = PDFProcessor(
            pdftoppm_path=pdf_config.get("pdftoppm_path", ""),
            dpi=ocr_config.get("dpi", 150),
            image_format=pdf_config.get("image_format", "png")
        )

        self.ocr_engine = OCREngine(
            model=ocr_config.get("model", "glm-ocr"),
            base_url=ocr_config.get("ollama_base_url", "http://127.0.0.1:11434"),
            timeout=ocr_config.get("timeout", 180)
        )

        self.image_handler = ImageHandler(
            output_folder=image_config.get("output_folder", "images"),
            pdfimages_path=pdf_config.get("pdfimages_path", "")
        )

        self.markdown_cleaner = MarkdownCleaner()

    def convert(
        self,
        pdf_path: str,
        output_dir: Optional[str] = None,
        title: Optional[str] = None
    ) -> ConversionResult:
        """
        执行 PDF 到 Markdown 的转换

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录，默认为 PDF 同目录下的 output 文件夹
            title: 文档标题，默认使用 PDF 文件名

        Returns:
            转换结果
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 设置输出目录
        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_md"
        else:
            output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 设置标题
        if title is None:
            title = pdf_path.stem

        # 文档 slug（同时用于 Markdown 文件名与图片前缀，避免多篇论文图片重名冲突）
        import re as _re
        safe_title = _re.sub(r'[^\w]+', '-', title, flags=_re.UNICODE).strip('-').lower() or "document"
        today_str = datetime.now().strftime('%Y-%m-%d')
        doc_stem = f"{today_str}-{safe_title}"

        # 创建临时目录
        temp_dir = output_dir / ".temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 创建图片目录
        images_dir = output_dir / self.config["image"]["output_folder"]
        images_dir.mkdir(parents=True, exist_ok=True)

        errors = []

        try:
            # Step 1: 检查 OCR 模型
            console.print(Panel("[bold blue]Step 1: 检查环境[/bold blue]", expand=False))
            if not self.ocr_engine.check_model_available():
                raise RuntimeError(f"OCR 模型 {self.ocr_engine.model} 不可用，请先通过 'ollama pull {self.ocr_engine.model}' 下载")
            
            # 检查模型是否已加载，显示模型信息
            loaded, model_info = self.ocr_engine.is_model_loaded()
            model_detail = self.ocr_engine.get_model_info()
            size_gb = model_detail.get("size", 0) / (1024**3) if model_detail else 0
            
            if loaded:
                vram_gb = model_info.get("size_vram", 0) / (1024**3) if model_info else 0
                console.print(f"[green]✓[/green] OCR 模型 {self.ocr_engine.model} 已加载 ({vram_gb:.1f}GB VRAM)")
            else:
                console.print(f"[yellow]⚡[/yellow] OCR 模型 {self.ocr_engine.model} 未加载 ({size_gb:.1f}GB)，首次OCR可能需要等待模型加载...")
                if size_gb > 3:
                    console.print(f"[dim]  提示: 大模型首次加载可能需要30-60秒，请耐心等待[/dim]")

            # Step 2: PDF 转图片
            console.print(Panel("[bold blue]Step 2: PDF 转换为图片[/bold blue]", expand=False))
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("正在转换 PDF...", total=None)
                pages = self.pdf_processor.convert_to_images(str(pdf_path), str(temp_dir))
                progress.update(task, description=f"[green]✓[/green] 已转换 {len(pages)} 页")

            # Step 3: OCR 处理
            console.print(Panel("[bold blue]Step 3: OCR 识别[/bold blue]", expand=False))
            ocr_results = []
            total_ocr_time = 0
            page_times = []

            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("OCR 处理中", total=len(pages))

                for page in pages:
                    progress.update(task, description=f"OCR 处理第 {page.page_number}/{len(pages)} 页")
                    
                    cache_path = temp_dir / f"page_{page.page_number}.json"
                    
                    # Try to load from cache
                    if cache_path.exists():
                        try:
                            import json
                            with open(cache_path, "r", encoding="utf-8") as f:
                                cache_data = json.load(f)
                            if cache_data.get("success", False):
                                result = OCRResult(
                                    page_number=cache_data["page_number"],
                                    raw_text=cache_data["raw_text"],
                                    markdown=cache_data["markdown"],
                                    formulas=cache_data.get("formulas", []),
                                    figures=cache_data.get("figures", []),
                                    tables=cache_data.get("tables", []),
                                    success=True,
                                    error_message=""
                                )
                                console.print(f"[dim]  第 {page.page_number} 页完成 (从缓存加载)[/dim]")
                                ocr_results.append(result)
                                progress.advance(task)
                                continue
                        except Exception as e:
                            console.print(f"[yellow]  加载第 {page.page_number} 页缓存失败: {e}，将重新 OCR[/yellow]")
                    
                    start_time = time.time()
                    # 使用带有重试机制的 OCR 方法，最大重试 2 次
                    result = self.ocr_engine.ocr_image_with_retry(page.image_path, page.page_number, max_retries=2)
                    elapsed = time.time() - start_time
                    total_ocr_time += elapsed
                    page_times.append((page.page_number, elapsed))
                    
                    # Save to cache if successful
                    if result.success:
                        try:
                            import json
                            with open(cache_path, "w", encoding="utf-8") as f:
                                json.dump({
                                    "page_number": result.page_number,
                                    "raw_text": result.raw_text,
                                    "markdown": result.markdown,
                                    "formulas": result.formulas,
                                    "figures": result.figures,
                                    "tables": result.tables,
                                    "success": result.success,
                                    "error_message": result.error_message
                                }, f, ensure_ascii=False, indent=2)
                        except Exception as e:
                            console.print(f"[yellow]  写入第 {page.page_number} 页缓存失败: {e}[/yellow]")
                    
                    ocr_results.append(result)

                    if not result.success:
                        errors.append(f"第 {page.page_number} 页 OCR 失败: {result.error_message}")
                        console.print(f"[red]  第 {page.page_number} 页失败: {result.error_message}[/red]")
                    else:
                        # 显示每页耗时
                        status = "首次加载" if elapsed > 15 else "正常"
                        console.print(f"[dim]  第 {page.page_number} 页完成: {elapsed:.1f}秒 ({status})[/dim]")

                    progress.advance(task)
            
            # 显示OCR统计
            avg_time = total_ocr_time / len(pages) if pages else 0
            console.print(f"[green]✓[/green] OCR 完成，总耗时 {total_ocr_time:.1f}秒，平均 {avg_time:.1f}秒/页")

            # Step 4: 提取图表（按标题锚定裁剪页面区域，矢量图/位图通用）
            console.print(Panel("[bold blue]Step 4: 提取图表[/bold blue]", expand=False))
            figures = extract_figures(str(pdf_path), str(images_dir), prefix=doc_stem)
            figures_by_page = {}
            for fig in figures:
                figures_by_page.setdefault(fig.page, []).append(fig)
            labeled = sum(1 for f in figures if f.label)
            console.print(f"[green]✓[/green] 提取了 {len(figures)} 张图表（{labeled} 张带标题）")

            # Step 5: 构建 Markdown
            console.print(Panel("[bold blue]Step 5: 生成 Markdown[/bold blue]", expand=False))
            builder = MarkdownBuilder(title)
            builder.add_metadata("source", str(pdf_path.name))
            builder.add_metadata("converted", datetime.now().isoformat())
            builder.add_metadata("pages", len(pages))

            img_folder = self.config["image"]["output_folder"]
            for result in ocr_results:
                cleaned_content = self.markdown_cleaner.clean(result.markdown)
                page_figs = figures_by_page.get(result.page_number, [])
                if page_figs:
                    cleaned_content = inject_figures(cleaned_content, page_figs, img_folder)
                builder.add_page_content(result.page_number, cleaned_content)

            # 保存 Markdown（slug 已在前面计算）
            slug_name = f"{doc_stem}.md"
            md_path = output_dir / slug_name
            
            markdown_content = builder.build(include_metadata=False)
            
            # 注入 YAML Frontmatter
            fm = {"title": title, "source": pdf_path.name, "type": "papers", "ingested": today_str, "tags": [], "summary": ""}
            yaml_frontmatter = "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, default_flow_style=False) + "---\n\n"
            final_content = yaml_frontmatter + markdown_content

            with open(md_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            console.print(f"[green]✓[/green] Markdown 已保存: {md_path}")

            # Step 6: 清理临时文件
            if not self.config["output"].get("keep_temp_images", False):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)

            # 显示结果摘要
            self._display_summary(ocr_results, md_path, images_dir)

            return ConversionResult(
                success=True,
                markdown_path=str(md_path),
                images_dir=str(images_dir),
                pages_processed=len(pages),
                errors=errors
            )

        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:
            console.print(f"[red]✗ 转换失败: {e}[/red]")
            return ConversionResult(
                success=False,
                markdown_path="",
                images_dir="",
                pages_processed=0,
                errors=[str(e)]
            )

    def _display_summary(self, results: List[OCRResult], md_path: Path, images_dir: Path):
        """显示转换摘要"""
        table = Table(title="转换摘要")
        table.add_column("项目", style="cyan")
        table.add_column("值", style="green")

        total_pages = len(results)
        success_pages = sum(1 for r in results if r.success)

        table.add_row("总页数", str(total_pages))
        table.add_row("成功处理", str(success_pages))
        table.add_row("失败页数", str(total_pages - success_pages))
        table.add_row("输出文件", str(md_path.name))
        table.add_row("图片目录", str(images_dir.name))

        console.print(table)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PDF 转 Markdown Agent - 将学术论文 PDF 转换为 Markdown 格式"
    )
    parser.add_argument(
        "pdf_path",
        help="PDF 文件路径"
    )
    parser.add_argument(
        "-o", "--output",
        help="输出目录（默认为 PDF 同目录下的 {filename}_md 文件夹）",
        default=None
    )
    parser.add_argument(
        "-t", "--title",
        help="文档标题（默认使用 PDF 文件名）",
        default=None
    )
    parser.add_argument(
        "-c", "--config",
        help="配置文件路径",
        default=None
    )

    args = parser.parse_args()

    # 创建 Agent
    agent = PDF2MarkdownAgent(config_path=args.config)

    # 执行转换
    result = agent.convert(
        pdf_path=args.pdf_path,
        output_dir=args.output,
        title=args.title
    )

    if result.success:
        console.print("\n[bold green]✓ 转换完成！[/bold green]")
        console.print(f"  Markdown: {result.markdown_path}")
        console.print(f"  图片目录: {result.images_dir}")
        if result.errors:
            console.print(f"\n[yellow]警告: 有 {len(result.errors)} 个错误[/yellow]")
    else:
        console.print("\n[bold red]✗ 转换失败[/bold red]")
        for error in result.errors:
            console.print(f"  - {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
