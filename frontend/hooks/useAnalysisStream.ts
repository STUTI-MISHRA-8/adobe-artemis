"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE } from "@/lib/api";
import type { AnalysisResult, ProgressEvent } from "@/lib/types";

export function useAnalysisStream(jobId: string | null) {
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    setProgress(null);
    setResult(null);
    setError(null);

    const source = new EventSource(`${API_BASE}/api/jobs/${jobId}/stream`);
    sourceRef.current = source;

    source.addEventListener("progress", (e) => {
      setProgress(JSON.parse((e as MessageEvent).data));
    });

    source.addEventListener("result", (e) => {
      setResult(JSON.parse((e as MessageEvent).data));
      source.close();
    });

    source.addEventListener("error", (e) => {
      const messageEvent = e as MessageEvent;
      if (messageEvent.data) {
        try {
          const parsed = JSON.parse(messageEvent.data);
          setError(parsed.message ?? "Analysis failed");
        } catch {
          setError("Analysis failed");
        }
      }
      source.close();
    });

    return () => {
      source.close();
    };
  }, [jobId]);

  return { progress, result, error };
}
