"""
jf8net — Python library for the JF8Call WebSocket API.

Quick start (async)::

    import asyncio
    from jf8net import JF8Client, DecodedMessage

    async def main():
        async with JF8Client() as client:
            status = await client.get_status()
            print(status)

            @client.on_message
            async def handle(msg: DecodedMessage):
                print(msg)

            await client.run_forever()

    asyncio.run(main())

Quick start (sync)::

    from jf8net.sync import JF8ClientSync

    with JF8ClientSync() as client:
        print(client.get_status())
        for msg in client.messages():
            print(msg)
"""

from ._client import JF8Client, JF8Error, ConnectionError
from ._models import (
    DecodedMessage,
    FrameUpdate,
    Status,
    Config,
    RadioStatus,
    TxFrame,
    AudioDevices,
    Spectrum,
    MessageType,
    FrameType,
    ModemType,
    PttType,
)

__version__ = "0.1.0"
__all__ = [
    "JF8Client",
    "JF8Error",
    "ConnectionError",
    "DecodedMessage",
    "FrameUpdate",
    "Status",
    "Config",
    "RadioStatus",
    "TxFrame",
    "AudioDevices",
    "Spectrum",
    "MessageType",
    "FrameType",
    "ModemType",
    "PttType",
]
