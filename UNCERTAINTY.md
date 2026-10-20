# Phase 2: integration under uncertainty

The four silos record the same medicine pack independently, and each records it imperfectly. A
pharmacist types a smudged serial. A phone camera reads a label through glare. A warehouse clerk
re-keys a dispatch note. A citizen types a code into a complaint form. Phase 2 links those imperfect
records back to the national registry, cleanses the silos, and does both without erasing the
evidence of counterfeiting that the same records contain.

**Headline results** (held-out test split, 2,887 records):

| | Best plain string metric | Chosen model |
|---|---|---|
| Correct product, damaged codes | 92.1% (Damerau-Levenshtein) | **98.4%** |
| Precision of automatic links | 92.6% | **99.85%** |
| Counterfeit codes linked to a real product | 80–100% | **0%** |
| Counterfeit codes flagged "no registered product" | none (a string metric cannot say "none") | **100%** |
| Records left to a person | n/a | 5.6% (top suggestion right 81% of the time) |

All 20 phase-1 benchmark verdicts are unchanged, both on the noisy data and after cleansing.

---

## 1. The rubric, mapped onto this project

| The rubric's insurance example | Asali / Nakali |
|---|---|
| Scanned image of a number plate | Photo of the pack label: code, brand, strength, batch number, expiry, MRP |
| Noisy plate reading | Damaged pack code: OCR misread, typo, transposition, dropped character, format noise |
| All registered vehicles | DB3, the national drug registry (201 distinct registered batches) |
| Context: model, colour | Was this batch shipped to this pharmacy (DB2)? Does the price fit its MRP (DB3)? Was the sale between manufacture and expiry? What does the label say? |
| "…and vice-versa" | Given a registered product, every record in DB1, DB2 and DB4 that approximately refers to it |
| Cleanse w.r.t. image and context | Every anomaly fixed, reviewed or quarantined, with a lineage log and undo |
| Checked by insert/delete/modify | The matcher re-reads the live silos on every request; an Explorer write returns the matcher's reading of the row |

---

## 2. The data

`python scripts/rebuild_data.py` builds every silo from scratch, deterministically (seed 2026).

| Silo | Rows | What was added in phase 2 |
|---|---|---|
| DB3 registry | 207 products, 10 manufacturers | 40 invented brands of 35 molecules, 2–4 *consecutive* batches per SKU (so many codes are one edit apart, like number plates), 6 batches registered twice |
| DB2 ledger | 427 shipments, 9 distributors | shipments by authorised carriers; 2 unlicensed traders moving counterfeit stock |
| DB1 retail | 1,647 checkout scans, 38 pharmacies | sales only at the pharmacies that received each batch; 176 label captures by camera; 3 pharmacies registered twice |
| DB4 ministry | 149 complaints, 9 blacklist entries | citizen complaints with misspelt brands, codes only in the free text, refilings; blacklist and alert entries for counterfeits |

**How each capture channel fails.** Barcode and QR reads are almost always right (0.4% damaged).
Hand entry is damaged 35% of the time (keyboard slips, swaps, skipped characters). Camera reads of
the label are damaged 50% of the time (glyph confusion: O/0, B/8, S/5, Z/2, M/N…).

**Defects injected**, each recorded in `data/generated/ground_truth.json`. That file is used only to
*score* results, never to make a decision.

| Defect | Count |
|---|---|
| Damaged identifiers (OCR 65, keyboard 46, format 38, mixed 32, deletion 24, swap 13, insertion 10, truncation 7) | 235 |
| Real code, wrong product (a typo that lands on a sibling batch) | 22 |
| Code missing from a complaint, present in its text | 9 |
| Counterfeit records (30 fake codes, near-misses of real ones and fabricated) | 175 |
| Representation defects (dates, currency, vendor ids, separators) | 221 |
| Duplicate records (POS retries, re-imported shipments, complaints filed twice) | 56 |
| Master-data duplicates (6 products, 3 pharmacies) | 9 |
| Cross-source conflicts (wrong manufacturer in DB2, received > shipped) | 15 |
| Missing values (manufacturer, currency) | 28 |
| Unit-error prices (×10, ×100) | 13 |

**Image data.** For each camera capture, DB1 stores the OCR text of the label
(`purchase_events.label_text`) and, for 32 of them, the photo (`label_image`,
`dashboard/samples/labels/`). The photo shows what is really printed, rendered from the registry and
then damaged the way a counter camera damages it (tilt, blur, sensor noise, glare, JPEG). The
stored OCR text is the damaged reading of that photo.

---

## 3. Rubric 1: approximate matching

### 3.1 Pipeline

```
 noisy code  ─┐   label photo ─> OCR text ─> brand, strength, batch, expiry, MRP
 + context   ─┤
              v
  1 canonicalise   case, spacing, separators, country prefix          (never changes a character)
  2 block          products sharing confusion-folded bigrams          (100% of true products kept, 85.5% of comparisons avoided)
  3 compare        per candidate, a comparison vector γ:
                     code     learned noisy-channel distance, by capture channel
                     custody  shipped to this pharmacy / same city / elsewhere          (DB2)
                     price    unit price against MRP                                    (DB3)
                     date     sale between manufacture, arrival and expiry              (DB2, DB3)
                     label    brand · strength · batch · expiry · MRP read off the pack (image)
                   (shipments and complaints use the evidence they carry instead)
  4 weigh          Fellegi–Sunter: each value adds log2( P(value | same) / P(value | different) )
  5 normalise      posterior over the candidates  AND  "no registered product"  (prior π0)
  6 decide         EXACT · AUTO_LINK (≥ 0.90) · REVIEW · NO_MATCH (≥ 0.80) · VALID_BUT_WRONG
```

Code: `integration/uncertainty/linkage.py` (steps 2–6), `confusion.py` (the distance),
`standardize.py` (step 1 and label parsing), `context.py` (the evidence).

### 3.2 Which algorithm, and why: measured

Everything was fitted on a training split (2,884 records) and measured on a held-out split
(2,887 records: 2,808 genuine, 1,921 of them with a damaged code, and 79 counterfeit). A record and
its re-corrupted copies are always on the same side of the split. Each string metric got its own
best threshold on the training split. Reproduce with `python -m integration.uncertainty.train`.

| Method | Top-1, all | Top-1, damaged | Recall@5 | Link precision | Link recall | F1 | Fakes linked to a real product |
|---|---|---|---|---|---|---|---|
| Levenshtein | 93.8% | 90.9% | 99.9% | 91.2% | 93.8% | 92.5% | 100% |
| Damerau-Levenshtein | 94.6% | 92.1% | 100% | 92.6% | 94.6% | 93.6% | 79.7% |
| Jaro-Winkler | 93.4% | 90.4% | 99.9% | 90.9% | 93.4% | 92.1% | 100% |
| Bigram Jaccard | 94.0% | 91.3% | 99.9% | 92.0% | 94.0% | 93.0% | 79.7% |
| Soundex | 7.0% | 5.9% | 28.9% | 8.2% | 6.9% | 7.5% | 84.8% |
| Learned OCR distance | 96.9% | 95.4% | 100% | 94.2% | 96.9% | 95.5% | 100% |
| Fellegi–Sunter, code only | 96.7% | 95.1% | 99.8% | 98.6% | 55.2% | 70.8% | 0% |
| **Fellegi–Sunter + context (chosen)** | **98.8%** | **98.4%** | **100%** | **99.85%** | **93.9%** | **96.8%** | **0%** |

Top-1 by kind of damage (held-out):

| Damage | Lev | Damerau | Jaro-W | Jaccard | Learned distance | **Chosen** |
|---|---|---|---|---|---|---|
| OCR glyph confusion | 89.5 | 89.4 | 85.4 | 89.4 | 99.1 | **98.7** |
| Keyboard slip | 93.0 | 93.0 | 90.7 | 92.6 | 93.9 | **98.4** |
| Transposition | 89.8 | 98.6 | 99.5 | 93.5 | 98.6 | **100** |
| Two defects at once | 87.0 | 89.9 | 86.5 | 87.0 | 94.2 | **99.0** |
| Truncated code | 21.1 | 21.1 | 21.1 | 21.1 | 21.1 | **84.2** |
| Real code, wrong product | 0 | 0 | 0 | 0 | 0 | **87.5** |
| Code only in the complaint text | n/a | n/a | n/a | n/a | n/a | **100** |

**Why this combination:**

1. **On structured codes the classic metrics are nearly interchangeable.** Every pack code shares
   the `MED-XXXXX-NNN` skeleton, so Levenshtein, Damerau, Jaro-Winkler and q-grams all land at 90–92%
   on damaged codes, and tie at the top for 6–8% of queries. Damerau beats Levenshtein mainly on
   swaps (98.6% vs 89.8%), which is exactly what it is designed for.
2. **The error model matters more than the metric.** A camera reads O as 0 constantly and O as X
   almost never; plain edit distances charge both the same. The learned noisy-channel distance
   prices each substitution by how much likelier than a random slip it is in the training pairs
   (a printed 0 read as O costs 0.16, S read as 5 0.16, 3 read as 8 0.17; a random substitution 1.0). It is the best single metric
   (95.4% on damaged codes, 99.1% on OCR damage against 85–90% for the rest).
3. **No string metric can say "none", and that is disqualifying here.** A string metric always
   returns its nearest code. A counterfeit code printed one edit from a real one *is* nearest to that
   real product, so at their best thresholds the string metrics link 80–100% of counterfeits to a
   genuine product and hand them its clean verdict. Fellegi–Sunter with an explicit "no registered
   product" hypothesis links none.
4. **The code alone is not enough evidence.** Fellegi–Sunter on the code only is safe (98.6%
   precision, 0 fakes linked) but has to ask a person about 41% of records. Context is what
   separates a misread from a lookalike: custody, price, dates and the label raise top-1 on damaged
   codes to 98.4% and cut review to 5.6%, at 99.85% precision.
5. **Some cases only context can solve.** A truncated code (`MED-FMRAO-66`) is one edit from ten
   products, and a typo can land on a different real code. Every string metric gets 21% and 0%
   respectively; the chosen model gets 84% and 88%, because only one of those products was shipped
   to that pharmacy, at that price, before that date.
6. **Soundex is for names, not codes.** On codes it ties every query with dozens of others (5.9%
   top-1). On brand names (from label text and complaints) every edit metric scores 98.9–99.9% and
   Soundex alone 77.8%. The matcher compares names with Jaro-Winkler (99.6%, within 0.3 points of
   the best) and never uses Soundex on codes.

**Weights the model learned** for a checkout (bits; positive is evidence for the same product):

| Evidence | Value → weight |
|---|---|
| code, barcode/QR | exact +22.3 · one confusable glyph −6.4 · one edit −3.0 (a scanner misread is rare, so a near-miss *scan* is suspicious) |
| code, typed | exact +8.8 · confusable +6.0 · one edit +4.2 · two edits +0.1 · far −15.3 |
| code, camera | exact +8.2 · confusable +7.4 · one edit +2.2 · two edits +0.3 · far −9.3 |
| custody | shipped to this pharmacy +3.5 · same city −2.0 · elsewhere −9.2 |
| price | fits MRP +2.7 · 20–60% below −10.9 · under 40% (dumping) −13.9 · above MRP −12.4 |
| date | consistent +0.2 · sold before it arrived −7.7 · before manufacture −13.1 · after expiry −6.7 |
| label (image) | batch exact +19.3 · brand agrees +2.6 / disagrees −9.7 · expiry +4.7 / −6.7 · MRP +3.4 / −9.2 |

**Thresholds.** Tuned on the training split for maximum automation, subject to policy floors.
Auto-link needs ≥ 0.90 posterior and 99.5% training precision. "No registered product" needs
≥ 0.80 and 90% training precision. The targets differ on purpose: a wrong link rewrites a
counterfeit into a real product and destroys the evidence, while a wrong quarantine is an annotation
a reviewer can lift.

### 3.3 And the reverse

`reverse(uid)` scans DB1, DB2 and DB4 for every record that approximately refers to a product
(stored exactly, or damaged), with each one's posterior. For `MED-ASALI-001` it finds both
shipments, the original sale, the lab report, and the camera capture stored as `MED-ASALI-0O1`.

### 3.4 The scanned image

On the page, upload a photo or pick a captured pack. Tesseract.js reads it in the browser
(downloaded on first use; offline, the recorded OCR reading is used instead). The parsed label
becomes evidence. When the code is unreadable, the label alone proposes candidates by brand and
batch: `N0VAMOX 500MG | B.No. BATCH-A0O1 | EXP 01/2027 | MRP Rs.115.00`, sold at Apollo Bandra,
resolves to `MED-ASALI-001` with p = 1.00.

---

## 4. Rubric 2: cleansing

`integration/uncertainty/cleanser.py`. One scan of all four silos takes 1–4 s:

| Category | Automatic | Review | Example | Policy |
|---|---|---|---|---|
| Representation mismatch | 266 | 0 | `21-Feb-2026` → `2026-02-21`; `vnd-10` → `VND-010`; `Rs.` → `INR` | Deterministic. An ambiguous `03/10/2025` is read the way the product's own timeline allows |
| Noisy identifier | 170 | 23 | `MED-ASAL1-OO7` → `MED-ASALI-007` (p 0.993) | Auto only at posterior ≥ 0.90 |
| Real code, wrong product | 15 | 8 | DB2 `MED-AMXLN-203` → `…-201` (p 0.993) | Auto only from hand/camera channels at ≥ 0.98; a scanner read is never overruled |
| Duplicate record | 55 | 1 | POS retry 7 s later; re-keyed retry with a typo; complaint filed twice | Rows deleted; a complaint is closed as a duplicate, never deleted |
| Duplicate master record | 9 | 0 | `ZITHROLANE 250 MG` (MED-ZITHR-227) = `Zithrolane 250mg` (MED-ZTHRL-227) | Survivor = most referenced; references re-pointed, then the copy removed |
| Cross-source conflict | 14 | 0 | DB2 says MFG-007, DB3 says MFG-008 | DB3 owns who made a product. Received > shipped is *annotated*, because neither count outranks the other |
| Missing value | 37 | 0 | empty manufacturer → from DB3 via the linked product; code only in complaint text | Imputed only when another silo determines it |
| Implausible value | 13 | 0 | Rs 6200 for a Rs 62 strip → Rs 62 | Only when ÷10 or ÷100 lands exactly in the MRP band |
| Counterfeit signal | 155 quarantined | — | `MED-NAKALI-001` shipped by a ghost distributor | **Never rewritten.** Flagged as evidence; the code stays as recorded |

**Against ground truth:** automatic identifier fixes 185/185 correct. Review suggestions 27/31.
Quarantined codes 152/155 really counterfeit. Duplicates 56/56 found with no false positives.
Outliers 13/13, missing values 28/28, representation defects 221/221, conflicts 14/15 (the
fifteenth surfaces once its damaged code has been reviewed).

**After "apply automatic fixes"** (one pass, 954 changes, about 6 s): 0 automatic issues and 0
unquarantined counterfeit codes remain. 25 genuinely uncertain items wait for a person, for
example two sibling batches both shipped to the same pharmacy. The reviewer accepts the
suggestion, picks another candidate, marks it counterfeit, or keeps the record as it is; after
that nothing is left. Every change is logged with its old value (and a snapshot of any deleted
row) in `databases/data_quality.sqlite`, and any run can be undone. Undo refuses if a later run
touched the same rows.

**Effect on verification.** The 20 curated verdicts and scores are identical before and after
cleansing. The one visible difference is a better one: blacklist entry `BL-G02` was stored as
`med cprvn 590`, so the blacklist veto never matched it. Cleansing canonicalises it (format only:
a regulatory reference is never re-pointed at a registered product), and the counterfeit
`MED-CPRVN-590` now trips `V2_MINISTRY_BLACKLIST`.

---

## 5. Checking it by insert, modify and delete

Each check works from the dashboard (*Uncertainty → 6*), from the Explorer, or from the terminal.

| Do this | Expect |
|---|---|
| **Insert** a DB1 checkout: code `med asali 0O8`, Apollo Bandra (VND-001), Rs 85, typed | The insert response already says `AUTO_LINK MED-ASALI-008` (Omez), p 0.998; the next scan lists it; apply fixes it |
| **Insert** a counterfeit: `MED-ASALI-011` by barcode at a kiosk (VND-007), Rs 30 | `NO_MATCH`, p(no product) 0.99. String metrics would call it Novamox or Calcirol |
| **Modify** DB3: set Ciplox (`MED-ASALI-007`) MRP to Rs 400 | The smudged Ciplox sale drops from AUTO_LINK 0.993 to REVIEW; nothing is auto-linked to the wrong product |
| **Delete** Omez (`MED-ASALI-008`) from DB3 | Its noisy sale falls from AUTO_LINK 0.998 to REVIEW; Omez is no longer a candidate |
| **Insert** a copy of a sale 12 s later | Scan reports a `duplicate_record`, automatic |
| **Insert** a product into DB3 | Immediately a candidate; the legacy resolver also refreshes now |

Terminal equivalents:

```bash
python -m integration.uncertainty match "med asali 0O8" --vendor VND-001 --price 85 --date "2025-04-20 10:15"
python -m integration.uncertainty match MED-ASALI-011 --channel scan --vendor VND-007 --price 30
python -m integration.uncertainty compare MED-ASALI-011
python -m integration.uncertainty reverse MED-ASALI-001
python -m integration.uncertainty scan --show 20
python -m integration.uncertainty apply        # then: lineage, undo <run_id>
python -m unittest tests.test_uncertainty      # the same checks, automated, on a throwaway copy
```

---

## 6. Rubric 3: vibe coding

`vibe_coding/` holds the evidence for this item:

* `PROMPTS.md`: the request as typed, and the eleven component prompts it was turned into.
* `generated_v0/`: every new or touched file exactly as first generated, frozen before anything ran.
* `CHANGES.md`: each change made after that, with the observation that forced it (17 entries;
  for example the Windows console crash, the miscalibrated confusion costs, the 0.5 threshold, the
  blacklist entry that could have been pointed at a genuine medicine).
* `phase1_baseline/`: the project before phase 2.
* `make_diff_report.py` builds `dashboard/vibe/index.html`, showing the prompts, the generated code,
  and side-by-side highlighted diffs (generated → now, and phase 1 → now). Rerun it after any edit.

---

## 7. Limitations

* **The data is synthetic.** The confusion costs and weights were learned from the generator's own
  noise channel, so the absolute numbers are what this channel produces, not a claim about real
  pharmacies. The method transfers: refit on real (observed, true) pairs with the same script.
* **Some context features rest on regularities the generator builds in**, such as shipping a batch
  within 75 days of manufacture, or selling only at pharmacies that received it. These are plausible
  business rules, but their weights are sharper here than real data would make them.
* **The counterfeit test set is small** (79 records, 30 codes). "0 linked" means 0 of 79.
* **Brand-name matching is easy here** (55 brands); the name benchmark separates Soundex from the
  rest, little more.
* **The nodes serve one request at a time.** A scan takes seconds, and refitting runs on a
  background thread for 3–4 minutes.
* **In-browser OCR needs internet on first use** (Tesseract.js from a CDN). Offline, the recorded
  OCR reading stands in.

---

## 8. Files

| Path | Role |
|---|---|
| `integration/uncertainty/` | the library: similarity, noise, confusion, standardize, context, linkage, cleanser, train, http_api, CLI |
| `data/generate_uncertain_data.py`, `data/render_label_images.py` | dataset, ground truth, label photos |
| `data/generated/` | `ground_truth.json`, `linkage_model.json`, `benchmark_results.json` |
| `dashboard/uncertainty.html`, `uncertainty.js` | the phase-2 page |
| `scripts/rebuild_data.py` | rebuild everything from scratch |
| `tests/test_uncertainty.py` | 18 checks, including insert / modify / delete |
| `vibe_coding/` | prompts, generated snapshot, change log, diff report |
