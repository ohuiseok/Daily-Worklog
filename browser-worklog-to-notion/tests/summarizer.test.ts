import { describe, expect, it } from "vitest";

import type { ActivityChunk } from "../src/activityStore";
import { extractKeywords, summarizeBrowserChunks } from "../src/summarizer";

function chunk(partial: Partial<ActivityChunk>): ActivityChunk {
  return {
    id: partial.id ?? crypto.randomUUID(),
    createdAt: partial.createdAt ?? "2026-08-23T10:00:00.000Z",
    domain: partial.domain ?? "chatgpt.com",
    pageTitle: partial.pageTitle ?? "ChatGPT",
    urlHint: partial.urlHint ?? partial.domain ?? "chatgpt.com",
    fieldType: partial.fieldType ?? "contenteditable",
    text: partial.text ?? "browser extension Local Detail Mode Notion worklog",
    charCount: partial.text?.length ?? 55,
    hash: partial.hash ?? "hash",
    uploaded: false
  };
}

describe("summarizer", () => {
  it("returns no content summary for empty chunks", () => {
    expect(summarizeBrowserChunks([])).toEqual({
      bullets: ["브라우저에서 새로 작성한 내용이 없다."],
      details: [],
      mainDomains: [],
      writtenChunks: 0
    });
  });

  it("extracts keywords from titles and chunks", () => {
    const keywords = extractKeywords([
      chunk({ pageTitle: "Notion API Plan", text: "Notion API calendar worklog worklog" })
    ]);

    expect(keywords.slice(0, 3).sort()).toEqual(["api", "calendar", "plan"]);
  });

  it("groups chunks into readable bullets", () => {
    const summary = summarizeBrowserChunks([
      chunk({
        domain: "chatgpt.com",
        pageTitle: "ChatGPT",
        text: "Local Detail Mode browser extension Notion worklog design"
      }),
      chunk({
        domain: "notion.so",
        pageTitle: "자동 작업일지 구현 계획",
        text: "Notion API calendar view worklog automation policy"
      })
    ]);

    expect(summary.writtenChunks).toBe(2);
    expect(summary.mainDomains).toEqual(["ChatGPT", "Notion"]);
    expect(summary.bullets).toHaveLength(2);
    expect(summary.bullets[0]).toContain("정리했다");
  });

  it("writes a natural Notion worklog sentence from localized titles", () => {
    const summary = summarizeBrowserChunks([
      chunk({
        domain: "app.notion.com",
        pageTitle: "(1) 취업준비",
        text: "이력서 포트폴리오 면접 준비 내용을 정리"
      })
    ]);

    expect(summary.mainDomains).toEqual(["Notion"]);
    expect(summary.bullets[0]).toBe("Notion에서 취업준비 관련 문서를 정리했다.");
    expect(summary.details[0]).toBe(
      'Notion의 "취업준비" 페이지에서 이력서 포트폴리오 면접 준비 내용을 정리했다.'
    );
  });

  it("does not copy a raw chunk verbatim into bullets", () => {
    const raw = "This entire raw sentence should not be copied directly into Notion summary";
    const summary = summarizeBrowserChunks([chunk({ text: raw })]);

    expect(summary.bullets.join(" ")).not.toContain(raw);
  });
});
