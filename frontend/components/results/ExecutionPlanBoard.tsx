"use client";

import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { MessageCircleQuestion } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LAYER_COLORS, PRIORITY_COLORS } from "@/lib/badges";
import type { Task } from "@/lib/types";
import { cn } from "@/lib/utils";

const PHASES: { phase: 1 | 2 | 3 | 4; title: string; subtitle: string }[] = [
  { phase: 1, title: "Schema", subtitle: "XDM schemas, field groups, identity" },
  { phase: 2, title: "Dataset", subtitle: "Datasets, profile enablement" },
  { phase: 3, title: "Ingestion", subtitle: "Connectors, dataflows, mapping" },
  { phase: 4, title: "Activation", subtitle: "Segments, destinations, flows" },
];

export function ExecutionPlanBoard({
  tasks,
  onAskAbout,
  onJumpToRequirement,
  highlightTaskId,
  onHighlightConsumed,
}: {
  tasks: Task[];
  onAskAbout?: (question: string) => void;
  onJumpToRequirement?: (reqId: string) => void;
  highlightTaskId?: string | null;
  onHighlightConsumed?: () => void;
}) {
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  useEffect(() => {
    if (!highlightTaskId) return;
    const timer = setTimeout(() => {
      cardRefs.current.get(highlightTaskId)?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 50);
    const clearTimer = setTimeout(() => onHighlightConsumed?.(), 2200);
    return () => {
      clearTimeout(timer);
      clearTimeout(clearTimer);
    };
  }, [highlightTaskId, onHighlightConsumed]);

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
      {PHASES.map(({ phase, title, subtitle }) => {
        const phaseTasks = tasks.filter((t) => t.phase === phase);
        return (
          <div key={phase} className="flex flex-col rounded-xl border bg-muted/30">
            <div className="border-b p-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">{title}</h3>
                <Badge variant="secondary">{phaseTasks.length}</Badge>
              </div>
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            </div>
            <div className="flex-1 space-y-2 p-2">
              {phaseTasks.map((task, i) => (
                <motion.div
                  key={task.task_id}
                  ref={(el) => {
                    if (el) cardRefs.current.set(task.task_id, el);
                    else cardRefs.current.delete(task.task_id);
                  }}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{
                    opacity: 1,
                    y: 0,
                    ...(highlightTaskId === task.task_id ? { scale: [1, 1.03, 1] } : {}),
                  }}
                  transition={{ delay: Math.min(i * 0.02, 0.4) }}
                  className={cn(
                    "group relative rounded-lg border bg-card p-3 shadow-sm transition-colors",
                    highlightTaskId === task.task_id && "border-brand-accent ring-2 ring-brand-accent/40"
                  )}
                >
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute top-1.5 right-1.5 h-6 w-6 opacity-0 group-hover:opacity-100"
                    onClick={() =>
                      onAskAbout?.(`Explain task ${task.task_id} ("${task.title}"), which implements requirement ${task.req_id} — what does it involve and why is it needed?`)
                    }
                  >
                    <MessageCircleQuestion className="h-3.5 w-3.5" />
                  </Button>
                  <p className="pr-6 text-sm font-medium leading-snug">{task.title}</p>
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{task.description}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    <Badge variant="secondary" className={cn("font-normal text-[10px]", LAYER_COLORS[task.aep_layer])}>
                      {task.aep_layer}
                    </Badge>
                    <Badge variant="secondary" className={cn("font-normal text-[10px]", PRIORITY_COLORS[task.priority])}>
                      {task.priority}
                    </Badge>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onJumpToRequirement?.(task.req_id);
                      }}
                      className="ml-auto font-mono text-[10px] text-muted-foreground underline decoration-dotted transition-colors hover:text-brand-accent"
                    >
                      {task.req_id}
                    </button>
                  </div>
                </motion.div>
              ))}
              {phaseTasks.length === 0 && (
                <p className="p-3 text-center text-xs text-muted-foreground">No tasks in this phase</p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
