# MCP Tools

One stdio MCP server exposes the enabled XWiki and Jira integrations. Production code lives under `src/`; each integration has a `core/` directory for shared client/configuration logic and a `tools/` directory organized by responsibility. Tests live separately under `tests/`, one file per integration.

## 1. Configure the integrations

These settings belong to the **MCP-tools checkout**, not to the project that will use the MCP. From the `MCP-tools/` folder, copy the example files:

```sh
cp config.example.toml config.toml
cp .env.example .env
```

`config.toml` is ignored by Git. It contains the server host, enabled integrations, wiki and project access, and the names of environment variables used for credentials. `.env` contains the corresponding secret values and is also ignored by Git. Never put credentials in a project's Codex or Claude MCP registration file.

### Add or configure XWiki wikis

Each `[[integrations.xwiki.wikis]]` entry represents one wiki. Keep `id` as a short, unique selector the model will pass to tools. Set `wiki` to the XWiki wiki identifier: it is the segment after `/xwiki/wiki/` in a wiki URL (for example, `speam` in `/xwiki/wiki/speam/view/...`). Set `read_only = true` unless that wiki is explicitly approved for writing. `default_wiki` must match one of the configured `id` values.

Add another wiki by copying this block into `config.toml` and replacing its values:

```toml
[[integrations.xwiki.wikis]]
id = "research"
wiki = "wiki-id-from-url"
read_only = true
```

Replace `wiki-id-from-url` with the segment after `/xwiki/wiki/` in that wiki's URL.

The supplied example already defines `team`, `global`, `openshift`, and `SPEAM`; `team` is writable and the other three are read-only. To disable the entire XWiki integration, set `enabled = false` under `[integrations.xwiki]`.

### Add or configure Jira projects

Add one `[[integrations.jira.projects]]` block per project. `id` is a unique selector for tool calls. `key` is the Jira project key, usually the prefix of an issue key (`ABC` in `ABC-123`); you can also find it in the Jira project URL or project details. Set `read_only = true` to prevent all Jira changes in that project.

```toml
[[integrations.jira.projects]]
id = "team"
key = "ABC"
read_only = true
```

Replace the example `YOUR_PROJECT_KEY` in the supplied template with the real key. Add more blocks for other projects. Searches can cover all configured projects or select one by `id` or key. To disable Jira entirely, set `enabled = false` under `[integrations.jira]`.

### Credentials and tool visibility

The `username_env` and `password_env` settings in `config.toml` name the variables to set in `.env`. The example file shows the expected variable names; replace its placeholder values with your credentials. Jira checks credentials when a Jira tool is called. XWiki checks them when the server starts.

Write tools are visible by default. Set `[tools].expose_write = false` to hide them. Destructive tools are hidden by default; set `[tools].expose_destructive = true` to expose them. A destructive write tool appears only when both settings allow it. Restart the MCP client after changing the server configuration.

## 2. Install the MCP in a project

Install the MCP server once, then register it only in each project where you want it available. The project gets a small client configuration file; the MCP's own `config.toml` and `.env` remain in the separate `MCP-tools/` checkout.

From the MCP-tools repository root, install its dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

In each project root, add the relevant client file:

```text
my-project/
├── .codex/
│   └── config.toml   # Codex project registration
└── .mcp.json         # Claude Code project registration (if used)
```

Replace `/absolute/path/to/MCP-tools` below with the full path to the MCP-tools checkout on your machine.

### Codex

Create `my-project/.codex/config.toml`:

```toml
[mcp_servers.mcp-tools]
command = "/absolute/path/to/MCP-tools/.venv/bin/python"
args = ["-m", "src.server"]
cwd = "/absolute/path/to/MCP-tools"
default_tools_approval_mode = "writes"
```

Codex loads project `.codex/config.toml` for trusted projects. Trust the project when prompted. The `writes` approval mode uses each tool's `readOnlyHint`: reads run without a prompt and writes request approval. Codex starts the server automatically; no separate server terminal is needed. See the [Codex MCP configuration guide](https://learn.chatgpt.com/docs/extend/mcp).

### Claude Code

Create `my-project/.mcp.json` (replace both occurrences of the path with your MCP-tools checkout):

```json
{
  "mcpServers": {
    "mcp-tools": {
      "command": "/absolute/path/to/MCP-tools/.venv/bin/python",
      "args": ["-m", "src.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/MCP-tools"
      }
    }
  }
}
```

Claude Code starts project `.mcp.json` servers from the project directory; `PYTHONPATH` points Python to the MCP-tools checkout. Open the project in Claude Code and approve the project-scoped server when prompted. Run `/mcp` or `claude mcp list` to check its connection. See the [Claude Code MCP guide](https://docs.anthropic.com/en/docs/claude-code/mcp).

To run the server manually for debugging only, open a terminal in the MCP-tools repository and run `python -m src.server`.

## Jira tools

- `jira_search` (read) searches configured projects by text, issue type, status, assignee, sprint, or update date. Omit `project` to search all configured projects.
- `jira_get_issue` (read) returns issue details, optionally including comments, worklogs, change history, or an epic's child issues.
- `jira_list_boards` (read) lists boards associated with a configured project.
- `jira_list_sprints` (read) lists sprints for a project board, optionally filtered by active, future, or closed state.
- `jira_search_users` (read) finds users assignable to a project by name or email.
- `jira_get_issue_types` (read) lists the issue types available in a project.
- `jira_get_priorities` (read) lists Jira priorities for a configured project.
- `jira_create_issue` (write) creates an issue with a required description prefixed by `[AI]` and adds the `ai-assisted` label.
- `jira_update_issue` (write) updates an issue's summary, description, assignee, priority, and/or labels.
- `jira_add_comment` (write) adds an issue comment prefixed with `[AI]`.
- `jira_add_worklog` (write) records time spent with a required comment prefixed with `[AI]`.
- `jira_transition_issue` (write) moves an issue through one of its currently available workflow transitions.
- `jira_add_issue_to_sprint` (write) adds an issue to a sprint on a board belonging to the configured project.

Every Jira tool is scoped to projects in `config.toml`; read-only projects reject writes. Write tools are annotated as writes so Codex can request approval according to the MCP server approval mode. The Jira MCP does not expose arbitrary HTTP requests or issue deletion.

## XWiki tools

- `read_page` (read) returns a page's content and metadata.
- `read_page_section` (read) returns the content under a matching heading.
- `create_page` (write) creates a page with the supplied content, optional title, and syntax.
- `edit_page` (write) replaces a page's content and can update its title or syntax.
- `append_section` (write) adds a level-two section to an existing page.
- `edit_page_section` (write) replaces one section's body while preserving its heading and sibling sections.
- `move_page` (destructive write) renames or moves a page while preserving version history; it updates links by default and can optionally change the visible title.
- `list_spaces` (read) lists the spaces available in the selected wiki.
- `page_tree` (read) lists pages with creator, last editor, modification date, and version; it can filter by space or author.
- `search_pages` (read) searches page names, titles, content, or objects, with optional space filtering and pagination.
- `get_page_links` (read) lists XWiki syntax links found on a page.
- `find_orphan_pages` (read) finds scanned pages with no incoming XWiki syntax links.
- `list_attachments` (read) lists attachment metadata for a page.
- `read_attachment` (read) returns a text attachment as text or a binary attachment as base64, within the configured size limit.
- `add_comment` (write) posts a comment on a page.
- `list_comments` (read) lists comments attached to a page.
- `add_tags` (write) adds one or more tags to a page.
- `page_history` (read) lists recent versions of a page, including authors and dates when available.
- `diff_page_versions` (read) compares the text content of two page versions.
- `recent_changes` (read) lists pages modified within a selected number of days.
- `who_wrote_pages` (read) lists page creators, last editors, and modification dates, with optional space or author filters.
- `consistency_check` (read) checks scanned pages for required headings and unresolved internal links.
- `create_page_from_template` (write) creates a meeting, decision, task, or report page from supplied fields.
- `decision_log` (read) finds likely decision statements and reports their source pages and matching lines.
- `project_status` (read) collects checkbox tasks and nearby owner labels from pages in a space.
- `wiki_digest` (read) lists recently changed pages with titles, authors, and modification dates.

Every XWiki tool accepts the `wiki` selector. It defaults to `team`; page names use `space` and `page`, with nested spaces separated by `/`.

The Jira integration follows the teacher's SPEAM pages “AI & API capabilities on Jira and XWiki” and “Project Backlog Management,” including human review for writes, the `ai-assisted` label, and a visible AI comment prefix.
