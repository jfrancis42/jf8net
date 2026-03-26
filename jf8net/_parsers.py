"""
jf8net._parsers — Convert raw API dicts to typed model objects.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from ._models import (
    DecodedMessage, FrameUpdate, Status, Config,
    RadioStatus, TxFrame, AudioDevices, Spectrum,
)


def _utc(iso: str) -> datetime:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(tz=timezone.utc)


def parse_decoded_message(d: dict) -> DecodedMessage:
    return DecodedMessage(
        time=_utc(d.get("utc_iso", "")),
        freq_hz=float(d.get("freq_hz", 0)),
        snr_db=int(d.get("snr_db", 0)),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        from_call=str(d.get("from", "")),
        to=str(d.get("to", "")),
        body=str(d.get("body", "")),
        raw=str(d.get("raw", "")),
        type=int(d.get("type", 0)),
        type_name=str(d.get("type_name", "")),
    )


def parse_frame_update(d: dict) -> FrameUpdate:
    return FrameUpdate(
        time=_utc(d.get("utc_iso", "")),
        freq_hz=float(d.get("freq_hz", 0)),
        snr_db=int(d.get("snr_db", 0)),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        frame_type=int(d.get("frame_type", 0)),
        frame_text=str(d.get("frame_text", "")),
        assembled_text=str(d.get("assembled_text", "")),
        is_complete=bool(d.get("is_complete", False)),
    )


def parse_status(d: dict) -> Status:
    return Status(
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        submode=int(d.get("submode", 0)),
        submode_name=str(d.get("submode_name", "")),
        frequency_khz=float(d.get("frequency_khz", 0)),
        tx_freq_hz=float(d.get("tx_freq_hz", 0)),
        transmitting=bool(d.get("transmitting", False)),
        audio_running=bool(d.get("audio_running", False)),
        radio_connected=bool(d.get("radio_connected", False)),
        radio_freq_khz=float(d.get("radio_freq_khz", 0)),
        radio_mode=str(d.get("radio_mode", "")),
        tx_queue_size=int(d.get("tx_queue_size", 0)),
        heartbeat_enabled=bool(d.get("heartbeat_enabled", False)),
        heartbeat_interval_periods=int(d.get("heartbeat_interval_periods", 4)),
        auto_reply=bool(d.get("auto_reply", False)),
        ws_port=int(d.get("ws_port", 2102)),
        ws_clients=int(d.get("ws_clients", 0)),
    )


def parse_config(d: dict) -> Config:
    return Config(
        callsign=str(d.get("callsign", "")),
        grid=str(d.get("grid", "")),
        audio_input_name=str(d.get("audioInputName", "")),
        audio_output_name=str(d.get("audioOutputName", "")),
        modem_type=int(d.get("modemType", 0)),
        submode=int(d.get("submode", 0)),
        frequency_khz=float(d.get("frequencyKhz", 0)),
        tx_freq_hz=float(d.get("txFreqHz", 0)),
        tx_power_pct=int(d.get("txPowerPct", 50)),
        heartbeat_enabled=bool(d.get("heartbeatEnabled", False)),
        heartbeat_interval_periods=int(d.get("heartbeatIntervalPeriods", 4)),
        auto_reply=bool(d.get("autoReply", False)),
        station_info=str(d.get("stationInfo", "")),
        station_status=str(d.get("stationStatus", "")),
        cq_message=str(d.get("cqMessage", "")),
        dist_miles=bool(d.get("distMiles", False)),
        auto_atu=bool(d.get("autoAtu", False)),
        psk_reporter_enabled=bool(d.get("pskReporterEnabled", True)),
        rig_model=int(d.get("rigModel", 1)),
        rig_port=str(d.get("rigPort", "")),
        rig_baud=int(d.get("rigBaud", 9600)),
        rig_data_bits=int(d.get("rigDataBits", 8)),
        rig_stop_bits=int(d.get("rigStopBits", 1)),
        rig_parity=int(d.get("rigParity", 0)),
        rig_handshake=int(d.get("rigHandshake", 0)),
        rig_dtr_state=int(d.get("rigDtrState", 2)),
        rig_rts_state=int(d.get("rigRtsState", 2)),
        ptt_type=int(d.get("pttType", 0)),
        ws_enabled=bool(d.get("wsEnabled", True)),
        ws_port=int(d.get("wsPort", 2102)),
    )


def parse_radio_status(d: dict) -> RadioStatus:
    return RadioStatus(
        connected=bool(d.get("connected", False)),
        freq_khz=float(d.get("freq_khz", 0)),
        mode=str(d.get("mode", "")),
        rig_model=int(d.get("rig_model", 1)),
        port=str(d.get("port", "")),
        baud=int(d.get("baud", 9600)),
        data_bits=int(d.get("data_bits", 8)),
        stop_bits=int(d.get("stop_bits", 1)),
        parity=int(d.get("parity", 0)),
        handshake=int(d.get("handshake", 0)),
        dtr_state=int(d.get("dtr_state", 2)),
        rts_state=int(d.get("rts_state", 2)),
        ptt_type=int(d.get("ptt_type", 0)),
    )


def parse_tx_frame(d: dict) -> TxFrame:
    return TxFrame(
        payload=str(d.get("payload", "")),
        frame_type=int(d.get("frame_type", 0)),
        submode=int(d.get("submode", 0)),
    )


def parse_spectrum(d: dict) -> Spectrum:
    return Spectrum(
        bins=[float(v) for v in d.get("bins", [])],
        bin_count=int(d.get("bin_count", 0)),
        hz_per_bin=float(d.get("hz_per_bin", 0)),
        sample_rate=float(d.get("sample_rate", 12000)),
    )


# ── Config set: python snake_case kwargs → API camelCase ─────────────────────

_SNAKE_TO_CAMEL = {
    "callsign":                   "callsign",
    "grid":                       "grid",
    "audio_input_name":           "audioInputName",
    "audio_output_name":          "audioOutputName",
    "modem_type":                 "modemType",
    "submode":                    "submode",
    "frequency_khz":              "frequencyKhz",
    "tx_freq_hz":                 "txFreqHz",
    "tx_power_pct":               "txPowerPct",
    "heartbeat_enabled":          "heartbeatEnabled",
    "heartbeat_interval_periods": "heartbeatIntervalPeriods",
    "auto_reply":                 "autoReply",
    "station_info":               "stationInfo",
    "station_status":             "stationStatus",
    "cq_message":                 "cqMessage",
    "dist_miles":                 "distMiles",
    "auto_atu":                   "autoAtu",
    "psk_reporter_enabled":       "pskReporterEnabled",
    "rig_model":                  "rigModel",
    "rig_port":                   "rigPort",
    "rig_baud":                   "rigBaud",
    "rig_data_bits":              "rigDataBits",
    "rig_stop_bits":              "rigStopBits",
    "rig_parity":                 "rigParity",
    "rig_handshake":              "rigHandshake",
    "rig_dtr_state":              "rigDtrState",
    "rig_rts_state":              "rigRtsState",
    "ptt_type":                   "pttType",
    "ws_enabled":                 "wsEnabled",
    "ws_port":                    "wsPort",
}


def config_kwargs_to_api(kwargs: dict) -> dict:
    """Convert set_config() keyword arguments to API field names."""
    result = {}
    for k, v in kwargs.items():
        api_key = _SNAKE_TO_CAMEL.get(k)
        if api_key is None:
            # Also accept camelCase keys directly
            if k in _SNAKE_TO_CAMEL.values():
                api_key = k
            else:
                raise ValueError(
                    f"Unknown config field: {k!r}. "
                    f"Valid fields: {sorted(_SNAKE_TO_CAMEL)}"
                )
        result[api_key] = v
    return result
