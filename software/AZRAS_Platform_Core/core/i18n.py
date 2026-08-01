
from __future__ import annotations
import json
from pathlib import Path

class I18N:
    def __init__(self, root: Path, language: str = "ja"):
        self.root = Path(root)
        self.language = language if language in ("ja", "en") else "ja"
        self.data = {}
        self.load()

    def load(self) -> None:
        path = self.root / "lang" / f"{self.language}.json"
        self.data = json.loads(path.read_text(encoding="utf-8"))

    def set_language(self, language: str) -> None:
        if language not in ("ja", "en"):
            raise ValueError("Only ja and en are supported.")
        self.language = language
        self.load()

    def t(self, key: str) -> str:
        return self.data.get(key, key)
