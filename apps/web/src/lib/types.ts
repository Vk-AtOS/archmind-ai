// Mirrors the API's Pydantic models (apps/api/archmind). ponytail: hand-written; switch to an
// OpenAPI-generated client once the API surface stops changing every week.

export type Me = { id: string; email: string; name: string; org_id: string; role: string };
export type Project = { id: string; name: string; location: string; rule_pack: string; created_at: string };

export type OptionSummary = {
  id: string;
  label: string;
  score: number;
  failed_checks: number;
  unknown_checks: number;
  built_up_m2: number;
  estimate_total: number;
  currency: string;
};
export type BriefOut = { id: string; created_at: string; data: Record<string, unknown>; options: OptionSummary[] };

export type Rect = { x: number; y: number; w: number; d: number };
export type Room = { id: string; type: string; name: string; floor: number; rect: Rect; target_area_m2: number };
export type Floor = { level: number; footprint: Rect; corridor: Rect | null; stair: Rect | null; rooms: Room[] };
export type Layout = { id: string; plot: Rect; floors: Floor[]; rule_pack: string; generator_version: string };

export type Check = {
  rule_id: string;
  subject: string;
  result: "pass" | "fail" | "unknown";
  measured: number | null;
  limit: number | null;
  unit: string;
  rule_status: string;
};
export type QuantityLine = { item_id: string; description: string; qty: number; unit: string; method: string };
export type EstimateLine = { item_id: string; description: string; qty: number; unit: string; rate: number; amount: number };
export type OptionDetail = {
  id: string;
  label: string;
  layout: Layout;
  checks: Check[];
  quantities: { lines: QuantityLine[]; version: string };
  estimate: {
    lines: EstimateLine[];
    total: number;
    currency: string;
    warnings: string[];
    label: string;
    exclusions: string[];
    rate_table: string;
  };
  schedule: { floor: number; name: string; width_m: number; depth_m: number; area_m2: number }[];
};

export const money = (v: number, currency: string) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);
