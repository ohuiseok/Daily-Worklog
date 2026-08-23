import { isCaptureAllowedForUrl } from "./domainMatcher";
import {
  CaptureSession,
  extractEditableText,
  findEditableElement,
  shouldIgnoreEditable
} from "./captureEngine";
import { filterSensitiveText } from "./sensitiveFilter";

interface ContentScriptSettings {
  captureEnabled: boolean;
  userAllowedDomains: string[];
}

const DEFAULT_CONTENT_SCRIPT_SETTINGS: ContentScriptSettings = {
  captureEnabled: true,
  userAllowedDomains: []
};

let debounceTimer: number | undefined;
const captureSession = new CaptureSession();
const CAPTURE_DEBOUNCE_MS = 1_500;

void initializeContentScript();

async function initializeContentScript(): Promise<void> {
  const settings = await loadContentScriptSettings();
  const allowed = settings.captureEnabled && isCaptureAllowedForUrl(window.location.href, {
    userAllowedDomains: settings.userAllowedDomains
  });

  if (!allowed) {
    console.info("Browser Worklog capture disabled for this page.", {
      host: window.location.host
    });
    return;
  }

  console.info("Browser Worklog capture enabled.", {
    host: window.location.host
  });

  document.addEventListener("input", handleInput, true);
  document.addEventListener("beforeinput", handleInput, true);
  document.addEventListener("keyup", handleInput, true);
  document.addEventListener("paste", handleInput, true);
  document.addEventListener("focusin", handleFocusIn, true);
  document.addEventListener("compositionstart", () => captureSession.startComposition(), true);
  document.addEventListener("compositionend", handleCompositionEnd, true);
}

function handleFocusIn(event: FocusEvent): void {
  const target = event.target instanceof Element ? event.target : document.activeElement;
  const editable = findEditableElement(target);
  if (!editable || shouldIgnoreEditable(editable)) {
    return;
  }

  captureSession.setBaseline(extractEditableText(editable));
}

function handleInput(event: Event): void {
  const target = event.target instanceof Element ? event.target : document.activeElement;
  const editable = findEditableElement(target);
  if (!editable || shouldIgnoreEditable(editable)) {
    return;
  }

  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => {
    const currentSnapshot = extractEditableText(editable);
    const chunk = captureSession.update(currentSnapshot);

    if (chunk) {
      const filtered = filterSensitiveText(chunk.text);
      if (filtered.action === "discard") {
        console.info("Browser Worklog discarded sensitive chunk.", {
          reasons: filtered.reasons
        });
        return;
      }

      console.info("Browser Worklog captured chunk draft.", {
        host: window.location.host,
        charCount: filtered.text.length,
        masked: filtered.action === "mask"
      });
      void chrome.runtime.sendMessage({
        type: "activity-chunk",
        payload: {
          domain: window.location.hostname,
          pageTitle: document.title,
          urlHint: window.location.hostname,
          fieldType: editable.tagName.toLowerCase(),
          text: filtered.text
        }
      });
    }
  }, CAPTURE_DEBOUNCE_MS);
}

function handleCompositionEnd(event: CompositionEvent): void {
  captureSession.endComposition();
  handleInput(event);
}

async function loadContentScriptSettings(): Promise<ContentScriptSettings> {
  const result = await chrome.storage.local.get("settings");
  const saved = result.settings;
  if (typeof saved !== "object" || saved === null || Array.isArray(saved)) {
    return { ...DEFAULT_CONTENT_SCRIPT_SETTINGS };
  }

  const record = saved as Record<string, unknown>;
  return {
    captureEnabled: true,
    userAllowedDomains: Array.isArray(record.userAllowedDomains)
      ? record.userAllowedDomains
          .filter((item): item is string => typeof item === "string")
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean)
      : []
  };
}
