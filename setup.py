#!/usr/bin/env python
import setuptools
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

__version__ = "1.1.20"

setuptools.setup(
    name="qontrol",
    version=__version__,
    description="Python Library for interfacing with Qontrol integrated optics control hardware.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/takeqontrol/api",
    author="Qontrol",
    author_email="support@qontrol.co.uk",
    py_modules=["qontrol"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Physics",
    ],
    install_requires=["pyserial"],
)