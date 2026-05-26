# Suburb Research Memes

Automated research system for Sydney suburb cultural vibes and stereotypes, designed to run independently on a gcloud VM. Output is formatted for creating funny Instagram scripts (400 words each).

## Overview

This system researches 710 unique Sydney suburbs to extract:
- Suburb stereotypes from Reddit and social media
- Funny local news and council dramas
- Cultural quirks and local humor

All research uses search engine snippets only (no full page loads) and maintains PG-13 content standards.

## Files Created

- `suburb_research_parallel.py` - **Main script** (multi-threaded, uses full VM capacity)
- `suburb_research_automation.py` - Single-threaded version
- `setup_vm.sh` - VM setup script
- `start_research.sh` - Startup script (runs in background)
- `requirements.txt` - Python dependencies
- `urban_schools_2025.csv` - Input data (710 Sydney suburbs)

## Output Files

All output saved to `/home/tim/suburb_research_output/`:
- `all_suburb_research.json` - Complete results
- `progress.json` - Progress tracking (resumable)
- `research.log` - Log file when run via startup script

## Quick Start on gcloud VM

### 1. Copy files to VM
```bash
# From your local machine
gcloud compute scp --recurse /home/tim/*.py /home/tim/*.sh /home/tim/requirements.txt /home/tim/urban_schools_2025.csv your-vm-name:/home/tim/
```

### 2. SSH into VM and run setup
```bash
gcloud compute ssh your-vm-name
bash /home/tim/setup_vm.sh
```

### 3. Set your Brave API key
```bash
export BRAVE_API_KEY='your_brave_api_key_here'
# Add to ~/.bashrc for persistence:
echo 'export BRAVE_API_KEY="your_key_here"' >> ~/.bashrc
```

### 4. Start the research
```bash
# Option A: Using startup script (recommended - runs in background)
bash /home/tim/start_research.sh

# Option B: Direct execution
source /home/tim/suburb_research_env/bin/activate
python3 /home/tim/suburb_research_parallel.py
```

### 5. Monitor progress
```bash
# Watch the log
tail -f /home/tim/suburb_research_output/research.log

# Check progress file
cat /home/tim/suburb_research_output/progress.json

# Count completed suburbs
python3 -c "import json; d=json.load(open('/home/tim/suburb_research_output/progress.json')); print(f'Completed: {len(d.get(\"completed\", []))}')"
```

## Resume Capability

The script is fully resumable. If the VM restarts or the process is interrupted:
- Progress is saved after each suburb
- Simply re-run the script to continue from where it left off
- No data is lost

## Configuration

Edit `MAX_WORKERS` in `suburb_research_parallel.py` to adjust parallelism:
- Default: 10 threads
- Increase for more powerful VMs (e.g., 20-50)
- Respect Brave API rate limits

## API Key Setup

Get a Brave Search API key:
1. Visit https://brave.com/search/api/
2. Sign up for free tier (2,000 queries/month) or paid plan
3. Set the environment variable as shown above

## Processing Time

- 710 suburbs × 4 searches each = 2,840 API calls
- With 10 workers and 2-second delays: ~10 minutes
- With higher parallelism on a powerful VM: ~3-5 minutes

## Results Format

```json
[
  {
    "suburb": "Bondi",
    "timestamp": "2025-01-15T10:30:00",
    "searches": {
      "stereotype": {
        "query": "site:reddit.com/r/sydney \"Bondi\" stereotype",
        "results": [...]
      },
      ...
    },
    "extracted_snippets": ["...", "..."]
  }
]
```

## Post-Processing

After research completes, use the results to generate the cultural vibe summaries using your preferred AI tool with the prompt provided earlier.
