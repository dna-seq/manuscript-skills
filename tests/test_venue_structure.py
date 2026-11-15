"""venues.py common: the body structure a ladder's venues share (a flexible order accepts another) and what each
word limit counts, run through the real report code on venue facts that carry `section_order` and `<limit>_counts`."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_journal_0_19 import _common, _section, catalogue  # noqa: F401

IMRD = ["Introduction", "Materials and Methods", "Results", "Discussion"]
IRDM = ["Introduction", "Results", "Discussion", "Materials and Methods"]
MBE = ("Results and Discussion may be combined, and the order of the sections can be modified if deemed necessary "
       "for clarity of presentation (e.g., Materials and Methods prior to Results).")


def test_a_flexible_venue_accepts_the_order_the_fixed_ones_set(catalogue: Path, tmp_path: Path) -> None:
    out = _common(tmp_path, {
        "calm": {"required_sections": ["Introduction", "Method", "Results", "Discussion", "Conclusion"]},
        "strict": {"required_sections": IRDM, "section_order": "flexible", "section_order_quote": [MBE]}},
        "calm", "strict")
    now, differ = _section(out, "Adapt now"), _section(out, "Choose per venue")
    assert ("Body sections: Introduction, Method, Results, Discussion (every venue), in this order, "
            "which every venue accepts: Strict Journal lists another order but allows this one") in now
    assert MBE in now
    assert "Conclusion, after Discussion, needed by Calm Journal alone" in differ


@pytest.mark.parametrize("order", [None, "fixed"])
def test_an_order_not_recorded_as_flexible_is_never_counted_as_accepting(catalogue: Path, tmp_path: Path,
                                                                          order: str | None) -> None:
    strict = {"required_sections": IRDM, **({"section_order": order} if order else {})}
    out = _common(tmp_path, {"calm": {"required_sections": IMRD}, "strict": strict}, "calm", "strict")
    assert "Body sections:" not in _section(out, "Adapt now")
    assert "No one order suits them all" in _section(out, "Choose per venue")


def test_a_venue_with_no_recorded_structure_stays_unknown(catalogue: Path, tmp_path: Path) -> None:
    out = _common(tmp_path, {"calm": {"required_sections": IRDM, "section_order": "flexible"}}, "calm", "strict")
    differ = _section(out, "Choose per venue")
    assert "Body sections" not in _section(out, "Adapt now")
    assert "Strict Journal set none or are not researched for it, so whether it accepts this order is unknown" in differ


def test_each_limit_says_what_it_counts_or_that_the_page_does_not(catalogue: Path, tmp_path: Path) -> None:
    out = _common(tmp_path, {
        "calm": {"limits": {"body_words": 5000, "body_words_kind": "recommended", "body_words_counts":
                            "excluding the Materials and methods, References, and Figure legends"}},
        "strict": {"limits": {"body_words": 4000, "body_words_counts": "not_stated"}}}, "calm", "strict")
    differ = _section(out, "Choose per venue")
    assert ("Calm Journal, 5000 words (recommended; excluding the Materials and methods, References, and Figure "
            "legends); Strict Journal, 4000 words (the page does not say what it counts)") in differ
    assert "They do not all count the same parts of the paper" in differ
