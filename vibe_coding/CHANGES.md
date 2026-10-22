# Changes made to the generated code

`vibe_coding/generated_v0/` holds every new or touched file exactly as the assistant first wrote
it, before a single line was run (snapshot taken 2026-10-20 01:06). Everything below was changed
afterwards, because running, testing or reviewing the code showed it was wrong. Each entry says
what was observed, what was changed, and where. The diff report highlights every one of these
lines.

## Found by running the benchmark

**1. Console crash on Windows.** `train.py` printed `→` in the results table; the Windows console
(cp1252) cannot encode it and the run died after 200 s of work. → ASCII header (`fake->real`).
*train.py*

**2. Learned substitution costs were miscalibrated.** With the first formula, `1 − 0.85 · share`,
the cheapest learned pairs were `C→G` and `H→N` (0.33), while the 0/O confusion, the most common
OCR error in the data, did not even reach the ten cheapest (all ≤ 0.40). That made it dearer than
its 0.25 shape prior. A character with several genuine confusions (`0` is read as `O`, `D`, `Q`, `8`)
splits its share among them, so each one looked rare. → Cost from the likelihood ratio against a
random slip: `1 − log(p/p0)/log(1/p0)`, p0 = 1/36. A printed 0 read as O now costs 0.16.
*confusion.py*

**3. Auto-link threshold tuned down to 0.5.** Grid search found 0.5 still met 99.5% precision on
the synthetic training split. Rewriting a medicine record on a coin flip is not acceptable when
the training data is synthetic. → Policy floors: auto-link ≥ 0.90, no-match ≥ 0.80. *train.py*

**4. Training ignored duplicate pharmacy records.** Sales booked under `VND-036` (Apollo Bandra
registered a second time) got custody "same city" instead of "shipped to this pharmacy", so a
sibling batch won (`MED-FVRLE-785` chosen for `…-786`). The cleanser used vendor aliases, training
did not. → Duplicate detection made static and shared (`duplicate_aliases`), training builds its
context with both alias maps. *cleanser.py, train.py*

**5. A real-but-wrong code was always accepted.** `MED-MTPRE-696` sold before batch 696 was even
manufactured had 99.9% of the probability on its siblings, but no single sibling reached 0.6, so
the rule kept the wrong code. → VALID_BUT_WRONG when the probability *mass* on other registered
products is ≥ 0.6; one shared `is_auto()` policy for the cleanser and the evaluation (they had
used different definitions of "automatic"). *linkage.py, cleanser.py*

**6. Shipments could not separate sibling batches.** 203 of the 320 genuine records left for
review were DB2 shipments: consecutive batches share maker, carrier and dates, so only the code
discriminated. → Cross-silo evidence: was this batch later **scanned by barcode at the
destination pharmacy** (DB1 → DB2, scanner reads only, so no circular fuzzy link); destination
licence; dispatch lag after manufacture. Together with 7, held-out link recall rose from 88% to 94% at
99.9% precision.
*context.py, linkage.py*

**7. The no-match target treated both mistakes as equally bad.** Requiring 97% precision for
"no product" pushed its threshold to 0.995 and left every counterfeit in review. A wrong link
destroys counterfeit evidence; a wrong quarantine is an annotation a reviewer can lift. → 90%
target for no-match, 99.5% kept for links. On the held-out split every counterfeit code is now called
"no registered product" outright (100%), none is linked to a real product. *train.py*

**8. Smoothing artefact.** DB2 `date=expired` got +2.08 bits although it was never observed in
either class: Laplace smoothing with very different denominators turns "never seen" into
evidence for a match. → Smoothing toward the prior m/u instead (now −0.66). *train.py*

**9. Benchmark speed.** Exact top-k pruning: candidates visited in bigram order, edit-distance DP
abandoned once it cannot beat the k-th best. The bound uses the last two DP rows because an OSA
transposition jumps from row i−2 to row i. Verified identical to exhaustive scoring on 60 codes.
*similarity.py, confusion.py, train.py*

## Found by running the cleanser

**10. A counterfeit blacklist entry was steered toward a real product.** `BL-G02` stored
`med cprvn 590` (a fake code with formatting noise). The review suggestion was `MED-CPRVN-580`, a
genuine product; accepting it would blacklist a real medicine and leave the fake un-vetoed.
→ Regulatory references (`ministry_blacklist`, `public_alerts`, `lab_reports`) are always
canonicalised (format only, so the V2 veto finds them) and never re-pointed at a registered
product without a person. After cleansing, `MED-CPRVN-590` now triggers the V2 blacklist veto.
*cleanser.py*

**11. Reviewers had no "this is a fake" option.** → Third decision: quarantine as counterfeit
evidence. Quarantined rows are not re-reported. Annotations are appended to existing notes
(`_append_note`) instead of overwriting, e.g. a "units damaged in transit" note. *cleanser.py,
uncertainty.js*

**12. Apply and undo hardening.** Apply runs to a fixpoint (a fixed code can reveal a duplicate).
Undo refuses to revert a run while a later run that touched the same rows is still applied,
because it would silently overwrite the later change. *cleanser.py*

**13a. Duplicates hidden behind a typo.** Scored against ground truth, the duplicate detector
found 49 of 56 injected duplicates (no false positives). The 7 it missed were re-keyed: a POS retry
typed again with a typo, a complaint refiled with a different damaged code. Grouping on the
resolved product never brought them together. → The neighbouring record is itself the evidence:
same till, price and quantity within a minute, and codes a small learned distance apart; for
complaints, the same person within three days with near-identical codes or a description that
repeats the earlier one. Now 56 of 56, still no false positives. *cleanser.py*

## Found through the API and the browser

**13. A label photo without a readable code found nothing.** Candidates came only from the code,
and an absent code was scored as "far from every product". → The label's brand and damaged batch
number propose candidates; the code feature is omitted when there is no code. Explanations name
the candidate their evidence describes. *linkage.py*

**14. The match endpoint showed duplicate master records.** `MED-CALCI-218` (a second registration
of a Calcivane batch) appeared as a candidate while the cleanser treated it as an alias.
→ `live_matcher()` gives every endpoint the same alias-aware view as a scan. *cleanser.py,
http_api.py*

**15. Page text that overclaimed.** The names note said Jaro-Winkler was chosen because typos fall
late in a word; the benchmark shows Damerau-Levenshtein marginally ahead (99.9% vs 99.6%) and the
noise is position-uniform. The counterfeit card named the wrong lookalikes. → Both now match the
measured data. *uncertainty.js, uncertainty.html*

**16. Training on cleansed data went unreported.** → The benchmark records how many cleansing
changes were applied and the page warns. *train.py, uncertainty.js*

## Phase-1 files changed outside the snapshot

* `scripts/run_cluster.py`: `--stop` used `ps` and `SIGKILL`, neither of which exists on Windows;
  it now uses PowerShell/CIM and `taskkill` there.
* `create_databases.py`, `data/seed_db1..4.py`: honour `ASALI_DB_DIR` so the test suite builds
  in a temporary directory.

## Later prompts (12 onwards)

Each is shown with the code it changed in part 2 of the report.

### Prompt 12: connecting phase 1 and phase 2, and a simpler UI

**17. A product registered on one PC never reached the other.** Each node reads only its own
copy of the databases. The Explorer sends a DB3 insert to PC2, but the Uncertainty page asks
PC1, so with two laptops the new product never appeared in phase 2 (a real case:
`MED-SAM-001` was in PC1's DB1 and DB2 but only in PC2's DB3). → Every write a node accepts
(explorer insert/update/delete, registration across all databases, blacklisting, cleansing
apply/decide/undo) is forwarded to the other node, which applies the same request to its own
copy. The dashboard sends the other node's address with each write. Generated ids (federated
item code, blacklist id, cleansing run id) travel with the copy, so both copies stay identical
and "Undo this run" works on both. When both nodes share one folder, a storage id detects it and
the copy is skipped. Copies are sent in order by one background thread per node, so two writes
crossing between the PCs cannot deadlock. The page shows "Also saved on the other PC", or the
reason it was not. *integration/replication.py (new), api/node_pc1.py, api/node_pc2.py,
assets/cluster.js, explorer.js, cleanser.py, http_api.py, db_explorer.py, tests/test_replication.py (new)*

**18. Check a medicine showed stored examples for real products.** The verdict was live, but the
product, journey and evidence came from 22 stored examples, so any other product (newly
registered, or the generated catalogue) showed a live verdict beside "Unregistered product".
→ The live check now returns the full dossier built from the live records, and the page draws
it. The stored examples are used only when no PC answers. *api/verify_item.py, db_explorer.py,
app.js*

**19. The Uncertainty page kept an old product list.** → It re-reads the registry when you return
to the tab, and says when it last read it. *uncertainty.js*

**20. A cluttered UI with unclear wording.** → Every page opens with a plain title and a guide
listing its parts. Every part has a number, a heading saying what it does, and a "Use this to…"
line. Jargon was replaced (silo → database, node → PC, posterior → chance, verdict arbitration →
deciding). Inputs got labels. All pages share one nav: Check a medicine, Databases, Matching &
cleaning. No features were added or removed. *all dashboard pages, style.css*

**21. The Phase 2 page scrolled sideways on a phone.** The result table widened its grid column.
→ The column may now shrink, and the nav fits a 390 px screen. *uncertainty.html, style.css*

### Prompt 13: mistyped codes on Check a medicine

**22. Check a medicine corrected codes against 22 stored examples.** Before asking the PCs, the
page "corrected" the typed code using its built-in example list, which knows no newly registered
product: `med sam 001` became the recalled `MED-RECALL-003`, `MEDSAM001` became `MED-ASALI-003`.
The server had the same kind of slip: a code typed without dashes was read as a brand name.
→ The page sends what was typed; the PCs read it against the live registry and say how
(formatting, look-alike characters, batch number, product name). A code with no dashes is tidied
the Phase 2 way (formatting only) instead of name-matched. A closer miss (`MED-SAN-001`,
`MED-SAM-002`) is checked as typed and comes out as not registered, with a "Did you mean
MED-SAM-001?" button from the Phase 2 matcher (shown only at 50% or more), because a fake can
carry a near-miss code. The stored examples remain the fallback when no PC answers. The check
button stays busy until the answer arrives. *api/verify_item.py, db_explorer.py, app.js,
verify.html, tests/test_uncertainty.py*

### Prompt 14: this report

**23. Later prompts were mixed into one big diff.** The report compared everything against the
generated snapshot, so it could not show which prompt changed which line. → Each later prompt
now has a folder in `vibe_coding/rounds/` with the prompt, the list of files it changed and those
files just before it; the report shows each prompt with its own before → after diffs (part 2).
Prompt 12's starting point is the git commit; prompt 13's was rebuilt by undoing its exact edits,
and checked to compile. The report also got the same plain headings and guide as the site.
*vibe_coding/make_diff_report.py, vibe_coding/rounds/ (new), uncertainty.html*

---

## Your changes

*Add your own modifications below.* Whatever you change after this point is picked up
automatically: rerun `python vibe_coding/make_diff_report.py` and the report highlights it
against both the generated snapshot and the phase-1 baseline.

To show a new prompt on its own, like prompts 12–14: before changing anything, make a folder
`vibe_coding/rounds/15-short-name/` with `ROUND.md` (the prompt, quoted), `FILES.txt` (one
path per line) and `before/` (copies of those files as they are now). Then make the changes
and rerun the script.
