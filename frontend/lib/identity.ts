"use client";

const KEY_PREFIX = "artemis_identity_";

export interface LocalIdentity {
  memberId: string;
  name: string;
  role: string;
}

export function getLocalIdentity(jobId: string): LocalIdentity | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(KEY_PREFIX + jobId);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setLocalIdentity(jobId: string, identity: LocalIdentity) {
  localStorage.setItem(KEY_PREFIX + jobId, JSON.stringify(identity));
}

export function clearLocalIdentity(jobId: string) {
  localStorage.removeItem(KEY_PREFIX + jobId);
}
