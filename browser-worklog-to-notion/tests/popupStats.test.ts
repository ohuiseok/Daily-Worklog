import { describe, expect, it } from "vitest";

import { getActivityStats, saveActivityChunk } from "../src/activityStore";

class MemoryStorage {
  data: Record<string, unknown> = {};

  async get(): Promise<Record<string, unknown>> {
    return this.data;
  }

  async set(items: Record<string, unknown>): Promise<void> {
    this.data = { ...this.data, ...items };
  }
}

describe("popup activity stats", () => {
  it("counts today's chunks and pending days", async () => {
    const storage = new MemoryStorage();
    await saveActivityChunk(
      {
        domain: "chatgpt.com",
        pageTitle: "ChatGPT",
        urlHint: "chatgpt.com",
        fieldType: "contenteditable",
        text: "today chunk text that is long enough",
        createdAt: "2026-08-23T10:00:00.000Z"
      },
      storage
    );
    await saveActivityChunk(
      {
        domain: "github.com",
        pageTitle: "GitHub",
        urlHint: "github.com",
        fieldType: "textarea",
        text: "yesterday chunk text that is long enough",
        createdAt: "2026-08-22T10:00:00.000Z"
      },
      storage
    );

    const stats = await getActivityStats(storage, new Date("2026-08-23T12:00:00.000Z"));

    expect(stats.todayChunks).toBe(1);
    expect(stats.pendingDays).toEqual(["2026-08-22", "2026-08-23"]);
  });
});
