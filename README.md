# XWiki MCP

## Configure

Add your connection details to `.env`:

```dotenv
XWIKI_BASE_URL=https://your-xwiki.example/xwiki
XWIKI_WIKI=team0526
XWIKI_USERNAME=your-username
XWIKI_PASSWORD=your-password
```

## Start

From this folder, install dependencies once:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

The project MCP configuration starts the server automatically. Restart Codex after changing the server or its configuration.

## Tools

- **Discovery:** `list_spaces`, `page_tree`, `search_pages`, `get_page_links`, `find_orphan_pages`
- **Pages:** `read_page`, `read_page_section`, `create_page`, `edit_page`, `append_section`, `edit_page_section`
- **History:** `page_history`, `diff_page_versions`, `recent_changes`, `who_wrote_pages`
- **Attachments and discussion:** `list_attachments`, `read_attachment`, `upload_attachment`, `list_comments`, `add_comment`
- **Tags:** `add_tags`
- **Project workflows:** `create_page_from_template`, `project_status`, `decision_log`, `wiki_digest`, `consistency_check`

The global wiki connection is read-only. The team wiki connection supports page, comment, and tag changes. Page names use a `space` and `page`; nested spaces are separated with `/`.

Place files to upload in `uploads/` inside this folder, then call `upload_attachment` with the page and file name. Files larger than 10 MiB are rejected.
