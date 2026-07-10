"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { CheckCircle2, Clock, FileText, XCircle } from "lucide-react";
import { listJobs } from "@/lib/api";
import type { JobSummary } from "@/lib/types";

const STATUS_ICON = {
  done: CheckCircle2,
  error: XCircle,
  queued: Clock,
} as const;

export default function HistoryPage() {
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listJobs()
      .then(setJobs)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-12">
      <h1 className="mb-6 text-xl font-semibold">Analysis history</h1>

      {loading && <p className="text-sm text-muted-foreground">Loading...</p>}
      {!loading && jobs.length === 0 && (
        <p className="text-sm text-muted-foreground">No documents analyzed yet.</p>
      )}

      <div className="space-y-2">
        {jobs.map((job, i) => {
          const Icon = STATUS_ICON[job.status as keyof typeof STATUS_ICON] ?? Clock;
          const content = (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.03, 0.3) }}
              className="flex items-center gap-3 rounded-lg border bg-card p-4 transition-colors hover:bg-muted/40"
            >
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{job.filename}</p>
                <p className="text-xs text-muted-foreground">{new Date(job.created_at).toLocaleString()}</p>
              </div>
              <Icon
                className={
                  job.status === "done"
                    ? "h-4 w-4 text-green-500"
                    : job.status === "error"
                    ? "h-4 w-4 text-destructive"
                    : "h-4 w-4 text-muted-foreground"
                }
              />
            </motion.div>
          );
          return job.status === "done" ? (
            <Link key={job.id} href={`/analyze/${job.id}`}>
              {content}
            </Link>
          ) : (
            <div key={job.id}>{content}</div>
          );
        })}
      </div>
    </div>
  );
}
