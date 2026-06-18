"""Standalone package for the FilingFirehose buried-events 8-K classifier."""
from setuptools import setup, find_packages
from pathlib import Path

setup(
    name="buried-events-parser",
    version="0.1.0",
    description="Find buried material events in SEC 8-K filings the filer didn't report. Pure-Python regex classifier, no LLM.",
    long_description=(Path(__file__).parent / "README.md").read_text(),
    long_description_content_type="text/markdown",
    author="Jared Ablon",
    author_email="info@filingfirehose.com",
    url="https://github.com/jaablon/buried-events-parser",
    project_urls={
        "Homepage": "https://filingfirehose.com",
        "Source": "https://github.com/jaablon/buried-events-parser",
        "Issues": "https://github.com/jaablon/buried-events-parser/issues",
    },
    license="MIT",
    packages=find_packages(exclude=["tests", "examples"]),
    python_requires=">=3.10",
    install_requires=[],  # stdlib only
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
        "Topic :: Text Processing :: Linguistic",
    ],
    keywords="sec edgar 8-k filings cybersecurity disclosure parser regex",
)
