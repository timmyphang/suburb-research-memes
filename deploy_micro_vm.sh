#!/bin/bash
# Deploy and run on e2-micro VM (limited resources)
# Usage: bash deploy_micro_vm.sh [vm-name] [zone]

VM_NAME="${1:-your-vm-name}"
ZONE="${2:-australia-southeast1-a}"

echo "========================================="
echo "Deploying to e2-micro VM"
echo "VM: $VM_NAME"
echo "Zone: $ZONE"
echo "========================================="

# Check if VM exists
if ! gcloud compute instances describe $VM_NAME --zone=$ZONE &>/dev/null; then
    echo "ERROR: VM $VM_NAME not found in zone $ZONE"
    exit 1
fi

echo "[1/4] Creating project directory on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE -- "mkdir -p /home/tim/suburb-research"

echo "[2/4] Copying files to VM (lightweight - no prompt_batches)..."
gcloud compute scp /home/tim/codex_batch_processor.py $VM_NAME:/home/tim/suburb-research/ --zone=$ZONE
gcloud compute scp /home/tim/start_codex_research.sh $VM_NAME:/home/tim/suburb-research/ --zone=$ZONE
gcloud compute scp -r /home/tim/suburb_research_output $VM_NAME:/home/tim/suburb-research/ --zone=$ZONE

echo "[3/4] Setting permissions on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE -- "chmod +x /home/tim/suburb-research/*.sh /home/tim/suburb-research/*.py"

echo "[4/4] Starting research process on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE -- "cd /home/tim/suburb-research && bash start_codex_research.sh"

echo ""
echo "========================================="
echo "Deployment complete!"
echo "========================================="
echo ""
echo "Monitor progress (run this command):"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE -- 'tail -f /home/tim/suburb-research/suburb_research_output/codex_processing.log'"
echo ""
echo "Check status:"
echo "  gcloud compute ssh $VM_NAME --zone=$ZONE -- 'cat /home/tim/suburb-research/suburb_research_output/processing_status.json'"
echo ""
echo "Estimated time: 6-8 hours on e2-micro (710 suburbs, 2 workers)"
