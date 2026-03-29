# Teleportdog Developer Constraints

This document explains what teleportdog is doing today, where answers come from, and what its architecture can and cannot do.

## Short Version

teleportdog is a tiny offline hybrid assistant, not a large semantic model.

Its behavior comes from three layers:

1. Intent rules
2. Retrieval from learned text
3. Tiny local generation (subword n-gram with constrained decoding)

This can reduce exact parroting, but it does not provide deep reasoning.

## The Three Response Paths

## 1. Intent Rules

For common prompts, teleportdog uses explicit logic in `teleportdog/chat.py`.

Examples:
- `who are you`
- `summarise`
- simple patterned prompts like `starts with X and ends with Y`

Why this matters:
- makes frequent interactions predictable
- avoids nonsense from tiny generation
- gives stable baseline behavior even with little corpus data

Constraint:
- coverage is only as broad as the rules we write
- phrasing variation outside these patterns may miss the intended branch

## 2. Retrieval From Learned Text

When a prompt does not match an intent rule, teleportdog searches its sentence bank using a zero-dependency hybrid ranker.

The sentence bank is learned from:

1. built-in bootstrap corpus
2. session context snippets
3. optional external corpus files
4. prior conversation turns

Mechanically, the system:
- splits text into sentence-like chunks
- filters markdown and metadata-like noise
- extracts keyword terms
- scores sentences with BM25-style lexical ranking
- adds lightweight random-indexing similarity
- expands a small set of paraphrase-like query hints such as `without internet -> offline`
- returns one or two top sentences

Why this matters:
- answers can come from larger local corpora
- facts can be reused without repeating full paragraphs
- remains fully offline and dependency-free

Constraint:
- this is still not deep semantic understanding
- coverage of paraphrases is limited to corpus signal plus a small built-in hint layer
- contradictions are not resolved robustly

## 3. Tiny Local Generation

teleportdog includes a tiny n-gram model in `teleportdog/lm.py`.

Current generator behavior:
- subword-token n-grams (legacy char state remains loadable)
- tiny response planner chooses style and strictness
- adaptive grounding chooses a small number of supporting snippets
- constrained decoding rejects repetitive or markup-like output
- quality and relevance scoring select the best candidate
- stable fallback path is used when confidence is low

Why it exists:
- preserves local-first, inspectable generation
- enables practical experimentation in very small code
- keeps runtime simple and fast

Constraint:
- coherence is improved but still shallow on complex prompts
- factual synthesis remains limited
- longer reasoning chains are weak compared to larger models

## What "Not Parroting" Means Here

There are several meanings of "not parroting":

## Exact non-repetition

Output is not an exact copy of a corpus chunk.

teleportdog can usually do this.

## Sentence recombination

Output reuses one or two relevant facts rather than repeating a paragraph.

teleportdog can often do this.

## Rule-constructed replies

Output is created by explicit logic for known intents.

teleportdog can do this well for covered cases.

## Semantic synthesis

Output merges multiple facts into faithful, novel explanation.

teleportdog does not do this robustly today.

## What Works Well Today

teleportdog is a good fit for:
- tiny offline chat experiments
- local corpus retrieval
- practical CLI interactions
- T9-assisted input experiments
- personalized local state across sessions
- educational exploration of small language systems

## What Does Not Work Well Today

teleportdog is not currently strong at:
- multi-step reasoning
- deep factual synthesis
- contradiction resolution across sources
- robust semantic search
- long coherent freeform generation

## Corpus Size vs Capability

More corpus helps coverage, but not reasoning depth.

What more corpus improves:
- vocabulary and topic coverage
- retrieval hit rate
- T9 suggestion coverage
- random-indexing context quality

What more corpus does not automatically improve:
- abstraction quality
- truthfulness under ambiguity
- cross-document synthesis

## Why The Design Is Still Valuable

The current design is:
- easy to read and modify
- fully offline after install
- transparent about response sources
- cheap to run

This makes it a practical base for experimentation.

## Practical Guidance For Developers

When extending teleportdog:
- do not assume more text alone makes answers smarter
- keep intent behavior explicit for common prompts
- treat retrieval as lexical unless scoring is upgraded
- keep uncertainty handling honest
- preserve offline-first behavior unless product direction changes

## Bottom Line

teleportdog is a tiny hybrid assistant:
- partly rule-based
- partly retrieval-based
- partly generative at small scale

It is intentionally simple, inspectable, and local-first.

## CLI Ergonomics

- If Python `readline` is available, teleportdog supports line editing/history and command tab completion.
- Without `readline`, teleportdog still runs normally.
- `/exit` is supported as an alias for `/quit`.
