import type { ActivityChunk } from "./activityStore";

export interface BrowserSummary {
  bullets: string[];
  details: string[];
  mainDomains: string[];
  writtenChunks: number;
}

const STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "with",
  "from",
  "this",
  "that",
  "about",
  "있는",
  "없는",
  "하는",
  "해서",
  "그리고",
  "으로",
  "에서",
  "notion",
  "browser",
  "worklog",
  "작성했다",
  "관련",
  "내용"
]);

const SERVICE_NAMES: Record<string, string> = {
  "app.notion.com": "Notion",
  "notion.com": "Notion",
  "notion.so": "Notion",
  "chatgpt.com": "ChatGPT",
  "chat.openai.com": "ChatGPT",
  "claude.ai": "Claude",
  "gemini.google.com": "Gemini",
  "perplexity.ai": "Perplexity",
  "github.com": "GitHub",
  "gitlab.com": "GitLab",
  "atlassian.net": "Jira",
  "linear.app": "Linear",
  "confluence.com": "Confluence",
  "docs.google.com": "Google Docs"
};

export function summarizeBrowserChunks(chunks: ActivityChunk[]): BrowserSummary {
  if (chunks.length === 0) {
    return {
      bullets: ["브라우저에서 새로 작성한 내용이 없다."],
      details: [],
      mainDomains: [],
      writtenChunks: 0
    };
  }

  const groups = groupByDomainAndTitle(chunks);
  const keywords = extractKeywords(chunks);
  const mainDomains = topValues(chunks.map((chunk) => serviceName(chunk.domain)), 5);
  const bullets = [...groups.entries()]
    .slice(0, 10)
    .map(([key, groupChunks]) => buildBullet(key, groupChunks, keywords));
  const details = [...groups.entries()]
    .slice(0, 10)
    .map(([key, groupChunks]) => buildDetail(key, groupChunks));

  return {
    bullets,
    details,
    mainDomains,
    writtenChunks: chunks.length
  };
}

export function extractKeywords(chunks: ActivityChunk[], limit = 12): string[] {
  const counts = new Map<string, number>();

  for (const chunk of chunks) {
    const source = `${chunk.pageTitle}\n${chunk.text}`;
    for (const token of tokenize(source)) {
      counts.set(token, (counts.get(token) ?? 0) + 1);
    }
  }

  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit)
    .map(([token]) => token);
}

function groupByDomainAndTitle(chunks: ActivityChunk[]): Map<string, ActivityChunk[]> {
  const groups = new Map<string, ActivityChunk[]>();
  for (const chunk of chunks) {
    const key = `${chunk.domain}|${chunk.pageTitle || chunk.domain}`;
    groups.set(key, [...(groups.get(key) ?? []), chunk]);
  }
  return groups;
}

function buildBullet(key: string, chunks: ActivityChunk[], allKeywords: string[]): string {
  const [domain, title] = key.split("|", 2);
  const service = serviceName(domain);
  const cleanTitle = title && title !== domain ? sanitizeTitle(title) : "";
  const topic = pickTopic(cleanTitle, chunks, allKeywords);
  const action = actionForDomain(domain);

  return topic
    ? `${service}에서 ${topic} 관련 ${action}.`
    : `${service}에서 작업 내용을 작성했다.`;
}

function buildDetail(key: string, chunks: ActivityChunk[]): string {
  const [domain, title] = key.split("|", 2);
  const service = serviceName(domain);
  const cleanTitle = title && title !== domain ? sanitizeTitle(title) : "";
  const preview = summarizeWrittenText(chunks.map((chunk) => chunk.text).join(" "));

  if (cleanTitle && preview) {
    return `${service}의 "${cleanTitle}" 페이지에서 ${preview}`;
  }
  if (preview) {
    return `${service}에서 ${preview}`;
  }
  if (cleanTitle) {
    return `${service}의 "${cleanTitle}" 페이지에서 내용을 작성했다.`;
  }
  return `${service}에서 내용을 작성했다.`;
}

function tokenize(value: string): string[] {
  return value
    .replace(/[^\p{L}\p{N}_-]+/gu, " ")
    .split(/\s+/)
    .map((token) => token.trim().toLowerCase())
    .filter((token) => token.length >= 3)
    .filter((token) => !STOP_WORDS.has(token));
}

function topValues(values: string[], limit: number): string[] {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit)
    .map(([value]) => value);
}

function sanitizeTitle(title: string): string {
  return title
    .replace(/\s+/g, " ")
    .replace(/^\(?\d+\)?\s*[-_.:|]?\s*/, "")
    .replace(/\b(Notion|ChatGPT|Claude|Gemini)\b/gi, "")
    .replace(/[|·•]+/g, " ")
    .trim()
    .slice(0, 50);
}

function serviceName(domain: string): string {
  const normalized = domain.toLowerCase();
  if (SERVICE_NAMES[normalized]) {
    return SERVICE_NAMES[normalized];
  }

  const match = Object.entries(SERVICE_NAMES).find(([knownDomain]) =>
    normalized === knownDomain || normalized.endsWith(`.${knownDomain}`)
  );
  if (match) {
    return match[1];
  }

  return normalized.replace(/^www\./, "");
}

function pickTopic(
  cleanTitle: string,
  chunks: ActivityChunk[],
  allKeywords: string[]
): string {
  const titleTopic = topicFromTitle(cleanTitle);
  if (titleTopic) {
    return titleTopic;
  }

  const domainKeywords = extractKeywords(chunks, 3);
  const selectedKeywords = (domainKeywords.length ? domainKeywords : allKeywords)
    .filter((keyword) => !keyword.includes("."))
    .slice(0, 2);
  return selectedKeywords.join(", ");
}

function topicFromTitle(title: string): string {
  const withoutNoise = title
    .replace(/\bBrowser Worklog\b/gi, "")
    .replace(/\bUntitled\b/gi, "")
    .replace(/\s+/g, " ")
    .trim();

  if (!withoutNoise || withoutNoise.length < 2) {
    return "";
  }

  return withoutNoise;
}

function actionForDomain(domain: string): string {
  const service = serviceName(domain);
  if (service === "Notion" || service === "Google Docs" || service === "Confluence") {
    return "문서를 정리했다";
  }
  if (service === "ChatGPT" || service === "Claude" || service === "Gemini" || service === "Perplexity") {
    return "질문과 답변을 정리했다";
  }
  if (service === "GitHub" || service === "GitLab") {
    return "개발 작업을 기록했다";
  }
  if (service === "Jira" || service === "Linear") {
    return "업무 항목을 정리했다";
  }
  return "작업 내용을 작성했다";
}

function summarizeWrittenText(value: string): string {
  const cleaned = value
    .replace(/\s+/g, " ")
    .replace(/[{}[\]<>]/g, "")
    .trim();
  if (!cleaned) {
    return "";
  }

  const sentence = cleaned
    .split(/[.!?。！？\n]/)
    .map((part) => part.trim())
    .find((part) => part.length >= 6) ?? cleaned;
  const clipped = `${sentence.slice(0, 90)}${sentence.length > 90 ? "..." : ""}`;
  if (/[다요함음]$/.test(clipped)) {
    return `${clipped}.`;
  }
  if (/(정리|작성|수정|구현|검토|분석|준비|기록)$/.test(clipped)) {
    return `${clipped}했다.`;
  }
  return `${clipped} 내용을 작성했다.`;
}
