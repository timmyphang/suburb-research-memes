#!/bin/bash
# Simplified Codex Suburb Research - VM Startup
# Runs independently on gcloud VM using Codex CLI with native web search

cd /home/tim

echo "========================================="
echo "Codex Suburb Research - Starting"
echo "========================================="
echo "Start time: $(date)"
echo ""

# Check if Codex is available
if ! command -v codex &> /dev/null; then
    echo "ERROR: Codex CLI not found in PATH"
    echo "Please install Codex first: https://github.com/openai/codex"
    exit 1
fi

echo "Codex CLI found: $(which codex)"
echo "Codex version: $(codex --version 2>&1 | head -1)"
echo ""

# Check if prompts exist
if [ ! -f "/home/tim/suburb_research_output/suburb_research_prompts.json" ]; then
    echo "ERROR: Prompts file not found!"
    echo "Run: python3 /home/tim/generate_codex_prompts.py"
    exit 1
fi

echo "Prompts ready: $(wc -l < /home/tim/suburb_research_output/suburb_research_prompts.json) bytes"
echo ""

# Run the batch processor in background
echo "Starting batch processor (using full VM capacity)..."
echo "Logs: /home/tim/suburb_research_output/codex_processing.log"
echo "PID will be written to /tmp/codex_research.pid"
echo ""

nohup python3 /home/tim/codex_batch_processor.py \
    > /home/tim/suburb_research_output/codex_processing.log 2>&1 &
    
PID=$!
echo $PID > /tmp/codex_research.pid

echo "Process started with PID: $PID"
echo ""
echo "To monitor: tail -f /home/tim/suburb_research_output/codex_processing.log"
echo "To check status: cat /home/tim/suburb_research_output/processing_status.json"
echo "To stop: kill $PID"
echo ""
echo "========================================="
echo "Startup complete!"
echo "========================================="
