"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { getTeam, getWizard } from "@/lib/api";
import { MemberAvatar } from "@/components/team/MemberAvatar";
import type { TeamMember, WizardState } from "@/lib/types";

// Darker than the badge-tint foreground colors (validated separately for
// white-text contrast, since a bold card background is a different contrast
// job than a pastel badge) — same hue identity, just deep enough that white
// text clears 4.5:1 AA.
const PHASE_CARDS = [
  { phase: 1, title: "Schema", subtitle: "XDM schemas, field groups, identity", bg: "#8A5A0F" },
  { phase: 2, title: "Dataset", subtitle: "Datasets, profile enablement", bg: "#087885" },
  { phase: 3, title: "Ingestion", subtitle: "Connectors, dataflows, mapping", bg: "#6D3FC4" },
  { phase: 4, title: "Activation", subtitle: "Segments, destinations, flows", bg: "#B02368" },
] as const;

export function OverviewCards({ jobId, onOpenPhase }: { jobId: string; onOpenPhase: () => void }) {
  const [wizard, setWizard] = useState<WizardState | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);

  useEffect(() => {
    Promise.all([getWizard(jobId), getTeam(jobId)]).then(([w, t]) => {
      setWizard(w);
      setTeam(t);
    });
  }, [jobId]);

  if (!wizard) return null;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {PHASE_CARDS.map((card, i) => {
        const steps = wizard.steps.filter((s) => s.phase === card.phase);
        const done = steps.filter((s) => s.status === "done").length;
        const pct = steps.length ? Math.round((done / steps.length) * 100) : 0;
        const assignees = team.filter((m) => steps.some((s) => s.assigned_to === m.id));

        return (
          <motion.button
            key={card.phase}
            onClick={onOpenPhase}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.05 }}
            whileHover={{ y: -2 }}
            className="flex flex-col justify-between rounded-2xl p-5 text-left text-white shadow-lg"
            style={{ backgroundColor: card.bg }}
          >
            <div>
              <p className="text-sm font-semibold opacity-90">{card.title}</p>
              <p className="mt-0.5 text-xs opacity-70">{card.subtitle}</p>
            </div>
            <div className="mt-6 flex items-end justify-between">
              <div>
                <p className="text-2xl font-bold">{steps.length}</p>
                <p className="text-xs opacity-70">tasks · {pct}% done</p>
              </div>
              {assignees.length > 0 && (
                <div className="flex -space-x-2">
                  {assignees.slice(0, 3).map((m) => (
                    <MemberAvatar key={m.id} name={m.name} color={m.color} size="sm" className="ring-2 ring-white/40" />
                  ))}
                  {assignees.length > 3 && (
                    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-[10px] font-semibold ring-2 ring-white/40">
                      +{assignees.length - 3}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/20">
              <div className="h-full rounded-full bg-white" style={{ width: `${pct}%` }} />
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
