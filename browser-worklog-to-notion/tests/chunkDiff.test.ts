import { describe, expect, it } from "vitest";

import { createChunkFromSnapshots } from "../src/captureEngine";

describe("createChunkFromSnapshots", () => {
  it("returns appended text as a chunk", () => {
    const chunk = createChunkFromSnapshots(
      "hello",
      "hello this is a long enough browser worklog note"
    );

    expect(chunk).toEqual({
      text: "this is a long enough browser worklog note",
      charCount: 42
    });
  });

  it("ignores short additions", () => {
    expect(createChunkFromSnapshots("hello", "hello short")).toBeNull();
  });

  it("ignores deletions", () => {
    expect(createChunkFromSnapshots("hello world", "hello")).toBeNull();
  });

  it("limits chunk size", () => {
    const chunk = createChunkFromSnapshots("a", `a${"b".repeat(50)}`, {
      minChars: 20,
      maxSnapshotChars: 100,
      maxChunkChars: 30
    });

    expect(chunk?.text).toHaveLength(30);
  });
});
