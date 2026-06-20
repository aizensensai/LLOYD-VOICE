"""21 realistic dictation scenarios - fumble-heavy."""
import sys
sys.path.insert(0, r'C:\Users\DELL\voice-prism\src')

from lloyd_voice.core.commands import process_utterance

def run():
    scenarios = [
        ("plain dictation", "", "hello world", "hello world"),
        ("append to existing", "hello", "world", "hello world"),
        ("end with period", "", "this is great period", "this is great."),
        ("append then period", "hello", "world period", "hello world."),
        ("end with question", "", "are you sure question mark", "are you sure?"),
        ("end with exclamation", "", "wow exclamation point", "wow!"),
        ("comma at end", "", "first comma", "first,"),
        ("delete last sentence", "keep this. remove this.", "delete that", "keep this."),
        ("clear all", "some text here", "clear all", ""),
        ("replace word", "hello world", "change hello to hi", "hi world"),
        ("insert newline", "line one", "new line", "line one\n"),
        ("wait no remove phrase", "task one", "wait no not task one", ""),
        ("oh wait no full remove", "hello", "oh wait no not hello", ""),
        ("no not short form", "foo bar", "no not foo bar", ""),
        ("connector cleanup", "task one and task two", "no not task two", "task one"),
        ("exact repeat dedup", "we will discuss", "we will discuss", "we will discuss"),
        ("partial overlap dedup", "hello world", "world peace", "hello world peace"),
        ("filler stripped with cmd", "", "actually period", "."),
        ("multi filler stripped", "", "actually we are done period", "we are done."),
        ("capitalize standalone", "", "hello world capitalize", "Hello world"),
        ("capitalize first word", "hello world", "capitalize that", "Hello world"),
    ]

    passed = 0
    failed = 0
    details = []

    for name, doc, utterance, expected in scenarios:
        new_doc, cmd, _ = process_utterance(doc, utterance, [])
        ok = new_doc.rstrip() == expected.rstrip()
        if ok:
            passed += 1
            details.append(f"  OK {name}")
        else:
            failed += 1
            details.append(f"  FAIL {name}")
            details.append(f"       doc:      '{doc}'")
            details.append(f"       input:    '{utterance}'")
            details.append(f"       expected: '{expected}'")
            details.append(f"       got:      '{new_doc}'")

    print()
    print("=" * 60)
    print("  21 SIMULATION SCENARIOS (fumble-heavy)")
    print("=" * 60)
    for d in details:
        print(d)
    print("=" * 60)
    print(f"  PASSED: {passed}/{len(scenarios)}")
    if failed:
        print(f"  FAILED: {failed}")
    else:
        print(f"  ALL PASSED!")
    print("=" * 60)
    print()
    return failed == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
