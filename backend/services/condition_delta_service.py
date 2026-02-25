"""
Condition Delta Service
Compares subject property condition against equity comps using
the Vision Agent's quick_condition_summary() method.

Produces a numeric delta: negative = subject in worse shape than comps,
which supports a §23.01 depreciation argument.

Uses ThreadPoolExecutor for TRUE parallel execution that works in
both FastAPI and Streamlit event loops.
"""

import logging
import re
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Text-to-score mapping for quick_condition_summary output
CONDITION_SCORES = {
    "excellent": 10,
    "very good": 8,
    "good": 7,
    "above average": 7,
    "average": 6,
    "fair": 5,
    "below average": 4,
    "poor": 3,
    "very poor": 2,
    "condemned": 1,
}


def score_condition_text(summary: str) -> Optional[int]:
    """
    Parse a condition rating from quick_condition_summary text.
    Looks for keywords like 'Good condition', 'Fair', 'Poor', etc.
    Returns numeric score (1-10) or None if unparseable.
    """
    if not summary:
        return None
    lower = summary.lower()

    # Try exact phrase matches first (longest match wins)
    for phrase, score in sorted(CONDITION_SCORES.items(), key=lambda x: -len(x[0])):
        if phrase in lower:
            return score

    # Fallback: look for "condition: X" or "rated X" patterns
    m = re.search(r'(?:condition|rated|rating)[:\s]+(\w+)', lower)
    if m:
        word = m.group(1)
        for phrase, score in CONDITION_SCORES.items():
            if word in phrase or phrase in word:
                return score

    # Last resort: look for numeric score
    m = re.search(r'(\d+)\s*/\s*10', lower)
    if m:
        return min(10, max(1, int(m.group(1))))

    return None


def compute_delta(subject_score: int, comp_scores: List[int]) -> Dict:
    """
    Compute condition delta between subject and comps.
    Returns delta, avg comp score, and suggested depreciation adjustment %.
    """
    if not comp_scores:
        return {"condition_delta": 0, "avg_comp_condition_score": 0, "depreciation_adjustment_pct": 0}

    avg_comp = sum(comp_scores) / len(comp_scores)
    delta = subject_score - avg_comp  # Negative = subject worse

    # Depreciation adjustment: each point of delta ≈ 1.5% reduction
    # Capped at 15% max adjustment, only applies when subject is worse
    depreciation_pct = 0
    if delta < 0:
        depreciation_pct = min(15.0, abs(delta) * 1.5)

    return {
        "subject_condition_score": subject_score,
        "avg_comp_condition_score": round(avg_comp, 1),
        "condition_delta": round(delta, 1),
        "depreciation_adjustment_pct": round(depreciation_pct, 1),
    }


def _score_comp_sync(comp: Dict, vision_agent) -> Optional[Dict]:
    """
    Synchronous worker that scores a single comp.
    Runs in a ThreadPoolExecutor thread — no asyncio needed.
    """
    addr = comp.get('address', '')
    if not addr:
        return None
    try:
        # get_comp_street_view checks local cache first, then fetches via requests.get
        slug = addr.replace(' ', '_').replace(',', '').replace('.', '')[:60]
        cached_path = f"data/comp_{slug}_front.jpg"

        if os.path.exists(cached_path) and os.path.getsize(cached_path) > 5000:
            img = cached_path
            logger.info(f"Comp Street View cache hit: {img}")
        else:
            # Fetch synchronously (we're already in a thread)
            import requests
            os.makedirs("data", exist_ok=True)
            params = {
                "size": "1024x768",
                "location": addr,
                "key": vision_agent.google_api_key,
                "fov": 80, "pitch": 0, "source": "outdoor"
            }
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/streetview",
                params=params, timeout=15
            )
            if resp.status_code != 200 or len(resp.content) < 5000:
                logger.warning(f"ConditionDelta: Street View failed for {addr}")
                return None
            img = cached_path
            with open(img, 'wb') as f:
                f.write(resp.content)

        # Run quick condition via OpenAI (synchronous call — fine in thread)
        import base64
        if not vision_agent.openai_client:
            return None

        with open(img, "rb") as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')

        prompt = (
            "You are a property appraiser. Look at this Street View image and provide a "
            "brief 1-2 sentence condition assessment. Focus on: roof condition, paint/siding, "
            "driveway, landscaping, and overall maintenance level. Be specific about what you see. "
            "Rate overall condition as: Excellent, Good, Fair, or Poor. "
            "Return ONLY the text summary, no JSON or formatting."
        )

        response = vision_agent.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                ]
            }],
            max_tokens=150,
            timeout=30
        )
        summary = response.choices[0].message.content.strip() if response.choices[0].message.content else ""
        score = score_condition_text(summary)

        return {
            "account_number": comp.get('account_number', ''),
            "address": addr,
            "score": score,
            "summary": summary,
            "image_path": img,
        }
    except Exception as e:
        logger.warning(f"ConditionDelta: Scoring failed for {addr}: {e}")
        return None


async def enrich_comps_with_condition(
    subject_data: Dict,
    equity_5: List[Dict],
    vision_agent,
    subject_image_path: str = None,
) -> Dict:
    """
    Orchestrates condition delta scoring:
    1. Extract subject condition_score from existing vision analysis
    2. Fetch comp Street View images
    3. Run quick_condition_summary on each comp (TRUE PARALLEL via ThreadPoolExecutor)
    4. Compute delta

    Returns enrichment dict to merge into equity_results.
    """

    # 1. Get subject condition score
    subject_score = None

    # Try from existing vision detections (already computed)
    vision_dets = subject_data.get('vision_detections', [])
    for det in vision_dets:
        if det.get('issue') == 'CONDITION_SUMMARY':
            subject_score = det.get('condition_score')
            break

    # If no existing score, try quick analysis on subject image
    if subject_score is None and subject_image_path:
        try:
            summary = await vision_agent.quick_condition_summary(subject_image_path)
            subject_score = score_condition_text(summary)
            logger.info(f"ConditionDelta: Subject quick-scored as {subject_score} from summary")
        except Exception as e:
            logger.warning(f"ConditionDelta: Subject quick-score failed: {e}")

    if subject_score is None:
        subject_score = 6  # Default to "Average" if we can't determine
        logger.info("ConditionDelta: Using default subject score of 6 (Average)")

    # 2. Score comps using ThreadPoolExecutor for TRUE parallelism
    #    This bypasses asyncio entirely — works in both FastAPI and Streamlit
    comp_conditions = []
    comp_scores = []
    comps_to_score = equity_5[:5]

    logger.info(f"ConditionDelta: Scoring {len(comps_to_score)} comps in parallel via ThreadPoolExecutor...")

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(_score_comp_sync, comp, vision_agent): i
            for i, comp in enumerate(comps_to_score)
        }
        # Wait for all futures with a 45-second timeout
        results = {}
        for future in as_completed(futures, timeout=45):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                logger.warning(f"ConditionDelta: Comp {idx} thread failed: {e}")
                results[idx] = None

    # Process results in order
    for i in range(len(comps_to_score)):
        result = results.get(i)
        if result and result.get('score') is not None:
            comp_conditions.append(result)
            comp_scores.append(result['score'])
            # Attach score to the comp dict for PDF rendering
            equity_5[i]['condition_score'] = result['score']
            equity_5[i]['condition_summary'] = result.get('summary', '')

    logger.info(f"ConditionDelta: Successfully scored {len(comp_conditions)}/{len(comps_to_score)} comps")

    # 3. Compute delta
    delta_result = compute_delta(subject_score, comp_scores)
    delta_result["comp_conditions"] = comp_conditions

    logger.info(
        f"ConditionDelta: Subject={subject_score}, "
        f"AvgComp={delta_result['avg_comp_condition_score']}, "
        f"Delta={delta_result['condition_delta']}, "
        f"DepreciationAdj={delta_result['depreciation_adjustment_pct']}%"
    )

    return delta_result
