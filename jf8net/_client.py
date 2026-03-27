"""
jf8net._client — Async WebSocket client for the JF8Call API.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Union

import websockets
import websockets.exceptions

from ._models import (
    AudioDevices, BandEntry, Config, DecodedMessage, FrameUpdate,
    InboxMessage, QsoEntry, RadioStatus, SolarData, Spectrum, Status, TxFrame,
    VersionInfo,
)
from ._parsers import (
    config_kwargs_to_api,
    parse_band_entry, parse_config, parse_decoded_message, parse_frame_update,
    parse_inbox_message, parse_qso_entry, parse_radio_status,
    parse_solar_data, parse_spectrum, parse_status, parse_tx_frame,
    parse_version_info,
)

logger = logging.getLogger(__name__)

Handler = Callable[[Any], Any]   # sync or async; receives the typed model object


class JF8Error(Exception):
    """Raised when the JF8Call API returns ok=false."""


class ConnectionError(JF8Error):
    """Raised when the WebSocket connection fails or is lost."""


class JF8Client:
    """
    Async WebSocket client for JF8Call.

    Typical usage::

        async with JF8Client() as client:
            status = await client.get_status()
            print(status)

            @client.on_message
            async def handle(msg: DecodedMessage):
                print(msg)

            await client.run_forever()

    All public methods are coroutines and must be awaited.
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
        self._host = host
        self._port = port
        self._auto_reconnect = auto_reconnect
        self._reconnect_delay = reconnect_delay
        self._cmd_timeout = cmd_timeout

        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._running = False

        # Pending command futures: id → Future[dict]
        self._pending: Dict[str, asyncio.Future] = {}

        # Event handlers: event_name → [handler, ...]
        # Special key "*" receives every event.
        self._handlers: Dict[str, List[Handler]] = {}

        # Cached status (updated from every "status" event)
        self._status: Optional[Status] = None

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self) -> None:
        """Open the WebSocket connection and start the receive pump."""
        uri = f"ws://{self._host}:{self._port}"
        try:
            self._ws = await websockets.connect(uri)
        except Exception as e:
            raise ConnectionError(f"Cannot connect to JF8Call at {uri}: {e}") from e

        # Drain hello + initial status push
        try:
            await self._ws.recv()  # hello
            raw = await self._ws.recv()  # status event
            obj = json.loads(raw)
            if obj.get("event") == "status":
                self._status = parse_status(obj.get("data", {}))
        except Exception:
            pass  # Not fatal; receive loop will catch future events

        self._running = True
        self._recv_task = asyncio.create_task(self._recv_loop(), name="jf8net-recv")
        logger.debug("Connected to JF8Call at %s", uri)

    async def disconnect(self) -> None:
        """Close the connection and stop the receive pump."""
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.debug("Disconnected from JF8Call")

    async def __aenter__(self) -> "JF8Client":
        await self.connect()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.disconnect()

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def cached_status(self) -> Optional[Status]:
        """Most recent status received (updated every second from the status event)."""
        return self._status

    # ── Receive pump ─────────────────────────────────────────────────────────

    async def _recv_loop(self) -> None:
        while self._running:
            try:
                raw = await self._ws.recv()
                msg = json.loads(raw)
                await self._dispatch(msg)
            except websockets.exceptions.ConnectionClosed:
                if not self._running:
                    break
                logger.warning("JF8Call connection closed")
                if self._auto_reconnect:
                    await self._reconnect()
                else:
                    break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Receive error: %s", e)

    async def _reconnect(self) -> None:
        self._ws = None
        while self._running:
            await asyncio.sleep(self._reconnect_delay)
            logger.info("Reconnecting to JF8Call…")
            try:
                uri = f"ws://{self._host}:{self._port}"
                self._ws = await websockets.connect(uri)
                await self._ws.recv()  # hello
                await self._ws.recv()  # status
                logger.info("Reconnected")
                return
            except Exception as e:
                logger.warning("Reconnect failed: %s", e)

    async def _dispatch(self, msg: dict) -> None:
        msg_type = msg.get("type")

        if msg_type == "reply":
            msg_id = msg.get("id")
            fut = self._pending.get(msg_id)
            if fut and not fut.done():
                fut.set_result(msg)
            return

        if msg_type != "event":
            return

        event = msg.get("event", "")
        raw_data = msg.get("data", {})

        # Update cached status
        if event == "status":
            self._status = parse_status(raw_data)

        # Convert raw data to typed model for well-known events
        typed: Any = raw_data
        if event == "message.decoded":
            typed = parse_decoded_message(raw_data)
        elif event == "message.frame":
            typed = parse_frame_update(raw_data)
        elif event == "status":
            typed = self._status
        elif event == "config.changed":
            # config.changed uses snake_case keys; pass raw dict
            typed = raw_data

        # Dispatch to registered handlers
        for handler in self._handlers.get(event, []) + self._handlers.get("*", []):
            try:
                result = handler(typed)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                logger.warning("Handler error for event %r: %s", event, e)

    # ── Command transport ─────────────────────────────────────────────────────

    async def _cmd(self, cmd: str, data: Optional[dict] = None) -> dict:
        if not self.connected:
            raise ConnectionError("Not connected to JF8Call")
        cmd_id = str(uuid.uuid4())[:8]
        msg: dict = {"type": "cmd", "id": cmd_id, "cmd": cmd}
        if data:
            msg["data"] = data
        loop = asyncio.get_event_loop()
        fut: asyncio.Future = loop.create_future()
        self._pending[cmd_id] = fut
        try:
            await self._ws.send(json.dumps(msg))
            reply = await asyncio.wait_for(asyncio.shield(fut), timeout=self._cmd_timeout)
        except asyncio.TimeoutError:
            raise JF8Error(f"Command {cmd!r} timed out after {self._cmd_timeout}s") from None
        finally:
            self._pending.pop(cmd_id, None)
        if not reply.get("ok"):
            raise JF8Error(reply.get("error", "unknown error"))
        return reply.get("data") or {}

    # ── Event handler registration ────────────────────────────────────────────

    def on(self, event: str, handler: Optional[Handler] = None) -> Any:
        """
        Register a handler for a named event. Can be used as a decorator.

        The handler receives a typed model object for well-known events:
        - ``message.decoded`` → :class:`DecodedMessage`
        - ``message.frame``   → :class:`FrameUpdate`
        - ``status``          → :class:`Status`
        - ``spectrum``        → raw dict (see :meth:`on_spectrum`)
        - ``"*"``             → any event (raw typed or dict)

        The handler may be a plain function or a coroutine function.

        Example::

            @client.on("message.decoded")
            async def handler(msg: DecodedMessage):
                print(msg)

            # Or with an explicit callsign filter:
            @client.on("message.decoded")
            def only_w4abc(msg: DecodedMessage):
                if msg.from_call == "W4ABC":
                    print(msg)
        """
        def decorator(fn: Handler) -> Handler:
            self._handlers.setdefault(event, []).append(fn)
            return fn
        if handler is not None:
            return decorator(handler)
        return decorator

    def off(self, event: str, handler: Handler) -> None:
        """Remove a previously registered handler."""
        handlers = self._handlers.get(event, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    # Convenience decorators for the most common events
    def on_message(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("message.decoded")``."""
        return self.on("message.decoded", fn)

    def on_frame(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("message.frame")``."""
        return self.on("message.frame", fn)

    def on_status(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("status")``."""
        return self.on("status", fn)

    def on_spectrum(self, fn: Handler) -> Handler:
        """
        Register a handler that receives a typed :class:`Spectrum` object.

        The raw ``spectrum`` event carries a dict; this wrapper parses it first.
        """
        def wrapper(raw: dict) -> Any:
            result = fn(parse_spectrum(raw))
            return result
        self._handlers.setdefault("spectrum", []).append(wrapper)
        return fn

    def on_tx_started(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("tx.started")``."""
        return self.on("tx.started", fn)

    def on_tx_finished(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("tx.finished")``."""
        return self.on("tx.finished", fn)

    def on_radio_connected(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("radio.connected")``."""
        return self.on("radio.connected", fn)

    def on_radio_disconnected(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("radio.disconnected")``."""
        return self.on("radio.disconnected", fn)

    def on_config_changed(self, fn: Handler) -> Handler:
        """Shorthand for ``@client.on("config.changed")``."""
        return self.on("config.changed", fn)

    # ── Run forever ───────────────────────────────────────────────────────────

    async def run_forever(self) -> None:
        """
        Block until the connection is closed.

        Use this at the end of your event-driven program to keep it running::

            async with JF8Client() as client:
                @client.on_message
                async def handle(msg):
                    print(msg)
                await client.run_forever()
        """
        if self._recv_task:
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self) -> Status:
        """Fetch the current application status snapshot."""
        d = await self._cmd("status.get")
        self._status = parse_status(d)
        return self._status

    # ── Config ────────────────────────────────────────────────────────────────

    async def get_config(self) -> Config:
        """Fetch the full persistent configuration."""
        d = await self._cmd("config.get")
        return parse_config(d)

    async def set_config(self, **kwargs) -> Config:
        """
        Update one or more configuration fields.

        Use Python snake_case keyword arguments matching the :class:`Config`
        field names::

            await client.set_config(
                callsign="W5XYZ",
                grid="DM79AA",
                auto_atu=True,
                psk_reporter_enabled=True,
            )

        Returns the full updated :class:`Config`.
        """
        data = config_kwargs_to_api(kwargs)
        d = await self._cmd("config.set", data)
        return parse_config(d)

    # ── Audio ─────────────────────────────────────────────────────────────────

    async def get_audio_devices(self) -> AudioDevices:
        """List available PortAudio input and output device names."""
        d = await self._cmd("audio.devices")
        return AudioDevices(
            inputs=list(d.get("input", [])),
            outputs=list(d.get("output", [])),
        )

    async def restart_audio(self) -> None:
        """Stop and restart PortAudio with the current device configuration."""
        await self._cmd("audio.restart")

    # ── Radio ─────────────────────────────────────────────────────────────────

    async def get_radio(self) -> RadioStatus:
        """Fetch rig connection state and serial configuration."""
        d = await self._cmd("radio.get")
        return parse_radio_status(d)

    async def connect_radio(
        self,
        *,
        rig_model: Optional[int] = None,
        port: Optional[str] = None,
        baud: Optional[int] = None,
        ptt_type: Optional[int] = None,
        data_bits: Optional[int] = None,
        stop_bits: Optional[int] = None,
        parity: Optional[int] = None,
        handshake: Optional[int] = None,
        dtr_state: Optional[int] = None,
        rts_state: Optional[int] = None,
    ) -> None:
        """
        Connect to the rig via Hamlib. Omit any field to use the saved value.

        Common Hamlib model numbers:
        - 3073 = IC-7300
        - 3085 = IC-7610
        - 2014 = TS-2000
        - 1035 = FT-991A

        PTT type: 0=VOX, 1=CAT, 2=DTR, 3=RTS
        """
        data: dict = {}
        if rig_model  is not None: data["rig_model"]  = rig_model
        if port       is not None: data["port"]        = port
        if baud       is not None: data["baud"]        = baud
        if ptt_type   is not None: data["ptt_type"]    = ptt_type
        if data_bits  is not None: data["data_bits"]   = data_bits
        if stop_bits  is not None: data["stop_bits"]   = stop_bits
        if parity     is not None: data["parity"]      = parity
        if handshake  is not None: data["handshake"]   = handshake
        if dtr_state  is not None: data["dtr_state"]   = dtr_state
        if rts_state  is not None: data["rts_state"]   = rts_state
        await self._cmd("radio.connect", data or None)

    async def disconnect_radio(self) -> None:
        """Disconnect from the rig."""
        await self._cmd("radio.disconnect")

    async def set_frequency(self, khz: float) -> float:
        """
        Set the VFO frequency in kHz via Hamlib CAT.

        Requires a connected rig. If ``auto_atu`` is enabled in config,
        the ATU tune cycle is triggered automatically after the frequency change.

        Returns the frequency that was set.
        """
        d = await self._cmd("radio.frequency.set", {"freq_khz": khz})
        return float(d.get("freq_khz", khz))

    async def set_ptt(self, on: bool) -> None:
        """
        Direct PTT control.

        .. warning::
            The TX queue manages PTT automatically during normal operation.
            Use this only for special cases; leaving PTT keyed with no audio
            transmits noise.
        """
        await self._cmd("radio.ptt.set", {"ptt": on})

    async def tune(self) -> None:
        """
        Trigger the internal ATU tune cycle via Hamlib ``RIG_OP_TUNE`` (no RF).

        Requires a connected rig that supports ``RIG_OP_TUNE``. Most modern
        Icom rigs support this. For rigs that don't, briefly key PTT instead.

        This is called automatically by :meth:`set_frequency` when ``auto_atu``
        is enabled in the configuration.
        """
        await self._cmd("radio.tune")

    # ── Messages ──────────────────────────────────────────────────────────────

    async def get_messages(
        self, offset: int = 0, limit: int = 100
    ) -> List[DecodedMessage]:
        """
        Fetch decoded messages from the log (newest first).

        :param offset: Start position in the log.
        :param limit:  Maximum messages to return (server cap: 1000).
        """
        d = await self._cmd("messages.get", {"offset": offset, "limit": limit})
        return [parse_decoded_message(m) for m in d.get("messages", [])]

    async def clear_messages(self) -> None:
        """Clear the decoded message log."""
        await self._cmd("messages.clear")

    # ── Spectrum ──────────────────────────────────────────────────────────────

    async def get_spectrum(self) -> Spectrum:
        """Fetch the latest FFT spectrum snapshot."""
        d = await self._cmd("spectrum.get")
        return parse_spectrum(d)

    # ── TX ────────────────────────────────────────────────────────────────────

    async def send(
        self,
        text: str,
        submode: Optional[Union[str, int]] = None,
    ) -> int:
        """
        Encode and queue a message for transmission.

        :param text:    Message text (e.g. ``"W4ABC DE W5XYZ HELLO 73"``).
        :param submode: Optional submode override. For JS8: ``"normal"``,
                        ``"fast"``, ``"turbo"``, ``"slow"``, ``"ultra"``
                        or numeric 0–4. If omitted, uses the active submode.
        :returns:       Total frames now in the TX queue.
        """
        data: dict = {"text": text}
        if submode is not None:
            data["submode"] = str(submode)
        d = await self._cmd("tx.send", data)
        return int(d.get("queue_size", 0))

    async def send_heartbeat(self) -> int:
        """Queue a ``CALLSIGN @HB`` heartbeat. Returns new queue size."""
        d = await self._cmd("tx.hb")
        return int(d.get("queue_size", 0))

    async def send_snr_query(self, to: str) -> int:
        """Queue a ``TO MYCALL @SNR?`` request. Returns new queue size."""
        d = await self._cmd("tx.snr", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_info_query(self, to: str) -> int:
        """Queue a ``TO MYCALL @INFO?`` request. Returns new queue size."""
        d = await self._cmd("tx.info", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_status_query(self, to: str) -> int:
        """Queue a ``TO MYCALL @?`` status request. Returns new queue size."""
        d = await self._cmd("tx.status", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def get_tx_queue(self) -> List[TxFrame]:
        """Fetch the current TX frame queue."""
        d = await self._cmd("tx.queue.get")
        return [parse_tx_frame(f) for f in d.get("queue", [])]

    async def clear_tx_queue(self) -> None:
        """Remove all pending TX frames (does not abort in-progress TX)."""
        await self._cmd("tx.queue.clear")

    # ── Convenience helpers ───────────────────────────────────────────────────

    async def wait_for_tx(self, timeout: Optional[float] = 120.0) -> None:
        """
        Block until the current TX queue is empty and TX has finished.

        Useful after :meth:`send` when you need to know transmission is done::

            await client.send("W4ABC HELLO")
            await client.wait_for_tx()
            print("TX complete")

        :raises asyncio.TimeoutError: if TX does not complete within *timeout* seconds.
        """
        done = asyncio.Event()

        def on_finished(_: Any) -> None:
            done.set()

        self.on("tx.finished", on_finished)
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        finally:
            self.off("tx.finished", on_finished)

    async def send_and_wait(
        self, text: str, submode: Optional[Union[str, int]] = None,
        timeout: float = 120.0
    ) -> None:
        """
        Send a message and block until TX is complete.

        Equivalent to ``await client.send(text); await client.wait_for_tx()``.
        """
        await self.send(text, submode=submode)
        await self.wait_for_tx(timeout=timeout)

    # ── TX query helpers ──────────────────────────────────────────────────────

    async def send_grid_query(self, to: str) -> int:
        """Queue a ``TO MYCALL @GRID?`` request. Returns new queue size."""
        d = await self._cmd("tx.grid", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    async def send_hearing_query(self, to: str) -> int:
        """Queue a ``TO MYCALL @HEARING?`` request. Returns new queue size."""
        d = await self._cmd("tx.hearing", {"to": to.upper()})
        return int(d.get("queue_size", 0))

    # ── Band list ─────────────────────────────────────────────────────────────

    async def get_bands(self) -> List[BandEntry]:
        """Return the user-editable band/frequency list."""
        d = await self._cmd("bands.get")
        return [parse_band_entry(b) for b in d.get("bands", [])]

    async def set_bands(self, bands: List[BandEntry]) -> int:
        """Replace the band list. Pass an empty list to reset to factory defaults."""
        payload = [{"name": b.name, "freqKhz": b.freq_khz, "txFreqHz": b.tx_freq_hz}
                   for b in bands]
        d = await self._cmd("bands.set", {"bands": payload})
        return int(d.get("count", 0))

    # ── Solar data ────────────────────────────────────────────────────────────

    async def get_solar(self) -> SolarData:
        """Return the latest NOAA solar indices."""
        d = await self._cmd("solar.get")
        return parse_solar_data(d)

    # ── Version ───────────────────────────────────────────────────────────────

    async def get_version(self) -> VersionInfo:
        """Return JF8Call version information.

        The returned :class:`VersionInfo` includes the full version string,
        major/minor/patch integers, and a release label
        (``"ALPHA"``, ``"BETA"``, ``"RC"``, or ``"RELEASE"``).
        """
        d = await self._cmd("version.get")
        return parse_version_info(d)

    # ── QSO log ───────────────────────────────────────────────────────────────

    async def get_qso_log(self, offset: int = 0, limit: int = 100) -> List[QsoEntry]:
        """Return logged QSOs."""
        d = await self._cmd("qso.log.get", {"offset": offset, "limit": limit})
        return [parse_qso_entry(q) for q in d.get("qsos", [])]

    async def export_adif(self) -> str:
        """Return the QSO log as an ADIF string."""
        d = await self._cmd("qso.log.adif")
        return str(d.get("adif", ""))

    # ── Inbox ─────────────────────────────────────────────────────────────────

    async def get_inbox(self, for_call: str = "") -> List[InboxMessage]:
        """Return inbox messages. Pass *for_call* to filter by recipient."""
        data: dict = {}
        if for_call:
            data["for"] = for_call.upper()
        d = await self._cmd("inbox.get", data if data else None)
        return [parse_inbox_message(m) for m in d.get("messages", [])]

    async def inbox_send(self, to: str, body: str) -> bool:
        """Send a message to *to* immediately via the TX queue."""
        d = await self._cmd("inbox.send", {"to": to.upper(), "body": body})
        return bool(d.get("queued", False))

    async def inbox_store(self, to: str, body: str) -> str:
        """Store a message for *to* to retrieve later. Returns the message ID."""
        d = await self._cmd("inbox.store", {"to": to.upper(), "body": body})
        return str(d.get("id", ""))

    async def inbox_delete(self, msg_id: int) -> None:
        """Delete an inbox message by ID."""
        await self._cmd("inbox.delete", {"id": msg_id})

    async def inbox_mark_read(self, msg_id: int) -> None:
        """Mark an inbox message as read."""
        await self._cmd("inbox.mark_read", {"id": msg_id})
