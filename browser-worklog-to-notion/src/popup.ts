import { getActivityStats } from "./activityStore";
import { loadSettings, loadUploadState } from "./settingsStore";

void renderPopup();

async function renderPopup(): Promise<void> {
  const settings = await loadSettings();
  const uploadState = await loadUploadState();
  const stats = await getActivityStats();

  setCaptureStatus(settings.captureEnabled);
  setText("#today-chunks", String(stats.todayChunks));
  setText("#pending-days", formatPendingDays(stats.pendingDays));
  setText("#last-upload", formatUploadTime(uploadState.lastSuccessAt));

  document.querySelector<HTMLButtonElement>("#manual-upload")?.addEventListener("click", async (event) => {
    const button = event.currentTarget as HTMLButtonElement;
    button.disabled = true;
    setStatus("업로드 요청 중...", "neutral");
    try {
      const response = await chrome.runtime.sendMessage({ type: "manual-upload" });
      if (!response?.ok) {
        throw new Error(response?.error ?? "Upload failed.");
      }
      const result = response.result;
      if (result?.uploaded) {
        setStatus(`업로드 완료: ${result.chunkCount ?? 0}개 기록`, "success");
      } else {
        setStatus(uploadSkipMessage(result?.reason), "neutral");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error), "error");
    } finally {
      button.disabled = false;
    }
  });
}

function setText(selector: string, value: string): void {
  const element = document.querySelector<HTMLElement>(selector);
  if (element) {
    element.textContent = value;
  }
}

function setCaptureStatus(enabled: boolean): void {
  const element = document.querySelector<HTMLElement>("#capture-status");
  if (!element) {
    return;
  }
  element.textContent = enabled ? "켜짐" : "꺼짐";
  element.classList.toggle("is-off", !enabled);
}

function setStatus(message: string, tone: "neutral" | "success" | "error"): void {
  const element = document.querySelector<HTMLElement>("#popup-status");
  if (!element) {
    return;
  }
  element.textContent = message;
  element.classList.toggle("is-success", tone === "success");
  element.classList.toggle("is-error", tone === "error");
}

function formatPendingDays(days: string[]): string {
  if (days.length === 0) {
    return "없음";
  }
  if (days.length <= 2) {
    return days.join(", ");
  }
  return `${days[0]} 외 ${days.length - 1}일`;
}

function formatUploadTime(value: string | null | undefined): string {
  if (!value) {
    return "없음";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function uploadSkipMessage(reason: string | undefined): string {
  if (reason === "no_pending_chunks") {
    return "업로드할 새 기록이 없습니다.";
  }
  if (reason === "missing_notion_settings") {
    return "Options에서 Notion 설정을 먼저 완료하세요.";
  }
  return "업로드가 실행되지 않았습니다.";
}

export {};
