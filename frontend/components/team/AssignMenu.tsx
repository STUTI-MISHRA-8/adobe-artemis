"use client";

import { Check, UserRound } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MemberAvatar } from "@/components/team/MemberAvatar";
import type { TeamMember } from "@/lib/types";

export function AssignMenu({
  team,
  assignedTo,
  onAssign,
}: {
  team: TeamMember[];
  assignedTo: string | null;
  onAssign: (memberId: string | null) => void;
}) {
  const current = team.find((m) => m.id === assignedTo);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <button
            className="flex h-7 shrink-0 items-center gap-1.5 rounded-full border px-1.5 text-xs text-muted-foreground transition-colors hover:border-brand-accent hover:text-foreground"
            onClick={(e: React.MouseEvent) => e.stopPropagation()}
          />
        }
      >
        {current ? (
          <>
            <MemberAvatar name={current.name} color={current.color} size="xs" />
            <span className="max-w-20 truncate">{current.name}</span>
          </>
        ) : (
          <>
            <UserRound className="h-3.5 w-3.5" />
            Unassigned
          </>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(e) => e.stopPropagation()}>
        <DropdownMenuItem onClick={() => onAssign(null)}>
          <UserRound className="mr-2 h-3.5 w-3.5 text-muted-foreground" />
          Unassigned
          {!assignedTo && <Check className="ml-auto h-3.5 w-3.5" />}
        </DropdownMenuItem>
        {team.map((member) => (
          <DropdownMenuItem key={member.id} onClick={() => onAssign(member.id)}>
            <MemberAvatar name={member.name} color={member.color} size="xs" className="mr-2" />
            {member.name}
            {assignedTo === member.id && <Check className="ml-auto h-3.5 w-3.5" />}
          </DropdownMenuItem>
        ))}
        {team.length === 0 && (
          <p className="px-2 py-1.5 text-xs text-muted-foreground">No teammates yet</p>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
