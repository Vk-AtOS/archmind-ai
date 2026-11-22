"""Cost estimator (ARCH-152) and rate tables (ARCH-153). Indicative only, never a contractual quote."""

import csv
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from archmind.design.quantities import Quantities

RATE_DIR = Path(__file__).parent / "rates"


class Rate(BaseModel):
    item_id: str
    description: str
    unit: str
    rate: float
    currency: str


class RateTable(BaseModel):
    id: str
    city: str
    currency: str
    status: str  # sample | verified
    source: str
    rates: list[Rate]


class EstimateLine(BaseModel):
    item_id: str
    description: str
    qty: float
    unit: str
    rate: float
    amount: float


class Estimate(BaseModel):
    option_id: str
    rate_table: str
    rate_status: str
    currency: str
    lines: list[EstimateLine]
    total: float
    warnings: list[str]
    label: str = "Indicative estimate - not a quotation"
    exclusions: list[str] = [
        "foundations and site work",
        "plumbing, electrical and other services",
        "finishes beyond flooring and plaster",
        "taxes, fees and contractor margin",
    ]


@cache
def load_rates(table_id: str) -> RateTable:
    if not table_id.replace("-", "").isalnum():
        raise ValueError(f"invalid rate table id: {table_id!r}")
    path = RATE_DIR / f"{table_id}.csv"
    if not path.is_file():
        raise ValueError(f"unknown rate table: {table_id}")
    lines = path.read_text().splitlines()
    meta = dict(x.split("=", 1) for x in lines[0].lstrip("# ").split(";"))
    rows = list(csv.DictReader(lines[1:]))
    rates = [Rate(**r) for r in rows]  # type: ignore[arg-type]
    if {r.currency for r in rates} != {meta["currency"]}:
        raise ValueError(f"rate table {table_id} mixes currencies")
    return RateTable(
        id=table_id,
        city=meta["city"],
        currency=meta["currency"],
        status=meta["status"],
        source=meta["source"],
        rates=rates,
    )


def estimate(q: Quantities, table: RateTable) -> Estimate:
    out: list[EstimateLine] = []
    warnings: list[str] = []
    for r in table.rates:
        line = next((x for x in q.lines if x.item_id == r.item_id), None)
        if line is None:
            warnings.append(f"no quantity for rate item {r.item_id}")
            continue
        if line.unit != r.unit:
            raise ValueError(f"unit mismatch for {r.item_id}: quantity in {line.unit}, rate per {r.unit}")
        out.append(
            EstimateLine(
                item_id=r.item_id,
                description=r.description,
                qty=line.qty,
                unit=r.unit,
                rate=r.rate,
                amount=round(line.qty * r.rate, 2),
            )
        )
    if table.status != "verified":
        warnings.append(f"rates are {table.status}: {table.source}")
    return Estimate(
        option_id=q.option_id,
        rate_table=table.id,
        rate_status=table.status,
        currency=table.currency,
        lines=out,
        total=round(sum(x.amount for x in out), 2),
        warnings=warnings,
    )
