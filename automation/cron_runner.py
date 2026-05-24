#!/usr/bin/env python3
"""
MIMO 100T Cron Runner - Continuous form submission
Generates new email each run, fills form, submits, logs results.
"""
import asyncio
import json
import os
import sys
import time
import random
import string
from datetime import datetime
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from automation.fill_form import (
    Config, TempMailClient, CaptchaSolver, FormFiller
)

LOG_FILE = os.path.expanduser("~/mimo-devflow/automation/cron_log.jsonl")
MAX_RETRIES = 2

def log_result(entry: dict):
    """Append result to JSONL log"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

async def single_run():
    """Single automation run - generate email, fill form, submit"""
    run_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    start = time.time()
    
    print(f"[{datetime.now().isoformat()}] Starting run {run_id}")
    
    # Step 1: Generate temp email
    tempmail = TempMailClient(Config.TEMPMAIL_API_KEY)
    try:
        mailbox = await tempmail.create_mailbox()
        email = mailbox.get("address", "")
        mailbox_id = mailbox.get("id", "")
        print(f"  Email: {email}")
    except Exception as e:
        print(f"  TempMail error: {e}")
        suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        email = f"mimodev_{suffix}@morvo.me"
        mailbox_id = None
    
    # Step 2: Fill form with Playwright
    filler = FormFiller(email, Config.PROOF_IMAGES_DIR)
    status = "FAILED"
    error_msg = ""
    
    try:
        await filler.init_browser()
        await filler.navigate_to_form()
        
        # Fill all fields
        await filler.fill_email()
        await filler.select_ai_tools(Config.AI_TOOLS)
        await filler.select_model_series(Config.MODEL_SERIES)
        await filler.fill_project_description(Config.PROJECT_DESCRIPTION)
        await filler.upload_proof_images()
        await filler.fill_github_link(Config.GITHUB_LINK)
        
        # Handle captcha
        await filler.handle_captcha()
        
        # Submit
        await filler.submit_form()
        
        result = await filler.get_result()
        status = result
        print(f"  Result: {result}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"  ERROR: {error_msg}")
    finally:
        await filler.close()
        await tempmail.close()
    
    duration = round(time.time() - start, 1)
    
    entry = {
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(),
        "email": email,
        "status": status,
        "error": error_msg,
        "duration_s": duration
    }
    log_result(entry)
    print(f"  Completed in {duration}s - Status: {status}")
    return entry

async def main():
    print(f"{'='*60}")
    print(f"MIMO 100T Cron Run - {datetime.now().isoformat()}")
    print(f"{'='*60}")
    
    for attempt in range(MAX_RETRIES):
        try:
            result = await single_run()
            if result["status"] == "SUCCESS":
                print(f"\n✅ SUCCESS on attempt {attempt+1}")
                return
            else:
                print(f"\n⚠️ Attempt {attempt+1} status: {result['status']}")
                if attempt < MAX_RETRIES - 1:
                    wait = random.randint(10, 30)
                    print(f"  Retrying in {wait}s...")
                    await asyncio.sleep(wait)
        except Exception as e:
            print(f"\n❌ Attempt {attempt+1} failed: {e}")
            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(15)
    
    print(f"\n❌ All {MAX_RETRIES} attempts completed without confirmed success")

if __name__ == "__main__":
    asyncio.run(main())
