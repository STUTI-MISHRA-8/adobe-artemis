"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronRight, MessageCircleQuestion, Quote } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LAYER_COLORS } from "@/lib/badges";
import type { TraceNode } from "@/lib/types";
import { cn } from "@/lib/utils";

export function TraceabilityTree({
  trace,
  onAskAbout,
  onJumpToTask,
  onJumpToRequirement,
}: {
  trace: TraceNode[];
  onAskAbout?: (question: string) => void;
  onJumpToTask?: (taskId: string) => void;
  onJumpToRequirement?: (reqId: string) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      {trace.map((node) => {
        const isOpen = openId === node.req_id;
        return (
          <div key={node.req_id} className="group rounded-lg border bg-card">
            <div
              role="button"
              tabIndex={0}
              onClick={() => setOpenId(isOpen ? null : node.req_id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setOpenId(isOpen ? null : node.req_id);
                }
              }}
              className="flex w-full cursor-pointer items-center gap-3 p-3 text-left"
            >
              <motion.div animate={{ rotate: isOpen ? 90 : 0 }}>
                <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
              </motion.div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onJumpToRequirement?.(node.req_id);
                }}
                className="shrink-0 font-mono text-xs text-muted-foreground underline decoration-dotted transition-colors hover:text-brand-accent"
              >
                {node.req_id}
              </button>
              <Badge variant="secondary" className={cn("font-normal shrink-0", LAYER_COLORS[node.aep_layer])}>
                {node.aep_layer}
              </Badge>
              <span className="truncate text-sm">{node.description}</span>
              <span className="ml-auto shrink-0 text-xs text-muted-foreground">
                {node.observations.length} source · {node.tasks.length} task{node.tasks.length === 1 ? "" : "s"}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 shrink-0 opacity-0 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onAskAbout?.(`Explain requirement ${node.req_id} ("${node.description}") and show me its exact source in the document.`);
                }}
              >
                <MessageCircleQuestion className="h-3.5 w-3.5" />
              </Button>
            </div>

            <AnimatePresence initial={false}>
              {isOpen && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="overflow-hidden"
                >
                  <div className="grid grid-cols-1 gap-4 border-t p-4 md:grid-cols-2">
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Source in document — {node.source_section}
                      </h4>
                      <div className="space-y-2">
                        {node.observations.map((obs) => (
                          <div key={obs.obs_id} className="rounded-md bg-muted/50 p-2.5 text-xs">
                            <div className="mb-1 flex items-center gap-1.5 text-muted-foreground">
                              <Quote className="h-3 w-3" />
                              <span className="font-mono">{obs.obs_id}</span>
                            </div>
                            <p className="italic text-foreground/80">&ldquo;{obs.verbatim_quote || obs.text}&rdquo;</p>
                          </div>
                        ))}
                        {node.observations.length === 0 && (
                          <p className="text-xs text-muted-foreground">No direct source observations.</p>
                        )}
                      </div>
                    </div>
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                        Implementation tasks
                      </h4>
                      <div className="space-y-2">
                        {node.tasks.map((task) => (
                          <button
                            key={task.task_id}
                            onClick={() => onJumpToTask?.(task.task_id)}
                            className="w-full rounded-md border p-2.5 text-left text-xs transition-colors hover:border-brand-accent/50 hover:bg-accent"
                          >
                            <div className="mb-1 flex items-center justify-between">
                              <span className="font-mono text-muted-foreground">{task.task_id}</span>
                              <Badge variant="outline" className="text-[10px]">Phase {task.phase}</Badge>
                            </div>
                            <p className="font-medium">{task.title}</p>
                          </button>
                        ))}
                        {node.tasks.length === 0 && (
                          <p className="text-xs text-muted-foreground">No tasks generated yet.</p>
                        )}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        );
      })}
    </div>
  );
}
