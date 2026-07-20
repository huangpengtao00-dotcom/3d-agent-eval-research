import re
from pathlib import Path

FORBIDDEN_PATTERNS = [
    re.compile(r"https?" + r"://", re.IGNORECASE),
    re.compile(r"\b(?:PRO|ENG|MES|SUP|QA)-\d+\b"),
    re.compile(r"(?:token|api[_-]?key|password)\s*[:=]", re.IGNORECASE),
]


def test_public_files_contain_no_identifying_or_secret_patterns() -> None:
    roots = [Path("src"), Path("tests"), Path("docs")]
    failures: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".png", ".glb", ".pyc"}
            ):
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(text):
                    failures.append(f"{path}: {pattern.pattern}")
    assert failures == []
