import type { AepStatus, AnalysisResult, ChatMessage, JobSummary, TaskExecution, TaskPayload, TeamMember, TeamRole, WizardState } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8010";

export async function uploadDocument(file: File): Promise<{ job_id: string; cached: boolean }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? "Upload failed");
  }
  return res.json();
}

export async function listJobs(): Promise<JobSummary[]> {
  const res = await fetch(`${API_BASE}/api/jobs`);
  if (!res.ok) throw new Error("Failed to load history");
  return res.json();
}

export async function getJob(jobId: string): Promise<{ result?: AnalysisResult; status: string }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) throw new Error("Job not found");
  return res.json();
}

export function exportUrl(jobId: string, format: "json" | "requirements_csv" | "tasks_csv" | "markdown") {
  return `${API_BASE}/api/jobs/${jobId}/export?format=${format}`;
}

export async function getChatHistory(jobId: string): Promise<ChatMessage[]> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/chat`);
  if (!res.ok) throw new Error("Failed to load chat history");
  return res.json();
}

export interface ChatDonePayload {
  answer: string;
  citations: string[];
  followups: string[];
  provider: string;
}

async function streamSSE<TDone>(
  url: string,
  init: RequestInit,
  handlers: {
    onChunk: (text: string) => void;
    onDone: (data: TDone) => void;
    onError: (message: string) => void;
  },
  failureMessage: string
) {
  try {
    const res = await fetch(url, init);
    if (!res.ok || !res.body) {
      throw new Error(`${failureMessage} (${res.status})`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = buffer.indexOf("\n\n");
      while (boundary !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        boundary = buffer.indexOf("\n\n");

        const eventMatch = rawEvent.match(/^event: (.+)$/m);
        const dataMatch = rawEvent.match(/^data: (.+)$/m);
        if (!eventMatch || !dataMatch) continue;

        const eventType = eventMatch[1];
        const data = JSON.parse(dataMatch[1]);
        if (eventType === "chunk") {
          handlers.onChunk(data.text);
        } else if (eventType === "done") {
          handlers.onDone(data);
        }
      }
    }
  } catch (err) {
    handlers.onError(err instanceof Error ? err.message : failureMessage);
  }
}

export async function streamChat(
  jobId: string,
  question: string,
  history: { role: string; content: string }[],
  handlers: {
    onChunk: (text: string) => void;
    onDone: (payload: ChatDonePayload) => void;
    onError: (message: string) => void;
  }
) {
  await streamSSE<ChatDonePayload>(
    `${API_BASE}/api/jobs/${jobId}/chat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    },
    handlers,
    "Chat request failed"
  );
}

export async function getWizard(jobId: string): Promise<WizardState> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard`);
  if (!res.ok) throw new Error("Failed to load wizard");
  return res.json();
}

export async function setTaskStatus(jobId: string, taskId: string, status: "done" | "pending"): Promise<WizardState> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Failed to update task status");
  return res.json();
}

export async function streamTaskHowto(
  jobId: string,
  taskId: string,
  handlers: {
    onChunk: (text: string) => void;
    onDone: (payload: { content: string; cached: boolean }) => void;
    onError: (message: string) => void;
  }
) {
  await streamSSE<{ content: string; cached: boolean }>(
    `${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/howto`,
    { method: "POST" },
    handlers,
    "Failed to generate how-to guide"
  );
}

export async function getTaskPayload(jobId: string, taskId: string): Promise<TaskPayload> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/payload`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to generate API payload");
  return res.json();
}

export async function executeTaskPayload(jobId: string, taskId: string): Promise<TaskExecution> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/execute`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? "Failed to execute against AEP");
  }
  return res.json();
}

export async function simulateTaskPayload(jobId: string, taskId: string): Promise<TaskExecution> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/simulate`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? "Failed to simulate execution");
  }
  return res.json();
}

export async function getAepStatus(): Promise<AepStatus> {
  const res = await fetch(`${API_BASE}/api/config/aep-status`);
  if (!res.ok) return { configured: false, sandbox: null };
  return res.json();
}

export async function getTeam(jobId: string): Promise<TeamMember[]> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/team`);
  if (!res.ok) throw new Error("Failed to load team");
  return res.json();
}

export async function joinTeam(jobId: string, name: string, role: TeamRole): Promise<TeamMember & { auto_assigned: number }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/team`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, role }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? "Failed to join team");
  }
  return res.json();
}

export async function leaveTeam(jobId: string, memberId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/team/${memberId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to remove team member");
}

export async function assignTask(jobId: string, taskId: string, memberId: string | null): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/wizard/tasks/${taskId}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ member_id: memberId }),
  });
  if (!res.ok) throw new Error("Failed to assign task");
}
