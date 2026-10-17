"""Process and service supervisor for SiteSentinel with graceful shutdown and health monitoring."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from sentinel.config import SentinelConfig, load_sentinel_config
from sentinel.ports.event_bus import EventBus

logger = logging.getLogger("sentinel.runtime.supervisor")


class ServiceDefinition:
    """Descriptor for a managed service task."""

    def __init__(self, name: str, coroutine_fn: Callable[..., Any]) -> None:
        self.name = name
        self.coroutine_fn = coroutine_fn
        self.status = "stopped"
        self.restart_count = 0
        self.task: Optional[asyncio.Task] = None


class ProcessSupervisor:
    """Manages service lifecycles, signal handling, PID files, and health heartbeats."""

    def __init__(
        self,
        config: Optional[SentinelConfig] = None,
        event_bus: Optional[EventBus] = None,
        pid_file: Path | str = "logs/sentinel.pid",
    ) -> None:
        self.cfg = config or load_sentinel_config()
        self.event_bus = event_bus
        self.pid_file = Path(pid_file)
        self.services: Dict[str, ServiceDefinition] = {}
        self.running = False
        self._shutdown_event = asyncio.Event()
        self._health_task: Optional[asyncio.Task] = None

    def register_service(self, name: str, coroutine_fn: Callable[..., Any]) -> None:
        """Registers a service task function."""
        self.services[name] = ServiceDefinition(name, coroutine_fn)

    def write_pid(self) -> None:
        """Writes current process ID to pid_file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()), encoding="utf-8")

    def remove_pid(self) -> None:
        """Removes pid_file if it exists."""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception:
            pass

    async def start(self) -> None:
        """Starts all registered services and monitors their execution."""
        self.running = True
        self.write_pid()
        self._setup_signals()

        logger.info("SiteSentinel Process Supervisor started (PID %d)", os.getpid())

        # Start health aggregator heartbeat
        self._health_task = asyncio.create_task(self._health_heartbeat_loop())

        # Launch services
        for name, service in self.services.items():
            service.status = "running"
            service.task = asyncio.create_task(self._run_supervised_service(service))

        # Wait until shutdown requested
        await self._shutdown_event.wait()
        await self._shutdown()

    async def _run_supervised_service(self, service: ServiceDefinition) -> None:
        while self.running:
            try:
                logger.info("Starting service '%s'", service.name)
                service.status = "running"
                await service.coroutine_fn()
                if not self.running:
                    break
                logger.warning("Service '%s' exited cleanly unexpectedly", service.name)
            except asyncio.CancelledError:
                logger.info("Service '%s' cancelled", service.name)
                break
            except Exception as e:
                service.restart_count += 1
                service.status = "degraded"
                logger.error(
                    "Service '%s' failed: %s. Restart count: %d",
                    service.name,
                    e,
                    service.restart_count,
                )
                if not self.running:
                    break
                await asyncio.sleep(min(service.restart_count * 0.5, 5.0))
        service.status = "stopped"

    async def _health_heartbeat_loop(self) -> None:
        """Publishes aggregated health every 2 seconds."""
        health_topic = self.cfg.mqtt.health_topic
        while self.running:
            try:
                payload = {
                    "component": "supervisor",
                    "status": "ok"
                    if all(s.status == "running" for s in self.services.values())
                    else "degraded",
                    "services": {s.name: s.status for s in self.services.values()},
                    "ts": time.time(),
                }
                if self.event_bus is not None:
                    self.event_bus.publish(health_topic, payload, qos=0, retain=True)
            except Exception as e:
                logger.debug("Failed publishing health heartbeat: %s", e)
            await asyncio.sleep(2.0)

    def _setup_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.trigger_shutdown)
            except NotImplementedError:
                # Signal handlers not implemented on Windows
                pass

    def trigger_shutdown(self) -> None:
        """Triggers graceful shutdown sequence."""
        if not self.running:
            return
        logger.info("Shutdown signal received, initiating graceful shutdown...")
        self.running = False
        self._shutdown_event.set()

    async def _shutdown(self) -> None:
        """Gracefully stops services, cancels background tasks, and removes PID file."""
        if self._health_task:
            self._health_task.cancel()

        for name, service in self.services.items():
            if service.task and not service.task.done():
                logger.info("Stopping service '%s'...", name)
                service.task.cancel()

        # Wait for service tasks to complete
        pending = [s.task for s in self.services.values() if s.task]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if self.event_bus is not None:
            try:
                self.event_bus.stop()
            except Exception:
                pass

        self.remove_pid()
        logger.info("SiteSentinel Process Supervisor stopped cleanly.")
