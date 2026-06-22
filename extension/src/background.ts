/**
 * Background service worker.
 *
 * Acts as a message bus between the content script (running on
 * drive.google.com) and the popup (App.tsx).
 *
 * Flow:
 *   content.ts  --QUEUE_FILE-->  background  --stored in chrome.storage.local-->  App.tsx
 *   App.tsx     --GET_QUEUED-->  background  (reads from storage, returns list)
 *   App.tsx     --CLEAR_QUEUED-> background  (clears after transfers are created)
 */

export interface QueuedFile {
  fileId: string;
  fileName: string;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "QUEUE_FILE") {
    const file: QueuedFile = { fileId: msg.fileId, fileName: msg.fileName };
    chrome.storage.local.get({ queuedFiles: [] }, (result) => {
      const existing: QueuedFile[] = result.queuedFiles;
      // Deduplicate by fileId.
      const updated = [
        ...existing.filter((f) => f.fileId !== file.fileId),
        file,
      ];
      chrome.storage.local.set({ queuedFiles: updated }, () => sendResponse({ ok: true }));
    });
    return true; // keep message channel open for async sendResponse
  }

  if (msg.type === "GET_QUEUED") {
    chrome.storage.local.get({ queuedFiles: [] }, (result) => {
      sendResponse({ files: result.queuedFiles });
    });
    return true;
  }

  if (msg.type === "CLEAR_QUEUED") {
    chrome.storage.local.set({ queuedFiles: [] }, () => sendResponse({ ok: true }));
    return true;
  }
});
