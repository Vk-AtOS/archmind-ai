"""DesignBrief (ARCH-146): the typed input every design starts from. All lengths in metres."""

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

RoomType = Literal["living", "dining", "kitchen", "bedroom", "bathroom"]

# Fallback room sizes (m2) when the brief gives none; rule-pack minimums still apply.
DEFAULT_AREA: dict[str, float] = {
    "living": 16.0,
    "dining": 9.0,
    "kitchen": 8.0,
    "bedroom": 12.0,
    "bathroom": 4.0,
}


class Setbacks(BaseModel):
    front: float = Field(ge=0)
    rear: float = Field(ge=0)
    left: float = Field(ge=0)
    right: float = Field(ge=0)


class RoomRequest(BaseModel):
    type: RoomType
    count: int = Field(default=1, ge=1, le=6)
    target_area_m2: float | None = Field(default=None, ge=1, le=200)


class DesignBrief(BaseModel):
    plot_width_m: float = Field(gt=0, le=100)
    plot_depth_m: float = Field(gt=0, le=100)
    setbacks: Setbacks
    floors: Literal[1, 2] = 1
    rooms: list[RoomRequest] = Field(min_length=1, max_length=10)
    rule_pack: str = "generic-metric-v0"

    @property
    def buildable_width(self) -> float:
        return self.plot_width_m - self.setbacks.left - self.setbacks.right

    @property
    def buildable_depth(self) -> float:
        return self.plot_depth_m - self.setbacks.front - self.setbacks.rear

    @model_validator(mode="after")
    def _fits(self) -> Self:
        if self.buildable_width <= 0 or self.buildable_depth <= 0:
            raise ValueError("setbacks leave no buildable area")
        types = {r.type for r in self.rooms}
        if "living" not in types:
            raise ValueError("a living room is required")
        if "kitchen" not in types:
            raise ValueError("a kitchen is required")
        if "bathroom" not in types:
            raise ValueError("at least one bathroom is required")
        wanted = sum((r.target_area_m2 or DEFAULT_AREA[r.type]) * r.count for r in self.rooms)
        # ponytail: 75% net-to-gross assumption; replace with measured circulation once layouts are rated.
        capacity = self.buildable_width * self.buildable_depth * self.floors * 0.75
        if wanted > capacity:
            raise ValueError(f"rooms need about {wanted:.0f} m2 but the plot allows about {capacity:.0f} m2")
        return self
