#!/usr/bin/env python3
"""
06_config_management.py — Read and update JF8Call configuration.

Demonstrates the config.get / config.set API, including all the fields
that js8net could not access: station_info, station_status, cq_message,
auto_atu, psk_reporter_enabled, and full rig serial parameters.

Run with:
    python3 examples/06_config_management.py --show
    python3 examples/06_config_management.py --callsign W5XYZ --grid DM79AA
    python3 examples/06_config_management.py --info "QTH: Austin TX  PWR: 100W"
    python3 examples/06_config_management.py --auto-atu on
    python3 examples/06_config_management.py --pskreporter off
    python3 examples/06_config_management.py --heartbeat on --hb-interval 6
"""
import argparse
import asyncio
from jf8net import JF8Client, ModemType


def yn(v: bool) -> str:
    return "yes" if v else "no"


async def main(host: str, port: int, args: argparse.Namespace) -> None:
    async with JF8Client(host=host, port=port) as client:
        if args.show:
            cfg = await client.get_config()
            print(f"Callsign             : {cfg.callsign}")
            print(f"Grid                 : {cfg.grid}")
            print(f"Station info         : {cfg.station_info or '(not set)'}")
            print(f"Station status       : {cfg.station_status or '(not set)'}")
            print(f"CQ message           : {cfg.cq_message or '(not set)'}")
            print(f"Modem type           : {ModemType.name(cfg.modem_type)}")
            print(f"Submode              : {cfg.submode}")
            print(f"Frequency            : {cfg.frequency_khz} kHz")
            print(f"TX offset            : {cfg.tx_freq_hz} Hz")
            print(f"TX power             : {cfg.tx_power_pct}%")
            print(f"Heartbeat            : {yn(cfg.heartbeat_enabled)}"
                  f"  every {cfg.heartbeat_interval_periods} periods")
            print(f"Auto-reply           : {yn(cfg.auto_reply)}")
            print(f"Distance units       : {'miles' if cfg.dist_miles else 'km'}")
            print(f"Auto-ATU             : {yn(cfg.auto_atu)}")
            print(f"PSKReporter          : {yn(cfg.psk_reporter_enabled)}")
            print(f"Rig model            : {cfg.rig_model}")
            print(f"Rig port             : {cfg.rig_port or '(not set)'}")
            print(f"Rig baud             : {cfg.rig_baud}")
            print(f"PTT type             : {cfg.ptt_type}"
                  f"  ({['VOX','CAT','DTR','RTS'][cfg.ptt_type]})")
            print(f"WebSocket            : {'enabled' if cfg.ws_enabled else 'disabled'}"
                  f"  port {cfg.ws_port}")
            return

        # Build the set of fields to update
        updates = {}

        if args.callsign:
            updates["callsign"] = args.callsign.upper()
        if args.grid:
            updates["grid"] = args.grid.upper()
        if args.info is not None:
            updates["station_info"] = args.info
        if args.status is not None:
            updates["station_status"] = args.status
        if args.cq is not None:
            updates["cq_message"] = args.cq
        if args.auto_atu is not None:
            updates["auto_atu"] = args.auto_atu.lower() in ("on", "true", "yes", "1")
        if args.pskreporter is not None:
            updates["psk_reporter_enabled"] = (
                args.pskreporter.lower() in ("on", "true", "yes", "1")
            )
        if args.heartbeat is not None:
            updates["heartbeat_enabled"] = (
                args.heartbeat.lower() in ("on", "true", "yes", "1")
            )
        if args.hb_interval is not None:
            updates["heartbeat_interval_periods"] = args.hb_interval
        if args.auto_reply is not None:
            updates["auto_reply"] = (
                args.auto_reply.lower() in ("on", "true", "yes", "1")
            )
        if args.miles is not None:
            updates["dist_miles"] = args.miles.lower() in ("on", "true", "yes", "1")

        if not updates:
            print("Nothing to update. Use --show to view config, or --help for options.")
            return

        print(f"Updating {len(updates)} field(s): {list(updates)}")
        new_cfg = await client.set_config(**updates)
        print("Done.")
        print(f"  Callsign  : {new_cfg.callsign}")
        print(f"  Grid      : {new_cfg.grid}")
        print(f"  Auto-ATU  : {yn(new_cfg.auto_atu)}")
        print(f"  PSKReport : {yn(new_cfg.psk_reporter_enabled)}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="JF8Call configuration management")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=2102)

    p.add_argument("--show", action="store_true", help="Print current configuration")
    p.add_argument("--callsign", help="Set callsign")
    p.add_argument("--grid", help="Set Maidenhead grid locator")
    p.add_argument("--info", metavar="TEXT", help="Set station info (@INFO? reply)")
    p.add_argument("--status", metavar="TEXT", help="Set station status (@? reply)")
    p.add_argument("--cq", metavar="TEXT", help="Set CQ message")
    p.add_argument("--auto-atu", metavar="on|off", help="Enable/disable auto-ATU")
    p.add_argument("--pskreporter", metavar="on|off",
                   help="Enable/disable PSKReporter submission")
    p.add_argument("--heartbeat", metavar="on|off",
                   help="Enable/disable periodic heartbeat")
    p.add_argument("--hb-interval", type=int, metavar="N",
                   help="Heartbeat every N JS8 periods")
    p.add_argument("--auto-reply", metavar="on|off",
                   help="Enable/disable auto-reply to @SNR?/@INFO?")
    p.add_argument("--miles", metavar="on|off",
                   help="Show distances in miles (on) or km (off)")

    args = p.parse_args()
    asyncio.run(main(args.host, args.port, args))
