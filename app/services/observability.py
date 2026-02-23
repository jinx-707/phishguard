"""
Observability service with OpenTelemetry integration.
"""
from typing import Optional, Dict, Any
import structlog
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

from app.config import settings

logger = structlog.get_logger(__name__)

# Prometheus metrics
SCAN_REQUESTS = Counter(
    'scan_requests_total',
    'Total number of scan requests',
    ['risk_level']
)

SCAN_DURATION = Histogram(
    'scan_duration_seconds',
    'Scan request duration in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

CACHE_HITS = Counter(
    'cache_hits_total',
    'Total number of cache hits'
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total number of cache misses'
)

GRAPH_QUERIES = Counter(
    'graph_queries_total',
    'Total number of graph queries'
)

MODEL_PREDICTIONS = Counter(
    'model_predictions_total',
    'Total number of model predictions',
    ['model_name']
)

ACTIVE_CONNECTIONS = Gauge(
    'active_connections',
    'Number of active connections'
)

ERROR_COUNT = Counter(
    'errors_total',
    'Total number of errors',
    ['error_type']
)


class ObservabilityService:
    """Observability service for metrics and tracing."""
    
    def __init__(self):
        self.tracer_provider: Optional[TracerProvider] = None
        self.meter_provider: Optional[MeterProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self.meter: Optional[metrics.Meter] = None
    
    def init_tracing(self):
        """Initialize OpenTelemetry tracing."""
        try:
            # Create resource
            resource = Resource.create({
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": settings.APP_VERSION,
            })
            
            # Create tracer provider
            self.tracer_provider = TracerProvider(resource=resource)
            
            # Create OTLP exporter
            otlp_exporter = OTLPSpanExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=True,
            )
            
            # Add span processor
            span_processor = BatchSpanProcessor(otlp_exporter)
            self.tracer_provider.add_span_processor(span_processor)
            
            # Set global tracer provider
            trace.set_tracer_provider(self.tracer_provider)
            
            # Get tracer
            self.tracer = trace.get_tracer(__name__)
            
            logger.info("OpenTelemetry tracing initialized")
        except Exception as e:
            logger.warning("Failed to initialize tracing", error=str(e))
    
    def init_metrics(self):
        """Initialize OpenTelemetry metrics."""
        try:
            # Create resource
            resource = Resource.create({
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": settings.APP_VERSION,
            })
            
            # Create metric exporter
            otlp_exporter = OTLPMetricExporter(
                endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
                insecure=True,
            )
            
            # Create metric reader
            metric_reader = PeriodicExportingMetricReader(
                otlp_exporter,
                export_interval_millis=60000,  # 1 minute
            )
            
            # Create meter provider
            self.meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader],
            )
            
            # Set global meter provider
            metrics.set_meter_provider(self.meter_provider)
            
            # Get meter
            self.meter = metrics.get_meter(__name__)
            
            logger.info("OpenTelemetry metrics initialized")
        except Exception as e:
            logger.warning("Failed to initialize metrics", error=str(e))
    
    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumented")
        except Exception as e:
            logger.warning("Failed to instrument FastAPI", error=str(e))
    
    def record_scan(self, risk_level: str, duration: float):
        """Record scan metrics."""
        SCAN_REQUESTS.labels(risk_level=risk_level).inc()
        SCAN_DURATION.observe(duration)
    
    def record_cache_hit(self):
        """Record cache hit."""
        CACHE_HITS.inc()
    
    def record_cache_miss(self):
        """Record cache miss."""
        CACHE_MISSES.inc()
    
    def record_graph_query(self):
        """Record graph query."""
        GRAPH_QUERIES.inc()
    
    def record_model_prediction(self, model_name: str):
        """Record model prediction."""
        MODEL_PREDICTIONS.labels(model_name=model_name).inc()
    
    def record_error(self, error_type: str):
        """Record error."""
        ERROR_COUNT.labels(error_type=error_type).inc()
    
    def set_active_connections(self, count: int):
        """Set active connections gauge."""
        ACTIVE_CONNECTIONS.set(count)
    
    def get_prometheus_metrics(self) -> bytes:
        """Get Prometheus metrics."""
        return generate_latest()


# Global observability service
observability = ObservabilityService()


def init_observability(app=None):
    """Initialize observability."""
    observability.init_tracing()
    observability.init_metrics()
    
    if app:
        observability.instrument_fastapi(app)
    
    logger.info("Observability initialized")


class MetricsCollector:
    """Collect and aggregate metrics."""
    
    @staticmethod
    async def collect_system_metrics() -> Dict[str, Any]:
        """Collect system-wide metrics."""
        try:
            from app.services.database import get_db_session
            from app.models.db import Scan, Domain
            from sqlalchemy import select, func
            from datetime import datetime, timedelta
            
            metrics = {}
            
            async for session in get_db_session():
                # Total scans
                scan_count = await session.execute(
                    select(func.count(Scan.id))
                )
                metrics['total_scans'] = scan_count.scalar()
                
                # Scans in last 24 hours
                yesterday = datetime.utcnow() - timedelta(days=1)
                recent_scans = await session.execute(
                    select(func.count(Scan.id)).where(Scan.created_at >= yesterday)
                )
                metrics['scans_24h'] = recent_scans.scalar()
                
                # Risk distribution
                high_risk = await session.execute(
                    select(func.count(Scan.id)).where(Scan.risk == 'HIGH')
                )
                metrics['high_risk_count'] = high_risk.scalar()
                
                # Total domains
                domain_count = await session.execute(
                    select(func.count(Domain.id))
                )
                metrics['total_domains'] = domain_count.scalar()
                
                # Malicious domains
                malicious_count = await session.execute(
                    select(func.count(Domain.id)).where(Domain.is_malicious == True)
                )
                metrics['malicious_domains'] = malicious_count.scalar()
                
                break
            
            return metrics
        except Exception as e:
            logger.error("Failed to collect metrics", error=str(e))
            return {}
    
    @staticmethod
    async def collect_performance_metrics() -> Dict[str, Any]:
        """Collect performance metrics."""
        metrics = {
            'cache_hit_rate': 0.0,
            'average_scan_duration': 0.0,
            'error_rate': 0.0,
        }
        
        try:
            # Calculate cache hit rate
            total_cache = CACHE_HITS._value.get() + CACHE_MISSES._value.get()
            if total_cache > 0:
                metrics['cache_hit_rate'] = CACHE_HITS._value.get() / total_cache
            
            # Get average scan duration
            if SCAN_DURATION._sum._value.get() > 0:
                metrics['average_scan_duration'] = (
                    SCAN_DURATION._sum._value.get() / SCAN_DURATION._count._value.get()
                )
            
            # Calculate error rate
            total_requests = sum(
                SCAN_REQUESTS.labels(risk_level=level)._value.get()
                for level in ['LOW', 'MEDIUM', 'HIGH']
            )
            if total_requests > 0:
                metrics['error_rate'] = ERROR_COUNT._value.get() / total_requests
        except Exception as e:
            logger.error("Failed to collect performance metrics", error=str(e))
        
        return metrics


def trace_function(func):
    """Decorator to trace function execution."""
    def wrapper(*args, **kwargs):
        if observability.tracer:
            with observability.tracer.start_as_current_span(func.__name__):
                return func(*args, **kwargs)
        return func(*args, **kwargs)
    return wrapper


async def trace_async_function(func):
    """Decorator to trace async function execution."""
    async def wrapper(*args, **kwargs):
        if observability.tracer:
            with observability.tracer.start_as_current_span(func.__name__):
                return await func(*args, **kwargs)
        return await func(*args, **kwargs)
    return wrapper
