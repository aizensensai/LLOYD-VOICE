import asyncio
import queue
import threading
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = np.float32
BLOCK_SIZE = 1600


@dataclass
class AudioLevel:
    rms: float
    peak: float
    waveform: list[float] = field(default_factory=list)


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        channels: int = CHANNELS,
        blocksize: int = BLOCK_SIZE,
        device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device
        self._stream: Optional[sd.InputStream] = None
        self._queue: queue.Queue = queue.Queue()
        self._level_callbacks: list[Callable[[AudioLevel], None]] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def on_level(self, callback: Callable[[AudioLevel], None]):
        self._level_callbacks.append(callback)

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            return
        chunk = indata.copy().flatten()
        self._queue.put(chunk)
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        peak = float(np.max(np.abs(chunk)))
        decimated = chunk[::8].tolist() if len(chunk) > 100 else chunk.tolist()
        level = AudioLevel(rms=rms, peak=peak, waveform=decimated[:200])
        for cb in self._level_callbacks:
            cb(level)

    def start(self):
        if self._running:
            return
        self._running = True
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=DTYPE,
            blocksize=self.blocksize,
            device=self.device,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def iter_chunks(self, stop_event: threading.Event):
        while not stop_event.is_set():
            try:
                chunk = self._queue.get(timeout=0.1)
                yield chunk
            except queue.Empty:
                continue

    async def iter_chunks_async(self, stop_event: asyncio.Event):
        loop = asyncio.get_event_loop()
        while not stop_event.is_set():
            try:
                chunk = await loop.run_in_executor(None, lambda: self._queue.get(timeout=0.1))
                yield chunk
            except queue.Empty:
                continue

    @property
    def is_active(self) -> bool:
        return self._running and self._stream is not None and self._stream.active
