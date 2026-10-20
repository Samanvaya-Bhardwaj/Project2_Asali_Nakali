"""
integration.uncertainty
-----------------------
Phase 2: data integration under uncertainty.

The four silos record the same medicine pack independently, and each records it
imperfectly. A pharmacist types a serial by hand, a phone camera reads a label
through glare, a warehouse clerk re-keys a dispatch note, a citizen types a code
into a complaint form. This package turns those imperfect records into linked,
cleansed ones without erasing the evidence of fraud they also contain.

Modules
  paths         where the live databases and generated artefacts live
  similarity    the classic string metrics, implemented here so they can be compared
  noise         a typed noise channel (OCR, keyboard, transposition, ...) used to
                generate data and to augment the benchmark
  confusion     a noisy-channel edit distance whose substitution costs are learned
                from (observed, true) pairs
  standardize   format canonicalisation: codes, dates, currency, vendor ids, labels
  context       a live snapshot of the silos used as matching evidence
  linkage       blocking + Fellegi-Sunter scoring + posterior over candidates and
                an explicit "no registered product" hypothesis
  cleanser      scan / plan / apply / undo, with a lineage log
  train         fits the model on a training split and benchmarks every algorithm
                on the held-out split
  http_api      endpoints shared by both nodes
"""
