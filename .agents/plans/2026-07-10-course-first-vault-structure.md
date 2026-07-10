# Course-First Vault Structure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make generated Obsidian vaults course-first by renaming generated folders, updating wikilinks, and making `00 Start Here.md` present course materials as the primary entry point.

**Architecture:** Keep the change inside the vault-generation layer. Add centralized vault path constants/helpers in `media_to_wiki_convertor/vault.py`, then update writers and link rewriters to use those helpers instead of hard-coded folder names. Raw data, LLM prompts, article planning, catalog planning, and course planning remain unchanged.

**Tech Stack:** Python 3.11+, pytest, ruff, Obsidian-flavored Markdown wikilinks.

---

## File Structure

- Modify `media_to_wiki_convertor/vault.py`: central vault path constants, note target helpers, managed dirs, writers, link rewriting, home/start page rendering.
- Modify `tests/test_vault.py`: path contract tests, full vault build assertions, English localization assertions, course-map/source-link assertions.
- Modify `README.md`: generated-output structure, managed folder warning, course-first navigation description.
- Modify `CHANGELOG.md`: add unreleased entry for course-first vault layout.

No raw-data file formats change. No CLI command names change.

---

### Task 1: Add Course-First Path Contract Tests

**Files:**
- Modify: `tests/test_vault.py`
- Later Modify: `media_to_wiki_convertor/vault.py`

- [ ] **Step 1: Write failing tests for note paths and canonical folder names**

Add this import to `tests/test_vault.py`:

```python
from media_to_wiki_convertor.vault import (
    ARTICLE_ROOT,
    COURSE_ROOT,
    INDEX_ROOT,
    SOURCE_ROOT,
    TRANSCRIPT_ROOT,
)
```

Add this test near `test_note_path_for_title_splits_slash_titles_into_nested_notes`:

```python
def test_course_first_vault_roots_are_numbered_for_obsidian_scanability() -> None:
    assert COURSE_ROOT == "01 Course Materials"
    assert ARTICLE_ROOT == "02 Reference Wiki"
    assert INDEX_ROOT == "03 Indexes"
    assert SOURCE_ROOT == "04 Sources"
    assert TRANSCRIPT_ROOT == "05 Transcripts"
```

Update `test_note_path_for_title_splits_slash_titles_into_nested_notes`:

```python
def test_note_path_for_title_splits_slash_titles_into_nested_notes() -> None:
    assert note_path_for_title("Spec Driven Development") == (
        Path("02 Reference Wiki") / "Spec Driven Development.md"
    )
    assert note_path_for_title("Daily / Standup") == (
        Path("02 Reference Wiki") / "Daily" / "Standup.md"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_course_first_vault_roots_are_numbered_for_obsidian_scanability tests/test_vault.py::test_note_path_for_title_splits_slash_titles_into_nested_notes -q
```

Expected: FAIL because the constants do not exist and `note_path_for_title()` still returns `Wiki/...`.

- [ ] **Step 3: Add minimal path constants and update article path helpers**

In `media_to_wiki_convertor/vault.py`, replace the current `MANAGED_DIRS` line with:

```python
START_HERE_NOTE = "00 Start Here.md"
COURSE_ROOT = "01 Course Materials"
ARTICLE_ROOT = "02 Reference Wiki"
INDEX_ROOT = "03 Indexes"
SOURCE_ROOT = "04 Sources"
TRANSCRIPT_ROOT = "05 Transcripts"
SYSTEM_ROOT = "99 System"

MANAGED_DIRS = (
    COURSE_ROOT,
    ARTICLE_ROOT,
    INDEX_ROOT,
    SOURCE_ROOT,
    TRANSCRIPT_ROOT,
    SYSTEM_ROOT,
)
```

Update `note_path_for_title`:

```python
def note_path_for_title(title: str) -> Path:
    parts = [sanitize_filename_part(part) for part in title.split("/")]
    parts = [part for part in parts if part]
    if not parts:
        parts = ["Untitled"]
    return Path(ARTICLE_ROOT, *parts[:-1], f"{parts[-1]}.md")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_course_first_vault_roots_are_numbered_for_obsidian_scanability tests/test_vault.py::test_note_path_for_title_splits_slash_titles_into_nested_notes -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add media_to_wiki_convertor/vault.py tests/test_vault.py
git commit -m "refactor: introduce course-first vault paths"
```

---

### Task 2: Migrate Main Vault Writers to New Folders

**Files:**
- Modify: `tests/test_vault.py`
- Modify: `media_to_wiki_convertor/vault.py`

- [ ] **Step 1: Write failing full-build assertions**

In `test_build_obsidian_vault_writes_articles_indexes_and_sources`, update the path assertions and key link assertions to the course-first structure:

```python
spec = (vault / "02 Reference Wiki" / "Spec Driven Development.md").read_text(encoding="utf-8")
daily = (vault / "02 Reference Wiki" / "Daily" / "Standup.md").read_text(encoding="utf-8")

assert "[[02 Reference Wiki/Daily/Standup|Daily / Standup]]" in spec
assert "[[05 Transcripts/video-a|Video A]]" in spec
assert "[[04 Sources/Chunks/video-a/0001|video-a/0001]]" in spec
assert "[[02 Reference Wiki/Spec Driven Development|SDD]]" in daily
assert (vault / "00 Start Here.md").exists()
assert (vault / "03 Indexes" / "Articles.md").exists()
assert (vault / "03 Indexes" / "Domains.md").exists()
assert (vault / "03 Indexes" / "Sources.md").exists()
assert (vault / "03 Indexes" / "Catalog.md").exists()
assert (vault / "03 Indexes" / "Catalog" / "software-engineering.md").exists()
assert (vault / "01 Course Materials" / "00 Справочные материалы по курсу.md").exists()
assert (vault / "01 Course Materials" / "software-engineering.md").exists()
assert (vault / "03 Indexes" / "Deferred Topics.md").exists()
assert not (vault / "Wiki").exists()
assert not (vault / "Index").exists()
assert not (vault / "Sources").exists()
assert not (vault / "Course Materials").exists()
assert not (vault / "90 Transcripts").exists()
assert not (vault / "90 Transcripts.md").exists()
```

Update the remaining local variables in that test:

```python
home = (vault / "00 Start Here.md").read_text(encoding="utf-8")
catalog_index = (vault / "03 Indexes" / "Catalog.md").read_text(encoding="utf-8")
catalog_category = (
    vault / "03 Indexes" / "Catalog" / "software-engineering.md"
).read_text(encoding="utf-8")
course_index = (
    vault / "01 Course Materials" / "00 Справочные материалы по курсу.md"
).read_text(encoding="utf-8")
course_chapter = (vault / "01 Course Materials" / "software-engineering.md").read_text(
    encoding="utf-8"
)
sources_index = (vault / "03 Indexes" / "Sources.md").read_text(encoding="utf-8")
source_note = (
    vault / "04 Sources" / "Chunks" / "video-a" / "0001.md"
).read_text(encoding="utf-8")
deferred_source_note = (
    vault / "04 Sources" / "Chunks" / "video-c" / "0003.md"
).read_text(encoding="utf-8")
transcript_index = (vault / "05 Transcripts" / "00 Transcripts.md").read_text(
    encoding="utf-8"
)
transcript_note = (vault / "05 Transcripts" / "video-a.md").read_text(encoding="utf-8")
```

Expected link assertions in the same test:

```python
assert "[[03 Indexes/Catalog|Catalog]]" in home
assert (
    "[[01 Course Materials/00 Справочные материалы по курсу|Справочные материалы по курсу]]"
    in home
)
assert "[[03 Indexes/Catalog/software-engineering|Software Engineering]]" in catalog_index
assert "[[01 Course Materials/software-engineering|Software Engineering]]" in course_index
assert "[[02 Reference Wiki/Spec Driven Development|Spec Driven Development]]" in course_chapter
assert "[[04 Sources/Chunks/video-c/0003|video-c/0003]]" in course_chapter
assert "[[02 Reference Wiki/Spec Driven Development|Spec Driven Development]]" in catalog_category
assert "[[02 Reference Wiki/Deferred Topic" not in catalog_category
assert "[[04 Sources/Chunks/video-c/0003|video-c/0003]]" in catalog_category
assert "[[03 Indexes/Catalog/software-engineering|Deferred Topic]]" in sources_index
assert "[[02 Reference Wiki/Deferred Topic" not in sources_index
assert "[[05 Transcripts/video-a|Video A]]" in source_note
assert "[[05 Transcripts/video-c|Video C]]" in deferred_source_note
assert "[[03 Indexes/Catalog/software-engineering|Deferred Topic]]" in deferred_source_note
assert "[[05 Transcripts/video-a|Video A]]" in transcript_index
assert "[[04 Sources/Chunks/video-a/0001|video-a/0001]]" in transcript_note
```

- [ ] **Step 2: Run the full-build test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_build_obsidian_vault_writes_articles_indexes_and_sources -q
```

Expected: FAIL because writers still use old folders.

- [ ] **Step 3: Add target helper functions in `vault.py`**

Add these helpers below `note_target_for_title`:

```python
def course_target(path: str = "") -> str:
    return slash_join(COURSE_ROOT, path)


def index_target(path: str = "") -> str:
    return slash_join(INDEX_ROOT, path)


def source_chunk_target(video_id: str, chunk_id: str) -> str:
    return slash_join(SOURCE_ROOT, "Chunks", video_id, chunk_id)


def transcript_target(video_id: str) -> str:
    return slash_join(TRANSCRIPT_ROOT, video_id)


def slash_join(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part)
```

- [ ] **Step 4: Update article, index, source, transcript writers**

Update hard-coded targets in `vault.py`:

```python
write_text(vault / INDEX_ROOT / "Articles.md", render_articles_index(pages))
write_text(vault / INDEX_ROOT / "Domains.md", render_domains_index(pages))
write_text(vault / INDEX_ROOT / "Sources.md", render_sources_index(source_pages, records_by_id))
write_text(vault / INDEX_ROOT / "Deferred Topics.md", render_deferred_index(...))
write_text(vault / INDEX_ROOT / "Unlinked Mentions.md", render_unlinked_mentions(...))
```

Update source links:

```python
f"[[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]"
```

Update transcript links:

```python
return f"[[{transcript_target(record.video_id)}|{record.title}]]"
```

Update transcript note writes:

```python
write_text(vault / TRANSCRIPT_ROOT / "00 Transcripts.md", ...)
write_text(vault / TRANSCRIPT_ROOT / f"{record.video_id}.md", ...)
```

Update source note writes:

```python
write_text(vault / SOURCE_ROOT / "Chunks" / video_id / f"{chunk_id}.md", ...)
```

Update catalog links:

```python
return f"[[{index_target(f'Catalog/{catalog_key}')}|{title}]]"
```

- [ ] **Step 5: Run the full-build test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_build_obsidian_vault_writes_articles_indexes_and_sources -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add media_to_wiki_convertor/vault.py tests/test_vault.py
git commit -m "feat: write course-first vault folders"
```

---

### Task 3: Migrate Course Material Link Rewriting

**Files:**
- Modify: `tests/test_vault.py`
- Modify: `media_to_wiki_convertor/vault.py`

- [ ] **Step 1: Update course link rewriter tests**

In `test_rewrite_course_material_links_rewrites_llm_source_refs_to_chunk_links`, replace expected source link prefixes:

```python
assert "[[04 Sources/Chunks/f323d805b520/0011|f323d805b520/0011]]" in rewritten
assert "[[04 Sources/Chunks/307869628eba/0004|307869628eba/0004]]" in rewritten
assert "[[04 Sources/Chunks/14c6fbca1e96/0002|14c6fbca1e96/0002]]" in rewritten
assert "[[04 Sources/Chunks/14c6fbca1e96/0003|14c6fbca1e96/0003]]" in rewritten
assert "[[04 Sources/Chunks/18797da45247/0005|18797da45247/0005]]" in rewritten
assert "[[04 Sources/Chunks/18797da45247/0002|18797da45247/0002]]" in rewritten
assert "[[04 Sources/Chunks/903e979351ee/0004|903e979351ee/0004]]" in rewritten
assert "[[04 Sources/Chunks/7d1f2472d5ed/0007|7d1f2472d5ed/0007]]" in rewritten
assert "[[04 Sources/Chunks/8dac023c7ead/0002|8dac023c7ead/0002]]" in rewritten
assert "[[04 Sources/Chunks/3eef9508e333/0003|3eef9508e333/0003]]" in rewritten
assert "[[04 Sources/Chunks/dc51bf126b22/0008|dc51bf126b22/0008]]" in rewritten
assert "[[04 Sources/Chunks/9eb1cccd1e24/0010|9eb1cccd1e24/0010]]" in rewritten
assert "[[04 Sources/Chunks/9e4e5e61cab0/0011|9e4e5e61cab0/0011]]" in rewritten
assert "[[04 Sources/Chunks/9e4e5e61cab0/0004|9e4e5e61cab0/0004]]" in rewritten
assert "[[04 Sources/Chunks/8dac023c7ead/0005|8dac023c7ead/0005]]" in rewritten
assert "[[04 Sources/Chunks/492d35edaba6/0007|492d35edaba6/0007]]" in rewritten
assert "[[04 Sources/Chunks/f323d805b520/0011|готовая ссылка]]" in rewritten
assert "[[02 Reference Wiki/AWS Bedrock|AWS Bedrock]]" in rewritten
```

In map-link tests, replace course targets:

```python
assert "- [[01 Course Materials/software-engineering#Deferred Topic|Deferred Topic]]" in rewritten
assert "- [[01 Course Materials/software-engineering#Полный список подтем и источников|Missing Topic]]" in rewritten
assert "- [[01 Course Materials/devops#CI/CD и monorepository|CI/CD]]" in rewritten
assert "- [[01 Course Materials/devops#CI/CD and monorepository|CI/CD]]" in rewritten
assert "- [[01 Course Materials/devops#Full Topic and Source Index|Missing Topic]]" in rewritten
```

- [ ] **Step 2: Run rewritten-link tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_rewrite_course_material_links_rewrites_llm_source_refs_to_chunk_links tests/test_vault.py::test_rewrite_course_material_map_links_links_articles_and_local_headings tests/test_vault.py::test_rewrite_course_material_map_links_fuzzy_matches_heading_titles tests/test_vault.py::test_rewrite_course_material_map_links_handles_english_section_headings -q
```

Expected: FAIL because rewriters still emit old `Sources/` and `Course Materials/` targets.

- [ ] **Step 3: Update rewriter prefixes and generated targets**

In `rewrite_course_material_links`, update:

```python
known_vault_prefixes = (
    f"{ARTICLE_ROOT}/",
    f"{SOURCE_ROOT}/",
    f"{COURSE_ROOT}/",
    f"{INDEX_ROOT}/",
    f"{TRANSCRIPT_ROOT}/",
)
```

In `rewrite_course_material_map_links`, update course material targets:

```python
rewritten_lines.append(f"- [[{course_target(f'{chapter_key}#{label}')}|{label}]]")
rewritten_lines.append(f"- [[{course_target(f'{chapter_key}#{heading}')}|{label}]]")
rewritten_lines.append(f"- [[{course_target(f'{chapter_key}#{reference_anchor}')}|{label}]]")
```

In `rewrite_course_material_source_refs.source_link`, update return:

```python
return f"[[{source_chunk_target(video_id, chunk_id)}|{video_id}/{chunk_id}]]"
```

In `catalog_topic_source_links`, use `source_chunk_target`.

- [ ] **Step 4: Run rewritten-link tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_rewrite_course_material_links_rewrites_llm_source_refs_to_chunk_links tests/test_vault.py::test_rewrite_course_material_map_links_links_articles_and_local_headings tests/test_vault.py::test_rewrite_course_material_map_links_fuzzy_matches_heading_titles tests/test_vault.py::test_rewrite_course_material_map_links_handles_english_section_headings -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add media_to_wiki_convertor/vault.py tests/test_vault.py
git commit -m "fix: rewrite links for course-first vault"
```

---

### Task 4: Make Start Page Course-First

**Files:**
- Modify: `tests/test_vault.py`
- Modify: `media_to_wiki_convertor/vault.py`

- [ ] **Step 1: Write failing assertions for `00 Start Here.md` hierarchy**

In `test_build_obsidian_vault_writes_articles_indexes_and_sources`, add:

```python
assert "# Start Here" in home
assert "## Read First" in home
assert "[[01 Course Materials/00 Справочные материалы по курсу|Справочные материалы по курсу]]" in home
assert "[[02 Reference Wiki/Spec Driven Development|Spec Driven Development]]" in home
assert "[[04 Sources" in home
assert "[[05 Transcripts/00 Transcripts|Transcripts]]" in home
```

In `test_build_obsidian_vault_localizes_course_materials_to_english`, update:

```python
home = (vault / "00 Start Here.md").read_text(encoding="utf-8")
assert "# Start Here" in home
assert "## Read First" in home
assert "[[01 Course Materials/00 Course Reference Materials|Course Reference Materials]]" in home
assert "[[05 Transcripts/00 Transcripts|Transcripts]]" in home
```

In `test_build_obsidian_vault_omits_catalog_link_when_catalog_is_missing`, update:

```python
home = (vault / "00 Start Here.md").read_text(encoding="utf-8")
assert "[[03 Indexes/Catalog|Catalog]]" not in home
assert not (vault / "03 Indexes" / "Catalog.md").exists()
```

- [ ] **Step 2: Run start-page tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_build_obsidian_vault_writes_articles_indexes_and_sources tests/test_vault.py::test_build_obsidian_vault_localizes_course_materials_to_english tests/test_vault.py::test_build_obsidian_vault_omits_catalog_link_when_catalog_is_missing -q
```

Expected: FAIL until `write_home` becomes course-first.

- [ ] **Step 3: Update `write_home` to render `00 Start Here.md`**

Replace the top of `lines` in `write_home` with:

```python
lines = [
    "# Start Here",
    "",
    "## Read First",
]
if has_course_materials:
    lines.append(
        f"- [[{course_target(f'00 {labels.course_materials_title}')}|{labels.course_materials_title}]]"
    )
lines.extend(
    [
        "- Use reference wiki pages for atomic concepts and practices.",
        "- Use source chunks when you need evidence from transcripts.",
        "- Use full transcripts only when you need the raw original text.",
        "",
        f"## {labels.navigation}",
    ]
)
```

Render navigation links with helpers:

```python
navigation = [
    f"- [[{index_target('Articles')}|Articles]]",
    f"- [[{index_target('Domains')}|Domains]]",
]
if has_catalog:
    navigation.append(f"- [[{index_target('Catalog')}|Catalog]]")
if has_course_materials:
    navigation.append(
        f"- [[{course_target(f'00 {labels.course_materials_title}')}|{labels.course_materials_title}]]"
    )
navigation.extend(
    [
        f"- [[{index_target('Sources')}|Sources]]",
        f"- [[{transcript_target('00 Transcripts')}|Transcripts]]",
        f"- [[{index_target('Deferred Topics')}|Deferred Topics]]",
        f"- [[{index_target('Unlinked Mentions')}|Unlinked Mentions]]",
    ]
)
```

Write to the new start note:

```python
write_text(vault / START_HERE_NOTE, "\n".join(lines) + "\n")
```

- [ ] **Step 4: Run start-page tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider tests/test_vault.py::test_build_obsidian_vault_writes_articles_indexes_and_sources tests/test_vault.py::test_build_obsidian_vault_localizes_course_materials_to_english tests/test_vault.py::test_build_obsidian_vault_omits_catalog_link_when_catalog_is_missing -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add media_to_wiki_convertor/vault.py tests/test_vault.py
git commit -m "feat: make vault start page course-first"
```

---

### Task 5: Update README and Changelog

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update README generated output section**

Replace the current vault structure list in `README.md` with:

```markdown
The vault is course-first:

- `00 Start Here.md` - primary entry point.
- `01 Course Materials/` - structured course reference chapters.
- `02 Reference Wiki/` - atomic concept and practice pages.
- `03 Indexes/` - catalog, articles, domains, deferred topics, unresolved links, and source indexes.
- `04 Sources/` - transcript chunk evidence notes.
- `05 Transcripts/` - full transcript notes and file links.
- `99 System/` - generated system/build notes when present.
```

Replace the managed folders list with:

```markdown
`build-vault` treats these vault paths as generated output and rewrites them on every run:

- `00 Start Here.md`
- `01 Course Materials/`
- `02 Reference Wiki/`
- `03 Indexes/`
- `04 Sources/`
- `05 Transcripts/`
- `99 System/`
```

- [ ] **Step 2: Update CHANGELOG**

Under `## Unreleased`, add:

```markdown
- Make generated Obsidian vaults course-first with numbered folders for course materials, reference wiki pages, indexes, sources, and transcripts.
```

- [ ] **Step 3: Run docs grep check**

Run:

```bash
rg -n "Course Materials/|Wiki/|Index/|Sources/|90 Transcripts|00 Home" README.md CHANGELOG.md
```

Expected: any remaining old names are historical explanations or explicitly marked as old paths. Fresh generated-output docs use numbered course-first folders.

- [ ] **Step 4: Commit**

```bash
git add README.md CHANGELOG.md
git commit -m "docs: document course-first vault layout"
```

---

### Task 6: Full Verification and Push

**Files:**
- No planned code edits.

- [ ] **Step 1: Run full tests**

Run:

```bash
.venv/bin/python -m pytest -p no:cacheprovider -q
```

Expected:

```text
144 passed
```

The exact count may increase if new tests were added beyond this plan.

- [ ] **Step 2: Run ruff**

Run:

```bash
env RUFF_CACHE_DIR=/private/tmp/media-to-wiki-ruff-cache .venv/bin/python -m ruff check .
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run CLI smoke**

Run:

```bash
tmp_project="$(mktemp -d /private/tmp/mtw-course-first-XXXXXX)/project"
.venv/bin/media-to-wiki-convertor init "$tmp_project"
cd "$tmp_project"
"/Users/timur555/projects/PycharmProjects/Other/larchenko training/.venv/bin/media-to-wiki-convertor" status
"/Users/timur555/projects/PycharmProjects/Other/larchenko training/.venv/bin/media-to-wiki-convertor" run --dry-run
```

Expected:

```text
Media To Wiki Convertor pipeline
Pipeline dry run:
...
- healthcheck
...
```

- [ ] **Step 4: Inspect final diff**

Run:

```bash
git status --short
git log --oneline -5
```

Expected: working tree clean after task commits; recent commits correspond to the tasks above.

- [ ] **Step 5: Push**

Run:

```bash
git push
```

Expected: `main -> main`.

- [ ] **Step 6: Check GitHub Actions**

Run:

```bash
gh run list --repo TimurTsedik/media-to-wiki-convertor --branch main --limit 5
```

Expected: latest workflow for this feature is `completed success`.

---

## Self-Review

Spec coverage:

- Course-first structure: Tasks 1, 2, and 4.
- Rename map: Tasks 1, 2, and 3.
- Navigation contract: Task 4.
- Link contract: Tasks 2 and 3.
- Implementation surface limited to vault generation and docs: Tasks 1-5.
- Compatibility and managed folder documentation: Task 5.
- Verification: Task 6.

No raw-data, LLM prompt, article plan, catalog plan, or course plan changes are included.
