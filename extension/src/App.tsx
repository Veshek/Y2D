import { useEffect, useState } from "react";
import {
  createTransfers,
  subscribeProgress,
  type Privacy,
} from "./api";
import { getSession, signIn, signOut } from "./auth";
import type { QueuedFile } from "./background";

interface Progress {
  status: string;
  progress: number;
  youtube_video_id?: string;
  error?: string;
}

export default function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [queued, setQueued] = useState<QueuedFile[]>([]);
  const [privacy, setPrivacy] = useState<Privacy>("private");
  const [progress, setProgress] = useState<Record<string, Progress>>({});
  const [error, setError] = useState<string | null>(null);

  // Restore session on popup open.
  useEffect(() => {
    getSession().then(setSessionId);
  }, []);

  // Fetch queued files from the background service worker whenever the popup opens.
  useEffect(() => {
    chrome.runtime.sendMessage({ type: "GET_QUEUED" }, (res) => {
      if (res?.files) setQueued(res.files);
    });
  }, []);

  async function handleSignIn() {
    setError(null);
    try {
      setSessionId(await signIn());
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleTransfer() {
    if (!sessionId || queued.length === 0) return;
    setError(null);
    try {
      const { transfer_ids } = await createTransfers(
        sessionId,
        queued.map(({ fileId }) => ({ file_id: fileId, privacy })),
      );
      // Subscribe to progress for each transfer.
      transfer_ids.forEach((tid, i) => {
        const fileId = queued[i].fileId;
        subscribeProgress(tid, (rec) =>
          setProgress((p) => ({ ...p, [fileId]: rec })),
        );
      });
      // Clear the queue now that transfers are in flight.
      chrome.runtime.sendMessage({ type: "CLEAR_QUEUED" });
      setQueued([]);
    } catch (e) {
      setError(String(e));
    }
  }

  function removeFile(fileId: string) {
    const updated = queued.filter((f) => f.fileId !== fileId);
    setQueued(updated);
    chrome.storage.local.set({ queuedFiles: updated });
  }

  if (!sessionId) {
    return (
      <div className="app">
        <h1>Y2D</h1>
        <p>Move videos from Google Drive to YouTube.</p>
        <p className="hint">Click "▶ YouTube" on any file in Google Drive to queue it.</p>
        <button onClick={handleSignIn}>Connect Google account</button>
        {error && <p className="error">{error}</p>}
      </div>
    );
  }

  return (
    <div className="app">
      <header>
        <h1>Y2D</h1>
        <button className="link" onClick={() => signOut().then(() => setSessionId(null))}>
          Sign out
        </button>
      </header>

      <label className="privacy">
        Upload as:
        <select value={privacy} onChange={(e) => setPrivacy(e.target.value as Privacy)}>
          <option value="private">Private</option>
          <option value="unlisted">Unlisted</option>
          <option value="public">Public</option>
        </select>
      </label>

      {queued.length === 0 && (
        <p className="hint">No files queued. Go to Google Drive and click "▶ YouTube" on a video.</p>
      )}

      {error && <p className="error">{error}</p>}

      <ul className="videos">
        {queued.map(({ fileId, fileName }) => {
          const p = progress[fileId];
          return (
            <li key={fileId}>
              <span className="name">{fileName}</span>
              {p ? (
                <div className="status">
                  {p.status === "done" ? (
                    <a
                      href={`https://youtu.be/${p.youtube_video_id}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Done ↗
                    </a>
                  ) : p.status === "error" ? (
                    <span className="error">Error: {p.error}</span>
                  ) : (
                    <span>{p.status} — {p.progress}%</span>
                  )}
                </div>
              ) : (
                <button className="link remove" onClick={() => removeFile(fileId)}>✕</button>
              )}
            </li>
          );
        })}
      </ul>

      {queued.length > 0 && (
        <button onClick={handleTransfer}>
          Transfer {queued.length} to YouTube
        </button>
      )}
    </div>
  );
}
