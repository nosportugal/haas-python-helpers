from setuptools import setup, find_packages

setup(
    name='otel-log-wrapper',
    version='0.0.1',
    url='https://github.com/nosportugal/haas-python-helpers/otel-log-wrapper',
    author='Filipe Carvalho',
    author_email='filipe.carvalho@nos.pt',
    description='Description of my package',
    packages=find_packages(),
    install_requires=[
        'opentelemetry-exporter-otlp',
        'opentelemetry-instrumentation-logging'
    ],
)
