"""Performance profiling infrastructure for Cortex.

Provides timing, memory tracking, and reporting for critical code paths.
Used to establish baselines and validate optimization improvements.
"""

import time
import tracemalloc
import threading
import json
import logging
import functools
import statistics
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class OperationRecord:
    """A single recorded operation measurement."""

    name: str
    duration_ms: float
    memory_delta_kb: float
    timestamp: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationStats:
    """Aggregated statistics for an operation."""

    name: str
    count: int
    min_ms: float
    max_ms: float
    avg_ms: float
    median_ms: float
    p95_ms: float
    p99_ms: float
    total_ms: float
    avg_memory_kb: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "count": self.count,
            "min_ms": round(self.min_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "avg_ms": round(self.avg_ms, 3),
            "median_ms": round(self.median_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "total_ms": round(self.total_ms, 3),
            "avg_memory_kb": round(self.avg_memory_kb, 3),
        }


class PerformanceProfiler:
    """Singleton performance profiler for instrumenting critical code paths.

    Usage:
        profiler = PerformanceProfiler.get_instance()

        # Context manager
        with profiler.measure("search"):
            results = search_files(pattern)

        # Decorator
        @profiler.profile("ast_parse")
        def parse_file(path):
            ...

        # Report
        report = profiler.generate_report()
    """

    _instance: Optional["PerformanceProfiler"] = None
    _lock = threading.Lock()

    def __init__(self, enabled: bool = False, output_dir: Optional[str] = None):
        self._enabled = enabled
        self._output_dir = Path(output_dir) if output_dir else Path(".cortex/profiles")
        self._records: Dict[str, List[OperationRecord]] = {}
        self._records_lock = threading.Lock()
        self._tracemalloc_started = False

    @classmethod
    def get_instance(cls, **kwargs) -> "PerformanceProfiler":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(**kwargs)
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        with cls._lock:
            cls._instance = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
        if value and not self._tracemalloc_started:
            try:
                tracemalloc.start()
                self._tracemalloc_started = True
            except RuntimeError:
                pass

    def _record(self, name: str, duration_ms: float, memory_delta_kb: float, **metadata):
        with self._records_lock:
            if name not in self._records:
                self._records[name] = []
            self._records[name].append(
                OperationRecord(
                    name=name,
                    duration_ms=duration_ms,
                    memory_delta_kb=memory_delta_kb,
                    timestamp=time.time(),
                    metadata=metadata,
                )
            )

    @contextmanager
    def measure(self, name: str, **metadata):
        """Context manager to measure an operation's duration and memory.

        Args:
            name: Operation name (e.g., "search", "ast_parse", "token_count")
            **metadata: Additional metadata to attach to the record
        """
        if not self._enabled:
            yield
            return

        mem_before = 0
        if self._tracemalloc_started:
            snapshot = tracemalloc.take_snapshot()
            mem_before = sum(stat.size for stat in snapshot.statistics("filename"))

        start = time.perf_counter()
        yield
        duration_ms = (time.perf_counter() - start) * 1000

        mem_after = 0
        if self._tracemalloc_started:
            snapshot = tracemalloc.take_snapshot()
            mem_after = sum(stat.size for stat in snapshot.statistics("filename"))

        memory_delta_kb = (mem_after - mem_before) / 1024
        self._record(name, duration_ms, memory_delta_kb, **metadata)

    def profile(self, name: str):
        """Decorator to profile a function.

        Args:
            name: Operation name for the profiled function
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.measure(name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def _compute_percentile(self, sorted_values: List[float], percentile: float) -> float:
        if not sorted_values:
            return 0.0
        k = (len(sorted_values) - 1) * (percentile / 100.0)
        f = int(k)
        c = f + 1
        if c >= len(sorted_values):
            return sorted_values[-1]
        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def get_stats(self, name: str) -> Optional[OperationStats]:
        """Get aggregated statistics for a named operation."""
        with self._records_lock:
            records = self._records.get(name)
            if not records:
                return None

            durations = sorted(r.duration_ms for r in records)
            memory_deltas = [r.memory_delta_kb for r in records]

            return OperationStats(
                name=name,
                count=len(durations),
                min_ms=durations[0],
                max_ms=durations[-1],
                avg_ms=statistics.mean(durations),
                median_ms=statistics.median(durations),
                p95_ms=self._compute_percentile(durations, 95),
                p99_ms=self._compute_percentile(durations, 99),
                total_ms=sum(durations),
                avg_memory_kb=statistics.mean(memory_deltas) if memory_deltas else 0,
            )

    def generate_report(self) -> Dict[str, Any]:
        """Generate a full profiling report for all recorded operations."""
        with self._records_lock:
            operation_names = list(self._records.keys())

        report = {
            "timestamp": time.time(),
            "operations": {},
            "summary": {
                "total_operations": 0,
                "total_time_ms": 0,
                "slowest_operation": None,
                "most_called_operation": None,
            },
        }

        slowest_avg = 0
        most_calls = 0

        for name in operation_names:
            stats = self.get_stats(name)
            if stats:
                report["operations"][name] = stats.to_dict()
                report["summary"]["total_operations"] += stats.count
                report["summary"]["total_time_ms"] += stats.total_ms

                if stats.avg_ms > slowest_avg:
                    slowest_avg = stats.avg_ms
                    report["summary"]["slowest_operation"] = name

                if stats.count > most_calls:
                    most_calls = stats.count
                    report["summary"]["most_called_operation"] = name

        report["summary"]["total_time_ms"] = round(report["summary"]["total_time_ms"], 3)
        return report

    def export_report(self, path: Optional[str] = None) -> str:
        """Export profiling report to a JSON file.

        Returns:
            Path to the exported report file
        """
        report = self.generate_report()

        if path is None:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = int(time.time())
            path = str(self._output_dir / f"profile_{timestamp}.json")

        with open(path, "w") as f:
            json.dump(report, f, indent=2)

        logger.info(f"Profile report exported to {path}")
        return path

    def clear(self):
        """Clear all recorded data."""
        with self._records_lock:
            self._records.clear()

    def get_operation_names(self) -> List[str]:
        """Get list of all recorded operation names."""
        with self._records_lock:
            return list(self._records.keys())

    def get_record_count(self, name: str) -> int:
        """Get number of records for a named operation."""
        with self._records_lock:
            records = self._records.get(name)
            return len(records) if records else 0
