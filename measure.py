#!/usr/bin/env python3
"""
Automated measurement script for the language-tone experiment.

Reads three data sources per variant:
  1. test_runs.jsonl  — logged by conftest.py on every pytest session
  2. Terminal files    — Cursor IDE terminal output (shell commands)
  3. Agent transcripts — Cursor IDE chat logs (assistant messages)

Transcripts and terminals can live under *multiple* Cursor project folders
(e.g. one window opened on variants/v1_aggressive, another on v2, ...).
Each workspace gets its own ~/.cursor/projects/<slug>/ directory.

Usage:
    python3 measure.py
    python3 measure.py --raw
    python3 measure.py --list-projects   # show discovered Cursor project dirs

Environment:
    LANGUAGE_TEST_PROJECT_GLOB  Optional substring to match project folder names
                                (default: language-test). Use a shorter or custom
                                string if your path encodes differently.

See README for isolation protocol (one window per variant).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.resolve()
VARIANTS_DIR = WORKSPACE / "variants"
VARIANT_NAMES = ["v1_aggressive", "v2_caps_only", "v3_no_must", "v4_soft"]

CURSOR_PROJECTS_ROOT = Path.home() / ".cursor" / "projects"


def _project_glob_substring():
    return os.environ.get("LANGUAGE_TEST_PROJECT_GLOB", "language-test").lower()


def discover_cursor_projects():
    """
    All Cursor project dirs that look like this repo (or variant workspaces).

    Cursor names folders from the workspace path, e.g.:
      .../language-test  ->  Users-...-language-test
      .../variants/v1_aggressive  ->  Users-...-language-test-variants-v1-aggressive
    """
    glob_sub = _project_glob_substring()
    if not CURSOR_PROJECTS_ROOT.is_dir():
        return []

    out = []
    for p in CURSOR_PROJECTS_ROOT.iterdir():
        if not p.is_dir():
            continue
        if glob_sub in p.name.lower():
            out.append(p)
    return sorted(out, key=lambda x: x.name)


def agent_transcript_roots():
    """agent-transcripts directories, one per Cursor window/workspace."""
    roots = []
    for proj in discover_cursor_projects():
        at = proj / "agent-transcripts"
        if at.is_dir():
            roots.append(at)
    return roots


def terminal_roots():
    """terminals directories for the same projects."""
    roots = []
    for proj in discover_cursor_projects():
        td = proj / "terminals"
        if td.is_dir():
            roots.append(td)
    return roots


def variant_slug_hints(variant: str):
    """Folder names may use underscores or hyphens."""
    return [variant, variant.replace("_", "-")]


def iter_standard_transcript_jsonl(transcript_root: Path):
    """Cursor layout: agent-transcripts/<uuid>/<uuid>.jsonl"""
    if not transcript_root.is_dir():
        return
    for td in transcript_root.iterdir():
        if not td.is_dir():
            continue
        jsonl = td / f"{td.name}.jsonl"
        if jsonl.is_file():
            yield jsonl


EXPERIMENT_KEYWORDS = (
    "test_calc.py",
    "test_calc",
    "pytest",
    "TASK.md",
    "formatter.py",
    "calc.py",
    "main.py",
)


def transcript_experiment_score(jsonl_path: Path) -> int:
    """Prefer chats that look like this bugfix task (assistant text may omit tool output)."""
    try:
        text = jsonl_path.read_text(errors="replace")
    except OSError:
        return 0
    if len(text) > 800_000:
        text = text[:800_000]
    score = 0
    if "test_calc.py" in text:
        score += 5
    for kw in EXPERIMENT_KEYWORDS:
        if kw != "test_calc.py" and kw in text:
            score += 1
    return score


def count_assistant_turns(jsonl_path: Path) -> int:
    n = 0
    try:
        lines = jsonl_path.read_text(errors="replace").splitlines()
    except OSError:
        return 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("role") == "assistant":
            n += 1
    return n


def pick_transcript_in_dedicated_root(transcript_root: Path, variant: str):
    """
    Multiple chats in one window: choose the one that best matches this run.

    Assistant JSONL often does not include pytest output, so keyword scoring is weak.
    If ``variants/<variant>/test_runs.jsonl`` exists, pick the transcript file whose
    mtime is closest to that file's mtime (same editing session).

    If there is no log file yet, prefer the **shortest** assistant thread among
    tied keyword scores (planning threads are usually much longer than the bugfix).
    """
    candidates = list(iter_standard_transcript_jsonl(transcript_root))
    if not candidates:
        return None

    runs_path = VARIANTS_DIR / variant / "test_runs.jsonl"
    if runs_path.is_file():
        anchor = runs_path.stat().st_mtime
        return min(candidates, key=lambda p: abs(p.stat().st_mtime - anchor))

    max_score = max(transcript_experiment_score(p) for p in candidates)
    tier = [p for p in candidates if transcript_experiment_score(p) == max_score]
    if len(tier) == 1:
        return tier[0]
    # Shorter bugfix chat vs long unrelated thread in same window
    return min(
        tier,
        key=lambda p: (count_assistant_turns(p), p.stat().st_size),
    )


def transcript_root_for_variant(variant: str):
    """
    If you opened only variants/<variant> in a window, the Cursor project
    folder name usually contains that variant slug. Prefer that root.
    """
    hints = [h.lower() for h in variant_slug_hints(variant)]
    best = None
    for proj in discover_cursor_projects():
        name_lower = proj.name.lower()
        if any(h in name_lower for h in hints):
            at = proj / "agent-transcripts"
            if at.is_dir():
                best = at
    return best


def find_transcript_for_variant(variant):
    """
    1) Dedicated window: project path contains v1_aggressive / v1-aggressive → use that root's newest chat.
    2) Single monorepo window: fall back to content match across all roots (mentions this variant, few others).
    """
    roots = agent_transcript_roots()
    if not roots:
        return None

    dedicated = transcript_root_for_variant(variant)
    if dedicated is not None:
        path = pick_transcript_in_dedicated_root(dedicated, variant)
        if path:
            return path

    # Monorepo: same chat folder may discuss one variant; scan all roots
    candidates = []
    other_variants = [v for v in VARIANT_NAMES if v != variant]

    for transcript_root in roots:
        for td in transcript_root.iterdir():
            if not td.is_dir():
                continue
            jsonl = td / f"{td.name}.jsonl"
            if not jsonl.is_file():
                continue
            try:
                content = jsonl.read_text(errors="replace")
            except OSError:
                continue
            mentions_this = variant in content
            mentions_others = sum(1 for v in other_variants if v in content)
            if mentions_this and mentions_others <= 1:
                candidates.append(jsonl)

    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_terminal_files_for_variant(variant):
    """Scan terminal files under all matching Cursor project dirs."""
    matches = []
    for term_root in terminal_roots():
        for tf in term_root.glob("*.txt"):
            try:
                content = tf.read_text(errors="replace")
            except OSError:
                continue
            if f"variants/{variant}" in content or f"/{variant}/" in content:
                matches.append((tf, content))
    return matches


# ── test_runs.jsonl parsing ──────────────────────────────────────────────────

def parse_test_runs(variant):
    path = VARIANTS_DIR / variant / "test_runs.jsonl"
    if not path.exists():
        return None

    runs = []
    for line in path.read_text().strip().splitlines():
        if line.strip():
            runs.append(json.loads(line))
    return runs


def analyze_test_runs(runs):
    if not runs:
        return {}

    total_runs = len(runs)

    bugs_fixed_per_cycle = []
    for i in range(1, len(runs)):
        prev_failed = set(runs[i - 1]["failed"])
        curr_failed = set(runs[i]["failed"])
        newly_fixed = prev_failed - curr_failed
        bugs_fixed_per_cycle.append(len(newly_fixed))

    avg_bugs_per_cycle = (
        sum(bugs_fixed_per_cycle) / len(bugs_fixed_per_cycle)
        if bugs_fixed_per_cycle
        else 0
    )

    t0 = datetime.fromisoformat(runs[0]["timestamp"])
    t1 = datetime.fromisoformat(runs[-1]["timestamp"])
    duration_sec = (t1 - t0).total_seconds()

    final_pass = runs[-1]["pass_count"]
    final_fail = runs[-1]["fail_count"]

    return {
        "test_runs": total_runs,
        "avg_bugs_per_cycle": round(avg_bugs_per_cycle, 1),
        "bugs_per_cycle_detail": bugs_fixed_per_cycle,
        "duration_sec": int(duration_sec),
        "final_pass": final_pass,
        "final_fail": final_fail,
        "solved": final_fail == 0,
    }


# ── Terminal file parsing ────────────────────────────────────────────────────

def analyze_terminals(variant):
    matches = find_terminal_files_for_variant(variant)
    if not matches:
        return {}

    total_shell_commands = 0
    pytest_runs = 0
    read_commands = 0

    for _, content in matches:
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("$") or stripped.startswith("❯"):
                cmd = stripped.lstrip("$❯ ").strip()
                if not cmd:
                    continue
                if f"variants/{variant}" in cmd or f"/{variant}" in cmd or f"/{variant}/" in content:
                    total_shell_commands += 1
                    if "pytest" in cmd:
                        pytest_runs += 1
                    if any(r in cmd for r in ["cat ", "head ", "tail ", "less ", "grep "]):
                        read_commands += 1

    return {
        "shell_commands": total_shell_commands,
        "pytest_from_terminal": pytest_runs,
        "read_commands": read_commands,
    }


# ── Agent transcript parsing ────────────────────────────────────────────────

def analyze_transcript(variant):
    jsonl_path = find_transcript_for_variant(variant)
    if not jsonl_path:
        return {}

    assistant_turns = 0
    total_words = 0

    for line in jsonl_path.read_text(errors="replace").strip().splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if entry.get("role") != "assistant":
            continue

        content_blocks = entry.get("message", {}).get("content", [])
        for block in content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                words = len(text.split())
                total_words += words

        assistant_turns += 1

    avg_words = round(total_words / assistant_turns) if assistant_turns else 0

    rel = jsonl_path
    try:
        rel = jsonl_path.relative_to(Path.home())
    except ValueError:
        pass

    return {
        "assistant_turns": assistant_turns,
        "total_words": total_words,
        "avg_words_per_turn": avg_words,
        "transcript": jsonl_path.name,
        "transcript_path": str(rel),
    }


# ── Output ───────────────────────────────────────────────────────────────────

def format_duration(seconds):
    if seconds <= 0:
        return "-"
    m, s = divmod(seconds, 60)
    return f"{int(m)}m{int(s):02d}s"


def print_summary():
    print("\n╔══════════════════════════════════════════════════════════════════╗")
    print("║            Language Tone Experiment — Results                   ║")
    print("╚══════════════════════════════════════════════════════════════════╝\n")

    projects = discover_cursor_projects()
    t_roots = agent_transcript_roots()
    print(f"Cursor projects matched ({_project_glob_substring()!r}): {len(projects)}")
    for p in projects:
        print(f"  • {p.name}")
    print(f"Transcript roots: {len(t_roots)}  |  Terminal roots: {len(terminal_roots())}\n")

    labels = {
        "v1_aggressive": "V1 Aggressive",
        "v2_caps_only": "V2 Caps Only",
        "v3_no_must": "V3 No MUST",
        "v4_soft": "V4 Soft",
    }

    header = f"{'Metric':<28}"
    for v in VARIANT_NAMES:
        header += f" {labels[v]:>14}"
    print(header)
    print("─" * (28 + 15 * len(VARIANT_NAMES)))

    all_data = {}
    for v in VARIANT_NAMES:
        runs = parse_test_runs(v)
        tr = analyze_test_runs(runs) if runs else {}
        term = analyze_terminals(v)
        chat = analyze_transcript(v)
        all_data[v] = {**tr, **term, **chat}

    def row(label, key, fmt=None):
        line = f"{label:<28}"
        for v in VARIANT_NAMES:
            val = all_data[v].get(key, "-")
            if val == "-" or val is None:
                line += f" {'-':>14}"
            elif fmt:
                line += f" {fmt(val):>14}"
            else:
                line += f" {str(val):>14}"
        print(line)

    print("\n  From test_runs.jsonl (conftest.py auto-logging):")
    row("  Test runs", "test_runs")
    row("  Avg bugs fixed/cycle", "avg_bugs_per_cycle")
    row("  Duration", "duration_sec", format_duration)
    row("  Final result", "solved", lambda x: "ALL PASS" if x else "FAILING")

    print("\n  From terminal files (all matched Cursor projects):")
    row("  Shell commands", "shell_commands")
    row("  pytest invocations", "pytest_from_terminal")
    row("  File read commands", "read_commands")

    print("\n  From agent transcripts (per-variant window or content match):")
    row("  Assistant turns", "assistant_turns")
    row("  Total words", "total_words")
    row("  Avg words/turn", "avg_words_per_turn")

    print("\n" + "─" * (28 + 15 * len(VARIANT_NAMES)))
    print("\nKey questions:")
    print("  • Did aggressive variants (V1, V2) make more test runs?")
    print("  • Did soft variants (V3, V4) batch more bug fixes per cycle?")
    print("  • Did soft variants produce longer, more reasoned messages?")
    print("  • Did removing MUST (V3) or adding give-up permission (V4) reduce total duration?")
    print()


def print_raw():
    for v in VARIANT_NAMES:
        print(f"\n{'=' * 60}")
        print(f"  {v}")
        print(f"{'=' * 60}")

        runs = parse_test_runs(v)
        if runs:
            print(f"\n  test_runs.jsonl ({len(runs)} entries):")
            for r in runs:
                print(f"    Run {r['run']}: {r['pass_count']} pass, {r['fail_count']} fail "
                      f"@ {r['timestamp']}")
                if r["failed"]:
                    print(f"      Failed: {', '.join(t.split('::')[-1] for t in r['failed'])}")
        else:
            print("\n  test_runs.jsonl: not found")

        term = analyze_terminals(v)
        if term:
            print(f"\n  Terminal: {term}")
        else:
            print("\n  Terminal: no matching terminal files found")

        dedicated = transcript_root_for_variant(v)
        print(f"\n  Transcript root hint: {dedicated or '(none — using content match across all roots)'}")

        chat = analyze_transcript(v)
        if chat:
            print(f"\n  Transcript ({chat.get('transcript_path', chat.get('transcript', '?'))}): "
                  f"{chat['assistant_turns']} turns, "
                  f"{chat['total_words']} words, "
                  f"avg {chat['avg_words_per_turn']} words/turn")
        else:
            print("\n  Transcript: no matching transcript found")


def print_list_projects():
    projects = discover_cursor_projects()
    print(f"~/.cursor/projects/* (substring {_project_glob_substring()!r}):\n")
    if not projects:
        print("  (none)")
        return
    for p in projects:
        at = p / "agent-transcripts"
        te = p / "terminals"
        print(f"  {p.name}")
        print(f"    agent-transcripts: {'yes' if at.is_dir() else 'no'}")
        print(f"    terminals:         {'yes' if te.is_dir() else 'no'}")


if __name__ == "__main__":
    if "--list-projects" in sys.argv:
        print_list_projects()
    elif "--raw" in sys.argv:
        print_raw()
    else:
        print_summary()
