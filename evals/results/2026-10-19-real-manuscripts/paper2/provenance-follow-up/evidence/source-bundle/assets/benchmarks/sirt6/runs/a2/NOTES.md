# Plugin friction notes — run-sirt6-a2

1. lookup_citation(doi=...) returns doi_exists:true but title/journal/year/first_author ALL null.
   The tool's own docstring says only a title settles identity — so the DOI path cannot do the
   one job the docstring says matters. Had to fall back to literature_search(query=<the DOI>),
   which worked but ranked the target #1 among 9 irrelevant hits (a Crossref "Back cover", a
   1977 German literature calendar). A DOI is an exact identifier; searching it as free text is
   the wrong shape.

2. literature_search returned pmcid as the malformed string "pmc-id: PMC12624115;" — a raw
   EuropePMC field pasted through unparsed. fetch_fulltext(pmid=) returned clean "PMC12624115",
   so the two disagree about the same record within one session.

3. semanticscholar 429 on the first call of the run. Reported honestly (results:null +
   warning), which is right, but per module-start that means the preprint/published linkage
   check is UNCHECKED and there is no retry/backoff offered.

4. literature_search `withheld` emitted one full ~90-word DOI-refusal note per result row — 10
   near-identical paragraphs, ~900 words, for a search whose useful payload was one paper.
   CLAUDE.md's own "aggregate repeated warnings by reason, with a count" rule is violated by
   the tool's own output.

5. The 6 `licensing` hints returned by literature_search are also one-per-source boilerplate,
   emitted whether or not I read that source. Only pubmed/europepmc/openalex actually answered.

6. TWO SKILLS CONTRADICT EACH OTHER ON THE literature LAYER.
   module-start/GUIDE.md: "It must cover every source your fact tables cite, including PubMed if
   you carry studies ... the row is the only record of its terms."
   module-tables/references/licensing.md: "**nobody, ever - the `literature` layer.** ... there is
   deliberately no `pubmed` entry in TERMS_BY_SOURCE and there will not be one (RM46) ... A
   `pubmed` row here would be ... a false all-clear for one carrying a provenance_quote lifted
   from a CC-BY-NC article."
   Same plugin, same release, opposite instructions. I wrote the row with all permission booleans
   blank as a compromise. Nothing in the tool surface adjudicates this.

7. describe_table("variants.csv") lists `state` options flat: alt|neutral|protective|ref|risk|
   significant. It does NOT say that format's own derive.py calls alt/ref "the retired
   alt/ref descriptors", nor that they map to direction=unknown. Zero of 16 reference examples
   use alt, ref or significant (only risk=377, neutral=4). The instruction is "ask the tool,
   never memory" - but the tool's answer is missing the one fact that decides the cell. I had to
   read .venv site-packages source to author `state` honestly.

8. There is no way to FIND a trait CURIE. lookup_identifier only verifies one you already hold,
   and its docstring says "Writing an ontology id from memory is the failure this exists to
   prevent" - while memory is the only source of candidates. I burned 4 guesses:
   EFO_0007796 = "parental longevity" (wrong trait, would have passed silently as `current`),
   EFO_0007797 = "language measurement", HP_0025153 = "Transient", and finally EFO_0004300 =
   obsolete_longevity, which named its successor OBA_VT0005372 = "life span determination trait".
   Only the obsolete one led anywhere. A trait SEARCH tool is the missing piece.

9. compile_module license warning is inaccurate. It printed:
     "module declares license 'CC-BY-NC-ND-4.0' but annotation-layer sources report ['CC0-1.0']."
   The module has TWO annotation-layer rows: clingen=CC0-1.0 and pmid:41249831=CC-BY-NC-ND-4.0.
   The second is an EXACT match for the declaration. compiler.py:5063-5074 filters
   `r.license != declared_license` then prints the remainder as if it were the whole set. An
   author reads "your declaration matches nothing" when it matches one of two.

10. The clingen annotation-layer licence row was written by enrich_facts' dosage pass even though
    the pass covered NOTHING: covered={dosage:[]}, missing={dosage:["SIRT6"]}. A source that
    contributed zero rows now holds an annotation-layer licence row - and that phantom row is the
    sole trigger for finding 9's warning.

11. The audit's `checks_that_never_ran` decision is the direct cost of following the skills'
    advice. module-curate says author rsid-only ("that is what gives the compiler's
    rsid-vs-coordinate check something independent to compare"). Doing so makes
    rsid_coordinate_agreement and genome_build_agreement report `nothing_to_check`. The safest
    authoring choice disables two of eleven verification checks. The tools are each right; the
    combination is not explained anywhere.

12. HEADLINE: the plugin's own mandated field makes a module unpublishable, and nothing local warns.
    server.INSTRUCTIONS rule 5 + CLAUDE.md 2 require filling StudyRow.curator on every row whose
    quote was located. curator shipped in format 0.6.5. Both live registries serve format 0.6.1
    (curl /api/v1/version on prod and polygon). StudyRow is extra="forbid", so:
      validate_module(strict)  -> valid
      compile_module(strict)   -> success
      registry_check(strict)   -> valid:false, "studies.csv line 2 [curator]: Extra inputs are not permitted"
    Counterfactual run with the column removed: verdict:true, module_level_clear:true, blocking:[].
    The version-contract check cannot see it (scoped to major.minor; 0.6 == 0.6). CLAUDE.md 11
    asserts "every 0.6.x interoperates" - that is false for any field added after 0.6.1.

13. compile_module(output_dir=<spec_dir>/build) silently poisons every later registry call.
    The compiler copies README.md into output_dir; the uploader walks the spec tree recursively;
    registry_check then 422s with ambiguous_spec_layout ("README.md arrives from more than one
    path"). Nothing in compile_module's docstring says output_dir must not be under spec_dir, and
    putting build/ inside the module directory is the obvious default. Cost: one confusing 422 and
    a directory restructure. A one-line refusal in compile_module would prevent it.

14. declared_use normalisation is inconsistent inside one plugin.
    enrich_facts(use="non-commercial")      -> accepted, records "non_commercial"
    enrich_gwas_effects(use="non-commercial") -> accepted
    registry_check(declared_use="non-commercial") -> HTTP 422 from the server, unnormalised
    module-start/GUIDE.md documents exactly this hyphen/underscore split for the CLI --use flag but
    registry_check's own docstring says nothing, so the 422 is the first you hear of it.

15. record_override's returned `note` describes the wrong mode. I called it WITHOUT source_value,
    which its docstring defines as edit-log mode ("written as an authored move, not an outranking
    one"). The response still said: "Recorded, not resolved. The cross-check still reports this
    mismatch and the row stays in review_queue - a recorded outrank is downgraded, never passed."
    There is no mismatch and no outrank. The persisted log line is correct
    ("authored ... (judged; no value from PMID 41249831 to disagree with)"); only the note is wrong.

16. review_queue reports record.authored_value as "" for every entry, always. record_override
    returned authored_value:"alt", but upstream's ProvenanceItem has only
    {variant_key, rationale, human_reviewed, outranks}, so our field/value/source/timestamp are
    packed into a "[jmc field=... value_sha256=... ]" suffix INSIDE the free-text rationale and only
    the sha256 survives. still_bound and current_value work; authored_value is structurally always
    blank. Also: that machine tag publishes verbatim in the module's provenance.json rationale.

17. WHAT I DID BY HAND THAT A TOOL SHOULD HAVE DONE:
    - Read .venv site-packages (just_dna_format/derive.py, spec.py) to learn that state=alt/ref are
      "retired descriptors" mapping to direction=unknown. describe_table will not say it.
    - Read just_dna_compiler/compiler.py:5063 to work out why the licence warning listed only the
      conflicting row. No tool explains its own warning.
    - Ran a python csv script to count `state` usage across the 16 reference examples, to find out
      whether `alt` had ever been used. There is no "show me how this column is used in practice"
      tool, and the reference corpus is the calibration the skills keep pointing at.
    - Verified the provenance quote was verbatim by eye against a 40kB fulltext blob. lint_rows does
      not check the quote; only enrich_literature_pass does, one full stage later.
    - Restructured the whole directory after the ambiguous_spec_layout 422.

18. WHAT WOULD HAVE SAVED THE MOST TIME, in order:
    a. registry_check-style schema compatibility warning at COMPILE time: "you used a field the
       target registry's format version does not have". This is finding 12 and it is the big one.
    b. A trait/ontology SEARCH (finding 8). Four guesses to find one CURIE.
    c. describe_table flagging retired/unused vocabulary members and their derived semantics (7).
    d. compile_module refusing output_dir inside spec_dir (13).
    e. lint_rows verifying provenance_quote against a fulltext it already knows how to fetch.
