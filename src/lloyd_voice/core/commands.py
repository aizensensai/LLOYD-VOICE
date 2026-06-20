import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CommandType(Enum):
    DELETE_LAST = "delete_last"
    DELETE_ALL = "delete_all"
    DELETE_PHRASE = "delete_phrase"
    REPLACE = "replace"
    UNDO = "undo"
    REDO = "redo"
    INSERT_AT = "insert_at"
    CAPITALIZE = "capitalize"
    NEW_LINE = "new_line"
    NEW_PARAGRAPH = "new_paragraph"
    PERIOD = "period"
    COMMA = "comma"
    QUESTION = "question"
    EXCLAMATION = "exclamation"
    STOP_LISTENING = "stop_listening"
    START_LISTENING = "start_listening"
    CLEAR = "clear"
    MOVE_CURSOR = "move_cursor"
    SELECT_ALL = "select_all"
    CORRECT = "correct"


@dataclass
class VoiceCommand:
    type: CommandType
    params: dict = field(default_factory=dict)
    confidence: float = 1.0
    original_text: str = ""


COMMAND_PATTERNS: list[tuple[re.Pattern, CommandType, Callable]] = []


def _build_patterns():
    global COMMAND_PATTERNS
    if COMMAND_PATTERNS:
        return
    COMMAND_PATTERNS = [
        (re.compile(r'\b(?:delete|remove|erase)\s+(?:that|this|the\s+last\s+one|it)\s*$', re.IGNORECASE), CommandType.DELETE_LAST, lambda m: {}),
        (re.compile(r'\b(?:delete|remove|erase)\s+(?:that|this|the\s+last\s+one|it)\s+.*?(?:no|not|don\'t|wait|scratch|actually|cancel)', re.IGNORECASE), CommandType.UNDO, lambda m: {}),
        (re.compile(r'\b(?:no|wait\s+no|scratch\s+that|never\s+mind|forget\s+it|undo|actually\s+no)\s*$', re.IGNORECASE), CommandType.UNDO, lambda m: {}),
        (re.compile(r'\b(?:oh\s+)?wait\s+no\s+not\s+(.+?)(?:\s+(?:either|actually|please|thanks|tho|though))?\s*$', re.IGNORECASE), CommandType.DELETE_PHRASE, lambda m: {'phrase': m.group(1).strip()}),
        (re.compile(r'\bno\s+not\s+(.+?)(?:\s+(?:either|actually|please|thanks|tho|though))?\s*$', re.IGNORECASE), CommandType.DELETE_PHRASE, lambda m: {'phrase': m.group(1).strip()}),
        (re.compile(r'\b(?:oh\s+)?wait\s+no\b', re.IGNORECASE), CommandType.UNDO, lambda m: {}),
        (re.compile(r'\bundo\b', re.IGNORECASE), CommandType.UNDO, lambda m: {}),
        (re.compile(r'\bre(?:do|make)\b', re.IGNORECASE), CommandType.REDO, lambda m: {}),
        (re.compile(r'\bclear\s+(?:all|everything|the\s+document)\s*$', re.IGNORECASE), CommandType.CLEAR, lambda m: {}),
        (re.compile(r'\bdelete\s+(?:all|everything)\s*$', re.IGNORECASE), CommandType.DELETE_ALL, lambda m: {}),
        (re.compile(r'\bchange\s+(.+?)\s+to\s+(.+?)\s*$', re.IGNORECASE), CommandType.REPLACE, lambda m: {'old': m.group(1).strip(), 'new': m.group(2).strip()}),
        (re.compile(r'\breplace\s+(.+?)\s+with\s+(.+?)\s*$', re.IGNORECASE), CommandType.REPLACE, lambda m: {'old': m.group(1).strip(), 'new': m.group(2).strip()}),
        (re.compile(r'\bcapitalize\s+(?:that|this|the\s+word)\s*$', re.IGNORECASE), CommandType.CAPITALIZE, lambda m: {}),
        (re.compile(r'\bnew\s+line\s*$', re.IGNORECASE), CommandType.NEW_LINE, lambda m: {}),
        (re.compile(r'\bnew\s+paragraph\s*$', re.IGNORECASE), CommandType.NEW_PARAGRAPH, lambda m: {}),
        (re.compile(r'\bperiod\s*$', re.IGNORECASE), CommandType.PERIOD, lambda m: {}),
        (re.compile(r'\bcomma\s*$', re.IGNORECASE), CommandType.COMMA, lambda m: {}),
        (re.compile(r'\bquestion\s+mark\s*$', re.IGNORECASE), CommandType.QUESTION, lambda m: {}),
        (re.compile(r'\bexclamation\s+(?:point|mark)\s*$', re.IGNORECASE), CommandType.EXCLAMATION, lambda m: {}),
        (re.compile(r'\bstop\s+(?:listening|recording)\s*$', re.IGNORECASE), CommandType.STOP_LISTENING, lambda m: {}),
        (re.compile(r'\b(?:start|resume)\s+(?:listening|recording)\s*$', re.IGNORECASE), CommandType.START_LISTENING, lambda m: {}),
        (re.compile(r'\bdelete\s+(\d+)\s+(?:words|chars?|characters?)\s*$', re.IGNORECASE), CommandType.DELETE_LAST, lambda m: {'count': int(m.group(1))}),
        (re.compile(r'\bdelete\s+(?:the\s+)?(?:word|phrase|sentence)\s+(.+?)\s*$', re.IGNORECASE), CommandType.DELETE_PHRASE, lambda m: {'phrase': m.group(1).strip()}),
        (re.compile(r'\bselect\s+all\s*$', re.IGNORECASE), CommandType.SELECT_ALL, lambda m: {}),
        (re.compile(r'\bcorrect\s+(.+?)\s+to\s+(.+?)\s*$', re.IGNORECASE), CommandType.CORRECT, lambda m: {'old': m.group(1).strip(), 'new': m.group(2).strip()}),
    ]


_build_patterns()


def parse_command(text: str) -> Optional[VoiceCommand]:
    if not text or not text.strip():
        return None
    stripped = text.strip()
    for pattern, cmd_type, param_extractor in COMMAND_PATTERNS:
        match = pattern.search(stripped)
        if match:
            params = param_extractor(match)
            return VoiceCommand(
                type=cmd_type,
                params=params,
                confidence=1.0,
                original_text=stripped,
            )
    return None


def contains_command(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    for pattern, _, _ in COMMAND_PATTERNS:
        if pattern.search(stripped):
            return True
    return False


def strip_command_from_text(text: str) -> str:
    if not text:
        return text
    result = text.strip()
    changed = True
    while changed:
        changed = False
        for pattern, _, _ in COMMAND_PATTERNS:
            new_result = pattern.sub('', result).strip()
            if new_result != result:
                result = new_result
                changed = True
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def apply_command(document: str, command: VoiceCommand, history: list[str]) -> tuple[str, Optional[VoiceCommand]]:
    if command.type == CommandType.DELETE_LAST:
        if command.params.get('count'):
            words = document.split()
            if command.params['count'] < len(words):
                return ' '.join(words[:-command.params['count']]), command
        sentences = re.split(r'(?<=[.!?])\s+', document)
        if len(sentences) >= 1:
            return ' '.join(sentences[:-1]) if len(sentences) > 1 else '', command
        words = document.split()
        return ' '.join(words[:-3]) if len(words) > 3 else '', command

    elif command.type == CommandType.UNDO:
        if history:
            return history[-1], command
        return document, command

    elif command.type == CommandType.REDO:
        return document, command

    elif command.type == CommandType.CLEAR or command.type == CommandType.DELETE_ALL:
        return '', command

    elif command.type == CommandType.REPLACE:
        old = command.params.get('old', '')
        new = command.params.get('new', '')
        if old:
            return document.replace(old, new, 1), command
        return document, command

    elif command.type == CommandType.DELETE_PHRASE:
        phrase = command.params.get('phrase', '')
        if phrase:
            idx = document.lower().rfind(phrase.lower())
            if idx >= 0:
                before = document[:idx].rstrip()
                after = document[idx + len(phrase):].lstrip()
                before = re.sub(r'\b(?:and|or|the|a|an|then|also|with|for)\s*$', '', before).rstrip()
                after = re.sub(r'^\s*(?:and|or|the|a|an|then|also|with|for)\b', '', after).lstrip()
                result = (before + ' ' + after).strip()
                return re.sub(r'\s+', ' ', result), command
        return document, command

    elif command.type == CommandType.CORRECT:
        old = command.params.get('old', '')
        new = command.params.get('new', '')
        if old:
            return document.replace(old, new, 1), command
        return document, command

    elif command.type == CommandType.CAPITALIZE:
        words = document.split()
        if words:
            words[-1] = words[-1].capitalize()
            return ' '.join(words), command
        return document, command

    elif command.type == CommandType.NEW_LINE:
        return document + '\n', command

    elif command.type == CommandType.NEW_PARAGRAPH:
        return document + '\n\n', command

    elif command.type == CommandType.PERIOD:
        return document.rstrip() + '.', command

    elif command.type == CommandType.COMMA:
        return document.rstrip() + ',', command

    elif command.type == CommandType.QUESTION:
        return document.rstrip() + '?', command

    elif command.type == CommandType.EXCLAMATION:
        return document.rstrip() + '!', command

    elif command.type == CommandType.SELECT_ALL:
        return document, command

    return document, command


def _dedup_append(document: str, new_text: str) -> str:
    if not document:
        return new_text
    if not new_text:
        return document
    doc_words = document.split()
    new_words = new_text.split()
    for overlap in range(min(len(new_words), len(doc_words)), 0, -1):
        if doc_words[-overlap:] == new_words[:overlap]:
            return document + ' ' + ' '.join(new_words[overlap:])
    return document + ' ' + new_text


_FILLER_WORDS = {'actually', 'basically', 'honestly', 'literally', 'so', 'well', 'okay', 'ok', 'right', 'now', 'then'}


def _is_filler(text: str) -> bool:
    words = text.strip().lower().split()
    return len(words) <= 2 and all(w.strip('.,!?') in _FILLER_WORDS for w in words)


def process_utterance(document: str, utterance: str, history: list[str]) -> tuple[str, Optional[VoiceCommand], Optional[str]]:
    if not utterance or not utterance.strip():
        return document, None, None
    command = parse_command(utterance)
    if command:
        clean_text = strip_command_from_text(utterance)
        if clean_text and not _is_filler(clean_text):
            interim = _dedup_append(document, clean_text) if document else clean_text
        else:
            interim = document
        new_doc, _ = apply_command(interim, command, history)
        return new_doc, command, utterance
    else:
        new_doc = _dedup_append(document, utterance) if document else utterance
        return new_doc, None, None
