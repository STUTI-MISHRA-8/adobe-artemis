"use client";

import { AnimatePresence, motion } from "framer-motion";
import { Check, FileSearch, Layers, ListTree, Loader2, Workflow } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProgressEvent } from "@/lib/types";

const STAGES = [
  { key: "parsing", label: "Parsing document", icon: FileSearch },
  { key: "extracting", label: "Extracting requirements", icon: Layers },
  { key: "structuring", label: "Structuring requirements", icon: ListTree },
  { key: "planning", label: "Building execution plan", icon: Workflow },
] as const;

function stageIndex(stage: string | undefined) {
  if (!stage) return -1;
  if (stage === "done") return STAGES.length;
  return STAGES.findIndex((s) => s.key === stage);
}

export function LiveProgress({ progress }: { progress: ProgressEvent | null }) {
  const currentIndex = stageIndex(progress?.stage);

  return (
    <div className="w-full max-w-xl space-y-8">
      <div className="flex items-center justify-between">
        {STAGES.map((stage, i) => {
          const isDone = currentIndex > i;
          const isActive = currentIndex === i;
          const Icon = stage.icon;
          return (
            <div key={stage.key} className="flex flex-1 flex-col items-center gap-2">
              <motion.div
                animate={isActive ? { scale: [1, 1.08, 1] } : {}}
                transition={{ repeat: isActive ? Infinity : 0, duration: 1.4 }}
                className={cn(
                  "flex h-11 w-11 items-center justify-center rounded-full border-2 transition-colors",
                  isDone && "border-primary bg-primary text-primary-foreground",
                  isActive && "border-primary text-primary",
                  !isDone && !isActive && "border-border text-muted-foreground"
                )}
              >
                {isDone ? <Check className="h-5 w-5" /> : isActive ? <Loader2 className="h-5 w-5 animate-spin" /> : <Icon className="h-5 w-5" />}
              </motion.div>
              <span className={cn("text-center text-xs font-medium", isActive ? "text-foreground" : "text-muted-foreground")}>
                {stage.label}
              </span>
              {i < STAGES.length - 1 && (
                <div className="absolute" />
              )}
            </div>
          );
        })}
      </div>

      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          animate={{ width: `${progress?.percent ?? 0}%` }}
          transition={{ ease: "easeOut", duration: 0.4 }}
        />
      </div>

      <div className="h-6 text-center text-sm text-muted-foreground">
        <AnimatePresence mode="wait">
          {progress?.message && (
            <motion.p
              key={progress.message}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.2 }}
            >
              {progress.message}
            </motion.p>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
