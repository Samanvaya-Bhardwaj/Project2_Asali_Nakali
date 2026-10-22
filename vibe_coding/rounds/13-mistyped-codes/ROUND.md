# Prompt 13: mistyped codes on Check a medicine

> let say if the prouct is MED-SAM-001 then in schema matching if we mistyped something will it
> verify it? how will algorithm react? let say i typed MED_sam_001

> yes do it

What the code does now (details in part 3, change 22):

* The page sends the code as typed; the PCs read it against the live registry and say how they read
  it (formatting, look-alike characters, batch number, product name).
* A code typed without dashes (`MEDSAM001`) is tidied, not matched as a brand name.
* A closer miss (`MED-SAN-001`) is checked as typed, with a "Did you mean MED-SAM-001?" button from
  the Phase 2 matcher: a fake can carry a near-miss code, so it is never checked in its place.
