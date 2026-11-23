"use client";

import { setUnit, type Unit, UNITS, useUnit } from "@/lib/units";

const NAMES: Record<Unit, string> = { m: "metres", cm: "centimetres", mm: "millimetres", ft: "feet" };

export default function UnitPicker() {
  const unit = useUnit();
  return (
    <label className="flex items-center gap-1 text-sm text-stone-600">
      Units
      <select
        aria-label="Units"
        data-testid="units"
        value={unit}
        onChange={(e) => setUnit(e.target.value as Unit)}
        className="rounded border border-stone-300 bg-white px-1 py-0.5"
      >
        {UNITS.map((u) => (
          <option key={u} value={u} title={NAMES[u]}>
            {u}
          </option>
        ))}
      </select>
    </label>
  );
}
