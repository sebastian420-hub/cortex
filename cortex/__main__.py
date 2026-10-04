"""Allow ``python -m cortex`` (used by the Docker image) as an alias for the ``cortex`` command."""

from .cli import main

if __name__ == "__main__":
    main()
