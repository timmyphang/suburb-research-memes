#!/bin/bash
# Watches for main batch to finish, then runs VIC batch + sync
set -e

export AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY"

OUTPUT_DIR="$HOME/suburb_research_output"
GDRIVE_PATH="gdrive:suburb-research-memes-output"

echo "=== Waiting for main batch to finish ==="
while pgrep -f "python3 pi_batch_processor" > /dev/null 2>&1; do
    sleep 30
done
echo "Main batch finished at $(date)"

# ── Run VIC batch ──
echo ""
echo "=== Starting VIC batch (363 suburbs) ==="

cp "$OUTPUT_DIR/suburb_research_prompts.json" "$OUTPUT_DIR/prompts_main_backup.json"
MAIN_RESULTS="$OUTPUT_DIR/all_suburb_research.json"
if [ -f "$MAIN_RESULTS" ]; then
    mv "$MAIN_RESULTS" "$OUTPUT_DIR/main_results.json"
fi
cp "$OUTPUT_DIR/vic_batch_prompts.json" "$OUTPUT_DIR/suburb_research_prompts.json"

python3 -c "
import json
from datetime import datetime
s = {'total': 363, 'pending': 363, 'processing': 0, 'completed': 0, 'failed': 0, 'generated_at': datetime.now().isoformat()}
json.dump(s, open('$OUTPUT_DIR/processing_status.json', 'w'), indent=2)
"

cd ~/suburb-research-memes
python3 pi_batch_processor.py 2>&1 | tee "$OUTPUT_DIR/run_vic_$(date +%Y%m%d_%H%M%S).log"

# ── Merge ──
echo "=== Merging ==="
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

# ── Sync ──
echo "=== Syncing to Google Drive ==="
rclone copy "$OUTPUT_DIR/" "$GDRIVE_PATH/" --include "all_suburb_research.json" --include "run_main_*.log" --include "run_vic_*.log" --verbose 2>&1 || true

# ── Cleanup ──
rm -f "$OUTPUT_DIR/suburb_research_prompts.json" "$OUTPUT_DIR/main_results.json" "$OUTPUT_DIR/prompts_main_backup.json"

echo "=== All done: $(date) ==="
df -h / | tail -1
