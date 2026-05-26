#!/bin/bash
# Setup script for gcloud VM
# Run this on your gcloud VM to set up the suburb research automation

set -e

echo "========================================="
echo "Suburb Research Automation - VM Setup"
echo "========================================="

# Update system
echo "[1/5] Updating system packages..."
apt-get update -q

# Install Python and pip if not present
echo "[2/5] Installing Python dependencies..."
apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
echo "[3/5] Creating virtual environment..."
cd /home/tim
python3 -m venv suburb_research_env
source suburb_research_env/bin/activate

# Install Python packages
echo "[4/5] Installing Python packages..."
pip install -q -r requirements.txt

# Create output directory
echo "[5/5] Creating output directory..."
mkdir -p /home/tim/suburb_research_output

echo ""
echo "========================================="
echo "Setup complete!"
echo "========================================="
echo ""
echo "NEXT STEPS:"
echo "1. Set your Brave API key:"
echo "   export BRAVE_API_KEY='your_api_key_here'"
echo ""
echo "2. Run the research script:"
echo "   source suburb_research_env/bin/activate"
echo "   python3 /home/tim/suburb_research_parallel.py"
echo ""
echo "OR use the startup script:"
echo "   ./start_research.sh"
echo ""
