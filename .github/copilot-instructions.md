---
name: teleportdog instructions
description: Copilot guidance for contributing to teleportdog
applyTo: "**"
---

# Copilot Instructions for teleportdog

Thank you for working on teleportdog! This is a tiny, offline, dependency-free chat assistant. The spirit of the project is clarity, minimalism, and transparency about what it can and can't do.

## Project Philosophy

- **Zero dependencies**: Python 3.12 standard library only. No PyPI packages. This keeps the project portable, inspectable, and offline-capable.
- **Hybrid responses over pure generation**: Three-path architecture (intent rules → retrieval → fallback). This avoids overfitting and maintains coherence with tiny models.
- **Quality over coverage**: Better to silently fall back to a generic response than to emit noisy generated text. Err on the side of caution.
- **Transparent architecture**: All response paths and filtering logic are explicit in the code. Future contributors should understand *why* decisions were made, not just *what* they do.
- **Session context is fundamental**: Every chat starts with `SESSION_CONTEXT_SNIPPETS` to give the model stable, consistent behavior guidance. Changes here affect all sessions.

## Before You Start

1. **Read `docs/DEVELOPER_CONSTRAINTS.md`** — explains the three response paths, definitions of "not parroting", what the system excels at, and known limitations.
2. **Read `docs/CORPUS_EXPANSION.md`** — if you're working on corpus ingestion, filtering, or knowledge management.
3. **Understand the architecture**:
   - `teleportdog/lm.py`: tiny char n-gram model (generate method exists; use with caution and quality thresholds).
   - `teleportdog/t9.py`: T9 encoding/decoding and word suggestion.
   - `teleportdog/chat.py`: session init, intent routing, retrieval, learning, persistence, state management.
   - `teleportdog/cli.py`: interactive loop, command parsing, readline support (optional on OS).

## Common Patterns

### Adding a New Command

1. Add the command name to `_COMMANDS` list in `cli.py` if it's tab-completable.
2. Add a handler in the `if raw.startswith("/"):` section of `run_chat()`.
3. Update `HELP_TEXT` with usage and description.
4. Update `README.md` commands section.
5. Test with: `printf '/newcmd\n/quit\n' | teleportdog --state /tmp/test.json`

### Modifying Response Paths

The reply paths are (in order):
1. **Intent rules**: hand-coded responses for common prompts in `reply()` method — fast, safe, predictable.
2. **Retrieval**: keyword-based sentence matching from learned knowledge bank via `_top_sentences()` — contextual, stable.
3. **Fallback**: rotating generic responses or optional generation — graceful, never errors.

If modifying any of these, add comments explaining *why* you're changing the order or thresholds. Quality scoring logic should be explicit.

### Working with Corpus Ingestion

- Sentences are ingested in `_split_sentences()` with aggressive filtering:
  - Markdown/code blocks are stripped.
  - Lines that look like structured metadata (JSON/YAML style) are rejected.
  - Very short sentences (<5 chars) are dropped.
  - "assistant:" prefixes are stripped before storage.
- Retrieval uses `_top_sentences()` which:
  - Keyword-matches against the user prompt.
  - Deduplicates near-identical sentences.
  - Avoids returning sequential "Also:" lines if they're near-duplicates.
- If adding new corpus sources, consider what noise they introduce. Test with real data.

### Quality Scoring for Generation

Generated candidates are scored by:
- Character distribution (avoid repetitive patterns like "43556").
- Spacing uniformity (avoid bunched punctuation).
- Length (avoid too-short or too-long outputs).
- Relevance to user prompt (keyword overlap).

If generation quality regresses, check:
1. Temperature settings (lower = more conservative).
2. Multi-candidate sampling count.
3. Quality threshold (minimum score to use a candidate).
4. Fallback triggers (definition-style prompts auto-fall-back to retrieval).

## Testing & Validation

- **Syntax check**: `python3.12 -m py_compile teleportdog/*.py`
- **Import check**: `python3 -c "from teleportdog import chat, cli, lm, t9; print('OK')"`
- **Smoke test**: `printf 'Hello\n/quit\n' | teleportdog --state /tmp/test.json`
- **Corpus test**: `teleportdog --corpus ./docs/**/*.md --state /tmp/test.json`
- **Tab completion test**: Verify readline is not broken. Test `/mod` + Tab.
- **State persistence**: Run a session, save, restart, verify state is loaded.

## Code Style

- **Readable over clever**: small functions, clear variable names, explicit logic.
- **Comments for *why*, not *what***: the code shows what; comments should explain intent.
- **Type hints welcome** but not required (project uses `from __future__ import annotations` for forward refs).
- **No external dependencies**: if you're tempted to `import` something from PyPI, reconsider the design.

## Branching & Commits

- Use clear, descriptive commit messages: "Add tab completion for commands" not "fix stuff".
- One logical change per commit when possible.
- Test before committing: at minimum run smoke tests.
- Update `README.md` and relevant docs files if your change affects user-facing behavior.

## If You Encounter Issues

1. **Noisy retrieval**: Check `_is_usable_sentence()` filters. Does your corpus have metadata/markup that should be rejected?
2. **Generation falling back too much**: Raise the quality threshold or inspect actual candidate scores with temporary debug output.
3. **T9 lookups returning wrong words**: T9 index is built during corpus ingest; check `t9.py` for encoding bugs or run `/suggest` to inspect suggestions.
4. **Session context not working**: Verify `SESSION_CONTEXT_SNIPPETS` version matches; old sessions use old context.
5. **Readline not completing**: Check if `readline` is available (`python3 -c "import readline"` should not error); tab completion only works if readline is present.

## Git Workflow

```bash
# Make changes in a feature branch
git checkout -b feature/your-feature

# Test thoroughly
python3.12 -m py_compile teleportdog/*.py
printf 'Hello\n/quit\n' | teleportdog

# Commit with clear message
git add .
git commit -m "Add your feature"

# Push and create PR
git push origin feature/your-feature
```

## Questions?

If something feels confusing or limits what you're trying to do, it's probably intentional — but check the docs first. If the docs don't explain it, that's a gap we should fix.

---

**Last updated**: March 2026  
**Project**: teleportdog (offline tiny chat, zero dependencies)  
**License**: MIT
