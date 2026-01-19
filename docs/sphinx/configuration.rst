Configuration
=============

Cortex can be configured through YAML files, environment variables, and command-line arguments.

Configuration File
------------------

The default configuration file is located at ``config/default.yaml``:

.. code-block:: yaml

   # Model settings
   model: claude-sonnet-4-20250514
   permission_mode: normal
   max_iterations: 15
   max_tokens: 100000

   # Parallel execution
   parallel_execution:
     enabled: true
     max_workers: 0  # 0 = auto-detect
     batch_size: 10

Environment Variables
---------------------

API keys are read from environment variables:

.. list-table::
   :header-rows: 1

   * - Variable
     - Description
   * - ``ANTHROPIC_API_KEY``
     - API key for Anthropic Claude models
   * - ``OPENROUTER_API_KEY``
     - API key for OpenRouter (multiple models)
   * - ``DEEPSEEK_API_KEY``
     - API key for DeepSeek models
   * - ``OPENAI_API_KEY``
     - API key for OpenAI models

Command-Line Arguments
----------------------

.. code-block:: bash

   cortex --help

   Options:
     -m, --model MODEL     Model to use
     -p, --permission      Permission mode (normal/auto/plan)
     --routing             Enable intelligent routing
     --config PATH         Path to config file
