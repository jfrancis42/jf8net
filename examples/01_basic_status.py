#!/usr/bin/env python3
"""
01_basic_status.py — Fetch and display current JF8Call status.

Run with:
    python3 examples/01_basic_status.py
    python3 examples/01_basic_status.py --host 192.168.86.173
"""
import argparse
import asyncio
from jf8net import JF8Client


async def main(host: str, port: int) -> None:
    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        print(status)
        print()

        config = await client.get_config()
        print(f"Station info   : {config.station_info or '(not set)'}")
        print(f"Station status : {config.station_status or '(not set)'}")
        print(f"CQ message     : {config.cq_message or '(not set)'}")
        print(f"Modem          : {config.modem_type} (0=JS8, 1=Codec2, 2=Olivia, 3=PSK)")
        print(f"PSKReporter    : {'enabled' if config.psk_reporter_enabled else 'disabled'}")
        print(f"Auto-ATU       : {'enabled' if config.auto_atu else 'disabled'}")
        print(f"Dist units     : {'miles' if config.dist_miles else 'km'}")

        devices = await client.get_audio_devices()
        print(f"\nAudio inputs  ({len(devices.inputs)}):")
        for d in devices.inputs:
            marker = " ← active" if d == config.audio_input_name else ""
            print(f"  {d}{marker}")
        print(f"Audio outputs ({len(devices.outputs)}):")
        for d in devices.outputs:
            marker = " ← active" if d == config.audio_output_name else ""
            print(f"  {d}{marker}")

        radio = await client.get_radio()
        print(f"\nRadio:")
        print(radio)

        recent = await client.get_messages(limit=5)
        print(f"\nLast {len(recent)} decoded message(s):")
        for msg in recent:
            print(f"  {msg}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Show JF8Call status")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    args = p.parse_args()
    asyncio.run(main(args.host, args.port))
