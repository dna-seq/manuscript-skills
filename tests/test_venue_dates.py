"""Dated venue facts, 0.30: the shipped catalogue, the user's own catalogue beside settings.yaml and a manuscript
record merge field by field, the newest read winning; `stale` lists only the facts old enough to re-read; `save`
keeps what an installed plugin reads across updates; the record keeps only the authors' cost routes. Run with
`uv run pytest`."""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "manuscript-journal-adapt" / "scripts"
CATALOGUE_YAML = ROOT / "skills" / "manuscript-integrity-check" / "references" / "venues.yaml"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


venues = _load("venues_dates", SCRIPTS / "venues.py")
scan = _load("scan_dates", ROOT / "skills" / "manuscript-integrity-check" / "scripts" / "scan.py")

# Calm: a journal of a publisher default, read on the file's date except its fee (read later) and its preprint
# rule. Server: a preprint server whose transfer list was read on its own date.
SHIPPED = {
    "checked": date(2026, 1, 10),
    "venues": {
        "pub": {"kind": "publisher", "name": "A Publisher", "writing_help": "disclose", "prompts": "no",
                "screening": "plagiarism", "ai_policy_url": "https://pub.example/ai"},
        "calm": {"name": "Calm Journal", "inherits": "pub", "url": "https://calm.example/guidelines",
                 "jif": 6.0, "jif_year": 2025, "provenance": {"jif": {"checked": date(2026, 1, 10),
                                                                    "source": "https://calm.example/about"}},
                 "limits": {"body_words": 4000, "abstract_words": 250},
                 "publication_costs": [{"amount": 2000, "currency": "EUR", "checked": date(2026, 3, 1),
                                        "source": "https://calm.example/fees"}],
                 "open_science": {"summary": "code in a repository", "preprints": "allowed",
                                  "source": "https://calm.example/policies", "checked": date(2026, 1, 10)}},
        "server": {"kind": "preprint", "name": "A Server", "writing_help": "disclose", "transfers": ["calm"],
                   "provenance": {"transfers": {"checked": date(2026, 2, 1), "source": "https://server.example/x"}}},
    },
}


@pytest.fixture()
def shipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "shipped.yaml"
    p.write_text(yaml.safe_dump(SHIPPED), encoding="utf-8")
    monkeypatch.setattr(venues, "VENUES_YAML", p)
    monkeypatch.setattr(venues, "SNAPSHOT_INDEX", tmp_path / "index.yaml")
    return p


def _user(data: dict) -> Path:
    p = venues.user_catalogue()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(data), encoding="utf-8")
    return p


def _run(*args: str) -> tuple[int, str, str]:
    result = CliRunner().invoke(venues.app, list(args))
    return result.exit_code, result.stdout, result.stderr if result.stderr_bytes is not None else ""


# ---------------------------------------------------------------------------------------- dates of a fact

def test_each_fact_takes_its_own_date_then_provenance_then_the_entry_then_the_file(shipped: Path) -> None:
    _, resolved = venues.load_venues()
    p = resolved["calm"]["provenance"]
    assert p["publication_costs"]["checked"] == date(2026, 3, 1)  # the list's own date
    assert p["jif"] == {"checked": date(2026, 1, 10), "source": "https://calm.example/about", "layer": "catalogue"}
    assert p["limits"]["checked"] == date(2026, 1, 10)  # no date of its own: the file's
    # Inherited from the publisher default, with the publisher's date.
    assert p["writing_help"]["checked"] == date(2026, 1, 10) and resolved["calm"]["writing_help"] == "disclose"
    stamped = venues._stamp({"checked": "2026-05-05", "jif": 3.0, "other_desk_rules": ["a rule"],
                             "other_desk_rules_source": "https://x.example", "other_desk_rules_checked":
                             "2026-10-27 (archived copy of 2026-10-17)", "transfers_checked": ["calm"],
                             "not_read": "403 on 2026-10-24"}, None, "record")
    assert stamped["provenance"]["jif"]["checked"] == date(2026, 5, 5)  # the entry's date
    assert stamped["provenance"]["other_desk_rules"] == {"checked": date(2026, 10, 27), "source": "https://x.example",
                                                         "layer": "record"}  # an older record's sidecar dates
    assert stamped["transfers_checked"] == ["calm"] and stamped["not_read"] == "403 on 2026-10-24"  # facts, not dates


def test_a_list_is_as_fresh_as_its_oldest_record() -> None:
    value = [{"days": 5, "checked": date(2026, 10, 27)}, {"days": 9, "checked": date(2026, 10, 19)}]
    assert venues._own_date(value, None) == date(2026, 10, 19)
    assert venues._own_date([{"days": 5, "checked": date(2026, 10, 27)}, {"days": 9}], date(2026, 1, 1)) == \
        date(2026, 1, 1)  # a record without a date counts at its entry's


# ---------------------------------------------------------------------------------------- the newest read wins

def test_the_user_catalogue_wins_where_it_is_newer_and_loses_where_it_is_older(shipped: Path) -> None:
    _user({"venues": {"calm": {
        "jif": 6.4, "jif_year": 2026, "provenance": {"jif": {"checked": date(2026, 7, 2), "source": "https://new"},
                                                     "jif_year": {"checked": date(2026, 7, 2)}},
        "publication_costs": [{"amount": 1800, "currency": "EUR", "checked": date(2025, 12, 1)}],  # older
    }}})
    _, resolved = venues.load_venues()
    calm = resolved["calm"]
    assert (calm["jif"], calm["jif_year"]) == (6.4, 2026)
    assert calm["provenance"]["jif"] == {"checked": date(2026, 7, 2), "source": "https://new", "layer": "user"}
    assert calm["publication_costs"][0]["amount"] == 2000  # the shipped fee was read later
    assert calm["provenance"]["publication_costs"]["layer"] == "catalogue"


def test_a_mapping_merges_key_by_key_and_keeps_the_older_date_for_keys_it_did_not_cover(shipped: Path) -> None:
    _user({"venues": {"calm": {"open_science": {"preprints": "only the submitted version",
                                                "source": "https://calm.example/new", "checked": date(2026, 9, 1)},
                               "limits": {"abstract_words": 200}, "provenance": {"limits": date(2026, 9, 1)}}}})
    _, resolved = venues.load_venues()
    calm = resolved["calm"]
    assert calm["open_science"]["preprints"] == "only the submitted version"
    assert calm["open_science"]["summary"] == "code in a repository"  # a key the newer read did not cover stays
    # ... and is not dated by a read that skipped it.
    assert calm["open_science"]["checked"] == calm["provenance"]["open_science"]["checked"] == date(2026, 1, 10)
    assert calm["limits"] == {"body_words": 4000, "abstract_words": 200}


def test_a_list_replaces_the_older_list(shipped: Path) -> None:
    _user({"venues": {"server": {"transfers": ["other"], "provenance": {"transfers": date(2026, 10, 27)}}}})
    _, resolved = venues.load_venues()
    assert resolved["server"]["transfers"] == ["other"]


def test_a_re_read_that_finds_a_fact_unchanged_moves_only_its_date(shipped: Path) -> None:
    _user({"venues": {"calm": {"provenance": {"publication_costs": {"checked": date(2026, 10, 27)}},
                               "open_science": {"checked": date(2026, 10, 27)}}}})
    _, resolved = venues.load_venues()
    calm = resolved["calm"]
    assert calm["publication_costs"] == [{"amount": 2000, "currency": "EUR", "checked": date(2026, 10, 27),
                                          "source": "https://calm.example/fees"}]
    assert calm["open_science"]["summary"] == "code in a repository"
    assert calm["provenance"]["open_science"]["checked"] == date(2026, 10, 27)
    assert calm["provenance"]["publication_costs"]["source"] == "https://calm.example/fees"


def test_on_the_same_date_the_later_layer_wins_and_a_new_venue_needs_a_name(shipped: Path) -> None:
    _user({"venues": {"calm": {"jif": 6.1, "provenance": {"jif": date(2026, 1, 10)}},
                      "nameless": {"jif": 2.0}, "added": {"name": "Added Journal", "jif": 4.0, "jif_year": 2026}}})
    code, out, err = _run("show", "added")
    assert code == 0 and "# Added Journal" in out
    _, resolved = venues.load_venues()
    assert resolved["calm"]["jif"] == 6.1 and "nameless" not in resolved


def test_an_unreadable_user_catalogue_never_stops_a_run(shipped: Path) -> None:
    p = venues.user_catalogue()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("venues: [unclosed", encoding="utf-8")
    code, out, err = _run("show", "calm")
    assert code == 0 and "could not be read and is left out" in err


def test_a_record_older_than_the_catalogue_no_longer_overrides_it(shipped: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"updated": "2026-02-01", "venue_facts": {
        "calm": {"jif": 5.0, "limits": {"abstract_words": 300}},
        "server": {"transfers": ["calm", "x"], "transfers_read": "2026-01-15"}}}), encoding="utf-8")
    _, resolved = venues.load_venues()
    merged = venues.with_facts(resolved, venues.load_record(record)[1])
    assert merged["calm"]["jif"] == 5.0 and merged["calm"]["from_facts"] == ["jif", "limits"]  # newer than the file
    assert merged["server"]["transfers"] == ["calm"]  # its own date, older than the catalogue's
    _user({"venues": {"calm": {"jif": 6.4, "jif_year": 2026, "provenance": {"jif": date(2026, 7, 2)}}}})
    _, resolved = venues.load_venues()
    assert venues.with_facts(resolved, venues.load_record(record)[1])["calm"]["jif"] == 6.4


# ---------------------------------------------------------------------------------------- cost routes

def test_the_record_cost_route_sets_what_the_authors_pay(shipped: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"priorities": {"journals": ["cost"]}, "cost_routes": {
        "calm": {"author_cost_eur": 0, "route": "the library's agreement pays", "checked": "2026-10-27"}}}),
        encoding="utf-8")
    code, out, _ = _run("ladder", "--only", "calm", "--record", str(record), "--format", "csv")
    row = next(csv.DictReader(io.StringIO(out)))
    assert code == 0 and row["author_cost_eur"] == "0" and row["fee_amount"] == "2000"
    assert row["fee_route"] == "the library's agreement pays" and row["facts_from_record"] == "cost_route"
    code, out, _ = _run("ladder", "--only", "calm", "--record", str(record))
    assert "the authors would pay about 0 EUR" in out


# ---------------------------------------------------------------------------------------- staleness

def test_stale_lists_only_old_facts_by_kind(shipped: Path) -> None:
    _, resolved = venues.load_venues()
    calm = resolved["calm"]
    due = {d["field"] for d in venues.stale_facts(calm, date(2026, 3, 15))}
    assert "writing_help" in due and "limits" not in due and "jif" not in due  # AI after 60 days; a JIF before June
    later = {d["field"]: d for d in venues.stale_facts(calm, date(2026, 7, 1))}
    assert "jif" in later and "June 2026" in later["jif"]["reason"]  # a newer JCR release came out
    assert "publication_costs" not in later and "limits" not in later  # within the year
    year = {d["field"] for d in venues.stale_facts(calm, date(2027, 1, 11))}
    assert {"limits", "open_science"} <= year and "publication_costs" not in year
    assert "name" not in year and "url" not in year  # names and addresses are never re-read for their age
    unverified = {**calm, "jif_year": None}
    assert "jif" not in {d["field"] for d in venues.stale_facts(unverified, date(2026, 3, 1))}  # due like any JIF
    assert "third-party" in {d["field"]: d for d in venues.stale_facts(unverified, date(2026, 7, 1))}["jif"]["reason"]


def test_the_stale_report_names_the_page_and_reads_the_record_ladders(shipped: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"ladders": {"journals": ["calm"], "preprints": ["server"]}}), encoding="utf-8")
    code, out, _ = _run("stale", "--record", str(record), "--on", "2026-03-15")
    assert code == 0
    assert "## Calm Journal (`calm`)" in out and "https://pub.example/ai" in out  # the AI policy's page
    assert "## A Server (`server`)" in out
    code, out, _ = _run("stale", "calm", "--on", "2026-03-15", "--format", "csv")
    rows = list(csv.DictReader(io.StringIO(out)))
    assert {r["field"] for r in rows} == {"writing_help", "prompts", "screening", "ai_policy_url"}
    assert all(r["checked"] == "2026-01-10" and r["layer"] == "catalogue" for r in rows)
    code, out, _ = _run("stale", "calm", "--on", "2026-02-01")
    assert "Every recorded fact about these venues is within its re-check period." in out
    assert _run("stale")[0] != 0  # no venues, no record


def test_the_ladder_points_to_stale_when_a_venue_has_old_facts(shipped: Path) -> None:
    code, out, _ = _run("ladder", "--only", "calm")
    assert code == 0 and "`venues.py stale calm`" in out  # read on 2026-01-10: its AI policy is due


# ---------------------------------------------------------------------------------------- where and save

def test_where_names_the_shipped_file_in_a_checkout_and_the_users_otherwise(shipped: Path, tmp_path: Path,
                                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(venues, "PLUGIN_ROOT", checkout)
    code, out, _ = _run("where")
    assert out.splitlines()[0] == str(shipped) and "repository checkout" in out
    cache = tmp_path / ".claude" / "plugins" / "cache" / "market" / "manuscript-skills" / "0.30.0"
    (cache / ".git").mkdir(parents=True)  # a cached copy that kept its .git is still an installed copy
    monkeypatch.setattr(venues, "PLUGIN_ROOT", cache)
    code, out, _ = _run("where")
    assert out.splitlines()[0] == str(venues.user_catalogue()) and "installed copy" in out


def test_save_merges_facts_into_the_user_catalogue_by_date(shipped: Path, tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(venues, "PLUGIN_ROOT", tmp_path / "installed")
    facts = tmp_path / "facts.yaml"
    facts.write_text(yaml.safe_dump({"venues": {"calm": {
        "jif": 6.4, "jif_year": 2026, "provenance": {"jif": {"checked": "2026-07-02", "source": "https://a"},
                                                     "jif_year": {"checked": "2026-07-02"}}}}}), encoding="utf-8")
    code, out, err = _run("save", str(facts))
    assert code == 0, err
    saved = yaml.safe_load(venues.user_catalogue().read_text(encoding="utf-8"))
    assert saved["venues"]["calm"]["jif"] == 6.4
    assert saved["venues"]["calm"]["provenance"]["jif"] == {"checked": date(2026, 7, 2), "source": "https://a"}
    # An older reading saved later does not replace the newer one; an unchanged re-read moves only the date.
    facts.write_text(yaml.safe_dump({"venues": {"calm": {"jif": 6.0, "provenance": {"jif": "2026-05-01"}}}}),
                     encoding="utf-8")
    assert _run("save", str(facts))[0] == 0
    facts.write_text(yaml.safe_dump({"venues": {"calm": {"provenance": {"jif": "2026-10-27"}}}}), encoding="utf-8")
    assert _run("save", str(facts))[0] == 0
    calm = yaml.safe_load(venues.user_catalogue().read_text(encoding="utf-8"))["venues"]["calm"]
    assert calm["jif"] == 6.4 and calm["provenance"]["jif"]["checked"] == date(2026, 10, 27)
    _, resolved = venues.load_venues()
    assert resolved["calm"]["jif"] == 6.4
    assert [p.name for p in venues.user_catalogue().parent.iterdir()] == ["venues.yaml"]  # no temporary file left


def test_save_refuses_undated_facts_and_the_checkout_without_user(shipped: Path, tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    facts = tmp_path / "facts.yaml"
    facts.write_text(yaml.safe_dump({"venues": {"calm": {"jif": 7.0}}}), encoding="utf-8")
    monkeypatch.setattr(venues, "PLUGIN_ROOT", tmp_path / "installed")
    code, out, err = _run("save", str(facts))
    assert code != 0 and "calm.jif" in out + err and not venues.user_catalogue().exists()
    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    monkeypatch.setattr(venues, "PLUGIN_ROOT", checkout)
    facts.write_text(yaml.safe_dump({"checked": "2026-10-27", "venues": {"calm": {"jif": 7.0}}}), encoding="utf-8")
    code, _, err = _run("save", str(facts))
    assert code == 2 and str(shipped) in err and not venues.user_catalogue().exists()
    assert _run("save", str(facts), "--user")[0] == 0 and venues.user_catalogue().exists()


# ---------------------------------------------------------------------------------------- other readers

def test_scan_reads_limits_from_the_user_catalogue(shipped: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan, "VENUES_YAML", shipped)
    _user({"venues": {"calm": {"limits": {"body_words": 3000}, "provenance": {"limits": date(2026, 10, 27)}}}})
    assert scan.load_venue_limits()["calm"] == {"body_words": 3000, "abstract_words": 250}
    assert scan.venue_name_and_url("calm") == ("Calm Journal", "https://calm.example/guidelines")


def test_show_prints_the_referee_form_and_the_figure_rules(shipped: Path) -> None:
    _user({"venues": {"calm": {
        "reviewer_form": {"questions": ["Are the conclusions supported?"], "recommendations": ["Accept", "Reject"],
                          "source": "https://calm.example/reviewers", "checked": date(2026, 10, 27)},
        "figure_rules": {"widths_mm": [85, 180], "min_text_pt": 8, "dpi": 300,
                         "source": "https://calm.example/figures", "checked": date(2026, 10, 27)}}}})
    code, out, _ = _run("show", "calm")
    assert code == 0
    assert "**What the journal asks its referees:**" in out and "“Are the conclusions supported?”" in out
    assert "recommendation options:" in out and "“Reject”" in out
    assert "**Figure rules:**" in out and "widths (mm): 85, 180" in out and "smallest text at print size (pt): 8" in out


# ---------------------------------------------------------------------------------------- the shipped catalogue

FIELD_KEYS = {
    "reviewer_form": {"questions", "recommendations", "guidance", "note", "source", "checked"},
    "figure_rules": {"widths_mm", "max_height_mm", "min_text_pt", "max_text_pt", "dpi", "formats", "display_items",
                     "alt_text", "other", "note", "source", "checked"},
}


def test_the_shipped_referee_forms_and_figure_rules_follow_their_contract() -> None:
    raw = yaml.safe_load(CATALOGUE_YAML.read_text(encoding="utf-8"))["venues"]
    seen = 0
    for key, entry in raw.items():
        for field, allowed in FIELD_KEYS.items():
            value = entry.get(field)
            if value is None:
                continue
            seen += 1
            assert set(value) <= allowed, (key, field, set(value) - allowed)
            assert value.get("source", "").startswith("https://") and venues._as_date(value.get("checked")), key
    assert seen >= 4


def test_every_dated_fact_in_the_shipped_catalogue_has_a_page_and_a_real_date() -> None:
    raw = yaml.safe_load(CATALOGUE_YAML.read_text(encoding="utf-8"))
    for key, entry in raw["venues"].items():
        for field, p in (entry.get("provenance") or {}).items():
            p = p if isinstance(p, dict) else {"checked": p}
            assert venues._as_date(p.get("checked")), (key, field)
            assert venues._as_date(p["checked"]) <= date.today(), (key, field)
            assert field in entry, (key, field)  # in the shipped file, provenance dates a fact the entry holds


def test_a_record_that_repeats_the_catalogue_is_not_named_as_the_source(shipped: Path, tmp_path: Path) -> None:
    record = tmp_path / "manuscript-record.yaml"
    record.write_text(yaml.safe_dump({"updated": "2026-10-27", "venue_facts": {
        "calm": {"jif": 6.0, "limits": {"abstract_words": 250}, "review_speed": []}}}), encoding="utf-8")
    _, resolved = venues.load_venues()
    calm = venues.with_facts(resolved, venues.load_record(record)[1])["calm"]
    assert calm["from_facts"] == ["review_speed"]  # only what the catalogue did not already say
    assert calm["provenance"]["jif"]["checked"] == date(2026, 10, 27)  # read again later: its date moves
    assert calm["provenance"]["jif"]["layer"] == "catalogue"


def test_an_unverified_impact_factor_passes_the_floor_but_ranks_below_verified_ones(shipped: Path, tmp_path: Path) -> None:
    _user({"venues": {
        "big": {"name": "Big Journal", "jif": 9.0, "provenance": {"jif": {"checked": date(2026, 10, 27),
                                                                      "source": "an aggregator site"}}},
        "small": {"name": "Small Journal", "jif": 3.1, "jif_year": 2026, "provenance": {"jif": date(2026, 10, 27)}}}})
    code, out, _ = _run("ladder", "--only", "big", "--only", "small", "--only", "calm", "--priority", "reach",
                        "--min-jif", "3", "--format", "csv")
    assert code == 0
    assert [r["key"] for r in csv.DictReader(io.StringIO(out))] == ["calm", "small", "big"]  # 9.0 is not verified
    code, out, _ = _run("ladder", "--only", "big", "--only", "calm", "--priority", "reach")
    assert "9.0 (not verified: a third-party figure without its year)" in out
    assert "placed below the verified ones at the step for reach (journal impact factor): Big Journal." in out
