"""One result type for every PDF/LaTeX -> Markdown route.

The OCR route already returned this; ``tex2md`` and ``mineru`` called
``sys.exit(1)`` instead — eleven times in mineru's case. That difference is why
``ingest auto`` cannot tell what a converter did without diffing a directory
listing before and after the subprocess (see ``auto._newest_markdown``): the
routes had no way to report.

Same shape as the dataclass this generalises, so the OCR route's callers are
unaffected. ``findings`` is the only addition: a route knows things about its
own output that are worth surfacing to a human reviewer without being fatal —
"six figures were referenced and none survived" is the motivating case, and it
was previously a ``print`` lost inside a captured subprocess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Finding:
    """Something a human should look at. Never fatal on its own."""

    code: str
    detail: str
    severity: str = "flag"   # "flag" | "info"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.code}: {self.detail}"


@dataclass
class ConversionResult:
    success: bool
    markdown_path: str = ""
    images_dir: str = ""
    pages_processed: int = 0
    errors: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)

    @classmethod
    def failed(cls, *errors: str) -> "ConversionResult":
        return cls(success=False, errors=list(errors))

    def flag(self, code: str, detail: str, severity: str = "flag") -> None:
        self.findings.append(Finding(code=code, detail=detail, severity=severity))
