#!/usr/bin/env python3
"""
Generate Instagram posts from suburb research profiles using GPT-5-mini.
Each post saved as separate JSON, synced to Drive, then deleted locally.
"""

import gc, json, os, time, httpx, subprocess
from pathlib import Path
from datetime import datetime

AZURE_BASE_URL = "https://gai-443-openai.openai.azure.com/openai/v1"
DEPLOYMENT = "gpt-5-mini"
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
REQUEST_TIMEOUT = 180
LOCAL_DIR = Path.home() / "suburb_research_output" / "posts"
INPUT_FILE = Path.home() / "suburb_research_output" / "all_suburb_research.json"
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

PROFILER_SYSTEM = """You are an expert comedic strategist and data analyst.
Your objective is to read raw web search snippets about a specific Australian suburb and write a highly restrictive SYSTEM PROMPT for a satirical writer.

INSTRUCTIONS FOR THE PROMPT YOU WILL GENERATE:
1. Identify the most unique, absurd, or highly specific piece of local drama, complaint, or cultural marker from the provided data.
2. Instruct the writer to make that specific event/marker the central theme of a 400-word satirical Instagram post.
3. Explicitly FORBID the use of generic Australian tropes (e.g., Ford Rangers, Lululemon, flat whites, Bunnings) UNLESS they specifically appear in the raw data.
4. Demand the writer adopt a cynical, highly sarcastic internet commentator persona (punching UP at pretensions, not DOWN at genuine struggles).

Output ONLY the final system prompt. Do not include any introductory or explanatory text."""

def slugify(name):
    return name.lower().replace(" ", "-")

def call_azure_with_backoff(body, max_retries=4):
    headers = {"api-key": API_KEY, "Content-Type": "application/json"}
    url = AZURE_BASE_URL.rstrip("/") + "/chat/completions"
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                r = client.post(url, headers=headers, json=body)
            if r.status_code == 200:
                payload = r.json()
                choice = payload["choices"][0]
                content = choice["message"]["content"].strip()
                if not content and choice.get("finish_reason") == "length":
                    wait = (2 ** attempt) * 5
                    print("    Empty response (reasoning exhausted tokens), retrying in " + str(wait) + "s...")
                    time.sleep(wait)
                    continue
                return content, None
            if r.status_code == 429:
                wait = (2 ** attempt) * 5
                print("    Rate limited, retrying in " + str(wait) + "s...")
                time.sleep(wait)
                continue
            if r.status_code == 400:
                return None, "Content filter (400): " + r.text[:200]
            return None, "HTTP " + str(r.status_code) + ": " + r.text[:200]
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * 5
                time.sleep(wait)
                continue
            return None, str(e)
    return None, "Max retries exceeded"

def run_profiler(suburb_name, search_snippets):
    user_msg = "Here is the raw search data for " + suburb_name + ": " + search_snippets
    body = {
        "model": DEPLOYMENT,
        "messages": [
            {"role": "system", "content": PROFILER_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_completion_tokens": 4000,
    }
    return call_azure_with_backoff(body, max_retries=4)

def generate_post(entry):
    suburb_name = entry.get("suburb", "Unknown")
    state = entry.get("state", "NSW")
    location = suburb_name + ", " + state
    searches = entry.get("searches", {})

    # Flatten all search results into a single JSON string for both passes
    all_snippets = {}
    for category, result in searches.items():
        all_snippets[category] = result.get("results", [])
    search_snippets = json.dumps(all_snippets, ensure_ascii=False)

    # Pass 1: Profiler generates a suburb-specific system prompt
    dynamic_system, error = run_profiler(location, search_snippets)
    if error:
        return None, "Pass 1 failed: " + error

    # Pass 2: Satirist uses the dynamic prompt to write the post
    user_msg = "Write a 400-word satirical post for " + location + " based strictly on these search results: " + search_snippets

    body = {
        "model": DEPLOYMENT,
        "messages": [
            {"role": "system", "content": dynamic_system},
            {"role": "user", "content": user_msg},
        ],
        "max_completion_tokens": 8000,
    }

    return call_azure_with_backoff(body, max_retries=4)

def upload_and_clean(slug, local_path):
    """Upload to Drive and delete local file."""
    remote = GDRIVE_DIR + "/" + slug + ".json"
    try:
        result = subprocess.run(
            ["rclone", "copyto", str(local_path), remote, "--timeout", "30s"],
            capture_output=True, timeout=35
        )
        if result.returncode != 0:
            raise Exception(result.stderr.decode()[:100])
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
    del entry  # free search data immediately

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
        del post_text, record

        success = upload_and_clean(slug, local_path)
        gc.collect()
        if success:
            print("  [" + str(idx) + "/" + str(total) + "] OK " + suburb)
            return slug, True
        else:
            print("  [" + str(idx) + "/" + str(total) + "] OK " + suburb + " (upload failed, kept local)")
            return slug, "local_only"
    else:
        gc.collect()
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
    print("Sequential execution (e2-micro safe)")
    print("Start: " + str(datetime.now()))
    print("=" * 60)

    if not pending:
        print("All done!")
        return

    completed = 0
    failed = 0

    for idx, entry in pending:
        slug, status = process_one(entry, idx + 1, total)
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
