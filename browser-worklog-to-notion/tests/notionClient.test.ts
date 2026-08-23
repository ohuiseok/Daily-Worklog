import { describe, expect, it } from "vitest";

import { BrowserNotionClient } from "../src/notionClient";

function response(status: number, payload: unknown, headers = new Headers()): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: new Headers({ "Content-Type": "application/json", ...Object.fromEntries(headers) })
  });
}

describe("BrowserNotionClient", () => {
  it("creates a page when no existing page is found", async () => {
    const calls: string[] = [];
    const fetchImpl = async (url: string | URL | Request, init?: RequestInit): Promise<Response> => {
      calls.push(`${init?.method} ${String(url)}`);
      if (calls.length === 1) {
        return response(200, { properties: completeSchemaProperties() });
      }
      return calls.length === 2
        ? response(200, { results: [] })
        : response(200, { id: "page_1" });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const result = await client.upsert(
      { parent: {}, properties: {}, children: [] },
      {
        databaseId: "db",
        worklogDate: "2026-08-23",
        source: "Browser",
        projectName: "Browser Worklog"
      }
    );

    expect(result).toEqual({ pageId: "page_1", created: true });
    expect(calls[0]).toContain("/data_sources/db");
    expect(calls[1]).toContain("/data_sources/db/query");
    expect(calls[2]).toContain("/pages");
  });

  it("updates an existing page and appends blocks", async () => {
    const methods: string[] = [];
    const fetchImpl = async (_url: string | URL | Request, init?: RequestInit): Promise<Response> => {
      methods.push(String(init?.method));
      if (methods.length === 1) {
        return response(200, { properties: completeSchemaProperties() });
      }
      if (methods.length === 2) {
        return response(200, { results: [{ id: "page_1" }] });
      }
      return response(200, { id: "page_1" });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const result = await client.upsert(
      { parent: {}, properties: {}, children: [{ type: "paragraph" }] },
      {
        databaseId: "db",
        worklogDate: "2026-08-23",
        source: "Browser",
        projectName: "Browser Worklog"
      }
    );

    expect(result).toEqual({ pageId: "page_1", created: false });
    expect(methods).toEqual(["GET", "POST", "PATCH", "PATCH"]);
  });

  it("resolves a database ID to its first data source", async () => {
    const calls: string[] = [];
    const fetchImpl = async (url: string | URL | Request): Promise<Response> => {
      calls.push(String(url));
      if (calls.length === 1) {
        return response(404, { object: "error", status: 404 });
      }
      if (calls.length === 2) {
        return response(200, { data_sources: [{ id: "data_source_1", name: "Table" }] });
      }
      return response(200, { properties: completeSchemaProperties() });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const target = await client.resolveDataSourceTarget("database_1");

    expect(target.inputType).toBe("database");
    expect(target.dataSourceId).toBe("data_source_1");
    expect(calls[0]).toContain("/data_sources/database_1");
    expect(calls[1]).toContain("/databases/database_1");
    expect(calls[2]).toContain("/data_sources/data_source_1");
  });

  it("adds missing database properties", async () => {
    const bodies: unknown[] = [];
    const fetchImpl = async (_url: string | URL | Request, init?: RequestInit): Promise<Response> => {
      bodies.push(init?.body ? JSON.parse(String(init.body)) : null);
      return bodies.length === 1
        ? response(200, { properties: { Name: { type: "title", title: {} } } })
        : response(200, { properties: completeSchemaProperties() });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const result = await client.ensureDatabaseSchema("db");

    expect(result.targetType).toBe("data_source");
    expect(result.dataSourceId).toBe("db");
    expect(result.titlePropertyName).toBe("Name");
    expect(result.added).toContain("Date");
    expect(JSON.stringify(bodies[1])).toContain("Written Chunks");
  });

  it("uses an existing localized title property instead of creating Name", async () => {
    const bodies: unknown[] = [];
    const fetchImpl = async (_url: string | URL | Request, init?: RequestInit): Promise<Response> => {
      bodies.push(init?.body ? JSON.parse(String(init.body)) : null);
      if (bodies.length === 1) {
        return response(200, {
          properties: {
            "이름": { type: "title", title: {} },
            Date: { type: "date", date: {} },
            Source: {
              type: "select",
              select: { options: [{ name: "Browser" }, { name: "Desktop" }] }
            },
            Project: { type: "rich_text", rich_text: {} },
            Status: {
              type: "select",
              select: { options: [{ name: "Success" }, { name: "Failed" }, { name: "Skipped" }] }
            },
            Summary: { type: "rich_text", rich_text: {} },
            "Written Chunks": { type: "number", number: { format: "number" } },
            "Main Domains": { type: "multi_select", multi_select: { options: [] } },
            "Commit Count": { type: "number", number: { format: "number" } },
            "Modified Files": { type: "number", number: { format: "number" } }
          }
        });
      }
      if (bodies.length === 2) {
        return response(200, { results: [] });
      }
      return response(200, { id: "page_1" });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const result = await client.upsert(
      {
        parent: {},
        properties: { Name: { title: [{ text: { content: "title" } }] } },
        children: []
      },
      {
        databaseId: "db",
        worklogDate: "2026-08-23",
        source: "Browser",
        projectName: "Browser Worklog"
      }
    );

    expect(result).toEqual({ pageId: "page_1", created: true });
    expect(JSON.stringify(bodies[2])).toContain("이름");
    expect(JSON.stringify(bodies[2])).not.toContain("\"Name\"");
  });

  it("rejects incompatible database properties", async () => {
    const fetchImpl = async (): Promise<Response> =>
      response(200, { properties: { Date: { type: "rich_text", rich_text: {} } } });
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    await expect(client.ensureDatabaseSchema("db")).rejects.toThrow("incompatible properties");
  });

  it("searches accessible data sources", async () => {
    const fetchImpl = async (_url: string | URL | Request, init?: RequestInit): Promise<Response> => {
      expect(String(init?.body)).toContain("data_source");
      return response(200, {
        results: [
          {
            id: "data_source_1",
            object: "data_source",
            title: [{ plain_text: "Daily Worklog" }],
            url: "https://notion.so/source"
          }
        ]
      });
    };
    const client = new BrowserNotionClient("ntn_test", fetchImpl);

    const result = await client.searchAccessibleTargets("Daily Worklog");

    expect(result).toEqual([
      {
        id: "data_source_1",
        object: "data_source",
        title: "Daily Worklog",
        url: "https://notion.so/source"
      }
    ]);
  });
});

function completeSchemaProperties(): Record<string, unknown> {
  return {
    Name: { type: "title", title: {} },
    Date: { type: "date", date: {} },
    Source: {
      type: "select",
      select: { options: [{ name: "Browser" }, { name: "Desktop" }] }
    },
    Project: { type: "rich_text", rich_text: {} },
    Status: {
      type: "select",
      select: { options: [{ name: "Success" }, { name: "Failed" }, { name: "Skipped" }] }
    },
    Summary: { type: "rich_text", rich_text: {} },
    "Written Chunks": { type: "number", number: { format: "number" } },
    "Main Domains": { type: "multi_select", multi_select: { options: [] } },
    "Commit Count": { type: "number", number: { format: "number" } },
    "Modified Files": { type: "number", number: { format: "number" } }
  };
}
