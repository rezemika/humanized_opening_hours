from setuptools import setup, find_packages
import os

import humanized_opening_hours

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

setup(
    name="osm_humanized_opening_hours",
    version=humanized_opening_hours.__version__,
    packages=find_packages(exclude=["doc", "tests"]),
    author="rezemika",
    author_email="reze.mika@gmail.com",
    description="A parser for the opening_hours fields from OpenStreetMap.",
    long_description=open(BASE_DIR + "/README.md", 'r').read(),
    install_requires=["lark-parser", "babel", "astral"],
    include_package_data=True,
    url='http://github.com/rezemika/humanized_opening_hours',
    keywords="openstreetmap opening_hours parser",
    classifiers=[
        "Programming Language :: Python",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Natural Language :: English",
        "Natural Language :: French",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Utilities",
        "Topic :: Other/Nonlisted Topic",
    ]
)
