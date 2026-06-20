import pytest
from lloyd_voice.core.commands import (
    parse_command, contains_command, strip_command_from_text,
    apply_command, process_utterance, CommandType,
)


class TestParseCommand:
    def test_delete_last(self):
        cmd = parse_command("delete that")
        assert cmd is not None
        assert cmd.type == CommandType.DELETE_LAST

        cmd = parse_command("remove that")
        assert cmd is not None
        assert cmd.type == CommandType.DELETE_LAST

    def test_undo(self):
        cmd = parse_command("no")
        assert cmd is not None
        assert cmd.type == CommandType.UNDO

        cmd = parse_command("undo")
        assert cmd is not None
        assert cmd.type == CommandType.UNDO

        cmd = parse_command("wait no")
        assert cmd is not None
        assert cmd.type == CommandType.UNDO

    def test_clear(self):
        cmd = parse_command("clear all")
        assert cmd is not None
        assert cmd.type == CommandType.CLEAR

        cmd = parse_command("clear everything")
        assert cmd is not None
        assert cmd.type == CommandType.CLEAR

    def test_replace(self):
        cmd = parse_command("change hello to hi")
        assert cmd is not None
        assert cmd.type == CommandType.REPLACE
        assert cmd.params["old"] == "hello"
        assert cmd.params["new"] == "hi"

    def test_punctuation(self):
        cmd = parse_command("period")
        assert cmd is not None
        assert cmd.type == CommandType.PERIOD

        cmd = parse_command("comma")
        assert cmd is not None
        assert cmd.type == CommandType.COMMA

    def test_no_command(self):
        cmd = parse_command("this is normal speech")
        assert cmd is None

        cmd = parse_command("")
        assert cmd is None


class TestContainsCommand:
    def test_contains(self):
        assert contains_command("delete that")
        assert contains_command("no undo")
        assert not contains_command("normal speech here")
        assert not contains_command("")


class TestStripCommand:
    def test_strip(self):
        result = strip_command_from_text("delete that")
        assert result == ""

        result = strip_command_from_text("hello there period")
        assert result == "hello there"

        result = strip_command_from_text("no undo")
        assert result == ""


class TestApplyCommand:
    def test_delete_last(self):
        doc = "first sentence. second sentence."
        cmd = parse_command("delete that")
        new_doc, _ = apply_command(doc, cmd, [])
        assert new_doc == "first sentence."

    def test_clear(self):
        doc = "some text here"
        cmd = parse_command("clear all")
        new_doc, _ = apply_command(doc, cmd, [])
        assert new_doc == ""

    def test_replace(self):
        doc = "hello world"
        cmd = parse_command("change hello to hi")
        new_doc, _ = apply_command(doc, cmd, [])
        assert new_doc == "hi world"

    def test_punctuation(self):
        doc = "hello"
        cmd = parse_command("period")
        new_doc, _ = apply_command(doc, cmd, [])
        assert new_doc == "hello."


class TestProcessUtterance:
    def test_normal_speech(self):
        doc = ""
        new_doc, cmd, _ = process_utterance(doc, "hello world", [])
        assert new_doc == "hello world"
        assert cmd is None

    def test_command_only(self):
        doc = "some text"
        new_doc, cmd, _ = process_utterance(doc, "undo", [])
        assert cmd is not None
        assert cmd.type == CommandType.UNDO

    def test_appending_speech(self):
        doc = "hello"
        new_doc, cmd, _ = process_utterance(doc, "world", [])
        assert new_doc == "hello world"
        assert cmd is None

    def test_punctuation_with_content(self):
        doc = ""
        new_doc, cmd, _ = process_utterance(doc, "this is great period", [])
        assert cmd is not None
        assert cmd.type == CommandType.PERIOD
        assert new_doc == "this is great."

    def test_period_appended_to_existing(self):
        doc = "hello"
        new_doc, cmd, _ = process_utterance(doc, "world period", [])
        assert cmd is not None
        assert cmd.type == CommandType.PERIOD
        assert new_doc == "hello world."
