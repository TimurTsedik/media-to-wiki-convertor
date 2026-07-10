# Course-First Vault Structure Design

Date: 2026-07-10
Status: Approved for implementation planning

## Problem

The generated Obsidian vault currently exposes `Course Materials/` and `Wiki/` as sibling
sections with similar visual weight. This makes the output feel like two competing knowledge
bases instead of one course-oriented knowledge base with supporting reference and evidence
layers.

## Product Model

The default vault should be course-first:

- course materials are the main reading path;
- reference wiki articles are atomic concept pages used by course chapters;
- indexes are navigation and audit tools;
- sources and transcripts are evidence layers, not primary reading surfaces.

## Target Folder Structure

```text
vault/
  00 Start Here.md

  01 Course Materials/
    00 Course Overview.md
    01 Career.md
    02 Architecture.md
    03 AWS.md
    ...
    _Course Index.md

  02 Reference Wiki/
    Career/
      CV.md
      Interview.md
      Seniority.md
    Architecture/
      System Design.md
      Event Driven Architecture.md
    AWS/
      IAM.md
      S3.md
      Lambda.md
    ...

  03 Indexes/
    Articles.md
    Domains.md
    Catalog.md
    Deferred Topics.md
    Unlinked Mentions.md
    Sources.md

  04 Sources/
    Chunks/
      video-a/
        0001.md
        0002.md

  05 Transcripts/
    00 Transcripts.md
    video-a.md
    video-b.md

  99 System/
    Build Report.md
    Generation Notes.md
```

## Rename Map

```text
00 Home.md         ->  00 Start Here.md
Course Materials/  ->  01 Course Materials/
Wiki/              ->  02 Reference Wiki/
Index/             ->  03 Indexes/
Sources/           ->  04 Sources/
90 Transcripts/    ->  05 Transcripts/
90 Transcripts.md  ->  05 Transcripts/00 Transcripts.md
```

## Navigation Contract

`00 Start Here.md` must make the hierarchy explicit:

1. Start with `01 Course Materials/`.
2. Use `02 Reference Wiki/` for atomic concepts and practices.
3. Use `04 Sources/` for transcript chunks and source evidence.
4. Use `05 Transcripts/` only for full raw transcripts.
5. Use `03 Indexes/` for catalog, deferred topics, unresolved links, and audit navigation.

## Link Contract

Generated links must target the new paths:

- course chapters link to `02 Reference Wiki/...` for article pages;
- article source sections link to `04 Sources/Chunks/...`;
- source notes link back to `05 Transcripts/...`;
- index pages live under `03 Indexes/...`;
- existing generated course-map links point inside `01 Course Materials/...`.

Old generated paths should not appear in newly built vaults:

- `Wiki/`
- `Index/`
- `Sources/`
- `Course Materials/`
- `90 Transcripts/`
- `90 Transcripts.md`

## Implementation Surface

The implementation should stay inside the vault-generation layer:

- update managed directory constants;
- centralize folder names and targets so link generation is not string-spliced across the file;
- update `write_home`, article path helpers, course material writers, source writers, transcript writers, and index writers;
- update tests for path generation and rewritten wikilinks;
- update README generated-output docs.

This should not change raw-data artifact formats, LLM prompts, article planning, catalog planning, or course planning.

## Compatibility

This is a generated-vault layout change. Since `build-vault` already rewrites managed folders,
the new structure can be applied on the next vault rebuild. Manual user notes should still stay
outside managed folders unless the user intentionally wants generated output to replace them.

## Acceptance Criteria

- `build-vault` writes the new course-first folder structure.
- `00 Start Here.md` presents course materials as the primary entry point.
- Generated wikilinks resolve to the new folders.
- No old generated folder names remain in a fresh vault build.
- Existing tests are updated and pass.
- README documents the new structure and managed folders.
