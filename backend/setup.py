from setuptools import find_packages, setup


setup(
    name="tarkov",
    version="0.1.0",
    description="Tarkov event extraction pipeline",
    package_dir={"": "."},
    packages=find_packages(where="."),
    include_package_data=True,
    install_requires=[
        "SQLAlchemy==2.0.23",
        "pydantic==2.5.0",
        "click==8.1.7",
        "fastapi==0.115.6",
        "uvicorn==0.34.0",
        "requests==2.31.0",
    ],
    entry_points={
        "console_scripts": [
            "tarkov=tarkov.main:cli",
            "nsa=nsa.main:cli",
        ]
    },
)
