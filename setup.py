from setuptools import setup, find_packages

setup(
    name="ledgergpt",
    version="1.0.0",
    description="Enterprise Conversational AI & Deterministic Query Engine for ERP & Tally Prime",
    author="Amit Rathi (Datawizibility)",
    author_email="datawizibility@gmail.com",
    packages=find_packages(),
    py_modules=["cli"],
    include_package_data=True,
    install_requires=[
        "flask>=2.3.0",
        "python-dotenv>=1.0.0",
        "requests>=2.28.0",
        "openpyxl>=3.1.0",
    ],
    entry_points={
        "console_scripts": [
            "ledgergpt=ledgergpt.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Office/Business :: Financial :: Accounting",
    ],
    python_requires=">=3.9",
)
