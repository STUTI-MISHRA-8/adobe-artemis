"use client";

import { useEffect, useState } from "react";
import { Loader2, UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MemberAvatar } from "@/components/team/MemberAvatar";
import { getTeam } from "@/lib/api";
import type { TeamMember } from "@/lib/types";

const ROLE_LABELS: Record<string, string> = {
  schema: "Schema Engineer",
  dataset: "Dataset Engineer",
  ingestion: "Ingestion Engineer",
  activation: "Activation Specialist",
  pm: "Project Manager",
  reviewer: "Reviewer",
};

export function TeamView({ jobId, onInviteAnother }: { jobId: string; onInviteAnother: () => void }) {
  const [team, setTeam] = useState<TeamMember[] | null>(null);

  useEffect(() => {
    getTeam(jobId).then(setTeam);
  }, [jobId]);

  if (!team) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Team monitor</h3>
          <p className="text-xs text-muted-foreground">Who&apos;s working on what, and how far along they are.</p>
        </div>
        <Button size="sm" variant="outline" onClick={onInviteAnother}>
          <UserPlus className="mr-1.5 h-3.5 w-3.5" />
          Add teammate
        </Button>
      </div>

      {team.length === 0 && (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          Nobody&apos;s joined yet. Add teammates to split up the work.
        </p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {team.map((member) => {
          const pct = member.assigned > 0 ? Math.round((member.done / member.assigned) * 100) : 0;
          return (
            <div key={member.id} className="rounded-xl border bg-card p-4">
              <div className="flex items-center gap-3">
                <MemberAvatar name={member.name} color={member.color} size="md" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{member.name}</p>
                  <Badge variant="secondary" className="mt-0.5 font-normal">
                    {ROLE_LABELS[member.role] ?? member.role}
                  </Badge>
                </div>
              </div>
              <div className="mt-3 space-y-1.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{member.done} of {member.assigned} done</span>
                  <span>{pct}%</span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-brand-accent transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
