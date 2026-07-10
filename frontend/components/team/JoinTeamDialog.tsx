"use client";

import { useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { joinTeam } from "@/lib/api";
import { setLocalIdentity } from "@/lib/identity";
import type { TeamRole } from "@/lib/types";

const ROLE_OPTIONS: { value: TeamRole; label: string; hint: string }[] = [
  { value: "schema", label: "Schema Engineer", hint: "XDM schemas, field groups, identity" },
  { value: "dataset", label: "Dataset Engineer", hint: "Datasets, profile enablement" },
  { value: "ingestion", label: "Ingestion Engineer", hint: "Connectors, dataflows, mapping" },
  { value: "activation", label: "Activation Specialist", hint: "Segments, destinations, flows" },
  { value: "pm", label: "Project Manager", hint: "Oversees the whole plan" },
  { value: "reviewer", label: "Reviewer", hint: "Reviews, no task ownership" },
];

export function JoinTeamDialog({
  jobId,
  open,
  mode = "self",
  onJoined,
  onOpenChange,
}: {
  jobId: string;
  open: boolean;
  mode?: "self" | "invite";
  onJoined: (memberId: string, name: string, role: TeamRole) => void;
  onOpenChange?: (open: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [role, setRole] = useState<TeamRole | "">("");
  const [loading, setLoading] = useState(false);

  async function handleJoin() {
    if (!name.trim() || !role) return;
    setLoading(true);
    try {
      const res = await joinTeam(jobId, name.trim(), role);
      if (mode === "self") {
        setLocalIdentity(jobId, { memberId: res.id, name: res.name, role: res.role });
      }
      if (res.auto_assigned > 0) {
        toast.success(`${res.name} added — ${res.auto_assigned} ${res.role} task(s) assigned.`);
      } else {
        toast.success(`${res.name} added to the project.`);
      }
      setName("");
      setRole("");
      onJoined(res.id, res.name, res.role);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to join");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={mode === "invite"}>
        <DialogHeader>
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Users className="h-5 w-5" />
          </div>
          <DialogTitle>{mode === "self" ? "Who's working on this?" : "Add a teammate"}</DialogTitle>
          <DialogDescription>
            {mode === "self"
              ? "A BRD this size isn't a one-person job. Tell us your name and role — we'll suggest which tasks are yours."
              : "Add someone else to the roster and suggest tasks for their role."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <Input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleJoin()}
            autoFocus
          />
          <Select value={role} onValueChange={(v) => setRole(v as TeamRole)}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Your role on this project" />
            </SelectTrigger>
            <SelectContent>
              {ROLE_OPTIONS.map((r) => (
                <SelectItem key={r.value} value={r.value}>
                  <div className="flex flex-col">
                    <span>{r.label}</span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {role && (
            <p className="text-xs text-muted-foreground">
              {ROLE_OPTIONS.find((r) => r.value === role)?.hint}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button onClick={handleJoin} disabled={!name.trim() || !role || loading}>
            {loading ? "Adding..." : mode === "self" ? "Join project" : "Add teammate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
