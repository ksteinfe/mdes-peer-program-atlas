"""HTML → simplified markup for URL evidence (full body + head meta; no region heuristics)."""

from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
from bs4.formatter import HTMLFormatter

# Strip entire subtree (non-human-readable / non-evidence machinery in body).
_DECOMPOSE_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "iframe",
        "svg",
        "canvas",
        "video",
        "audio",
        "picture",
        "template",
        "object",
        "embed",
        "map",
        "img",
        "meta",
        "link",
        "input",
        "button",
        "select",
        "textarea",
        "option",
    }
)

_UNWRAP_TAGS = frozenset({"form", "fieldset", "label"})
_UNWRAP_PHRASING = frozenset({"strong"})

# Serialize text with fewer entities (e.g. ``&`` not forced to ``&amp;`` where safe).
_HTML_MIN_ENTITIES = HTMLFormatter()

# Do not collapse whitespace inside these (code-like blocks).
_SKIP_TEXT_WS_NORMALIZE: frozenset[str] = frozenset({"pre", "code", "kbd", "samp"})

# Playwright waits for one of these to attach before stability + snapshot (same list as before).
_CONTENT_SELECTORS: tuple[str, ...] = (
    "main",
    "[role='main']",
    "#main-content",
    "#content",
    "article",
    ".field--name-field-page-body",
    ".field--name-body",
    ".node__content",
    ".region-content",
    ".layout-content",
    ".l-content",
    ".l-main",
    ".region--content",
)

# Public alias for Playwright (wait until a content region attaches).
CONTENT_REGION_SELECTORS: tuple[str, ...] = _CONTENT_SELECTORS

# Per-tag attribute allowlist (everything else dropped). No ``id`` anywhere; ``<a>`` has no attributes.
_ATTR_ALLOW: dict[str, frozenset[str]] = {
    "a": frozenset(),
    "abbr": frozenset({"title"}),
}

# Flow / phrasing wrappers removed when they contain no non-blank text (children walked).
_STRIP_IF_EMPTY_TAGS: frozenset[str] = frozenset(
    {
        "div",
        "span",
        "section",
        "article",
        "aside",
        "header",
        "footer",
        "nav",
        "main",
        "figure",
        "figcaption",
        "blockquote",
        "center",
        "summary",
        "details",
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        "table",
        "thead",
        "tbody",
        "tfoot",
        "tr",
        "td",
        "th",
        "caption",
        "colgroup",
        "col",
        "p",
        "pre",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "em",
        "b",
        "i",
        "u",
        "sub",
        "sup",
        "small",
        "cite",
        "abbr",
        "mark",
        "a",
        "code",
        "kbd",
        "samp",
        "var",
        "del",
        "ins",
        "q",
        "address",
        "time",
    }
)


def looks_like_html(s: str) -> bool:
    """Heuristic: treat as HTML when markup-shaped, not for plain error placeholders."""
    if not s or not isinstance(s, str):
        return False
    raw = s.lstrip()
    if raw.startswith("[Peer Atlas fetch:"):
        return False
    t = raw[:12000]
    tl = t.lower()
    if "<!doctype html" in tl[:300]:
        return True
    if "<html" in tl[:800] and "<" in t[:200]:
        return True
    if "<body" in tl[:4000]:
        return True
    if t.startswith("<") and t.count("<") >= 4:
        return bool(re.search(r"<\s*[a-zA-Z][-a-zA-Z0-9:]*(\s|>)", t[:8000]))
    return False


def _normalize_plain_text_line(s: str) -> str:
    """For non-HTML inputs: decode entities and collapse all whitespace to single spaces."""
    t = unescape((s or "").strip())
    return re.sub(r"\s+", " ", t).strip()


def _minimal_escape_pcdata(s: str) -> str:
    """Escape only ``<`` / ``>`` so ``&`` and typical prose stay literal in stored HTML."""
    return (s or "").replace("<", "&lt;").replace(">", "&gt;")


def _normalize_excerpt_field(s: str) -> str:
    return re.sub(r"\s+", " ", unescape((s or "").strip())).strip()


def _snapshot_head_meta(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Title, meta description, canonical URL (plain strings)."""
    title = ""
    st = soup.title
    if st and st.string:
        title = st.string.strip()
    desc = ""
    m = soup.find("meta", attrs={"name": "description"})
    if m and m.get("content"):
        desc = str(m["content"]).strip()
    if not desc:
        m = soup.find("meta", attrs={"property": "og:description"})
        if m and m.get("content"):
            desc = str(m["content"]).strip()
    canon = ""
    for lk in soup.find_all("link"):
        rel = lk.get("rel")
        rels = " ".join(rel) if isinstance(rel, list) else str(rel or "")
        if "canonical" in rels.lower() and lk.get("href"):
            canon = str(lk["href"]).strip()
            break
    return title, desc, canon


def _format_head_excerpt(title: str, desc: str, canon: str) -> str:
    if not (title or desc or canon):
        return ""
    title = _normalize_excerpt_field(title)
    desc = _normalize_excerpt_field(desc)
    canon = _normalize_excerpt_field(canon)
    parts: list[str] = ["<section>"]
    if title:
        parts.append(f"<h1>{_minimal_escape_pcdata(title)}</h1>")
    if desc:
        parts.append(f"<p>{_minimal_escape_pcdata(desc)}</p>")
    if canon:
        parts.append(f"<p>{_minimal_escape_pcdata(canon)}</p>")
    parts.append("</section>")
    return "".join(parts)


def _remove_scripts_styles_comments(root: BeautifulSoup | Tag) -> None:
    for el in list(root.find_all(True)):
        n = (el.name or "").lower()
        if n in {"script", "style", "noscript"}:
            el.decompose()
    for c in root.find_all(string=True):
        if isinstance(c, Comment):
            c.extract()


def _body_or_wrapper(soup: BeautifulSoup) -> Tag:
    if soup.body is not None:
        return soup.body
    for h in soup.find_all("head"):
        h.decompose()
    if soup.html is not None:
        return soup.html
    wrap = soup.new_tag("div")
    for c in list(soup.contents):
        wrap.append(c)
    return wrap


def _filter_tag_attrs(el: Tag) -> None:
    name = (el.name or "").lower()
    keep = set(_ATTR_ALLOW.get(name, ()))
    new: dict[str, str] = {}
    for k in keep:
        if k not in el.attrs:
            continue
        v = el.attrs[k]
        if isinstance(v, list):
            v = " ".join(str(x) for x in v)
        new[k] = str(v)
    el.attrs = new


_WS_TEXT_RE = re.compile(r"[\s\u00a0\u200b\ufeff]+", re.UNICODE)
_RUN_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def _subtree_has_nonblank_text(el: Tag) -> bool:
    """True if any descendant string has a non-whitespace character, or a ``br``/``hr``."""
    for child in el.descendants:
        if isinstance(child, Tag):
            n = (child.name or "").lower()
            if n in {"br", "hr", "wbr"}:
                return True
    for s in el.strings:
        if _WS_TEXT_RE.sub("", str(s)):
            return True
    return False


def _ancestor_is_skip_ws_tag(node: NavigableString | Tag) -> bool:
    p = node.parent
    while p is not None:
        if isinstance(p, Tag) and (p.name or "").lower() in _SKIP_TEXT_WS_NORMALIZE:
            return True
        p = p.parent
    return False


def _normalize_text_nodes(fragment: Tag) -> None:
    """Decode entities in text nodes and collapse runs of whitespace to a single space."""
    for s in list(fragment.strings):
        if isinstance(s, Comment):
            continue
        if not isinstance(s, NavigableString):
            continue
        if _ancestor_is_skip_ws_tag(s):
            continue
        raw = str(s)
        t = _RUN_WHITESPACE_RE.sub(" ", unescape(raw)).strip()
        if t == raw:
            continue
        s.replace_with(t)


def _strip_empty_wrapper_tags(fragment: Tag) -> None:
    """
    Remove container tags in ``_STRIP_IF_EMPTY_TAGS`` that have no non-blank text
    in any descendant (including nested empty markup).
    """
    for _ in range(200):
        changed = False
        candidates = [
            t
            for t in fragment.find_all(True)
            if isinstance(t, Tag) and (t.name or "").lower() in _STRIP_IF_EMPTY_TAGS
        ]
        candidates.sort(key=lambda t: len(list(t.parents)), reverse=True)
        for el in candidates:
            if _subtree_has_nonblank_text(el):
                continue
            el.decompose()
            changed = True
        if not changed:
            break


def _finalize_fragment(fragment: Tag) -> None:
    for el in list(fragment.find_all(True)):
        n = (el.name or "").lower()
        if n in _DECOMPOSE_TAGS:
            el.decompose()
    for name in _UNWRAP_TAGS:
        for el in list(fragment.find_all(name)):
            el.unwrap()
    for name in _UNWRAP_PHRASING:
        for el in list(fragment.find_all(name)):
            el.unwrap()
    for el in fragment.find_all(True):
        _filter_tag_attrs(el)
    _strip_empty_wrapper_tags(fragment)
    _normalize_text_nodes(fragment)
    _strip_empty_wrapper_tags(fragment)


def _clone_and_simplify_body_tree(body: Tag) -> Tag:
    """Deep clone of ``body`` (or root tag) then strip scripts/decompose/unwrap/attrs."""
    clone = BeautifulSoup(str(body), "html.parser")
    root = clone.body
    if root is None:
        root = clone.find(True)
    if not isinstance(root, Tag):
        return body
    _finalize_fragment(root)
    return root


def html_to_visible_text(html: str) -> str:
    """
    Return **simplified HTML** for the **entire** document body (no “main only” heuristics):

    - Prepends a small **head excerpt** (title, meta description, canonical) as
      a bare ``<section>…</section>`` block.
    - Serializes **everything under ``<body>``** (or the document root if there is no
      ``body``): navigation, headers, footers, and main copy—all kept so DOM text is
      not dropped by region selection.
    - Removes ``script`` / ``style`` / ``noscript`` / comments, decomposes other
      machinery in ``_DECOMPOSE_TAGS`` (including all ``img``), unwraps forms and
      ``strong`` (inner text kept), strips all attributes from ``<a>`` (link text only),
      drops ``id`` on every tag, keeps ``title`` only on ``abbr`` where allowlisted,
      removes empty wrapper elements, then **normalizes text**: HTML entities decoded
      to characters (e.g. ``&amp;`` → ``&``), newlines and other runs of whitespace
      collapsed to a **single space** (skipped inside ``pre`` / ``code`` / ``kbd`` /
      ``samp``).

    **Displayed vs DOM:** this follows the **live HTML** after fetch (Playwright waits
    handle settling); it does not re-check CSS ``display:none`` on every node.

    Non-HTML strings get entity decode + single-line whitespace collapse.
    """
    if not isinstance(html, str):
        return ""
    raw = html.strip()
    if not raw:
        return ""
    if not looks_like_html(raw):
        return _normalize_plain_text_line(raw)

    soup = BeautifulSoup(raw, "html.parser")
    title, desc, canon = _snapshot_head_meta(soup)
    head_html = _format_head_excerpt(title, desc, canon)

    _remove_scripts_styles_comments(soup)

    body = _body_or_wrapper(soup)
    fragment = _clone_and_simplify_body_tree(body)
    inner = fragment.decode_contents(formatter=_HTML_MIN_ENTITIES).strip()
    if not inner:
        inner = _normalize_plain_text_line(fragment.get_text(" "))

    if head_html:
        return (head_html + "\n" + inner).strip()
    return inner
