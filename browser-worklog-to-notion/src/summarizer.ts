import type { ActivityChunk } from "./activityStore";

export interface BrowserSummary {
  bullets: string[];
  details: string[];
  mainDomains: string[];
  writtenChunks: number;
}

const MAX_PAGE_DETAILS = 15;
const MAX_CONTENT_PREVIEW_CHARS = 700;

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
  "내용",
  "내용을"
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

  const pageGroups = groupByDomainAndTitle(chunks);
  const serviceGroups = groupByService(chunks);
  const mainDomains = topValues(chunks.map((chunk) => serviceName(chunk.domain)), 5);
  const bullets = [...serviceGroups.entries()]
    .slice(0, 10)
    .map(([service, groupChunks]) => buildServiceBullet(service, groupChunks));
  const details = [...pageGroups.entries()]
    .slice(0, MAX_PAGE_DETAILS)
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

function groupByService(chunks: ActivityChunk[]): Map<string, ActivityChunk[]> {
  const groups = new Map<string, ActivityChunk[]>();
  for (const chunk of chunks) {
    const service = serviceName(chunk.domain);
    groups.set(service, [...(groups.get(service) ?? []), chunk]);
  }
  return groups;
}

function buildServiceBullet(service: string, chunks: ActivityChunk[]): string {
  const pageTitles = uniqueCleanTitles(chunks);
  const target =
    pageTitles.length === 0
      ? `${chunks.length}개 작성 기록`
      : pageTitles.length === 1
        ? `"${pageTitles[0]}" 페이지`
        : `${pageTitles.length}개 페이지`;
  const action = actionForService(service);

  return `${service}에서 ${target}에 ${action}.`;
}

function buildDetail(key: string, chunks: ActivityChunk[]): string {
  const [domain, title] = key.split("|", 2);
  const service = serviceName(domain);
  const cleanTitle = title && title !== domain ? sanitizeTitle(title) : "";
  const preview = summarizeWrittenText(chunks.map((chunk) => chunk.text).join(" "));
  const location = cleanTitle ? `${service} / ${cleanTitle}` : service;

  if (cleanTitle && preview) {
    return `${location}: ${preview}`;
  }
  if (preview) {
    return `${location}: ${preview}`;
  }
  if (cleanTitle) {
    return `${location}: 내용을 작성했다.`;
  }
  return `${service}에서 내용을 작성했다.`;
}

function tokenize(value: string): string[] {
  return value
    .replace(/[^\p{L}\p{N}_-]+/gu, " ")
    .split(/\s+/)
    .map((token) => token.trim().toLowerCase())
    .filter((token) => token.length >= 3 || /[가-힣]{2,}/.test(token))
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
    .replace(/^\s*[-–—]?\s*\[[^\]]+\]\s*/, "")
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

function actionForService(service: string): string {
  if (service === "Notion" || service === "Google Docs" || service === "Confluence") {
    return "문서 내용을 작성했다";
  }
  if (service === "ChatGPT" || service === "Claude" || service === "Gemini" || service === "Perplexity") {
    return "질문/프롬프트를 작성했다";
  }
  if (service === "GitHub" || service === "GitLab") {
    return "개발 설정이나 설명을 작성했다";
  }
  if (service === "Jira" || service === "Linear") {
    return "업무 항목을 작성했다";
  }
  return "작업 내용을 작성했다";
}

function summarizeWrittenText(value: string): string {
  const cleaned = cleanWrittenText(value);
  if (!cleaned) {
    return "";
  }

  const keywords = keywordSummary(cleaned, 5);
  const preview = contentPreview(cleaned, MAX_CONTENT_PREVIEW_CHARS);
  if (keywords.length >= 2) {
    return `작성 주제: ${keywords.join(", ")} / 내용 일부: ${preview}`;
  }

  return `내용 일부: ${preview}`;
}

function uniqueCleanTitles(chunks: ActivityChunk[]): string[] {
  const seen = new Set<string>();
  const titles: string[] = [];
  for (const chunk of chunks) {
    const title = sanitizeTitle(chunk.pageTitle || "");
    if (!title || seen.has(title)) {
      continue;
    }
    seen.add(title);
    titles.push(title);
  }
  return titles;
}

function cleanWrittenText(value: string): string {
  return value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/!\[[^\]]*]\([^)]*\)/g, " ")
    .replace(/\[[^\]]+]\([^)]*\)/g, " ")
    .replace(/https?:\/\/\S+/g, " ")
    .replace(/[#>*_\-~]+/g, " ")
    .replace(/[{}[\]<>]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function keywordSummary(value: string, limit: number): string[] {
  const counts = new Map<string, number>();
  for (const token of tokenize(value)) {
    if (token.includes(".") || token.length < 2) {
      continue;
    }
    counts.set(token, (counts.get(token) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit)
    .map(([token]) => token);
}

function contentPreview(value: string, maxLength: number): string {
  const sentenceLike = value
    .split(/[.!?。！？\n]/)
    .map((part) => part.trim())
    .filter((part) => part.length >= 6)
    .join(". ");
  const preview = sentenceLike || value;
  if (preview.length <= maxLength) {
    return preview;
  }
  return `${preview.slice(0, maxLength - 3).trim()}...`;
}
