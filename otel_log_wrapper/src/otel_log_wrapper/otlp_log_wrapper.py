import json
import logging
import os
import sys

from logging import config as logging_config
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # noqa E501
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


class LogConfiguration:
    def __init__(self, name, correlation_id, level='DEBUG'):
        self.level = level
        self.name = name
        self.correlation_id = correlation_id

        # transverse directories down (up to 4) to find a configuration file
        logging_config_filename = self._find_file('.','logging_config.json')

        # configure with those settings
        if logging_config_filename:
            with open(logging_config_filename, "r") as logging_config_file:
                config_dict = json.load(logging_config_file)
            config_dict["handlers"]["console"]["level"] = self.level
            logging_config.dictConfig(config_dict)
        else:
            print('Not found a logging_config.json file')

        # configure OTLP
        if not os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT'):
            logging.debug('OTEL_EXPORTER_OTLP_ENDPOINT not found.')
        else:
            self._setup_otlp()

        logging.debug('Log Setup Done')

    def _setup_otlp(self):

        resource_labels = {
            'service.name': self.name,
            'service.instance.id': os.uname().nodename,
            'service.correlation_id': self.correlation_id,
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
            level=self.level,
            logger_provider=logger_provider
        )

        logging.getLogger().addHandler(handler)
        logging.debug('OTLP Setup Done')

    def _find_file(self, root_folder, file_name):

        # safe guard to not go to deep
        if root_folder.count('/') > 4:
            return None

        for root, dirs, files in os.walk(root_folder,topdown=True):
            if file_name in files:
                return os.path.join(root, file_name)
            else:
                return self._find_file(root_folder+'/..',file_name)

        return None