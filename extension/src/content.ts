/**
 * Content script injected into drive.google.com.
 *
 * Watches the Drive DOM for video file rows/cards and injects an
 * "Upload to YouTube" button next to each one. When clicked, it reads
 * the file ID and name from the DOM and sends them to the background
 * service worker, which stores them for the popup to pick up.
 *
 * Drive is a React SPA — the DOM mutates constantly. We use a
 * MutationObserver to re-run injection whenever the file list changes.
 *
 * Brittle surface: Drive's class names and data attributes may change.
 * If buttons stop appearing, check:
 *   - The list-row selector (currently [data-id])
 *   - The file name selector (currently .KF4T6b or [data-tooltip])
 *   - The MIME type indicator if we add video-only filtering
 */

const BUTTON_ATTR = "data-y2d-injected";
const BUTTON_CLASS = "y2d-yt-btn";

/** Inject a stylesheet once so buttons look consistent. */
function injectStyles() {
  if (document.getElementById("y2d-styles")) return;
  const style = document.createElement("style");
  style.id = "y2d-styles";
  style.textContent = `
    .${BUTTON_CLASS} {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      margin-left: 8px;
      padding: 2px 8px;
      border: 1px solid #c00;
      border-radius: 4px;
      background: #fff;
      color: #c00;
      font-size: 12px;
      font-family: Google Sans, Roboto, sans-serif;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      vertical-align: middle;
      line-height: 20px;
    }
    .${BUTTON_CLASS}:hover {
      background: #fce8e6;
    }
    .${BUTTON_CLASS}:active {
      background: #f5c6c2;
    }
    .${BUTTON_CLASS}.y2d-queued {
      border-color: #188038;
      color: #188038;
      cursor: default;
    }
  `;
  document.head.appendChild(style);
}

/** Extract file ID from a Drive list row element. */
function getFileId(row: Element): string | null {
  // List view: rows have data-id="FILE_ID"
  const id = row.getAttribute("data-id");
  if (id) return id;
  return null;
}

/** Extract file name from a row element — tries a few known selectors. */
function getFileName(row: Element): string {
  // The visible file name lives in different elements depending on view mode.
  // Try each known selector in order of reliability.
  const candidates = [
    row.querySelector<HTMLElement>(".KF4T6b"),          // list view label
    row.querySelector<HTMLElement>("[data-tooltip]"),    // sometimes the name is in a tooltip attr
    row.querySelector<HTMLElement>(".rgNFne"),           // grid view label
  ];
  for (const el of candidates) {
    if (!el) continue;
    const text = (el.getAttribute("data-tooltip") || el.textContent || "").trim();
    if (text) return text;
  }
  return "Untitled";
}

/** Send the chosen file to the background service worker. */
function queueFile(fileId: string, fileName: string, btn: HTMLButtonElement) {
  chrome.runtime.sendMessage(
    { type: "QUEUE_FILE", fileId, fileName },
    () => {
      btn.textContent = "✓ Queued";
      btn.classList.add("y2d-queued");
      btn.disabled = true;
    },
  );
}

/** Inject a button into a single row if not already present. */
function injectButton(row: Element) {
  if (row.hasAttribute(BUTTON_ATTR)) return;
  const fileId = getFileId(row);
  if (!fileId) return;

  row.setAttribute(BUTTON_ATTR, "1");

  const btn = document.createElement("button");
  btn.className = BUTTON_CLASS;
  btn.textContent = "▶ YouTube";
  btn.title = "Upload to YouTube via Y2D";

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    e.preventDefault();
    const fileName = getFileName(row);
    queueFile(fileId, fileName, btn);
  });

  // Append to the row's action area. Drive renders a right-side actions
  // cell; if we can't find it we fall back to appending to the row itself.
  const actionsCell =
    row.querySelector(".d-dFUf") ||   // list view actions cell
    row.querySelector(".Z8xBtb") ||   // another known actions cell class
    row;
  actionsCell.appendChild(btn);
}

/** Scan the DOM for all file rows and inject buttons. */
function injectAll() {
  // Drive renders file rows with a [data-id] attribute in both list and grid views.
  const rows = document.querySelectorAll("[data-id]:not([data-y2d-injected])");
  rows.forEach(injectButton);
}

/** Observe DOM mutations so we re-inject after Drive's SPA navigations. */
function observe() {
  const observer = new MutationObserver(() => injectAll());
  observer.observe(document.body, { childList: true, subtree: true });
}

injectStyles();
injectAll();
observe();
