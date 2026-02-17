from fastapi import FastAPI, HTTPException
from backend.agents.hcad_scraper import HCADScraper
from backend.agents.non_disclosure_bridge import NonDisclosureBridge
from backend.agents.equity_agent import EquityAgent
from backend.agents.vision_agent import VisionAgent
from backend.services.narrative_pdf_service import NarrativeAgent, PDFService
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="Texas Equity AI API")

# Initialize Agents
scraper = HCADScraper()
bridge = NonDisclosureBridge()
equity_engine = EquityAgent()
vision_agent = VisionAgent()
narrative_agent = NarrativeAgent()
pdf_service = PDFService()

@app.get("/")
async def root():
    return {"message": "Texas Equity AI API is running"}

@app.get("/protest/{account_number}")
async def get_full_protest(account_number: str):
    # 1. Scrape HCAD
    property_details = await scraper.get_property_details(account_number)
    if not property_details:
        # Fallback for demo
        property_details = {
            "account_number": account_number,
            "address": "123 Example St, Houston, TX",
            "appraised_value": 450000,
            "building_area": 2500
        }

    # 2. Get Market Data / Fallback
    market_value = await bridge.get_last_sale_price(property_details['address'])
    if not market_value:
        market_value = await bridge.get_estimated_market_value(
            property_details['appraised_value'], 
            property_details['address']
        )

    # 3. Equity Analysis
    # Mock neighborhood for MVP
    mock_neighborhood = [
        {"address": f"{100+i} Example St", "appraised_value": 400000 + (i*5000), "building_area": 2400 + (i*20)}
        for i in range(20)
    ]
    equity_results = equity_engine.find_equity_5(property_details, mock_neighborhood)

    # 4. Vision Analysis
    image_path = await vision_agent.get_street_view_image(property_details['address'])
    vision_detections = vision_agent.detect_condition_issues(image_path)

    # 5. Narrative & PDF
    narrative = narrative_agent.generate_protest_narrative(property_details, equity_results, vision_detections)
    
    return {
        "property": property_details,
        "market_value": market_value,
        "equity": equity_results,
        "vision": vision_detections,
        "narrative": narrative
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
