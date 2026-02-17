import os
import requests
import logging
import json
import math
import base64
from typing import Optional, List, Dict
import google.generativeai as genai
from openai import OpenAI
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

class VisionAgent:
    def __init__(self):
        self.google_api_key = os.getenv("GOOGLE_STREET_VIEW_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.xai_api_key = os.getenv("XAI_API_KEY")
        
        # Initialize Gemini
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("Gemini Vision model initialized.")
            except Exception as e:
                logger.error(f"Error initializing Gemini: {e}")
                self.gemini_model = None
        else:
            self.gemini_model = None

        # Initialize OpenAI
        if self.openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized.")
            except Exception as e:
                logger.error(f"Error initializing OpenAI: {e}")
                self.openai_client = None
        else:
            self.openai_client = None

        # Initialize xAI (Grok) - uses OpenAI client
        if self.xai_api_key:
            try:
                self.xai_client = OpenAI(
                    api_key=self.xai_api_key,
                    base_url="https://api.x.ai/v1"
                )
                logger.info("xAI client initialized.")
            except Exception as e:
                logger.error(f"Error initializing xAI: {e}")
                self.xai_client = None
        else:
            self.xai_client = None

        if not any([self.gemini_model, self.openai_client, self.xai_client]):
            logger.warning("No Vision API keys found. Vision analysis will be mocked.")

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_lambda = math.radians(lon2 - lon1)
        
        y = math.sin(delta_lambda) * math.cos(phi2)
        x = math.cos(phi1) * math.sin(phi2) - \
            math.sin(phi1) * math.cos(phi2) * math.cos(delta_lambda)
        
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360

    def _geocode_address(self, address: str) -> Optional[Dict[str, float]]:
        if not self.google_api_key:
            return None
        try:
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {"address": address, "key": self.google_api_key}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "OK":
                    location = data["results"][0]["geometry"]["location"]
                    return {"lat": location["lat"], "lng": location["lng"]}
                else:
                    logger.warning(f"Geocoding failed status: {data['status']}. Msg: {data.get('error_message', 'No message')}")
            else:
                logger.error(f"Geocoding API returned status code {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Geocoding error: {e}")
            return None

    async def get_street_view_images(self, address: str) -> List[str]:
        """
        Fetches up to 3 angles of the property: Front, Left 45, Right 45.
        Returns a list of local file paths.
        """
        if not self.google_api_key:
            logger.info(f"Mocking Street View images for: {address}")
            return ["mock_street_view.jpg"]
            
        try:
            # 1. Geocode the property
            prop_coords = self._geocode_address(address)
            if not prop_coords:
                logger.warning(f"Could not geocode address: {address}. Falling back to default view.")
                # Fallback to simple address-based fetch
                path = await self._fetch_single_image(address, address.replace(' ', '_'), "default")
                return [path] if path else ["mock_street_view.jpg"]

            # 2. Get Street View Metadata to find the camera location
            meta_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
            meta_params = {"location": f"{prop_coords['lat']},{prop_coords['lng']}", "key": self.google_api_key}
            meta_resp = requests.get(meta_url, params=meta_params)
            
            base_heading = 0
            location_param = f"{prop_coords['lat']},{prop_coords['lng']}"
            
            if meta_resp.status_code == 200:
                meta_data = meta_resp.json()
                if meta_data.get("status") == "OK":
                    cam_loc = meta_data["location"]
                    # Calculate bearing from camera to property
                    base_heading = self._calculate_bearing(cam_loc['lat'], cam_loc['lng'], prop_coords['lat'], prop_coords['lng'])
                    logger.info(f"Calculated base heading: {base_heading}")
                else:
                    logger.warning(f"Metadata Status not OK: {meta_data.get('status')}")

            # 3. Fetch images from 3 angles
            angles = [
                ("front", base_heading),
                ("left", (base_heading - 35) % 360),
                ("right", (base_heading + 35) % 360)
            ]
            
            os.makedirs("data", exist_ok=True)
            slug = address.replace(' ', '_').replace(',', '').replace('.', '')
            
            image_paths = []
            for suffix, heading in angles:
                path = await self._fetch_single_image(location_param, slug, suffix, heading)
                if path:
                    image_paths.append(path)
            
            return image_paths if image_paths else ["mock_street_view.jpg"]
            
        except Exception as e:
            logger.error(f"Error in multi-angle acquisition: {e}")
            return ["mock_street_view.jpg"]

    async def _fetch_single_image(self, location: str, slug: str, suffix: str, heading: Optional[float] = None) -> Optional[str]:
        params = {
            "size": "1024x768", # Higher resolution for better Gemini analysis
            "location": location,
            "key": self.google_api_key,
            "fov": 80,
            "pitch": 0,
            "source": "outdoor"
        }
        if heading is not None:
            params["heading"] = heading
            
        url = "https://maps.googleapis.com/maps/api/streetview"
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                path = f"data/{slug}_{suffix}.jpg"
                with open(path, 'wb') as f:
                    f.write(response.content)
                return path
            logger.error(f"Street View API error: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error fetching image {suffix}: {e}")
            return None

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    async def analyze_property_condition(self, image_paths: List[str]) -> List[Dict]:
        """
        Uses Gemini 1.5 Vision (with OpenAI/Grok fallbacks) to detect physical defects.
        """
        if not image_paths or image_paths[0] == "mock_street_view.jpg":
            return [
                {"issue": "Roof Wear", "description": "Visible granule loss and curling shingles across 30% of the roof surface.", "severity": "Medium", "deduction": 5000, "confidence": 0.85},
                {"issue": "Foundation Issues", "description": "Horizontal cracks visible in the stem wall near the front entrance.", "severity": "Medium", "deduction": 8000, "confidence": 0.70}
            ]

        prompt = """
        You are a Licensed Property Inspector and Real Estate Appraisal Expert.
        Analyze the provided Street View images of a residential property to identify physical defects that justify a reduction in taxable value.
        
        Categories to inspect:
        1. Foundation: Visible cracks in slab/skirting, uneven siding, or doors/windows that appear out of square.
        2. Roofing: Curled or missing shingles, discoloration, sagging ridge lines, or moss/debris buildup.
        3. Exterior Condition: Peeling paint, rotting wood trim, cracked windows, or damaged siding/brickwork.
        4. Site Issues: Cracked driveway, overgrown trees impacting the structure, or signs of poor drainage.
        
        For each genuine defect identified:
        - Provide a concise 'issue' name.
        - A detailed 'description' of what is visible.
        - A 'severity' level (Low, Medium, High).
        - An estimated 'deduction' in property value (USD) based on typical repair costs (range $1,000 - $25,000).
        - A 'confidence' score between 0.0 and 1.0.
        - Provide bounding box coordinates [ymin, xmin, ymax, xmax] normalized to 1000 for the defect location.
        
        IMPORTANT: If the images are blurry or the house is obscured by trees, mention that. If no issues are found, return an empty list.
        
        Return ONLY a JSON list of objects:
        [{"issue": "...", "description": "...", "severity": "...", "deduction": 123, "confidence": 0.9, "bbox": [ymin, xmin, ymax, xmax]}]
        """

        # 1. Try Gemini
        if self.gemini_model:
            try:
                logger.info("Attempting Vision analysis with Gemini...")
                imgs = [Image.open(p) for p in image_paths if os.path.exists(p)]
                if imgs:
                    response = self.gemini_model.generate_content([prompt] + imgs)
                    return self._parse_json_response(response.text)
            except Exception as e:
                logger.warning(f"Gemini Vision failed: {e}. Falling back...")

        # 2. Try OpenAI (GPT-4o)
        if self.openai_client:
            try:
                logger.info("Attempting Vision analysis with OpenAI (GPT-4o fallback)...")
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                        ]
                    }
                ]
                for p in image_paths:
                    if os.path.exists(p):
                        base64_image = self._encode_image(p)
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=1000,
                    response_format={"type": "json_object"}
                )
                content = response.choices[0].message.content
                # GPT-4o often returns a wrapper object if asked for json_object
                data = json.loads(content)
                if isinstance(data, dict) and "issues" in data:
                    return data["issues"]
                if isinstance(data, list):
                    return data
                # If it's a dict with the issues, return the list within
                for key in data:
                    if isinstance(data[key], list):
                        return data[key]
                return []
            except Exception as e:
                logger.warning(f"OpenAI Vision failed: {e}. Falling back...")

        # 3. Try xAI (Grok-2)
        if self.xai_client:
            try:
                logger.info("Attempting Vision analysis with xAI (Grok fallback)...")
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                        ]
                    }
                ]
                for p in image_paths:
                    if os.path.exists(p):
                        base64_image = self._encode_image(p)
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })

                response = self.xai_client.chat.completions.create(
                    model="grok-2-vision-latest",
                    messages=messages,
                    max_tokens=1000
                )
                return self._parse_json_response(response.choices[0].message.content)
            except Exception as e:
                logger.error(f"xAI Vision failed: {e}")

        logger.error("All Vision providers failed or no keys provided.")
        return []

    def _parse_json_response(self, text: str) -> List[Dict]:
        try:
            # Clean JSON response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            detections = json.loads(text.strip())
            # Sometimes models return a dict with a list inside
            if isinstance(detections, dict):
                for key in detections:
                    if isinstance(detections[key], list):
                        return detections[key]
            return detections if isinstance(detections, list) else []
        except Exception as e:
            logger.error(f"Error parsing Vision JSON: {e}")
            return []

    def draw_detections(self, image_path: str, detections: List[Dict]) -> str:
        """
        Draws red bounding boxes on the image for each detected issue.
        """
        if not os.path.exists(image_path) or image_path == "mock_street_view.jpg":
            return image_path
            
        try:
            with Image.open(image_path).convert("RGB") as img:
                draw = ImageDraw.Draw(img)
                width, height = img.size
                
                has_boxes = False
                if isinstance(detections, list):
                    for det in detections:
                        if not isinstance(det, dict):
                            continue
                        bbox = det.get('bbox')
                        if bbox and len(bbox) == 4:
                            ymin, xmin, ymax, xmax = bbox
                            left = xmin * width / 1000
                            top = ymin * height / 1000
                            right = xmax * width / 1000
                            bottom = ymax * height / 1000
                            
                            # Draw bold red box
                            draw.rectangle([left, top, right, bottom], outline="red", width=6)
                            has_boxes = True
                
                if not has_boxes:
                    return image_path

                annotated_path = image_path.replace(".jpg", "_annotated.jpg")
                img.save(annotated_path)
                return annotated_path
        except Exception as e:
            logger.error(f"Error drawing detections: {e}")
            return image_path

    # Compatibility methods for main.py
    async def get_street_view_image(self, address: str) -> str:
        paths = await self.get_street_view_images(address)
        return paths[0] if paths else "mock_street_view.jpg"

    def detect_condition_issues(self, image_path: str) -> List[Dict]:
        # This is now handled by the async analyze_property_condition
        # For simplicity in the existing main.py flow, we'll keep this but it's better to use the async one.
        # Since this tool is synchronous, we won't be able to call the async gemini here without a bridge.
        # Let's update main.py to use the async version instead.
        return []

    def calculate_total_deduction(self, detections: List[Dict]) -> float:
        return sum(d.get('deduction', 0) for d in detections)
