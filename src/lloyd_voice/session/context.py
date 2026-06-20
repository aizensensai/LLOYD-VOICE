import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from lloyd_voice.core.commands import (
    VoiceCommand, process_utterance, contains_command,
    CommandType,
)


@dataclass
class SessionSegment:
    text: str
    timestamp: float = field(default_factory=time.time)
    is_command: bool = False
    command: Optional[VoiceCommand] = None
    corrected: bool = False
    correction_of: Optional[int] = None


class SessionContext:
    def __init__(self, max_history: int = 100):
        self._segments: list[SessionSegment] = []
        self._history: list[str] = []
        self._document: str = ""
        self._max_history = max_history
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._session_start: float = time.time()
        self._segment_id: int = 0

    @property
    def document(self) -> str:
        return self._document

    @document.setter
    def document(self, value: str):
        self._document = value

    @property
    def segments(self) -> list[SessionSegment]:
        return list(self._segments)

    @property
    def duration(self) -> float:
        return time.time() - self._session_start

    def add_utterance(self, utterance: str) -> tuple[str, Optional[VoiceCommand]]:
        prev_doc = self._document
        new_doc, command, command_text = process_utterance(
            self._document, utterance, self._history
        )

        if command:
            if command.type in (CommandType.UNDO,):
                if self._undo_stack:
                    self._redo_stack.append(self._document)
                    new_doc = self._undo_stack.pop()
                    self._document = new_doc
            elif command.type == CommandType.REDO:
                if self._redo_stack:
                    self._undo_stack.append(self._document)
                    new_doc = self._redo_stack.pop()
                    self._document = new_doc
            else:
                if new_doc != prev_doc:
                    self._undo_stack.append(prev_doc)
                    self._redo_stack.clear()
                self._document = new_doc

            segment = SessionSegment(
                text=utterance,
                is_command=True,
                command=command,
            )
        else:
            if new_doc != prev_doc:
                self._undo_stack.append(prev_doc)
                self._redo_stack.clear()
            segment = SessionSegment(
                text=utterance,
                is_command=False,
            )
            self._document = new_doc

        self._segments.append(segment)
        self._history.append(prev_doc)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        return new_doc, command

    def get_recent_context(self, n_segments: int = 5) -> str:
        recent = self._segments[-n_segments:] if len(self._segments) > n_segments else self._segments
        return "\n".join(
            f"[{'CMD' if s.is_command else 'TXT'}] {s.text}"
            for s in recent
        )

    def get_structured_document(self) -> list[dict]:
        result = []
        i = 0
        buffer = []
        for seg in self._segments:
            if seg.is_command:
                if buffer:
                    result.append({"type": "text", "content": " ".join(buffer)})
                    buffer = []
                result.append({
                    "type": "command",
                    "command": seg.command.type.value if seg.command else "unknown",
                    "text": seg.text,
                })
            else:
                buffer.append(seg.text)
        if buffer:
            result.append({"type": "text", "content": " ".join(buffer)})
        return result

    def summarize(self) -> dict:
        total_utterances = len(self._segments)
        command_count = sum(1 for s in self._segments if s.is_command)
        text_count = total_utterances - command_count
        return {
            "duration": self.duration,
            "total_utterances": total_utterances,
            "command_count": command_count,
            "text_count": text_count,
            "document_length": len(self._document),
            "word_count": len(self._document.split()),
        }

    def reset(self):
        self._segments.clear()
        self._history.clear()
        self._document = ""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._session_start = time.time()
