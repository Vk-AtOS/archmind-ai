"use client";

// Display units (ARCH-162). The API always works in metres; these helpers only change what is
// shown and convert typed-in values back to metres. Lengths follow the chosen unit; areas and
// volumes stay m²/m³ for metric units (mm drawings still state areas in m²) and become ft²/ft³ for feet.
import { useSyncExternalStore } from "react";

export const UNITS = ["m", "cm", "mm", "ft"] as const;
export type Unit = (typeof UNITS)[number];

const FT = 0.3048;
const LENGTH: Record<Unit, [factor: number, dp: number]> = { m: [1, 2], cm: [100, 0], mm: [1000, 0], ft: [1 / FT, 2] };
const KEY = "archmind.units";
const EVENT = "archmind-units";

function read(): Unit {
  try {
    const v = localStorage.getItem(KEY);
    return (UNITS as readonly string[]).includes(v ?? "") ? (v as Unit) : "m";
  } catch {
    return "m";
  }
}

export function setUnit(u: Unit) {
  try {
    localStorage.setItem(KEY, u);
  } catch {
    // private mode: the choice still applies for this page view
  }
  window.dispatchEvent(new CustomEvent(EVENT));
}

function subscribe(cb: () => void) {
  window.addEventListener(EVENT, cb);
  window.addEventListener("storage", cb); // other tabs
  return () => {
    window.removeEventListener(EVENT, cb);
    window.removeEventListener("storage", cb);
  };
}

export const useUnit = () => useSyncExternalStore(subscribe, read, () => "m" as Unit);

const fmt = (v: number, dp: number) => v.toLocaleString("en-IN", { minimumFractionDigits: dp, maximumFractionDigits: dp });

export const toUnit = (m: number, u: Unit) => m * LENGTH[u][0];
export const fromUnit = (v: number, u: Unit) => v / LENGTH[u][0];
export const len = (m: number, u: Unit) => fmt(toUnit(m, u), LENGTH[u][1]);
export const lenU = (m: number, u: Unit) => `${len(m, u)} ${u}`;
export const areaLabel = (u: Unit) => (u === "ft" ? "ft²" : "m²");
export const area = (m2: number, u: Unit) => (u === "ft" ? fmt(m2 / FT ** 2, 0) : fmt(m2, 1));
export const areaU = (m2: number, u: Unit) => `${area(m2, u)} ${areaLabel(u)}`;

// Quantity in an API unit string (m, m2, m3, count, ratio...) re-expressed in the chosen unit.
// Returns the per-unit factor too so rates (cost per unit) convert inversely and amounts stay equal.
export function qty(value: number, apiUnit: string, u: Unit): { value: number; unit: string; factor: number } {
  const imperial = u === "ft";
  switch (apiUnit) {
    case "m":
      return { value: toUnit(value, u), unit: u, factor: LENGTH[u][0] };
    case "m2":
      return imperial ? { value: value / FT ** 2, unit: "ft²", factor: 1 / FT ** 2 } : { value, unit: "m²", factor: 1 };
    case "m3":
      return imperial ? { value: value / FT ** 3, unit: "ft³", factor: 1 / FT ** 3 } : { value, unit: "m³", factor: 1 };
    default:
      return { value, unit: apiUnit, factor: 1 };
  }
}

export function qtyText(value: number, apiUnit: string, u: Unit) {
  const q = qty(value, apiUnit, u);
  if (q.factor === 1 && q.unit === apiUnit) return `${value} ${apiUnit}`; // count, ratio...
  return `${fmt(q.value, q.unit === "cm" || q.unit === "mm" ? 0 : 2)} ${q.unit}`;
}

// Rate per API unit (e.g. INR per m2) re-expressed per displayed unit (INR per ft²).
export const rateText = (rate: number, apiUnit: string, u: Unit) => fmt(rate / qty(1, apiUnit, u).factor, 2);

// Rule check figures (measured / limit) in the chosen unit.
export function checkText(c: { measured: number | null; limit: number | null; unit: string }, u: Unit) {
  const show = (v: number) => qtyText(v, c.unit, u).replace(/ \S+$/, "");
  const unitLabel = qtyText(0, c.unit, u).replace(/^\S+ /, "");
  return `${c.measured === null ? "" : show(c.measured)}${c.limit !== null ? ` / ${show(c.limit)}` : ""} ${unitLabel}`;
}
