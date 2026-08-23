import { describe, expect, it } from "vitest";

import {
  DEFAULT_ACTIVITY_LIMITS,
  getChunksSince,
  loadChunks,
  markChunksUploaded,
  pruneExpiredChunks,
  saveActivityChunk
} from "../src/activityStore";

class MemoryStorage {
  data: Record<string, unknown> = {};

  async get(): Promise<Record<string, unknown>> {
    return this.data;
  }

  async set(items: Record<string, unknown>): Promise<void> {
    this.data = { ...this.data, ...items };
  }
}

const baseInput = {
  domain: "chatgpt.com",
  pageTitle: "ChatGPT",
  urlHint: "chatgpt.com",
  fieldType: "contenteditable",
  text: "브라우저 확장 프로그램 Local Detail Mode 구현 내용을 작성했다."
};

describe("activityStore", () => {
  it("saves chunks", async () => {
    const storage = new MemoryStorage();

    const chunk = await saveActivityChunk(
      { ...baseInput, createdAt: "2026-08-23T10:00:00.000Z" },
      storage
    );

    expect(chunk?.uploaded).toBe(false);
    await expect(loadChunks(storage)).resolves.toHaveLength(1);
  });

  it("deduplicates by hash", async () => {
    const storage = new MemoryStorage();

    await saveActivityChunk(baseInput, storage);
    await saveActivityChunk(baseInput, storage);

    await expect(loadChunks(storage)).resolves.toHaveLength(1);
  });

  it("queries chunks since a timestamp", async () => {
    const storage = new MemoryStorage();
    const oldChunk = await saveActivityChunk(
      { ...baseInput, text: "old enough chunk text value", createdAt: "2026-08-22T10:00:00.000Z" },
      storage
    );
    const newChunk = await saveActivityChunk(
      { ...baseInput, text: "new enough chunk text value", createdAt: "2026-08-23T10:00:00.000Z" },
      storage
    );
    await markChunksUploaded([oldChunk!.id], storage);

    const chunks = await getChunksSince("2026-08-22T12:00:00.000Z", storage);

    expect(chunks.map((chunk) => chunk.id)).toEqual([newChunk!.id]);
  });

  it("applies per page chunk limits", async () => {
    const storage = new MemoryStorage();
    const limits = { ...DEFAULT_ACTIVITY_LIMITS, maxChunksPerPagePerDay: 1 };

    const first = await saveActivityChunk({ ...baseInput, text: "first long enough text" }, storage, limits);
    const second = await saveActivityChunk({ ...baseInput, text: "second long enough text" }, storage, limits);

    expect(first).not.toBeNull();
    expect(second).toBeNull();
  });

  it("applies total daily char limits", async () => {
    const storage = new MemoryStorage();
    const limits = { ...DEFAULT_ACTIVITY_LIMITS, maxTotalCharsPerDay: 25 };

    const first = await saveActivityChunk({ ...baseInput, text: "12345678901234567890" }, storage, limits);
    const second = await saveActivityChunk({ ...baseInput, text: "abcdefghijklmnopqrst" }, storage, limits);

    expect(first).not.toBeNull();
    expect(second).toBeNull();
  });

  it("prunes expired chunks", async () => {
    const storage = new MemoryStorage();
    await saveActivityChunk(
      { ...baseInput, text: "old chunk text for pruning", createdAt: "2026-08-22T00:00:00.000Z" },
      storage
    );
    await saveActivityChunk(
      { ...baseInput, text: "fresh chunk text for keeping", createdAt: "2026-08-23T00:00:00.000Z" },
      storage
    );

    const removed = await pruneExpiredChunks("2026-08-23T12:00:00.000Z", storage, {
      ...DEFAULT_ACTIVITY_LIMITS,
      rawRetentionHours: 24
    });

    expect(removed).toBe(1);
    await expect(loadChunks(storage)).resolves.toHaveLength(1);
  });
});
