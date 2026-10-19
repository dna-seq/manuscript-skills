"""Score a benchmark run. The command line is `scripts/bench_score.py`.

Deterministic: same inputs, same bytes out. Wraps `compare_modules`'
`_compare` rather than re-deriving a diff, so the score can never drift from
what the shipped tool says — a hand-rolled comparison is a second opinion
nobody asked for and it disagrees eventually.

**Engine, not a tool surface.** Nothing here is registered with the MCP server, so
its models live in this module rather than in `models.py` — the rule there is that
every *tool* returns a model from `models.py`, and `overrides.py` is the precedent
for a pydantic model at engine level. If a `bench_score` tool is ever added, its
return type moves to `models.py` and these become its inputs.

**Three modes, in rank order, because three questions are being asked.**
`--fixture` is the **primary** one and is the manuscript's own protocol: did this
run recover the adjudicated answer — the right rows, the right directions. The
default mode is **secondary** and needs no adjudication: run-to-run agreement,
which is
reference-relative and answers *did this run reproduce that one*. The census is
reference-free and answers *what does this run assert* — which is the only form
available to a paper that will never have a reference, and it is the shape the
corrected benchmark criterion needs: a source running no association test should
produce rows asserting no direction, and zero rows and sixty honest rows are both
passes. The census **reports and does not judge**: the expectation for a given
paper is a sentence in the round's results, never a threshold in here.

**Either mode locates the spec directory.** Benchmark runs put `module_spec.yaml`
at the run root, under `spec/`, or under `longevity_*/`, and all three satisfy the
ask that produced them. A script assuming one shape silently scores nothing, so a
path with no `module_spec.yaml` is searched beneath, and zero or several matches
is an error naming what it found rather than a guess.

Prints JSON to stdout. Two properties matter and both are deliberate:

- **Volatile columns are excluded by name, and the exclusions are printed**
  in the output rather than applied silently. `fetched_at` moves on every run
  by construction and `curator` names who did the work, so neither is evidence
  about agreement; anything else that gets excluded has to be argued for here.
- **Key agreement and cell agreement are reported separately.** A run that
  authors the right variants with the wrong values, and one that authors half
  the variants perfectly, are different failures, and one score cannot say
  which happened.

`unscored` is not a zero. A table nothing could be counted over is reported as
absent, never folded into the denominator as a miss — the same rule the tools
apply to a check that could not run. **Two different tables land there and only
one was handled**: a table present on one side, and an *unkeyed* one present on
both, whose rows cannot be paired because upstream's `hints.key_fields` gives it
the `overlap` rule rather than `equality`. The second raised `TypeError` on the
first binning module it met, because the filter asked about `presence` when the
question is whether anything was counted.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Protocol

from just_dna_compiler import draft, hints
from pydantic import BaseModel, Field

from just_module_creator import compare
from just_module_creator.tools.comparison import _compare

#: Columns whose disagreement is not evidence about the run. `fetched_at` is a
#: wall-clock stamp; `curator` is the identity of whoever authored the row,
#: which differs between two runs by definition and says nothing about whether
#: they agreed on the genetics.
VOLATILE = ("fetched_at", "curator")

#: Columns the census counts. Every one is a cell that asserts something a source
#: must have *measured* — a direction, a significance verdict, an effect, a
#: clinical call, a weight — as against a cell that records what a source *says*.
#: This is a benchmark judgement about which claims are worth watching, not a
#: schema fact: the tables are read by header, so a column that does not exist in
#: a given CSV is simply absent from that CSV's census rather than reported as
#: empty.
ASSERTION_COLUMNS = (
    "direction",
    "stat_significance",
    "clin_sig",
    "effect_size",
    "p_value",
    "weight",
)

#: What an empty cell and the literal `unknown` have in common is that neither
#: asserts anything, and what separates them is whether the author said so. Both
#: are counted, and they are counted apart.
_WITHHELD = ("", "unknown")


class Unscored(BaseModel):
    """One question this report did not answer, and why. Never a silent zero."""

    subject: str = Field(description="What could not be scored — `variants.csv:stat_significance`.")
    reason: str = Field(description="Why the question could not be put.")


class ColumnCensus(BaseModel):
    """One watched column in one table: what it asserts and what it withholds."""

    column: str
    values: dict[str, int] = Field(
        description="Every value and its count, key-sorted. Emitted from a sorted "
        "dict rather than set iteration, because the payload is compared."
    )
    asserted: int = Field(description="Rows carrying a value that claims something.")
    withheld_blank: int = Field(description="Rows with an empty cell.")
    withheld_unknown: int = Field(
        description="Rows carrying the literal `unknown`. Counted APART from blank: "
        "both withhold, and only one of them says so on purpose."
    )
    off_vocabulary: list[str] = Field(
        default_factory=list,
        description="Values outside the column's closed vocabulary, sorted. Not "
        "counted as asserted — a cell nothing recognises claims nothing. The "
        "vocabulary is upstream's `hints.field_vocabularies`, never a list here.",
    )


class TableCensus(BaseModel):
    """One authored table, and the three ways a watched column can be absent."""

    csv: str
    rows: int
    columns: list[ColumnCensus] = Field(
        description="Watched columns this CSV actually carries, sorted by name."
    )
    columns_not_carried: list[str] = Field(
        default_factory=list,
        description="Watched columns the table's model HAS and this file's header "
        "does not. A missing column is not a file full of withheld cells — nothing "
        "was asserted and nothing was withheld, because the question was never put.",
    )
    columns_absent_from_table_kind: list[str] = Field(
        default_factory=list,
        description="Watched columns that are not fields of this table's model at "
        "all. Different from the above: not an authoring choice, a category error.",
    )


class Census(BaseModel):
    """What a run asserts, with no reference. Reports; does not judge."""

    run: str
    tables: list[TableCensus]
    note: str = Field(
        default=(
            "Reports and does not judge. The expectation for a given paper is a "
            "sentence in the round's results, never a threshold in here: a source "
            "running no association test should produce rows asserting no "
            "direction, and zero rows and sixty honest rows are both passes."
        )
    )


class BenchFixtureError(Exception):
    """A fixture that cannot be trusted to score anything. Raised at load, never later."""


class BenchFixture(BaseModel):
    """A prompt, an expected answer, and the provenance of how it became one.

    **The expected answer is a directory, never a pair of loose CSVs.** A bare
    `expected_variants.csv` has no `module_spec.yaml`, so no `defaults:` block to
    fold and no `genome_build` — which makes every comparison against it
    not-comparable and disagrees with `content_signature` on rows nobody changed.
    So `expected_spec` points at a real spec directory and the rows are read
    through `compare.authored_tables`, the same loader the comparison uses.
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    path: Path = Field(description="The fixture directory, holding metadata.json and prompt.txt.")
    trait: str
    reference: Path | None = Field(
        description="The adjudicated spec directory, or None where no reference exists yet. "
        "None is honest rather than empty: two of this corpus's three papers have no "
        "adjudicated answer, and claiming otherwise is what the decoys exist to prevent."
    )
    scored_tables: list[str]
    expected_keys: dict[str, set[tuple]] = Field(
        default_factory=dict,
        description="Natural keys per table, from upstream's `draft.natural_key`. The "
        "manuscript's '(rsID, genotype) pair' IS that key — it is never spelled out here.",
    )
    expected_rows: dict[str, dict[tuple, BaseModel]] = Field(
        default_factory=dict,
        description="The expected rows themselves, keyed, so a metric can compare a cell "
        "rather than only a key.",
    )
    tier_of: dict[str, str] = Field(
        default_factory=dict, description="rsID -> tier name, for the weighted recall."
    )
    tier_weights: dict[str, float] = Field(default_factory=dict)
    untiered_rsids: list[str] = Field(
        default_factory=list,
        description="Expected rsIDs no tier names. Not an error — they weigh 1.0 — but "
        "counted, because forcing a tier on every row would make adding a variant to the "
        "reference break the fixture.",
    )
    decoys: list[str] = Field(
        default_factory=list,
        description="Real rsIDs an expert asserts do NOT belong. This is the only sound "
        "false-positive signal: a fixture is one curation, not the set of all correct rows.",
    )
    thresholds: dict[str, float] = Field(default_factory=dict)
    prompt: str = ""
    provenance: dict = Field(default_factory=dict)


def load_fixture(path: Path) -> BenchFixture:
    """Read a fixture and refuse it loudly if it cannot be trusted.

    Every refusal below is a way a fixture scores something other than what it
    claims to, and each one is silent if it is not checked here:

    * a tier naming an rsID the reference lacks inflates the weighted denominator;
    * a decoy that is also expected makes `decoy_rate` and recall contradict;
    * overlapping tiers give one rsID two weights;
    * a `scored_tables` entry whose key rule is not `equality` cannot be paired at
      all, so it would report `None` that nobody reads as a refusal;
    * an absolute `expected_spec` is a fixture that does not travel to another
      machine, which is the whole reason the corpus was committed.
    """
    meta_path = path / "metadata.json"
    if not meta_path.is_file():
        raise BenchFixtureError(f"no metadata.json in {path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    raw_spec = meta.get("expected_spec")
    reference: Path | None = None
    if raw_spec is not None:
        if Path(raw_spec).is_absolute():
            raise BenchFixtureError(
                f"{meta_path}: expected_spec must be relative to the fixture, got {raw_spec!r}"
            )
        reference = (path / str(raw_spec)).resolve()
        if not (reference / "module_spec.yaml").is_file():
            raise BenchFixtureError(f"{meta_path}: no module_spec.yaml at {reference}")

    scored_tables = list(meta.get("scored_tables") or [])
    for name in scored_tables:
        # `None` where upstream has no key for the name at all — a table we cannot
        # pair for a different reason, and refused with a different sentence rather
        # than folded into the overlap case.
        key = hints.key_fields(name)
        if key is None:
            raise BenchFixtureError(
                f"{meta_path}: {name} has no natural key upstream, so its rows cannot be "
                "paired and it cannot be a scored table."
            )
        if key.rule != "equality":
            raise BenchFixtureError(
                f"{meta_path}: {name} is keyed on the {key.rule!r} rule, so its rows cannot be "
                "paired one to one and it cannot be a scored table."
            )

    expected_keys: dict[str, set[tuple]] = {}
    expected_rows: dict[str, dict[tuple, BaseModel]] = {}
    expected_rsids: set[str] = set()
    if reference is not None:
        loaded = compare.authored_tables(reference)
        for name in scored_tables:
            table = loaded.get(name)
            if table is None or not table.readable:
                raise BenchFixtureError(
                    f"{meta_path}: {name} is missing or unreadable in {reference}"
                )
            keyed = {
                key: row for row in table.rows if (key := draft.natural_key(row)) is not None
            }
            expected_keys[name] = set(keyed)
            expected_rows[name] = keyed
            expected_rsids |= {
                rsid for row in table.rows if (rsid := getattr(row, "rsid", None))
            }

    tier_of: dict[str, str] = {}
    tier_weights: dict[str, float] = {}
    for tier, body in sorted((meta.get("variant_tiers") or {}).items()):
        tier_weights[tier] = float(body.get("weight", 1.0))
        for rsid in body.get("rsids") or []:
            if rsid in tier_of:
                raise BenchFixtureError(
                    f"{meta_path}: {rsid} is in both {tier_of[rsid]!r} and {tier!r}, so it has "
                    "two weights."
                )
            if reference is not None and rsid not in expected_rsids:
                raise BenchFixtureError(
                    f"{meta_path}: tier {tier!r} names {rsid}, which the reference does not "
                    "carry — a tier over a row that is not expected inflates the denominator."
                )
            tier_of[rsid] = tier

    decoys = sorted((meta.get("decoy_variants") or {}).get("rsids") or [])
    overlap = sorted(set(decoys) & expected_rsids)
    if overlap:
        raise BenchFixtureError(
            f"{meta_path}: {', '.join(overlap)} is both expected and a decoy, so recall and "
            "decoy_rate would contradict each other."
        )

    prompt_path = path / "prompt.txt"
    return BenchFixture(
        name=meta.get("name") or path.name,
        path=path,
        trait=meta.get("trait", ""),
        reference=reference,
        scored_tables=scored_tables,
        expected_keys=expected_keys,
        expected_rows=expected_rows,
        tier_of=tier_of,
        tier_weights=tier_weights,
        untiered_rsids=sorted(expected_rsids - set(tier_of)),
        decoys=decoys,
        thresholds=dict((meta.get("scoring") or {}).get("minimum_acceptable") or {}),
        prompt=prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else "",
        provenance=meta.get("provenance") or {},
    )


def locate_spec(path: Path) -> Path:
    """The directory holding `module_spec.yaml`, at or beneath `path`."""
    if (path / "module_spec.yaml").is_file():
        return path
    found = sorted(p.parent for p in path.rglob("module_spec.yaml"))
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit(f"no module_spec.yaml at or beneath {path}")
    listed = ", ".join(str(f) for f in found)
    raise SystemExit(f"several spec directories beneath {path}: {listed}")


class TierBreakdown(BaseModel):
    """One evidence tier's own recall, so a weighted number can be read back apart."""

    tier: str
    weight: float
    expected_pairs: int
    recovered_pairs: int
    recall: float | None = Field(
        description="None where the tier expects nothing — an empty denominator, never a zero."
    )


class VariantRecovery(BaseModel):
    """Did the run author the rows the reference has, and none it asserts do not belong.

    **`pair_recall` and `rsid_recall` are two numbers on purpose.** A run that finds
    the right variant and gets its genotypes wrong, and one that finds half the
    variants perfectly, are different failures — the gap between the two numbers is
    that signal, and a single score with partial credit destroys it.

    **`decoy_rate` is the sound false-positive number, not `precision_over_fixture`.**
    A fixture is one expert's curation of one trait, not the set of all correct rows,
    so a variant the reference does not carry is usually just a variant the reference
    does not carry. A decoy is different: an rsID an expert asserted does *not* belong.
    """

    csv: str
    expected_pairs: int
    generated_pairs: int
    recovered_pairs: int
    missing_pairs: list[str] = Field(
        description="Which keys were missed, sorted — not how many. Tier weighting "
        "needs the identities, which is why this axis does not wrap `_compare`."
    )
    missing_rsids: list[str]
    extra_pairs: list[str] = Field(
        description="Authored, not expected, not a decoy. Reported and NOT scored as "
        "wrong: the fixture is one curation, not the set of all correct rows."
    )
    decoys_present: list[str]
    pair_recall: float | None
    rsid_recall: float | None
    precision_over_fixture: float | None = Field(
        description="Named for its denominator. It is agreement with one curation, "
        "not correctness."
    )
    f1_over_fixture: float | None
    weighted_recall: float | None = Field(
        description="Tier weight of what was recovered over tier weight of what was "
        "expected. Untiered rows weigh 1.0."
    )
    decoy_rate: float | None
    tiers: list[TierBreakdown]
    unscored: list[Unscored] = Field(default_factory=list)


class DirectionAgreement(BaseModel):
    """Sign agreement on the rows where BOTH sides asserted one.

    A withheld row leaves the denominator rather than counting against either side.
    The four tallies are what make that visible: a run writing `unknown` everywhere
    scores `agreement: None` with every reference assertion sitting in
    `reference_asserted_run_withheld`, which reads as nothing rather than as perfect.
    """

    column: str
    pairs_compared: int
    both_asserted: int
    agreeing: int
    disagreeing: int
    reference_asserted_run_withheld: int
    run_asserted_reference_withheld: int
    both_withheld: int
    agreement: float | None
    disagreements: list[str]
    unscored: list[Unscored] = Field(default_factory=list)


class WeightSignAgreement(BaseModel):
    """Sign only. Magnitude is reported and is never a pass or a fail.

    A module weight is an authored choice rather than a GWAS beta copied across, so
    the size of it is a judgement and only its direction is checkable. `0.0` is its
    own sign and is never folded into blank.
    """

    pairs_compared: int
    both_present: int
    agreeing_sign: int
    disagreeing_sign: int
    reference_present_run_blank: int
    run_present_reference_blank: int
    both_blank: int
    sign_agreement: float | None
    mean_absolute_error: float | None
    unscored: list[Unscored] = Field(default_factory=list)


def _sign(value) -> int | None:
    return None if value is None else (0 if value == 0 else (1 if value > 0 else -1))


def _pair(key: tuple) -> str:
    return ":".join(str(part) for part in key)


def _asserted(value) -> bool:
    """A cell claims something when it is neither blank nor the withheld token."""
    return value is not None and str(value).strip() not in _WITHHELD


def _column_census(column: str, rows: list[dict], vocabulary: dict | None) -> ColumnCensus:
    """One column's tally. Read from raw bytes, checked against the live schema.

    The values are what the author wrote, including one the model would reject —
    which is the point, and is why `off_vocabulary` exists rather than the value
    being silently counted as an assertion.
    """
    values = Counter((r.get(column) or "").strip() for r in rows)
    options = set(vocabulary["options"]) if vocabulary and vocabulary.get("closed") else None
    off = sorted(
        v for v in values if v and v not in _WITHHELD and options is not None and v not in options
    )
    return ColumnCensus(
        column=column,
        values=dict(sorted(values.items())),
        asserted=sum(n for v, n in values.items() if v not in _WITHHELD and v not in off),
        withheld_blank=values.get("", 0),
        withheld_unknown=values.get("unknown", 0),
        off_vocabulary=off,
    )


def census(run: Path) -> Census:
    """Count what a run's authored CSVs assert. Reference-free, report-only.

    Machine-written sidecars are skipped, because the question is what the *run*
    asserted and a fact pass's `p_value` is the source's claim rather than the
    author's. The roster is upstream's own `hints.DERIVED_TABLE_MODELS`, never a
    list here: a sidecar we did not know about would otherwise be counted as
    authored, which is the reading the census exists to avoid — and it is what
    absorbs a new sidecar (0.7 adds PubMind's) without an edit.

    **A watched column can be absent in two different ways and they are reported
    apart**, because collapsing them is the shape this whole file exists to avoid.
    `assets/fto_bmi/variants.csv` carries no `stat_significance`, while
    `stat_significance` *is* a field of `VariantRow` — so the author did not carry
    it, which is a choice. A column that is not a field of the table's model at all
    is a category error instead. Neither is a file full of withheld cells: nothing
    was asserted and nothing was withheld, because the question was never put.
    """
    derived = set(hints.DERIVED_TABLE_MODELS)
    tables: list[TableCensus] = []
    for path in sorted(run.glob("*.csv")):
        if path.name in derived:
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        header = set(rows[0]) if rows else set()

        model = draft.DRAFTABLE.get(path.name)
        # `None` is not `set()`: a table kind we cannot resolve tells us nothing
        # about which columns it could have carried, so nothing is claimed about it.
        fields = set(hints.authored_field_names(model)) if model is not None else None
        vocabularies = hints.field_vocabularies(model) if model is not None else {}

        present = [c for c in ASSERTION_COLUMNS if c in header]
        not_carried = sorted(
            c for c in ASSERTION_COLUMNS
            if c not in header and (fields is None or c in fields)
        )
        wrong_kind = sorted(
            c for c in ASSERTION_COLUMNS
            if c not in header and fields is not None and c not in fields
        )
        if not present and not not_carried and not wrong_kind:
            continue
        tables.append(
            TableCensus(
                csv=path.name,
                rows=len(rows),
                columns=[_column_census(c, rows, vocabularies.get(c)) for c in sorted(present)],
                columns_not_carried=not_carried,
                columns_absent_from_table_kind=wrong_kind,
            )
        )
    return Census(run=str(run), tables=tables)


def score_variant_recovery(
    fixture: BenchFixture, run_rows: dict[tuple, BaseModel]
) -> VariantRecovery:
    """Set arithmetic over natural keys, plus the tier weights. See `VariantRecovery`."""
    csv_name = "variants.csv"
    expected = fixture.expected_keys.get(csv_name, set())
    generated = set(run_rows)
    recovered = expected & generated

    def rsids(keys) -> set[str]:
        return {str(k[0]) for k in keys if k}

    expected_rsids, generated_rsids = rsids(expected), rsids(generated)
    decoys_present = sorted(set(fixture.decoys) & generated_rsids)
    extra = sorted(
        _pair(k) for k in generated - expected if str(k[0]) not in set(fixture.decoys)
    )

    def weight_of(key) -> float:
        return fixture.tier_weights.get(fixture.tier_of.get(str(key[0]), ""), 1.0)

    expected_weight = sum(weight_of(k) for k in expected)
    tiers = []
    for tier, weight in sorted(fixture.tier_weights.items()):
        in_tier = {k for k in expected if fixture.tier_of.get(str(k[0])) == tier}
        hit = len(in_tier & generated)
        tiers.append(
            TierBreakdown(
                tier=tier,
                weight=weight,
                expected_pairs=len(in_tier),
                recovered_pairs=hit,
                recall=round(hit / len(in_tier), 4) if in_tier else None,
            )
        )

    unscored: list[Unscored] = []
    if not expected:
        unscored.append(
            Unscored(
                subject=f"{csv_name}:recovery",
                reason="the fixture has no adjudicated reference, so there is nothing to recover",
            )
        )
    return VariantRecovery(
        csv=csv_name,
        expected_pairs=len(expected),
        generated_pairs=len(generated),
        recovered_pairs=len(recovered),
        missing_pairs=sorted(_pair(k) for k in expected - generated),
        missing_rsids=sorted(expected_rsids - generated_rsids),
        extra_pairs=extra,
        decoys_present=decoys_present,
        pair_recall=round(len(recovered) / len(expected), 4) if expected else None,
        rsid_recall=(
            round(len(expected_rsids & generated_rsids) / len(expected_rsids), 4)
            if expected_rsids
            else None
        ),
        precision_over_fixture=(
            round(len(recovered) / len(generated), 4) if generated else None
        ),
        f1_over_fixture=(
            round(2 * len(recovered) / (len(expected) + len(generated)), 4)
            if expected and generated
            else None
        ),
        weighted_recall=(
            round(sum(weight_of(k) for k in recovered) / expected_weight, 4)
            if expected_weight
            else None
        ),
        decoy_rate=(
            round(len(decoys_present) / len(fixture.decoys), 4) if fixture.decoys else None
        ),
        tiers=tiers,
        unscored=unscored,
    )


def score_direction(
    fixture: BenchFixture, run_rows: dict[tuple, BaseModel], column: str = "direction"
) -> DirectionAgreement:
    """Agreement over the rows both sides asserted. See `DirectionAgreement`."""
    expected = fixture.expected_rows.get("variants.csv", {})
    shared = sorted(set(expected) & set(run_rows))
    unscored: list[Unscored] = []
    if shared and not any(hasattr(expected[k], column) for k in shared):
        unscored.append(
            Unscored(
                subject=f"variants.csv:{column}",
                reason=f"{column} is not a field of this table's model, so nothing was asked",
            )
        )

    both = agree = disagree = ref_only = run_only = neither = 0
    disagreements: list[str] = []
    for key in shared:
        left, right = getattr(expected[key], column, None), getattr(run_rows[key], column, None)
        left_says, right_says = _asserted(left), _asserted(right)
        if left_says and right_says:
            both += 1
            if str(left).strip() == str(right).strip():
                agree += 1
            else:
                disagree += 1
                disagreements.append(f"{_pair(key)} reference={left} run={right}")
        elif left_says:
            ref_only += 1
        elif right_says:
            run_only += 1
        else:
            neither += 1

    return DirectionAgreement(
        column=column,
        pairs_compared=len(shared),
        both_asserted=both,
        agreeing=agree,
        disagreeing=disagree,
        reference_asserted_run_withheld=ref_only,
        run_asserted_reference_withheld=run_only,
        both_withheld=neither,
        agreement=round(agree / both, 4) if both else None,
        disagreements=sorted(disagreements),
        unscored=unscored,
    )


def score_weight_sign(
    fixture: BenchFixture, run_rows: dict[tuple, BaseModel]
) -> WeightSignAgreement:
    """Sign agreement, with the magnitude reported beside it and never gating.

    `0.0` is a real weight and its own sign — an explicit zero says *this genotype
    carries no effect*, which is a claim, where a blank says nobody decided.
    """
    expected = fixture.expected_rows.get("variants.csv", {})
    shared = sorted(set(expected) & set(run_rows))

    both = agree = disagree = ref_only = run_only = neither = 0
    errors: list[float] = []
    for key in shared:
        left = getattr(expected[key], "weight", None)
        right = getattr(run_rows[key], "weight", None)
        if left is not None and right is not None:
            both += 1
            errors.append(abs(float(left) - float(right)))
            if _sign(left) == _sign(right):
                agree += 1
            else:
                disagree += 1
        elif left is not None:
            ref_only += 1
        elif right is not None:
            run_only += 1
        else:
            neither += 1

    return WeightSignAgreement(
        pairs_compared=len(shared),
        both_present=both,
        agreeing_sign=agree,
        disagreeing_sign=disagree,
        reference_present_run_blank=ref_only,
        run_present_reference_blank=run_only,
        both_blank=neither,
        sign_agreement=round(agree / both, 4) if both else None,
        mean_absolute_error=round(sum(errors) / len(errors), 4) if errors else None,
    )


class Judgment(BaseModel):
    """One adjudicated cell. `unknown` is a verdict, never a soft `disagree`."""

    verdict: str = Field(description="`agree` | `disagree` | `unknown`.")
    confidence: float | None = None
    rationale: str
    judge: str = Field(
        description="What produced it — a name or a model id. Recorded, never inferred."
    )


class RowJudge(Protocol):
    """The seam an LLM adjudicator would fill. **Nothing implements it.**

    Deterministic scoring answers the questions with a right answer on disk. Three
    do not, and each is a place this seam would take over:

    * `conclusion` — free text, where two correct paraphrases are not string-equal;
    * `direction` on a row the deterministic rule excluded because one side withheld,
      but where a source names a direction the author could have read;
    * a `pmid` the fixture does not carry, where deciding whether the returned title
      names the paper the row's claim is about is a judgement rather than a lookup.

    **A judge never moves a row out of `unscored` into a pass.** Its verdicts would
    ride their own axis and never merge into the deterministic ratio: a model's
    judgement is not the same evidence as a cell match, and one number covering both
    cannot say which happened.
    """

    def judge_cell(
        self, column: str, reference: BaseModel | None, generated: BaseModel | None, key: tuple
    ) -> Judgment: ...


class CitationResolver(Protocol):
    """Answers *does this PMID exist, and what does it name* — Axis 2's network half.

    Two implementations are anticipated and neither is built: a cache reading
    resolutions stored beside the fixture, which is what a hermetic suite would use,
    and a thin adapter over the `lookup_citation` this package already depends on.
    Until one exists, `CitationIdentity.resolver` reports `none` and the verdicts
    that need a lookup stay empty rather than being guessed.
    """

    def resolve(self, pmid: str) -> dict: ...


class CitationIdentity(BaseModel):
    """Which papers a run cited, against which the reference cites.

    **`unrecognised` is not a failure.** A fixture is one curation: `assets/fto_bmi`
    cites one paper, so a run citing three genuinely relevant ones would score 1/3
    under `correct ÷ total`. `recall` is the sound offline number and `accuracy` is
    `None` until a resolver exists.

    **`misidentified` and `hallucinated` are empty offline, and that is honest rather
    than clean.** Sorting a PMID the fixture lacks into *names a different paper* or
    *does not exist* needs a lookup; `null` means UNCHECKED, and calling an unchecked
    id hallucinated is the check-that-could-not-run failure pointing the other way.
    """

    expected_pmids: list[str]
    generated_pmids: list[str]
    correct: list[str]
    missing: list[str]
    unrecognised: list[str] = Field(
        description="Cited by the run, absent from the fixture. Reported, not scored."
    )
    misidentified: list[str] = Field(default_factory=list)
    hallucinated: list[str] = Field(default_factory=list)
    resolver: str = Field(
        description="`none` | `cache` | `network`. An empty `hallucinated` from an "
        "unasked question and one from a real check are different claims."
    )
    accuracy: float | None
    recall: float | None
    unscored: list[Unscored] = Field(default_factory=list)


def score_citations(
    fixture: BenchFixture, run: Path, *, resolver: CitationResolver | None = None
) -> CitationIdentity:
    """Compare cited PMIDs. Offline unless a resolver is supplied; none exists yet."""
    expected = sorted(
        {str(k[1]) for k in fixture.expected_keys.get("studies.csv", set()) if len(k) > 1}
    )
    generated = sorted(
        {
            str(pmid)
            for row in _run_rows(run, "studies.csv").values()
            if (pmid := getattr(row, "pmid", None))
        }
    )
    correct = sorted(set(expected) & set(generated))
    unscored: list[Unscored] = []
    if resolver is None:
        unscored.append(
            Unscored(
                subject="studies.csv:pmid",
                reason="no resolver, so existence and title were not checked — an id absent "
                "from the fixture is unrecognised, never hallucinated",
            )
        )
    if not expected:
        unscored.append(
            Unscored(
                subject="studies.csv:recall",
                reason="the fixture has no adjudicated reference, so there is nothing to recall",
            )
        )
    return CitationIdentity(
        expected_pmids=expected,
        generated_pmids=generated,
        correct=correct,
        missing=sorted(set(expected) - set(generated)),
        unrecognised=sorted(set(generated) - set(expected)),
        resolver="none" if resolver is None else "cache",
        accuracy=None if resolver is None else None,
        recall=round(len(correct) / len(expected), 4) if expected else None,
        unscored=unscored,
    )


class GroundTruthScore(BaseModel):
    """The primary measurement: did this run recover the adjudicated answer.

    `thresholds_met` is `bool | None` per metric and is `None` exactly where the
    metric is — **an unasked question never passes**, which is the same rule the
    tools apply to a check that could not run.
    """

    fixture: str
    reference: str | None
    run: str
    comparable: bool = Field(
        description="False where the two declare different genome builds. The natural key "
        "is build-independent, so 'nothing changed' across two assemblies is the dangerous "
        "answer rather than a reassuring one."
    )
    reference_build: str | None
    run_build: str | None
    variants: VariantRecovery
    citations: CitationIdentity
    direction: DirectionAgreement
    weight_sign: WeightSignAgreement
    thresholds_met: dict[str, bool | None]
    unscored: list[Unscored]
    note: str = Field(
        default=(
            "Scored against one adjudicated curation, not against the set of all "
            "correct rows. Read decoy_rate as the false-positive signal and "
            "precision_over_fixture for what its name says. Free-text conclusions "
            "are not scored here at all."
        )
    )


def _run_rows(run: Path, csv_name: str) -> dict[tuple, BaseModel]:
    """A run's rows, keyed by upstream's own natural key, or empty where unreadable."""
    table = compare.authored_tables(run).get(csv_name)
    if table is None or not table.readable:
        return {}
    return {key: row for row in table.rows if (key := draft.natural_key(row)) is not None}


def score_ground_truth(
    fixture: BenchFixture,
    run: Path,
    *,
    judge: RowJudge | None = None,
    resolver: CitationResolver | None = None,
) -> GroundTruthScore:
    """Score a run against a fixture's adjudicated reference.

    **This axis does not wrap `_compare`, and that is deliberate.** The comparison
    reports `added`/`removed` as counts and truncates its examples, while tier
    weighting needs to know *which* rows were missed. What must never be hand-rolled
    is the notion of what makes two rows the same row, and that is exactly what is
    imported: `compare.authored_tables` for the loading, with its `defaults:` fold,
    and `draft.natural_key` for the identity.

    `judge` is the seam an LLM adjudicator would fill for the cells a string
    comparison cannot score — a free-text `conclusion`, a `direction` both sides
    withheld for different reasons. Nothing implements it, and where it is absent a
    metric it would own reports `None` with a reason rather than a pass.
    """
    run_rows = _run_rows(run, "variants.csv")
    variants = score_variant_recovery(fixture, run_rows)
    citations = score_citations(fixture, run, resolver=resolver)
    direction = score_direction(fixture, run_rows)
    weight_sign = score_weight_sign(fixture, run_rows)

    unscored = (
        list(variants.unscored)
        + list(citations.unscored)
        + list(direction.unscored)
        + list(weight_sign.unscored)
    )
    if judge is None:
        unscored.append(
            Unscored(
                subject="variants.csv:conclusion",
                reason="free text needs a judge and none was supplied; not scored, not passed",
            )
        )

    measured: dict[str, float | None] = {
        "pair_recall": variants.pair_recall,
        "rsid_recall": variants.rsid_recall,
        "decoy_rate": variants.decoy_rate,
        "citation_recall": citations.recall,
        "citation_accuracy": citations.accuracy,
        "direction_agreement": direction.agreement,
        "weight_sign_agreement": weight_sign.sign_agreement,
    }
    thresholds_met: dict[str, bool | None] = {}
    for metric, floor in sorted(fixture.thresholds.items()):
        value = measured.get(metric)
        if value is None:
            thresholds_met[metric] = None
            unscored.append(
                Unscored(
                    subject=f"threshold:{metric}",
                    reason="the metric could not be computed, so the threshold was not tested",
                )
            )
        else:
            # `decoy_rate` is the one metric where the floor is a ceiling: a decoy
            # is an rsID an expert said does not belong, so fewer is better.
            thresholds_met[metric] = value <= floor if metric == "decoy_rate" else value >= floor

    # Upstream's own reader, so a spec whose YAML will not parse reports `None`
    # rather than raising here — unknown, not a mismatch.
    reference_build = (
        compare.read_build(fixture.reference)[0] if fixture.reference else None
    )
    run_build = compare.read_build(run)[0]
    return GroundTruthScore(
        fixture=fixture.name,
        reference=str(fixture.reference) if fixture.reference else None,
        run=str(run),
        comparable=reference_build is not None and reference_build == run_build,
        reference_build=reference_build,
        run_build=run_build,
        variants=variants,
        citations=citations,
        direction=direction,
        weight_sign=weight_sign,
        thresholds_met=thresholds_met,
        unscored=sorted(unscored, key=lambda u: (u.subject, u.reason)),
    )


def _score_table(table) -> dict:
    if table.unchanged is None:
        # One-sided, or otherwise uncounted upstream. Every count is `None` here
        # rather than `0`: the table was not compared, and a zero would read as a
        # comparison that found nothing.
        return {
            "csv": table.csv,
            "presence": table.presence,
            "rows_reference": table.rows_left,
            "rows_run": table.rows_right,
            "keys_shared": None,
            "keys_only_reference": table.removed,
            "keys_only_run": table.added,
            "key_jaccard": None,
            "rows_changed_any_column": None,
            "rows_changed_after_volatile_exclusions": None,
            "cell_agreement_over_shared_keys": None,
            "changed_groups": [],
        }
    # `changed` is a list of GROUPS, not rows — a row belongs to exactly one
    # group, so the shared-key count sums each group's rows. Counting groups
    # here made agreement exceed 1 and go negative on the first real input.
    changed_rows = sum(g.rows for g in table.changed)
    shared = table.unchanged + changed_rows
    union = shared + table.added + table.removed
    substantive = [
        {"columns": sorted(set(g.columns) - set(VOLATILE)), "rows": g.rows}
        for g in table.changed
        if set(g.columns) - set(VOLATILE)
    ]
    substantive_rows = sum(g["rows"] for g in substantive)
    return {
        "csv": table.csv,
        "presence": table.presence,
        "rows_reference": table.rows_left,
        "rows_run": table.rows_right,
        "keys_shared": shared,
        "keys_only_reference": table.removed,
        "keys_only_run": table.added,
        "key_jaccard": round(shared / union, 4) if union else None,
        "rows_changed_any_column": changed_rows,
        "rows_changed_after_volatile_exclusions": substantive_rows,
        "cell_agreement_over_shared_keys": (
            round(1 - substantive_rows / shared, 4) if shared else None
        ),
        "changed_groups": sorted(
            substantive, key=lambda g: (-g["rows"], ",".join(g["columns"]))
        ),
    }


def score(reference: Path, run: Path) -> dict:
    cmp = _compare(reference, run, max_groups=64, examples_per_group=0)
    tables = [_score_table(t) for t in cmp.tables]
    # Keyed on what was actually counted, never on `presence`. An **unkeyed** table
    # — the binning kinds, whose `hints.key_fields(...).rule` is `overlap` rather
    # than `equality` — is `presence="both"` with every count `None`, so filtering
    # on presence put a `None` into the totals and raised. The rule this file
    # already stated is the right one and it is now the one implemented: a table
    # that was not counted is unscored, whichever way it failed to be counted.
    scored = [t for t in tables if t["keys_shared"] is not None]
    unscored = [t["csv"] for t in tables if t["keys_shared"] is None]
    return {
        "reference": str(reference),
        "run": str(run),
        "frame": {
            "reference_build": cmp.frame.left_build,
            "run_build": cmp.frame.right_build,
            "verdict": cmp.frame.verdict,
        },
        "comparable": cmp.frame.verdict == "same",
        "content_signature_reference": cmp.left_content_signature,
        "content_signature_run": cmp.right_content_signature,
        "content_identical": cmp.content == "same",
        "volatile_columns_excluded": list(VOLATILE),
        "tables": sorted(tables, key=lambda t: t["csv"]),
        "totals": {
            "keys_shared": sum(t["keys_shared"] for t in scored),
            "keys_only_reference": sum(t["keys_only_reference"] for t in scored),
            "keys_only_run": sum(t["keys_only_run"] for t in scored),
            "rows_disagreeing": sum(
                t["rows_changed_after_volatile_exclusions"] for t in scored
            ),
        },
        "unscored_tables": sorted(unscored),
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    if args and args[0] == "--fixture":
        if len(args) < 3:
            sys.stderr.write(__doc__ or "")
            return 2
        fixture = load_fixture(Path(args[1]).resolve())
        out: list[dict] = [
            score_ground_truth(fixture, locate_spec(Path(a).resolve())).model_dump()
            for a in args[2:]
        ]
    elif args and args[0] == "--census":
        if len(args) < 2:
            sys.stderr.write(__doc__ or "")
            return 2
        out = [census(locate_spec(Path(a).resolve())).model_dump() for a in args[1:]]
    else:
        if len(args) < 2:
            sys.stderr.write(__doc__ or "")
            return 2
        reference = locate_spec(Path(args[0]).resolve())
        out = [score(reference, locate_spec(Path(a).resolve())) for a in args[1:]]
    # `sort_keys` on top of the deterministic ordering inside the models, so the
    # payload is byte-stable and two runs can be diffed rather than eyeballed.
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
