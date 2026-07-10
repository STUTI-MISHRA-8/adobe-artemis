"use client";

import { use } from "react";
import { AlertTriangle } from "lucide-react";
import { LiveProgress } from "@/components/pipeline/LiveProgress";
import { ResultsDashboard } from "@/components/results/ResultsDashboard";
import { useAnalysisStream } from "@/hooks/useAnalysisStream";

export default function AnalyzePage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);
  const { progress, result, error } = useAnalysisStream(jobId);

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
        <AlertTriangle className="h-8 w-8 text-destructive" />
        <p className="max-w-md text-sm text-muted-foreground">{error}</p>
      </div>
    );
  }

  if (result) {
    return <ResultsDashboard result={result} />;
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-6">
      <LiveProgress progress={progress} />
    </div>
  );
}
