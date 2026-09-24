from setuptools import find_packages, setup


setup(
    name="banzena-inventory-check",
    version="0.1.0",
    description="Anonymous public inventory and storefront response check for Banzena shops.",
    author="Tiee",
    python_requires=">=3.11",
    packages=find_packages("src"),
    package_dir={"": "src"},
    entry_points={
        "console_scripts": [
            "banzena-inventory-check=banzena_inventory_check.__main__:main",
        ]
    },
)
