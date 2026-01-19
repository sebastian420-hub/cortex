Installation
============

Requirements
------------

* Python 3.8 or higher
* pip package manager

Installing from PyPI
--------------------

.. code-block:: bash

   pip install cortex-terminal

Installing from Source
----------------------

.. code-block:: bash

   git clone https://github.com/yourusername/cortex.git
   cd cortex
   pip install -e .

Development Installation
------------------------

For development, install with dev dependencies:

.. code-block:: bash

   pip install -e ".[dev]"
   # or
   pip install -r requirements-dev.txt

Optional Dependencies
---------------------

Tree-sitter (for AST analysis)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install tree-sitter tree-sitter-python tree-sitter-javascript

Ripgrep (for fast searching)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Cortex will use ripgrep if available, falling back to Python-based search otherwise.

* **macOS**: ``brew install ripgrep``
* **Ubuntu/Debian**: ``apt install ripgrep``
* **Windows**: ``choco install ripgrep`` or ``scoop install ripgrep``
