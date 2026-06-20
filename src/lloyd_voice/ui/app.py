import asyncio
import json
import logging
import threading
import time
from pathlib import Path
from typing import Optional

import aiohttp
import aiohttp_cors
from aiohttp import web

from lloyd_voice.core.audio import AudioCapture, AudioLevel
from lloyd_voice.core.transcriber import Transcriber
from lloyd_voice.session.context import SessionContext

logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
STATIC_DIR = HERE / "static"


class LloydVoiceServer:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        model_size: str = "base",
        device: str = "auto",
    ):
        self.host = host
        self.port = port
        self.model_size = model_size
        self.device = device
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._audio: Optional[AudioCapture] = None
        self._transcriber: Optional[Transcriber] = None
        self._session: Optional[SessionContext] = None
        self._ws_clients: set[web.WebSocketResponse] = set()
        self._stop_event = asyncio.Event()
        self._transcribe_task: Optional[asyncio.Task] = None
        self._recording = False
        self._paused = False

    async def _broadcast(self, event: str, data: dict):
        message = json.dumps({"event": event, "data": data})
        dead = set()
        for ws in self._ws_clients:
            try:
                await ws.send_str(message)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    def _on_audio_level(self, level: AudioLevel):
        loop = getattr(self, '_loop', None) or asyncio.get_event_loop()
        asyncio.run_coroutine_threadsafe(
            self._broadcast("audio_level", {
                "rms": level.rms,
                "peak": level.peak,
                "waveform": level.waveform,
            }),
            loop,
        )

    def _on_transcription(self, result):
        if not result.text.strip():
            return
        loop = getattr(self, '_loop', None) or asyncio.get_event_loop()
        is_command = False
        if self._session:
            new_doc, command = self._session.add_utterance(result.text)
            is_command = command is not None
            asyncio.run_coroutine_threadsafe(
                self._broadcast("transcription", {
                    "text": result.text,
                    "is_final": result.is_final,
                    "is_command": is_command,
                    "document": new_doc,
                    "language": result.language,
                }),
                loop,
            )
        else:
            asyncio.run_coroutine_threadsafe(
                self._broadcast("transcription", {
                    "text": result.text,
                    "is_final": result.is_final,
                    "is_command": False,
                    "document": result.text,
                    "language": result.language,
                }),
                loop,
            )

    async def _transcribe_loop(self):
        self._transcriber.load_model()
        stop_event = threading.Event()

        async def run_streaming():
            for chunk in self._audio.iter_chunks(stop_event):
                if self._paused:
                    continue
                self._transcriber.transcribe_streaming(
                    [chunk],
                    min_chunk_duration=0.5,
                    silence_threshold=0.01,
                    silence_duration=0.6,
                )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_streaming)

    async def _handle_ws(self, request: web.Request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self._ws_clients.add(ws)
        logger.info(f"WebSocket client connected ({len(self._ws_clients)} total)")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(ws, data)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error(f"WebSocket error: {ws.exception()}")
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            self._ws_clients.discard(ws)
            logger.info(f"WebSocket client disconnected ({len(self._ws_clients)} total)")

        return ws

    async def _handle_ws_message(self, ws: web.WebSocketResponse, data: dict):
        action = data.get("action", "")
        if action == "start_recording":
            if not self._recording:
                self._recording = True
                self._paused = False
                self._session = SessionContext()
                self._audio = AudioCapture()
                self._transcriber = Transcriber(
                    model_size=self.model_size,
                    device=self.device,
                )
                self._transcriber.on_result(self._on_transcription)
                self._audio.on_level(self._on_audio_level)
                self._audio.start()
                self._transcribe_task = asyncio.create_task(self._transcribe_loop())
                await ws.send_str(json.dumps({"event": "status", "data": {"recording": True}}))
                logger.info("Recording started")

        elif action == "stop_recording":
            if self._recording:
                self._recording = False
                if self._audio:
                    self._audio.stop()
                if self._transcribe_task:
                    self._transcribe_task.cancel()
                    self._transcribe_task = None
                if self._session:
                    summary = self._session.summarize()
                    await ws.send_str(json.dumps({"event": "summary", "data": summary}))
                await ws.send_str(json.dumps({"event": "status", "data": {"recording": False}}))
                logger.info("Recording stopped")

        elif action == "pause":
            self._paused = True
            await ws.send_str(json.dumps({"event": "status", "data": {"paused": True}}))

        elif action == "resume":
            self._paused = False
            await ws.send_str(json.dumps({"event": "status", "data": {"paused": False}}))

        elif action == "get_document":
            doc_text = self._session.document if self._session else ""
            await ws.send_str(json.dumps({
                "event": "document",
                "data": {"text": doc_text},
            }))

        elif action == "reset_session":
            if self._session:
                self._session.reset()
            await ws.send_str(json.dumps({"event": "document", "data": {"text": ""}}))

        elif action == "set_model":
            self.model_size = data.get("model", self.model_size)
            await ws.send_str(json.dumps({
                "event": "status",
                "data": {"model": self.model_size},
            }))

    async def _handle_index(self, request: web.Request):
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            return web.Response(text="UI not found", status=404)
        return web.FileResponse(index_path)

    async def _handle_static(self, request: web.Request):
        filename = request.match_info.get("filename", "")
        filepath = STATIC_DIR / filename
        if not filepath.exists() or not filepath.is_file():
            return web.Response(text="Not found", status=404)
        return web.FileResponse(filepath)

    async def _health_check(self, request: web.Request):
        return web.json_response({
            "status": "ok",
            "recording": self._recording,
            "clients": len(self._ws_clients),
            "session_active": self._session is not None,
        })

    def _build_app(self):
        app = web.Application()
        app.router.add_get("/", self._handle_index)
        app.router.add_get("/ws", self._handle_ws)
        app.router.add_get("/health", self._health_check)
        app.router.add_get("/static/{filename:.*}", self._handle_static)

        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
        })
        for route in app.router.routes():
            cors.add(route)

        self._app = app
        return app

    async def start(self):
        self._loop = asyncio.get_event_loop()
        app = self._build_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"Lloyd Voice server running at http://{self.host}:{self.port}")
        print(f"\n  Lloyd Voice server running at http://{self.host}:{self.port}")
        print(f"  Open this URL in your browser (or from any device on your network)\n")

    async def stop(self):
        if self._recording:
            self._recording = False
            if self._audio:
                self._audio.stop()
        if self._transcribe_task:
            self._transcribe_task.cancel()
        for ws in set(self._ws_clients):
            await ws.close()
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
