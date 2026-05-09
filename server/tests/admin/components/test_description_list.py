"""Tests for ``rapidly/admin/components/_description_list.py``.

Pure helpers + Item classes. Three load-bearing surfaces:

- ``_SOCIAL_LABELS`` carries the per-platform display label
  (with trailing colon). ``twitter`` and ``x`` BOTH map to the
  same mathematical-bold-X glyph (Twitter rebrand). Drift to
  drop a platform would fall back to title-case (`Discord:`)
  which is acceptable but loses the Twitter rebrand styling.
- ``_strip_protocol`` removes ``https://`` and ``http://``
  prefixes for display, leaves bare domains alone, and doesn't
  break on protocol-less URLs.
- ``DescriptionListAttrItem.get_value`` returns None when the
  underlying attr is None (so the renderer can show an em-dash
  placeholder) and stringifies otherwise.
"""

from __future__ import annotations

from rapidly.admin.components import _description_list as M
from rapidly.admin.components._description_list import (
    _SOCIAL_LABELS,
    DescriptionListAttrItem,
    _strip_protocol,
)


class TestSocialLabels:
    def test_twitter_and_x_share_same_glyph(self) -> None:
        # Pin: post-rebrand, both ``twitter`` and ``x`` keys
        # render as the bold-X (𝕏) symbol so legacy and current
        # entries display consistently.
        assert _SOCIAL_LABELS["twitter"] == _SOCIAL_LABELS["x"]
        assert "\U0001d54f" in _SOCIAL_LABELS["twitter"]

    def test_known_platforms_have_proper_case(self) -> None:
        # Pin: "GitHub" (NOT "Github" / "github"). Drift would
        # render the wrong brand casing on every workspace
        # detail page.
        assert _SOCIAL_LABELS["github"] == "GitHub:"
        assert _SOCIAL_LABELS["linkedin"] == "LinkedIn:"
        assert _SOCIAL_LABELS["youtube"] == "YouTube:"

    def test_all_labels_end_with_colon(self) -> None:
        # Pin: trailing colon — the renderer puts the label
        # before the URL without inserting punctuation. Drift
        # would render "GitHub https://..." (no separator).
        for value in _SOCIAL_LABELS.values():
            assert value.endswith(":")


class TestStripProtocol:
    def test_strips_https(self) -> None:
        assert _strip_protocol("https://github.com/x") == "github.com/x"

    def test_strips_http(self) -> None:
        assert _strip_protocol("http://example.com") == "example.com"

    def test_protocol_less_url_unchanged(self) -> None:
        # Pin: bare domains pass through unchanged.
        assert _strip_protocol("example.com/path") == "example.com/path"

    def test_does_not_strip_https_in_middle(self) -> None:
        # Pin: only LEADING prefix stripped (not embedded).
        assert (
            _strip_protocol("https://x.com/?next=https://y.com")
            == "x.com/?next=https://y.com"
        )

    def test_empty_string(self) -> None:
        assert _strip_protocol("") == ""


class _Obj:
    """Stand-in for an admin-detail entity."""

    def __init__(self, **kw: object) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class TestDescriptionListAttrItem:
    def test_label_defaults_to_attr_name(self) -> None:
        # Pin: omitting label falls back to the attr name so
        # callers can pass just the attr.
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem("name")
        assert item.label == "name"

    def test_explicit_label_takes_precedence(self) -> None:
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem(
            "name", label="Display Name"
        )
        assert item.label == "Display Name"

    def test_get_raw_value_uses_attrgetter(self) -> None:
        # Pin: dotted attrs work — ``user.name`` reaches into
        # nested objects.
        nested = _Obj(user=_Obj(name="Alice"))
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem("user.name")
        assert item.get_raw_value(nested) == "Alice"

    def test_get_value_returns_none_for_none_raw(self) -> None:
        # Pin: None passes through (the renderer shows em-dash
        # for None). Drift to "None" string would render the
        # literal text "None" on every detail page.
        obj = _Obj(name=None)
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem("name")
        assert item.get_value(obj) is None

    def test_get_value_stringifies_non_none(self) -> None:
        obj = _Obj(count=42)
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem("count")
        assert item.get_value(obj) == "42"

    def test_clipboard_default_false(self) -> None:
        # Pin: default no-clipboard. Otherwise every detail row
        # would render a copy button (clutter).
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem("x")
        assert item.clipboard is False

    def test_repr_includes_attr_label_clipboard(self) -> None:
        # Pin: __repr__ format used in admin dev console / logs.
        item: DescriptionListAttrItem[_Obj] = DescriptionListAttrItem(
            "name", label="Name", clipboard=True
        )
        r = repr(item)
        assert "DescriptionListAttrItem" in r
        assert "attr='name'" in r
        assert "label='Name'" in r
        assert "clipboard=True" in r


class TestExports:
    def test_dunder_all_pinned(self) -> None:
        assert M.__all__ == [
            "DescriptionList",
            "DescriptionListAttrItem",
            "DescriptionListDateTimeItem",
            "DescriptionListItem",
            "DescriptionListLinkItem",
        ]
