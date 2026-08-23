export interface ActivityChunk {
  id: string;
  createdAt: string;
  domain: string;
  pageTitle: string;
  urlHint: string;
  fieldType: string;
  text: string;
  charCount: number;
  hash: string;
  uploaded: boolean;
}

export interface ActivityStoreLimits {
  maxChunkChars: number;
  maxChunksPerPagePerDay: number;
  maxTotalCharsPerDay: number;
  rawRetentionHours: number;
}

export const DEFAULT_ACTIVITY_LIMITS: ActivityStoreLimits = {
  maxChunkChars: 2_000,
  maxChunksPerPagePerDay: 50,
  maxTotalCharsPerDay: 200_000,
  rawRetentionHours: 24
};

const CHUNKS_KEY = "activityChunks";

interface ChromeLikeStorage {
  get(keys?: string | string[] | Record<string, unknown> | null): Promise<Record<string, unknown>>;
  set(items: Record<string, unknown>): Promise<void>;
}

export interface SaveChunkInput {
  domain: string;
  pageTitle: string;
  urlHint: string;
  fieldType: string;
  text: string;
  createdAt?: string;
}

export async function saveActivityChunk(
  input: SaveChunkInput,
  storage: ChromeLikeStorage = chrome.storage.local,
  limits: ActivityStoreLimits = DEFAULT_ACTIVITY_LIMITS
): Promise<ActivityChunk | null> {
  const createdAt = input.createdAt ?? new Date().toISOString();
  const text = input.text.slice(0, limits.maxChunkChars);
  const hash = hashChunk([input.domain, input.pageTitle, text].join("\n"));
  const chunks = await loadChunks(storage);

  if (chunks.some((chunk) => chunk.hash === hash)) {
    return null;
  }

  const dateKey = createdAt.slice(0, 10);
  const pageChunksToday = chunks.filter(
    (chunk) =>
      chunk.createdAt.slice(0, 10) === dateKey &&
      chunk.domain === input.domain &&
      chunk.pageTitle === input.pageTitle
  );
  if (pageChunksToday.length >= limits.maxChunksPerPagePerDay) {
    return null;
  }

  const totalCharsToday = chunks
    .filter((chunk) => chunk.createdAt.slice(0, 10) === dateKey)
    .reduce((sum, chunk) => sum + chunk.charCount, 0);
  if (totalCharsToday + text.length > limits.maxTotalCharsPerDay) {
    return null;
  }

  const chunk: ActivityChunk = {
    id: `chunk_${createdAt.replace(/\W/g, "")}_${hash.slice(0, 8)}`,
    createdAt,
    domain: input.domain,
    pageTitle: input.pageTitle,
    urlHint: input.urlHint,
    fieldType: input.fieldType,
    text,
    charCount: text.length,
    hash,
    uploaded: false
  };

  await saveChunks([...chunks, chunk], storage);
  return chunk;
}

export async function getChunksSince(
  since: string,
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<ActivityChunk[]> {
  const chunks = await loadChunks(storage);
  return chunks.filter((chunk) => !chunk.uploaded && chunk.createdAt > since);
}

export async function markChunksUploaded(
  chunkIds: string[],
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<void> {
  const idSet = new Set(chunkIds);
  const chunks = await loadChunks(storage);
  await saveChunks(
    chunks.map((chunk) =>
      idSet.has(chunk.id) ? { ...chunk, uploaded: true } : chunk
    ),
    storage
  );
}

export async function pruneExpiredChunks(
  nowIso: string,
  storage: ChromeLikeStorage = chrome.storage.local,
  limits: ActivityStoreLimits = DEFAULT_ACTIVITY_LIMITS
): Promise<number> {
  const nowMs = Date.parse(nowIso);
  const maxAgeMs = limits.rawRetentionHours * 60 * 60 * 1000;
  const chunks = await loadChunks(storage);
  const kept = chunks.filter((chunk) => nowMs - Date.parse(chunk.createdAt) <= maxAgeMs);
  await saveChunks(kept, storage);
  return chunks.length - kept.length;
}

export async function loadChunks(
  storage: ChromeLikeStorage = chrome.storage.local
): Promise<ActivityChunk[]> {
  const result = await storage.get(CHUNKS_KEY);
  const value = result[CHUNKS_KEY];
  return Array.isArray(value) ? value.filter(isActivityChunk) : [];
}

export async function getActivityStats(
  storage: ChromeLikeStorage = chrome.storage.local,
  now: Date = new Date()
): Promise<{ todayChunks: number; pendingDays: string[] }> {
  const chunks = await loadChunks(storage);
  const today = now.toISOString().slice(0, 10);
  const pending = chunks.filter((chunk) => !chunk.uploaded);
  return {
    todayChunks: chunks.filter((chunk) => chunk.createdAt.slice(0, 10) === today).length,
    pendingDays: [...new Set(pending.map((chunk) => chunk.createdAt.slice(0, 10)))].sort()
  };
}

function saveChunks(chunks: ActivityChunk[], storage: ChromeLikeStorage): Promise<void> {
  return storage.set({ [CHUNKS_KEY]: chunks });
}

export function hashChunk(value: string): string {
  let hash = 5381;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 33) ^ value.charCodeAt(index);
  }
  return (hash >>> 0).toString(16);
}

function isActivityChunk(value: unknown): value is ActivityChunk {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const item = value as Partial<ActivityChunk>;
  return (
    typeof item.id === "string" &&
    typeof item.createdAt === "string" &&
    typeof item.domain === "string" &&
    typeof item.pageTitle === "string" &&
    typeof item.urlHint === "string" &&
    typeof item.fieldType === "string" &&
    typeof item.text === "string" &&
    typeof item.charCount === "number" &&
    typeof item.hash === "string" &&
    typeof item.uploaded === "boolean"
  );
}
