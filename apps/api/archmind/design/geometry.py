"""Plain geometry types for layouts. Metres; x along plot width, y from the front (road) edge."""

from pydantic import BaseModel

EPS = 1e-6


class Rect(BaseModel):
    x: float
    y: float
    w: float
    d: float

    @property
    def area(self) -> float:
        return self.w * self.d

    @property
    def min_side(self) -> float:
        return min(self.w, self.d)

    def overlaps(self, o: "Rect") -> bool:
        return (
            self.x < o.x + o.w - EPS
            and o.x < self.x + self.w - EPS
            and self.y < o.y + o.d - EPS
            and o.y < self.y + self.d - EPS
        )

    def contains(self, o: "Rect") -> bool:
        return (
            o.x >= self.x - EPS
            and o.y >= self.y - EPS
            and o.x + o.w <= self.x + self.w + EPS
            and o.y + o.d <= self.y + self.d + EPS
        )

    def touches(self, o: "Rect") -> bool:
        """Share an edge segment of positive length (not just a corner)."""
        x_overlap = min(self.x + self.w, o.x + o.w) - max(self.x, o.x)
        y_overlap = min(self.y + self.d, o.y + o.d) - max(self.y, o.y)
        vertical_edge = (
            abs(self.x + self.w - o.x) < EPS or abs(o.x + o.w - self.x) < EPS
        ) and y_overlap > EPS
        horizontal_edge = (
            abs(self.y + self.d - o.y) < EPS or abs(o.y + o.d - self.y) < EPS
        ) and x_overlap > EPS
        return vertical_edge or horizontal_edge
