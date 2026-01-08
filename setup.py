"""Setup script for LocalAgent (backup for compatibility)"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="localagent",
    version="1.0.0",
    author="LocalAgent Contributors",
    description="A Claude Code-like terminal agent using local LLM models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/localagent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "ollama>=0.1.0",
        "rich>=13.0.0",
        "prompt-toolkit>=3.0.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "localagent=localagent.cli:main",
        ],
    },
)

