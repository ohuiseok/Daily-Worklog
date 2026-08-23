import type { ActivityChunk } from "./activityStore";
import { getChunksSince, markChunksUploaded } from "./activityStore";
import { buildBrowserNotionPayload } from "./notionPayload";
import { REQUIRED_NOTION_PROPERTIES, type RequiredNotionProperty } from "./notionSchema";
import { loadSettings, loadUploadState, saveUploadState } from "./settingsStore";
import { summarizeBrowserChunks } from "./summarizer";

const NOTION_API_BASE = "https://api.notion.com/v1";
const NOTION_VERSION = "2026-03-11";

export interface UploadResult {
  uploaded: boolean;
  created: boolean;
  pageId: string | null;
  chunkCount: number;
  reason?: string;
}

export interface EnsureSchemaResult {
  ok: boolean;
  targetId: string;
  targetType: "database" | "data_source";
  dataSourceId: string;
  titlePropertyName: string;
  added: string[];
  existing: string[];
  incompatible: string[];
}

export interface AccessibleNotionTarget {
  id: string;
  object: string;
  title: string;
  url: string | null;
}

export async function uploadPendingBrowserWorklog(
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
): Promise<UploadResult> {
  const settings = await loadSettings();
  if (!settings.notionToken || !settings.databaseId) {
    return {
      uploaded: false,
      created: false,
      pageId: null,
      chunkCount: 0,
      reason: "missing_notion_settings"
    };
  }

  const uploadState = await loadUploadState();
  const since = uploadState.lastSuccessAt ?? "1970-01-01T00:00:00.000Z";
  const chunks = await getChunksSince(since);
  if (chunks.length === 0) {
    return {
      uploaded: false,
      created: false,
      pageId: null,
      chunkCount: 0,
      reason: "no_pending_chunks"
    };
  }

  const summary = summarizeBrowserChunks(chunks);
  const worklogDate = latestChunkDate(chunks);
  const payload = buildBrowserNotionPayload({
    databaseId: settings.databaseId,
    projectName: "Browser Worklog",
    worklogDate,
    source: "Browser",
    summary
  });

  const client = new BrowserNotionClient(settings.notionToken, fetchImpl);
  const result = await client.upsert(payload, {
    databaseId: settings.databaseId,
    worklogDate,
    source: "Browser",
    projectName: "Browser Worklog"
  });

  await markChunksUploaded(chunks.map((chunk) => chunk.id));
  await saveUploadState({ lastSuccessAt: new Date().toISOString() });

  return {
    uploaded: true,
    created: result.created,
    pageId: result.pageId,
    chunkCount: chunks.length
  };
}

export class BrowserNotionClient {
  constructor(
    private readonly token: string,
    private readonly fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
  ) {}

  async upsert(
    payload: Record<string, unknown>,
    key: {
      databaseId: string;
      worklogDate: string;
      source: string;
      projectName: string;
    }
  ): Promise<{ pageId: string; created: boolean }> {
    const target = await this.ensureDatabaseSchema(key.databaseId);
    const dataSourceId = target.dataSourceId;
    const resolvedPayload = withResolvedTitleProperty(payload, target.titlePropertyName);
    const existingPage = await this.findExistingPage({
      ...key,
      dataSourceId
    });
    if (!existingPage) {
      const created = await this.request("POST", "/pages", {
        ...resolvedPayload,
        parent: {
          type: "data_source_id",
          data_source_id: dataSourceId
        }
      });
      return { pageId: String(created.id), created: true };
    }

    await this.request("PATCH", `/pages/${existingPage.id}`, {
      properties: (resolvedPayload as { properties: unknown }).properties
    });
    await this.appendBlocks(String(existingPage.id), (resolvedPayload as { children: Record<string, unknown>[] }).children);
    return { pageId: String(existingPage.id), created: false };
  }

  async ensureDatabaseSchema(databaseId: string): Promise<EnsureSchemaResult> {
    const target = await this.resolveDataSourceTarget(databaseId);
    const properties = isRecord(target.dataSource.properties)
      ? target.dataSource.properties
      : {};
    const titlePropertyName = findTitlePropertyName(properties) ?? "Name";
    const missing: Record<string, unknown> = {};
    const added: string[] = [];
    const existing: string[] = [];
    const incompatible: string[] = [];

    for (const [name, required] of Object.entries(REQUIRED_NOTION_PROPERTIES)) {
      const current = properties[name];
      if (name === "Name" && !isRecord(current) && titlePropertyName !== "Name") {
        existing.push(titlePropertyName);
        continue;
      }

      if (!isRecord(current)) {
        missing[name] = required.schema;
        added.push(name);
        continue;
      }

      if (current.type !== required.type) {
        incompatible.push(`${name}: expected ${required.type}, got ${String(current.type)}`);
        continue;
      }

      existing.push(name);
      const optionPatch = buildOptionPatch(current, required);
      if (optionPatch) {
        missing[name] = optionPatch;
        added.push(`${name} options`);
      }
    }

    if (incompatible.length) {
      throw new Error(`Notion database schema has incompatible properties: ${incompatible.join(", ")}`);
    }

    if (Object.keys(missing).length) {
      await this.request("PATCH", `/data_sources/${target.dataSourceId}`, {
        properties: missing
      });
    }

    return {
      ok: true,
      targetId: target.inputId,
      targetType: target.inputType,
      dataSourceId: target.dataSourceId,
      titlePropertyName,
      added,
      existing,
      incompatible
    };
  }

  async searchAccessibleTargets(query = ""): Promise<AccessibleNotionTarget[]> {
    const response = await this.request("POST", "/search", {
      query,
      page_size: 20,
      filter: {
        property: "object",
        value: "data_source"
      },
      sort: {
        direction: "descending",
        timestamp: "last_edited_time"
      }
    });
    const results = Array.isArray(response.results) ? response.results : [];
    return results.filter(isRecord).map((item) => ({
      id: typeof item.id === "string" ? item.id : "",
      object: typeof item.object === "string" ? item.object : "unknown",
      title: titleFromSearchResult(item),
      url: typeof item.url === "string" ? item.url : null
    }));
  }

  async resolveDataSourceTarget(
    id: string
  ): Promise<{
    inputId: string;
    inputType: "database" | "data_source";
    dataSourceId: string;
    dataSource: Record<string, unknown>;
  }> {
    let dataSourceLookupError: string | null = null;
    const dataSource = await this.requestOrNull("GET", `/data_sources/${id}`, undefined, (error) => {
      dataSourceLookupError = error.message;
    });
    if (dataSource) {
      return {
        inputId: id,
        inputType: "data_source",
        dataSourceId: id,
        dataSource
      };
    }

    let database: Record<string, unknown>;
    try {
      database = await this.request("GET", `/databases/${id}`);
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("Notion API failed: 404")) {
        throw new Error(
          [
            "Could not access the Notion database/data source.",
            "Check that the copied ID is correct and that the database is shared with this integration.",
            dataSourceLookupError ? `Data source lookup: ${dataSourceLookupError}` : null,
            `Database lookup: ${error.message}`
          ]
            .filter(Boolean)
            .join(" ")
        );
      }
      throw error;
    }
    const dataSources = Array.isArray(database.data_sources)
      ? database.data_sources
      : [];
    const firstDataSource = dataSources.find(
      (item): item is Record<string, unknown> =>
        isRecord(item) && typeof item.id === "string"
    );
    if (!firstDataSource) {
      throw new Error("Notion database has no data sources.");
    }

    const dataSourceId = String(firstDataSource.id);
    return {
      inputId: id,
      inputType: "database",
      dataSourceId,
      dataSource: await this.request("GET", `/data_sources/${dataSourceId}`)
    };
  }

  async findExistingPage(key: {
    dataSourceId: string;
    worklogDate: string;
    source: string;
    projectName: string;
  }): Promise<{ id: string } | null> {
    const response = await this.request("POST", `/data_sources/${key.dataSourceId}/query`, {
      filter: {
        and: [
          { property: "Date", date: { equals: key.worklogDate } },
          { property: "Source", select: { equals: key.source } },
          { property: "Project", rich_text: { equals: key.projectName } }
        ]
      },
      page_size: 1
    });
    const results = Array.isArray(response.results) ? response.results : [];
    return results.length ? (results[0] as { id: string }) : null;
  }

  async appendBlocks(pageId: string, blocks: Record<string, unknown>[]): Promise<void> {
    for (const chunk of chunkBlocks(blocks, 100)) {
      await this.request("PATCH", `/blocks/${pageId}/children`, {
        children: chunk
      });
    }
  }

  private async request(
    method: string,
    path: string,
    body?: Record<string, unknown>
  ): Promise<Record<string, unknown>> {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const response = await this.fetchImpl(`${NOTION_API_BASE}${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${this.token}`,
          "Content-Type": "application/json",
          "Notion-Version": NOTION_VERSION
        },
        body: body ? JSON.stringify(body) : undefined
      });

      if (response.status === 429 && attempt < 2) {
        const retryAfter = Number(response.headers.get("Retry-After") ?? "1");
        await sleep(Number.isFinite(retryAfter) ? retryAfter * 1000 : 1000);
        continue;
      }

      if (!response.ok) {
        throw new Error(`Notion API failed: ${response.status} ${await response.text()}`);
      }

      return (await response.json()) as Record<string, unknown>;
    }

    throw new Error("Notion API failed after retries.");
  }

  private async requestOrNull(
    method: string,
    path: string,
    body?: Record<string, unknown>,
    onNotFound?: (error: Error) => void
  ): Promise<Record<string, unknown> | null> {
    try {
      return await this.request(method, path, body);
    } catch (error) {
      if (error instanceof Error && error.message.startsWith("Notion API failed: 404")) {
        onNotFound?.(error);
        return null;
      }
      throw error;
    }
  }
}

export async function ensureConfiguredNotionSchema(
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
): Promise<EnsureSchemaResult> {
  const settings = await loadSettings();
  if (!settings.notionToken || !settings.databaseId) {
    throw new Error("Notion token and database ID are required.");
  }

  const client = new BrowserNotionClient(settings.notionToken, fetchImpl);
  return client.ensureDatabaseSchema(settings.databaseId);
}

export async function searchConfiguredNotionTargets(
  fetchImpl: typeof fetch = globalThis.fetch.bind(globalThis)
): Promise<AccessibleNotionTarget[]> {
  const settings = await loadSettings();
  if (!settings.notionToken) {
    throw new Error("Notion token is required.");
  }

  const client = new BrowserNotionClient(settings.notionToken, fetchImpl);
  return client.searchAccessibleTargets("Daily Worklog");
}

function buildOptionPatch(
  current: Record<string, unknown>,
  required: RequiredNotionProperty
): Record<string, unknown> | null {
  if (required.type !== "select" && required.type !== "multi_select") {
    return null;
  }

  const requiredConfig = required.schema[required.type];
  const currentConfig = current[required.type];
  if (!isRecord(requiredConfig) || !isRecord(currentConfig)) {
    return null;
  }

  const requiredOptions = Array.isArray(requiredConfig.options) ? requiredConfig.options : [];
  const currentOptions = Array.isArray(currentConfig.options) ? currentConfig.options : [];
  const currentNames = new Set(
    currentOptions
      .filter(isRecord)
      .map((option) => option.name)
      .filter((name): name is string => typeof name === "string")
  );
  const missingOptions = requiredOptions.filter(
    (option): option is Record<string, unknown> =>
      isRecord(option) && typeof option.name === "string" && !currentNames.has(option.name)
  );

  if (!missingOptions.length) {
    return null;
  }

  return {
    [required.type]: {
      options: [...currentOptions, ...missingOptions]
    }
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function findTitlePropertyName(properties: Record<string, unknown>): string | null {
  for (const [name, property] of Object.entries(properties)) {
    if (isRecord(property) && property.type === "title") {
      return name;
    }
  }
  return null;
}

function withResolvedTitleProperty(
  payload: Record<string, unknown>,
  titlePropertyName: string
): Record<string, unknown> {
  if (titlePropertyName === "Name") {
    return payload;
  }

  const properties = isRecord(payload.properties) ? { ...payload.properties } : {};
  if (!("Name" in properties)) {
    return payload;
  }

  properties[titlePropertyName] = properties.Name;
  delete properties.Name;

  return {
    ...payload,
    properties
  };
}

function titleFromSearchResult(item: Record<string, unknown>): string {
  const title = item.title;
  if (Array.isArray(title)) {
    return title
      .filter(isRecord)
      .map((part) => part.plain_text)
      .filter((text): text is string => typeof text === "string")
      .join("")
      .trim() || "(untitled)";
  }
  return "(untitled)";
}

function latestChunkDate(chunks: ActivityChunk[]): string {
  return chunks
    .map((chunk) => chunk.createdAt.slice(0, 10))
    .sort()
    .at(-1)!;
}

function chunkBlocks<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let index = 0; index < items.length; index += size) {
    chunks.push(items.slice(index, index + size));
  }
  return chunks;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}
