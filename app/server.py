import asyncio, logging, os, uuid
from gemini_bridge import run

HOST = os.getenv("AUDIO_SOCKET_HOST", "0.0.0.0")
PORT = int(os.getenv("AUDIO_SOCKET_PORT", "9019"))
MAX_CALLS = int(os.getenv("MAX_CONCURRENT_CALLS", "2"))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("audio-bridge")
slots = asyncio.Semaphore(MAX_CALLS)

class AudioSocket:
    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.closed = False

    async def read(self):
        h = await self.reader.readexactly(3)
        typ, length = h[0], int.from_bytes(h[1:3], "big")
        return typ, await self.reader.readexactly(length) if length else b""

    async def send(self, typ, data=b""):
        if self.closed:
            return
        if len(data) > 65535:
            raise ValueError("AudioSocket payload too large")
        self.writer.write(bytes([typ]) + len(data).to_bytes(2, "big") + data)
        await self.writer.drain()

    async def close(self):
        if self.closed:
            return
        self.closed = True
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except Exception:
            pass

async def handle(reader, writer):
    async with slots:
        call_id = str(uuid.uuid4())[:8]
        log.info("[%s] AudioSocket from %s", call_id, writer.get_extra_info("peername"))
        sock = AudioSocket(reader, writer)
        incoming = asyncio.Queue(maxsize=100)
        outgoing = asyncio.Queue(maxsize=100)
        stop = asyncio.Event()

        async def receive_phone():
            try:
                while not stop.is_set():
                    typ, data = await sock.read()
                    if typ == 0x00:
                        break
                    if typ == 0x01:
                        log.info("[%s] UUID received", call_id)
                    elif typ == 0x03:
                        log.info("[%s] DTMF=%r", call_id, data.decode("ascii", "replace"))
                    elif 0x10 <= typ <= 0x18:
                        if typ != 0x10:
                            log.warning("[%s] unexpected audio type 0x%02x", call_id, typ)
                        try:
                            incoming.put_nowait(data)
                        except asyncio.QueueFull:
                            try: incoming.get_nowait()
                            except asyncio.QueueEmpty: pass
                            incoming.put_nowait(data)
            except (asyncio.IncompleteReadError, ConnectionError):
                pass
            finally:
                stop.set()

        async def transmit_phone():
            try:
                while not stop.is_set():
                    try:
                        data = await asyncio.wait_for(outgoing.get(), 0.1)
                    except asyncio.TimeoutError:
                        continue
                    if data:
                        await sock.send(0x10, data)
            except (ConnectionError, BrokenPipeError):
                stop.set()

        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(receive_phone())
                tg.create_task(transmit_phone())
                tg.create_task(run(incoming, outgoing, stop, call_id))
        except* Exception as group:
            for exc in group.exceptions:
                log.error("[%s] task failed: %r", call_id, exc)
        finally:
            stop.set()
            await sock.close()
            log.info("[%s] call ended", call_id)

async def main():
    server = await asyncio.start_server(handle, HOST, PORT, limit=1024 * 1024)
    log.info("AudioSocket listening on %s:%s", HOST, PORT)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
