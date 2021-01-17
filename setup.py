from setuptools import setup, find_packages
import os

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
exec(open(os.path.join(
    BASE_DIR, 'humanized_opening_hours', 'version.py')).read())

setup(
    name="osm_humanized_opening_hours",
    version=__version__,  # noqa
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
