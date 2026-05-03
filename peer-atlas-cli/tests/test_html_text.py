"""html_text — simplified body HTML."""

from __future__ import annotations

from peer_atlas_cli.html_text import html_to_visible_text, looks_like_html


def test_looks_like_html_simple() -> None:
    assert looks_like_html("<!DOCTYPE html><html><body>x</body></html>") is True
    assert looks_like_html("plain prose only") is False
    assert looks_like_html("[Peer Atlas fetch: error]\n") is False


def test_html_to_visible_text_keeps_structure_strips_script() -> None:
    html = """<!DOCTYPE html><html><head>
<script type="text/javascript">alert(1);</script>
<style>.x{color:red}</style>
<title>T</title></head><body>
<p class="foo" id="a">Hello <b>world</b></p>
<script>evil()</script>
</body></html>"""
    out = html_to_visible_text(html)
    assert "alert" not in out
    assert "evil" not in out
    assert ".x{" not in out
    assert "<p" in out
    assert "Hello" in out
    assert "world" in out
    assert "class=" not in out.lower()
    assert "id=" not in out.lower()
    assert "<section>" in out
    assert "<h1>T</h1>" in out


def test_html_to_visible_text_plain_collapses_whitespace() -> None:
    s = "  line one\n\nline two  "
    assert html_to_visible_text(s) == "line one line two"


def test_entities_decoded_and_amp_not_escaped_in_pcdata() -> None:
    html = "<html><head><title>T</title></head><body><p>a&amp;b &amp; c</p></body></html>"
    out = html_to_visible_text(html)
    assert "a&b & c" in out
    assert "&amp;" not in out


def test_strong_unwrapped() -> None:
    html = "<html><head><title>T</title></head><body><p>x<strong>y</strong>z</p></body></html>"
    out = html_to_visible_text(html)
    assert "<strong" not in out.lower()
    assert "xyz" in out


def test_html_to_visible_text_json_ld_script_removed() -> None:
    html = """<html><body>
<script type="application/json">{"x":1}</script>
<p>Visible only</p>
</body></html>"""
    out = html_to_visible_text(html)
    assert '"x"' not in out
    assert "<p>" in out
    assert "Visible only" in out


def test_html_img_tags_removed() -> None:
    html = (
        '<body><p>x</p><img src="/a.png" alt="A" class="c" data-x="1" /></body>'
    )
    out = html_to_visible_text(html)
    assert "<img" not in out.lower()
    assert "a.png" not in out
    assert "alt=" not in out.lower()
    assert "<p>" in out
    assert "x" in out


def test_anchor_text_kept_href_stripped() -> None:
    html = """<html><head><title>T</title></head><body>
<p><a href="/x" title="Tip">Label</a></p>
</body></html>"""
    out = html_to_visible_text(html)
    assert "Label" in out
    assert 'href=' not in out
    assert "title=" not in out.lower()


def test_full_body_keeps_nav_and_main() -> None:
    html = """<html><head><title>Paths</title>
<meta name="description" content="Every MIMS unique focus areas."/>
<link rel="canonical" href="https://example.edu/paths"/>
</head><body>
<nav><ul><li><a href="/nav">Navitem</a></li></ul></nav>
<main><h1>Paths Through</h1><p>Every MIMS student’s degree is unique. This is the main
body paragraph with enough text to count as substantial content here.</p></main>
</body></html>"""
    out = html_to_visible_text(html)
    assert "Every MIMS student" in out
    assert "main body paragraph" in out  # newline inside <p> collapsed to space
    assert "Navitem" in out
    assert 'href=' not in out
    assert "<a>" in out or "<a " in out
    assert "example.edu" in out
    assert "<h1>Paths</h1>" in out  # from head excerpt (title)


def test_head_meta_and_canonical_in_excerpt() -> None:
    html = """<!DOCTYPE html><html><head>
<title>Page T</title>
<meta name="description" content="Desc D"/>
<link rel="canonical" href="https://x.edu/y"/>
</head><body><p id="z">Body</p></body></html>"""
    out = html_to_visible_text(html)
    assert "Page T" in out
    assert "Desc D" in out
    assert "https://x.edu/y" in out
    assert "id=" not in out.lower()


def test_full_body_keeps_header_nav_footer() -> None:
    html = """<html><head><title>X</title></head><body>
<header><nav><a href="/n">N</a></nav></header>
<div class="node__content"><p>Deep content in node body forty chars minimum xxxxxxxxxxxx</p></div>
<footer>F</footer>
</body></html>"""
    out = html_to_visible_text(html)
    assert "Deep content" in out
    assert 'href=' not in out
    assert "N" in out
    assert "F" in out


def test_full_body_two_articles() -> None:
    html = """<!DOCTYPE html><html><head><title>T</title></head><body>
<article><p>First article block with enough characters to qualify as substantial text here.</p></article>
<article><p>Second article block with enough characters to qualify as substantial text here.</p></article>
</body></html>"""
    out = html_to_visible_text(html)
    assert "peer-atlas-region" not in out
    assert "First article" in out
    assert "Second article" in out


def test_empty_wrapper_divs_removed() -> None:
    html = """<html><head><title>T</title></head><body>
<div><div></div><div><span> </span></div></div>
<p>Kept</p>
</body></html>"""
    out = html_to_visible_text(html)
    assert "Kept" in out
    assert "<div" not in out.lower()


def test_p_with_only_br_not_removed() -> None:
    html = """<html><head><title>T</title></head><body><p><br/></p><p>After</p></body></html>"""
    out = html_to_visible_text(html)
    assert "br" in out.lower()
    assert "After" in out
