#!/usr/bin/env python3
"""
Check progress on the Agent Action Plan.

Reads AGENT_PROGRESS.md and prints:
  - Summary (done/total per phase and overall)
  - Next suggested task (first unchecked row)

Usage:
  python scripts/check_agent_progress.py
  # or from repo root:
  ./scripts/check_agent_progress.py
"""

from pathlib import Path
import re

# Repo root: parent of scripts/
ROOT = Path(__file__).resolve().parent.parent
PROGRESS_FILE = ROOT / "AGENT_PROGRESS.md"

PHASE_HEADER = re.compile(r"^## Phase (\d+) — (.+)$", re.MULTILINE)


def parse_task_row(line: str) -> tuple[bool, str, str] | None:
    """Return (done, task_id, description) or None if not a task row."""
    parts = [p.strip() for p in line.split("|")]
    # Expect: '', '[ ]' or '[x]', 'P1-01', 'Description', 'Section', 'Notes', ''
    if len(parts) < 5:
        return None
    done_cell = parts[1]
    if not re.match(r"\[[ x]\]", done_cell):
        return None
    task_id_cell = parts[2]
    if not re.match(r"P\d+-\d+[a-z]*", task_id_cell):
        return None
    desc = parts[3].strip()
    return (done_cell.strip().lower() == "[x]", task_id_cell.strip(), desc)


def main() -> None:
    if not PROGRESS_FILE.exists():
        print(f"Progress file not found: {PROGRESS_FILE}")
        return

    text = PROGRESS_FILE.read_text()
    lines = text.split("\n")
    current_phase = 0
    phase_names: dict[int, str] = {}
    total_done = 0
    total_tasks = 0
    phase_stats: list[tuple[int, str, int, int]] = []
    all_tasks: list[tuple[int, str, str, bool]] = []  # (phase, task_id, desc, done)
    phase_tasks: list[tuple[bool, str, str]] = []

    for line in lines:
        m_phase = PHASE_HEADER.match(line)
        if m_phase:
            if current_phase and phase_tasks:
                done_count = sum(1 for d, _, _ in phase_tasks if d)
                phase_total = len(phase_tasks)
                total_done += done_count
                total_tasks += phase_total
                phase_stats.append((current_phase, phase_names.get(current_phase, ""), done_count, phase_total))
                for d, tid, desc in phase_tasks:
                    all_tasks.append((current_phase, tid, desc, d))
            current_phase = int(m_phase.group(1))
            phase_names[current_phase] = m_phase.group(2).strip()
            phase_tasks = []
            continue
        row = parse_task_row(line)
        if row:
            done, task_id, desc = row
            # Only attribute to current phase if task id matches (e.g. P1-* for Phase 1)
            if current_phase and task_id.startswith(f"P{current_phase}-"):
                phase_tasks.append((done, task_id, desc))

    if current_phase and phase_tasks:
        done_count = sum(1 for d, _, _ in phase_tasks if d)
        phase_total = len(phase_tasks)
        total_done += done_count
        total_tasks += phase_total
        phase_stats.append((current_phase, phase_names.get(current_phase, ""), done_count, phase_total))
        for d, tid, desc in phase_tasks:
            all_tasks.append((current_phase, tid, desc, d))

    # Print summary
    print("Agent Action Plan — Progress")
    print("=" * 50)
    for phase_num, name, done, total in phase_stats:
        pct = (100 * done / total) if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  Phase {phase_num}: {bar} {done}/{total} ({pct:.0f}%)")
    overall_pct = (100 * total_done / total_tasks) if total_tasks else 0
    print(f"  Total:  {total_done}/{total_tasks} ({overall_pct:.0f}%)")
    print()

    # Next task (first unchecked)
    next_task = None
    for phase_num, task_id, desc, done in all_tasks:
        if not done:
            next_task = (phase_num, task_id, desc)
            break
    if next_task:
        p, tid, d = next_task
        print("Next suggested task:")
        print(f"  [{tid}] (Phase {p}) {d[:70]}{'...' if len(d) > 70 else ''}")
    else:
        print("All tasks are marked done.")


if __name__ == "__main__":
    main()
