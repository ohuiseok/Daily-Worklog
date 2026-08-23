import { saveActivityChunk } from "./activityStore";
import {
  ensureConfiguredNotionSchema,
  searchConfiguredNotionTargets,
  uploadPendingBrowserWorklog
} from "./notionClient";

chrome.runtime.onInstalled.addListener(() => {
  console.info("Browser Worklog installed.");
});

chrome.runtime.onStartup.addListener(() => {
  console.info("Browser Worklog started.");
  void uploadPending("startup");
});

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "activity-chunk") {
    void saveActivityChunk(message.payload).then((chunk) => {
      sendResponse({ ok: true, saved: Boolean(chunk) });
    });
    return true;
  }

  if (message?.type === "manual-upload") {
    void uploadPendingBrowserWorklog()
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error: unknown) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error)
        })
      );
    return true;
  }

  if (message?.type === "ensure-notion-schema") {
    void ensureConfiguredNotionSchema()
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error: unknown) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error)
        })
      );
    return true;
  }

  if (message?.type === "search-notion-targets") {
    void searchConfiguredNotionTargets()
      .then((result) => sendResponse({ ok: true, result }))
      .catch((error: unknown) =>
        sendResponse({
          ok: false,
          error: error instanceof Error ? error.message : String(error)
        })
      );
    return true;
  }

  return false;
});

async function uploadPending(reason: string): Promise<void> {
  try {
    const result = await uploadPendingBrowserWorklog();
    console.info("Browser Worklog upload checked.", { reason, result });
  } catch (error) {
    console.warn("Browser Worklog upload failed.", {
      reason,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
