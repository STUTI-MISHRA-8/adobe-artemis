import type { AEPLayer, FlagType, Priority } from "./types";

// Validated with the dataviz skill's CVD-safety checker (Machado-2009,
// deuteranopia/protanopia/tritanopia) — all pairs pass in both light and
// dark mode, at each mode's own lightness band and its own surface. Don't
// hand-tune these without re-running the validator.
export const LAYER_COLORS: Record<AEPLayer, string> = {
  schema: "bg-[#F5EBD9] text-[#8A5A0F] dark:bg-[#3A2E12] dark:text-[#B8781F]",
  dataset: "bg-[#DDF3F6] text-[#0097AD] dark:bg-[#0F2E33] dark:text-[#0A96A8]",
  ingestion: "bg-[#EDE5FB] text-[#6D3FC4] dark:bg-[#2A2050] dark:text-[#8B5CF6]",
  activation: "bg-[#FBE3EE] text-[#B02368] dark:bg-[#3A1830] dark:text-[#D63384]",
  // Secondary/rarer layers share one neutral treatment rather than inventing
  // more hues to validate — the text label is always shown alongside, so
  // identity is never color-alone even for these.
  modeling: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
  governance: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
  reporting: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
  general: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
};

export const PRIORITY_COLORS: Record<Priority, string> = {
  high: "bg-[#FCE8E8] text-[#DC2626] dark:bg-[#3A1A1A] dark:text-[#EF4444]",
  medium: "bg-[#F5EBD9] text-[#8A5A0F] dark:bg-[#3A2E12] dark:text-[#D99A2B]",
  low: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
};

export const FLAG_COLORS: Record<FlagType, string> = {
  clear: "bg-[#EDF1FA] text-[#5B6B8C] dark:bg-[#16213D] dark:text-[#A8B3CC]",
  implicit: "bg-[#DDF3F6] text-[#0097AD] dark:bg-[#0F2E33] dark:text-[#0A96A8]",
  ambiguous: "bg-[#F5EBD9] text-[#8A5A0F] dark:bg-[#3A2E12] dark:text-[#D99A2B]",
  contradiction: "bg-[#FCE8E8] text-[#DC2626] dark:bg-[#3A1A1A] dark:text-[#EF4444]",
  assumption: "bg-[#FBE3EE] text-[#B02368] dark:bg-[#3A1830] dark:text-[#D63384]",
  unclassified: "bg-[#F5EBD9] text-[#8A5A0F] dark:bg-[#3A2E12] dark:text-[#D99A2B]",
};

export const PHASE_LABELS: Record<number, string> = {
  1: "Phase 1 — Schema",
  2: "Phase 2 — Dataset",
  3: "Phase 3 — Ingestion",
  4: "Phase 4 — Activation",
};
