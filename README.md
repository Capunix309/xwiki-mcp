# MCP Tools

One stdio MCP server exposes the enabled XWiki and Jira integrations. Production code lives under `src/`; each integration has a `core/` directory for shared client/configuration logic and a `tools/` directory organized by responsibility. Tests live separately under `tests/`, one file per integration.

## Configure

Copy `config.example.toml` to `config.toml`. This central TOML file contains the shared host, integration enablement, API paths, credential environment-variable names, XWiki wiki definitions, and Jira project access rules. The active `config.toml` is ignored by Git. Set `enabled = false` on an integration to omit its tools at server startup.

Add one `[[integrations.jira.projects]]` table per project. Set a unique `id`, the Jira project `key`, and `read_only = true` or `false`. Jira tool calls select a configured project by id or key; searches and issue reads are scoped to it, and writes are rejected for read-only projects. Replace the example `YOUR_PROJECT_KEY` with a real project key.

Write tools are visible by default. Set `[tools].expose_write = false` in `config.toml` to hide them. Destructive tools are hidden by default; set `[tools].expose_destructive = true` to allow them, too. A destructive write tool is exposed only when both settings allow it. Restart the MCP server after changing these settings.

Copy `.env.example` to `.env` and set the credential values referenced by `config.toml`. The `.env` file is ignored by Git. Jira credentials are checked when Jira tools are called; XWiki credentials are validated at startup when XWiki is enabled.

The XWiki configuration retains the `team`, `global`, `openshift`, and `SPEAM` wikis. `team` is read-write; the other three are read-only.

## Install and connect to Codex

From the repository root, install the dependencies:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Add this server entry to Codex's `~/.codex/config.toml` or a trusted project's `.codex/config.toml`:

```toml
[mcp_servers.mcp-tools]
command = "/absolute/path/to/MCP-tools/.venv/bin/python"
args = ["-m", "src.server"]
cwd = "/absolute/path/to/MCP-tools"
default_tools_approval_mode = "writes"
```

The `writes` mode uses each tool's `readOnlyHint`: read tools run without a prompt, and write tools request approval. This covers both Jira and XWiki without per-tool approval entries. Restart Codex after changing its MCP configuration.

Codex launches the server automatically when it connects to this MCP configuration. You do not need to run the server command in a separate terminal. For a manual local run when debugging, use `python -m src.server` from the repository root.

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
