"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  FileText,
  LayoutDashboard,
  ListChecks,
  ListTree,
  MessageCircleQuestion,
  Route,
  Users,
  Workflow,
} from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CoverageBadge } from "@/components/results/CoverageBadge";
import { OverviewCards } from "@/components/results/OverviewCards";
import { RequirementsTable } from "@/components/results/RequirementsTable";
import { ExecutionPlanBoard } from "@/components/results/ExecutionPlanBoard";
import { TraceabilityTree } from "@/components/results/TraceabilityTree";
import { ExportMenu } from "@/components/results/ExportMenu";
import { DocChat } from "@/components/chat/DocChat";
import { GuidedWizard } from "@/components/wizard/GuidedWizard";
import { TeamView } from "@/components/team/TeamView";
import { JoinTeamDialog } from "@/components/team/JoinTeamDialog";
import type { AnalysisResult } from "@/lib/types";

function StatTile({
  icon: Icon,
  label,
  value,
  onClick,
}: {
  icon: typeof FileText;
  label: string;
  value: number;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 rounded-xl border bg-card p-4 text-left transition-colors hover:border-brand-accent/50 hover:bg-accent"
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div>
        <p className="text-lg font-semibold leading-none">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </button>
  );
}

const NAV_ITEMS = [
  { value: "overview", label: "Overview", icon: LayoutDashboard },
  { value: "requirements", label: "Requirements", icon: ListChecks },
  { value: "plan", label: "Execution Plan", icon: Workflow },
  { value: "trace", label: "Traceability", icon: ListTree },
  { value: "wizard", label: "Guided Build", icon: Route },
  { value: "team", label: "Team", icon: Users },
  { value: "chat", label: "Ask the Document", icon: MessageCircleQuestion },
] as const;

export function ResultsDashboard({ result }: { result: AnalysisResult }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [teamRefreshKey, setTeamRefreshKey] = useState(0);
  const [showInvite, setShowInvite] = useState(false);
  const [highlightReqId, setHighlightReqId] = useState<string | null>(null);
  const [highlightTaskId, setHighlightTaskId] = useState<string | null>(null);

  function askAbout(question: string) {
    setActiveTab("chat");
    setPendingQuestion(question);
  }

  function jumpToRequirement(reqId: string) {
    setActiveTab("requirements");
    setHighlightReqId(reqId);
  }

  function jumpToTask(taskId: string) {
    setActiveTab("plan");
    setHighlightTaskId(taskId);
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mx-auto w-full max-w-7xl space-y-6 px-6 py-10"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{result.filename}</h1>
          <p className="text-sm text-muted-foreground">{result.section_count} sections analyzed</p>
        </div>
        <ExportMenu jobId={result.job_id} />
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile icon={FileText} label="Observations" value={result.observation_count} onClick={() => setActiveTab("trace")} />
        <StatTile icon={ListChecks} label="Requirements" value={result.requirement_count} onClick={() => setActiveTab("requirements")} />
        <StatTile icon={Workflow} label="Tasks" value={result.task_count} onClick={() => setActiveTab("plan")} />
        <StatTile icon={ListTree} label="Sections" value={result.section_count} onClick={() => setActiveTab("trace")} />
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} orientation="vertical" className="items-start">
        <TabsList variant="line" className="w-56 shrink-0 gap-1 rounded-xl border bg-card p-2">
          {NAV_ITEMS.map(({ value, label, icon: Icon }) => (
            <TabsTrigger key={value} value={value} className="w-full justify-start gap-2 rounded-lg px-3 py-2">
              <Icon className="h-4 w-4" />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="min-w-0 flex-1 space-y-6">
          <TabsContent value="overview" className="mt-0 space-y-6">
            <CoverageBadge coverage={result.coverage} />
            <div>
              <h3 className="mb-3 text-sm font-semibold text-muted-foreground">Execution plan by phase</h3>
              <OverviewCards jobId={result.job_id} onOpenPhase={() => setActiveTab("plan")} />
            </div>
          </TabsContent>
          <TabsContent value="requirements" className="mt-0">
            <RequirementsTable
              requirements={result.requirements}
              onAskAbout={askAbout}
              highlightReqId={highlightReqId}
              onHighlightConsumed={() => setHighlightReqId(null)}
            />
          </TabsContent>
          <TabsContent value="plan" className="mt-0">
            <ExecutionPlanBoard
              tasks={result.tasks}
              onAskAbout={askAbout}
              onJumpToRequirement={jumpToRequirement}
              highlightTaskId={highlightTaskId}
              onHighlightConsumed={() => setHighlightTaskId(null)}
            />
          </TabsContent>
          <TabsContent value="trace" className="mt-0">
            <TraceabilityTree
              trace={result.trace}
              onAskAbout={askAbout}
              onJumpToTask={jumpToTask}
              onJumpToRequirement={jumpToRequirement}
            />
          </TabsContent>
          <TabsContent value="wizard" className="mt-0">
            <GuidedWizard jobId={result.job_id} onJumpToRequirement={jumpToRequirement} />
          </TabsContent>
          <TabsContent value="team" className="mt-0">
            <TeamView key={teamRefreshKey} jobId={result.job_id} onInviteAnother={() => setShowInvite(true)} />
          </TabsContent>
          <TabsContent value="chat" className="mt-0">
            <DocChat
              jobId={result.job_id}
              pendingQuestion={pendingQuestion}
              onConsumePendingQuestion={() => setPendingQuestion(null)}
              onJumpToRequirement={jumpToRequirement}
              onJumpToTask={jumpToTask}
            />
          </TabsContent>
        </div>
      </Tabs>

      <JoinTeamDialog
        jobId={result.job_id}
        open={showInvite}
        mode="invite"
        onOpenChange={setShowInvite}
        onJoined={() => {
          setShowInvite(false);
          setTeamRefreshKey((k) => k + 1);
        }}
      />
    </motion.div>
  );
}
