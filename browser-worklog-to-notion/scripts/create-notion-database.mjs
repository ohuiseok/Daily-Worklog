import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const NOTION_API_BASE = "https://api.notion.com/v1";
const NOTION_VERSION = "2022-06-28";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const schemaPath = resolve(scriptDir, "../../notion-schema/worklog-database.2022-06-28.json");

const args = parseArgs(process.argv.slice(2));

if (args.help) {
  printHelp();
  process.exit(0);
}

if (args["print-schema"]) {
  console.log(await readFile(schemaPath, "utf8"));
  process.exit(0);
}

const token = args.token ?? process.env.NOTION_TOKEN;
const parentPageId = args["parent-page-id"] ?? process.env.NOTION_PARENT_PAGE_ID;
const databaseTitle = args.title ?? process.env.NOTION_DATABASE_TITLE ?? "Worklog";

if (!token || !parentPageId) {
  printHelp();
  console.error("\nMissing NOTION_TOKEN or NOTION_PARENT_PAGE_ID.");
  process.exit(1);
}

const schema = JSON.parse(await readFile(schemaPath, "utf8"));
const payload = {
  parent: {
    type: "page_id",
    page_id: parentPageId
  },
  title: [
    {
      type: "text",
      text: {
        content: databaseTitle
      }
    }
  ],
  is_inline: Boolean(schema.is_inline),
  properties: schema.properties
};

const response = await fetch(`${NOTION_API_BASE}/databases`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
  },
  body: JSON.stringify(payload)
});

const bodyText = await response.text();
if (!response.ok) {
  console.error(`Notion database creation failed: ${response.status}`);
  console.error(bodyText);
  process.exit(1);
}

const body = JSON.parse(bodyText);
console.log("Created Notion worklog database.");
console.log(`Database ID: ${body.id}`);
if (body.url) {
  console.log(`URL: ${body.url}`);
}

function parseArgs(values) {
  const parsed = {};
  for (const value of values) {
    if (value === "--help" || value === "-h") {
      parsed.help = true;
      continue;
    }
    if (value === "--print-schema") {
      parsed["print-schema"] = true;
      continue;
    }
    const match = value.match(/^--([^=]+)=(.*)$/);
    if (match) {
      parsed[match[1]] = match[2];
    }
  }
  return parsed;
}

function printHelp() {
  console.log(`
Create the Notion database used by browser-worklog-to-notion and desktop-worklog-to-notion.

Usage:
  $env:NOTION_TOKEN="ntn_xxx"
  $env:NOTION_PARENT_PAGE_ID="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  npm run setup:notion-db

Options:
  --parent-page-id=<id>    Parent Notion page ID
  --title=<name>           Database title, defaults to Worklog
  --print-schema           Print the schema JSON without calling Notion
  --help                   Show this help
`);
}
