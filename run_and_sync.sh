#!/bin/bash
set -e

export AZURE_OPENAI_API_KEY="$AZURE_OPENAI_API_KEY"

REPO_DIR="$HOME/suburb-research-memes"
OUTPUT_DIR="$HOME/suburb_research_output"
GDRIVE_PATH="gdrive:suburb-research-memes-output"

cd "$REPO_DIR"

echo "============================================"
echo "Suburb Research Batch Processor"
echo "Started: $(date)"
echo "============================================"

echo "[1/3] Running pi_batch_processor.py (1 worker)..."
python3 pi_batch_processor.py 2>&1 | tee "$OUTPUT_DIR/run_$(date +%Y%m%d_%H%M%S).log"
EXIT_CODE=${PIPESTATUS[0]}

if [ $EXIT_CODE -ne 0 ]; then
    echo "ERROR: Processor exited with code $EXIT_CODE — skipping sync & cleanup"
    exit $EXIT_CODE
fi

echo ""
echo "[2/3] Syncing results to Google Drive..."
rclone copy "$OUTPUT_DIR/" "$GDRIVE_PATH/" \
    --create-empty-src-dirs \
    --verbose \
    2>&1 || echo "WARNING: rclone sync failed (non-fatal)"

echo ""
echo "[3/3] Cleaning up local outputs..."
find "$OUTPUT_DIR" -name "all_suburb_research.json" -delete
find "$OUTPUT_DIR" -name "suburb_research_prompts.json" -delete

echo ""
echo "============================================"
echo "Completed: $(date)"
echo "Google Drive: $GDRIVE_PATH"
df -h / | tail -1
echo "============================================"
