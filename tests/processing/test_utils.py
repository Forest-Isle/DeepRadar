from deepradar.processing.utils import strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_handles_plain_text():
    assert strip_html("no tags here") == "no tags here"


def test_strip_html_handles_empty_string():
    assert strip_html("") == ""


def test_strip_html_strips_whitespace():
    assert strip_html("  <p>  spaced  </p>  ") == "spaced"


def test_strip_html_handles_nested_tags():
    assert strip_html("<div><p>nested <a href='#'>link</a></p></div>") == "nested link"


def test_strip_html_preserves_entities():
    assert strip_html("&amp; &lt; &gt;") == "& < >"
