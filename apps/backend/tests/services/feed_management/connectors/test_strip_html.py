"""Tests for strip_html utility used by all feed connectors."""

from app.services.feed_management.connectors.base import strip_html


class TestStripHtml:
    def test_basic_tags(self):
        assert strip_html("<p>Hello</p>") == "Hello"

    def test_nested_tags(self):
        result = strip_html('<div class="x"><strong>Bold</strong> text</div>')
        assert "Bold" in result
        assert "text" in result
        assert "<" not in result

    def test_woocommerce_real_facebook_pasted(self):
        raw = (
            '<div class="xdj266r x14z9mp xat24cr x1lziwak x1vvkbs x126k92a">'
            ' <div dir="auto">VOLKSWAGEN TIGUAN 4x4</div>'
        )
        result = strip_html(raw)
        assert "<" not in result
        assert "VOLKSWAGEN TIGUAN 4x4" in result

    def test_woocommerce_real_paragraph_list(self):
        raw = "<p>DACIA SANDERO 2015</p> <p>*1.2 BENZINA</p> <p>*SENZORI PARCARE</p>"
        result = strip_html(raw)
        assert "DACIA SANDERO 2015" in result
        assert "*1.2 BENZINA" in result
        assert "<p>" not in result

    def test_preserves_text_structure(self):
        raw = "<p>Line 1</p><p>Line 2</p>"
        result = strip_html(raw)
        assert "Line 1" in result
        assert "Line 2" in result
        # Lines should be separated (newline between them)
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_none_returns_empty(self):
        assert strip_html(None) == ""

    def test_empty_returns_empty(self):
        assert strip_html("") == ""

    def test_plain_text_unchanged(self):
        assert strip_html("Already clean text") == "Already clean text"

    def test_html_entities_decoded(self):
        assert strip_html("Price &amp; Value") == "Price & Value"

    def test_br_tags_become_newline(self):
        result = strip_html("Line 1<br>Line 2<br/>Line 3")
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        assert len(lines) == 3

    def test_strong_bold_stripped(self):
        result = strip_html("<strong>Vw Tiguan 2012 4x4</strong>")
        assert result == "Vw Tiguan 2012 4x4"

    def test_complex_real_woocommerce(self):
        raw = (
            '<div class="x14z9mp xat24cr x1lziwak x1vvkbs xtlvy1s x126k92a">'
            ' <div dir="auto"> <strong>Vw Tiguan 2012 4x4</strong>'
            ' </div> </div>'
        )
        result = strip_html(raw)
        assert "Vw Tiguan 2012 4x4" in result
        assert "<" not in result
        assert "x14z9mp" not in result
