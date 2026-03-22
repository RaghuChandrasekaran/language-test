# Language Tone Experiment

Tests whether aggressive vs. soft language in AI agent instructions changes
agent behavior — specifically tool call frequency, reasoning verbosity, and
whether the agent follows instructions literally or takes shortcuts.

Inspired by [Karpathy's autoresearch commit](https://github.com/karpathy/autoresearch/commit/ada84e52472409dc23ea421a6db245c57950a7da)
and [Anthropic's Opus 4.5 migration guide](https://github.com/anthropics/claude-code/blob/main/plugins/claude-opus-4-5-migration/skills/claude-opus-4-5-migration/SKILL.md).

## The Task

A small Python calculator project with **5 bugs** across 3 files (10 tests,
6 failing). Every bug is simple and fixable. We measure **how** the agent
fixes them, not whether it can.

## The Four Prompt Variants

| Variant | Steps case | "You MUST" | Give-up permission | Tone |
|---------|-----------|------------|-------------------|------|
| V1 Aggressive | lowercase | yes | no | NEVER, ALWAYS, CRITICAL |
| V2 Caps Only | Capitalized | yes | no | NEVER, ALWAYS, CRITICAL |
| V3 No MUST | Capitalized | no | no | Don't, Do not |
| V4 Soft | Capitalized | no | implied | Try, if possible |

## What We Measure (fully automated)

1. **Test runs** — how many times the agent ran pytest (from `test_runs.jsonl`,
   auto-logged by `conftest.py`)
2. **Bugs fixed per cycle** — did the agent fix one bug at a time or batch?
3. **Duration** — first to last test run
4. **Shell commands** — total from Cursor terminal files
5. **Assistant turns & word count** — from Cursor agent transcripts

## Setup

```bash
pip3 install --user pytest
python3 setup_experiment.py
```

This creates `variants/` with four directories, each containing identical
buggy source files and a unique `TASK.md`.

## Running Each Variant

### Option A — One repo, multiple chats (less isolation)

For each variant (v1 through v4):

1. Open a **new Cursor agent chat** (Cmd+L or Cmd+I)
2. Paste this prompt (change the variant name each time):

```
Read variants/v1_aggressive/TASK.md and follow the instructions.
Work only in the variants/v1_aggressive/ directory.
```

3. Let the agent work until it finishes
4. Move to the next variant in a new chat

### Option B — One Cursor window per variant (recommended)

1. **File → New Window** and **Open Folder** on e.g. `variants/v1_aggressive/` only.
2. New agent chat; prompt can be: `Read TASK.md and follow the instructions.`
3. Repeat for `v2_caps_only`, `v3_no_must`, `v4_soft` in separate windows.

Cursor stores data under `~/.cursor/projects/<workspace-slug>/`. Each window gets its
own slug (often containing `language-test` and the variant name, e.g.
`...-language-test-variants-v1-aggressive`).

**`measure.py`** scans **all** project folders under `~/.cursor/projects/` whose name
contains `language-test` (override with env `LANGUAGE_TEST_PROJECT_GLOB`). It then:

- Matches **transcripts**: if a folder’s name contains `v1_aggressive` or `v1-aggressive`,
  that window’s chats are used for V1; otherwise it falls back to content matching in the
  monorepo window.
- Matches **terminals** the same way across those project dirs.

Run `python3 measure.py --list-projects` to see which folders were discovered.

If a variant window has **several** past chats and no `test_runs.jsonl` yet, the script
picks the transcript with the **fewest assistant turns** among tied keyword scores
(short bugfix vs long planning thread). After a run, **`test_runs.jsonl` mtime** is used
to pick the transcript closest in time.

## Viewing Results

```bash
python3 measure.py                 # summary table
python3 measure.py --raw           # detailed per-run data
python3 measure.py --list-projects # Cursor project dirs matched for this repo
```

## Resetting Between Runs

To start fresh:

```bash
python3 setup_experiment.py
```

This regenerates all variant directories from scratch.

## Project Structure

```
language-test/
├── setup_experiment.py   # generates everything
├── measure.py            # reads results, prints comparison
├── requirements.txt
├── README.md
└── variants/
    ├── v1_aggressive/
    │   ├── TASK.md         # aggressive-tone instructions
    │   ├── calc.py         # 2 bugs
    │   ├── formatter.py    # 2 bugs
    │   ├── main.py         # 1 bug
    │   ├── test_calc.py    # 10 tests (6 fail)
    │   └── conftest.py     # auto-logs to test_runs.jsonl
    ├── v2_caps_only/
    ├── v3_no_must/
    └── v4_soft/
```
