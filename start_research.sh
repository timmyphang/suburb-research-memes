#!/bin/bash
# Startup script for suburb research - runs in background with full capacity

cd /home/tim
source suburb_research_env/bin/activate

# Check if API key is set
if [ -z "$BRAVE_API_KEY" ]; then
    echo "ERROR: BRAVE_API_KEY environment variable is not set!"
    echo "Please set it with: export BRAVE_API_KEY='your_key_here'"
    exit 1
fi

# Run the parallel version to utilize full capacity
echo "Starting suburb research at $(date)"
echo "Using all available capacity..."

nohup python3 /home/tim/suburb_research_parallel.py > /home/tim/suburb_research_output/research.log 2>&1 &

echo "Process started in background. Check logs at:"
echo "  /home/tim/suburb_research_output/research.log"
echo ""
echo "To monitor progress:"
echo "  tail -f /home/tim/suburb_research_output/research.log"
echo ""
echo "PID: $!"
