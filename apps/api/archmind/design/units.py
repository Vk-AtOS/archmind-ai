"""Display units (ARCH-162). Everything is stored and computed in metres; units only change what is shown.

Lengths follow the chosen unit. Areas stay in m² for the metric units (drawings in mm still state
areas in m²) and switch to ft² for feet; volumes likewise.
"""

from typing import Literal

Unit = Literal["m", "cm", "mm", "ft"]
FT = 0.3048  # metres per foot, exact

_LENGTH: dict[str, tuple[float, int]] = {
    "m": (1.0, 2),
    "cm": (100.0, 0),
    "mm": (1000.0, 0),
    "ft": (1 / FT, 2),
}


def length(v_m: float, unit: Unit) -> str:
    factor, dp = _LENGTH[unit]
    return f"{v_m * factor:,.{dp}f} {unit}"


def area(v_m2: float, unit: Unit) -> str:
    return f"{v_m2 / FT**2:,.0f} ft²" if unit == "ft" else f"{v_m2:.1f} m²"


def bare_length(v_m: float, unit: Unit) -> str:
    factor, dp = _LENGTH[unit]
    return f"{v_m * factor:,.{dp}f}"
