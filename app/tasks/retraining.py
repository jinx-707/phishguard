"""
Continuous learning and model retraining tasks.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import structlog
from scipy import stats
import numpy as np

from app.tasks.celery_app import celery_app
from app.config import settings

logger = structlog.get_logger(__name__)


@celery_app.task(bind=True, name="monitor_drift")
def monitor_drift(self, window_days: int = 7):
    """
    Monitor model drift using statistical tests.
    
    Args:
        window_days: Number of days to analyze
    
    Returns:
        Drift analysis results
    """
    logger.info("Starting drift monitoring", window_days=window_days)
    
    async def analyze_drift():
        try:
            from app.services.database import get_db_session
            from app.models.db import Scan
            from sqlalchemy import select, and_
            
            cutoff_date = datetime.utcnow() - timedelta(days=window_days)
            old_cutoff = cutoff_date - timedelta(days=window_days)
            
            async for session in get_db_session():
                # Get recent predictions
                recent_stmt = select(Scan).where(
                    Scan.created_at >= cutoff_date
                )
                recent_result = await session.execute(recent_stmt)
                recent_scans = recent_result.scalars().all()
                
                # Get older predictions
                old_stmt = select(Scan).where(
                    and_(
                        Scan.created_at >= old_cutoff,
                        Scan.created_at < cutoff_date
                    )
                )
                old_result = await session.execute(old_stmt)
                old_scans = old_result.scalars().all()
                
                if len(recent_scans) < 30 or len(old_scans) < 30:
                    logger.warning("Insufficient data for drift analysis")
                    return {
                        'status': 'insufficient_data',
                        'recent_count': len(recent_scans),
                        'old_count': len(old_scans),
                    }
                
                # Extract scores
                recent_scores = [s.model_score for s in recent_scans]
                old_scores = [s.model_score for s in old_scans]
                
                # Kolmogorov-Smirnov test
                ks_stat, p_value = stats.ks_2samp(old_scores, recent_scores)
                
                # Determine if drift detected
                drift_detected = p_value < 0.05
                
                result = {
                    'status': 'completed',
                    'drift_detected': drift_detected,
                    'ks_statistic': float(ks_stat),
                    'p_value': float(p_value),
                    'recent_mean': float(np.mean(recent_scores)),
                    'old_mean': float(np.mean(old_scores)),
                    'recent_count': len(recent_scans),
                    'old_count': len(old_scans),
                    'timestamp': datetime.utcnow().isoformat(),
                }
                
                logger.info("Drift analysis completed", **result)
                
                # Trigger retraining if drift detected
                if drift_detected:
                    logger.warning("Model drift detected, triggering retraining")
                    trigger_retraining.delay()
                
                return result
        except Exception as e:
            logger.error("Drift monitoring failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(analyze_drift())
    loop.close()
    
    return result


@celery_app.task(bind=True, name="trigger_retraining")
def trigger_retraining(self):
    """
    Trigger model retraining process.
    
    This task prepares data and initiates the retraining pipeline.
    """
    logger.info("Starting retraining trigger")
    
    async def prepare_retraining():
        try:
            from app.services.database import get_db_session
            from app.models.db import Scan, Feedback, ModelMetadata
            from sqlalchemy import select
            
            async for session in get_db_session():
                # Get all scans with feedback
                stmt = select(Scan).join(Feedback).where(
                    Feedback.corrected_label.isnot(None)
                )
                result = await session.execute(stmt)
                training_scans = result.scalars().all()
                
                if len(training_scans) < 100:
                    logger.warning("Insufficient training data", count=len(training_scans))
                    return {
                        'status': 'insufficient_data',
                        'count': len(training_scans),
                    }
                
                # Export training data
                training_data = []
                for scan in training_scans:
                    training_data.append({
                        'text': scan.text or '',
                        'url': scan.url or '',
                        'label': scan.feedback.corrected_label if scan.feedback else scan.risk.value,
                        'timestamp': scan.created_at.isoformat(),
                    })
                
                # Save training data (would export to file or ML service)
                logger.info("Training data prepared", count=len(training_data))
                
                # Update model metadata
                model_stmt = select(ModelMetadata).where(
                    ModelMetadata.is_active == True
                )
                model_result = await session.execute(model_stmt)
                model = model_result.scalar_one_or_none()
                
                if model:
                    model.last_retrain_date = datetime.utcnow()
                    await session.commit()
                
                return {
                    'status': 'triggered',
                    'training_samples': len(training_data),
                    'timestamp': datetime.utcnow().isoformat(),
                }
        except Exception as e:
            logger.error("Retraining trigger failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(prepare_retraining())
    loop.close()
    
    return result


@celery_app.task(bind=True, name="export_training_data")
def export_training_data(self, output_path: str = "training_data.json"):
    """
    Export training data for model retraining.
    
    Args:
        output_path: Path to save training data
    
    Returns:
        Export statistics
    """
    logger.info("Exporting training data", output_path=output_path)
    
    async def export_data():
        try:
            from app.services.database import get_db_session
            from app.models.db import Scan, Feedback
            from sqlalchemy import select
            import json
            
            async for session in get_db_session():
                # Get all scans
                stmt = select(Scan).limit(10000)  # Limit for performance
                result = await session.execute(stmt)
                scans = result.scalars().all()
                
                # Prepare export data
                export_data = []
                for scan in scans:
                    item = {
                        'scan_id': scan.scan_id,
                        'text': scan.text,
                        'url': scan.url,
                        'html': scan.html,
                        'risk': scan.risk.value,
                        'confidence': scan.confidence,
                        'model_score': scan.model_score,
                        'graph_score': scan.graph_score,
                        'timestamp': scan.created_at.isoformat(),
                    }
                    
                    # Add feedback if available
                    if scan.feedback:
                        item['feedback'] = {
                            'user_flag': scan.feedback.user_flag,
                            'corrected_label': scan.feedback.corrected_label,
                        }
                    
                    export_data.append(item)
                
                # Save to file
                with open(output_path, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                logger.info("Training data exported", count=len(export_data), path=output_path)
                
                return {
                    'status': 'success',
                    'count': len(export_data),
                    'output_path': output_path,
                }
        except Exception as e:
            logger.error("Export failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(export_data())
    loop.close()
    
    return result


@celery_app.task(bind=True, name="calculate_model_metrics")
def calculate_model_metrics(self, days: int = 30):
    """
    Calculate model performance metrics.
    
    Args:
        days: Number of days to analyze
    
    Returns:
        Performance metrics
    """
    logger.info("Calculating model metrics", days=days)
    
    async def calculate_metrics():
        try:
            from app.services.database import get_db_session
            from app.models.db import Scan, Feedback
            from sqlalchemy import select, and_
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async for session in get_db_session():
                # Get scans with feedback
                stmt = select(Scan).join(Feedback).where(
                    and_(
                        Scan.created_at >= cutoff_date,
                        Feedback.corrected_label.isnot(None)
                    )
                )
                result = await session.execute(stmt)
                scans = result.scalars().all()
                
                if len(scans) < 10:
                    logger.warning("Insufficient data for metrics", count=len(scans))
                    return {
                        'status': 'insufficient_data',
                        'count': len(scans),
                    }
                
                # Prepare labels
                y_true = []
                y_pred = []
                
                for scan in scans:
                    # True label from feedback
                    true_label = 1 if scan.feedback.corrected_label == 'HIGH' else 0
                    # Predicted label
                    pred_label = 1 if scan.risk.value == 'HIGH' else 0
                    
                    y_true.append(true_label)
                    y_pred.append(pred_label)
                
                # Calculate metrics
                accuracy = accuracy_score(y_true, y_pred)
                precision = precision_score(y_true, y_pred, zero_division=0)
                recall = recall_score(y_true, y_pred, zero_division=0)
                f1 = f1_score(y_true, y_pred, zero_division=0)
                
                metrics = {
                    'status': 'success',
                    'accuracy': float(accuracy),
                    'precision': float(precision),
                    'recall': float(recall),
                    'f1_score': float(f1),
                    'sample_count': len(scans),
                    'days': days,
                    'timestamp': datetime.utcnow().isoformat(),
                }
                
                logger.info("Model metrics calculated", **metrics)
                
                return metrics
        except Exception as e:
            logger.error("Metrics calculation failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e),
            }
    
    # Run async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(calculate_metrics())
    loop.close()
    
    return result


@celery_app.task(bind=True, name="ab_test_models")
def ab_test_models(self, model_a: str, model_b: str, traffic_split: float = 0.5):
    """
    A/B test two models.
    
    Args:
        model_a: Name of model A
        model_b: Name of model B
        traffic_split: Percentage of traffic for model A (0-1)
    
    Returns:
        A/B test configuration
    """
    logger.info("Setting up A/B test", model_a=model_a, model_b=model_b, split=traffic_split)
    
    # This would configure the system to route traffic between models
    # Store configuration in Redis or database
    
    return {
        'status': 'configured',
        'model_a': model_a,
        'model_b': model_b,
        'traffic_split': traffic_split,
        'start_time': datetime.utcnow().isoformat(),
    }
