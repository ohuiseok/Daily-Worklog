import type { BrowserSummary } from "./summarizer";

export interface BrowserPayloadInput {
  databaseId: string;
  projectName: string;
  worklogDate: string;
  source: "Browser";
  summary: BrowserSummary;
}

export function buildBrowserNotionPayload(input: BrowserPayloadInput): Record<string, unknown> {
  const title = `${input.worklogDate} ${input.projectName}`;

  return {
    parent: { database_id: input.databaseId },
    properties: {
      Name: { title: [text(title)] },
      Date: { date: { start: input.worklogDate } },
      Source: { select: { name: input.source } },
      Project: { rich_text: [text(input.projectName)] },
      Status: { select: { name: "Success" } },
      Summary: { rich_text: [text(input.summary.bullets.slice(0, 2).join(" "))] },
      "Written Chunks": { number: input.summary.writtenChunks },
      "Main Domains": {
        multi_select: input.summary.mainDomains.map((domain) => ({ name: domain }))
      }
    },
    children: buildBrowserBlocks(input.summary)
  };
}

export function buildBrowserBlocks(summary: BrowserSummary): Record<string, unknown>[] {
  return [
    heading("오늘 브라우저 작업"),
    ...summary.bullets.map((bullet) => bulletedItem(bullet)),
    heading("사이트별 작성 내용"),
    ...summary.details.map((detail) => bulletedItem(detail)),
    heading("근거 지표"),
    bulletedItem(`작성 기록: ${summary.writtenChunks}개`),
    bulletedItem(
      `주요 사이트: ${summary.mainDomains.length ? summary.mainDomains.join(", ") : "없음"}`
    )
  ];
}

export function assertPayloadExcludesRawText(
  payload: Record<string, unknown>,
  rawTexts: string[]
): void {
  const rendered = JSON.stringify(payload);
  for (const rawText of rawTexts) {
    if (rawText && rendered.includes(rawText)) {
      throw new Error("Browser Notion payload includes raw text.");
    }
  }
}

function heading(content: string): Record<string, unknown> {
  return {
    object: "block",
    type: "heading_2",
    heading_2: { rich_text: [text(content)] }
  };
}

function bulletedItem(content: string): Record<string, unknown> {
  return {
    object: "block",
    type: "bulleted_list_item",
    bulleted_list_item: { rich_text: [text(content)] }
  };
}

function text(content: string): Record<string, unknown> {
  return {
    type: "text",
    text: { content: content.slice(0, 2_000) }
  };
}
