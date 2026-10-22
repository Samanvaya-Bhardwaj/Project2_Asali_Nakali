# Prompt 15: keep unneeded files off GitHub

> put the files that are not needed to be pushed on github in gitignore

What changed (details in part 3, change 24):

* `.gitignore` now covers Python caches, OS and editor files, runtime state the nodes rewrite on
  every run (activity log, audit ledger, cleansing history, incident reports, SQLite journals),
  and personal reference material the project never uses (screenshots, reference images, course
  PDFs, scratch work, an empty fonts folder, the old dashboard).
* Rules for top-level folders start with `/`, so `dashboard/assets/fonts/`, which the site uses,
  stays in the repository.
* The 77 files that were already committed were untracked (`git rm --cached`); they stay on disk.
