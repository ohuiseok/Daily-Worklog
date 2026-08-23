import { loadSettings, parseDomainList, saveSettings } from "./settingsStore";

const form = document.querySelector<HTMLFormElement>("#settings-form");
const notionTokenInput = document.querySelector<HTMLInputElement>("#notion-token");
const databaseIdInput = document.querySelector<HTMLInputElement>("#database-id");
const userAllowedDomainsInput = document.querySelector<HTMLTextAreaElement>("#user-allowed-domains");
const ensureSchemaButton = document.querySelector<HTMLButtonElement>("#ensure-schema");
const searchTargetsButton = document.querySelector<HTMLButtonElement>("#search-targets");
const saveDatabaseIdButton = document.querySelector<HTMLButtonElement>("#save-database-id");
const saveDomainsButton = document.querySelector<HTMLButtonElement>("#save-domains");
const saveStatus = document.querySelector<HTMLElement>("#save-status");
const targetList = document.querySelector<HTMLElement>("#target-list");
const toast = document.querySelector<HTMLElement>("#toast");
let toastTimer: number | undefined;

interface OptionSearchTarget {
  id: string;
  title: string;
}

void initialize();

async function initialize(): Promise<void> {
  if (
    !form ||
    !notionTokenInput ||
    !databaseIdInput ||
    !userAllowedDomainsInput
  ) {
    return;
  }

  const settings = await loadSettings();
  notionTokenInput.value = settings.notionToken;
  databaseIdInput.value = settings.databaseId;
  userAllowedDomainsInput.value = settings.userAllowedDomains.join("\n");

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void saveCurrentSettings();
  });
  ensureSchemaButton?.addEventListener("click", () => {
    void ensureSchema();
  });
  searchTargetsButton?.addEventListener("click", () => {
    void searchTargets();
  });
  saveDatabaseIdButton?.addEventListener("click", () => {
    void saveCurrentSettings().then(() => {
      showToast("DB ID를 저장했습니다.", "ok");
    });
  });
  saveDomainsButton?.addEventListener("click", () => {
    void saveCurrentSettings().then(() => {
      showToast("추가 허용 도메인을 저장했습니다.", "ok");
    });
  });
}

async function saveCurrentSettings(): Promise<void> {
  if (
    !notionTokenInput ||
    !databaseIdInput ||
    !userAllowedDomainsInput
  ) {
    return;
  }

  await saveSettings({
    notionToken: notionTokenInput.value.trim(),
    databaseId: databaseIdInput.value.trim(),
    captureEnabled: true,
    rawRetentionHours: 24,
    userAllowedDomains: parseDomainList(userAllowedDomainsInput.value)
  });

  if (saveStatus) {
    setStatus("설정이 저장되었습니다.", "ok");
  }
}

async function ensureSchema(): Promise<void> {
  await saveCurrentSettings();
  setStatus("Notion 스키마를 확인하는 중입니다...");

  const response = await chrome.runtime.sendMessage({ type: "ensure-notion-schema" });
  if (response?.ok) {
    const added = response.result?.added?.length
      ? response.result.added.join(", ")
      : "추가할 항목 없음";
    setStatus(`스키마 준비 완료. 추가됨: ${added}`, "ok");
  } else {
    setStatus(`스키마 준비 실패: ${response?.error ?? "알 수 없는 오류"}`, "error");
  }
}

async function searchTargets(): Promise<void> {
  await saveCurrentSettings();
  clearTargets();
  setStatus("접근 가능한 Notion 데이터베이스를 찾는 중입니다...");

  const response = await chrome.runtime.sendMessage({ type: "search-notion-targets" });
  if (!response?.ok) {
    setStatus(`검색 실패: ${response?.error ?? "알 수 없는 오류"}`, "error");
    return;
  }

  const targets: OptionSearchTarget[] = Array.isArray(response.result)
    ? response.result.filter(isOptionSearchTarget)
    : [];
  if (!targets.length) {
    setStatus("접근 가능한 데이터베이스가 없습니다. Notion에서 이 Integration에 DB 권한을 주세요.", "error");
    return;
  }

  renderTargets(targets.slice(0, 5));
  setStatus(`접근 가능한 대상 ${targets.length}개를 찾았습니다.`, "ok");
}

function isOptionSearchTarget(value: unknown): value is OptionSearchTarget {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }
  const item = value as Partial<OptionSearchTarget>;
  return typeof item.id === "string" && typeof item.title === "string";
}

function renderTargets(targets: OptionSearchTarget[]): void {
  if (!targetList || !databaseIdInput) {
    return;
  }

  clearTargets();
  for (const target of targets) {
    const row = document.createElement("div");
    row.className = "target-row";

    const button = document.createElement("button");
    button.className = "target-button";
    button.type = "button";
    button.innerHTML = `
      <span class="target-content">
        <span class="target-title"></span>
        <span class="target-id"></span>
      </span>
    `;
    const copyButton = document.createElement("button");
    copyButton.className = "copy-button";
    copyButton.type = "button";
    copyButton.title = "ID 복사";
    copyButton.setAttribute("aria-label", "ID 복사");
    copyButton.innerHTML = `
      <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="14" height="14" x="8" y="8" rx="2" ry="2"></rect>
        <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"></path>
      </svg>
    `;

    const title = button.querySelector<HTMLElement>(".target-title");
    const id = button.querySelector<HTMLElement>(".target-id");
    if (title) {
      title.textContent = target.title;
    }
    if (id) {
      id.textContent = target.id;
    }

    button.addEventListener("click", () => {
      databaseIdInput.value = target.id;
      void saveCurrentSettings().then(async () => {
        const copied = await copyText(target.id);
        setStatus(
          copied
            ? `${target.title} 선택 완료. ID도 클립보드에 복사했습니다.`
            : `${target.title} 선택 완료. ID가 입력칸에 저장되었습니다.`,
          "ok"
        );
        showToast(
          copied
            ? "ID를 클립보드에 복사했습니다."
            : "ID가 입력칸에 저장되었습니다.",
          copied ? "ok" : "neutral"
        );
      });
    });

    copyButton.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      void copyText(target.id).then((copied) => {
        showToast(
          copied ? "ID를 클립보드에 복사했습니다." : "브라우저가 클립보드 복사를 막았습니다.",
          copied ? "ok" : "error"
        );
      });
    });

    row.append(button, copyButton);
    targetList.append(row);
  }
}

function clearTargets(): void {
  if (targetList) {
    targetList.replaceChildren();
  }
}

function setStatus(message: string, tone: "neutral" | "ok" | "error" = "neutral"): void {
  if (!saveStatus) {
    return;
  }
  saveStatus.textContent = message;
  if (tone === "neutral") {
    saveStatus.removeAttribute("data-tone");
  } else {
    saveStatus.dataset.tone = tone;
  }
}

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

function showToast(message: string, tone: "neutral" | "ok" | "error" = "neutral"): void {
  if (!toast) {
    return;
  }

  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.dataset.visible = "true";
  if (tone === "neutral") {
    toast.removeAttribute("data-tone");
  } else {
    toast.dataset.tone = tone;
  }
  toastTimer = window.setTimeout(() => {
    toast.dataset.visible = "false";
  }, 2_400);
}

export {};
