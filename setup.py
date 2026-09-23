from setuptools import find_packages, setup

setup(
    name="forecastview",
    version="0.1.0",
    packages=find_packages(where="."),
    entry_points={
        "console_scripts": [
            "ncv=backend.scripts.ncv:main",
        ],
    },
)
