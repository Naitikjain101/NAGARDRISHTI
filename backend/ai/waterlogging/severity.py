"""
Urban Watch — Waterlogging Severity Logic
Assigns a severity label based on the persistence, confidence, and primarily the spatial area 
occupied by the water (water_area_ratio) relative to the screen or the region of interest.
"""

from ai.unified.schemas import SeverityLevel

class WaterloggingSeverityCalculator:
    """Calculates the severity of a waterlogging event."""
    
    def __init__(
        self,
        low_area_threshold: float = 0.05,
        medium_area_threshold: float = 0.15,
        high_area_threshold: float = 0.40,
        critical_area_threshold: float = 0.70,
    ) -> None:
        self.low_area = low_area_threshold
        self.medium_area = medium_area_threshold
        self.high_area = high_area_threshold
        self.critical_area = critical_area_threshold
        
    def calculate(self, max_area_ratio: float, stability_score: float, max_confidence: float) -> SeverityLevel:
        """
        Derive severity from max_area_ratio (fraction of box or screen covered by water),
        stability (how persistent the water is), and confidence.
        """
        
        # Penalize severity if stability is extremely low (meaning it was a fleeting blip)
        effective_area = max_area_ratio
        if stability_score < 0.3:
            effective_area *= 0.5
            
        if effective_area >= self.critical_area:
            return SeverityLevel.CRITICAL
        elif effective_area >= self.high_area:
            return SeverityLevel.HIGH
        elif effective_area >= self.medium_area:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW
