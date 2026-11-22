"""Rule packs (ARCH-147): versioned, city-scoped rule data. Values are data, never code."""

import json
from functools import cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

PACK_DIR = Path(__file__).parent / "rulepacks"


class Rule(BaseModel):
    id: str
    value: float
    unit: str
    status: Literal["provisional", "verified"]
    source: str


class RulePack(BaseModel):
    id: str
    version: str
    jurisdiction: str
    units: Literal["m"]
    status_note: str = ""
    rules: list[Rule]

    def get(self, rule_id: str) -> Rule | None:
        return next((r for r in self.rules if r.id == rule_id), None)

    def value(self, rule_id: str, default: float) -> float:
        r = self.get(rule_id)
        return r.value if r else default


@cache
def load_pack(pack_id: str) -> RulePack:
    if not pack_id.replace("-", "").replace(".", "").isalnum():
        raise ValueError(f"invalid rule pack id: {pack_id!r}")
    path = PACK_DIR / f"{pack_id}.json"
    if not path.is_file():
        raise ValueError(f"unknown rule pack: {pack_id}")
    return RulePack.model_validate(json.loads(path.read_text()))
