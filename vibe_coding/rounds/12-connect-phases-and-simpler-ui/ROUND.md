# Prompt 12: connect the two phases, and a simpler UI

> both phase 1 and phase 2 must be connected, like if we register some product in the database
> then it should be shown on uncertainity phase too... make the ui simple, use simple words, as of
> now, the ui is cluttered and not understandable which component is used for which task, so add
> proper heading for every component, do not add new functionalitites

What the code does now (details in part 3, changes 17–21):

* Every write a PC accepts is copied to the other PC, so a product registered on the Databases page
  (PC2) appears on Matching & cleaning (PC1). New module `integration/replication.py`; both node
  servers and `assets/cluster.js` send and accept the copy.
* Check a medicine draws the product, journey and evidence from the live databases instead of 22
  stored examples (`api/verify_item.py` builds the dossier).
* Every page has a plain title, a guide to its parts, and a numbered heading with a "Use this to…"
  line for each part; jargon replaced; shared navigation; phone layout fixed.
