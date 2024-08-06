import json
import logging
import os

from logging import config as logging_config
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # noqa E501
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


class Log:
    def __init__(self, verbose):
        self.verbose = verbose

    def setup(self):

        with open("logging_config.json", "r") as logging_config_file:
            config_dict = json.load(logging_config_file)

        if self.verbose:
            config_dict["handlers"]["console"]["level"] = "DEBUG"

        logging_config.dictConfig(config_dict)
        self._setup_otlp()
        logging.debug('Log Setup Done')

    def _setup_otlp(self):
        resource_labels = {
            'service.name': 'my_service',
            'service.instance.id': os.uname().nodename,
        }

        if os.getenv("CI"):
            logging.debug('CI Environment Detected')
            resource_labels['github_action'] = os.getenv('GITHUB_ACTION')
            resource_labels['github_branch'] = os.getenv('GITHUB_REF_NAME')
            resource_labels['github_job'] = os.getenv('GITHUB_JOB')
        else:
            logging.debug('Non-CI Environment Detected')

        # Create and set the logger provider
        LoggingInstrumentor().instrument(set_logging_format=True)
        logger_provider = LoggerProvider(
            resource=Resource.create(
                resource_labels
            ),
        )
        set_logger_provider(logger_provider)

        # Create the OTLP log exporter that sends logs to configured
        # destination

        otlp_exporter = OTLPLogExporter(
            endpoint=os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')
        )
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(
                otlp_exporter
            )
        )

        # Attach OTLP handler to root logger

        handler = LoggingHandler(
            level=logging.INFO,
            logger_provider=logger_provider
        )
        logging.getLogger().addHandler(handler)
        logging.debug('OTLP Setup Done')
