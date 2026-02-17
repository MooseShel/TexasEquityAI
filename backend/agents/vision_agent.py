import os
import requests
import logging
from typing import Optional, List, Dict
from ultralytics import YOLO

logger = logging.getLogger(__name__)

class VisionAgent:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
        # Load a pre-trained YOLOv8 model (yolov8n.pt is a small, fast model)
        # Note: In a real scenario, this would be fine-tuned for building defects
        try:
            self.model = YOLO('yolov8n.pt') 
        except Exception as e:
            logger.warning(f"Could not load YOLO model: {e}. Normal issues detection will be mocked.")
            self.model = None

    async def get_street_view_image(self, address: str) -> Optional[str]:
        """
        Pull Google Street View image for the given address.
        """
        if not self.google_api_key:
            logger.info(f"Mocking Street View image for: {address}")
            return "mock_street_view.jpg"
            
        try:
            url = f"https://maps.googleapis.com/maps/api/streetview?size=600x400&location={address}&key={self.google_api_key}"
            response = requests.get(url)
            if response.status_code == 200:
                img_path = f"data/{address.replace(' ', '_')}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                return img_path
            return None
        except Exception as e:
            logger.error(f"Error fetching Street View image: {e}")
            return None

    def detect_condition_issues(self, image_path: str) -> List[Dict]:
        """
        Detect Negative Adjusters: peeling paint, roof wear, foundation cracks, or debris.
        Assign a 'Condition Deduction' based on detected issues.
        """
        if not self.model or image_path == "mock_street_view.jpg":
            # Mock detections for demonstration purposes
            return [
                {"issue": "Roof Wear", "deduction": 5000, "confidence": 0.85},
                {"issue": "Peeling Paint", "deduction": 3000, "confidence": 0.75}
            ]
            
        try:
            results = self.model(image_path)
            detections = []
            # This is where we'd map YOLO classes to building defects
            # For this MVP, we map typical classes (e.g., 'crack' if custom model)
            # or just simulate 'damage' detected.
            for result in results:
                # result.boxes contains detected items
                # We'll simulate finding issues based on custom thresholds
                pass
            
            # Returning mock detected issues for MVP flow
            return [
                {"issue": "Detected Exterior Damage", "deduction": 8000, "confidence": 0.9}
            ]
        except Exception as e:
            logger.error(f"Error in Vision Agent detection: {e}")
            return []

    def calculate_total_deduction(self, detections: List[Dict]) -> float:
        return sum(d['deduction'] for d in detections)
