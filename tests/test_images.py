import pytest

from pipeline.images import extract_og_image, upgrade_image_url


@pytest.mark.parametrize("url,expected", [
    ("https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/dddf/live/x.jpg",
     "https://ichef.bbci.co.uk/ace/standard/976/cpsprodpb/dddf/live/x.jpg"),
    ("https://ichef.bbci.co.uk/news/240/cpsprodpb/1/x.jpg", "https://ichef.bbci.co.uk/news/976/cpsprodpb/1/x.jpg"),
    ("https://site.example/wp-content/uploads/2026/11/photo-150x150.jpg",
     "https://site.example/wp-content/uploads/2026/11/photo.jpg"),
    ("https://i0.wp.com/site.example/a.jpg?w=300&ssl=1", "https://i0.wp.com/site.example/a.jpg?w=1200&ssl=1"),
    ("https://i.guim.co.uk/img/x.jpg?width=140&quality=85&s=abc", "https://i.guim.co.uk/img/x.jpg?width=140&quality=85&s=abc"),
    ("https://cdn.example/big.jpg", "https://cdn.example/big.jpg"),
])
def test_upgrade_image_url(url, expected):
    assert upgrade_image_url(url) == expected


def test_extract_og_image_variants():
    base = "https://news.example/world/story"
    assert extract_og_image('<meta property="og:image" content="https://img.example/a.jpg">', base) == "https://img.example/a.jpg"
    assert extract_og_image("<meta content='/img/b.jpg' property='og:image'/>", base) == "https://news.example/img/b.jpg"
    assert extract_og_image('<meta name="twitter:image" content="https://img.example/t.jpg">', base) == "https://img.example/t.jpg"
    assert extract_og_image('<meta property="og:image" content="javascript:alert(1)">', base) is None
    assert extract_og_image('<html><head><title>x</title></head></html>', base) is None
    assert extract_og_image('<meta property="og:image" content="https://img.example/a&amp;b.jpg">', base) == "https://img.example/a&b.jpg"
