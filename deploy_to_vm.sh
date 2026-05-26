#!/bin/bash
# Deploy suburb-research-memes to gcloud VM
# Run this from your local machine

set -e

VM_NAME="${1:-suburb-research-vm}"
ZONE="${2:-australia-southeast1-a}"

echo "========================================="
echo "Deploying to gcloud VM"
echo "VM: $VM_NAME"
echo "Zone: $ZONE"
echo "========================================="

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo "ERROR: VM $VM_NAME not found in zone $ZONE"
    echo "Create it first with: gcloud compute instances create $VM_NAME --zone=$ZONE --machine-type=e2-standard-8"
    exit 1
fi

echo "[1/3] Copying files to VM..."
gcloud compute scp --recurse \
    /home/tim/sydney-suburb-research/codex_batch_processor.py \
    /home/tim/sydney-suburb-research/start_codex_research.sh \
    /home/tim/sydney-suburb-research/suburb_research_output \
    $VM_NAME:/home/tim/suburb-research/ --zone=$ZONE

echo "[2/3] Setting permissions..."
gcloud compute ssh $VM_NAME --zone=$ZONE -- "chmod +x /home/tim/suburb-research/*.sh /home/tim/suburb-research/*.py"

echo "[3/3] Starting research process..."
gcloud compute ssh $VM_NAME --zone=$ZONE -- "cd /home/tim/suburb-research && bash start_codex_research.sh"

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="
echo ""
echo "To monitor progress:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE -- 'tail -f /home/tim/suburb-research/suburb_research_output/codex_processing.log'"
echo ""
echo "To check status:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE -- 'cat /home/tim/suburb-research/suburb_research_output/processing_status.json'"
echo ""
