"""
Condition Delta Service
Compares subject property condition against equity comps using
the Vision Agent's quick_condition_summary() method.

Produces a numeric delta: negative = subject in worse shape than comps,
which supports a §23.01 depreciation argument.
"""

import logging
import re
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
    3. Run quick_condition_summary on each comp
    4. Compute delta

    Returns enrichment dict to merge into equity_results.
    """
    import asyncio

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

    # 2. Score comps (fetch images + quick analysis)
    comp_conditions = []
    comp_scores = []

    async def _score_comp(comp):
        addr = comp.get('address', '')
        if not addr:
            return None
        try:
            img = await vision_agent.get_comp_street_view(addr)
            if not img:
                return None
            summary = await vision_agent.quick_condition_summary(img)
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

    # Run comp scoring — limit to 5 comps, sequential to avoid rate limits
    for comp in equity_5[:5]:
        result = await _score_comp(comp)
        if result and result.get('score') is not None:
            comp_conditions.append(result)
            comp_scores.append(result['score'])
            # Attach score to the comp dict for PDF rendering
            comp['condition_score'] = result['score']
            comp['condition_summary'] = result.get('summary', '')

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
