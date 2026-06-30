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

// Make the action icon open the side panel.
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

function notifyPanelOfTabChange(tabId: number) {
  chrome.tabs.get(tabId, (tab) => {
    if (chrome.runtime.lastError) return;
    chrome.runtime.sendMessage({ type: "TAB_CHANGED", url: tab.url }).catch(() => {});
  });
}

// Fire whenever the user switches to a different tab.
chrome.tabs.onActivated.addListener(({ tabId }) => notifyPanelOfTabChange(tabId));

// Fire whenever the URL changes within the same tab.
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.url) notifyPanelOfTabChange(tabId);
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "QUEUE_FILE") {
    const file: QueuedFile = { fileId: msg.fileId, fileName: msg.fileName };
    chrome.storage.local.get({ queuedFiles: [] }, (result) => {
      const existing: QueuedFile[] = result.queuedFiles;
      const updated = [
        ...existing.filter((f) => f.fileId !== file.fileId),
        file,
      ];
      chrome.storage.local.set({ queuedFiles: updated }, () => sendResponse({ ok: true }));
    });
    return true;
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
