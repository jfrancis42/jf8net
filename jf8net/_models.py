"""
jf8net._models — Data classes for JF8Call API responses.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


# ── Message types ────────────────────────────────────────────────────────────

class MessageType:
    UNKNOWN           = 0
    HEARTBEAT         = 1
    DIRECTED          = 2
    SNR_QUERY         = 3
    SNR_REPLY         = 4
    INFO_QUERY        = 5
    INFO_REPLY        = 6
    STATUS_QUERY      = 7
    STATUS_REPLY      = 8
    COMPOUND_DIRECTED = 9

    _names = {
        0: "Unknown", 1: "Heartbeat", 2: "DirectedMessage",
        3: "SnrQuery", 4: "SnrReply", 5: "InfoQuery",
        6: "InfoReply", 7: "StatusQuery", 8: "StatusReply",
        9: "CompoundDirected",
    }

    @classmethod
    def name(cls, v: int) -> str:
        return cls._names.get(v, "Unknown")


# ── Frame types (Varicode::TransmissionType) ─────────────────────────────────

class FrameType:
    MIDDLE  = 0  # JS8Call   — middle of multi-frame
    FIRST   = 1  # JS8CallFirst
    LAST    = 2  # JS8CallLast
    SINGLE  = 3  # FrameDirected = First|Last

    _names = {0: "middle", 1: "first", 2: "last", 3: "single"}

    @classmethod
    def name(cls, v: int) -> str:
        return cls._names.get(v, str(v))


# ── Modem types ───────────────────────────────────────────────────────────────

class ModemType:
    GFSK8  = 0
    CODEC2 = 1
    OLIVIA = 2
    PSK    = 3

    _names = {0: "JS8/GFSK8", 1: "Codec2 DATAC", 2: "Olivia", 3: "PSK"}

    @classmethod
    def name(cls, v: int) -> str:
        return cls._names.get(v, str(v))


# ── PTT types ────────────────────────────────────────────────────────────────

class PttType:
    VOX = 0
    CAT = 1
    DTR = 2
    RTS = 3


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class DecodedMessage:
    """A fully assembled decoded message from JF8Call."""
    time: datetime
    freq_hz: float
    snr_db: int
    submode: int
    submode_name: str
    from_call: str
    to: str
    body: str
    raw: str
    type: int
    type_name: str

    @property
    def freq_key(self) -> int:
        """Frequency group key — round(freq_hz / 10). Used to correlate frames."""
        return round(self.freq_hz / 10)

    @property
    def is_directed(self) -> bool:
        return bool(self.to and self.to not in ("@ALL", ""))

    @property
    def is_heartbeat(self) -> bool:
        return self.type == MessageType.HEARTBEAT

    def __str__(self) -> str:
        dest = f" → {self.to}" if self.to else ""
        t = self.time.strftime("%H:%M:%S")
        return f"[{t}] +{self.freq_hz:.0f}Hz SNR{self.snr_db:+d}  {self.from_call}{dest}  {self.body}"


@dataclass
class FrameUpdate:
    """A single GFSK8 frame from a multi-frame in-progress message."""
    time: datetime
    freq_hz: float
    snr_db: int
    submode: int
    submode_name: str
    frame_type: int
    frame_text: str
    assembled_text: str
    is_complete: bool = False

    @property
    def freq_key(self) -> int:
        return round(self.freq_hz / 10)

    @property
    def frame_type_name(self) -> str:
        return FrameType.name(self.frame_type)

    def __str__(self) -> str:
        t = self.time.strftime("%H:%M:%S")
        return (f"[{t}] +{self.freq_hz:.0f}Hz SNR{self.snr_db:+d}"
                f"  [{self.frame_type_name.upper()}]  {self.assembled_text}")


@dataclass
class Status:
    """Live application state snapshot."""
    callsign: str
    grid: str
    submode: int
    submode_name: str
    frequency_khz: float
    tx_freq_hz: float
    transmitting: bool
    audio_running: bool
    radio_connected: bool
    radio_freq_khz: float
    radio_mode: str
    tx_queue_size: int
    heartbeat_enabled: bool
    heartbeat_interval_periods: int
    auto_reply: bool
    ws_port: int
    ws_clients: int

    def __str__(self) -> str:
        lines = [
            f"Callsign : {self.callsign or '(not set)'}  Grid: {self.grid or '(not set)'}",
            f"Submode  : {self.submode_name} ({self.submode})",
            f"Dial     : {self.frequency_khz} kHz   TX offset: {self.tx_freq_hz:.0f} Hz",
            f"TX       : {'TRANSMITTING' if self.transmitting else 'idle'}  "
            f"Audio: {'running' if self.audio_running else 'stopped'}",
            f"Radio    : {'connected' if self.radio_connected else 'not connected'}",
        ]
        if self.radio_connected:
            lines.append(f"  VFO    : {self.radio_freq_khz} kHz  {self.radio_mode}")
        lines += [
            f"TX queue : {self.tx_queue_size} frame(s)",
            f"Heartbeat: {'on' if self.heartbeat_enabled else 'off'}"
            f"  every {self.heartbeat_interval_periods} period(s)",
            f"Auto-reply: {'on' if self.auto_reply else 'off'}",
        ]
        return "\n".join(lines)


@dataclass
class Config:
    """Full persistent configuration."""
    callsign: str
    grid: str
    audio_input_name: str
    audio_output_name: str
    modem_type: int
    submode: int
    frequency_khz: float
    tx_freq_hz: float
    tx_power_pct: int
    heartbeat_enabled: bool
    heartbeat_interval_periods: int
    auto_reply: bool
    station_info: str
    station_status: str
    cq_message: str
    dist_miles: bool
    auto_atu: bool
    psk_reporter_enabled: bool
    rig_model: int
    rig_port: str
    rig_baud: int
    rig_data_bits: int
    rig_stop_bits: int
    rig_parity: int
    rig_handshake: int
    rig_dtr_state: int
    rig_rts_state: int
    ptt_type: int
    ws_enabled: bool
    ws_port: int


@dataclass
class RadioStatus:
    """Rig connection state and serial configuration."""
    connected: bool
    freq_khz: float
    mode: str
    rig_model: int
    port: str
    baud: int
    data_bits: int
    stop_bits: int
    parity: int
    handshake: int
    dtr_state: int
    rts_state: int
    ptt_type: int

    def __str__(self) -> str:
        ptt_names = {0: "VOX", 1: "CAT", 2: "DTR", 3: "RTS"}
        lines = [
            f"Connected : {'yes' if self.connected else 'no'}",
            f"Model     : {self.rig_model}",
            f"Port      : {self.port or '(not set)'}  {self.baud} baud",
            f"PTT       : {ptt_names.get(self.ptt_type, self.ptt_type)}",
        ]
        if self.connected:
            lines.insert(1, f"VFO       : {self.freq_khz} kHz  {self.mode}")
        return "\n".join(lines)


@dataclass
class TxFrame:
    """A single frame in the TX queue."""
    payload: str
    frame_type: int
    submode: int

    @property
    def frame_type_name(self) -> str:
        return FrameType.name(self.frame_type)


@dataclass
class AudioDevices:
    """Available PortAudio input and output device names."""
    inputs: List[str]
    outputs: List[str]


@dataclass
class Spectrum:
    """FFT spectrum snapshot."""
    bins: List[float]
    bin_count: int
    hz_per_bin: float
    sample_rate: float

    def peak_hz(self) -> float:
        """Frequency of the highest-power bin in Hz."""
        if not self.bins:
            return 0.0
        i = max(range(len(self.bins)), key=lambda j: self.bins[j])
        return i * self.hz_per_bin

    def peak_db(self) -> float:
        """Power of the highest bin in dBFS."""
        return max(self.bins) if self.bins else 0.0

    def slice(self, low_hz: float, high_hz: float) -> List[float]:
        """Return bins within a frequency range."""
        lo = max(0, int(low_hz / self.hz_per_bin))
        hi = min(len(self.bins), int(high_hz / self.hz_per_bin) + 1)
        return self.bins[lo:hi]
