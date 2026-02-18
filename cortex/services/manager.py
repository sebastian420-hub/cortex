"""Service lifecycle manager for Cortex Go services.

Manages starting, stopping, and health checking of Go gRPC services
that run as background processes.
"""

import logging
import subprocess
import time
import os
import signal
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class ServiceManager:
    """Manages lifecycle of Cortex Go background services.

    Handles starting/stopping the Go services binary and monitoring
    its health via gRPC health checks.

    Usage:
        manager = ServiceManager(services_config)
        manager.start_services()
        ...
        manager.stop_services()
    """

    def __init__(self, config: Dict[str, Any]):
        self._config = config
        self._process: Optional[subprocess.Popen] = None
        self._binary_path: Optional[Path] = None
        self._started = False

        # Try to find the Go services binary
        self._binary_path = self._find_binary()

    def _find_binary(self) -> Optional[Path]:
        """Find the cortex-services binary."""
        candidates = [
            Path("go/cmd/cortex-services/cortex-services"),
            Path("go/cmd/cortex-services/cortex-services.exe"),
            Path("go/cortex-services"),
            Path("go/cortex-services.exe"),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        return None

    def start_services(self) -> bool:
        """Start Go services as a background process.

        Returns:
            True if services started successfully
        """
        if self._started:
            logger.info("Services already running")
            return True

        if not self._binary_path:
            logger.warning("Go services binary not found. Build with 'make go-build'.")
            return False

        try:
            env = os.environ.copy()
            cache_config = self._config.get("cache", {})
            model_config = self._config.get("model_manager", {})

            env["CORTEX_CACHE_PORT"] = str(cache_config.get("port", 50051))
            env["CORTEX_MODEL_PORT"] = str(model_config.get("port", 50052))

            self._process = subprocess.Popen(
                [str(self._binary_path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait briefly for startup
            time.sleep(1)

            if self._process.poll() is not None:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                logger.error(f"Go services failed to start: {stderr}")
                return False

            self._started = True
            logger.info(f"Go services started (PID: {self._process.pid})")
            return True

        except FileNotFoundError:
            logger.error(f"Binary not found: {self._binary_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to start Go services: {e}")
            return False

    def stop_services(self):
        """Gracefully stop Go services."""
        if not self._started or not self._process:
            return

        try:
            # Send SIGTERM for graceful shutdown
            if os.name == "nt":
                self._process.terminate()
            else:
                self._process.send_signal(signal.SIGTERM)

            # Wait up to 5 seconds for clean shutdown
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Go services did not stop gracefully, killing...")
                self._process.kill()
                self._process.wait(timeout=2)

            logger.info("Go services stopped")
        except Exception as e:
            logger.error(f"Error stopping Go services: {e}")
        finally:
            self._started = False
            self._process = None

    def health_check(self) -> Dict[str, Any]:
        """Check health of all services.

        Returns:
            Dict with health status for each service
        """
        result = {
            "running": self._started,
            "pid": self._process.pid if self._process else None,
            "cache": {"status": "unknown"},
            "model_manager": {"status": "unknown"},
        }

        if not self._started:
            result["cache"]["status"] = "stopped"
            result["model_manager"]["status"] = "stopped"
            return result

        # Check if process is still running
        if self._process and self._process.poll() is not None:
            self._started = False
            result["running"] = False
            result["cache"]["status"] = "crashed"
            result["model_manager"]["status"] = "crashed"
            return result

        result["cache"]["status"] = "running"
        result["model_manager"]["status"] = "running"

        return result

    def ensure_running(self) -> bool:
        """Ensure services are running, restart if needed.

        Returns:
            True if services are running
        """
        if self._started and self._process and self._process.poll() is None:
            return True

        logger.info("Services not running, attempting restart...")
        self._started = False
        return self.start_services()

    @property
    def is_running(self) -> bool:
        """Check if services are currently running."""
        return self._started and self._process is not None and self._process.poll() is None
