import { describe, expect, it } from "vitest";

import { filterSensitiveText } from "../src/sensitiveFilter";

describe("filterSensitiveText", () => {
  it("keeps ordinary worklog text", () => {
    expect(filterSensitiveText("Notion API worklog design notes")).toEqual({
      action: "keep",
      text: "Notion API worklog design notes",
      reasons: []
    });
  });

  it("masks emails and phone numbers", () => {
    const result = filterSensitiveText("Contact user@example.com or 010-1234-5678");

    expect(result.action).toBe("mask");
    expect(result.text).toContain("[email]");
    expect(result.text).toContain("[phone]");
    expect(result.reasons).toEqual(["email", "phone"]);
  });

  it("discards api keys", () => {
    const result = filterSensitiveText("Use ntn_abcdefghijklmnopqrstuvwxyz as token");

    expect(result.action).toBe("discard");
    expect(result.reasons).toEqual(["api_key"]);
  });

  it("discards secret context", () => {
    const result = filterSensitiveText("password is hunter2");

    expect(result.action).toBe("discard");
    expect(result.reasons).toEqual(["secret_context"]);
  });

  it("discards private keys", () => {
    const result = filterSensitiveText("-----BEGIN PRIVATE KEY-----\nabc");

    expect(result.action).toBe("discard");
    expect(result.reasons).toEqual(["private_key"]);
  });
});
