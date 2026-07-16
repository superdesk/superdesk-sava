#!/usr/bin/env python
from setuptools import setup, find_packages

DESCRIPTION = "Superdesk SAVA - natural language agent for Superdesk"

setup(
    name="superdesk-sava",
    version="0.0.1",
    description=DESCRIPTION,
    long_description=DESCRIPTION,
    author="Brian Mwangi",
    url="https://github.com/BrianMwangi21/superdesk-sava",
    license="AGPLv3",
    package_dir={"": "server"},
    packages=find_packages("server"),
    include_package_data=True,
    install_requires=[
        "openai>=1.0,<2.0",
    ],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Plugins",
        "Framework :: Flask",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3",
    ],
)
