import { describe, expect, it } from "vitest";

import { assertPayloadExcludesRawText, buildBrowserNotionPayload } from "../src/notionPayload";

const summary = {
  bullets: [
    "ChatGPT에서 확장 프로그램 관련 질문과 답변을 정리했다.",
    "Notion에서 자동 작업일지 관련 문서를 정리했다."
  ],
  details: [
    "ChatGPT에서 확장 프로그램 설정 흐름을 정리한 내용을 작성했다.",
    "Notion에서 자동 작업일지 데이터베이스 설정 내용을 작성했다."
  ],
  mainDomains: ["ChatGPT", "Notion"],
  writtenChunks: 4
};

describe("notionPayload", () => {
  it("builds Browser source properties", () => {
    const payload = buildBrowserNotionPayload({
      databaseId: "db",
      projectName: "Browser Worklog",
      worklogDate: "2026-08-23",
      source: "Browser",
      summary
    });

    expect(payload.parent).toEqual({ database_id: "db" });
    expect(JSON.stringify(payload)).toContain("Browser");
    expect(JSON.stringify(payload)).toContain("Written Chunks");
    expect(JSON.stringify(payload)).toContain("작성 내용");
    expect(JSON.stringify(payload)).not.toContain("Keywords");
  });

  it("does not include raw chunk text", () => {
    const raw = "This is the exact raw prompt I wrote and it must not be copied";
    const payload = buildBrowserNotionPayload({
      databaseId: "db",
      projectName: "Browser Worklog",
      worklogDate: "2026-08-23",
      source: "Browser",
      summary
    });

    expect(JSON.stringify(payload)).not.toContain(raw);
    expect(() => assertPayloadExcludesRawText(payload, [raw])).not.toThrow();
  });

  it("throws when raw text is accidentally included", () => {
    expect(() =>
      assertPayloadExcludesRawText({ children: ["raw secret text"] }, ["raw secret text"])
    ).toThrow("Browser Notion payload includes raw text.");
  });
});
