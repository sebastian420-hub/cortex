Quick Start
===========

This guide will get you up and running with Cortex in 5 minutes.

Installation
------------

.. code-block:: bash

   pip install cortex-terminal

Or install from source:

.. code-block:: bash

   git clone https://github.com/yourusername/cortex.git
   cd cortex
   pip install -e .


Configuration
-------------

Set your API key:

.. code-block:: bash

   # For Anthropic Claude
   export ANTHROPIC_API_KEY=your-key-here

   # For OpenRouter (multiple models)
   export OPENROUTER_API_KEY=your-key-here

   # For DeepSeek
   export DEEPSEEK_API_KEY=your-key-here


Basic Usage
-----------

Start interactive mode:

.. code-block:: bash

   cortex

Or run a single command:

.. code-block:: bash

   cortex -m "What files are in this directory?"


Example Session
---------------

.. code-block:: text

   $ cortex
   Cortex v0.1.0 - Type 'exit' to quit

   You: What's in this directory?

   Assistant: Let me check the directory contents.

   [Executing: glob_files pattern="*"]

   I found the following files:
   - README.md
   - setup.py
   - cortex/
   - tests/
   - docs/

   You: Read the README

   Assistant: [Reading README.md...]


Next Steps
----------

* Learn about :doc:`commands` for available commands
* Explore :doc:`tools` for built-in capabilities
* Create custom tools with :doc:`plugin_development`
