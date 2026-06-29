#!/bin/bash
set -e

ENV_FILE="${SUBURB_ENV_FILE:-$HOME/.suburb_env}"
[ -f "$ENV_FILE" ] && set -a && . "$ENV_FILE" && set +a

REPO_DIR="$HOME/suburb-research-memes"
OUTPUT_DIR="$HOME/suburb_research_output"
GDRIVE_PATH="gdrive:suburb-research-memes-output"

cd "$REPO_DIR"

echo "============================================"
echo "Suburb Research - Chained Batch Processor"
echo "Started: $(date)"
echo "============================================"

# ── Batch 1: Main (1005 suburbs) ──
echo ""
echo "=== BATCH 1/2: Main (1005 suburbs) ==="
echo "Started: $(date)"
python3 pi_batch_processor.py 2>&1 | tee "$OUTPUT_DIR/run_main_$(date +%Y%m%d_%H%M%S).log"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Main batch exited with code $EXIT_CODE"
    exit $EXIT_CODE
fi

# Save main results
MAIN_RESULTS="$OUTPUT_DIR/all_suburb_research.json"
if [ -f "$MAIN_RESULTS" ]; then
    cp "$MAIN_RESULTS" "$OUTPUT_DIR/main_results_backup.json"
    echo "Main results backed up: $(wc -c < "$MAIN_RESULTS") bytes"
fi

# ── Batch 2: VIC addition (363 suburbs) ──
echo ""
echo "=== BATCH 2/2: VIC addition (363 suburbs) ==="
echo "Started: $(date)"

# Swap prompts
cp "$OUTPUT_DIR/suburb_research_prompts.json" "$OUTPUT_DIR/prompts_main_backup.json"
cp "$OUTPUT_DIR/vic_batch_prompts.json" "$OUTPUT_DIR/suburb_research_prompts.json"

# Reset status for VIC batch
python3 -c "
import json
from datetime import datetime
s = {'total': 363, 'pending': 363, 'processing': 0, 'completed': 0, 'failed': 0, 'generated_at': datetime.now().isoformat()}
json.dump(s, open('$OUTPUT_DIR/processing_status.json', 'w'), indent=2)
"

# Rename old results so new run starts fresh
[ -f "$MAIN_RESULTS" ] && mv "$MAIN_RESULTS" "$OUTPUT_DIR/main_results.json"

python3 pi_batch_processor.py 2>&1 | tee "$OUTPUT_DIR/run_vic_$(date +%Y%m%d_%H%M%S).log"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "WARNING: VIC batch exited with code $EXIT_CODE"
fi

# Merge results
echo ""
echo "=== Merging results ==="
python3 -c "
import json
results = []
for fpath in ['$OUTPUT_DIR/main_results.json', '$OUTPUT_DIR/all_suburb_research.json']:
    try:
        with open(fpath) as fh:
            results.extend(json.load(fh))
    except Exception:
        pass
with open('$OUTPUT_DIR/all_suburb_research.json', 'w') as fh:
    json.dump(results, fh, indent=2, ensure_ascii=False)
print(f'Merged {len(results)} total results')
"

# Sync to Google Drive
echo ""
echo "=== Syncing to Google Drive ==="
rclone copy "$OUTPUT_DIR/" "$GDRIVE_PATH/" \
    --include "all_suburb_research.json" \
    --include "main_results.json" \
    --include "run_main_*.log" \
    --include "run_vic_*.log" \
    --include "processing_status.json" \
    --verbose \
    2>&1 || echo "WARNING: rclone sync failed"

# Cleanup
echo ""
echo "=== Cleanup ==="
rm -f "$OUTPUT_DIR/suburb_research_prompts.json"
rm -f "$OUTPUT_DIR/main_results.json"
rm -f "$OUTPUT_DIR/main_results_backup.json"
rm -f "$OUTPUT_DIR/prompts_main_backup.json"

echo ""
echo "============================================"
echo "Completed: $(date)"
echo "Google Drive: $GDRIVE_PATH"
df -h / | tail -1
echo "============================================"
