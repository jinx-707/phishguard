"""
Fusion Intelligence Engine - Combines multiple detection sources
Person 1: AI Intelligence Engineer
"""
from typing import Dict, Any, List, Optional
import numpy as np


class FusionEngine:
    """Advanced fusion of multiple threat detection sources"""
    
    def __init__(self):
        # Configurable weights for each detection source
        self.weights = {
            'nlp': 0.25,        # NLP text analysis
            'url': 0.20,        # URL pattern analysis
            'dom': 0.20,        # DOM structure analysis
            'graph': 0.15,      # Graph intelligence
            'anomaly': 0.10,    # Zero-day anomaly detection
            'brand': 0.10       # Brand impersonation
        }
        
        # Confidence thresholds
        self.thresholds = {
            'high': 0.7,
            'medium': 0.4,
            'low': 0.2
        }
    
    def fuse(self, 
             nlp_score: float = 0.0,
             url_score: float = 0.0,
             dom_score: float = 0.0,
             graph_score: float = 0.0,
             anomaly_score: float = 0.0,
             brand_score: float = 0.0,
             reasons: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Fuse multiple detection scores into final verdict
        
        Args:
            nlp_score: NLP analysis score (0-1)
            url_score: URL analysis score (0-1)
            dom_score: DOM analysis score (0-1)
            graph_score: Graph intelligence score (0-1)
            anomaly_score: Anomaly detection score (0-1)
            brand_score: Brand impersonation score (0-1)
            reasons: List of detection reasons
        
        Returns:
            Fused result with risk level and confidence
        """
        # Collect all scores
        scores = {
            'nlp': nlp_score,
            'url': url_score,
            'dom': dom_score,
            'graph': graph_score,
            'anomaly': anomaly_score,
            'brand': brand_score
        }
        
        # Weighted fusion
        weighted_score = sum(scores[k] * self.weights[k] for k in scores)
        
        # Ensemble voting (majority vote)
        votes = {
            'high': sum(1 for s in scores.values() if s >= self.thresholds['high']),
            'medium': sum(1 for s in scores.values() if self.thresholds['medium'] <= s < self.thresholds['high']),
            'low': sum(1 for s in scores.values() if s < self.thresholds['medium'])
        }
        
        # Determine risk level
        if weighted_score >= self.thresholds['high'] or votes['high'] >= 2:
            risk_level = 'HIGH'
            confidence = min(weighted_score + 0.1, 1.0)
        elif weighted_score >= self.thresholds['medium'] or votes['medium'] >= 2:
            risk_level = 'MEDIUM'
            confidence = weighted_score
        else:
            risk_level = 'LOW'
            confidence = 1.0 - weighted_score
        
        # Aggregate reasons
        all_reasons = reasons or []
        
        # Add score-based reasons
        if nlp_score > 0.5:
            all_reasons.append(f"NLP analysis: {nlp_score:.2f}")
        if url_score > 0.5:
            all_reasons.append(f"URL suspicious: {url_score:.2f}")
        if dom_score > 0.5:
            all_reasons.append(f"DOM structure suspicious: {dom_score:.2f}")
        if graph_score > 0.3:
            all_reasons.append(f"Graph intelligence: {graph_score:.2f}")
        if anomaly_score > 0.5:
            all_reasons.append(f"Anomalous behavior detected")
        if brand_score > 0.5:
            all_reasons.append(f"Brand impersonation detected")
        
        return {
            'risk': risk_level,
            'confidence': round(confidence, 3),
            'weighted_score': round(weighted_score, 3),
            'individual_scores': {k: round(v, 3) for k, v in scores.items()},
            'votes': votes,
            'reasons': all_reasons[:5],
            'method': 'fusion_ensemble'
        }
    
    def update_weights(self, feedback: Dict[str, Any]):
        """Update weights based on feedback (online learning)"""
        # Simple weight adjustment based on feedback
        # In production, use more sophisticated methods
        if 'correct_source' in feedback:
            source = feedback['correct_source']
            if source in self.weights:
                # Increase weight of correct source
                self.weights[source] = min(self.weights[source] * 1.1, 0.5)
                # Normalize weights
                total = sum(self.weights.values())
                self.weights = {k: v/total for k, v in self.weights.items()}
    
    def explain_decision(self, fusion_result: Dict[str, Any]) -> str:
        """Generate human-readable explanation"""
        risk = fusion_result['risk']
        confidence = fusion_result['confidence']
        scores = fusion_result['individual_scores']
        
        explanation = f"Risk Level: {risk} (Confidence: {confidence:.1%})\n\n"
        explanation += "Detection Sources:\n"
        
        for source, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if score > 0.1:
                explanation += f"  • {source.upper()}: {score:.1%}\n"
        
        explanation += f"\nReasons:\n"
        for reason in fusion_result.get('reasons', []):
            explanation += f"  • {reason}\n"
        
        return explanation


class AdaptiveFusion(FusionEngine):
    """Adaptive fusion with dynamic weight adjustment"""
    
    def __init__(self):
        super().__init__()
        self.performance_history = {k: [] for k in self.weights.keys()}
    
    def record_performance(self, source: str, was_correct: bool):
        """Record performance of each source"""
        if source in self.performance_history:
            self.performance_history[source].append(1.0 if was_correct else 0.0)
            # Keep only last 100 records
            self.performance_history[source] = self.performance_history[source][-100:]
    
    def adapt_weights(self):
        """Adapt weights based on historical performance"""
        for source in self.weights.keys():
            history = self.performance_history[source]
            if len(history) >= 10:
                accuracy = np.mean(history)
                # Adjust weight based on accuracy
                self.weights[source] = accuracy * 0.3  # Scale to reasonable range
        
        # Normalize
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v/total for k, v in self.weights.items()}


if __name__ == "__main__":
    engine = FusionEngine()
    
    # Test case
    result = engine.fuse(
        nlp_score=0.8,
        url_score=0.6,
        dom_score=0.7,
        graph_score=0.3,
        anomaly_score=0.5,
        brand_score=0.4,
        reasons=["Urgency language", "Suspicious domain"]
    )
    
    print(engine.explain_decision(result))
