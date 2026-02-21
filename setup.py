"""Setup script for Cortex (backup for compatibility)"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="cortex",
    version="1.0.0",
    author="Cortex Contributors",
    description="A unified agent for coding, cybersecurity, and personal assistance",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/cortex",
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
        "tiktoken>=0.5.0",
        "openai>=1.0.0",
        "anthropic>=0.18.0",
        "ddgs>=9.0.0",
        "python-dotenv>=1.0.0",
        "tree-sitter>=0.21.0",
        "tree-sitter-python>=0.21.0",
        "tree-sitter-javascript>=0.21.0",
        "tree-sitter-typescript>=0.21.0",
        "tree-sitter-java>=0.21.0",
        "tree-sitter-go>=0.21.0",
    ],
    entry_points={
        "console_scripts": [
            "cortex=cortex.cli:main",
        ],
    },
)
