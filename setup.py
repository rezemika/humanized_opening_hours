# -*- coding: utf-8 -*-
 
from setuptools import setup, find_packages
import humanized_opening_hours

setup(
    name="osm_humanized_opening_hours",
    version=humanized_opening_hours.__version__,
    packages=find_packages(),
    author="rezemika",
    author_email="reze.mika@gmail.com",
    description="A parser for the opening_hours fields from OpenStreetMap.",
    long_description=open('README.md').read(),
    install_requires=["pytz", "isoweek", "copy", "babel"],
    include_package_data=True,
    url='http://github.com/rezemika/humanized_opening_hours',
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Natural Language :: French",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
    ]
)
