# Teleportdog Developer Constraints

This document explains what teleportdog is doing today, where its answers come from, and what its current architecture can and cannot do.

## Short Version

teleportdog is a small offline hybrid system, not a trained semantic chat model.

Its behavior comes from three layers:

1. Intent rules
2. Retrieval from learned text
3. Tiny character-level generation

That means it can often avoid exact parroting, but not because it deeply understands a corpus in the way a larger trained transformer would.

## The Three Response Paths

## 1. Intent Rules

For some common prompts, teleportdog uses direct logic in `teleportdog/chat.py`.

Examples:

- greetings
- `what can you do`
- `who are you`
- `summarise`
- simple patterned prompts like `starts with X and ends with Y`

These are not generated from the corpus at runtime. They are direct code paths that return a hand-authored response or a simple constructed response.

Why this exists:

- it makes high-frequency interactions predictable
- it avoids nonsense output from a tiny generator
- it gives the system a stable baseline behavior even with little corpus data

Constraint:

- this is only as broad as the explicit logic we write
- phrasing variation outside these patterns may miss the intended branch

## 2. Retrieval From Learned Text

When a prompt does not match a direct intent rule, teleportdog searches its learned sentence bank for overlapping keywords.

The learned sentence bank comes from:

1. built-in bootstrap corpus
2. session context snippets
3. optional external corpus files
4. prior conversation turns

Mechanically, the system:

- splits text into sentence-like chunks
- extracts crude keywords
- compares user keywords with sentence keywords
- returns one or two best-matching sentences

Why this matters:

- it can answer from larger local corpora
- it can reuse facts without quoting whole paragraphs
- it can feel responsive and relevant with no external dependencies

Constraint:

- this is still lexical matching, not deep semantic understanding
- it is sensitive to wording differences
- it can surface locally similar but globally wrong sentences
- it does not resolve contradictions well

## 3. Tiny Character-Level Generation

teleportdog also contains a small character n-gram language model in `teleportdog/lm.py`.

This model can produce novel strings in the narrow sense that the exact output may not appear in the training data. It learns short-range character patterns, not world models or reasoning.

Why it exists:

- it preserves some of the original microgpt spirit
- it is local, inspectable, dependency-free, and educational
- it allows experimentation with true generation, even at tiny scale

Constraint:

- output quality is weak for general chat
- it tends to stitch fragments together
- it drifts easily
- it is not a reliable summarizer or reasoning engine

In the current implementation, this generator is no longer the primary reply path for common chat behavior because the results were too noisy.

It is now explicitly exposed for experimentation via:

- `/mode gen` (continuous generative chat mode)
- `/gen <text>` (one-shot generative reply)

So the generative path is reachable on demand, but still intentionally not the default path.

Current gen-mode safeguards:

- lower default sampling temperature (less randomness)
- multi-candidate generation with heuristic quality scoring
- automatic fallback to the stable reply path when generation quality is too low

## What “Not Parroting” Means Here

There are several different meanings of "not parroting":

## Exact non-repetition

The output is not a verbatim copy of a full corpus chunk.

teleportdog can do this today.

## Sentence recombination

The output reuses one or two retrieved facts rather than echoing a paragraph exactly.

teleportdog can partly do this today.

## Constructed replies from explicit logic

The output is produced by code based on detected intent, even if the concepts originally came from corpus or session context.

teleportdog can do this today.

## Genuine semantic synthesis

The output integrates multiple facts into a faithful, novel explanation with reliable abstraction.

teleportdog does not do this robustly today.

That distinction is important. Some replies feel compositional because they summarize several system capabilities, but the mechanism may still be a hard-coded branch rather than learned synthesis.

## What Works Well Today

teleportdog is a good fit for:

- tiny offline chat experiments
- local corpus retrieval
- phrase-triggered assistant behavior
- T9-assisted text entry experiments
- personalized local state across sessions
- educational exploration of small language systems

It is especially reasonable when the desired behavior is:

- local
- inspectable
- hackable
- low dependency
- good enough rather than state of the art

## What Does Not Work Well Today

teleportdog is not currently strong at:

- multi-step reasoning
- grounded long-form summarization
- contradiction detection across sources
- robust semantic search
- faithful abstraction across many documents
- long coherent freeform generation
- answering subtle paraphrases unless retrieval happens to match

If you feed it a large corpus, it may become more useful as a retrieval assistant, but not automatically as a reasoning assistant.

## Corpus Size vs Capability

More corpus helps, but not in a magical way.

What more corpus improves:

- vocabulary coverage
- topic coverage
- retrieval hit rate
- T9 suggestion coverage
- domain familiarity in stored text

What more corpus does not automatically improve:

- reasoning depth
- semantic abstraction
- truthfulness under ambiguity
- cross-document synthesis
- conflict resolution between documents

A large corpus with this architecture mostly gives you a larger memory, not a qualitatively smarter model.

## Why The Current Design Is Still Valuable

Despite the limits, the current design has real engineering value.

It is:

- fast to read
- easy to modify
- fully offline after install
- cheap to run
- transparent about where outputs come from
- a practical base for experimentation

This matters because each response path is understandable and debuggable.

## Where To Improve Next

If you want better non-parrot behavior without giving up the local/offline spirit, the next useful improvements are:

1. Better intent matching
   - normalize paraphrases like `what are your capabilities`
   - classify broader question families

2. Better retrieval
   - scoring beyond raw keyword overlap
   - sentence deduplication and filtering
   - lightweight ranking by source quality or recency

3. Small compositional layer
   - build replies from retrieved facts using templates
   - combine multiple retrieved facts into one short answer
   - expose which facts were used

4. Better corpus shaping
   - encourage fact-like sentence structure
   - separate definitions, examples, and instructions
   - reduce contradictory or noisy sources

5. Optional stronger local model
   - word-level n-grams
   - small embedding-based retrieval
   - compact transformer inference if dependencies and model files become acceptable

## Practical Guidance For Developers

When extending teleportdog, keep these constraints in mind:

- Do not assume more text alone will produce smarter answers.
- Prefer explicit behavior for common user intents.
- Treat retrieval as lexical unless you have upgraded the scoring mechanism.
- Keep the system honest about uncertainty.
- Optimize for inspectability and debuggability first.
- Preserve offline-first behavior unless a deliberate product change is made.

## Bottom Line

teleportdog is currently a tiny hybrid assistant:

- partly hand-authored
- partly retrieval-based
- partly generative in a very small-scale sense

It can be useful and interesting without being a full language model in the modern sense.

That is the core constraint, and also the core charm.

## CLI Ergonomics

- On platforms where Python `readline` is available, teleportdog enables line editing and history navigation in the interactive prompt (for example, up-arrow history).
- On platforms without `readline`, teleportdog continues to run normally without interactive history/editing enhancements.
- `/exit` is supported as an alias of `/quit`.
