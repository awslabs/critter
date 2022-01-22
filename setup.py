# https://raw.githubusercontent.com/pypa/sampleproject/main/setup.py

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from setuptools import setup
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

# Load version from file
exec(open("critter/version.py").read())

# https://packaging.python.org/guides/distributing-packages-using-setuptools/#setup-args
setup(
    name="critter",
    version=__version__,  # noqa: F821
    description="AWS Config Rule Integration TesTER",
    license="Apache License 2.0",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/awslabs/critter",
    author="Austin Heiman, AWS",
    author_email="aheiman@amazon.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="aws, config, rules, test, testing, integration",
    packages=["critter"],
    python_requires=">= 3.6",
    install_requires=["boto3>=1.11"],
    scripts=["bin/critter"],
)
