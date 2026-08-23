export type NotionPropertyType =
  | "title"
  | "date"
  | "select"
  | "rich_text"
  | "number"
  | "multi_select";

export interface RequiredNotionProperty {
  type: NotionPropertyType;
  schema: Record<string, unknown>;
}

export const REQUIRED_NOTION_PROPERTIES: Record<string, RequiredNotionProperty> = {
  Name: { type: "title", schema: { title: {} } },
  Date: { type: "date", schema: { date: {} } },
  Source: {
    type: "select",
    schema: {
      select: {
        options: [
          { name: "Browser", color: "blue" },
          { name: "Desktop", color: "green" }
        ]
      }
    }
  },
  Project: { type: "rich_text", schema: { rich_text: {} } },
  Status: {
    type: "select",
    schema: {
      select: {
        options: [
          { name: "Success", color: "green" },
          { name: "Failed", color: "red" },
          { name: "Skipped", color: "gray" }
        ]
      }
    }
  },
  Summary: { type: "rich_text", schema: { rich_text: {} } },
  "Written Chunks": {
    type: "number",
    schema: { number: { format: "number" } }
  },
  "Main Domains": {
    type: "multi_select",
    schema: { multi_select: { options: [] } }
  },
  "Commit Count": {
    type: "number",
    schema: { number: { format: "number" } }
  },
  "Modified Files": {
    type: "number",
    schema: { number: { format: "number" } }
  }
};
