#!/usr/bin/env python
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

__version__ = "1.1.0"

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
    # packages=setuptools.find_packages(),
    # install_requires=[
    #     "ipython",
    #     "numpy",
    #     "pandas",
    #     "sympy",
    #     # "scipy",
    #     "cython",
    #     "tabulate",
    # ],

    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)