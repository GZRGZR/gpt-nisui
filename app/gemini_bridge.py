import asyncio, logging, os, struct
from google import genai
from google.genai import types

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-live")
VOICE = os.getenv("GEMINI_VOICE", "Kore")
KEY = os.environ["GEMINI_API_KEY"]
INSTRUCTION = os.getenv(
    "GEMINI_SYSTEM_INSTRUCTION",
    "אתה עוזר קולי. נהל שיחה טבעית ורציפה בעברית. ענה בקצרה ובבהירות, והקשב למתקשר גם כשהוא קוטע אותך."
)

log = logging.getLogger("gemini-live")
client = genai.Client(api_key=KEY)

def pcm8_to_pcm16(data: bytes) -> bytes:
    if not data:
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
    n = len(data) // 2
    s = struct.unpack("<%dh" % n, data[:n * 2])
    out = bytearray((n // 3) * 2)
    j = 0
    for i in range(0, n - 2, 3):
        struct.pack_into("<h", out, j, (s[i] + s[i + 1] + s[i + 2]) // 3)
        j += 2
    return bytes(out)

async def run(audio_in, audio_out, stop, call_id):
    resume = None
    failures = 0
    while not stop.is_set():
        restart = asyncio.Event()
        try:
            cfg = {
                "response_modalities": ["AUDIO"],
                "speech_config": {"voice_config": {
                    "prebuilt_voice_config": {"voice_name": VOICE}
                }},
                "system_instruction": INSTRUCTION,
                "session_resumption": {"handle": resume} if resume else {},
                "context_window_compression": {"sliding_window": {}},
            }
            async with client.aio.live.connect(model=MODEL, config=cfg) as session:
                await session.send_realtime_input(
                    text="ברך את המתקשר עכשיו במשפט קצר בעברית, ואז המתן לדבריו."
                )

                async def send():
                    while not stop.is_set() and not restart.is_set():
                        try:
                            chunk = await asyncio.wait_for(audio_in.get(), 0.2)
                        except asyncio.TimeoutError:
                            continue
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=pcm8_to_pcm16(chunk),
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

                async def recv():
                    nonlocal resume
                    try:
                        async for response in session.receive():
                            upd = getattr(response, "session_resumption_update", None)
                            if upd and getattr(upd, "resumable", False):
                                resume = getattr(upd, "new_handle", None) or resume

                            content = response.server_content
                            if not content:
                                continue

                            if getattr(content, "interrupted", False):
                                while not audio_out.empty():
                                    try: audio_out.get_nowait()
                                    except asyncio.QueueEmpty: break
                                continue

                            turn = content.model_turn
                            if turn:
                                for part in turn.parts:
                                    blob = part.inline_data
                                    if blob and blob.data:
                                        data = pcm24_to_pcm8(blob.data)
                                        if not data:
                                            continue
                                        try:
                                            audio_out.put_nowait(data)
                                        except asyncio.QueueFull:
                                            try: audio_out.get_nowait()
                                            except asyncio.QueueEmpty: pass
                                            audio_out.put_nowait(data)
                            if content.input_transcription and content.input_transcription.text:
                                log.info("[%s] user: %s", call_id, content.input_transcription.text.strip())
                            if content.output_transcription and content.output_transcription.text:
                                log.info("[%s] gemini: %s", call_id, content.output_transcription.text.strip())
                    finally:
                        restart.set()

                async with asyncio.TaskGroup() as tg:
                    tg.create_task(send())
                    tg.create_task(recv())
                    await stop.wait()

            if stop.is_set(): return
            failures = 0 if resume else failures + 1
            await asyncio.sleep(min(4, 0.25 * 2 ** min(failures, 4)))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            failures += 1
            log.exception("[%s] Gemini error: %s", call_id, exc)
            if stop.is_set(): return
            if failures >= 5 and not resume:
                stop.set()
                return
            await asyncio.sleep(min(8, 0.5 * 2 ** min(failures, 4)))
