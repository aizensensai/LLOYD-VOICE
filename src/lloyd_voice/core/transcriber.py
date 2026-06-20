import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable

import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    text: str
    is_final: bool
    timestamp: float = field(default_factory=time.time)
    language: Optional[str] = None
    duration: float = 0.0


class Transcriber:
    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        cpu_threads: int = 4,
        num_workers: int = 1,
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.num_workers = num_workers
        self._model: Optional[WhisperModel] = None
        self._buffer: list[np.ndarray] = []
        self._buffer_duration = 0.0
        self._callbacks: list[Callable[[TranscriptionResult], None]] = []
        self._language: Optional[str] = None

    def on_result(self, callback: Callable[[TranscriptionResult], None]):
        self._callbacks.append(callback)

    def _emit(self, text: str, is_final: bool, duration: float = 0.0):
        result = TranscriptionResult(
            text=text.strip(),
            is_final=is_final,
            duration=duration,
            language=self._language,
        )
        for cb in self._callbacks:
            cb(result)

    def load_model(self):
        if self._model is not None:
            return
        device = self.device
        compute_type = self.compute_type

        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"

        logger.info(f"Loading Whisper model '{self.model_size}' on {device} ({compute_type})")
        self._model = WhisperModel(
            self.model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=self.cpu_threads,
            num_workers=self.num_workers,
        )

    def transcribe_sync(self, audio: np.ndarray) -> str:
        if self._model is None:
            self.load_model()
        segments, info = self._model.transcribe(audio, beam_size=1)
        self._language = info.language
        return " ".join(seg.text for seg in segments)

    def transcribe_chunk(self, audio: np.ndarray, chunk_duration: float):
        if self._model is None:
            self.load_model()
        segments, info = self._model.transcribe(audio, beam_size=1)
        self._language = info.language
        full_text = " ".join(seg.text for seg in segments)
        if full_text.strip():
            self._emit(full_text, is_final=True, duration=chunk_duration)

    def transcribe_streaming(
        self,
        audio_iter,
        min_chunk_duration: float = 1.0,
        max_chunk_duration: float = 30.0,
        silence_threshold: float = 0.01,
        silence_duration: float = 0.8,
    ):
        if self._model is None:
            self.load_model()

        chunk_buffer = []
        chunk_start = time.time()
        speech_buffer = []
        speech_start = time.time()
        in_speech = False
        silence_start = None

        for audio_chunk in audio_iter:
            now = time.time()
            chunk_buffer.append(audio_chunk)
            rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
            is_speech = rms > silence_threshold

            if is_speech and not in_speech:
                in_speech = True
                speech_start = now
                silence_start = None
            elif not is_speech and in_speech:
                if silence_start is None:
                    silence_start = now
                elif now - silence_start >= silence_duration:
                    audio_array = np.concatenate(speech_buffer) if speech_buffer else np.array([], dtype=np.float32)
                    if len(audio_array) > 0 and np.sqrt(np.mean(audio_array ** 2)) > silence_threshold:
                        self.transcribe_chunk(audio_array, now - speech_start)
                    speech_buffer = []
                    in_speech = False
                    silence_start = None

            if in_speech:
                speech_buffer.append(audio_chunk)
            elif now - chunk_start >= max_chunk_duration:
                if speech_buffer:
                    audio_array = np.concatenate(speech_buffer)
                    if len(audio_array) > 0:
                        self.transcribe_chunk(audio_array, now - speech_start)
                    speech_buffer = []
                chunk_buffer = []
                chunk_start = now

        if speech_buffer:
            audio_array = np.concatenate(speech_buffer)
            if len(audio_array) > 0:
                self.transcribe_chunk(audio_array, time.time() - speech_start)

    def cleanup(self):
        self._model = None
