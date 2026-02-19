from pydantic import BaseModel
from typing import Optional, List
from datetime import date

class SalesComparable(BaseModel):
    address: str
    sale_price: float
    sale_date: Optional[str] = None
    sqft: int
    price_per_sqft: float
    year_built: Optional[int] = None
    source: str = "RentCast"
    dist_from_subject: Optional[float] = None
    similarity_score: Optional[float] = None
