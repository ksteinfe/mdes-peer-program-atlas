"""HTML → simplified markup for URL evidence (main content + head meta; chrome dropped)."""

from __future__ import annotations

import re
from html import escape

from bs4 import BeautifulSoup
from bs4.element import Comment, Tag

# Strip entire subtree (executable / chrome controls / head-only tags in body).
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

# Prefer in-document main content (order matters). Shared with Playwright post-load waits.
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

# Mega-menu / global chrome (removed only when **not** inside main/article).
_CHROME_SELECTORS: tuple[str, ...] = (
    ".tbm",
    ".tb-megamenu",
    "#block-topnavigation",
    "#block-quicksearch",
)

# Per-tag attribute allowlist (everything else dropped).
_ATTR_ALLOW: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "title"}),
    "img": frozenset({"src", "alt"}),
    "abbr": frozenset({"title"}),
}

_TAGS_MAY_KEEP_ID: frozenset[str] = frozenset(
    {
        "section",
        "article",
        "main",
        "div",
        "aside",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "span",
        "ul",
        "ol",
        "li",
        "table",
        "thead",
        "tbody",
        "tr",
        "th",
        "td",
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


def _collapse_blank_lines(s: str) -> str:
    lines = [ln.rstrip() for ln in s.splitlines()]
    out: list[str] = []
    for ln in lines:
        if not ln.strip():
            continue
        out.append(ln.strip())
    return "\n".join(out)


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
    parts: list[str] = ['<section id="peer-atlas-head-excerpt">']
    if title:
        parts.append(f"<h1>{escape(title)}</h1>")
    if desc:
        parts.append(f"<p>{escape(desc)}</p>")
    if canon:
        ce = escape(canon, quote=True)
        parts.append(f'<p><a href="{ce}">{ce}</a></p>')
    parts.append("</section>")
    return "".join(parts)


def _under_main_or_article(tag: Tag) -> bool:
    p = tag.parent
    while p is not None:
        if isinstance(p, Tag):
            n = (p.name or "").lower()
            if n in ("main", "article"):
                return True
        p = getattr(p, "parent", None)
    return False


def _remove_scripts_styles_comments(root: BeautifulSoup | Tag) -> None:
    for el in list(root.find_all(True)):
        n = (el.name or "").lower()
        if n in {"script", "style", "noscript"}:
            el.decompose()
    for c in root.find_all(string=True):
        if isinstance(c, Comment):
            c.extract()


def _substantial_block(el: Tag) -> bool:
    text = el.get_text(separator=" ", strip=True)
    if len(text) >= 40:
        return True
    return bool(el.find(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table"]))


def _preorder_index_map(body: Tag) -> dict[int, int]:
    """Map id(Tag) → preorder index under ``body`` (document order)."""
    idx: dict[int, int] = {}
    i = 0
    for el in body.descendants:
        if isinstance(el, Tag):
            idx[id(el)] = i
            i += 1
    return idx


def _is_strict_descendant_of(needle: Tag, ancestor: Tag) -> bool:
    p = needle.parent
    while p is not None:
        if p is ancestor:
            return True
        p = getattr(p, "parent", None)
    return False


def _collect_substantial_candidates(body: Tag) -> list[Tag]:
    """All selector hits + substantial articles; dedupe by Tag identity."""
    seen: set[int] = set()
    out: list[Tag] = []
    for sel in _CONTENT_SELECTORS:
        for t in body.select(sel):
            if not isinstance(t, Tag) or not _substantial_block(t):
                continue
            iid = id(t)
            if iid in seen:
                continue
            seen.add(iid)
            out.append(t)
    for art in body.find_all("article"):
        if not isinstance(art, Tag) or not _substantial_block(art):
            continue
        iid = id(art)
        if iid in seen:
            continue
        seen.add(iid)
        out.append(art)
    return out


def _filter_outermost_candidates(candidates: list[Tag]) -> list[Tag]:
    """Drop nodes that lie inside another candidate (emit outer shell once)."""
    roots: list[Tag] = []
    for t in candidates:
        inner = False
        for u in candidates:
            if u is t:
                continue
            if _is_strict_descendant_of(t, u):
                inner = True
                break
        if not inner:
            roots.append(t)
    return roots


def _visible_text_len(html_fragment: str) -> int:
    if not html_fragment.strip():
        return 0
    frag = BeautifulSoup(html_fragment, "html.parser")
    return len(frag.get_text(separator=" ", strip=True))


def _clone_body_after_chrome(body: Tag) -> Tag:
    """Deep clone of ``body`` then remove chrome outside main/article."""
    clone = BeautifulSoup(str(body), "html.parser").body
    if clone is None:
        c2 = BeautifulSoup(str(body), "html.parser")
        root = c2.find(True)
        if isinstance(root, Tag):
            return root
        return body
    _remove_chrome_outside_main(clone)
    return clone


def _remove_chrome_outside_main(body: Tag) -> None:
    for tag_name in ("header", "footer", "nav"):
        for el in list(body.find_all(tag_name)):
            if not _under_main_or_article(el):
                el.decompose()
    for sel in _CHROME_SELECTORS:
        for el in list(body.select(sel)):
            if not _under_main_or_article(el):
                el.decompose()


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
    if name in _TAGS_MAY_KEEP_ID and el.get("id"):
        keep.add("id")
    new: dict[str, str] = {}
    for k in keep:
        if k not in el.attrs:
            continue
        v = el.attrs[k]
        if isinstance(v, list):
            v = " ".join(str(x) for x in v)
        new[k] = str(v)
    el.attrs = new


def _finalize_fragment(fragment: Tag) -> None:
    for el in list(fragment.find_all(True)):
        n = (el.name or "").lower()
        if n in _DECOMPOSE_TAGS:
            el.decompose()
    for name in _UNWRAP_TAGS:
        for el in list(fragment.find_all(name)):
            el.unwrap()
    for el in fragment.find_all(True):
        _filter_tag_attrs(el)


def html_to_visible_text(html: str) -> str:
    """
    Return **simplified HTML** focused on **research-relevant page content**:

    - Prepends a small **head excerpt** (document title, meta description, canonical)
      as ``<section id="peer-atlas-head-excerpt">…``.
    - Collects **all** substantial matches from content-region selectors (plus
      substantial ``article`` tags), drops nested duplicates (keeps outer node only),
      concatenates each region as ``<section id="peer-atlas-region-NN">…``.
    - If merged regions are still thin vs chrome-stripped ``body``, appends
      ``<section id="peer-atlas-body-fallback">…`` with the rest of readable body.
    - If no substantial region is found, uses **``<body>``** after removing ``header``,
      ``footer``, ``nav``, and common mega-menu blocks **outside** ``main``/``article``.
    - Keeps structural tags (``p``, ``li``, headings, tables, etc.); drops ``script``,
      ``style``, and form controls.
    - **Preserves** ``href`` / ``title`` on ``<a>``, ``src`` / ``alt`` on ``<img>``,
      ``id`` on common block/heading tags, and strips other attributes.

    Non-HTML strings get light whitespace cleanup only.
    """
    if not isinstance(html, str):
        return ""
    raw = html.strip()
    if not raw:
        return ""
    if not looks_like_html(raw):
        return _collapse_blank_lines(raw)

    soup = BeautifulSoup(raw, "html.parser")
    title, desc, canon = _snapshot_head_meta(soup)
    head_html = _format_head_excerpt(title, desc, canon)

    _remove_scripts_styles_comments(soup)

    body = _body_or_wrapper(soup)

    if not (body.name and body.name.lower() == "body"):
        fragment = body
        _finalize_fragment(fragment)
        inner = fragment.decode_contents().strip()
        if not inner:
            inner = _collapse_blank_lines(fragment.get_text("\n"))
        if head_html:
            return (head_html + "\n" + inner).strip()
        return inner

    preorder = _preorder_index_map(body)
    candidates = _collect_substantial_candidates(body)
    roots = _filter_outermost_candidates(candidates)
    roots.sort(key=lambda t: preorder.get(id(t), 0))

    fb_body = _clone_body_after_chrome(body)
    _finalize_fragment(fb_body)
    fb_inner = fb_body.decode_contents().strip()
    fb_len = _visible_text_len(fb_inner)

    if not roots:
        inner = fb_inner
        if not inner:
            inner = _collapse_blank_lines(fb_body.get_text("\n"))
        if head_html:
            return (head_html + "\n" + inner).strip()
        return inner

    region_chunks: list[str] = []
    for i, root in enumerate(roots, start=1):
        copied = BeautifulSoup(str(root), "html.parser").find(True)
        if copied is None:
            continue
        wrap_soup = BeautifulSoup("", "html.parser")
        sec = wrap_soup.new_tag("section")
        sec["id"] = f"peer-atlas-region-{i:02d}"
        tag_name = (root.name or "div").lower()
        sec["data-peer-atlas-root"] = tag_name
        sec.append(copied)
        _finalize_fragment(sec)
        outer = str(sec).strip()
        if outer:
            region_chunks.append(outer)

    merged_inner = "\n".join(region_chunks).strip()
    merged_len = _visible_text_len(merged_inner)

    thin = fb_len > 0 and (
        merged_len < max(400, int(0.18 * fb_len)) or merged_len < 120
    )
    parts: list[str] = []
    if merged_inner:
        parts.append(merged_inner)
    if thin and fb_inner:
        parts.append(
            f'<section id="peer-atlas-body-fallback">\n{fb_inner}\n</section>'
        )

    inner = "\n".join(parts).strip()
    if not inner:
        inner = fb_inner or _collapse_blank_lines(body.get_text("\n"))

    if head_html:
        return (head_html + "\n" + inner).strip()
    return inner

