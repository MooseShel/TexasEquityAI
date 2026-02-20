import os
import requests
import logging
import json
import math
import base64
from typing import Optional, List, Dict
from google import genai
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
                self.gemini_client = genai.Client(api_key=self.gemini_api_key)
                logger.info("Gemini Vision client initialized (google-genai).")
            except Exception as e:
                logger.error(f"Error initializing Gemini: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None

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

        if not any([self.gemini_client, self.openai_client, self.xai_client]):
            logger.warning("No Vision API keys found. Vision analysis will be skipped.")

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
            logger.info(f"No Google API key. Skipping Street View for: {address}")
            return []
            
        try:
            # 1. Geocode the property (used for heading calculation only)
            prop_coords = self._geocode_address(address)
            
            # 2. Get Street View Metadata to find the camera location for heading
            base_heading = 0
            # Use address string directly for Street View — avoids snapping to wrong nearby panorama
            location_param = address  # e.g. "843 LAMONTE LN HOUSTON TX 77018"
            
            if prop_coords:
                meta_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
                meta_params = {"location": f"{prop_coords['lat']},{prop_coords['lng']}", "key": self.google_api_key}
                meta_resp = requests.get(meta_url, params=meta_params)
                
                if meta_resp.status_code == 200:
                    meta_data = meta_resp.json()
                    if meta_data.get("status") == "OK":
                        cam_loc = meta_data["location"]
                        # Calculate bearing from camera to property
                        base_heading = self._calculate_bearing(cam_loc['lat'], cam_loc['lng'], prop_coords['lat'], prop_coords['lng'])
                        logger.info(f"Calculated base heading: {base_heading}")
                    else:
                        logger.warning(f"Metadata Status not OK: {meta_data.get('status')}")
            else:
                logger.warning(f"Could not geocode {address} for heading — using default heading 0.")

            # 3. Fetch images from 3 angles, using address string as location
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
            
            return image_paths
            
        except Exception as e:
            logger.error(f"Error in multi-angle acquisition: {e}")
            return []

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

    async def analyze_property_condition(self, image_paths: List[str], property_data: dict = None) -> List[Dict]:
        """
        Uses OpenAI GPT-4o (primary), Gemini (secondary w/ retry), Grok (tertiary)
        to detect physical defects and estimate depreciation.
        """
        if not image_paths or image_paths[0] == "mock_street_view.jpg":
             logger.info("No valid images for vision analysis.")
             return []

        # Build context-aware prompt with property details
        prop_value = 0
        prop_age = "Unknown"
        prop_sqft = 0
        prop_type = "residential"
        if property_data:
            prop_value = property_data.get('appraised_value', 0) or 0
            year_built = property_data.get('year_built', 0)
            if year_built and int(str(year_built)[:4]) > 1900:
                import datetime
                prop_age = f"{datetime.datetime.now().year - int(str(year_built)[:4])} years (built {year_built})"
            prop_sqft = property_data.get('building_area', 0) or 0
            prop_type = property_data.get('property_type', 'residential')

        prompt = f"""
        You are a Licensed Texas Property Inspector and Certified Residential Appraiser.
        Analyze the provided Street View images of a {prop_type} property.
        
        PROPERTY CONTEXT:
        - Current Appraised Value: ${prop_value:,.0f}
        - Age: {prop_age}
        - Building Area: {prop_sqft:,.0f} sqft
        
        Inspect for depreciation under three Texas appraisal categories:
        
        1. PHYSICAL DETERIORATION (curable & incurable):
           - Foundation: Cracks in slab/skirting, settling, uneven surfaces
           - Roof: Missing/curling shingles, sagging ridge, moss/debris, age-related wear
           - Exterior: Peeling paint, rotting wood, damaged siding/brick, cracked windows
           - Driveway/Walkways: Cracks, heaving, deterioration
        
        2. FUNCTIONAL OBSOLESCENCE:
           - Outdated design elements, poor layout indicators, inadequate features
           - Single-car garage in multi-car neighborhood, no covered entry
        
        3. EXTERNAL OBSOLESCENCE:
           - Power lines/transmission towers, commercial adjacency, busy road
           - Overgrown neighboring lots, abandoned nearby structures
           - Drainage issues, flood-prone indicators
        
        For each genuine defect identified, provide:
        - "issue": concise name
        - "description": detailed observation from the image
        - "severity": "Low", "Medium", or "High"
        - "category": "Physical Deterioration", "Functional Obsolescence", or "External Obsolescence"
        - "deduction": estimated value impact in USD (scale to the ${prop_value:,.0f} property value — e.g. roof replacement ~3-5% of value, foundation ~5-10%, paint ~1-2%)
        - "confidence": 0.0 to 1.0
        - "bbox": [ymin, xmin, ymax, xmax] normalized to 1000

        Also include ONE summary object at the END of the list with:
        - "issue": "CONDITION_SUMMARY"
        - "condition_score": overall condition 1-10 (10=excellent, 1=condemned)
        - "effective_age": estimated effective age in years (may differ from actual age based on maintenance)
        - "total_physical": total physical deterioration deduction
        - "total_functional": total functional obsolescence deduction
        - "total_external": total external obsolescence deduction
        
        IMPORTANT: Be thorough but honest. Only report defects clearly visible in the images.
        If images are blurry or obstructed by trees, note that with low confidence scores.
        If no issues are found, return an empty list.
        
        Return ONLY a valid JSON list of objects.
        """

        image_paths_existing = [p for p in image_paths if os.path.exists(p)]
        if not image_paths_existing:
             logger.info("No valid local images found for analysis.")
             return []

        # 1. Try OpenAI (GPT-4o) - PRIMARY (best structured image analysis)
        if self.openai_client:
            try:
                logger.info("Attempting Vision analysis with OpenAI GPT-4o (Primary)...")
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                        ]
                    }
                ]
                
                valid_images = False
                for p in image_paths_existing:
                    try:
                        base64_image = self._encode_image(p)
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                        valid_images = True
                    except Exception as img_err:
                        logger.error(f"Failed to encode image {p}: {img_err}")

                if valid_images:
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        max_tokens=2000,
                        response_format={"type": "json_object"}
                    )
                    content = response.choices[0].message.content

                    # Guard: model may return None content on refusal or API error
                    if content is None:
                        logger.warning("OpenAI Vision returned None content — falling back to Gemini.")
                    else:
                        try:
                            data = json.loads(content)
                            if isinstance(data, dict):
                                if "issues" in data: return data["issues"]
                                for key, value in data.items():
                                    if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                                        return value
                                return []
                            elif isinstance(data, list):
                                return data
                        except json.JSONDecodeError:
                            return self._parse_json_response(content)

            except Exception as e:
                logger.warning(f"OpenAI Vision failed: {e}. Falling back to Gemini...")

        # 2. Try Gemini - SECONDARY (with retry for transient 429s only)
        if self.gemini_client:
            import time
            retries = [15, 30]  # Backoff delays for transient rate limits
            for attempt in range(len(retries) + 1):
                try:
                    logger.info(f"Attempting Vision analysis with Gemini (attempt {attempt + 1})...")
                    imgs = [Image.open(p) for p in image_paths_existing]
                    if imgs:
                        response = self.gemini_client.models.generate_content(
                            model='gemini-2.0-flash',
                            contents=[prompt] + imgs
                        )
                        return self._parse_json_response(response.text)
                except Exception as e:
                    error_str = str(e)
                    is_quota_exhausted = 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower()
                    if '429' in error_str and attempt < len(retries) and not is_quota_exhausted:
                        # Transient rate limit — worth a retry
                        delay = retries[attempt]
                        logger.warning(f"Gemini 429 rate limit — retrying in {delay}s (attempt {attempt + 1})...")
                        time.sleep(delay)
                    else:
                        if is_quota_exhausted:
                            logger.error(f"Gemini quota exhausted (RESOURCE_EXHAUSTED) — skipping retries, falling back to Grok.")
                        else:
                            logger.error(f"Gemini Vision failed: {e}. Falling back to Grok...")
                        break

        # 3. Try xAI (Grok-2) - TERTIARY
        if self.xai_client:
            try:
                logger.info("Attempting Vision analysis with xAI Grok (Tertiary)...")
                messages = [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                        ]
                    }
                ]
                
                valid_images = False
                for p in image_paths_existing:
                    try:
                        base64_image = self._encode_image(p)
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                        })
                        valid_images = True
                    except: pass

                if valid_images:
                    response = self.xai_client.chat.completions.create(
                        model="grok-2-vision-latest",
                        messages=messages,
                        max_tokens=2000
                    )
                    return self._parse_json_response(response.choices[0].message.content)
            except Exception as e:
                logger.warning(f"xAI Vision failed: {e}.")

        logger.error("All Vision providers failed.")
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
        return paths[0] if paths else ""

    def detect_condition_issues(self, image_path: str) -> List[Dict]:
        # This is now handled by the async analyze_property_condition
        # For simplicity in the existing main.py flow, we'll keep this but it's better to use the async one.
        # Since this tool is synchronous, we won't be able to call the async gemini here without a bridge.
        # Let's update main.py to use the async version instead.
        return []

    def calculate_total_deduction(self, detections: List[Dict]) -> float:
        return sum(d.get('deduction', 0) for d in detections)
