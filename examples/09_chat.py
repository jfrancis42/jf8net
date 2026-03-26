#!/usr/bin/env python3
"""
09_chat.py — Interactive two-way chat session.

Connects to JF8Call and opens an interactive terminal chat with a specific
callsign.  Incoming messages from your chat partner appear in real time;
type a line and press Enter to send.

Run with:
    python3 examples/09_chat.py W4ABC
    python3 examples/09_chat.py W4ABC --submode fast
    python3 examples/09_chat.py W4ABC --all     # also show other traffic
"""
import argparse
import asyncio
import sys
from datetime import datetime, timezone

from jf8net import JF8Client, DecodedMessage

ERASE = "\r\033[K"   # carriage-return + erase-to-end-of-line


def timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%Mz")


def print_msg(line: str) -> None:
    """Overwrite any partial input line, print the message, restore prompt."""
    sys.stdout.write(f"{ERASE}{line}\n> ")
    sys.stdout.flush()


async def main(host: str, port: int, peer: str,
               submode: str | None, show_all: bool) -> None:
    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        my_call = status.callsign
        if not my_call:
            print("ERROR: Callsign not configured in JF8Call.")
            return

        peer = peer.upper()

        print(f"\n{'─' * 52}")
        print(f"  JF8Call Chat  ·  {my_call} ↔ {peer}")
        print(f"  {status.frequency_khz} kHz  [{status.submode_name}]")
        print(f"  Type and Enter to send.  Ctrl-C to quit.")
        print(f"{'─' * 52}\n")
        sys.stdout.write("> ")
        sys.stdout.flush()

        # ── Event handlers ─────────────────────────────────────────────────

        @client.on_tx_started
        def on_tx_start(_) -> None:
            print_msg(f"[{timestamp()}] *** TX started ***")

        @client.on_tx_finished
        def on_tx_done(_) -> None:
            print_msg(f"[{timestamp()}] *** TX finished ***")

        @client.on_message
        def on_decoded(msg: DecodedMessage) -> None:
            ts = msg.time.strftime("%H:%Mz") if msg.time else timestamp()
            body = msg.body if msg.body else msg.raw

            if msg.from_call == peer:
                arrow = ">>>" if msg.to == my_call else "   "
                print_msg(f"[{ts}] {arrow} {msg.from_call}: {body}")
            elif show_all:
                print_msg(f"[{ts}]  ~  {msg.from_call} → {msg.to}: {body}")

        # ── Input / send loop ───────────────────────────────────────────────

        loop = asyncio.get_running_loop()
        input_q: asyncio.Queue[str | None] = asyncio.Queue()

        async def read_stdin() -> None:
            try:
                while True:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    await input_q.put(None if not line else line.rstrip("\n"))
                    if not line:   # EOF
                        return
            except Exception:
                await input_q.put(None)

        async def send_loop() -> None:
            while True:
                text = await input_q.get()
                if text is None:
                    return
                text = text.strip()
                if not text:
                    sys.stdout.write("> ")
                    sys.stdout.flush()
                    continue

                queue_size = await client.send(f"{peer} {text}", submode=submode)
                sys.stdout.write(
                    f"{ERASE}[{timestamp()}] <<< {my_call}: {text}"
                    f"  (queued #{queue_size})\n> "
                )
                sys.stdout.flush()

        stdin_task = asyncio.create_task(read_stdin())
        send_task  = asyncio.create_task(send_loop())
        ws_task    = asyncio.create_task(client.run_forever())

        _, pending = await asyncio.wait(
            [stdin_task, send_task, ws_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

        print("\nDisconnected.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Interactive JF8Call chat session")
    p.add_argument("peer", help="Callsign to chat with")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    p.add_argument("--submode", default=None,
                   help="Submode override: normal/fast/turbo/slow/ultra")
    p.add_argument("--all", dest="show_all", action="store_true",
                   help="Also display other decoded traffic in the background")
    args = p.parse_args()
    try:
        asyncio.run(main(args.host, args.port, args.peer, args.submode,
                         args.show_all))
    except KeyboardInterrupt:
        print("\nBye.")
