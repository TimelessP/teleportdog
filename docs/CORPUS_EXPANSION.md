# Expanding Teleportdog Corpus

This guide explains how to grow teleportdog's knowledge safely and predictably.

## Mental Model

teleportdog learns from text chunks. Sources are loaded in this order:

1. Built-in bootstrap corpus in `teleportdog/data/bootstrap_corpus.txt`
2. Session initialization context (built-in assistant behavior hints)
3. Optional external corpus files/globs from `--corpus`
4. Live conversation turns while you chat

Everything is local. No internet is required.

## Quick Start

Primary invocation:

```bash
teleportdog ...
```

Fallback invocation (if console scripts are not on your shell path):

```bash
python3.12 -m teleportdog ...
```

Use one extra file:

```bash
teleportdog --corpus ./my-notes/product-faq.txt
```

You can also import more corpus while the chat is already running:

```text
/learnglob ./my-notes/**/*.md
```

`/learnglob` accepts the same input styles as `--corpus`:

- a single file path
- a directory path
- a glob pattern

Use multiple sources:

```bash
teleportdog \
  --corpus ./my-notes/product-faq.txt \
  --corpus ./my-notes/style-guide.md
```

Use glob patterns:

```bash
teleportdog --corpus "./corpus/**/*.txt"
```

Use a directory (recursively scans text-like files):

```bash
teleportdog --corpus ./corpus
```

Combine files, dirs, and globs:

```bash
teleportdog \
  --corpus ./corpus \
  --corpus "./team-notes/**/*.md" \
  --corpus ./faq.txt
```

## Supported External File Types

When a directory or glob resolves to files, teleportdog automatically loads:

- `.txt`
- `.md`
- `.markdown`
- `.text`
- `.log`
- `.jsonl`
- `.csv`

Direct file paths are loaded as-is.

## How Chunking Works

Each loaded file is split by blank lines. Each paragraph-style block becomes one learning chunk.

Tip: keep related ideas in the same paragraph so the model learns coherent units.

## State and Repeat Runs

By default, state is saved at:

- `~/.teleportdog/state.json`

You can use a custom state file:

```bash
teleportdog --state ./state/team-bot.json --corpus ./corpus
```

To avoid relearning the exact same corpus file repeatedly, teleportdog stores import signatures (path + size + modified time). If the file changes, it is learned again.

## Typical Usage Patterns

One-off focused assistant:

```bash
teleportdog \
  --state ./state/support-bot.json \
  --corpus ./support/faq.txt
```

Team handbook assistant:

```bash
teleportdog \
  --state ./state/handbook-bot.json \
  --corpus "./handbook/**/*.md"
```

Project changelog assistant:

```bash
teleportdog \
  --state ./state/changelog-bot.json \
  --corpus ./CHANGELOG.md \
  --corpus "./releases/*.txt"
```

## Corpus Writing Tips

- Prefer short, factual sentences.
- Put definitions and examples close together.
- Avoid contradictory statements across files.
- Use consistent naming for products and features.
- Keep noisy machine logs minimal unless log analysis is your goal.

## Troubleshooting

No visible impact after adding corpus:

- Check your glob actually matches files.
- Try a direct file path first.
- Ensure you are using the same `--state` file between runs.

Unexpected answers:

- Tighten your corpus content to be more specific.
- Reduce unrelated documents.
- Start with a fresh state for a clean experiment:

```bash
teleportdog --state ./state/fresh.json --corpus ./corpus
```

## Minimal Experiments

No external corpus:

```bash
teleportdog
```

Single custom file:

```bash
teleportdog --corpus ./examples/simple.txt
```

Any number of custom inputs:

```bash
teleportdog \
  --corpus ./examples/simple.txt \
  --corpus ./examples \
  --corpus "./examples/**/*.md"
```
