from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="mimo-devflow",
    version="0.3.0",
    author="MIMO DevFlow Contributors",
    author_email="dev@mimodevflow.dev",
    description="Production-grade multi-agent orchestration framework for Xiaomi MiMo models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nousresearch/mimo-devflow",
    project_urls={
        "Bug Tracker": "https://github.com/nousresearch/mimo-devflow/issues",
        "Documentation": "https://mimodevflow.readthedocs.io",
        "Source Code": "https://github.com/nousresearch/mimo-devflow",
    },
    packages=find_packages(exclude=["tests", "tests.*", "examples", "examples.*", "docs"]),
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.25.0",
        "pydantic>=2.0.0",
        "rich>=13.0.0",
        "click>=8.0.0",
        "pyyaml>=6.0",
        "tiktoken>=0.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "ruff>=0.1.0",
            "mypy>=1.5.0",
            "black>=23.0.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings[python]>=0.24.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "mimo-devflow=mimo_devflow.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Typing :: Typed",
    ],
    keywords="ai, agents, xiaomi, mimo, multi-agent, workflow, orchestration, llm",
)
