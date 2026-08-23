export interface ExtensionSettings {
  notionToken: string;
  databaseId: string;
  captureEnabled: boolean;
  rawRetentionHours: number;
  userAllowedDomains: string[];
}

export interface UploadState {
  lastSuccessAt: string | null;
}

export const DEFAULT_SETTINGS: ExtensionSettings = {
  notionToken: "",
  databaseId: "",
  captureEnabled: true,
  rawRetentionHours: 24,
  userAllowedDomains: []
};

const SETTINGS_KEY = "settings";
const UPLOAD_STATE_KEY = "uploadState";

interface ChromeLikeStorage {
  get(keys?: string | string[] | Record<string, unknown> | null): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
}

export async function loadSettings(
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<ExtensionSettings> {
  const result = await storage.get(SETTINGS_KEY);
  const saved = result[SETTINGS_KEY];
  if (!isRecord(saved)) {
    return { ...DEFAULT_SETTINGS };
  }

  return normalizeSettings(saved);
}

export async function saveSettings(
  settings: ExtensionSettings,
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<ExtensionSettings> {
  const normalized = normalizeSettings({ ...settings });
  await storage.set({ [SETTINGS_KEY]: normalized });
  return normalized;
}

export function parseDomainList(value: string): string[] {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .filter((item, index, array) => array.indexOf(item) === index);
}

export async function loadUploadState(
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<UploadState> {
  const result = await storage.get(UPLOAD_STATE_KEY);
  const saved = result[UPLOAD_STATE_KEY];
  if (!isRecord(saved)) {
    return { lastSuccessAt: null };
  }
  return {
    lastSuccessAt:
      typeof saved.lastSuccessAt === "string" ? saved.lastSuccessAt : null
  };
}

export async function saveUploadState(
  state: UploadState,
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<void> {
  await storage.set({ [UPLOAD_STATE_KEY]: state });
}

function normalizeSettings(value: Record<string, unknown>): ExtensionSettings {
  return {
    notionToken: typeof value.notionToken === "string" ? value.notionToken : "",
    databaseId: typeof value.databaseId === "string" ? value.databaseId : "",
    captureEnabled: true,
    rawRetentionHours: clampNumber(value.rawRetentionHours, 1, 168, 24),
    userAllowedDomains: Array.isArray(value.userAllowedDomains)
      ? value.userAllowedDomains
          .filter((item): item is string => typeof item === "string")
          .map((item) => item.trim().toLowerCase())
          .filter(Boolean)
      : []
  };
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const numberValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numberValue)) {
    return fallback;
  }
  return Math.min(Math.max(Math.trunc(numberValue), min), max);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
