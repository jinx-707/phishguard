"""
Task scheduler using APScheduler for periodic jobs.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import structlog

from app.config import settings
from app.tasks.ingestion import ingest_feed, update_graph, recalculate_scores, cleanup_old_scans
from app.tasks.retraining import (
    monitor_drift,
    calculate_model_metrics,
    retrain_zero_day_model,
    save_isotonic_calibrator,
)

logger = structlog.get_logger(__name__)

# Global scheduler instance
scheduler = None


def init_scheduler():
    """Initialize and configure the task scheduler."""
    global scheduler
    
    scheduler = AsyncIOScheduler(timezone='UTC')
    
    # Threat feed ingestion - every hour
    scheduler.add_job(
        schedule_feed_ingestion,
        trigger=IntervalTrigger(hours=1),
        id='feed_ingestion',
        name='Threat Feed Ingestion',
        replace_existing=True,
    )
    
    # Graph update - every 6 hours
    scheduler.add_job(
        schedule_graph_update,
        trigger=IntervalTrigger(hours=6),
        id='graph_update',
        name='Graph Update',
        replace_existing=True,
    )
    
    # Score recalculation - daily at 2 AM
    scheduler.add_job(
        schedule_score_recalculation,
        trigger=CronTrigger(hour=2, minute=0),
        id='score_recalculation',
        name='Score Recalculation',
        replace_existing=True,
    )
    
    # Drift monitoring - daily at 3 AM
    scheduler.add_job(
        schedule_drift_monitoring,
        trigger=CronTrigger(hour=3, minute=0),
        id='drift_monitoring',
        name='Drift Monitoring',
        replace_existing=True,
    )
    
    # Model metrics - daily at 4 AM
    scheduler.add_job(
        schedule_model_metrics,
        trigger=CronTrigger(hour=4, minute=0),
        id='model_metrics',
        name='Model Metrics Calculation',
        replace_existing=True,
    )
    
    # Cleanup old scans - weekly on Sunday at 1 AM
    scheduler.add_job(
        schedule_cleanup,
        trigger=CronTrigger(day_of_week='sun', hour=1, minute=0),
        id='cleanup',
        name='Cleanup Old Scans',
        replace_existing=True,
    )

    # Zero-day IsolationForest retraining - weekly on Sunday at 5 AM
    scheduler.add_job(
        schedule_zero_day_retrain,
        trigger=CronTrigger(day_of_week='sun', hour=5, minute=0),
        id='zero_day_retrain',
        name='Zero-Day Model Retrain',
        replace_existing=True,
    )

    # Isotonic calibrator refit - weekly on Sunday at 5 AM 30 min
    scheduler.add_job(
        schedule_calibrator_save,
        trigger=CronTrigger(day_of_week='sun', hour=5, minute=30),
        id='calibrator_save',
        name='Isotonic Calibrator Save',
        replace_existing=True,
    )
    
    logger.info("Scheduler initialized with jobs", job_count=len(scheduler.get_jobs()))
    
    return scheduler


def start_scheduler():
    """Start the scheduler."""
    global scheduler
    
    if scheduler is None:
        init_scheduler()
    
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


def stop_scheduler():
    """Stop the scheduler."""
    global scheduler
    
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def get_scheduler():
    """Get the scheduler instance."""
    global scheduler
    
    if scheduler is None:
        init_scheduler()
    
    return scheduler


# Job functions

async def schedule_feed_ingestion():
    """Schedule threat feed ingestion."""
    logger.info("Triggering feed ingestion")
    
    # Get configured feeds from database
    feeds = await get_active_feeds()
    
    for feed in feeds:
        try:
            # Trigger Celery task
            ingest_feed.delay(feed['url'], feed['type'])
            logger.info("Feed ingestion scheduled", feed=feed['name'])
        except Exception as e:
            logger.error("Failed to schedule feed ingestion", feed=feed['name'], error=str(e))


async def schedule_graph_update():
    """Schedule graph update."""
    logger.info("Triggering graph update")
    
    try:
        update_graph.delay()
        logger.info("Graph update scheduled")
    except Exception as e:
        logger.error("Failed to schedule graph update", error=str(e))


async def schedule_score_recalculation():
    """Schedule score recalculation."""
    logger.info("Triggering score recalculation")
    
    try:
        recalculate_scores.delay()
        logger.info("Score recalculation scheduled")
    except Exception as e:
        logger.error("Failed to schedule score recalculation", error=str(e))


async def schedule_drift_monitoring():
    """Schedule drift monitoring."""
    logger.info("Triggering drift monitoring")
    
    try:
        monitor_drift.delay(window_days=7)
        logger.info("Drift monitoring scheduled")
    except Exception as e:
        logger.error("Failed to schedule drift monitoring", error=str(e))


async def schedule_model_metrics():
    """Schedule model metrics calculation."""
    logger.info("Triggering model metrics calculation")
    
    try:
        calculate_model_metrics.delay(days=30)
        logger.info("Model metrics calculation scheduled")
    except Exception as e:
        logger.error("Failed to schedule model metrics", error=str(e))


async def schedule_cleanup():
    """Schedule cleanup of old scans."""
    logger.info("Triggering cleanup")
    try:
        cleanup_old_scans.delay(days=90)
        logger.info("Cleanup scheduled")
    except Exception as e:
        logger.error("Failed to schedule cleanup", error=str(e))


async def schedule_zero_day_retrain():
    """Retrain IsolationForest zero-day model on latest scan corpus."""
    logger.info("Triggering zero-day model retrain")
    try:
        retrain_zero_day_model.delay()
        logger.info("Zero-day retrain scheduled")
    except Exception as e:
        logger.error("Failed to schedule zero-day retrain", error=str(e))


async def schedule_calibrator_save():
    """Refit and persist the isotonic calibrator from user-labelled data."""
    logger.info("Triggering calibrator refit")
    try:
        save_isotonic_calibrator.delay()
        logger.info("Calibrator refit scheduled")
    except Exception as e:
        logger.error("Failed to schedule calibrator save", error=str(e))


async def get_active_feeds():
    """Get active threat feeds from database."""
    try:
        from app.services.database import get_db_session
        from app.models.db import ThreatFeed
        from sqlalchemy import select
        
        async for session in get_db_session():
            stmt = select(ThreatFeed).where(ThreatFeed.is_active == True)
            result = await session.execute(stmt)
            feeds = result.scalars().all()
            
            return [
                {
                    'name': feed.feed_name,
                    'url': feed.feed_url,
                    'type': feed.feed_type,
                }
                for feed in feeds
            ]
    except Exception as e:
        logger.error("Failed to get active feeds", error=str(e))
        # Return default feeds
        return [
            {
                'name': 'OpenPhish',
                'url': 'https://openphish.com/feed.txt',
                'type': 'PHISHING',
            },
        ]


def list_scheduled_jobs():
    """List all scheduled jobs."""
    global scheduler
    
    if scheduler is None:
        return []
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger),
        })
    
    return jobs


def pause_job(job_id: str):
    """Pause a scheduled job."""
    global scheduler
    
    if scheduler:
        scheduler.pause_job(job_id)
        logger.info("Job paused", job_id=job_id)


def resume_job(job_id: str):
    """Resume a paused job."""
    global scheduler
    
    if scheduler:
        scheduler.resume_job(job_id)
        logger.info("Job resumed", job_id=job_id)


def trigger_job_now(job_id: str):
    """Trigger a job immediately."""
    global scheduler
    
    if scheduler:
        job = scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.utcnow())
            logger.info("Job triggered", job_id=job_id)
