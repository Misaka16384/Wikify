"""
OCR Engine Module
通过 Ollama API 调用视觉模型进行 OCR

支持的模型:
- glm-ocr: 专门的 OCR 模型，需要特定配置（较大 context size）
- qwen3-vl 系列: 通用视觉语言模型，OCR 能力优秀
"""

import base64
import io
import json
import sys
import time
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from PIL import Image


@dataclass
class OCRResult:
    """OCR 结果"""
    page_number: int
    raw_text: str
    markdown: str
    formulas: List[Dict[str, str]] = field(default_factory=list)
    figures: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error_message: str = ""


class OCREngine:
    """OCR 引擎，通过 Ollama API 调用视觉模型"""

    # 不同模型的最大像素限制
    MODEL_CONFIGS = {
        "glm-ocr": {
            "max_pixels": 2_000_000,  # glm-ocr 限制约 2MP
            "use_chat_api": False,
            "prompt": "Text Recognition:",
            "requires_large_context": True,
        },
        "glm-ocr-16k": {
            "max_pixels": 3_000_000,
            "use_chat_api": False,
            "prompt": "Text Recognition:",
            "requires_large_context": True,
        },
        "qwen3-vl": {
            "max_pixels": 4_000_000,
            "use_chat_api": True,
            "prompt": "Please transcribe all text from this academic paper page. Output in Markdown format with LaTeX for math formulas (inline: $formula$, display: $$formula$$). Keep the original document structure with proper headings.",
            "requires_large_context": False,
        },
        "qwen3-vl:4b": {
            "max_pixels": 3_000_000,
            "use_chat_api": True,
            "prompt": "Transcribe all text from this page to Markdown with LaTeX formulas (inline: $formula$, display: $$formula$$). Keep original structure.",
            "requires_large_context": False,
        },
        "qwen3-vl-fast": {
            "max_pixels": 4_000_000,
            "use_chat_api": True,
            "prompt": "Please transcribe all text from this academic paper page. Output in Markdown format with LaTeX for math formulas. Keep the original document structure.",
            "requires_large_context": False,
        },
    }

    def __init__(
        self,
        model: str = None,
        base_url: str = None,
        timeout: int = 180
    ):
        """
        初始化 OCR 引擎

        Args:
            model: Ollama 模型名称 (glm-ocr, qwen3-vl:4b, qwen3-vl-fast 等)
            base_url: Ollama API 基础 URL
            timeout: API 调用超时时间
        """
        self.model = model or "glm-ocr"
        self.base_url = (base_url or "http://127.0.0.1:11434").rstrip("/")
        self.timeout = timeout

        # 获取模型配置
        self.model_config = self._get_model_config(self.model)

    def _get_model_config(self, model: str) -> Dict:
        """获取模型配置"""
        # 精确匹配
        if model in self.MODEL_CONFIGS:
            return self.MODEL_CONFIGS[model]

        # 前缀匹配
        for key, config in self.MODEL_CONFIGS.items():
            if model.startswith(key):
                return config

        # 默认配置
        return {
            "max_pixels": 3_000_000,
            "use_chat_api": True,
            "prompt": "Transcribe all text from this image to Markdown format.",
            "requires_large_context": False,
        }

    def _preprocess_image(self, image_path: str) -> str:
        """
        预处理图片：调整大小以适应模型限制

        Args:
            image_path: 图片路径

        Returns:
            base64 编码的图片
        """
        max_pixels = self.model_config.get("max_pixels", 3_000_000)

        with Image.open(image_path) as img:
            # 转换为 RGB
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            width, height = img.size
            current_pixels = width * height

            # 如果超过限制，缩小图片
            if current_pixels > max_pixels:
                scale = (max_pixels / current_pixels) ** 0.5
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.LANCZOS)

            # 保存为 JPEG
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=95)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _build_ocr_prompt(self) -> str:
        """获取 OCR 提示词"""
        return self.model_config.get("prompt", "Text Recognition:")

    def ocr_image(self, image_path: str, page_number: int = 1) -> OCRResult:
        """
        对单张图片进行 OCR

        Args:
            image_path: 图片路径
            page_number: 页码

        Returns:
            OCR 结果
        """
        try:
            # 预处理图片
            image_base64 = self._preprocess_image(image_path)
            prompt = self._build_ocr_prompt()

            # 根据模型选择 API
            if self.model_config.get("use_chat_api", True):
                response_text = self._call_chat_api(image_base64, prompt)
            else:
                response_text = self._call_generate_api(image_base64, prompt)

            # 解析结果
            markdown = self._parse_ocr_result(response_text)

            return OCRResult(
                page_number=page_number,
                raw_text=response_text,
                markdown=markdown,
                success=True
            )

        except Exception as e:
            return OCRResult(
                page_number=page_number,
                raw_text="",
                markdown="",
                success=False,
                error_message=str(e)
            )

    def _call_chat_api(self, image_base64: str, prompt: str) -> str:
        """使用 /api/chat 端点（适用于 qwen3-vl 等模型）"""
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64]
                }
            ],
            "stream": False,
            "options": {
                "num_ctx": 8192
            }
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("message", {}).get("content", "")

    def _call_generate_api(self, image_base64: str, prompt: str) -> str:
        """使用 /api/generate 端点（适用于 glm-ocr 模型）"""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_base64],
            "stream": False,
            "options": {
                "num_ctx": 16384,  # glm-ocr 需要较大 context
                "temperature": 0
            }
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        return result.get("response", "")

    def _parse_ocr_result(self, raw_text: str) -> str:
        """解析和清理 OCR 结果"""
        # 清理可能的格式问题
        text = raw_text.strip()

        # 移除可能的开头/结尾标记
        if text.startswith("```markdown"):
            text = text[11:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def ocr_batch(self, image_paths: List[str], start_page: int = 1) -> List[OCRResult]:
        """
        批量 OCR 处理

        Args:
            image_paths: 图片路径列表
            start_page: 起始页码

        Returns:
            OCR 结果列表
        """
        results = []
        for idx, image_path in enumerate(image_paths, start=start_page):
            result = self.ocr_image(image_path, idx)
            results.append(result)
        return results

    def check_model_available(self) -> bool:
        """检查模型是否可用（已下载）"""
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return any(self.model in name for name in model_names)
        except Exception as e:
            print(f"Warning: check_model_available failed: {e}", file=sys.stderr)
        return False

    def is_model_loaded(self) -> Tuple[bool, Optional[Dict]]:
        """
        检查模型是否已加载到内存（GPU/VRAM）
        
        Returns:
            (是否已加载, 模型信息字典)
        """
        try:
            url = f"{self.base_url}/api/ps"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for m in models:
                    if self.model in m.get("name", ""):
                        return True, m
        except Exception as e:
            print(f"Warning: is_model_loaded failed: {e}", file=sys.stderr)
        return False, None

    def get_model_info(self) -> Optional[Dict]:
        """获取模型详细信息（包括大小）"""
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                models = response.json().get("models", [])
                for m in models:
                    if self.model in m.get("name", ""):
                        return m
        except Exception as e:
            print(f"Warning: get_model_info failed: {e}", file=sys.stderr)
        return None

    def warmup(self, timeout: int = 300) -> Tuple[bool, str]:
        """
        预热模型（将模型加载到内存）
        
        Args:
            timeout: 预热超时时间（秒）
            
        Returns:
            (是否成功, 消息)
        """
        loaded, info = self.is_model_loaded()
        if loaded:
            size_gb = info.get("size_vram", 0) / (1024**3)
            return True, f"模型已加载 ({size_gb:.1f}GB VRAM)"

        # 获取模型大小
        model_info = self.get_model_info()
        size_gb = model_info.get("size", 0) / (1024**3) if model_info else 0
        
        # 发送一个简单请求来加载模型
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": "warmup",
                "stream": False,
                "keep_alive": "10m"  # 保持加载10分钟
            }
            start = time.time()
            response = requests.post(url, json=payload, timeout=timeout)
            elapsed = time.time() - start
            
            if response.status_code == 200:
                return True, f"模型预热完成 ({size_gb:.1f}GB, 耗时{elapsed:.1f}秒)"
            else:
                return False, f"预热失败: HTTP {response.status_code}"
        except requests.exceptions.Timeout:
            return False, f"预热超时（>{timeout}秒），模型可能较大({size_gb:.1f}GB)，请耐心等待"
        except Exception as e:
            return False, f"预热失败: {e}"

    def ocr_image_with_retry(
        self, 
        image_path: str, 
        page_number: int = 1, 
        max_retries: int = 2
    ) -> OCRResult:
        """
        带重试的 OCR 处理
        
        Args:
            image_path: 图片路径
            page_number: 页码
            max_retries: 最大重试次数
            
        Returns:
            OCR 结果
        """
        last_error = None
        for attempt in range(max_retries + 1):
            result = self.ocr_image(image_path, page_number)
            if result.success:
                return result
            last_error = result.error_message
            
            # 如果是超时错误，等待后重试
            if "timeout" in last_error.lower() or "timed out" in last_error.lower():
                if attempt < max_retries:
                    time.sleep(5)
                    continue
                    
        return OCRResult(
            page_number=page_number,
            raw_text="",
            markdown="",
            success=False,
            error_message=f"重试{max_retries}次后仍失败: {last_error}"
        )


if __name__ == "__main__":
    # 测试连接
    engine = OCREngine()
    print(f"模型 {engine.model} 可用: {engine.check_model_available()}")
