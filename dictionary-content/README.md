# Dictionary content for 1.1

This is the editable source for both the bundled database and future remote releases. The current content is the accepted launch baseline; remaining linguistic review is deferred. Baseline acceptance is not editorial approval.

## Edit a word

Find its JSON file in `entries/` by searching for the word. Each file holds one sense with its Cyrillic, Latin, and English text. Correct the text in that file; keep its `id` unchanged. Distinct meanings can have distinct IDs even when their headwords match.

IDs 1–1106 preserve existing bundled identities. The ten month additions use IDs 1000000001–1000000010 to avoid interpreting old installation-dependent month IDs as different words. Allocate subsequent additions above 1000000010 and never reuse an ID. A removed legacy link may become unavailable; it must not point to an unrelated entry.

`corrections-1.1.json` records the initial cleanup as before/after fields. That cleanup removes mixed scripts and whitespace, fills number definitions, and fixes selected clear spelling/example errors. It does not resolve every issue in `reviews/dictionary-audit.md`. Ten month entries from the legacy feed are preserved with canonical IDs.

## Build a development dictionary

From the app repository root:

```sh
python3 scripts/build_dictionary.py --seed serbDictionary/dictionary.db
```

This validates structure, creates `build/dictionary/dictionary.json`, and regenerates the bundled SQLite database from the same records. Its output lists how many entries still need editorial approval. Releases allow unchanged launch-baseline entries. New or changed entries require exact-file editorial approval.

Raise `revision` in `review.json` whenever shipping changed content, including a changed bundled seed. Installed clients never replace a revision with the same or a lower revision. The content revision is independent of app version 1.1 and independent of the obsolete legacy feed version.

## Review and approve

Read each entry for translation accuracy, grammar, natural examples, and correct script correspondence. Resolve applicable findings in the prior audit. Automated validation cannot approve meanings.

The generated `build/dictionary/review-status.json` contains hashes of the exact entry files. After editorial review, add that entry's ID and hash to `approvedEntries` in `review.json`. Any later edit changes the hash and requires review again. Do not bulk-copy hashes just to bypass the release gate.

`launch-baseline.json` freezes the hashes of the current 1.1 bundled entries, following the decision to defer remaining corrections. Do not regenerate it when editing words. Unchanged baseline entries may be published without being labeled reviewed; changed/new entries require approval.

## Prepare the free GitHub backend

Copy `dictionary-content/` and `scripts/build_dictionary.py` into the root of the existing `serbian-dictionary-updates` repository. Copy `publish-workflow.yml` from this folder to `.github/workflows/publish-dictionary.yml` in that repository. Keep its existing `updates.json` unchanged for legacy clients.

The workflow is manually dispatched with a content revision. It requires an exact match with `review.json`, validates changed/new-entry approvals, rejects reused release tags, publishes `dictionary.json` as a GitHub Release asset, then updates `v1/manifest.json` last. It uses standard Ubuntu runners in the existing public repository. No paid backend service or secret in the app is needed; GitHub provides the workflow token.

The app reads `https://raw.githubusercontent.com/ljmakaronica/serbian-dictionary-updates/main/v1/manifest.json`. Until that file is published, background refresh quietly retains the bundled dictionary and manual refresh reports that updates are unavailable.

The workflow file is a deployment template; it has not been installed or run remotely. The repository needs Actions enabled and workflow write permissions for contents. The repository's branch rules may also require a reviewed pull request for manifest changes; adapt publication to those rules rather than bypassing them.

## Revert a published content mistake

Restore the previously approved entry text, increment the content revision, reapprove the exact files, and publish a new release. Never edit a published asset, reuse a tag, or lower the manifest revision. The client checks SHA-256 and byte count before installing. The checksum detects corruption or mismatched artifacts; it is not independent publisher authentication.

## Verification

```sh
python3 -m unittest discover -s scripts -p 'test_*.py'
```

Run the SharedDictionaryTests target in Xcode for atomic rollback, repeated installation, Unicode, manifest validation, seed migration, and widget-reader behavior.
