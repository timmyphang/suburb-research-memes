#!/usr/bin/env python3
"""
Suburb Research Prompt Generator for Codex
Generates structured prompts for all 710 Sydney suburbs.
These prompts are processed by Codex with native web search on the gcloud VM.
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime

OUTPUT_DIR = Path("/home/tim/suburb_research_output")
PROMPTS_FILE = OUTPUT_DIR / "suburb_research_prompts.json"
BATCHES_DIR = OUTPUT_DIR / "prompt_batches"

def generate_suburb_prompt(suburb):
    """Generate the exact research prompt for a suburb."""
    return f"""Research the cultural vibe and local stereotypes of {suburb}, Sydney NSW Australia. Extract lighthearted, satirical data to help new migrants understand the local humor. The information gathered must be detailed and comprehensive enough to later be adapted into a 400-word funny Instagram post script about the suburb.

CRITICAL EXECUTION RULES:
- Rely purely on search engine summary snippets. NEVER load full Reddit, Facebook, or forum pages into memory. 
- Keep all extracted concepts PG-13. Focus on low-stakes cultural quirks (e.g., coffee snobbery, parking complaints, types of dogs) to strictly comply with automated content safety filters. Do not extract political, offensive, or controversial material.
- Ensure all extracted data includes sufficient specific examples, anecdotes, and contextual details to support a 400-word humorous Instagram script.

Execute searches for these exact data points:
1) The Suburb Stereotype: Search "site:reddit.com/r/sydney {suburb} stereotype" or "{suburb} starter pack". Read the snippets to identify the most common joke about the residents (e.g., types of cars they drive, fashion choices like activewear, or weekend habits). Include 2-3 specific examples or anecdotes from snippets.
2) Low-Stakes Local Drama: Search "{suburb} funny local news" or "{suburb} local council dispute". Look for a humorous, minor local event in the snippets (e.g., a notorious local ibis/bin chicken, a funny noise complaint, or a ridiculous community Facebook group post). Include specific details of the event.
3) The Ideal Resident (Persona): Based on the search snippets regarding the suburb's vibe, describe the exaggerated persona of someone who would THRIVE living here. (e.g., "The double-shot oat milk flat white enthusiast who drives a pristine 4WD to the local shops"). Include their typical weekend routine and habits.
4) The Misfit (Persona): Based on the suburb's vibe, describe the exaggerated persona of someone who would absolutely HATE living here. (e.g., "The inner-city hipster looking for underground techno and late-night kebabs"). Include why they clash with the suburb's vibe.

Output the results in JSON format with keys: suburb, stereotype, local_drama, ideal_resident, misfit, snippets_used. Ensure each section has enough detail to contribute to a 400-word funny Instagram script."""

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BATCHES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load suburbs
    print("Loading suburbs from urban_schools_2025.csv...")
    df = pd.read_csv("/home/tim/urban_schools_2025.csv")
    nsw_schools = df[df['State'] == 'NSW']
    unique_suburbs = sorted(nsw_schools['Suburb'].unique())
    
    print(f"Total unique suburbs: {len(unique_suburbs)}")
    
    # Generate prompts
    prompts = []
    for idx, suburb in enumerate(unique_suburbs, 1):
        prompt_data = {
            "id": idx,
            "suburb": suburb,
            "prompt": generate_suburb_prompt(suburb),
            "status": "pending",
            "timestamp_generated": datetime.now().isoformat()
        }
        prompts.append(prompt_data)
        
        if idx % 100 == 0:
            print(f"Generated prompts for {idx}/{len(unique_suburbs)} suburbs...")
    
    # Save all prompts
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts, f, indent=2)
    
    print(f"\n✓ Saved {len(prompts)} prompts to: {PROMPTS_FILE}")
    
    # Create batches for parallel processing (100 prompts per batch)
    batch_size = 100
    for i in range(0, len(prompts), batch_size):
        batch = prompts[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        batch_file = BATCHES_DIR / f"batch_{batch_num:03d}.json"
        with open(batch_file, 'w') as f:
            json.dump(batch, f, indent=2)
    
    print(f"✓ Created {len(list(BATCHES_DIR.glob('*.json')))} batch files in: {BATCHES_DIR}")
    
    # Create a simple status tracker
    status_file = OUTPUT_DIR / "processing_status.json"
    status = {
        "total": len(prompts),
        "pending": len(prompts),
        "processing": 0,
        "completed": 0,
        "failed": 0,
        "batches": len(list(BATCHES_DIR.glob('*.json'))),
        "generated_at": datetime.now().isoformat()
    }
    with open(status_file, 'w') as f:
        json.dump(status, f, indent=2)
    
    print(f"\n{'='*60}")
    print("PROMPT GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total prompts: {len(prompts)}")
    print(f"Prompts file: {PROMPTS_FILE}")
    print(f"Batches directory: {BATCHES_DIR}")
    print(f"\nTo process with Codex (using full VM capacity):")
    print(f"1. Run: python3 /home/tim/codex_batch_processor.py")
    print(f"2. Or manually feed prompts to Codex from: {PROMPTS_FILE}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
