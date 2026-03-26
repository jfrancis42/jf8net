#!/usr/bin/env python3
"""
07_spectrum_monitor.py — Live spectrum monitoring.

Subscribes to the ~5 Hz spectrum push event and prints a live ASCII
waterfall to the terminal. Also demonstrates the typed Spectrum object
and the on_spectrum convenience decorator.

Run with:
    python3 examples/07_spectrum_monitor.py
    python3 examples/07_spectrum_monitor.py --low 500 --high 2500   # focus range
    python3 examples/07_spectrum_monitor.py --width 60              # terminal width
"""
import argparse
import asyncio
import time
from jf8net import JF8Client, Spectrum

# Simple ASCII waterfall characters (low power → high power)
CHARS = " ░▒▓█"


def render_bar(bins: list, hz_per_bin: float,
               low_hz: float, high_hz: float, width: int) -> str:
    """Render a single spectrum row as an ASCII string."""
    lo = max(0, int(low_hz / hz_per_bin))
    hi = min(len(bins), int(high_hz / hz_per_bin) + 1)
    if lo >= hi:
        return ""

    # Downsample to terminal width
    chunk = (hi - lo) / width
    bar = []
    for i in range(width):
        start = lo + int(i * chunk)
        end   = lo + int((i + 1) * chunk)
        val   = max(bins[start:end]) if start < hi else -120.0
        # Map -90..-30 dBFS → 0..4
        scaled = int((val + 90) / 60 * (len(CHARS) - 1))
        scaled = max(0, min(len(CHARS) - 1, scaled))
        bar.append(CHARS[scaled])
    return "".join(bar)


async def main(host: str, port: int,
               low_hz: float, high_hz: float, width: int) -> None:
    last_render = time.monotonic()
    frame_count = [0]

    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        print(f"Connected. {status.frequency_khz} kHz  {status.submode_name}")
        print(f"Showing {low_hz:.0f}–{high_hz:.0f} Hz  (Ctrl-C to stop)\n")

        @client.on_spectrum
        def on_spec(spec: Spectrum) -> None:
            frame_count[0] += 1
            bar = render_bar(spec.bins, spec.hz_per_bin, low_hz, high_hz, width)
            peak_hz = spec.peak_hz()
            peak_db = spec.peak_db()
            # Overwrite same line for live update
            print(f"\r|{bar}|  peak: {peak_hz:5.0f}Hz {peak_db:+5.1f}dB",
                  end="", flush=True)

        try:
            await client.run_forever()
        except asyncio.CancelledError:
            pass
        print(f"\n\n{frame_count[0]} spectrum frames received.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="JF8Call live spectrum display")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    p.add_argument("--low",   type=float, default=200,
                   help="Low frequency cutoff in Hz (default: 200)")
    p.add_argument("--high",  type=float, default=3000,
                   help="High frequency cutoff in Hz (default: 3000)")
    p.add_argument("--width", type=int, default=80,
                   help="Terminal display width in characters (default: 80)")
    args = p.parse_args()
    try:
        asyncio.run(main(args.host, args.port, args.low, args.high, args.width))
    except KeyboardInterrupt:
        pass
