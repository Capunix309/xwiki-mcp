# XWiki MCP

## Configure

Copy `.env.example` to `.env` and add credential values only. The variable names must match the `username_env` and `password_env` fields in `wikis.toml`.

```dotenv
XWIKI_TEAM_USERNAME=your-username
XWIKI_TEAM_PASSWORD=your-password
```

Add and configure wikis in `wikis.toml`. Each `[[wikis]]` entry has an `id`, `base_url`, XWiki `wiki` name, and `read_only` setting. Credential fields point to secret variable names in `.env`; omit them for anonymous access. Set `default_wiki` to the id used when a tool call does not specify `wiki`.

For another wiki, add an entry like this and add its credential variables to `.env`:

```toml
[[wikis]]
id = "research"
base_url = "https://xwiki.example.edu/xwiki"
wiki = "research"
read_only = true
username_env = "XWIKI_RESEARCH_USERNAME"
password_env = "XWIKI_RESEARCH_PASSWORD"
```

## Start

From this folder, install dependencies once:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

The project MCP configuration starts the server automatically. Restart Codex after changing the server or its configuration.

## Add to Codex

Replace the separate team/global server entries with this single definition in `~/.codex/config.toml` for all projects, or in `<project>/.codex/config.toml` for that trusted project only:

```toml
[mcp_servers.xwiki]
command = "/absolute/path/to/PI-TSC/xwiki-mcp/.venv/bin/python"
args = ["-m", "src.main"]
cwd = "/absolute/path/to/PI-TSC/xwiki-mcp"
default_tools_approval_mode = "auto"
```

Replace both paths with the local `xwiki-mcp` folder. A `wiki` argument on every tool selects one of the ids in `wikis.toml`.

The project Codex config defaults tools to `auto` and prompts before write tools. Codex supports per-tool approval overrides; here is the syntax used for those writes:

```toml
[mcp_servers.xwiki.tools.read_page]
approval_mode = "auto"

[mcp_servers.xwiki.tools.edit_page]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.upload_attachment]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.create_page]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.edit_page_section]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.append_section]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.create_page_from_template]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.add_comment]
approval_mode = "prompt"

[mcp_servers.xwiki.tools.add_tags]
approval_mode = "prompt"
```

This avoids an approval or auto-review step for reads; the tool call and its returned content still use model tokens. Restart Codex after configuration changes. See the [Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) for other options.

## Tools

- **Discovery:** `list_spaces`, `page_tree`, `search_pages`, `get_page_links`, `find_orphan_pages`
- **Pages:** `read_page`, `read_page_section`, `create_page`, `edit_page`, `append_section`, `edit_page_section`
- **History and reports:** `page_history`, `diff_page_versions`, `recent_changes`, `who_wrote_pages`
- **Attachments:** `list_attachments`, `read_attachment`, `upload_attachment`
- **Comments:** `list_comments`, `add_comment`
- **Tags:** `add_tags`
- **Workflows:** `create_page_from_template`, `project_status`, `decision_log`, `wiki_digest`, `consistency_check`

Read-only or read-write access is configured independently for every wiki. Page names use a `space` and `page`; nested spaces are separated with `/`.

Place files to upload in `uploads/` inside this folder, then call `upload_attachment` with the page and file name. Files larger than 10 MiB are rejected.
