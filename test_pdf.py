import asyncio
import logging
import os
from backend.db.supabase_client import supabase_service
from backend.services.narrative_pdf_service import PDFService

logging.basicConfig(level=logging.INFO)

async def test_pdf():
    print("Fetching 1311040030008...")
    prop = await supabase_service.get_property_by_account('1311040030008')
    if not prop: return
        
    pdf_service = PDFService()
    # Provide mock empty data for the rest since we only care about testing the cover page drawing logic
    output_path = os.path.join(os.getcwd(), 'test_cover.pdf')
    try:
        pdf_service.generate_evidence_packet("Test Narrative", prop, {}, [], output_path)
        print(f"Success! PDF written to {output_path}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_pdf())
