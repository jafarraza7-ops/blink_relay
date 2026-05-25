from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def setup_insights() -> None:
    """Configure Azure Application Insights via opencensus-ext-azure.

    No-ops gracefully when APPINSIGHTS_CONNECTION_STRING is not set (local dev).
    """
    settings = get_settings()
    if not settings.APPINSIGHTS_CONNECTION_STRING:
        logger.info("Application Insights not configured — skipping telemetry setup")
        return

    try:
        from opencensus.ext.azure.log_exporter import AzureLogHandler
        from opencensus.ext.azure.trace_exporter import AzureExporter
        from opencensus.trace.samplers import ProbabilitySampler
        from opencensus.trace.tracer import Tracer

        # Attach Azure log handler to the root logger
        azure_handler = AzureLogHandler(
            connection_string=settings.APPINSIGHTS_CONNECTION_STRING
        )
        logging.getLogger().addHandler(azure_handler)

        # Initialise distributed tracer (100% sampling in non-prod, 10% in prod)
        sample_rate = 0.1 if settings.ENVIRONMENT == "production" else 1.0
        Tracer(
            exporter=AzureExporter(
                connection_string=settings.APPINSIGHTS_CONNECTION_STRING
            ),
            sampler=ProbabilitySampler(rate=sample_rate),
        )
        logger.info("Application Insights configured (env=%s)", settings.ENVIRONMENT)
    except ImportError:
        logger.warning("opencensus-ext-azure not installed — Application Insights disabled")
    except Exception:
        logger.exception("Failed to configure Application Insights")
