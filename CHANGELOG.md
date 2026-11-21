# Changelog

All notable changes to WeRead2Notion AI are documented in this file.

The project remains free and open source. Documentation updates are kept here
so users can quickly see what changed without affecting the sync workflow.

## Unreleased

- Nest a personal thought under its matching highlight when WeRead provides a unique source range or matching source text; keep chapter reviews and ambiguous matches separate.
- Retry dropped connections to Notion without repeating a request that could create duplicate rows or blocks.
- Keep a book's previous notes when writing the new ones fails, and retry the book on the next sync, including after an interrupted run.
- Continue with the remaining books when Notion rejects one book's notes; the book is listed in the sync summary.
- Stop truncating highlights and thoughts longer than 2000 characters.
- Rebuild every book's notes once on the next sync, so pages left with truncated or unfinished notes by earlier versions are repaired.
- Update each day's period relations once per day instead of once per highlight, which shortens full rebuilds.
- Export audiobooks and the article collection from their shelf entry, continue after an unreadable book, and keep both files when two books share a title.
- Treat blank optional environment variables as unset.
- Queue overlapping sync workflow runs instead of letting them write to Notion at the same time.

## v1.0.2 - 2026-08-14

- Added one daily reading snapshot per shelf book, including cumulative and daily reading time.
- Reused the same snapshot during repeated syncs on the same day.
- Preserved historical snapshots when books leave the shelf.
- Restored the Notion icon used when creating new category pages.
- Added regression coverage for snapshot synchronization and category creation.

## v1.0.1

- Improved project documentation, release metadata, and GitHub discoverability.

## v1.0.0

- First stable release of the WeRead-to-Notion synchronization workflow.
