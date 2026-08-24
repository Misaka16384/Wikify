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

    @property
    def silent_about(self) -> List[str]:
        """Errors this result is carrying that nobody downstream will see.

        A route may succeed and still have errors — the OCR route converts
        page by page, and one failed page leaves the rest of the document
        intact and worth keeping. That is a legitimate state. What is not
        legitimate is reaching a human reviewer without saying so, and that
        is exactly what used to happen: ``success`` was True, the batch wrote
        ``error=None`` because it gated on ``success``, and no finding was
        raised. The document appeared in the review queue clean while missing
        whole pages.

        Two things make an error visible: the result failing outright, or a
        finding loud enough that ``ledger.loud_findings`` counts it. Anything
        else is silent, and ``batch`` turns a non-empty answer here into a
        finding of its own — so a route added later that forgets to speak up
        is caught by the seam every route already goes through, rather than by
        somebody remembering this rule.
        """
        if not self.errors or not self.success:
            return []
        if any(f.severity != "info" for f in self.findings):
            return []
        return list(self.errors)
