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

    # Use synchronous DB engine — avoids asyncio.new_event_loop() in Celery workers
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    import json, os

    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine   = create_engine(sync_url, pool_pre_ping=True)
    Session  = sessionmaker(bind=engine)
    session  = Session()

    try:
        rows = session.execute(
            text("""
                SELECT s.scan_id, s.text, s.url, s.risk,
                       f.corrected_label
                FROM scans s
                JOIN feedback f ON f.scan_id = s.scan_id
                WHERE f.corrected_label IS NOT NULL
                ORDER BY s.created_at DESC
                LIMIT 5000
            """)
        ).fetchall()

        if len(rows) < 100:
            logger.warning("Insufficient training data", count=len(rows))
            return {"status": "insufficient_data", "count": len(rows)}

        training_data = [
            {
                "text":  row.text or "",
                "url":   row.url or "",
                "label": row.corrected_label,
            }
            for row in rows
        ]

        # Export for external ML pipeline
        export_path = os.path.join("data", "training_data.json")
        os.makedirs("data", exist_ok=True)
        with open(export_path, "w") as f:
            json.dump(training_data, f, indent=2)

        # Update model metadata
        session.execute(
            text(
                "UPDATE model_metadata SET last_retrain_date = :now "
                "WHERE is_active = true"
            ),
            {"now": datetime.utcnow()},
        )
        session.commit()
        logger.info("Training data exported and metadata updated", count=len(training_data))

        # Also retrain the zero-day IsolationForest on the new data
        retrain_zero_day_model.delay()
        # Refit the isotonic calibrator on recent labels
        save_isotonic_calibrator.delay()

        return {
            "status":           "triggered",
            "training_samples": len(training_data),
            "export_path":      export_path,
            "timestamp":        datetime.utcnow().isoformat(),
        }
    except Exception as e:
        session.rollback()
        logger.error("Retraining trigger failed", error=str(e))
        return {"status": "failed", "error": str(e)}
    finally:
        session.close()


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
    A/B test two models by writing the routing config to Redis.
    The ML inference layer reads `ab_test:config` and splits traffic accordingly.
    """
    logger.info("Setting up A/B test", model_a=model_a, model_b=model_b, split=traffic_split)

    try:
        import redis as sync_redis, json
        r = sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
        config = {
            "model_a":       model_a,
            "model_b":       model_b,
            "traffic_split": traffic_split,
            "start_time":    datetime.utcnow().isoformat(),
            "active":        True,
        }
        r.set("ab_test:config", json.dumps(config))
        r.close()
        logger.info("A/B config written to Redis", config=config)
        return {"status": "configured", **config}
    except Exception as e:
        logger.error("A/B test setup failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="retrain_zero_day_model",
                 max_retries=2, autoretry_for=(Exception,))
def retrain_zero_day_model(self):
    """
    Retrain the IsolationForest zero-day anomaly detector on the latest
    scan text pulled directly from PostgreSQL.
    """
    logger.info("Retraining zero-day IsolationForest")

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import sys, os, pathlib

    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine   = create_engine(sync_url, pool_pre_ping=True)
    Session  = sessionmaker(bind=engine)
    session  = Session()

    texts = []
    try:
        rows = session.execute(
            text("SELECT text, url FROM scans WHERE text IS NOT NULL LIMIT 20000")
        ).fetchall()
        texts = [f"{row.text or ''} {row.url or ''}".strip() for row in rows]
        logger.info("Loaded scan texts for zero-day training", count=len(texts))
    except Exception as e:
        logger.warning("Could not load scan texts", error=str(e))
    finally:
        session.close()

    # Add zero-day detector to path
    project_root = pathlib.Path(__file__).resolve().parent.parent.parent
    ml_path      = str(project_root / "intelligence" / "nlp")
    if ml_path not in sys.path:
        sys.path.insert(0, ml_path)

    try:
        import zero_day_detector as zdd
        zdd.train(texts=texts if texts else None, save=True)
        logger.info("Zero-day model retrained and saved")
        return {"status": "success", "samples": len(texts)}
    except Exception as e:
        logger.error("Zero-day retraining failed", error=str(e))
        return {"status": "failed", "error": str(e)}


@celery_app.task(bind=True, name="save_isotonic_calibrator",
                 max_retries=2, autoretry_for=(Exception,))
def save_isotonic_calibrator(self):
    """
    Fit and persist an IsotonicRegression calibrator on scans that have
    ground-truth feedback labels, so the scoring engine uses a
    well-calibrated output probability.
    """
    logger.info("Fitting isotonic calibrator")

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    import sys, os, pathlib

    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine   = create_engine(sync_url, pool_pre_ping=True)
    Session  = sessionmaker(bind=engine)
    session  = Session()

    raw_scores = []
    true_labels = []

    try:
        rows = session.execute(
            text("""
                SELECT s.confidence, f.corrected_label
                FROM scans s
                JOIN feedback f ON f.scan_id = s.scan_id
                WHERE f.corrected_label IS NOT NULL
                LIMIT 10000
            """)
        ).fetchall()

        for row in rows:
            raw_scores.append(float(row.confidence))
            true_labels.append(1.0 if row.corrected_label == "HIGH" else 0.0)

        logger.info("Calibration samples loaded", count=len(raw_scores))
    except Exception as e:
        logger.warning("Could not load calibration data", error=str(e))
    finally:
        session.close()

    if len(raw_scores) < 20:
        logger.warning("Insufficient calibration data", count=len(raw_scores))
        return {"status": "insufficient_data", "count": len(raw_scores)}

    try:
        from sklearn.isotonic import IsotonicRegression
        import joblib, numpy as np

        cal = IsotonicRegression(out_of_bounds="clip")
        cal.fit(raw_scores, true_labels)

        project_root = pathlib.Path(__file__).resolve().parent.parent.parent
        cal_path     = project_root / "intelligence" / "nlp" / "isotonic_calibrator.joblib"
        joblib.dump(cal, str(cal_path))

        logger.info("Isotonic calibrator saved", path=str(cal_path), samples=len(raw_scores))
        return {"status": "success", "samples": len(raw_scores), "path": str(cal_path)}
    except Exception as e:
        logger.error("Calibrator fitting failed", error=str(e))
        return {"status": "failed", "error": str(e)}
