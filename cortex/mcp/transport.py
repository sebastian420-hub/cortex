"""MCP transport layer (stdio)."""

import asyncio
import json
import subprocess
import sys
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

from .protocol import MCPRequest, MCPResponse


@dataclass
class StdioTransport:
    """MCP transport over stdio (stdin/stdout)."""

    process: subprocess.Popen
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter

    @classmethod
    async def create(cls, command: str) -> "StdioTransport":
        """Create a new stdio transport by starting a subprocess."""
        # Start the process
        process = await asyncio.create_subprocess_exec(
            *command.split(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Create stream readers/writers
        loop = asyncio.get_event_loop()

        # Wrap stdin/stdout streams
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, process.stdout)

        transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, process.stdin
        )
        writer = asyncio.StreamWriter(transport, writer_protocol, reader, loop)

        return cls(process, reader, writer)

    async def send_request(self, request: MCPRequest) -> MCPResponse:
        """Send a request and wait for response."""
        # Send request
        request_json = request.to_json() + "\n"
        self.writer.write(request_json.encode("utf-8"))
        await self.writer.drain()

        # Read response line
        line_bytes = await self.reader.readline()
        if not line_bytes:
            raise ConnectionError("Server closed connection")

        line = line_bytes.decode("utf-8").rstrip("\n")

        # Parse response
        return MCPResponse.from_json(line)

    async def close(self) -> None:
        """Close the transport and terminate the process."""
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except (OSError, ConnectionError, BrokenPipeError):
            pass  # Connection already closed

        # Terminate process
        try:
            self.process.terminate()
            await self.process.wait()
        except (ProcessLookupError, OSError):
            pass  # Process already terminated


class SimpleStdioTransport:
    """Simpler synchronous stdio transport for basic testing."""

    def __init__(self, command: str, args: Optional[list] = None):
        self.command = command
        self.args = args or []
        self.process: Optional[subprocess.Popen] = None
        self._response_queue: Optional[Any] = None
        self._reader_thread: Optional[Any] = None

    def start(self) -> None:
        """Start the MCP server process."""
        import shlex
        import threading
        import queue

        # Parse command properly
        if sys.platform == "win32":
            # On Windows, parse command but don't use shell=True
            # Use shlex with posix=False for Windows
            try:
                cmd_parts = shlex.split(self.command, posix=False)
            except ValueError:
                cmd_parts = self.command.split()
        else:
            cmd_parts = shlex.split(self.command)

        self.process = subprocess.Popen(
            cmd_parts,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,  # Unbuffered
        )

        # Create a queue for responses and start reader thread
        self._response_queue = queue.Queue()

        def reader():
            """Read lines from stdout in a background thread."""
            try:
                while self.process and self.process.poll() is None:
                    line = self.process.stdout.readline()
                    if line:
                        self._response_queue.put(line.decode("utf-8").rstrip("\n\r"))
                    elif self.process.poll() is not None:
                        break
            except Exception as e:
                self._response_queue.put(f"__ERROR__:{e}")

        self._reader_thread = threading.Thread(target=reader, daemon=True)
        self._reader_thread.start()

        # Give process a moment to start
        import time

        time.sleep(0.2)

        # Check if process started successfully
        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode("utf-8") if self.process.stderr else ""
            raise RuntimeError(f"MCP server process failed to start: {stderr}")

    def send_notification(self, request: MCPRequest) -> None:
        """Send a notification (no response expected)."""
        if self.process is None:
            raise RuntimeError("Transport not started")

        # Check if process is still alive
        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode("utf-8") if self.process.stderr else ""
            raise RuntimeError(f"MCP server process died unexpectedly: {stderr}")

        # Send notification (binary mode) - don't wait for response
        request_json = request.to_json() + "\n"
        self.process.stdin.write(request_json.encode("utf-8"))
        self.process.stdin.flush()

    def send_request(self, request: MCPRequest, timeout: float = 10.0) -> MCPResponse:
        """Send request and get response (synchronous)."""
        import queue

        if self.process is None:
            raise RuntimeError("Transport not started")

        # Check if process is still alive
        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode("utf-8") if self.process.stderr else ""
            raise RuntimeError(f"MCP server process died unexpectedly: {stderr}")

        try:
            # Send request (binary mode)
            request_json = request.to_json() + "\n"
            self.process.stdin.write(request_json.encode("utf-8"))
            self.process.stdin.flush()

            # Read response from queue with timeout
            try:
                line = self._response_queue.get(timeout=timeout)
            except queue.Empty:
                stderr = ""
                if self.process and self.process.stderr:
                    try:
                        stderr = self.process.stderr.read().decode("utf-8")
                    except (IOError, OSError, UnicodeDecodeError):
                        pass  # Unable to read stderr
                raise TimeoutError(
                    f"No response from MCP server within {timeout}s. stderr: {stderr}"
                )

            if line.startswith("__ERROR__:"):
                raise RuntimeError(f"Reader thread error: {line[10:]}")

            # Parse response
            return MCPResponse.from_json(line)
        except (TimeoutError, RuntimeError):
            raise
        except Exception as e:
            # Try to get stderr for debugging
            stderr = ""
            if self.process and self.process.stderr:
                try:
                    stderr = self.process.stderr.read().decode("utf-8")
                except (IOError, OSError, UnicodeDecodeError):
                    pass  # Unable to read stderr
            raise RuntimeError(f"MCP request failed: {e}. stderr: {stderr}")

    def stop(self) -> None:
        """Stop the MCP server process."""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except (subprocess.TimeoutExpired, OSError, ProcessLookupError):
                try:
                    self.process.kill()
                except (OSError, ProcessLookupError):
                    pass  # Process already terminated
            finally:
                self.process = None
