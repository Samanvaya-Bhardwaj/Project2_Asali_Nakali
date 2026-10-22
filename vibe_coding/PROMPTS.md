# Vibe-coding prompts — Phase 2: integration under uncertainty

Tool: Claude Code (model: Claude Opus 5.5), run inside this repository.

There are three kinds of prompt:

* **Prompt 0** is the request exactly as it was typed to the assistant.
* **Prompts 1–11** are the component prompts that request was broken into. Each one is
  self-contained: pasting it into a coding assistant, together with the repository, should
  regenerate the corresponding module. They are listed in the order the code was generated.
* **Prompts 12 onwards** are later requests, typed after the code was generated, quoted exactly.
  The report shows each of them next to the code it changed (part 2 of the report).

The code as it stood straight after generation, before anything was run, is frozen in
`vibe_coding/generated_v0/`. Every change made after that point is listed in `CHANGES.md` and
highlighted line by line in the diff report (`python vibe_coding/make_diff_report.py`, then
open `dashboard/vibe/index.html`).

---

## Prompt 0 — the request

> now check the requirements of the project, now the second phase is data integration under
> uncertainity like data redundancy, duplicates, mismatching, conflicts project should focus on
> every aspect of uncertainity
> i am pasting the rubrics from same course but for different project check what we can do for
> our asli-nakli (As discussed earlier, you need to demonstrate the data integration (and entity
> matching) under noisy data. For example, for your insurance project, if the vehicle
> registration is not matched exactly, how to find out all vehicles which are very close to the
> scanned (image) registration number, and then how to cleanse this noisy record with the help of
> other contextual data (like, model, color etc). Your project will be evaluated based on the
> following rubric:
>
> 1. Given a scanned image of a car registration, find out all vehicles approximately matching
>    with this nosy car plate and vice-versa. Here you need to apply the matching algorithm which
>    gives the best accuracy. You need to justify why you have taken a particular algorithm or a
>    combination of algorithms. (5)
> 2. Cleansed the recorded data w.r.t. the image data and other contextual information so that
>    there are no anomalies (including the noise) in the recorded data. (5)
> 3. Show me the prompt (for vibe coding), generated code and highlights the changes you have
>    made in the generated code. (5)
>
> Note: All these tasks I shall be checking by asking you to insert/delete/modify the data
> records.)
> few things will obviously remain same... use the algorithm appropriately, generate more data or
> download from somewhere i don't care, but there should be enough data that to we can defend
> integration under uncertainty....(we can use dummy data) use this repository
> (https://github.com/Samanvaya-Bhardwaj/IIA-Asli-Nakli)
> , you need to update in the existing code in this folder Project2_Asali_Nakali (as of now
> nothing has been pushed to github)

**How the rubric was mapped onto Asali/Nakali**

| Insurance example | Asali/Nakali |
|---|---|
| Scanned image of a number plate | Photo of the medicine pack label (code, brand, strength, batch, expiry, MRP) |
| Noisy plate read | Damaged pack code: OCR misread, typo, transposition, truncation, format noise |
| Registered vehicles | DB3, the national drug registry (one row per registered batch) |
| Contextual data: model, colour | Which pharmacy received the batch (DB2), price vs MRP (DB3), sale vs manufacture/expiry dates, brand/strength/batch/expiry/MRP read off the label |
| "and vice-versa" | Given a registered product, every record in DB1/DB2/DB4 that approximately refers to it |
| Insert / delete / modify | Explorer operations on the live silos; the matcher re-reads them on every request |

---

## Prompt 1 — dataset

> Extend the four existing silos (DB1 retail POS, DB2 distributor ledger, DB3 manufacturer
> registry, DB4 ministry) with a deterministic synthetic dataset big enough to defend
> integration under uncertainty. Keep the 20 curated phase-1 items and their verdicts unchanged.
> Add ~6 manufacturers, ~35 molecules with invented brand names, 2–4 consecutive batches per SKU
> (consecutive batch numbers so many codes are one edit apart), ~30 pharmacies across 9 Indian
> cities plus unlicensed kiosks, shipments by authorised distributors, and checkout scans at the
> pharmacies that actually received each batch. Capture channel matters: barcode/QR reads are
> almost always right, hand entry and camera (OCR) reads are not. Inject every kind of defect
> with a typed noise channel: OCR glyph confusion, keyboard slips, transpositions, deletions,
> insertions, truncation, format noise, a real-but-wrong sibling code; exact and near duplicate
> rows; master-data duplicates (a batch registered twice, a pharmacy registered twice with its
> licence formatted differently); manufacturer conflicts and missing values in DB2; unit errors
> in prices; ambiguous DD/MM dates; citizen complaints with misspelt brands, codes only in the
> free text, and complaints filed twice. Add counterfeits: codes one or two edits from real ones
> and fabricated codes, shipped by ghost distributors to kiosks and sometimes to licensed
> pharmacies, sold at 30–60% of MRP, complained about, and blacklisted (one blacklist entry with
> formatting noise). For camera captures store the OCR text of the label in a new
> `purchase_events.label_text` column, and the photo path in `label_image`. Write the ground
> truth for every record to `data/generated/ground_truth.json`, which the matcher must never read.

## Prompt 2 — string metrics and noise channel

> Implement, without third-party packages: Levenshtein, Damerau-Levenshtein (optimal string
> alignment), Jaro-Winkler, padded q-gram Jaccard and American Soundex, each with a [0,1]
> similarity. Separately implement a typed noise channel (ocr, keyboard, transpose, delete,
> insert, format, truncate, mixed) with per-capture-channel profiles, seeded by a
> `random.Random`, used both to generate the dataset and to augment the benchmark.

## Prompt 3 — learned noisy-channel distance for codes

> Write a weighted OSA edit distance for printed codes: substitution cost depends on the pair of
> characters, transposition 0.6, separator insertion/deletion 0.1, a doubled keystroke 0.5,
> other indels 1.0, banded for speed. Start from a prior built from glyph-shape classes (O/0,
> I/1/L, S/5, B/8, Z/2, G/6 …) and learn substitution costs from (observed, true) training
> pairs via an alignment backtrace. Expose `distance`, `similarity`, `fit`, `top_confusions`,
> serialisation, and a discretisation of distance into agreement levels L0–L4.

## Prompt 4 — standardisation

> Deterministic format canonicalisation that never changes a character: pack codes to
> `MED-FAMILY-NNN` (case, spacing, separators, country prefix, GS1 digital-link serial), dates
> from ISO, DD/MM/YYYY, DD-Mon-YYYY, Mon DD YYYY (report both readings of an ambiguous DD/MM
> date), currency aliases to INR, vendor-id spellings to VND-NNN, licence keys, brand and
> strength keys, and a tolerant parser for OCR label text (brand, strength, batch, expiry
> month, MRP, code) that survives digits read as letters.

## Prompt 5 — live context

> A read-only snapshot of the silos used as matching evidence: registered products, vendors,
> distributors, manufacturer→distributor authorisations, custody (which product was shipped to
> which pharmacy, when), and a bigram blocking index on confusion-folded codes. Rebuild it
> automatically whenever any SQLite file changes so inserts, updates and deletes are visible to
> the next request. Support alias maps (duplicate product → survivor, duplicate pharmacy →
> survivor). Custody from damaged DB2 serials may only come from confident links.

## Prompt 6 — probabilistic linkage

> Implement Fellegi–Sunter record linkage for one noisy record against the registry: block,
> build a comparison vector per candidate (code level by capture channel; for checkouts:
> custody, price vs MRP, date consistency, and label brand/strength/batch/expiry/MRP; for
> shipments: manufacturer, distributor authorisation, dispatch date; for complaints: brand and
> shop mentioned in the text), weight each value by log2(m/u), and normalise into a posterior
> over the candidates **and a null hypothesis "this code belongs to no registered product"** with
> prior π0 per source. Decide EXACT / AUTO_LINK / REVIEW / NO_MATCH / VALID_BUT_WRONG. Provide
> the reverse lookup (every record that approximately refers to a product), plain-English
> explanations, and a per-query comparison of every string metric.

## Prompt 7 — cleanser

> Scan all four silos and produce issues with category, decision (AUTO, REVIEW, RETAIN),
> confidence, method, explanation and the exact row changes: format mismatches, noisy and
> valid-but-wrong identifiers, duplicate rows (POS retry, ERP re-import, complaint filed twice —
> close as duplicate, never delete a citizen's complaint), master-data duplicates with
> survivorship and re-pointing of references, cross-source conflicts resolved by source authority
> (DB3 owns who made a product) or annotated when neither source outranks the other, missing
> values imputed only when another silo determines them, unit-error outliers, and counterfeit
> codes **quarantined, never rewritten into a real product**. Apply with a lineage log (old value,
> new value, deleted-row snapshot) so any run can be undone; let a reviewer accept, pick another
> candidate or reject. Keep the DB1 JSON document mirror in sync.

## Prompt 8 — training and benchmark

> Split the labelled records 50/50 by record (a record and its re-corrupted copies on the same
> side). On the training half fit the confusion costs, the Fellegi–Sunter m/u tables and π0,
> and tune the thresholds for maximum automation subject to 99.5% auto-link precision. On the
> held-out half compare Levenshtein, Damerau-Levenshtein, Jaro-Winkler, bigram Jaccard,
> Soundex, the learned distance alone, Fellegi–Sunter on the code only, and Fellegi–Sunter with
> context: top-1 (all and damaged only), recall@5, MRR, link precision/recall/F1, the share of
> counterfeit codes linked to a real product, review rate, per-noise-kind accuracy, blocking
> completeness, and a separate brand-name benchmark. Save the model and the results as JSON.

## Prompt 9 — API and wiring

> Add `/api/v1/uncertainty/*` (match, compare, reverse, catalog, samples, scan, apply, decide,
> undo, lineage, benchmark, train) in one module that both nodes delegate to. After every
> explorer INSERT/UPDATE on purchase_events, distribution_batches or complaints, return the
> matcher's reading of the written row in the same response, and re-sync the DB1 mirror after
> any DB1 write. Fix FEDERATED_INSERT (RUNNING.md 5.1) so its writes satisfy the DB2/DB1
> constraints and its `success` reflects the results.

## Prompt 10 — dashboard

> A new page `dashboard/uncertainty.html` in the existing design system: match a noisy code or
> a label photo (in-browser OCR with Tesseract.js, falling back to the recorded OCR text),
> ranked candidates with evidence chips and posteriors, per-metric comparison; reverse lookup;
> the benchmark with justification drawn from the numbers; scan/apply/review/undo; lineage;
> insert/modify/delete test cards that write through the explorer endpoint and show the answer
> before and after; a link to this vibe-coding report. Link it from the other pages' navs.

## Prompt 11 — label images

> Render the photographed pack label for each camera-captured checkout from the product's
> registered data (what is really printed), then damage it like a counter camera would: tilt,
> blur, sensor noise, glare, JPEG compression. Pillow optional; skip cleanly without it.

## Prompt 12 — connect the two phases, and a simpler UI

> both phase 1 and phase 2 must be connected, like if we register some product in the database
> then it should be shown on uncertainity phase too... make the ui simple, use simple words, as of
> now, the ui is cluttered and not understandable which component is used for which task, so add
> proper heading for every component, do not add new functionalitites

## Prompt 13 — mistyped codes on Check a medicine

> let say if the prouct is MED-SAM-001 then in schema matching if we mistyped something will it
> verify it? how will algorithm react? let say i typed MED_sam_001

(After the answer showed that the page "corrected" `med sam 001` to a recalled product:)

> yes do it

## Prompt 14 — this report

> make the changes in vibe code page too, add the updated code and add the prompts further

## Prompt 15 — .gitignore

> put the files that are not needed to be pushed on github in gitignore

## Prompt 16 — a registered medicine shown as fake

> databases / 2 pc's are connected, http://192.168.52.152:8011 and http://192.168.52.111:8012, but
> when we are adding a new medicine from the databases page, and then trying to check it on
> matching and cleaning phase we are unable to detect the medicine, it is saying fake... can you
> run the test properly and made the changes if you find the issue
