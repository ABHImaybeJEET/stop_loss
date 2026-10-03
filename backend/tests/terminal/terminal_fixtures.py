import json
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parents[1] / "fixtures"
TERMINAL = FIXTURES / "terminal"


def load_json(name: str) -> dict[str, Any]:
    return json.loads((TERMINAL / name).read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    return (TERMINAL / name).read_text(encoding="utf-8")
