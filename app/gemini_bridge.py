import asyncio, logging, os, struct
from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
VOICE = os.getenv("GEMINI_VOICE", "Kore")
KEY = os.environ["GEMINI_API_KEY"]
ENABLE_GOOGLE_SEARCH = os.getenv("ENABLE_GOOGLE_SEARCH", "true").lower() in ("1", "true", "yes")
INSTRUCTION = os.getenv(
    "GEMINI_SYSTEM_INSTRUCTION",
    "אתה עוזר קולי. נהל שיחה טבעית ורציפה בעברית. ענה בקצרה ובבהירות. "
    "כאשר שואלים על חדשות או מידע עדכני, השתמש בחיפוש Google אם הוא זמין; "
    "הבהר את התאריך וציין בקצרה את המקורות. אל תמציא מידע עדכני. "
    "אל תכלול תמלילי שיחה במידע אבחון או ביומנים."
)

log = logging.getLogger("gemini-live")
client = genai.Client(api_key=KEY)

def pcm8_to_pcm16(data: bytes) -> bytes:
    """Upsample 8 kHz mono s16le to 16 kHz using linear interpolation."""
    if len(data) < 2:
        return b""
    n = len(data) // 2
    s = struct.unpack("<%dh" % n, data[:n * 2])
    out = bytearray(n * 4)
    j = 0
    for i, a in enumerate(s):
        b = s[i + 1] if i + 1 < n else a
        struct.pack_into("<h", out, j, a)
        struct.pack_into("<h", out, j + 2, (a + b) // 2)
        j += 4
    return bytes(out)

def pcm24_to_pcm8(data: bytes) -> bytes:
    """Downsample 24 kHz mono s16le to 8 kHz without dropping queued audio."""
    n = len(data) // 2
    if n < 3:
        return b""
    s = struct.unpack("<%dh" % n, data[:n * 2])
    count = n // 3
    out = bytearray(count * 2)
    j = 0
    for i in range(0, n - 2, 3):
        value = (s[i] + s[i + 1] + s[i + 2]) // 3
        struct.pack_into("<h", out, j, value)
        j += 2
    return bytes(out[:j])

async def run(audio_in, audio_out, stop, call_id):
    """Bidirectional Gemini Live session. Keeps receive loop alive across turns."""
    resume = None
    failures = 0

    while not stop.is_set():
        try:
            cfg = {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": VOICE}
                    }
                },
                "system_instruction": INSTRUCTION,
                "context_window_compression": {"sliding_window": {}},
            }
            if resume:
                cfg["session_resumption"] = {"handle": resume}
            if ENABLE_GOOGLE_SEARCH:
                cfg["tools"] = [{"google_search": {}}]

            log.info("[%s] connecting to Gemini Live; web_search=%s",
                     call_id, ENABLE_GOOGLE_SEARCH)

            async with client.aio.live.connect(model=MODEL, config=cfg) as session:
                failures = 0

                async def send():
                    while not stop.is_set():
                        chunk = await audio_in.get()
                        if not chunk:
                            continue
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm8_to_pcm16(chunk),
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

                async def receive():
                    nonlocal resume
                    while not stop.is_set():
                        # receive() can end at a completed turn; call it again
                        # while the same Live session remains open.
                        async for response in session.receive():
                            if stop.is_set():
                                return

                            update = getattr(response, "session_resumption_update", None)
                            if update and getattr(update, "resumable", False):
                                resume = getattr(update, "new_handle", None) or resume

                            if getattr(response, "go_away", None) is not None:
                                log.info("[%s] Gemini requested session reconnect", call_id)

                            content = response.server_content
                            if not content:
                                continue

                            if getattr(content, "interrupted", False):
                                while not audio_out.empty():
                                    try:
                                        audio_out.get_nowait()
                                    except asyncio.QueueEmpty:
                                        break
                                continue

                            turn = content.model_turn
                            if turn:
                                # Do not discard audio chunks when the queue fills:
                                # dropped chunks sound like words being cut off.
                                for part in turn.parts:
                                    blob = part.inline_data
                                    if blob and blob.data:
                                        data = pcm24_to_pcm8(blob.data)
                                        if data:
                                            await audio_out.put(data)

                        await asyncio.sleep(0)

                sender = asyncio.create_task(send())
                receiver = asyncio.create_task(receive())
                stop_waiter = asyncio.create_task(stop.wait())
                tasks = (sender, receiver, stop_waiter)
                try:
                    done, _ = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if stop_waiter not in done:
                        failed = next(
                            (task for task in (sender, receiver) if task in done),
                            None,
                        )
                        if failed is not None:
                            error = failed.exception()
                            if error is not None:
                                raise error
                        raise RuntimeError("Gemini audio task ended unexpectedly")
                finally:
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)

            return

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures += 1
            log.warning("[%s] Gemini session error (%s)", call_id, type(exc).__name__)
            if stop.is_set():
                return
            if failures >= 5 and not resume:
                log.error("[%s] stopping after repeated Gemini connection failures", call_id)
                stop.set()
                return
            await asyncio.sleep(min(8, 0.5 * (2 ** min(failures, 4))))
