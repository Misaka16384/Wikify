"""
Image Handler Module
处理 PDF 中的图片提取和图表截图
"""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from PIL import Image


@dataclass
class ExtractedImage:
    """提取的图片信息"""
    index: int
    original_path: str
    output_path: str
    description: str = ""
    figure_type: str = "figure"  # figure, table, equation


class ImageHandler:
    """图片处理器，负责提取和处理 PDF 中的图片"""

    def __init__(self, output_folder: str = "images", pdfimages_path: str = ""):
        """
        初始化图片处理器

        Args:
            output_folder: 图片输出子文件夹名称
            pdfimages_path: pdfimages 可执行文件路径，空则使用 PATH 中的
        """
        self.output_folder = output_folder
        self.pdfimages_path = pdfimages_path or self._find_pdfimages()

    def setup_output_dir(self, base_dir: str) -> Path:
        """创建图片输出目录"""
        output_path = Path(base_dir) / self.output_folder
        output_path.mkdir(parents=True, exist_ok=True)
        return output_path

    def extract_images_from_pdf(
        self,
        pdf_path: str,
        output_dir: str,
        prefix: str = "fig"
    ) -> List[ExtractedImage]:
        """
        从 PDF 中提取嵌入图片

        使用 pdfimages 工具提取图片

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录
            prefix: 文件名前缀

        Returns:
            提取的图片列表
        """
        pdf_path = Path(pdf_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        images = []

        # 查找 pdfimages 工具
        pdfimages_path = self.pdfimages_path
        if not pdfimages_path:
            print("警告: pdfimages 未找到，跳过图片提取")
            return images

        # 构建 pdfimages 命令
        # -all 提取所有图片，包括嵌入的
        output_prefix = output_dir / prefix
        cmd = [
            pdfimages_path,
            "-all",
            str(pdf_path),
            str(output_prefix)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"pdfimages 警告: {result.stderr}")
        except Exception as e:
            print(f"图片提取失败: {e}")
            return images

        # 收集提取的图片
        for img_path in output_dir.glob(f"{prefix}-*"):
            if img_path.suffix.lower() in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
                # 提取索引号
                match = re.search(rf"{prefix}-(\d+)", img_path.name)
                idx = int(match.group(1)) if match else len(images) + 1

                images.append(ExtractedImage(
                    index=idx,
                    original_path=str(img_path),
                    output_path=str(img_path),
                    figure_type="figure"
                ))

        return sorted(images, key=lambda x: x.index)

    def _find_pdfimages(self) -> str:
        """查找 pdfimages 工具"""
        # 1. 检查环境变量
        env_path = os.environ.get("PDFIMAGES_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        # 2. 优先使用 PATH 中的 pdfimages
        result = shutil.which("pdfimages")
        if result:
            return result

        # 3. Linux / macOS 常见路径
        unix_paths = [
            "/usr/bin/pdfimages",
            "/usr/local/bin/pdfimages",
        ]
        for path in unix_paths:
            if os.path.exists(path):
                return path

        # 4. Windows 常见路径 (fallback)
        common_paths = [
            r"D:\texlive\2024\bin\windows\pdfimages.exe",
            r"C:\texlive\2024\bin\windows\pdfimages.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return ""

    def process_page_screenshots(
        self,
        page_images: List[str],
        output_dir: str,
        regions: List[Dict[str, Any]] = None
    ) -> List[ExtractedImage]:
        """
        处理页面截图，提取特定区域

        Args:
            page_images: 页面图片路径列表
            output_dir: 输出目录
            regions: 要提取的区域列表，每个区域包含 page, x, y, width, height

        Returns:
            提取的图片列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        images = []

        for idx, region in enumerate(regions or []):
            page_idx = region.get("page", 1) - 1
            if page_idx >= len(page_images):
                continue

            try:
                with Image.open(page_images[page_idx]) as img:
                    # 计算裁剪区域
                    x, y = region.get("x", 0), region.get("y", 0)
                    w, h = region.get("width", img.width), region.get("height", img.height)

                    # 裁剪图片
                    cropped = img.crop((x, y, x + w, y + h))

                    # 保存
                    output_path = output_dir / f"fig_{idx + 1}.png"
                    cropped.save(output_path)

                    images.append(ExtractedImage(
                        index=idx + 1,
                        original_path=page_images[page_idx],
                        output_path=str(output_path),
                        description=region.get("description", ""),
                        figure_type=region.get("type", "figure")
                    ))

            except Exception as e:
                print(f"截图处理失败: {e}")
                continue

        return images

    def extract_figure_regions_from_markdown(
        self,
        markdown: str
    ) -> List[Dict[str, Any]]:
        """
        从 Markdown 中提取图表区域信息

        Args:
            markdown: Markdown 文本

        Returns:
            区域信息列表
        """
        regions = []

        # 匹配图片占位符 ![描述](images/fig_X.png)
        pattern = r'!\[(.*?)\]\(images/fig_\d+\.png\)'
        for match in re.finditer(pattern, markdown):
            regions.append({
                "type": "figure",
                "description": match.group(1)
            })

        return regions

    def optimize_image(
        self,
        image_path: str,
        max_width: int = 1200,
        quality: int = 85
    ) -> str:
        """
        优化图片大小

        Args:
            image_path: 图片路径
            max_width: 最大宽度
            quality: JPEG 质量

        Returns:
            优化后的图片路径
        """
        path = Path(image_path)
        with Image.open(path) as img:
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.LANCZOS)

            # 保存优化后的图片
            output_path = path.with_suffix(".optimized.png")
            img.save(output_path, "PNG", optimize=True)

            # 替换原文件
            output_path.replace(path)

        return str(path)


class FigureDetector:
    """图表检测器，用于检测页面中的图表区域"""

    def detect_figures(self, image_path: str) -> List[Dict[str, Any]]:
        """
        检测图片中的图表区域

        Args:
            image_path: 图片路径

        Returns:
            检测到的区域列表
        """
        # 这里可以使用 OpenCV 或其他方法检测图表区域
        # 目前返回空列表，可以后续扩展
        return []

    def detect_tables(self, image_path: str) -> List[Dict[str, Any]]:
        """
        检测图片中的表格区域

        Args:
            image_path: 图片路径

        Returns:
            检测到的表格区域列表
        """
        # 表格检测逻辑
        return []

    def detect_equations(self, image_path: str) -> List[Dict[str, Any]]:
        """
        检测图片中的公式区域

        Args:
            image_path: 图片路径

        Returns:
            检测到的公式区域列表
        """
        # 公式检测逻辑
        return []


if __name__ == "__main__":
    handler = ImageHandler()
    print("ImageHandler 初始化成功")
