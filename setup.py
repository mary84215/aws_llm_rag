from pathlib import Path

from setuptools import find_packages, setup

README = Path(__file__).parent / "README.md"

setup(
    name="aws-bedrock-kb-cli",
    version="0.1.0",
    description="CLI for querying AWS Bedrock Knowledge Bases with metadata filtering",
    long_description=README.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    python_requires=">=3.9",
    packages=find_packages(include=["kb_tool", "kb_tool.*"]),
    py_modules=["cli"],
    install_requires=[
        "boto3>=1.34.0",
    ],
    extras_require={
        "dev": ["mypy", "black"],
    },
    entry_points={
        "console_scripts": [
            "kb-cli=cli:main",
        ]
    },
)
