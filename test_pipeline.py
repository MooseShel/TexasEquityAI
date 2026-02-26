"""Quick test of protest pipeline."""
import sys, os
sys.path.insert(0, r'c:\Users\Husse\Documents\TexasEquityAI')
sys.path.insert(0, r'c:\Users\Husse\Documents\TexasEquityAI\frontend_reflex')
from dotenv import load_dotenv
load_dotenv(r'c:\Users\Husse\Documents\TexasEquityAI\.env')
import asyncio, traceback

async def test():
    try:
        from texas_equity_ai.services.protest_service import run_protest_pipeline
        count = 0
        async for update in run_protest_pipeline('0660460360030', 'HCAD'):
            count += 1
            if 'status' in update:
                msg = update['status']
                print(f'[STATUS {count}] {msg[:80]}')
            elif 'error' in update:
                print(f'[ERROR] {update["error"]}')
            elif 'warning' in update:
                print(f'[WARN] {update["warning"]}')
            elif 'data' in update:
                d = update['data']
                pkeys = list(d.get('property', {}).keys())[:5]
                print(f'[DATA] property keys: {pkeys}')
                print(f'[DATA] narrative len: {len(d.get("narrative", ""))}')
                print(f'[DATA] pdf: {d.get("combined_pdf_path")}')
            if count > 30:
                print('Stopping after 30 updates...')
                break
        print(f'Done. Total updates: {count}')
    except Exception:
        traceback.print_exc()

asyncio.run(test())
