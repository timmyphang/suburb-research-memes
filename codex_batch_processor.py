#!/usr/bin/env python3
"""
Codex Batch Processor for Suburb Research
Processes prompts in parallel using Codex's native web search.
Assumes Codex CLI or API is available on the VM.
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTPUT_DIR = Path("/home/tim/suburb_research_output")
PROMPTS_FILE = OUTPUT_DIR / "suburb_research_prompts.json"
RESULTS_FILE = OUTPUT_DIR / "all_suburb_research.json"
STATUS_FILE = OUTPUT_DIR / "processing_status.json"
MAX_WORKERS = 20  # Adjust based on VM capacity and Codex's parallelism

def process_prompt_with_codex(prompt_data):
    """
    Process a single prompt using Codex CLI with native web search.
    Uses --output-last-message to capture the response.
    """
    import subprocess
    import tempfile
    
    suburb = prompt_data["suburb"]
    prompt = prompt_data["prompt"]
    
    try:
        print(f"Processing {suburb}...")
        
        # Create a temp file for the output
        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as f:
            output_file = f.name
        
        # Call Codex CLI with the prompt
        # Using --output-last-message to get clean response
        # Using --skip-git-repo-check since we may not be in a git repo
        # Using --full-auto for non-interactive mode
        result = subprocess.run(
            ['codex', 'exec', '--skip-git-repo-check', '--full-auto',
             '--output-last-message', output_file, prompt],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout per suburb
            cwd='/tmp'  # Use /tmp as working directory
        )
        
        if result.returncode == 0:
            # Read the output from the file
            with open(output_file, 'r') as f:
                codex_response = f.read().strip()
            
            # Clean up temp file
            import os
            os.unlink(output_file)
            
            # Try to parse as JSON, fallback to raw text
            try:
                response_data = json.loads(codex_response)
            except json.JSONDecodeError:
                response_data = {"text": codex_response}
            
            return {
                "success": True,
                "suburb": suburb,
                "data": {
                    "suburb": suburb,
                    "codex_response": response_data,
                    "raw_response": codex_response,
                    "timestamp": datetime.now().isoformat()
                }
            }
        else:
            raise Exception(f"Codex CLI error (code {result.returncode}): {result.stderr}")
        
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "suburb": suburb,
            "error": "Codex CLI timeout (5 minutes)"
        }
    except Exception as e:
        return {
            "success": False,
            "suburb": suburb,
            "error": str(e)
        }

def update_status(completed=0, failed=0):
    """Update processing status."""
    with open(STATUS_FILE, 'r') as f:
        status = json.load(f)
    
    status["completed"] += completed
    status["failed"] += failed
    status["processing"] = 0
    status["pending"] = status["total"] - status["completed"] - status["failed"]
    
    with open(STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)

def main():
    """Process all prompts using Codex in parallel."""
    
    # Load prompts
    with open(PROMPTS_FILE, 'r') as f:
        prompts = json.load(f)
    
    # Filter pending prompts
    pending = [p for p in prompts if p["status"] == "pending"]
    total = len(pending)
    
    print(f"\n{'='*60}")
    print(f"CODEX BATCH PROCESSOR")
    print(f"{'='*60}")
    print(f"Total prompts: {len(prompts)}")
    print(f"Pending: {total}")
    print(f"Using {MAX_WORKERS} parallel workers")
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    if total == 0:
        print("No pending prompts to process.")
        return
    
    # Process in parallel
    results = []
    completed_count = 0
    failed_count = 0
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_prompt_with_codex, prompt): prompt
            for prompt in pending
        }
        
        for idx, future in enumerate(as_completed(futures), 1):
            prompt = futures[future]
            suburb = prompt["suburb"]
            
            try:
                result = future.result()
                
                if result["success"]:
                    results.append(result["data"])
                    completed_count += 1
                    print(f"[{idx}/{total}] ✓ {suburb}")
                else:
                    failed_count += 1
                    print(f"[{idx}/{total}] ✗ {suburb}: {result.get('error', 'Unknown error')}")
                
                # Update status every 10 prompts
                if idx % 10 == 0:
                    update_status(
                        completed=10 if completed_count >= 10 else completed_count,
                        failed=failed_count
                    )
                    
            except Exception as e:
                failed_count += 1
                print(f"[{idx}/{total}] ✗ {suburb}: {e}")
    
    # Save results
    existing_results = []
    if RESULTS_FILE.exists():
        with open(RESULTS_FILE, 'r') as f:
            existing_results = json.load(f)
    
    existing_results.extend(results)
    
    with open(RESULTS_FILE, 'w') as f:
        json.dump(existing_results, f, indent=2)
    
    # Final status update
    update_status(completed=completed_count, failed=failed_count)
    
    print(f"\n{'='*60}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*60}")
    print(f"Successfully processed: {completed_count}")
    print(f"Failed: {failed_count}")
    print(f"Results saved to: {RESULTS_FILE}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
