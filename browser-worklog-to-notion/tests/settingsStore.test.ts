import { describe, expect, it } from "vitest";

import { DEFAULT_SETTINGS, loadSettings, parseDomainList, saveSettings } from "../src/settingsStore";

class MemoryStorage {
  data: Record<string, unknown> = {};

  async get(): Promise<Record<string, unknown>> {
    return this.data;
  }

  async set(items: Record<string, unknown>): Promise<void> {
    this.data = { ...this.data, ...items };
  }
}

describe("settingsStore", () => {
  it("loads defaults when settings are missing", async () => {
    const storage = new MemoryStorage();

    await expect(loadSettings(storage)).resolves.toEqual(DEFAULT_SETTINGS);
  });

  it("saves and normalizes settings", async () => {
    const storage = new MemoryStorage();

    const saved = await saveSettings(
      {
        notionToken: " ntn_test ",
        databaseId: " db ",
        captureEnabled: true,
        rawRetentionHours: 999,
        userAllowedDomains: [" GitHub.com ", ""]
      },
      storage
    );

    expect(saved.rawRetentionHours).toBe(168);
    expect(saved.userAllowedDomains).toEqual(["github.com"]);
    await expect(loadSettings(storage)).resolves.toEqual(saved);
  });

  it("parses newline and comma separated domains", () => {
    expect(parseDomainList("github.com\nnotion.so, chatgpt.com\ngithub.com")).toEqual([
      "github.com",
      "notion.so",
      "chatgpt.com"
    ]);
  });
});
