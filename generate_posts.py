#!/usr/bin/env python3
"""
Generate Instagram posts from suburb research profiles using GPT-5-mini.
Each post saved as separate JSON, synced to Drive, then deleted locally.
"""

import json, os, time, httpx, subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

AZURE_BASE_URL = "https://gai-443-openai.openai.azure.com/openai/v1"
DEPLOYMENT = "gpt-5-mini"
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
REQUEST_TIMEOUT = 180
MAX_WORKERS = 5
LOCAL_DIR = Path.home() / "suburb_research_output" / "posts"
INPUT_FILE = Path.home() / "suburb_research_output" / "all_batches_combined.json"
GDRIVE_DIR = "gdrive:suburb-research-memes-output/posts"
PROGRESS_FILE = Path.home() / "suburb_research_output" / "posts_progress.json"

POST_SYSTEM = """You are a sharp Australian cultural commentator. Think The Chaser meets Kath and Kim. 
You write 400-word Instagram posts about Australian suburbs that are affectionate roasts.

STYLE RULES:
- Write in first person "we" voice, as if you are a proud local
- Open with a hook that captures the suburb essence in one specific image
- Weave in SPECIFIC details: actual cafe names, car models, clothing brands, dog breeds, street names
- Include a morning or weekend routine vignette
- Include a petty local drama (bin disputes, parking wars, cafe loyalty, strata battles)
- End with a misfit paragraph: who would HATE living here, and why they clash
- Close with a warm welcome: who would LOVE it and why
- Keep it PG-13, punch up at pretensions, never down at genuine struggles
- NO race, religion, politics, sexuality, disability references
- Output ONLY the post text. No preamble, no markdown, no JSON.
- Target about 400 words. Make every sentence quotable."""

def slugify(name):
    return name.lower().replace(" ", "-")

def generate_post(entry):
    suburb_name = entry.get("suburb", "Unknown")
    profile_data = entry.get("profile", entry)
    
    parts = []
    
    stereotype = profile_data.get("stereotype", {})
    if isinstance(stereotype, dict):
        desc = stereotype.get("description", "")
        if desc:
            parts.append("STEREOTYPE: " + desc)
        examples = stereotype.get("examples", [])
        if examples:
            parts.append("Examples: " + "; ".join(examples[:3]))
    
    drama = profile_data.get("local_drama", {})
    if isinstance(drama, dict):
        desc = drama.get("description", "")
        if desc:
            parts.append("LOCAL DRAMA: " + desc)
        details = drama.get("details", [])
        if details:
            parts.append("Details: " + "; ".join(details[:2]))
    
    ideal = profile_data.get("ideal_resident", {})
    if isinstance(ideal, dict):
        persona = ideal.get("persona", "")
        if persona:
            parts.append("IDEAL RESIDENT: " + persona)
        routine = ideal.get("weekend_routine", "")
        if routine:
            parts.append("Their weekend: " + routine)
        habits = ideal.get("habits", "")
        if habits:
            parts.append("Their habits: " + habits)
    
    misfit = profile_data.get("misfit", {})
    if isinstance(misfit, dict):
        persona = misfit.get("persona", "")
        if persona:
            parts.append("MISFIT: " + persona)
        clash = misfit.get("clash_reason", "")
        if clash:
            parts.append("Why they clash: " + clash)
    
    context = "\n\n".join(parts)
    user_msg = "Write a 400-word Instagram post about " + suburb_name + " using these research notes:\n\n" + context + "\n\nWrite the post now."

    body = {
        "model": DEPLOYMENT,
        "messages": [
            {"role": "system", "content": POST_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_completion_tokens": 2000,
    }

    headers = {"api-key": API_KEY, "Content-Type": "application/json"}
    url = AZURE_BASE_URL.rstrip("/") + "/chat/completions"

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            r = client.post(url, headers=headers, json=body)
        if r.status_code != 200:
            return None, "HTTP " + str(r.status_code) + ": " + r.text[:200]
        content = r.json()["choices"][0]["message"]["content"]
        return content.strip(), None
    except Exception as e:
        return None, str(e)

def upload_and_clean(slug, local_path):
    """Upload to Drive and delete local file."""
    remote = GDRIVE_DIR + "/" + slug + ".json"
    try:
        subprocess.run(
            ["rclone", "copyto", str(local_path), remote, "--timeout", "30s"],
            capture_output=True, timeout=35
        )
        local_path.unlink()
        return True
    except Exception as e:
        print("    rclone error for " + slug + ": " + str(e)[:100])
        return False

def process_one(entry, idx, total):
    suburb = entry.get("suburb", "Unknown")
    slug = slugify(suburb)
    
    local_path = LOCAL_DIR / (slug + ".json")
    
    post_text, error = generate_post(entry)
    
    if post_text:
        record = {
            "suburb": suburb,
            "slug": slug,
            "post": post_text,
            "generated_at": datetime.now().isoformat()
        }
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "w") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        
        success = upload_and_clean(slug, local_path)
        if success:
            print("  [" + str(idx) + "/" + str(total) + "] OK " + suburb)
            return slug, True
        else:
            print("  [" + str(idx) + "/" + str(total) + "] OK " + suburb + " (upload failed, kept local)")
            return slug, "local_only"
    else:
        print("  [" + str(idx) + "/" + str(total) + "] FAIL " + suburb + ": " + str(error)[:100])
        return slug, False

def main():
    if not API_KEY:
        print("ERROR: AZURE_OPENAI_API_KEY not set")
        return

    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    with open(INPUT_FILE) as f:
        entries = json.load(f)
    
    # Load progress to skip already-done
    done = set()
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            done = set(json.load(f).get("done", []))
    
    pending = [(i, e) for i, e in enumerate(entries) if slugify(e.get("suburb", "")) not in done]
    total = len(entries)
    
    print("Total: " + str(total) + " | Already done: " + str(len(done)) + " | Pending: " + str(len(pending)))
    print("Using " + str(MAX_WORKERS) + " workers")
    print("Start: " + str(datetime.now()))
    print("=" * 60)

    if not pending:
        print("All done!")
        return

    completed = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_one, entry, idx + 1, total): entry
            for idx, entry in pending
        }

        for future in as_completed(futures):
            slug, status = future.result()
            if status == True:
                completed += 1
                done.add(slug)
            elif status == "local_only":
                completed += 1
                done.add(slug)
            else:
                failed += 1
            
            # Save progress every 20
            if (completed + failed) % 20 == 0:
                with open(PROGRESS_FILE, "w") as f:
                    json.dump({"done": list(done), "total": total, "completed": completed, "failed": failed}, f)
                print("  --- Progress: " + str(completed) + " ok, " + str(failed) + " fail, " + str(total - completed - failed) + " remaining ---")

    # Final sync: upload any files still local
    remaining = list(LOCAL_DIR.glob("*.json"))
    if remaining:
        print("\nUploading " + str(len(remaining)) + " remaining local files...")
        for p in remaining:
            slug = p.stem
            upload_and_clean(slug, p)

    with open(PROGRESS_FILE, "w") as f:
        json.dump({"done": list(done), "total": total, "completed": completed, "failed": failed}, f)

    print("\n" + "=" * 60)
    print("Done: " + str(completed) + " posts, " + str(failed) + " failed")
    print("End: " + str(datetime.now()))

if __name__ == "__main__":
    main()
