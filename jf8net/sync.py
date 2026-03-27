"""
jf8net.sync — Synchronous wrapper around JF8Client.

For scripts that don't want to manage an asyncio event loop::

    from jf8net.sync import JF8ClientSync

    with JF8ClientSync() as client:
        print(client.get_status())
        client.set_frequency(14078.0)
        client.send("W4ABC HELLO 73")

        for msg in client.messages():   # blocks, yields DecodedMessage
            print(msg)

Event handlers in sync mode are plain functions (not coroutines)::

    @client.on_message
    def handle(msg):
        print(msg)

    client.run_forever()   # blocks until Ctrl-C or disconnect
"""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import Any, Callable, Generator, Iterator, Optional, Union

from ._client import JF8Client, JF8Error, ConnectionError
from ._models import (
    AudioDevices, Config, DecodedMessage, FrameUpdate,
    RadioStatus, Spectrum, Status, TxFrame,
)
from typing import List

__all__ = ["JF8ClientSync", "JF8Error", "ConnectionError"]


class JF8ClientSync:
    """
    Synchronous wrapper around :class:`~jf8net.JF8Client`.

    All methods block until the result is available. Event callbacks are
    plain functions (not coroutines) and are called from the background thread.

    Use as a context manager::

        with JF8ClientSync(host="localhost") as client:
            status = client.get_status()
            client.send("W4ABC HELLO")

    Or manually::

        client = JF8ClientSync()
        client.connect()
        try:
            ...
        finally:
            client.disconnect()
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 2102,
        *,
        auto_reconnect: bool = True,
        reconnect_delay: float = 5.0,
        cmd_timeout: float = 10.0,
    ):
        self._async = JF8Client(
            host, port,
            auto_reconnect=auto_reconnect,
            reconnect_delay=reconnect_delay,
            cmd_timeout=cmd_timeout,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    # ── Connection lifecycle ──────────────────────────────────────────────────

    def connect(self) -> None:
        """Open the connection. Called automatically by the context manager."""
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, name="jf8net-sync", daemon=True
        )
        self._thread.start()
        # Wait until the event loop is running and connected
        if not self._ready.wait(timeout=15.0):
            raise ConnectionError("Timed out waiting for JF8Call connection")

    def disconnect(self) -> None:
        """Close the connection."""
        if self._loop and not self._loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._async.disconnect(), self._loop
            ).result(timeout=5.0)
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5.0)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._start())

    async def _start(self) -> None:
        await self._async.connect()
        self._ready.set()
        await self._async.run_forever()

    def __enter__(self) -> "JF8ClientSync":
        self.connect()
        return self

    def __exit__(self, *_: Any) -> None:
        self.disconnect()

    # ── Internal helper ───────────────────────────────────────────────────────

    def _run(self, coro) -> Any:
        if self._loop is None or self._loop.is_closed():
            raise ConnectionError("Not connected")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=self._async._cmd_timeout + 2)

    # ── Event handlers ────────────────────────────────────────────────────────

    def on(self, event: str, handler: Optional[Callable] = None) -> Any:
        """Register a plain-function event handler."""
        return self._async.on(event, handler)

    def off(self, event: str, handler: Callable) -> None:
        self._async.off(event, handler)

    def on_message(self, fn: Callable) -> Callable:
        return self._async.on_message(fn)

    def on_frame(self, fn: Callable) -> Callable:
        return self._async.on_frame(fn)

    def on_status(self, fn: Callable) -> Callable:
        return self._async.on_status(fn)

    def on_spectrum(self, fn: Callable) -> Callable:
        return self._async.on_spectrum(fn)

    def on_tx_started(self, fn: Callable) -> Callable:
        return self._async.on_tx_started(fn)

    def on_tx_finished(self, fn: Callable) -> Callable:
        return self._async.on_tx_finished(fn)

    def on_radio_connected(self, fn: Callable) -> Callable:
        return self._async.on_radio_connected(fn)

    def on_radio_disconnected(self, fn: Callable) -> Callable:
        return self._async.on_radio_disconnected(fn)

    def on_config_changed(self, fn: Callable) -> Callable:
        return self._async.on_config_changed(fn)

    def run_forever(self) -> None:
        """Block the calling thread until the connection closes."""
        if self._thread:
            self._thread.join()

    # ── Blocking API — mirrors JF8Client ─────────────────────────────────────

    @property
    def cached_status(self) -> Optional[Status]:
        return self._async.cached_status

    def get_status(self) -> Status:
        return self._run(self._async.get_status())

    def get_config(self) -> Config:
        return self._run(self._async.get_config())

    def set_config(self, **kwargs) -> Config:
        return self._run(self._async.set_config(**kwargs))

    def get_audio_devices(self) -> AudioDevices:
        return self._run(self._async.get_audio_devices())

    def restart_audio(self) -> None:
        self._run(self._async.restart_audio())

    def get_radio(self) -> RadioStatus:
        return self._run(self._async.get_radio())

    def connect_radio(self, **kwargs) -> None:
        self._run(self._async.connect_radio(**kwargs))

    def disconnect_radio(self) -> None:
        self._run(self._async.disconnect_radio())

    def set_frequency(self, khz: float) -> float:
        return self._run(self._async.set_frequency(khz))

    def set_ptt(self, on: bool) -> None:
        self._run(self._async.set_ptt(on))

    def tune(self) -> None:
        self._run(self._async.tune())

    def get_messages(self, offset: int = 0, limit: int = 100) -> List[DecodedMessage]:
        return self._run(self._async.get_messages(offset, limit))

    def clear_messages(self) -> None:
        self._run(self._async.clear_messages())

    def get_spectrum(self) -> Spectrum:
        return self._run(self._async.get_spectrum())

    def send(self, text: str, submode: Optional[Union[str, int]] = None) -> int:
        return self._run(self._async.send(text, submode=submode))

    def send_heartbeat(self) -> int:
        return self._run(self._async.send_heartbeat())

    def send_snr_query(self, to: str) -> int:
        return self._run(self._async.send_snr_query(to))

    def send_info_query(self, to: str) -> int:
        return self._run(self._async.send_info_query(to))

    def send_status_query(self, to: str) -> int:
        return self._run(self._async.send_status_query(to))

    def get_tx_queue(self) -> List[TxFrame]:
        return self._run(self._async.get_tx_queue())

    def clear_tx_queue(self) -> None:
        self._run(self._async.clear_tx_queue())

    def wait_for_tx(self, timeout: float = 120.0) -> None:
        self._run(self._async.wait_for_tx(timeout=timeout))

    def send_and_wait(
        self, text: str, submode: Optional[Union[str, int]] = None,
        timeout: float = 120.0
    ) -> None:
        self._run(self._async.send_and_wait(text, submode=submode, timeout=timeout))

    def send_grid_query(self, to: str) -> int:
        return self._run(self._async.send_grid_query(to))

    def send_hearing_query(self, to: str) -> int:
        return self._run(self._async.send_hearing_query(to))

    def get_bands(self):
        return self._run(self._async.get_bands())

    def set_bands(self, bands) -> int:
        return self._run(self._async.set_bands(bands))

    def get_solar(self):
        return self._run(self._async.get_solar())

    def get_qso_log(self, offset: int = 0, limit: int = 100):
        return self._run(self._async.get_qso_log(offset=offset, limit=limit))

    def export_adif(self) -> str:
        return self._run(self._async.export_adif())

    def get_inbox(self, for_call: str = ""):
        return self._run(self._async.get_inbox(for_call=for_call))

    def inbox_send(self, to: str, body: str) -> bool:
        return self._run(self._async.inbox_send(to, body))

    def inbox_store(self, to: str, body: str) -> str:
        return self._run(self._async.inbox_store(to, body))

    def inbox_delete(self, msg_id: int) -> None:
        self._run(self._async.inbox_delete(msg_id))

    def inbox_mark_read(self, msg_id: int) -> None:
        self._run(self._async.inbox_mark_read(msg_id))

    # ── Generator-style streaming ─────────────────────────────────────────────

    def messages(
        self,
        *,
        include_frames: bool = False,
        timeout: Optional[float] = None,
    ) -> Iterator[Union[DecodedMessage, FrameUpdate]]:
        """
        Yield decoded messages as they arrive. Blocks until interrupted.

        :param include_frames: If True, also yield :class:`FrameUpdate` objects
                               for in-progress multi-frame GFSK8 messages.
        :param timeout:        Stop after this many seconds of silence (None = forever).

        Example::

            with JF8ClientSync() as client:
                for msg in client.messages():
                    print(f"{msg.from_call}: {msg.body}")
        """
        q: queue.Queue = queue.Queue()

        def on_decoded(msg: DecodedMessage) -> None:
            q.put(msg)

        def on_frame(frame: FrameUpdate) -> None:
            q.put(frame)

        self._async.on("message.decoded", on_decoded)
        if include_frames:
            self._async.on("message.frame", on_frame)

        try:
            while True:
                try:
                    yield q.get(timeout=timeout)
                except queue.Empty:
                    return
        finally:
            self._async.off("message.decoded", on_decoded)
            if include_frames:
                self._async.off("message.frame", on_frame)
