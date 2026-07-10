"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import {
  AlertTriangle,
  Check,
  CheckCheck,
  ChevronRight,
  Copy,
  FlaskConical,
  Lock,
  Loader2,
  Sparkles,
  Terminal,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  assignTask,
  executeTaskPayload,
  getAepStatus,
  getTaskPayload,
  getTeam,
  getWizard,
  setTaskStatus,
  simulateTaskPayload,
  streamTaskHowto,
} from "@/lib/api";
import { LAYER_COLORS, PHASE_LABELS, PRIORITY_COLORS } from "@/lib/badges";
import { getLocalIdentity } from "@/lib/identity";
import { AssignMenu } from "@/components/team/AssignMenu";
import { JoinTeamDialog } from "@/components/team/JoinTeamDialog";
import type { AepStatus, TaskExecution, TaskPayload, TeamMember, WizardState, WizardStep } from "@/lib/types";
import { cn } from "@/lib/utils";

function buildCurl(payload: TaskPayload): string {
  const headerFlags = Object.entries(payload.headers)
    .map(([k, v]) => `  -H '${k}: ${v}'`)
    .join(" \\\n");
  const bodyFlag = payload.body != null ? ` \\\n  -d '${JSON.stringify(payload.body, null, 2)}'` : "";
  return `curl -X ${payload.method} '${payload.endpoint}' \\\n${headerFlags}${bodyFlag}`;
}

function ExecutionResult({ execution }: { execution: TaskExecution }) {
  const summary =
    typeof execution.response === "string"
      ? execution.response
      : JSON.stringify(execution.response ?? execution.error, null, 2);

  const simulated = !!execution.simulated;

  return (
    <div
      className={cn(
        "space-y-1.5 rounded-md border p-3",
        execution.ok ? "border-[#16A34A]/40 bg-[#16A34A]/10" : "border-destructive/40 bg-destructive/10"
      )}
    >
      <div className="flex items-center gap-2 text-xs font-medium">
        {execution.ok ? (
          <CheckCheck className="h-3.5 w-3.5 text-[#16A34A]" />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-destructive" />
        )}
        {execution.ok ? "Success" : `Failed${execution.status_code ? ` (HTTP ${execution.status_code})` : ""}`}
        {simulated && (
          <Badge variant="secondary" className="gap-1 font-normal text-[10px]">
            <FlaskConical className="h-2.5 w-2.5" />
            Dry run
          </Badge>
        )}
        <span className="ml-auto text-[10px] font-normal text-muted-foreground">
          {new Date(execution.executed_at).toLocaleTimeString()}
        </span>
      </div>
      <pre className="max-h-40 overflow-auto rounded bg-background p-2 text-[10px] leading-relaxed">
        <code>{summary}</code>
      </pre>
    </div>
  );
}

function PayloadPanel({
  payload,
  jobId,
  taskId,
  aepStatus,
  onExecuted,
}: {
  payload: TaskPayload;
  jobId: string;
  taskId: string;
  aepStatus: AepStatus;
  onExecuted?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [execution, setExecution] = useState<TaskExecution | null>(payload.last_execution ?? null);

  async function copyCurl() {
    await navigator.clipboard.writeText(buildCurl(payload));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }

  async function handleExecute() {
    setExecuting(true);
    setConfirming(false);
    try {
      const result = await executeTaskPayload(jobId, taskId);
      setExecution(result);
      if (result.ok) onExecuted?.();
    } catch (e) {
      setExecution({
        ok: false,
        status_code: null,
        response: null,
        endpoint: null,
        error: e instanceof Error ? e.message : "Execution failed",
        executed_at: new Date().toISOString(),
      });
    } finally {
      setExecuting(false);
    }
  }

  async function handleSimulate() {
    setSimulating(true);
    try {
      const result = await simulateTaskPayload(jobId, taskId);
      setExecution(result);
      onExecuted?.();
    } catch (e) {
      setExecution({
        ok: false,
        status_code: null,
        response: null,
        endpoint: null,
        error: e instanceof Error ? e.message : "Simulation failed",
        executed_at: new Date().toISOString(),
      });
    } finally {
      setSimulating(false);
    }
  }

  return (
    <div className="space-y-2 rounded-md border bg-muted/50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="font-mono text-[10px]">{payload.method}</Badge>
          <span className="text-xs font-medium">{payload.api_name}</span>
          {payload.cached && <span className="text-[10px] text-muted-foreground">(cached)</span>}
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={copyCurl}>
            {copied ? <CheckCheck className="mr-1.5 h-3.5 w-3.5" /> : <Copy className="mr-1.5 h-3.5 w-3.5" />}
            {copied ? "Copied" : "Copy curl"}
          </Button>
          <Button size="sm" onClick={handleSimulate} disabled={simulating}>
            {simulating ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
            )}
            {simulating ? "Running..." : "Dry run"}
          </Button>
        </div>
      </div>
      <pre className="overflow-x-auto rounded bg-background p-2.5 text-[11px] leading-relaxed">
        <code>{buildCurl(payload)}</code>
      </pre>
      {payload.notes && <p className="text-xs text-muted-foreground">{payload.notes}</p>}

      {execution && <ExecutionResult execution={execution} />}

      {aepStatus.configured && !confirming && (
        <button
          onClick={() => setConfirming(true)}
          disabled={executing}
          className="text-[11px] text-muted-foreground underline decoration-dotted transition-colors hover:text-brand-accent"
        >
          {executing ? "Executing..." : `Run this for real in sandbox "${aepStatus.sandbox}" instead →`}
        </button>
      )}

      {confirming && (
        <div className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-2.5 text-xs">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
          <span>
            This will make a real <strong>{payload.method}</strong> call against sandbox{" "}
            <strong>{aepStatus.sandbox}</strong>. It may create or modify data there.
          </span>
          <div className="ml-auto flex shrink-0 gap-1.5">
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button size="sm" variant="destructive" onClick={handleExecute}>
              Confirm & execute
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function StepRow({
  step,
  jobId,
  team,
  aepStatus,
  isExpanded,
  onToggleExpand,
  onToggleDone,
  onAssign,
  onJumpToRequirement,
  onExecuted,
}: {
  step: WizardStep;
  jobId: string;
  team: TeamMember[];
  aepStatus: AepStatus;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onToggleDone: () => void;
  onAssign: (memberId: string | null) => void;
  onJumpToRequirement?: (reqId: string) => void;
  onExecuted?: () => void;
}) {
  const [howto, setHowto] = useState<string | null>(null);
  const [loadingHowto, setLoadingHowto] = useState(false);
  const [payload, setPayload] = useState<TaskPayload | null>(null);
  const [loadingPayload, setLoadingPayload] = useState(false);
  const [payloadError, setPayloadError] = useState(false);

  async function handleGetHowto() {
    if (howto || loadingHowto) return;
    setLoadingHowto(true);
    setHowto("");
    await streamTaskHowto(jobId, step.task_id, {
      onChunk: (text) => setHowto((prev) => (prev ?? "") + text),
      onDone: () => setLoadingHowto(false),
      onError: () => {
        setHowto("Sorry, couldn't generate a walkthrough for this step right now.");
        setLoadingHowto(false);
      },
    });
  }

  async function handleGetPayload() {
    if (payload || loadingPayload) return;
    setLoadingPayload(true);
    setPayloadError(false);
    try {
      const result = await getTaskPayload(jobId, step.task_id);
      setPayload(result);
    } catch {
      setPayloadError(true);
    } finally {
      setLoadingPayload(false);
    }
  }

  const blocked = !step.is_ready;

  return (
    <div
      className={cn(
        "rounded-lg border bg-card transition-colors",
        step.is_current && "border-brand-accent ring-1 ring-brand-accent/30",
        blocked && "opacity-50"
      )}
    >
      <div className="flex items-center gap-3 p-3">
        <button
          onClick={onToggleDone}
          disabled={blocked}
          className={cn(
            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
            step.status === "done" && "border-[#16A34A] bg-[#16A34A] text-white dark:border-[#22C55E] dark:bg-[#22C55E]",
            step.status !== "done" && !blocked && "border-muted-foreground/40 hover:border-brand-accent",
            blocked && "cursor-not-allowed border-muted-foreground/20"
          )}
          title={blocked ? "Finish earlier-phase tasks first" : step.status === "done" ? "Mark as not done" : "Mark as done"}
        >
          {step.status === "done" ? <Check className="h-3.5 w-3.5" /> : blocked ? <Lock className="h-3 w-3 text-muted-foreground" /> : null}
        </button>

        <button onClick={onToggleExpand} className="flex flex-1 items-center gap-2 text-left">
          <motion.div animate={{ rotate: isExpanded ? 90 : 0 }}>
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          </motion.div>
          <span className={cn("text-sm font-medium", step.status === "done" && "text-muted-foreground line-through")}>
            {step.title}
          </span>
          {step.is_current && (
            <Badge className="bg-brand-accent text-brand-accent-foreground hover:bg-brand-accent">Up next</Badge>
          )}
        </button>

        <Badge variant="secondary" className={cn("font-normal shrink-0", LAYER_COLORS[step.aep_layer])}>
          {step.aep_layer}
        </Badge>
        <Badge variant="secondary" className={cn("font-normal shrink-0", PRIORITY_COLORS[step.priority])}>
          {step.priority}
        </Badge>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onJumpToRequirement?.(step.req_id);
          }}
          className="shrink-0 font-mono text-xs text-muted-foreground underline decoration-dotted transition-colors hover:text-brand-accent"
        >
          {step.req_id}
        </button>
        <AssignMenu team={team} assignedTo={step.assigned_to} onAssign={onAssign} />
      </div>

      <AnimatePresence initial={false}>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t p-4">
              <p className="text-sm text-muted-foreground">{step.description}</p>
              {step.acceptance_criteria && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Acceptance: </span>
                  {step.acceptance_criteria}
                </p>
              )}

              <div className="flex flex-wrap gap-2">
                {!howto && (
                  <Button size="sm" variant="outline" onClick={handleGetHowto} disabled={loadingHowto}>
                    {loadingHowto ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {loadingHowto ? "Generating walkthrough..." : "How do I actually do this in AEP?"}
                  </Button>
                )}
                {!payload && (
                  <Button size="sm" variant="outline" onClick={handleGetPayload} disabled={loadingPayload}>
                    {loadingPayload ? (
                      <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Terminal className="mr-1.5 h-3.5 w-3.5" />
                    )}
                    {loadingPayload ? "Building API call..." : "Generate the API call for this step"}
                  </Button>
                )}
              </div>

              {howto && (
                <div className="rounded-md bg-muted/50 p-3 prose prose-sm dark:prose-invert max-w-none prose-p:my-1 prose-ol:my-1 prose-li:my-0.5">
                  <ReactMarkdown>{howto}</ReactMarkdown>
                </div>
              )}

              {payloadError && (
                <p className="text-xs text-destructive">Couldn&apos;t generate an API call for this step right now.</p>
              )}
              {payload && (
                <PayloadPanel
                  payload={payload}
                  jobId={jobId}
                  taskId={step.task_id}
                  aepStatus={aepStatus}
                  onExecuted={onExecuted}
                />
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function GuidedWizard({ jobId, onJumpToRequirement }: { jobId: string; onJumpToRequirement?: (reqId: string) => void }) {
  const [wizard, setWizard] = useState<WizardState | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showJoin, setShowJoin] = useState(false);
  const [myId, setMyId] = useState<string | null>(null);
  const [myTasksOnly, setMyTasksOnly] = useState(false);
  const [aepStatus, setAepStatus] = useState<AepStatus>({ configured: false, sandbox: null });

  function refreshTeam() {
    getTeam(jobId).then(setTeam);
  }

  function refreshWizard() {
    getWizard(jobId).then(setWizard);
  }

  useEffect(() => {
    Promise.all([getWizard(jobId), getTeam(jobId), getAepStatus()])
      .then(([w, t, aep]) => {
        setWizard(w);
        setTeam(t);
        setAepStatus(aep);
        const current = w.steps.find((s) => s.is_current);
        if (current) setExpandedId(current.task_id);
      })
      .finally(() => setLoading(false));

    const identity = getLocalIdentity(jobId);
    if (identity) {
      setMyId(identity.memberId);
    } else {
      setShowJoin(true);
    }
  }, [jobId]);

  async function toggleDone(step: WizardStep) {
    const nextStatus = step.status === "done" ? "pending" : "done";
    const updated = await setTaskStatus(jobId, step.task_id, nextStatus);
    setWizard(updated);
  }

  async function handleAssign(taskId: string, memberId: string | null) {
    await assignTask(jobId, taskId, memberId);
    const updated = await getWizard(jobId);
    setWizard(updated);
    refreshTeam();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
      </div>
    );
  }

  if (!wizard) return null;

  const visibleSteps = myTasksOnly ? wizard.steps.filter((s) => s.assigned_to === myId) : wizard.steps;
  const grouped = [1, 2, 3, 4].map((phase) => ({
    phase,
    steps: visibleSteps.filter((s) => s.phase === phase),
  }));

  return (
    <div className="space-y-6">
      <JoinTeamDialog
        jobId={jobId}
        open={showJoin}
        onJoined={(memberId) => {
          setMyId(memberId);
          setShowJoin(false);
          getWizard(jobId).then(setWizard);
          refreshTeam();
        }}
      />

      <div className="rounded-xl border bg-card p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium">
            {wizard.done} of {wizard.total} steps complete
          </span>
          <span className="text-muted-foreground">{wizard.percent_complete}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted">
          <motion.div
            className="h-full rounded-full bg-brand-accent"
            animate={{ width: `${wizard.percent_complete}%` }}
            transition={{ ease: "easeOut", duration: 0.4 }}
          />
        </div>
      </div>

      {myId && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={myTasksOnly ? "default" : "outline"}
            onClick={() => setMyTasksOnly((v) => !v)}
          >
            {myTasksOnly ? "Showing my tasks" : "Show only my tasks"}
          </Button>
        </div>
      )}

      {grouped.map(({ phase, steps }) => (
        <div key={phase}>
          <h3 className="mb-2 text-sm font-semibold text-muted-foreground">{PHASE_LABELS[phase]}</h3>
          <div className="space-y-2">
            {steps.map((step) => (
              <StepRow
                key={step.task_id}
                step={step}
                jobId={jobId}
                team={team}
                aepStatus={aepStatus}
                isExpanded={expandedId === step.task_id}
                onToggleExpand={() => setExpandedId(expandedId === step.task_id ? null : step.task_id)}
                onToggleDone={() => toggleDone(step)}
                onAssign={(memberId) => handleAssign(step.task_id, memberId)}
                onJumpToRequirement={onJumpToRequirement}
                onExecuted={refreshWizard}
              />
            ))}
            {steps.length === 0 && <p className="text-xs text-muted-foreground">No tasks in this phase.</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
