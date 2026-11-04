"""Lightweight Prometheus text-format registry (no external dependency)."""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Sequence


class Counter:
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        registry: PrometheusRegistry | None = None,
    ) -> None:
        self._name = name
        self._documentation = documentation
        self._labelnames = tuple(labelnames)
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = threading.Lock()
        if registry is not None:
            registry.register(self)

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self._values[key] += amount

    def _label_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((k, labels[k]) for k in self._labelnames if k in labels))

    def collect(self) -> list[str]:
        lines = [f"# HELP {self._name} {self._documentation}", f"# TYPE {self._name} counter"]
        with self._lock:
            items = list(self._values.items())
        for label_tuple, value in sorted(items):
            label_str = _format_labels(label_tuple)
            lines.append(f"{self._name}{label_str} {value}")
        if not items:
            lines.append(f"{self._name} 0")
        return lines


class Gauge:
    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: Sequence[str] = (),
        registry: PrometheusRegistry | None = None,
    ) -> None:
        self._name = name
        self._documentation = documentation
        self._labelnames = tuple(labelnames)
        self._values: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._lock = threading.Lock()
        if registry is not None:
            registry.register(self)

    def set(self, value: float, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = value

    def inc(self, amount: float = 1.0, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self._values[key] += amount

    def dec(self, amount: float = 1.0, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = max(0.0, self._values[key] - amount)

    def _label_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((k, labels[k]) for k in self._labelnames if k in labels))

    def collect(self) -> list[str]:
        lines = [f"# HELP {self._name} {self._documentation}", f"# TYPE {self._name} gauge"]
        with self._lock:
            items = list(self._values.items())
        for label_tuple, value in sorted(items):
            label_str = _format_labels(label_tuple)
            lines.append(f"{self._name}{label_str} {value}")
        if not items:
            lines.append(f"{self._name} 0")
        return lines


class Histogram:
    def __init__(
        self,
        name: str,
        documentation: str,
        buckets: Sequence[float] = (10, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
        labelnames: Sequence[str] = (),
        registry: PrometheusRegistry | None = None,
    ) -> None:
        self._name = name
        self._documentation = documentation
        self._buckets = tuple(sorted(buckets))
        self._labelnames = tuple(labelnames)
        self._counts: dict[tuple[tuple[str, str], ...], dict[float, int]] = defaultdict(
            lambda: {b: 0 for b in self._buckets}
        )
        self._sums: dict[tuple[tuple[str, str], ...], float] = defaultdict(float)
        self._totals: dict[tuple[tuple[str, str], ...], int] = defaultdict(int)
        self._lock = threading.Lock()
        if registry is not None:
            registry.register(self)

    def observe(self, value: float, **labels: str) -> None:
        key = self._label_key(labels)
        with self._lock:
            self._sums[key] += value
            self._totals[key] += 1
            for bucket in self._buckets:
                if value <= bucket:
                    self._counts[key][bucket] += 1

    def _label_key(self, labels: dict[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((k, labels[k]) for k in self._labelnames if k in labels))

    def collect(self) -> list[str]:
        lines = [
            f"# HELP {self._name} {self._documentation}",
            f"# TYPE {self._name} histogram",
        ]
        with self._lock:
            items = list(self._counts.items())
            sums = dict(self._sums)
            totals = dict(self._totals)
        for label_tuple, bucket_counts in sorted(items):
            label_str = _format_labels(label_tuple)
            for bucket in self._buckets:
                le = "+Inf" if bucket == self._buckets[-1] else str(bucket)
                # Cumulative bucket counts
                cumulative = sum(
                    bucket_counts[b] for b in self._buckets if b <= bucket
                )
                bucket_labels = label_tuple + (("le", le),)
                lines.append(f"{self._name}_bucket{_format_labels(bucket_labels)} {cumulative}")
            lines.append(f"{self._name}_sum{label_str} {sums.get(label_tuple, 0.0)}")
            lines.append(f"{self._name}_count{label_str} {totals.get(label_tuple, 0)}")
        if not items:
            for bucket in self._buckets:
                le = "+Inf" if bucket == self._buckets[-1] else str(bucket)
                lines.append(f'{self._name}_bucket{{le="{le}"}} 0')
            lines.append(f"{self._name}_sum 0")
            lines.append(f"{self._name}_count 0")
        return lines


class PrometheusRegistry:
    def __init__(self) -> None:
        self._collectors: list = []
        self._lock = threading.Lock()

    def register(self, collector) -> None:
        with self._lock:
            self._collectors.append(collector)

    def generate_latest(self) -> str:
        lines: list[str] = []
        with self._lock:
            collectors = list(self._collectors)
        for collector in collectors:
            lines.extend(collector.collect())
        return "\n".join(lines) + "\n"


def _format_labels(labels: tuple[tuple[str, str], ...]) -> str:
    if not labels:
        return ""
    inner = ",".join(f'{k}="{_escape(v)}"' for k, v in labels)
    return "{" + inner + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
