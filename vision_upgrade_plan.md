# Vision Agent Upgrade Plan: "The Visual Inspector"

To move the Vision Agent from a prototype to a professional-grade evidence generator, we have shifted from basic object detection (YOLO) to an **AI-powered Visual Assessment** system.

## Phase 1: Advanced Image Acquisition (COMPLETE)
*   **[x] Geocoding Integration**: Resolve addresses to exact Latitude/Longitude before calling Street View. This ensures the camera is centered on the house.
*   **[x] Three-Point Perspective**: Pull three angles (Front-Facing, 45° Left, 45° Right) to capture side-yard issues or roof slope condition.
*   **[x] Automatic Metadata Storage**: Captured bearing and location from Street View Metadata API for optimized orientation.

## Phase 2: Intelligence Upgrade (The "Visual Inspector") (COMPLETE)
*   **[x] Multimodal Analysis (Gemini Vision)**: Replaced YOLO with **Gemini 2.0 Flash**.
    *   **Task**: Acts as a Licensed Property Inspector.
    *   **Target Detections**:
        *   **Foundation**: Cracks, uneven siding (settlement).
        *   **Roofing**: Missing shingles, discoloration (moisture), sagging.
        *   **Exterior**: Peeling paint, rotting wood, cracked windows.
        *   **Landscaping**: Overgrown trees touching the structures (hazard).
*   **[ ] Feature Verification**: Detect if the house matches HCAD's record. (Pending detailed record comparison).

## Phase 3: Evidence & Form Integration (COMPLETE)
*   **[x] Annotated Evidence**: `VisionAgent` generates images with "Red Boxes" around detected issues using normalized bounding boxes from Gemini.
*   **[x] Condition Deductions**: Findings map to specific USD deductions included in the savings calculator.
*   **[x] Form 41.44 Auto-Fill**: Automatically checks the "Property Condition" box on the protest form if external damage is detected.

## Current System Capabilities
1.  **VisionAgent**: Capable of 3-point acquisition and asynchronous condition analysis with **multi-provider fallbacks** (Gemini 2.0 -> GPT-4o -> Grok-2).
2.  **Annotated Imagery**: Bounding boxes drawn on the primary evidence image for visual proof.
3.  **PDF Evidence**: Detailed vision deductions and annotated photos are now automatically integrated into the generated evidence packet.
4.  **Form 41.44**: Section 2 (Reason for Protest) is dynamically updated based on computer vision findings.
