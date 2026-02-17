# Vision Agent Upgrade Plan: "The Visual Inspector"

To move the Vision Agent from a prototype to a professional-grade evidence generator, we will shift from basic object detection (YOLO) to an **AI-powered Visual Assessment** system.

## Phase 1: Advanced Image Acquisition (Morning)
*   **Geocoding Integration**: Resolve addresses to exact Latitude/Longitude before calling Street View. This ensures the camera is centered on the house, not the neighbor.
*   **Three-Point Perspective**: Instead of one static image, pull three angles (Front-Facing, 45° Left, 45° Right) to capture side-yard issues or roof slope condition.
*   **Automatic Metadata Storage**: Save the "Date Captured" from Street View. HCAD often uses old data; showing that current imagery shows damage not reflected in their records is a powerful protest point.

## Phase 2: Intelligence Upgrade (The "Visual Inspector")
*   **Multimodal Analysis (Gemini Vision)**: Augment/Replace YOLO with **Gemini 1.5 Pro Vision**.
    *   **Task**: Act as a Licensed Property Inspector.
    *   **Target Detections**:
        *   **Foundation**: Cracks, uneven siding (settlement).
        *   **Roofing**: Missing shingles, discoloration (moisture), sagging.
        *   **Exterior**: Peeling paint, rotting wood, cracked windows.
        *   **Landscaping**: Overgrown trees touching the structures (hazard).
*   **Feature Verification**: Detect if the house matches HCAD's record (e.g., If HCAD says "Brick" but we see "Siding," that's a value adjustment).

## Phase 3: Evidence & Form Integration (Afternoon)
*   **Annotated Evidence**: Update the `PDFService` to include the images with "Red Boxes" around detected issues.
*   **Condition Deductions**: Map Gemini's findings (e.g., "Extensive Roof Damage") to a specific $ deduction based on local repair estimates.
*   **Form 41.44 Auto-Fill**: Automatically check the "Property Condition" box on the protest form if issues are found.

## Tomorrow's Workflow
1.  **09:00**: Update `VisionAgent` to fetch 3 angles.
2.  **11:00**: Integrate `google-generativeai` Vision for defect description.
3.  **14:00**: Connect Vision deductions to the final savings calculator.
4.  **16:00**: Update PDF report to show "Physical Evidence Gallery."
