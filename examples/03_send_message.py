#!/usr/bin/env python3
"""
03_send_message.py — Send a directed message and wait for TX to complete.

Run with:
    python3 examples/03_send_message.py W4ABC "HELLO 73"
    python3 examples/03_send_message.py W4ABC "QUICK MSG" --submode fast
    python3 examples/03_send_message.py --hb                # send heartbeat
    python3 examples/03_send_message.py --snr W4ABC         # send @SNR? query
    python3 examples/03_send_message.py --info W4ABC        # send @INFO? query
"""
import argparse
import asyncio
from jf8net import JF8Client


async def main(host: str, port: int, args: argparse.Namespace) -> None:
    async with JF8Client(host=host, port=port) as client:
        status = await client.get_status()
        my_call = status.callsign
        if not my_call:
            print("ERROR: Callsign not configured in JF8Call.")
            return

        tx_started = asyncio.Event()
        tx_done = asyncio.Event()

        @client.on_tx_started
        def on_start(_):
            tx_started.set()
            print(">>> TX started")

        @client.on_tx_finished
        def on_done(_):
            tx_done.set()
            print("<<< TX finished")

        if args.hb:
            queue_size = await client.send_heartbeat()
            print(f"Queued heartbeat ({my_call} @HB). Queue size: {queue_size}")

        elif args.snr:
            queue_size = await client.send_snr_query(args.snr)
            print(f"Queued @SNR? query to {args.snr.upper()}. Queue size: {queue_size}")

        elif args.info:
            queue_size = await client.send_info_query(args.info)
            print(f"Queued @INFO? query to {args.info.upper()}. Queue size: {queue_size}")

        elif args.status_q:
            queue_size = await client.send_status_query(args.status_q)
            print(f"Queued @? query to {args.status_q.upper()}. Queue size: {queue_size}")

        elif args.dest and args.text:
            text = f"{args.dest.upper()} {args.text}"
            queue_size = await client.send(text, submode=args.submode)
            print(f"Queued: {text!r}. Queue size: {queue_size}")

        else:
            print("Nothing to send. Use --help for usage.")
            return

        print("Waiting for TX to complete (Ctrl-C to cancel)…")
        try:
            await client.wait_for_tx(timeout=300)
            print("Done.")
        except asyncio.TimeoutError:
            print("Timeout waiting for TX.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Send a JF8Call message")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)
    p.add_argument("dest", nargs="?", help="Destination callsign")
    p.add_argument("text", nargs="?", help="Message text")
    p.add_argument("--submode", default=None,
                   help="Submode: normal/fast/turbo/slow/ultra")
    p.add_argument("--hb", action="store_true", help="Send heartbeat")
    p.add_argument("--snr", metavar="CALL", help="Send @SNR? query")
    p.add_argument("--info", metavar="CALL", help="Send @INFO? query")
    p.add_argument("--status-q", metavar="CALL", dest="status_q",
                   help="Send @? status query")
    args = p.parse_args()
    try:
        asyncio.run(main(args.host, args.port, args))
    except KeyboardInterrupt:
        pass
