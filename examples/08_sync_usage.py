#!/usr/bin/env python3
"""
08_sync_usage.py — Synchronous API usage examples.

JF8ClientSync wraps the async client in a background thread so you can
write ordinary blocking code without managing an event loop. Useful for
scripts, REPL exploration, or integration with synchronous frameworks.

Run with:
    python3 examples/08_sync_usage.py
"""
import time
from jf8net.sync import JF8ClientSync


def example_status_and_config():
    print("=== Status & Config ===")
    with JF8ClientSync() as client:
        status = client.get_status()
        print(status)
        print()

        cfg = client.get_config()
        print(f"Station info: {cfg.station_info or '(not set)'}")
        print(f"Auto-ATU    : {cfg.auto_atu}")
        print(f"PSKReporter : {cfg.psk_reporter_enabled}")


def example_receive_messages():
    print("\n=== Receive Messages (10 seconds) ===")
    with JF8ClientSync() as client:
        # messages() is a generator that blocks and yields
        for msg in client.messages(timeout=10.0):
            print(f"  {msg}")
        print("(10s elapsed, stopping)")


def example_receive_with_frames():
    print("\n=== Receive Messages + Partial Frames (15 seconds) ===")
    with JF8ClientSync() as client:
        for item in client.messages(include_frames=True, timeout=15.0):
            print(f"  {item}")


def example_event_callbacks():
    print("\n=== Event Callbacks (20 seconds) ===")
    with JF8ClientSync() as client:
        @client.on_message
        def on_msg(msg):
            print(f"  DECODED: {msg}")

        @client.on_frame
        def on_frame(frame):
            print(f"  FRAME [{frame.frame_type_name.upper()}]: {frame.assembled_text!r}")

        @client.on_tx_started
        def on_tx(_):
            print("  >>> TX STARTED")

        @client.on_tx_finished
        def on_done(_):
            print("  <<< TX FINISHED")

        time.sleep(20)


def example_send_and_wait():
    print("\n=== Send and Wait ===")
    with JF8ClientSync() as client:
        status = client.get_status()
        if not status.callsign:
            print("Callsign not set — skipping TX example")
            return

        print(f"Sending heartbeat as {status.callsign}…")
        q = client.send_heartbeat()
        print(f"Queued (queue size: {q}). Waiting for TX…")
        client.wait_for_tx(timeout=60)
        print("TX complete.")


def example_radio_control():
    print("\n=== Radio Control ===")
    with JF8ClientSync() as client:
        radio = client.get_radio()
        print(radio)

        if not radio.connected:
            print("Rig not connected — skipping frequency change")
            return

        print("\nTuning to 20m JS8 calling frequency (14.078 MHz)…")
        actual = client.set_frequency(14078.0)
        print(f"VFO set to {actual} kHz")

        cfg = client.get_config()
        if not cfg.auto_atu:
            print("Triggering ATU tune…")
            client.tune()
            print("ATU tune sent.")
        else:
            print("auto_atu is on — ATU triggered automatically with set_frequency()")


if __name__ == "__main__":
    print("jf8net Synchronous API Examples")
    print("=" * 40)

    example_status_and_config()

    # Uncomment the examples you want to run:
    # example_receive_messages()
    # example_receive_with_frames()
    # example_event_callbacks()
    # example_send_and_wait()
    # example_radio_control()
