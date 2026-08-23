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
    expect(summary.bullets[0]).toContain("질문/프롬프트를 작성했다");
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
    expect(summary.bullets[0]).toBe('Notion에서 "취업준비" 페이지에 문서 내용을 작성했다.');
    expect(summary.details[0]).toContain(
      "Notion / 취업준비: 작성 주제: 면접, 이력서, 정리, 준비, 포트폴리오"
    );
    expect(summary.details[0]).toContain("내용 일부: 이력서 포트폴리오 면접 준비 내용을 정리");
  });

  it("does not copy a raw chunk verbatim into bullets", () => {
    const raw = "This entire raw sentence should not be copied directly into Notion summary";
    const summary = summarizeBrowserChunks([chunk({ text: raw })]);

    expect(summary.bullets.join(" ")).not.toContain(raw);
  });

  it("summarizes long browser writing into compact topics", () => {
    const longText = `
      오늘은 Browser Worklog 확장 프로그램의 Notion 업로드 결과를 검토했다.
      브라우저 작업일지에 너무 긴 원문이 그대로 들어가면 사용자가 읽기 어렵기 때문에
      요약 품질을 개선해야 한다고 판단했다.
      특히 ChatGPT에서 작성한 긴 프롬프트와 Notion에서 정리한 문서 내용은
      원문 전체보다 작업 주제 중심으로 기록되는 편이 좋다.
      그래서 작성 기록, Notion, 브라우저, 요약, 작업일지, 확장 프로그램,
      사이트별 작성 내용 같은 단어가 반복되는 상황을 테스트한다.
      이 문장은 일부러 길게 작성해서 원문 전체가 Notion payload에 그대로 복사되지 않고
      작성 주제 형태로 짧게 정리되는지 확인하기 위한 테스트 문장이다.
      Browser Worklog 확장 프로그램은 로컬에서 가볍게 동작해야 하므로
      AI API 없이도 작성 주제를 뽑아낼 수 있어야 한다.
    `;

    const summary = summarizeBrowserChunks([
      chunk({
        domain: "chatgpt.com",
        pageTitle: "[US] 의석 공부 - Browser Worklog 개선",
        text: longText
      })
    ]);

    expect(summary.bullets[0]).toBe(
      'ChatGPT에서 "의석 공부 - Browser Worklog 개선" 페이지에 질문/프롬프트를 작성했다.'
    );
    expect(summary.details[0]).toContain("ChatGPT / 의석 공부 - Browser Worklog 개선: 작성 주제:");
    expect(summary.details[0]).toContain("내용 일부:");
    expect(summary.details[0]).toContain("오늘은 Browser Worklog 확장 프로그램의 Notion 업로드 결과를 검토했다");
    expect(summary.details[0].length).toBeLessThan(850);
  });

  it("keeps up to fifteen page details", () => {
    const chunks = Array.from({ length: 18 }, (_, index) =>
      chunk({
        domain: "chatgpt.com",
        pageTitle: `작업 ${index}`,
        text: `브라우저 작업일지 상세 내용 ${index}`
      })
    );

    const summary = summarizeBrowserChunks(chunks);

    expect(summary.details).toHaveLength(15);
  });
});
