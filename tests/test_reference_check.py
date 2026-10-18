"""Offline tests for manuscript-reference-check: scripts/support.py and the reference code of scan.py.

Network calls are answered from real API responses recorded on 2026-10-15 and trimmed to the fields the scripts
read (evals/fixtures/manuscript-reference-check/recorded/). The seeded and clean manuscripts are the eval fixtures,
so these tests also check that the mechanical layer finds each planted defect once, where it was planted, and
nothing in the clean control.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
import urllib.parse
from pathlib import Path
from types import ModuleType
from typing import Callable, Optional

import httpx
import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "evals" / "fixtures" / "manuscript-reference-check"
REC = FIX / "recorded"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # pydantic resolves deferred annotations through sys.modules
    spec.loader.exec_module(module)
    return module


support = _load("refcheck_support", ROOT / "skills" / "manuscript-reference-check" / "scripts" / "support.py")
scan = _load("refcheck_scan", ROOT / "skills" / "manuscript-integrity-check" / "scripts" / "scan.py")

SEEDED_STATUS = {"C1": "quote_located", "C6": "quote_located", "C2": "numbers_missing", "C3": "polarity_mismatch",
                 "C4": "quote_located", "C5": "source_unavailable", "C7": "source_unavailable"}


# --------------------------------------------------------------------------------------------------
# Recorded registries
# --------------------------------------------------------------------------------------------------

def _rec(name: str) -> dict:
    return json.loads((REC / name).read_text(encoding="utf-8"))


CROSSREF = {
    "10.1126/science.1190532": "crossref_sebastiani.json",
    "10.1101/2020.05.20.20108217": "crossref_pgs_preprint.json",
    "10.1038/s41588-021-00783-5": "crossref_pgs_published.json",
    "10.1093/bioinformatics/bts280": "crossref_li2012.json",
    "10.1038/s41467-019-11112-0": "crossref_duncan.json",
    "10.1038/s41576-018-0018-x": "crossref_torkamani.json",
    "10.3389/fgene.2022.1000667": "crossref_frontiers.json",
    "10.1093/nar/gkg509": "crossref_sift.json",
}
EUROPEPMC = {
    "10.1126/science.1190532": "epmc_search_sebastiani.json",
    "10.1038/s41467-019-11112-0": "epmc_search_duncan.json",
    "10.3389/fgene.2022.1000667": "epmc_search_frontiers.json",
    "10.1038/s41576-018-0018-x": "epmc_search_torkamani.json",
    "10.1038/s41588-021-00783-5": "epmc_search_pgs_published.json",
    "10.1101/2020.05.20.20108217": "epmc_search_pgs_preprint.json",
}
ARXIV = {"1206.6899": "arxiv_1206.6899.xml", "1203.6364": "arxiv_1203.6364.xml"}
DATACITE = {"10.5281/zenodo.21457492": "datacite_zenodo.json"}
JATS_URL = "/content/early/2020/05/23/2020.05.20.20108217.source.xml"


class Registry:
    """A MockTransport handler serving the recordings; `down` hosts answer 503, `patch` edits a recording."""

    def __init__(self, down: tuple[str, ...] = (), patch: Optional[dict[str, Callable[[dict], None]]] = None,
                 fail_all: bool = False) -> None:
        self.down, self.patch, self.fail_all = down, patch or {}, fail_all
        self.calls: list[str] = []

    def _json(self, name: str) -> httpx.Response:
        data = _rec(name)
        if name in self.patch:
            data = copy.deepcopy(data)
            self.patch[name](data)
        return httpx.Response(200, json=data)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        self.calls.append(f"{request.method} {url.host}{url.path}")
        if self.fail_all:
            raise httpx.ConnectError("offline", request=request)
        if url.host in self.down:
            return httpx.Response(503)
        path = url.path
        if url.host == "api.crossref.org" and path.startswith("/works/"):
            name = CROSSREF.get(path[len("/works/"):].lower())
            return self._json(name) if name else httpx.Response(404, text="Resource not found.")
        if url.host == "www.ebi.ac.uk" and path.endswith("/search"):
            doi = url.params.get("query", "").removeprefix('DOI:"').rstrip('"').lower()
            name = EUROPEPMC.get(doi)
            return self._json(name) if name else httpx.Response(200, json={"hitCount": 0, "resultList": {"result": []}})
        if url.host == "www.ebi.ac.uk" and path.endswith("/fullTextXML"):
            if "PMC6658471" in path:
                return httpx.Response(200, text=(REC / "epmc_fulltext_PMC6658471.xml").read_text(encoding="utf-8"))
            return httpx.Response(500)  # what Europe PMC answers for an author manuscript it does not serve
        if url.host == "api.biorxiv.org":
            name = "medrxiv_pgs.json" if "/medrxiv/10.1101/2020.05.20.20108217" in path else "biorxiv_empty.json"
            return self._json(name)
        if url.host == "www.medrxiv.org" and path == JATS_URL:
            return httpx.Response(200, text=(REC / "medrxiv_jats_pgs.xml").read_text(encoding="utf-8"))
        if url.host == "export.arxiv.org":
            name = ARXIV.get(url.params.get("id_list", ""))
            return httpx.Response(200, text=(REC / name).read_text(encoding="utf-8")) if name else httpx.Response(
                200, text="<feed><entry><title>Error</title></entry></feed>")
        if url.host == "arxiv.org":
            return httpx.Response(404)
        if url.host == "api.datacite.org":
            name = DATACITE.get(path[len("/dois/"):].lower())
            return self._json(name) if name else httpx.Response(404)
        if url.host == "doi.org":
            known = path[1:].lower() in CROSSREF or path[1:].lower() in DATACITE
            return httpx.Response(302 if known else 404)
        if url.host == "eutils.ncbi.nlm.nih.gov":
            return self._json("pubmed_sift.json") if url.params.get("id") == "12824425" else httpx.Response(
                200, json={"result": {url.params.get("id", ""): {"error": "cannot get document summary"}}})
        return httpx.Response(404)


@pytest.fixture()
def registry(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Registry]:
    """Route every httpx.Client the scripts open to a recorded Registry; no sleeping."""
    original = httpx.Client

    def install(**kwargs: object) -> Registry:
        handler = Registry(**kwargs)  # type: ignore[arg-type]
        monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
        return handler

    monkeypatch.setattr(scan.time, "sleep", lambda _: None)
    return install


def _line_of(path: Path, needle: str) -> int:
    return next(i for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1) if needle in line)


def _manuscript(tmp_path: Path, *entries: str) -> Path:
    body = "# Results\n\nAs reported [1].\n\n## References\n\n" + "\n".join(f"{i}. {e}" for i, e in
                                                                           enumerate(entries, start=1)) + "\n"
    path = tmp_path / "paper.md"
    path.write_text(body, encoding="utf-8")
    return path


# --------------------------------------------------------------------------------------------------
# support.py: normalisation, numbers, polarity
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("quote, source", [
    ("a significant effect", "a signiﬁcant effect"),                       # ligature in the source
    ("the regulation of", "the regu-\nlation of"),                              # hyphenation at a line break
    ("the regulation of", "the regu­lation of"),                           # soft hyphen
    ('the "gold standard" set', "the “gold standard” set"),           # typographic quotes
    ("the authors' own data", "the authors’ own data"),
    ("studies (2008-2017, inclusive)", "studies (2008–2017, inclusive)"),  # en dash
    ("67% of studies", "67 % of studies"),                             # no-break and thin spaces
    ("(Duncan et al., 2019)", "( Duncan et al., 2019 )"),                       # spacing inside brackets (XML)
    ("p = 3.7 × 10⁻⁶", "p = 3.7 × 10 −6"),                            # superscript vs extracted exponent
    ("non-European ancestry", "non- European ancestry"),
    ("WE FIND that", "we find that"),
    ("café au lait", "café au lait"),                                     # composed vs decomposed accent
])
def test_quotes_are_located_through_copy_artifacts(quote: str, source: str) -> None:
    assert support.locate(quote, support.normalise(source)) is not None


@pytest.mark.parametrize("quote, source", [
    ("polygenic scores is higher", "polygenic scores is lower"),
    ("another 29% included", "another 19% included"),
    ("67% of studies", "6.7% of studies"),
    ("", "anything"),
])
def test_a_changed_word_or_number_is_not_located(quote: str, source: str) -> None:
    assert support.locate(quote, support.normalise(source)) is None


def test_an_ellipsis_quote_matches_its_parts_in_order_only() -> None:
    source = support.normalise("Alpha beta gamma. Delta epsilon zeta. Eta theta.")
    assert support.locate("Alpha beta ... epsilon zeta", source)[2] == "ellipsis"
    assert support.locate("Alpha beta […] epsilon zeta", source) is not None
    assert support.locate("epsilon zeta ... Alpha beta", source) is None


@pytest.mark.parametrize("claim, quote, missing, years", [
    ("141,456 humans were sequenced", "variation in 141456 humans", [], []),
    ("an AUC of 0.50", "AUC 0.5", [], []),
    ("p = 3.7e-6", "p = 3.7 × 10 −6", [], []),
    ("p = 3.7 × 10⁻⁶", "p = 0.0000037", [], []),
    ("A further 29% of studies [1]", "another 19% included", ["29"], []),
    ("67% of studies [12, 14] (see Figure 2 and Table S3)", "67% of studies", [], []),
    ("67% of studies (Duncan et al., 2019)", "67% of studies", [], []),
    ("In 2019, 67% of studies", "67% of studies", [], ["2019"]),
    ("COVID-19 patients in 3 cohorts", "patients in 3 cohorts", [], []),
    ("rs429358 carriers", "carriers", [], []),
])
def test_claim_numbers_must_occur_in_the_quote(claim: str, quote: str, missing: list[str], years: list[str]) -> None:
    check = support.check_numbers(claim, quote)
    assert check.missing == missing and check.year_like_missing == years
    assert set(check.found) | set(check.missing) | set(check.year_like_missing) == set(check.in_claim)


@pytest.mark.parametrize("claim, quote, mismatch", [
    ("scores performed comparably in African ancestry samples", "scores is lower in non-European samples", True),
    ("scores were lower in African ancestry samples", "scores is lower in non-European samples", False),
    ("the variant was not associated with risk", "the variant was associated with risk", True),
    ("the variant was associated with risk", "the variant was associated with risk", False),
    ("treatment increased survival", "treatment decreased survival", True),
    ("treatment did not reduce survival", "treatment reduced survival", True),
    ("loss-of-function variants were associated with disease", "loss-of-function variants were associated with disease",
     False),
    ("no significant difference in accuracy", "no significant difference in accuracy", False),
    ("accuracy was higher with the new score", "there was no significant difference in accuracy", True),
    ("the cohort included 412 people", "412 people were recruited", False),
])
def test_polarity(claim: str, quote: str, mismatch: bool) -> None:
    assert bool(support.polarity_mismatch(claim, quote)) is mismatch


# --------------------------------------------------------------------------------------------------
# support.py: the seeded fixture and its clean control
# --------------------------------------------------------------------------------------------------

def test_seeded_claims_flag_each_planted_mechanical_defect_once(tmp_path: Path) -> None:
    report = support.run(FIX / "claims-seeded.yaml", online=False, cache_dir=tmp_path)
    status = {r.id: r.status for r in report.results}
    assert status == SEEDED_STATUS
    by_id = {r.id: r for r in report.results}
    assert by_id["C2"].numbers.missing == ["29"]
    assert by_id["C3"].polarity and not by_id["C3"].numbers.missing
    # Only the review's passage attributes the number to another study.
    assert {r.id for r in report.results if r.secondary_markers} == {"C4"}
    assert any("duncan et al" in m for m in by_id["C4"].secondary_markers)
    assert support.exit_code(report) == 1


def test_clean_control_raises_no_mechanical_flag(tmp_path: Path) -> None:
    report = support.run(FIX / "claims-clean.yaml", online=False, cache_dir=tmp_path)
    assert not [r for r in report.results if r.status in support.FLAGGED]
    assert {r.id for r in report.results if r.status == "source_unavailable"} == {"C6", "C7"}
    assert not [r for r in report.results if r.secondary_markers]
    assert support.exit_code(report) == 3  # unavailable sources keep the run from reading as clean


def test_the_script_never_reports_confirmed(tmp_path: Path) -> None:
    for name in ("claims-seeded.yaml", "claims-clean.yaml"):
        report = support.run(FIX / name, online=False, cache_dir=tmp_path)
        assert {r.status for r in report.results} <= set(support.STATUSES)
        assert "confirmed" not in {r.status for r in report.results} | {f for r in report.results for f in r.flags}


def test_cli_writes_reports_and_exit_codes(tmp_path: Path) -> None:
    runner = CliRunner()
    out_json, out_md = tmp_path / "s.json", tmp_path / "s.md"
    seeded = runner.invoke(support.app, [str(FIX / "claims-seeded.yaml"), "--cache-dir", str(tmp_path / "c"),
                                         "--json", str(out_json), "--md", str(out_md)])
    assert seeded.exit_code == 1, seeded.output
    data = json.loads(out_json.read_text())
    assert {r["id"]: r["status"] for r in data["results"]} == SEEDED_STATUS
    assert "The claim gives 29, which the passage does not contain." in out_md.read_text()
    clean = runner.invoke(support.app, [str(FIX / "claims-clean.yaml"), "--cache-dir", str(tmp_path / "c")])
    assert clean.exit_code == 3, clean.output
    one = tmp_path / "one.yaml"
    one.write_text("claims:\n  - id: C1\n    location: L6\n    reference: 1\n"
                   "    claim: 67% of studies included only European ancestry participants [1].\n"
                   "    quote: 67% of studies included exclusively European ancestry participants\n"
                   f"    source: {FIX / 'sources' / 'duncan2019.txt'}\n", encoding="utf-8")
    assert runner.invoke(support.app, [str(one), "--cache-dir", str(tmp_path / "c")]).exit_code == 0


def test_markdown_quotes_the_claim_and_passage_links_identifiers_and_says_the_status_in_words(
        tmp_path: Path) -> None:
    """The report a person reads: each claim quoted with its section, the passage quoted, the cited work as a
    link, and what was found in words; never a bare line reference or a status token."""
    report = support.run(FIX / "claims-seeded.yaml", online=False, cache_dir=tmp_path)
    md = support.to_markdown(report)
    by_id = {r.id: r for r in report.results}
    for r in report.results:
        assert f"\u201c{' '.join(r.claim.split())}\u201d" in md, r.id
        if r.status != "source_unavailable":
            assert f"\u201c{' '.join(r.quote.split())}\u201d" in md, r.id
    assert "under Introduction (seeded.md, line 14)" in md
    assert "(https://doi.org/10.1126/science.1190532)" in md and "(https://doi.org/10.1038/s41576-018-0018-x)" in md
    assert "A number in the claim is not in the passage (claim C2)" in md
    assert "This claim could not be checked" in md and "different direction from the claim" in md
    assert by_id["C3"].polarity[0] in md
    for token in support.STATUSES:
        assert token not in md, token
    assert not re.search(r"\bL\d+\b", md)
    assert "\u2192" not in md and "->" not in md
    # Flagged claims come before the ones whose passage was found clean.
    assert md.index("(claim C3)") < md.index("(claim C2)") < md.index("(claim C5)") < md.index("(claim C1)")


@pytest.mark.parametrize("location, where", [
    ("seeded.md:14 (Introduction)", "under Introduction (seeded.md, line 14)"),
    ("paper.md:42", "(paper.md, line 42)"),
    ("L6", "(line 6)"),
    ("42", "(line 42)"),
    ("Results, Performance (paper.md, line 42)", "under Results, Performance (paper.md, line 42)"),
])
def test_claim_locations_are_rendered_as_sections_with_lines_in_parentheses(location: str, where: str) -> None:
    assert support.where_in_manuscript(location) == where


@pytest.mark.parametrize("kind, value, url", [
    ("doi", "10.1038/s41467-019-11112-0", "https://doi.org/10.1038/s41467-019-11112-0"),
    ("pmid", "31346163", "https://pubmed.ncbi.nlm.nih.gov/31346163/"),
    ("pmcid", "PMC6658471", "https://europepmc.org/article/PMC/PMC6658471"),
    ("arxiv", "1203.6364", "https://arxiv.org/abs/1203.6364"),
])
def test_identifiers_become_links(kind: str, value: str, url: str) -> None:
    assert support.identifier_url(kind, value) == url


@pytest.mark.parametrize("name, content, problems", [
    ("bad.yaml", "claims: [unclosed", ["not valid YAML"]),
    ("bad.json", "{\"claims\": [", ["not valid JSON"]),
    ("empty.yaml", "claims: []\n", ["non-empty list"]),
    ("scalar.yaml", "just text\n", ["non-empty list"]),
    ("strings.yaml", "claims:\n  - just a string\n", ["expected a mapping"]),
    ("missing.yaml", "- id: C1\n  claim: Something [1].\n", ["'location' field required", "'reference' field required"]),
    ("blank.yaml", "- {id: C1, location: L1, reference: '1', claim: '   '}\n", ["'claim' value error, must not be blank"]),
    ("dupe.yaml", "- {id: C1, location: L1, reference: '1', claim: A}\n- {id: C1, location: L2, reference: '2', claim: B}\n",
     ["duplicate id 'C1'"]),
    ("priority.yaml", "- {id: C1, location: L1, reference: '1', claim: A, priority: urgent}\n", ["must be one of"]),
    ("types.yaml", "- {id: C1, location: L1, reference: '1', claim: [a, b]}\n", ["'claim' input should be a valid string"]),
])
def test_malformed_claims_files_are_refused_with_every_problem(tmp_path: Path, name: str, content: str,
                                                               problems: list[str]) -> None:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    result = CliRunner().invoke(support.app, [str(path), "--cache-dir", str(tmp_path / "c")])
    assert result.exit_code == 2
    for problem in problems:
        assert problem in result.output, result.output
    with pytest.raises(support.ClaimsFileError) as raised:
        support.load_claims(path)
    assert len(raised.value.problems) == len(problems)


def test_integer_ids_and_locations_are_accepted(tmp_path: Path) -> None:
    path = tmp_path / "claims.yaml"
    path.write_text("- {id: 1, location: 42, reference: 3, claim: A claim.}\n", encoding="utf-8")
    claims, _ = support.load_claims(path)
    assert (claims[0].id, claims[0].location, claims[0].reference) == ("1", "42", "3")


@pytest.mark.parametrize("source, reason", [
    ("missing.txt", "was not found"),
    ("paper.pdf", "convert it to text"),
    (None, "No source was given"),
    ("doi:10.1038/s41467-019-11112-0", "needs --online"),
])
def test_sources_that_cannot_be_read_are_unavailable(tmp_path: Path, source: Optional[str], reason: str) -> None:
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.7")
    entry = {"id": "C1", "location": "L1", "reference": "1", "claim": "A claim.", "quote": "A claim."}
    if source:
        entry["source"] = source
    path = tmp_path / "claims.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    result = support.run(path, online=False, cache_dir=tmp_path / "cache").results[0]
    assert result.status == "source_unavailable" and reason in (result.source.reason or "")


@pytest.mark.parametrize("value, parsed", [
    ("doi:10.1038/s41467-019-11112-0", ("doi", "10.1038/s41467-019-11112-0")),
    ("https://doi.org/10.1038/s41467-019-11112-0", ("doi", "10.1038/s41467-019-11112-0")),
    ("10.48550/arXiv.1203.6364", ("arxiv", "1203.6364")),
    ("arxiv:1203.6364v2", ("arxiv", "1203.6364")),
    ("https://arxiv.org/abs/1203.6364", ("arxiv", "1203.6364")),
    ("pmc6658471", ("pmcid", "PMC6658471")),
    ("pmid: 31346163", ("pmid", "31346163")),
    ("sources/duncan.txt", None),
])
def test_identifiers_are_recognised(value: str, parsed: Optional[tuple[str, str]]) -> None:
    assert support.parse_identifier(value) == parsed


def test_online_sources_come_from_open_routes_and_the_cache(tmp_path: Path, registry: Callable[..., Registry]) -> None:
    claims = tmp_path / "claims.yaml"
    claims.write_text("""claims:
  - id: OA
    location: L1
    reference: "1"
    claim: "67% of studies included only European ancestry participants [1]."
    quote: "67% of studies included exclusively European ancestry participants"
    source: "doi:10.1038/s41467-019-11112-0"
  - id: RXIV
    location: L2
    reference: "2"
    claim: "The PGS Catalog held 192 published scores from 78 publications [2]."
    quote: "The PGS Catalog currently contains 192 published PGS from 78 publications"
    source: "doi:10.1101/2020.05.20.20108217"
  - id: ABSTRACT
    location: L3
    reference: "3"
    claim: "A model of 150 SNPs predicted exceptional longevity with 77% accuracy [3]."
    quote: "a genetic model that includes 150 single-nucleotide polymorphisms (SNPs) and found that it could predict EL with 77% accuracy"
    source: "doi:10.1126/science.1190532"
  - id: PAYWALLED
    location: L4
    reference: "4"
    claim: "Polygenic risk profiling has been proposed for screening [4]."
    source: "doi:10.1038/s41576-018-0018-x"
  - id: MANUSCRIPT
    location: L5
    reference: "5"
    claim: "As of December 2020 the catalog held 657 scores [5]."
    quote: "As of December 2020, the PGS Catalog contains 657 consistently annotated PGSs"
    source: "doi:10.1038/s41588-021-00783-5"
""", encoding="utf-8")
    calls = registry()
    report = {r.id: r for r in support.run(claims, online=True, cache_dir=tmp_path / "cache").results}
    assert (report["OA"].status, report["OA"].source.scope, report["OA"].source.via) == (
        "quote_located", "full_text", "europepmc:fullTextXML")
    assert (report["RXIV"].status, report["RXIV"].source.scope) == ("quote_located", "full_text")
    assert report["RXIV"].source.via.startswith("medrxiv:jatsxml")
    assert (report["ABSTRACT"].status, report["ABSTRACT"].source.scope) == ("quote_located", "abstract")
    assert report["PAYWALLED"].status == "source_unavailable" and report["PAYWALLED"].source.scope == "abstract"
    assert report["MANUSCRIPT"].status == "source_unavailable"
    assert report["MANUSCRIPT"].source.free_urls, "a free page the API does not serve is offered for reading"
    assert not any("sci-hub" in c or "nature.com" in c for c in calls.calls)
    # A second run, with the network gone, reuses the cached texts; nothing that failed was cached.
    offline = registry(fail_all=True)
    again = {r.id: r for r in support.run(claims, online=True, cache_dir=tmp_path / "cache").results}
    assert {k for k, r in again.items() if r.source.cache_file} == {"OA", "RXIV", "ABSTRACT", "PAYWALLED"}
    assert {k: r.status for k, r in again.items()} == {k: r.status for k, r in report.items()}
    # Only the uncached source was asked for again (and failed, which is not cached either).
    assert offline.calls == ["GET www.ebi.ac.uk/europepmc/webservices/rest/search"]


# --------------------------------------------------------------------------------------------------
# scan.py: retractions, preprints, withdrawals, authors
# --------------------------------------------------------------------------------------------------

def _refs_by_doi(report: object) -> dict[str, object]:
    return {(r.doi or r.arxiv or r.pmid).lower(): r for r in report.references}


def test_seeded_identity_defects_are_found_once_where_planted(registry: Callable[..., Registry]) -> None:
    registry()
    seeded = FIX / "seeded.md"
    report = scan.check_references(seeded, online=True, search_unidentified=True)
    refs = _refs_by_doi(report)
    findings = {(f.line, f.severity.value, "retracted" if "retracted" in f.message else "published"
                 if "has been published" in f.message else f.message[:40])
                for f in report.findings if f.check == "references"}
    assert findings == {(_line_of(seeded, "Sebastiani P"), "blocker", "retracted"),
                        (_line_of(seeded, "Lambert SA"), "minor", "published")}
    seb = refs["10.1126/science.1190532"]
    assert (seb.retraction, seb.retraction_source, seb.retraction_notice) == (
        "retracted", "crossref (retraction-watch)", "10.1126/science.333.6041.404-a")
    assert {doi: r.retraction for doi, r in refs.items()} == {
        "10.1038/s41467-019-11112-0": "none_found", "10.3389/fgene.2022.1000667": "none_found",
        "10.1126/science.1190532": "retracted", "10.1101/2020.05.20.20108217": "none_found",
        "10.1038/s41576-018-0018-x": "none_found"}
    assert refs["10.1038/s41467-019-11112-0"].retraction_source == "crossref+europepmc"
    pv = refs["10.1101/2020.05.20.20108217"].published_version
    assert (pv.doi, pv.venue, pv.year, pv.source, pv.shared_authors, pv.metadata_checked) == (
        "10.1038/s41588-021-00783-5", "Nature Genetics", "2021", "crossref:is-preprint-of", True, True)
    assert refs["10.1101/2020.05.20.20108217"].withdrawn is False
    assert all(r.author_check == "consistent" for r in report.references)


def test_clean_control_raises_no_identity_finding(registry: Callable[..., Registry]) -> None:
    registry()
    report = scan.check_references(FIX / "clean.md", online=True, search_unidentified=True)
    assert [f for f in report.findings if f.check == "references"] == []
    assert {r.retraction for r in report.references} == {"none_found"}
    assert all(r.status == "resolved" and r.author_check == "consistent" and r.published_version is None
               for r in report.references)


def test_offline_references_are_never_reported_clean(tmp_path: Path) -> None:
    report = scan.check_references(FIX / "seeded.md", online=False, search_unidentified=False)
    assert {r.retraction for r in report.references} == {"not_checked"}
    assert all(r.withdrawn is None and r.author_check == "not_compared" for r in report.references)
    assert "not assessed (offline mode)" in scan.references_to_markdown(report)


def test_a_retraction_one_registry_misses_is_found_by_the_next(tmp_path: Path,
                                                               registry: Callable[..., Registry]) -> None:
    registry(patch={"crossref_sebastiani.json": lambda d: d["message"].pop("updated-by")})
    paper = _manuscript(tmp_path, "Sebastiani P, Solovieff N, Puca A, et al. Genetic signatures of exceptional "
                                  "longevity in humans. Science. 2010. doi:10.1126/science.1190532")
    ref = scan.check_references(paper, online=True, search_unidentified=True).references[0]
    assert (ref.status, ref.retraction, ref.retraction_source) == ("retracted", "retracted", "europepmc")


def test_registries_that_do_not_answer_leave_retraction_unchecked(tmp_path: Path,
                                                                  registry: Callable[..., Registry]) -> None:
    paper = _manuscript(tmp_path, "Duncan L, Shen H, Gelaye B, Meijsen J, Ressler K, Feldman M, Peterson R, "
                                  "Domingue B. Analysis of polygenic risk score usage and performance in diverse "
                                  "human populations. Nat Commun. 2019. doi:10.1038/s41467-019-11112-0")
    registry(down=("www.ebi.ac.uk",))
    ref = scan.check_references(paper, online=True, search_unidentified=True).references[0]
    assert (ref.retraction, ref.retraction_source) == ("none_found", "crossref")
    assert any("Europe PMC did not answer" in n for n in ref.lookup_notes)
    registry(down=("api.crossref.org", "doi.org", "www.ebi.ac.uk"))
    report = scan.check_references(paper, online=True, search_unidentified=True)
    ref = report.references[0]
    assert (ref.status, ref.retraction) == ("lookup_failed", "not_checked")
    assert not [f for f in report.findings if f.severity == scan.Severity.blocker]
    assert any("not known to be clean" in f.message for f in report.findings)


def test_a_preprint_found_published_through_the_server_record(tmp_path: Path,
                                                              registry: Callable[..., Registry]) -> None:
    registry(patch={"crossref_pgs_preprint.json": lambda d: d["message"].pop("relation")})
    paper = _manuscript(tmp_path, "Lambert SA, Gil L, Jupp S, et al. The Polygenic Score Catalog: an open database "
                                  "for reproducibility and systematic evaluation. medRxiv. 2020. "
                                  "doi:10.1101/2020.05.20.20108217")
    ref = scan.check_references(paper, online=True, search_unidentified=True).references[0]
    assert ref.is_preprint and ref.published_version.source == "medrxiv:published"
    assert ref.published_version.doi == "10.1038/s41588-021-00783-5"


def test_arxiv_withdrawal_published_version_and_short_surnames(tmp_path: Path,
                                                               registry: Callable[..., Registry]) -> None:
    registry()
    paper = _manuscript(tmp_path,
                        "Thomas A, Ouangraoua A, Varre JS. Tandem halving problems by DCJ. arXiv:1206.6899",
                        "Li H. Exploring single-sample SNP and INDEL calling with whole-genome de novo assembly. "
                        "arXiv:1203.6364")
    report = scan.check_references(paper, online=True, search_unidentified=True)
    refs = _refs_by_doi(report)
    withdrawn, li = refs["1206.6899"], refs["1203.6364"]
    assert (withdrawn.withdrawn, withdrawn.withdrawn_source, withdrawn.status) == (True, "arxiv:comment", "resolved")
    assert withdrawn.author_check == "consistent"  # Varré cited as Varre, Ouangraoua with its diaeresis folded
    assert li.withdrawn is False and li.first_author_found is True and li.status == "resolved"
    assert (li.published_version.doi, li.published_version.venue) == ("10.1093/bioinformatics/bts280", "Bioinformatics")
    lines = {f.line: f for f in report.findings if f.check == "references" and f.line}
    assert lines[withdrawn.line].severity == scan.Severity.major and "withdrawn" in lines[withdrawn.line].message
    assert "has been published" in lines[li.line].message
    assert {r.retraction for r in report.references} == {"not_checked"}
    assert any("not known to be clean" in f.message for f in report.findings)


@pytest.mark.parametrize("comment, withdrawn", [
    ("This paper has been withdrawn by the author", True),
    ("Withdrawn by the authors pending an institutional intellectual property review", True),
    ("v4 replaces v3, which had erroneously been withdrawn", False),
    ("12 pages; studies of opioid withdrawal symptoms", False),
    ("", False),
])
def test_withdrawal_comments(comment: str, withdrawn: bool) -> None:
    assert scan._withdrawn(comment) is withdrawn


@pytest.mark.parametrize("entry", [
    "Ng PC, Henikoff S. SIFT: predicting amino acid changes that affect protein function. Nucleic Acids Res. "
    "2003;31(13):3812-4. doi:10.1093/nar/gkg509",
    "Ng PC, Henikoff S. SIFT: predicting amino acid changes that affect protein function. Nucleic Acids Res. "
    "2003;31(13):3812-4. PMID: 12824425",
])
def test_two_letter_surnames_match_the_record(tmp_path: Path, registry: Callable[..., Registry], entry: str) -> None:
    registry()
    report = scan.check_references(_manuscript(tmp_path, entry), online=True, search_unidentified=True)
    ref = report.references[0]
    assert (ref.status, ref.first_author_found, ref.author_check) == ("resolved", True, "consistent")
    assert not [f for f in report.findings if f.line == ref.line]
    if ref.doi:  # Crossref lists only Ng: a record that stops short is noted, never a finding
        assert any("stop short" in n for n in ref.author_notes)


DUNCAN = ("Analysis of polygenic risk score usage and performance in diverse human populations. Nat Commun. 2019. "
          "doi:10.1038/s41467-019-11112-0")


@pytest.mark.parametrize("authors, check, severity, note", [
    ("Duncan L, Shen H, Gelaye B, Meijsen J, Ressler K, Feldman M, Peterson R, Domingue B.", "consistent", None, None),
    ("Duncan L, Shen H, Gelaye B, et al.", "consistent", None, None),
    ("Duncan, L., Shen, H., & Gelaye, B. et al. (2019).", "consistent", None, None),
    ("L. Duncan, H. Shen, B. Gelaye, J. Meijsen, K. Ressler, M. Feldman, R. Peterson and B. Domingue.",
     "consistent", None, None),
    ("Duncan L, Gelaye B, Meijsen J, et al.", "differs", "minor", "but not in the citation's list: Shen"),
    ("Duncan L, Smith J, Gelaye B, Meijsen J, Ressler K, Feldman M, Peterson R, Domingue B.", "differs", "minor",
     "not on the Crossref record: Smith"),
    ("Duncan K, Shen H, Gelaye B, et al.", "differs", "info", "Initials differ for Duncan"),
    ("Duncan L, Shen H.", "differs", "info", "2 of the record's 8 authors without 'et al.'"),
])
def test_author_lists_beyond_the_first_author(tmp_path: Path, registry: Callable[..., Registry], authors: str,
                                              check: str, severity: Optional[str], note: Optional[str]) -> None:
    registry()
    report = scan.check_references(_manuscript(tmp_path, f"{authors} {DUNCAN}"), online=True, search_unidentified=True)
    ref = report.references[0]
    assert ref.status == "resolved" and ref.author_check == check
    found = [f for f in report.findings if f.line == ref.line]
    if note is None:
        assert not found
    else:
        assert any(note in n for n in ref.author_notes), ref.author_notes
        assert [f.severity.value for f in found] == [severity]
        assert "not evidence of fabrication" in found[0].suggestion


def test_a_data_citation_resolves_through_datacite(tmp_path: Path, registry: Callable[..., Registry]) -> None:
    registry()
    report = scan.check_references(_manuscript(
        tmp_path, "Badalova F, Mayr P. Manual Reference Verification Dataset for Hallucinated and Suspicious Citation "
                  "Detection Tools. Zenodo. 2026. doi:10.5281/zenodo.21457492"), online=True, search_unidentified=True)
    ref = report.references[0]
    assert (ref.status, ref.retraction, ref.author_check, ref.first_author_found) == (
        "resolved", "not_checked", "consistent", True)
    assert any(str(ref.line) in f.message for f in report.findings if "not known to be clean" in f.message)


def test_an_unknown_identifier_is_unresolved_and_a_wrong_one_is_a_mismatch(tmp_path: Path,
                                                                            registry: Callable[..., Registry]) -> None:
    registry()
    report = scan.check_references(_manuscript(
        tmp_path, "Doe J. An invented study of everything. J Imag. 2024. doi:10.9999/invented.1",
        "Doe J. A different title entirely about something else. Nat Commun. 2019. doi:10.1038/s41467-019-11112-0"),
        online=True, search_unidentified=True)
    invented, wrong = report.references
    assert invented.status == "unresolved" and wrong.status == "mismatch"
    assert [f.severity.value for f in report.findings if f.line == invented.line] == ["blocker"]


def test_reference_json_keeps_every_earlier_field() -> None:
    earlier = {"line", "text", "doi", "pmid", "arxiv", "resolved_title", "resolved_year", "resolved_first_author",
               "first_author_found", "title_similarity", "status"}
    added = {"retraction", "retraction_source", "retraction_notice", "is_preprint", "published_version", "withdrawn",
             "withdrawn_source", "resolved_authors", "author_check", "author_notes", "author_severity", "lookup_notes"}
    from_cite_check = {"url", "other_ids", "cited_title", "other_id_checks", "url_status"}
    assert set(scan.Reference(line=1, text="x").model_dump()) == earlier | added | from_cite_check


def test_an_arxiv_paper_whose_title_contains_error_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    feed = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2101.00001v1</id>'
            "<title>Error bounds for deep networks</title><published>2021-01-01T00:00:00Z</published>"
            "<author><name>Ada Lovelace</name></author></entry></feed>")
    errors = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#incorrect_id_format'
              "</id><title>Error</title></entry></feed>")
    pages = {"2101.00001": feed, "bad-id": errors, "2101.99999": '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "export.arxiv.org":
            return httpx.Response(200, text=pages[request.url.params.get("id_list", "")])
        return httpx.Response(404)

    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(scan.time, "sleep", lambda _: None)
    refs = [scan.Reference(line=1, text="Lovelace, A. (2021). Error bounds for deep networks. arXiv.", arxiv=aid)
            for aid in ("2101.00001", "bad-id", "2101.99999")]
    scan.resolve_references(refs, search_unidentified=False)
    assert [r.status for r in refs] == ["resolved", "unresolved", "unresolved"]
    assert refs[0].resolved_title == "Error bounds for deep networks"


BIB = r"""@string{natgen = "Nature Genetics"}
@comment{this is not an entry}
@article(paren2021, author = {Lambert, Samuel A.}, title = "The {Polygenic} Score Catalog", journal = natgen,
  year = 2021, doi = {https://doi.org/10.1038/s41588-021-00783-5}, pmid = {33692568})
@misc{old1999, author = {Witten, E.}, title = {A paper}, eprint = {hep-th/9901001}, eprinttype = {arxiv}}
@misc{linked, author = {Doe, J.}, title = {Linked}, url = {https://arxiv.org/abs/2403.19087v2}}
@misc{site, author = {Doe, J.}, title = {A site}, url = {https://example.org/tool\_page}}
@article{broken, title = {No closing brace}
@article{after, title = {Never read}}
"""


def test_bibtex_reader_takes_macros_parentheses_and_every_identifier(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    errors: list[tuple[int, str]] = []
    refs = dict(scan._bib_references(bib, errors))
    assert list(refs) == ["paren2021", "old1999", "linked", "site"]
    paren = refs["paren2021"]
    assert (paren.doi, paren.pmid, paren.cited_title) == ("10.1038/s41588-021-00783-5", "33692568",
                                                         "The Polygenic Score Catalog")
    assert "Nature Genetics" in paren.text
    assert refs["old1999"].arxiv == "hep-th/9901001" and refs["linked"].arxiv == "2403.19087"
    assert refs["site"].url == "https://example.org/tool_page" and refs["site"].doi is None
    assert errors and errors[0][0] == BIB.splitlines().index("@article{broken, title = {No closing brace}") + 1


def test_a_bibtex_entry_that_does_not_parse_is_a_finding_not_a_silent_drop(tmp_path: Path) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text(BIB, encoding="utf-8")
    report = scan.check_references(bib, online=False, search_unidentified=False)
    malformed = [f for f in report.findings if "does not parse" in f.message]
    assert len(malformed) == 1 and malformed[0].severity == scan.Severity.major and malformed[0].section == "refs.bib"


@pytest.mark.parametrize("text, expected", [
    ("PMID: 123", "123"), ("PMID 33692568", "33692568"), ("arXiv:hep-th/9901001v2", "hep-th/9901001"),
    ("arXiv:2101.00001", "2101.00001"), ("https://arxiv.org/abs/2101.00001", "2101.00001")])
def test_short_pmids_and_old_arxiv_ids_are_read(text: str, expected: str) -> None:
    pmid, arxiv = scan.PMID_RE.search(text), scan._arxiv_id(scan.ARXIV_RE.search(text))
    assert (pmid.group(1) if pmid else arxiv) == expected


class Wire:
    """A MockTransport for the cite-check merge: doi.org CSL records, PubMed, arXiv and web pages; every request
    recorded."""

    CSL = {"10.9999/medra.1": {"title": "Deep <i>Learning</i> for Müller–Škoda Graphs", "issued": {"date-parts": [[2020]]},
                               "author": [{"family": "Müller", "given": "Ana"}]},
           "10.9999/norecord": None}
    PUBMED = {"111": "Deep learning for Müller–Škoda graphs.", "222": "Something else entirely about mice."}

    def __init__(self) -> None:
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        url = request.url
        if url.host in ("api.crossref.org", "api.datacite.org", "www.ebi.ac.uk"):
            return httpx.Response(404)
        if url.host == "doi.org":
            doi = urllib.parse.unquote(url.path[1:])
            if doi not in self.CSL:
                return httpx.Response(404)
            rec = self.CSL[doi]
            return httpx.Response(406) if rec is None else httpx.Response(200, json=rec)
        if url.host == "eutils.ncbi.nlm.nih.gov":
            pmid = url.params.get("id", "")
            if not pmid.isdigit():
                return httpx.Response(400)
            doc = {"uid": pmid, "title": self.PUBMED[pmid]} if pmid in self.PUBMED else {"error": "cannot get"}
            return httpx.Response(200, json={"result": {"uids": [pmid], pmid: doc}})
        if url.host == "example.org":
            pages = {"/page": 200, "/nohead": 200, "/gone": 404, "/private": 403, "/broken": 503}
            if url.path == "/nohead" and request.method == "HEAD":
                return httpx.Response(405)
            return httpx.Response(pages.get(url.path, 404))
        return httpx.Response(404)


@pytest.fixture()
def wire(monkeypatch: pytest.MonkeyPatch) -> Wire:
    handler = Wire()
    original = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(scan.time, "sleep", lambda _: None)
    return handler


def _resolved(**kw: object) -> "scan.Reference":
    ref = scan.Reference(line=1, text=str(kw.pop("text", "Müller, A. (2020). Deep learning for Müller–Škoda graphs.")),
                         **kw)  # type: ignore[arg-type]
    scan.resolve_references([ref], search_unidentified=False)
    return ref


def test_a_doi_of_another_agency_gets_its_title_from_doi_org(wire: Wire) -> None:
    ref = _resolved(doi="10.9999/medra.1")
    assert ref.status == "resolved" and ref.resolved_title == "Deep Learning for Müller–Škoda Graphs"
    assert ref.resolved_authors == ["Müller, Ana"]
    asked = [r for r in wire.seen if r.url.host == "doi.org"]
    assert asked[0].headers["accept"] == scan.CSL and asked[0].method == "GET"
    assert _resolved(doi="10.9999/norecord").status == "lookup_failed"  # 406: the agency gives no record
    assert _resolved(doi="10.9999/nothing").status == "unresolved"


def test_each_identifier_is_asked_once_per_run_and_pubmed_names_the_tool(wire: Wire) -> None:
    refs = [scan.Reference(line=n, text="Deep learning for Müller–Škoda graphs", pmid="111") for n in (1, 2, 3)]
    scan.resolve_references(refs, search_unidentified=False)
    pubmed = [r for r in wire.seen if r.url.host == "eutils.ncbi.nlm.nih.gov"]
    assert len(pubmed) == 1 and pubmed[0].url.params["tool"] == "manuscript-skills"
    assert "email" not in str(pubmed[0].url) and "mailto" not in str(pubmed[0].url)


def test_every_identifier_of_an_entry_is_followed(wire: Wire) -> None:
    ref = _resolved(doi="10.9999/medra.1", other_ids=["pmid:111", "pmid:222", "pmid:99999999", "pmid:abc"])
    states = [(c["id"], c["state"], c["same_work"]) for c in ref.other_id_checks]
    assert states == [("pmid:111", "ok", "true"), ("pmid:222", "ok", "false"), ("pmid:99999999", "dead", None),
                      ("pmid:abc", "dead", None)]
    messages = [f.message for f in scan._reference_findings([ref], online=True)]
    assert any("point to different works: pmid 222" in m for m in messages)
    assert sum("does not resolve" in m for m in messages) == 2


@pytest.mark.parametrize("path, severity, words", [
    ("/page", None, ""), ("/nohead", None, ""), ("/gone", scan.Severity.major, "does not answer (HTTP 404)"),
    ("/private", scan.Severity.info, "refuses automated access"), ("/broken", scan.Severity.info, "could not be checked")])
def test_a_url_field_is_checked_by_its_status(wire: Wire, path: str, severity: object, words: str) -> None:
    ref = _resolved(doi="10.9999/medra.1", url=f"https://example.org{path}")
    found = [f for f in scan._reference_findings([ref], online=True) if "url" in f.message]
    assert ([(f.severity, words in f.message) for f in found] == [(severity, True)]) if severity else not found
