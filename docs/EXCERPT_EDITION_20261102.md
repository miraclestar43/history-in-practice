# 原文精选: the first sample (2026-11-02)

**What changed.** A new edition kind, `excerpt`: the author's own text as the body, with a short editor's introduction, a few notes, an optional afterword, where to read on, and a paragraph-for-paragraph AI translation into the other language. Each part is labelled.

**The chain** (`src/history_in_practice/excerpt.py`, prompts `excerpt_*.md`, all Claude Opus via the Claude Code CLI):
1. **select:** the model reads a numbered window of a library book and returns the paragraph range, any whole-paragraph omissions, an editor's title, why it chose the passage and why it stands alone. It never returns text.
2. **extract** (program): takes the paragraphs from the saved book file. Chapter-heading lines are dropped, since they appear in the byline, and the location is kept.
3. **guide:** dek, introduction, a name list, notes keyed to a term that appears verbatim in its paragraph, an optional afterword and a read-on line, both languages.
4. **translate:** one output paragraph per paragraph, using the name list, labelled AI translation.
5. **review** (twice): selection, missing context, references, unsupported claims in the guide, translation fidelity. Fixes may replace the editor's text or a translation paragraph, never the original.
6. **checks** (program):
   - every displayed original paragraph equals the source paragraph and is in the source cache;
   - skipped paragraphs carry 〔中略〕;
   - one translation per paragraph;
   - every note's term is in its paragraph.

**Sample:** 容闳 Yung Wing, *My Life in China and America* (Henry Holt, 1909; Project Gutenberg #54635; public domain).
- **Choice:** the agent was given chapters XII–XV and chose all of chapter XII, "Expedition to the Taiping Tea District" (paragraphs 233–244).
- **Reading time:** about 15 minutes (zh, AI translation) / 18 (en, original).
- **Checks:** 0 problems.
- **Review:**
  - round 1 fixed two errors in the introduction;
  - round 2 left one unsupported phrase in the Chinese dek ("无人认领"; the book says the rebels held the tea). The reviewer's own wording was applied by the operator and recorded.
- **Operator change:** the two chapter-heading paragraphs were dropped from the passage, and `extract` now does this itself.

**Where to read it:** the TEST preview site only: https://hip-test-20261030.website-test-7i3.pages.dev/history/?story=excerpt-20261102-yungwing-1&lang=zh. The email was rendered for preview and not sent. Nothing is scheduled, nothing reached starhub.vip, and the send time and recipients are unchanged.

**Not yet:** an excerpt edition is not yet admitted into inventory or scheduled. Admission, schedule and send integration come after the owner judges the reading experience.
