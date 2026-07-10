"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { PartyPopper, ShieldCheck } from "lucide-react";
import type { CoverageAudit } from "@/lib/types";

export function CoverageBadge({ coverage }: { coverage: CoverageAudit }) {
  const [displayPercent, setDisplayPercent] = useState(0);
  const isPerfect = coverage.coverage_percent >= 100;
  const radius = 34;
  const circumference = 2 * Math.PI * radius;

  useEffect(() => {
    const target = coverage.coverage_percent;
    const start = performance.now();
    const duration = 900;
    let frame: number;
    function tick(now: number) {
      const t = Math.min(1, (now - start) / duration);
      setDisplayPercent(Math.round(target * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [coverage.coverage_percent]);

  const offset = circumference * (1 - displayPercent / 100);

  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-4">
      <div className="relative h-20 w-20 shrink-0">
        <svg viewBox="0 0 80 80" className="h-20 w-20 -rotate-90">
          <circle cx="40" cy="40" r={radius} fill="none" stroke="var(--muted)" strokeWidth="7" />
          <motion.circle
            cx="40"
            cy="40"
            r={radius}
            fill="none"
            stroke={isPerfect ? "#22c55e" : "var(--primary)"}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center text-sm font-semibold">
          {displayPercent}%
        </div>
      </div>
      <div>
        <div className="flex items-center gap-1.5 text-sm font-medium">
          {isPerfect ? (
            <>
              <PartyPopper className="h-4 w-4 text-green-500" />
              Nothing missed
            </>
          ) : (
            <>
              <ShieldCheck className="h-4 w-4 text-muted-foreground" />
              Coverage
            </>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {coverage.mapped_observations}/{coverage.total_observations} observations mapped to requirements
        </p>
      </div>
    </div>
  );
}
