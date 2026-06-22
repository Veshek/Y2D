// Thin client for the Clipflow backend. The session_id authenticates every call
// via the X-Session-Id header.

const BACKEND = "http://localhost:8000";

export type Privacy = "private" | "unlisted" | "public";

export interface TransferItem {
  file_id: string;
  title?: string;
  privacy: Privacy;
}

function headers(sessionId: string): HeadersInit {
  return { "Content-Type": "application/json", "X-Session-Id": sessionId };
}

export async function getMe(sessionId: string): Promise<{ email: string | null }> {
  const r = await fetch(`${BACKEND}/me`, { headers: headers(sessionId) });
  if (!r.ok) throw new Error("Not signed in");
  return r.json();
}

export async function createTransfers(
  sessionId: string,
  items: TransferItem[],
): Promise<{ transfer_ids: string[] }> {
  const r = await fetch(`${BACKEND}/transfers`, {
    method: "POST",
    headers: headers(sessionId),
    body: JSON.stringify({ items }),
  });
  if (!r.ok) throw new Error("Failed to create transfers");
  return r.json();
}

// Subscribe to a transfer's progress via SSE. Returns an unsubscribe function.
export function subscribeProgress(
  transferId: string,
  onUpdate: (record: any) => void,
): () => void {
  const es = new EventSource(`${BACKEND}/transfers/${transferId}/events`);
  es.addEventListener("progress", (e) => onUpdate(JSON.parse((e as MessageEvent).data)));
  es.onerror = () => es.close();
  return () => es.close();
}
