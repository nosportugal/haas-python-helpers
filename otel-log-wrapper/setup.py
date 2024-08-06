from setuptools import setup, find_packages

setup(
    name='otel-log-wrapper',
    version='0.0.1',
    url='https://github.com/nosportugal/haas-python-helpers/otel-log-wrapper',
    author='Filipe Carvalho',
    author_email='filipe.carvalho@nos.pt',
    description='Description of my package',
    packages=find_packages(),
    install_requires=['opentelemetry._logs',
                      'opentelemetry.exporter.otlp.proto.http._log_exporter',
                      'opentelemetry.instrumentation.logging',
                      'opentelemetry.sdk._logs',
                      'opentelemetry.sdk._logs.export',
                      'opentelemetry.sdk.resources'],
)
