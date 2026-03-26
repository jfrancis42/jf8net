# jf8net

Python library for the [JF8Call](https://github.com/jfrancis42/jf8call) WebSocket API.

jf8net provides complete coverage of JF8Call's WebSocket API with asyncio
and typed dataclasses.

---

## Installation

```bash
pip install websockets
pip install -e /path/to/jf8net   # editable install from source
```

**Requirements:** Python 3.10+, `websockets` 11+.

JF8Call must be running with the WebSocket API enabled (the default) on
`ws://localhost:2102`.

---

## Quick Start

### Async (recommended)

```python
import asyncio
from jf8net import JF8Client, DecodedMessage

async def main():
    async with JF8Client() as client:
        # Print current status
        print(await client.get_status())

        # Receive messages in real time
        @client.on_message
        async def handle(msg: DecodedMessage):
            print(f"{msg.from_call} → {msg.to}: {msg.body}")

        await client.run_forever()

asyncio.run(main())
```

### Sync (for scripts)

```python
from jf8net.sync import JF8ClientSync

with JF8ClientSync() as client:
    print(client.get_status())
    for msg in client.messages():   # blocks, yields DecodedMessage
        print(msg)
```

---

## API Reference

### `JF8Client` — Async Client

```python
from jf8net import JF8Client
client = JF8Client(host="localhost", port=2102,
                   auto_reconnect=True, reconnect_delay=5.0, cmd_timeout=10.0)
```

Use as an async context manager (`async with`) or call `await client.connect()`
and `await client.disconnect()` manually.

#### Status & Configuration

```python
status: Status = await client.get_status()
config: Config = await client.get_config()
config: Config = await client.set_config(**kwargs)
```

`set_config` accepts any subset of `Config` fields as keyword arguments
using Python snake_case names:

```python
await client.set_config(
    callsign="W5XYZ",
    grid="DM79AA",
    station_info="QTH: Austin TX  PWR: 100W  ANT: 80m Dipole",
    station_status="Available for sked",
    cq_message="CQ CQ DE W5XYZ",
    heartbeat_enabled=True,
    heartbeat_interval_periods=4,
    auto_reply=True,
    auto_atu=True,
    psk_reporter_enabled=True,
    dist_miles=False,
)
```

#### Audio

```python
devices: AudioDevices = await client.get_audio_devices()
# devices.inputs  → list[str]
# devices.outputs → list[str]

await client.restart_audio()
```

#### Radio (Hamlib)

```python
radio: RadioStatus = await client.get_radio()

await client.connect_radio(
    rig_model=3073,          # IC-7300
    port="/dev/ttyUSB0",
    baud=19200,
    ptt_type=1,              # 0=VOX 1=CAT 2=DTR 3=RTS
    # data_bits, stop_bits, parity, handshake, dtr_state, rts_state also available
)
await client.disconnect_radio()

freq_khz: float = await client.set_frequency(14078.0)
await client.tune()          # RIG_OP_TUNE — no RF, just CAT ATU command
await client.set_ptt(True)   # direct PTT (use with care)
```

When `auto_atu=True` is set in config, `set_frequency()` automatically
triggers `tune()` after every successful frequency change.

#### Transmit

```python
queue_size: int = await client.send("W4ABC DE W5XYZ HELLO 73")
queue_size: int = await client.send("W4ABC QUICK", submode="fast")

await client.send_heartbeat()
await client.send_snr_query("W4ABC")
await client.send_info_query("W4ABC")
await client.send_status_query("W4ABC")

frames: list[TxFrame] = await client.get_tx_queue()
await client.clear_tx_queue()

# Send and block until TX completes
await client.send_and_wait("W4ABC DE W5XYZ 73", timeout=120)
```

Valid `submode` values for GFSK8: `"normal"` (or `0`), `"fast"` (`1`),
`"turbo"` (`2`), `"slow"` (`3`), `"ultra"` (`4`).

#### Messages & Spectrum

```python
messages: list[DecodedMessage] = await client.get_messages(offset=0, limit=100)
await client.clear_messages()

spectrum: Spectrum = await client.get_spectrum()
peak_hz = spectrum.peak_hz()
slice_db = spectrum.slice(500, 2500)   # bins between 500–2500 Hz
```

#### Waiting for TX

```python
await client.send("W4ABC HELLO")
await client.wait_for_tx(timeout=120)  # blocks until tx.finished event
```

---

### Event Handlers

Register handlers using decorators or direct calls. Handlers may be plain
functions or coroutines.

```python
# Decorator style
@client.on_message
async def handle_decoded(msg: DecodedMessage):
    print(msg)

# Direct registration
def my_handler(msg): print(msg)
client.on("message.decoded", my_handler)
client.off("message.decoded", my_handler)
```

#### Available Events

| Event | Convenience method | Typed argument |
|-------|-------------------|----------------|
| `message.decoded` | `on_message` | `DecodedMessage` |
| `message.frame` | `on_frame` | `FrameUpdate` |
| `status` | `on_status` | `Status` |
| `spectrum` | `on_spectrum` | `Spectrum` |
| `tx.started` | `on_tx_started` | `None` |
| `tx.finished` | `on_tx_finished` | `None` |
| `radio.connected` | `on_radio_connected` | `dict` |
| `radio.disconnected` | `on_radio_disconnected` | `None` |
| `config.changed` | `on_config_changed` | `dict` |
| `"*"` | — | any (typed or dict) |

#### `message.frame` — Partial GFSK8 Frames

For multi-frame GFSK8 messages (e.g. a long Normal-mode message spanning
several 15-second periods), JF8Call emits a `message.frame` event for each
frame as it arrives. This lets you display in-progress messages in real time
rather than waiting for the complete assembled message.

```python
@client.on_frame
async def on_partial(frame: FrameUpdate):
    print(f"[{frame.frame_type_name.upper()}] +{frame.freq_hz:.0f}Hz  {frame.assembled_text!r}")
    # frame.assembled_text grows with each frame
    # frame.freq_key = round(frame.freq_hz / 10) — use this to correlate frames

@client.on_message
async def on_complete(msg: DecodedMessage):
    # Fires once after the last frame; freq_key is the same as the frame events
    print(f"COMPLETE: {msg}")
```

`message.frame` is only emitted for first and middle frames of multi-frame
GFSK8 messages. Single-frame messages and streaming modem (PSK/Olivia/Codec2)
chunks go directly to `message.decoded`.

---

### Data Classes

#### `DecodedMessage`

```python
msg.time           # datetime (UTC)
msg.freq_hz        # float — audio frequency in Hz
msg.snr_db         # int — signal-to-noise ratio
msg.submode        # int
msg.submode_name   # str (e.g. "Normal")
msg.from_call      # str — sender callsign
msg.to             # str — destination callsign (empty = broadcast)
msg.body           # str — parsed message body
msg.raw            # str — full raw text
msg.type           # int — MessageType constant
msg.type_name      # str (e.g. "DirectedMessage")
msg.freq_key       # int — round(freq_hz/10), for frame correlation
msg.is_directed    # bool
msg.is_heartbeat   # bool
```

#### `FrameUpdate`

```python
frame.time           # datetime (UTC)
frame.freq_hz        # float
frame.snr_db         # int
frame.submode        # int
frame.submode_name   # str
frame.frame_type     # int — FrameType constant (0=middle, 1=first)
frame.frame_type_name # str ("first", "middle")
frame.frame_text     # str — raw text of just this frame
frame.assembled_text # str — everything accumulated so far
frame.is_complete    # bool — always False for this event
frame.freq_key       # int — round(freq_hz/10)
```

#### `Status`

```python
status.callsign                  # str
status.grid                      # str
status.submode                   # int
status.submode_name              # str
status.frequency_khz             # float
status.tx_freq_hz                # float
status.transmitting              # bool
status.audio_running             # bool
status.radio_connected           # bool
status.radio_freq_khz            # float
status.radio_mode                # str
status.tx_queue_size             # int
status.heartbeat_enabled         # bool
status.heartbeat_interval_periods # int
status.auto_reply                # bool
status.ws_port                   # int
status.ws_clients                # int
```

#### `Config`

All `Status` fields plus:

```python
config.audio_input_name          # str
config.audio_output_name         # str
config.modem_type                # int (ModemType.GFSK8 etc.)
config.tx_power_pct              # int
config.station_info              # str
config.station_status            # str
config.cq_message                # str
config.dist_miles                # bool
config.auto_atu                  # bool
config.psk_reporter_enabled      # bool
config.rig_model                 # int
config.rig_port                  # str
config.rig_baud                  # int
config.rig_data_bits             # int
config.rig_stop_bits             # int
config.rig_parity                # int
config.rig_handshake             # int
config.rig_dtr_state             # int
config.rig_rts_state             # int
config.ptt_type                  # int
config.ws_enabled                # bool
config.ws_port                   # int
```

#### Constants

```python
from jf8net import MessageType, FrameType, ModemType, PttType

MessageType.HEARTBEAT       # 1
MessageType.DIRECTED        # 2
MessageType.SNR_QUERY       # 3
MessageType.SNR_REPLY       # 4
MessageType.INFO_QUERY      # 5
MessageType.INFO_REPLY      # 6
MessageType.STATUS_QUERY    # 7
MessageType.STATUS_REPLY    # 8

FrameType.FIRST    # 1
FrameType.MIDDLE   # 0
FrameType.LAST     # 2
FrameType.SINGLE   # 3

ModemType.GFSK8    # 0 — GFSK8 (default)
ModemType.CODEC2   # 1
ModemType.OLIVIA   # 2
ModemType.PSK      # 3

PttType.VOX  # 0
PttType.CAT  # 1
PttType.DTR  # 2
PttType.RTS  # 3
```

---

### `JF8ClientSync` — Synchronous Client

```python
from jf8net.sync import JF8ClientSync

with JF8ClientSync(host="localhost", port=2102) as client:
    status = client.get_status()
    config = client.get_config()
    config = client.set_config(callsign="W5XYZ")

    devices = client.get_audio_devices()
    radio   = client.get_radio()

    client.set_frequency(14078.0)
    client.tune()

    client.send("W4ABC HELLO")
    client.wait_for_tx()

    # Generator — blocks, yields DecodedMessage
    for msg in client.messages():
        print(msg)

    # Generator — also yields FrameUpdate for partial frames
    for item in client.messages(include_frames=True):
        print(item)

    # With a timeout (raises StopIteration after N seconds of silence)
    for msg in client.messages(timeout=60.0):
        print(msg)
```

Event handlers in sync mode are plain functions:

```python
with JF8ClientSync() as client:
    @client.on_message
    def handle(msg):
        print(msg)

    @client.on_frame
    def on_partial(frame):
        print(frame.assembled_text)

    client.run_forever()   # blocks until disconnect
```

---

## Examples

| File | Description |
|------|-------------|
| `examples/01_basic_status.py` | Status, config, audio devices, recent messages |
| `examples/02_receive_messages.py` | Stream decoded messages with filters |
| `examples/03_send_message.py` | Send directed messages and wait for TX |
| `examples/04_frame_assembly.py` | Real-time multi-frame GFSK8 assembly display |
| `examples/05_radio_control.py` | Frequency changes, ATU tuning, rig connect |
| `examples/06_config_management.py` | Read/write all config fields |
| `examples/07_spectrum_monitor.py` | ASCII waterfall from live spectrum events |
| `examples/08_sync_usage.py` | All of the above using the sync wrapper |
| `examples/09_chat.py` | Interactive two-way terminal chat with a specific callsign |

Run any example with `--help` for its options, and `--host` to point at a
remote JF8Call instance.

---

## Recipes

### Auto-respond to directed messages

```python
async with JF8Client() as client:
    status = await client.get_status()
    my_call = status.callsign

    @client.on_message
    async def respond(msg: DecodedMessage):
        if msg.to == my_call and msg.body == "PING":
            await client.send(f"{msg.from_call} PONG")

    await client.run_forever()
```

### Log all decoded messages to a JSONL file

```python
import json
from datetime import datetime

async with JF8Client() as client:
    with open("rx.jsonl", "a") as f:
        @client.on_message
        def log(msg: DecodedMessage):
            f.write(json.dumps({
                "time": msg.time.isoformat(),
                "freq_hz": msg.freq_hz,
                "snr_db": msg.snr_db,
                "from": msg.from_call,
                "to": msg.to,
                "body": msg.body,
                "raw": msg.raw,
            }) + "\n")
            f.flush()
        await client.run_forever()
```

### Band-change macro with ATU

```python
JS8_BANDS = {20: 14078.0, 40: 7078.0, 80: 3578.0}

async def switch_band(client: JF8Client, meters: int) -> None:
    khz = JS8_BANDS[meters]
    await client.set_frequency(khz)
    # If auto_atu is off, trigger manually:
    cfg = await client.get_config()
    if not cfg.auto_atu:
        await client.tune()
    print(f"On {meters}m ({khz} kHz)")
```

### Monitor multiple JF8Call instances simultaneously

```python
import asyncio
from jf8net import JF8Client, DecodedMessage

STATIONS = [
    ("localhost", 2102, "greybox"),
    ("192.168.86.50", 2102, "shack2"),
]

async def watch(host, port, name):
    async with JF8Client(host=host, port=port) as client:
        @client.on_message
        def handle(msg: DecodedMessage):
            print(f"[{name}] {msg}")
        await client.run_forever()

async def main():
    await asyncio.gather(*[watch(*s) for s in STATIONS])

asyncio.run(main())
```

### Track per-station SNR over time

```python
from collections import defaultdict
spots = defaultdict(list)   # call → [snr, ...]

@client.on_message
def track_snr(msg: DecodedMessage):
    if msg.from_call:
        spots[msg.from_call].append(msg.snr_db)

# Later:
for call, readings in sorted(spots.items()):
    avg = sum(readings) / len(readings)
    print(f"{call}: {len(readings)} readings, avg SNR {avg:+.1f} dB")
```

---

## License

GPL-3.0-or-later (matching JF8Call's license).
