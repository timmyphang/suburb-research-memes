#!/usr/bin/env python3
"""
Suburb Research Prompt Generator — NSW + QLD combined.

Reads school CSVs from NSW and QLD, deduplicates suburbs, and generates
structured research prompts for all unique suburbs. Prompts are state-aware
(searching r/sydney for NSW, r/brisbane for QLD).

Usage:
    python3 generate_codex_prompts.py
    python3 generate_codex_prompts.py --nsw /path/to/nsw_schools.csv --qld /path/to/qld_schools.csv
    python3 generate_codex_prompts.py --output-dir /home/tim/suburb_research_output
"""

import argparse
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

# ── Default paths (VM-compatible with local fallback) ─────────────
OUTPUT_DIR_DEFAULT = Path("/home/tim/suburb_research_output")
NSW_CSV_DEFAULT = "/home/tim/naplan-data/nsw_schools.csv"
QLD_CSV_DEFAULT = "/home/tim/naplan-data/QLD schools/qld_schools.csv"


def generate_suburb_prompt(suburb: str, state: str) -> str:
    """Generate a state-aware research prompt for a suburb.

    Args:
        suburb: Suburb name
        state:  'NSW' or 'QLD'

    Returns:
        Full prompt string
    """
    if state == "QLD":
        location = f"{suburb}, QLD Australia"
        reddit_sub = "/r/brisbane"
        state_full = "Queensland"
    else:
        location = f"{suburb}, Sydney NSW Australia"
        reddit_sub = "/r/sydney"
        state_full = "New South Wales"

    return f"""Research the cultural vibe and local stereotypes of {location}. Extract lighthearted, satirical data to help new migrants understand the local humor. The information gathered must be detailed and comprehensive enough to later be adapted into a 400-word funny Instagram post script about the suburb.

CRITICAL EXECUTION RULES:
- Rely purely on search engine summary snippets. NEVER load full Reddit, Facebook, or forum pages into memory.
- Keep all extracted concepts PG-13. Focus on low-stakes cultural quirks (e.g., coffee snobbery, parking complaints, types of dogs) to strictly comply with automated content safety filters. Do not extract political, offensive, or controversial material.
- Ensure all extracted data includes sufficient specific examples, anecdotes, and contextual details to support a 400-word humorous Instagram script.

Execute searches for these exact data points:
1) The Suburb Stereotype: Search "site:reddit.com{reddit_sub} {{{suburb}}} stereotype" or "{{{suburb}}} starter pack". Read the snippets to identify the most common joke about the residents (e.g., types of cars they drive, fashion choices like activewear, or weekend habits). Include 2-3 specific examples or anecdotes from snippets.
2) Low-Stakes Local Drama: Search "{{{suburb}}} funny local news" or "{{{suburb}}} local council dispute". Look for a humorous, minor local event in the snippets (e.g., a notorious local ibis/bin chicken, a funny noise complaint, or a ridiculous community Facebook group post). Include specific details of the event.
3) The Ideal Resident (Persona): Based on the search snippets regarding the suburb's vibe, describe the exaggerated persona of someone who would THRIVE living here. Include their typical weekend routine and habits.
4) The Misfit (Persona): Based on the suburb's vibe, describe the exaggerated persona of someone who would absolutely HATE living here. Include why they clash with the suburb's vibe.

Output the results in JSON format with keys: suburb, stereotype, local_drama, ideal_resident, misfit, snippets_used. Ensure each section has enough detail to contribute to a 400-word funny Instagram script."""


def load_suburbs(nsw_path: str, qld_path: str) -> list[dict]:
    """Load and deduplicate suburbs from NSW and QLD school CSVs.

    Returns:
        Sorted list of {'suburb': str, 'state': 'NSW'|'QLD'} dicts
    """
    print(f"Loading NSW schools from: {nsw_path}")
    nsw = pd.read_csv(nsw_path)
    # NSW CSV uses lowercase column names: 'suburb'
    nsw_col = "suburb" if "suburb" in nsw.columns else "Suburb"
    nsw_subs = set(nsw[nsw_col].dropna().str.strip().str.title())
    print(f"  {len(nsw)} schools, {len(nsw_subs)} unique suburbs")

    print(f"Loading QLD schools from: {qld_path}")
    qld = pd.read_csv(qld_path)
    qld_col = "suburb" if "suburb" in qld.columns else "Suburb"
    qld_subs = set(qld[qld_col].dropna().str.strip().str.title())
    print(f"  {len(qld)} schools, {len(qld_subs)} unique suburbs")

    # Deduplicate — suburbs appearing in both states keep both entries
    # (each state gets its own prompt with state-specific Reddit sub and location)
    overlap = nsw_subs & qld_subs
    if overlap:
        print(f"  {len(overlap)} suburbs appear in both states (keeping both entries)")
        overlap_preview = sorted(overlap)[:5]
        print(f"  Examples: {', '.join(overlap_preview)}")

    # Build sorted list — one entry per (suburb, state) pair
    entries = []
    for s in sorted(nsw_subs):
        entries.append({"suburb": s, "state": "NSW"})
    for s in sorted(qld_subs):
        entries.append({"suburb": s, "state": "QLD"})

    nsw_count = sum(1 for e in entries if e["state"] == "NSW")
    qld_count = sum(1 for e in entries if e["state"] == "QLD")
    print(f"  Combined: {len(entries)} unique suburbs ({nsw_count} NSW, {qld_count} QLD)")
    return entries


def main():
    parser = argparse.ArgumentParser(
        description="Generate suburb research prompts from NSW+QLD school CSVs"
    )
    parser.add_argument("--nsw", default=NSW_CSV_DEFAULT, help="Path to NSW schools CSV")
    parser.add_argument("--qld", default=QLD_CSV_DEFAULT, help="Path to QLD schools CSV")
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR_DEFAULT),
        help="Output directory for prompts and status files",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    prompts_file = output_dir / "suburb_research_prompts.json"
    batches_dir = output_dir / "prompt_batches"

    output_dir.mkdir(parents=True, exist_ok=True)
    batches_dir.mkdir(parents=True, exist_ok=True)

    # Load suburbs
    suburbs = load_suburbs(args.nsw, args.qld)

    # Generate prompts
    prompts = []
    for idx, entry in enumerate(suburbs, 1):
        prompt_data = {
            "id": idx,
            "suburb": entry["suburb"],
            "state": entry["state"],
            "prompt": generate_suburb_prompt(entry["suburb"], entry["state"]),
            "status": "pending",
            "timestamp_generated": datetime.now().isoformat(),
        }
        prompts.append(prompt_data)

        if idx % 100 == 0:
            print(f"  Generated prompts for {idx}/{len(suburbs)} suburbs...")

    # Save all prompts
    with open(prompts_file, "w") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Saved {len(prompts)} prompts to: {prompts_file}")

    # Create batches for parallel processing (100 prompts per batch)
    batch_size = 100
    for i in range(0, len(prompts), batch_size):
        batch = prompts[i : i + batch_size]
        batch_num = (i // batch_size) + 1
        batch_file = batches_dir / f"batch_{batch_num:03d}.json"
        with open(batch_file, "w") as f:
            json.dump(batch, f, indent=2, ensure_ascii=False)

    batch_count = len(list(batches_dir.glob("*.json")))
    print(f"✓ Created {batch_count} batch files in: {batches_dir}")

    # Create status tracker
    status_file = output_dir / "processing_status.json"
    nsw_pending = sum(1 for p in prompts if p["state"] == "NSW" and p["status"] == "pending")
    qld_pending = sum(1 for p in prompts if p["state"] == "QLD" and p["status"] == "pending")
    status = {
        "total": len(prompts),
        "pending": len(prompts),
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "nsw_total": sum(1 for p in prompts if p["state"] == "NSW"),
        "qld_total": sum(1 for p in prompts if p["state"] == "QLD"),
        "batches": batch_count,
        "generated_at": datetime.now().isoformat(),
    }
    with open(status_file, "w") as f:
        json.dump(status, f, indent=2)

    print(f"\n{'='*60}")
    print("PROMPT GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total prompts: {len(prompts)}")
    print(f"  NSW: {nsw_pending}  |  QLD: {qld_pending}")
    print(f"Prompts file: {prompts_file}")
    print(f"Batches directory: {batches_dir}")
    print(f"\nTo process:")
    print(f"  python3 pi_batch_processor.py           # pi-coder search (fast/cheap)")
    print(f"  python3 codex_batch_processor.py        # codex agent (original)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
