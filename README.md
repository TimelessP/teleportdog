# teleportdog

License: MIT (see `LICENSE`)

teleportdog is a tiny offline chat CLI for Python 3.12 that blends:

- microgpt spirit: very small local character-level language modeling
- teeny-tiny-t9 spirit: numeric keypad predictive text for whole words
- nanochat spirit: simple chat loop with transcript-driven responses

No network is needed after installation.

## Source Lineage

This project was inspired by ideas from three public sources:

1. `microgpt.py` by Andrej Karpathy
	- Source: https://gist.githubusercontent.com/karpathy/8627fe009c40f57531cb18360106ce95/raw/14fb038816c7aae0bb9342c2dbf1a51dd134a5ff/microgpt.py
	- Influence: tiny, readable, local-first language modeling mindset and minimalism.

2. `teeny-tiny-t9` by realityinspector
	- Source repo: https://github.com/realityinspector/teeny-tiny-t9
	- Raw source referenced: https://raw.githubusercontent.com/realityinspector/teeny-tiny-t9/refs/heads/main/main.py
	- Influence: compact T9 word mapping from keypad digits to candidate words.

3. `nanochat` by Andrej Karpathy
	- Source: https://github.com/karpathy/nanochat
	- Influence: chat-oriented workflow, conversational turn formatting, and practical chat UX focus.

## What Teleportdog Adds

teleportdog is not a direct copy of any of the above. It combines ideas and adds:

- A pure Python 3.12 offline CLI experience with no runtime dependencies.
- Session initialization context, so every new run starts with stable assistant behavior.
- A hybrid response path tuned for coherence in a tiny local setup:
  - lightweight intent handling for common prompts
  - local knowledge retrieval from learned sentences
  - graceful fallback responses when confidence is low
- Persistent local memory in `~/.teleportdog/state.json` (or `--state <path>`), including:
  - learned language model state
  - T9 index
  - recent chat history
  - learned knowledge snippets
- Incremental on-device learning from both user and assistant turns.

## Architecture Snapshot

- `teleportdog/lm.py`: tiny char n-gram model (small, local, inspectable).
- `teleportdog/t9.py`: T9 encoder/index/suggester and phrase decoding.
- `teleportdog/chat.py`: session context init, intent routing, retrieval, learning, persistence.
- `teleportdog/cli.py`: interactive chat loop and commands.
- `teleportdog/data/bootstrap_corpus.txt`: bootstrap local corpus.

## Install

```bash
python3.12 -m pip install -e .
```

Or prepare a local dev environment:

```bash
./dev-prepare.sh
```

## Run

```bash
teleportdog
```

If your shell does not expose script shims, use:

```bash
python3.12 -m teleportdog
```

If `teleportdog` is still not found after install, run:

```bash
pyenv rehash
hash -r
```

Run with custom corpus sources (file, dir, glob; zero or many):

```bash
teleportdog --corpus ./notes --corpus "./docs/**/*.md"
```

Run the bundled demo flow:

```bash
./run-demo.sh
```

## Commands

- `/help` show help
- `/mode text` normal text input mode
- `/mode t9` T9 input mode (digits become words)
- `/mode gen` local character-model generation mode
- `/gen <text>` one-shot generated reply from the local model
- `/learnglob <pattern>` import extra corpus at runtime (glob/file/dir)
- `/suggest 43556` show word candidates for one T9 sequence
- `/learn some text` force-learn text into local model
- `/save` persist model state to `~/.teleportdog/state.json`
- `/quit` exit
- `/exit` exit (alias for `/quit`)

## Notes

- On first run, the model trains on a bundled tiny corpus.
- During chat, both your messages and assistant replies are learned incrementally.
- T9 dictionary is built from the corpus and updated with conversation words.
- Once installed, operation is fully local and does not require internet access.
- **Tab completion**: if readline is available on your OS, you can press Tab to autocomplete commands. Type `/` followed by a few letters and press Tab to see matching commands.

## Corpus Expansion Guide

For a full, example-driven guide to adding custom corpus sources, read:

- `docs/CORPUS_EXPANSION.md`

## Developer Notes

For an explanation of the current architecture, response paths, and practical constraints, read:

- `docs/DEVELOPER_CONSTRAINTS.md`
