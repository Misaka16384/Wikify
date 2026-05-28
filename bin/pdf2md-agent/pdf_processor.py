"""
PDF Processor Module
使用 pdftoppm 将 PDF 转换为高分辨率图片
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class PDFPage:
    """PDF 页面信息"""
    page_number: int
    image_path: str
    width: int
    height: int


class PDFProcessor:
    """PDF 处理器，负责将 PDF 转换为图片"""

    def __init__(self, pdftoppm_path: str = "", dpi: int = 300, image_format: str = "png"):
        """
        初始化 PDF 处理器

        Args:
            pdftoppm_path: pdftoppm 可执行文件路径，空则使用 PATH 中的
            dpi: 输出图片 DPI
            image_format: 输出图片格式 (png, jpg, tiff)
        """
        self.pdftoppm_path = pdftoppm_path or self._find_pdftoppm()
        self.dpi = dpi
        self.image_format = image_format.lower()

        if not self.pdftoppm_path:
            raise RuntimeError("pdftoppm 未找到，请确保 texlive 已安装并添加到 PATH")

    def _find_pdftoppm(self) -> str:
        """查找 pdftoppm 可执行文件"""
        # 1. 检查环境变量
        env_path = os.environ.get("PDFTOPPM_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        # 2. 优先使用 PATH 中的 pdftoppm
        result = shutil.which("pdftoppm")
        if result:
            return result

        # 3. Linux / macOS 常见路径
        unix_paths = [
            "/usr/bin/pdftoppm",
            "/usr/local/bin/pdftoppm",
        ]
        for path in unix_paths:
            if os.path.exists(path):
                return path

        # 4. Windows 常见路径 (fallback)
        common_paths = [
            r"D:\texlive\2024\bin\windows\pdftoppm.exe",
            r"C:\texlive\2024\bin\windows\pdftoppm.exe",
            r"D:\texlive\2023\bin\windows\pdftoppm.exe",
            r"C:\texlive\2023\bin\windows\pdftoppm.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

        return ""

    def convert_to_images(self, pdf_path: str, output_dir: str) -> List[PDFPage]:
        """
        将 PDF 转换为图片

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录

        Returns:
            页面信息列表
        """
        pdf_path = Path(pdf_path).resolve()
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

        # 构建输出文件前缀
        output_prefix = output_dir / "page"

        # 构建 pdftoppm 命令
        cmd = [
            self.pdftoppm_path,
            f"-{self.image_format}",
            "-r", str(self.dpi),
            str(pdf_path),
            str(output_prefix)
        ]

        # 执行转换
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"pdftoppm 转换失败: {result.stderr}")

        # 收集生成的图片
        pages = []
        pattern = f"page-*.{self.image_format}"
        image_files = sorted(output_dir.glob(pattern))

        for idx, img_path in enumerate(image_files, start=1):
            # 获取图片尺寸
            from PIL import Image
            with Image.open(img_path) as img:
                width, height = img.size

            pages.append(PDFPage(
                page_number=idx,
                image_path=str(img_path),
                width=width,
                height=height
            ))

        return pages

    def get_page_count(self, pdf_path: str) -> int:
        """获取 PDF 页数"""
        # 使用 pdfinfo 或通过转换获取
        pdfinfo_name = Path(self.pdftoppm_path).name.replace("pdftoppm", "pdfinfo")
        pdfinfo_path = str(Path(self.pdftoppm_path).parent / pdfinfo_name)
        if os.path.exists(pdfinfo_path):
            result = subprocess.run(
                [pdfinfo_path, pdf_path],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.split("\n"):
                if line.startswith("Pages:"):
                    try:
                        page_count = int(line.split(":")[1].strip())
                    except (ValueError, IndexError) as e:
                        print(f"Warning: failed to parse page count: {e}", file=sys.stderr)
                        page_count = 0
                    return page_count

        # 备用方法：通过转换第一页来验证文件有效
        return -1  # 未知页数


if __name__ == "__main__":
    # 测试
    processor = PDFProcessor()
    print(f"pdftoppm 路径: {processor.pdftoppm_path}")
