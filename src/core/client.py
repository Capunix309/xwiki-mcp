"""Small authenticated HTTP client and XWiki REST URL builders."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from . import config


def wiki_url(resource: str = "", params: list[tuple[str, str]] | None = None) -> str:
    """Build a URL below the configured wiki resource."""
    path = f"{config.rest_root()}/wikis/{urllib.parse.quote(config.current().wiki, safe='')}"
    if resource:
        path += "/" + resource.lstrip("/")
    if params:
        path += "?" + urllib.parse.urlencode(params)
    return path


def page_url(space: str, page: str, suffix: str = "") -> str:
    """Build a page URL, accepting nested space paths separated by '/'."""
    space_parts = [part.strip() for part in space.split("/")]
    if not space_parts or any(part in {"", ".", ".."} for part in space_parts):
        raise ValueError("space must contain valid space names separated by '/'.")
    page = page.strip()
    if not page or page in {".", ".."} or "/" in page or "\\" in page:
        raise ValueError("page must be a single, non-empty page name.")
    path = f"spaces/{'/spaces/'.join(urllib.parse.quote(part, safe='') for part in space_parts)}/pages/{urllib.parse.quote(page, safe='')}"
    if suffix:
        path += "/" + "/".join(urllib.parse.quote(item, safe="") for item in suffix.strip("/").split("/"))
    return wiki_url(path)


def request(method: str, url: str, body: bytes | None = None, content_type: str | None = None) -> tuple[bytes, str]:
    """Send a REST request and return its payload and content type."""
    headers = {"Accept": "application/json, application/xml;q=0.9, */*;q=0.8"}
    if content_type:
        headers["Content-Type"] = content_type
    settings = config.current()
    if method.upper() not in {"GET", "HEAD", "OPTIONS"} and settings.read_only:
        raise PermissionError(f"The {settings.name} XWiki is read-only.")
    if settings.username:
        token = base64.b64encode(f"{settings.username}:{settings.password}".encode()).decode("ascii")
        headers["Authorization"] = f"Basic {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read(800).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"XWiki returned HTTP {exc.code}" + (f": {detail}" if detail else "")) from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach the XWiki REST API: {exc.reason}") from None


def _xml_value(element: ET.Element) -> Any:
    children = list(element)
    if not children:
        return element.text or ""
    result: dict[str, Any] = {}
    for child in children:
        key = child.tag.rsplit("}", 1)[-1]
        value = _xml_value(child)
        if key in result:
            if not isinstance(result[key], list):
                result[key] = [result[key]]
            result[key].append(value)
        else:
            result[key] = value
    return result


def parse(payload: bytes, content_type: str = "") -> Any:
    """Decode JSON or XML REST responses into Python values."""
    text = payload.decode("utf-8", errors="replace")
    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    try:
        return _xml_value(ET.fromstring(text))
    except ET.ParseError:
        return text


def get(resource: str, params: list[tuple[str, str]] | None = None) -> Any:
    """GET and decode a wiki-level REST resource."""
    return parse(*request("GET", wiki_url(resource, params)))


def get_page(space: str, page: str, suffix: str = "", params: list[tuple[str, str]] | None = None) -> Any:
    """GET and decode a page-level REST resource."""
    url = page_url(space, page, suffix)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return parse(*request("GET", url))


def xml_page(content: str, title: str | None = None, syntax: str | None = None) -> bytes:
    """Serialize only the provided page fields so other fields stay intact."""
    root = ET.Element("page", xmlns="http://www.xwiki.org")
    if title is not None:
        ET.SubElement(root, "title").text = title
    if syntax is not None:
        ET.SubElement(root, "syntax").text = syntax
    ET.SubElement(root, "content").text = content
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def records(value: Any, collection: str) -> list[dict[str, Any]]:
    """Extract a collection from either JSON or XML REST representations."""
    if isinstance(value, dict):
        items = value.get(collection)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        if isinstance(items, dict):
            return [items]
        singular = collection[:-1] if collection.endswith("s") else collection
        if singular in value and isinstance(value[singular], dict):
            return [value[singular]]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def value_text(value: Any, *keys: str) -> str:
    """Find the first non-empty named field in a REST record."""
    if not isinstance(value, dict):
        return ""
    for key in keys:
        found = value.get(key)
        if isinstance(found, (str, int, float)) and str(found):
            return str(found)
    return ""


def all_pages(space: str | None = None, author: str | None = None, max_pages: int = 500) -> list[dict[str, Any]]:
    """Fetch pages in bounded chunks from the wiki-wide page endpoint."""
    params: list[tuple[str, str]] = [("start", "0"), ("number", "100")]
    if space:
        params.append(("space", space))
    if author:
        params.append(("author", author))
    results: list[dict[str, Any]] = []
    start = 0
    while len(results) < max_pages:
        current = [(key, str(start) if key == "start" else value) for key, value in params]
        data = get("pages", current)
        batch = records(data, "pageSummaries") or records(data, "page") or records(data, "pages")
        if not batch:
            break
        results.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    return results[:max_pages]


def page_fields(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize page summary metadata for tool responses."""
    return {
        "fullName": value_text(item, "fullName", "pageFullName", "id"),
        "title": value_text(item, "title"),
        "space": value_text(item, "space"),
        "pageName": value_text(item, "name", "pageName"),
        "creator": value_text(item, "creator"),
        "author": value_text(item, "author"),
        "lastEditor": value_text(item, "modifier", "lastEditor"),
        "modified": value_text(item, "modified"),
        "version": value_text(item, "version"),
    }
