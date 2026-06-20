"""Basic example of using Lloyd Voice as a Python library."""
import time
import threading

from lloyd_voice.core.audio import AudioCapture
from lloyd_voice.core.transcriber import Transcriber
from lloyd_voice.session.context import SessionContext


def print_result(result):
    if result.text.strip():
        print(f"[{'FINAL' if result.is_final else 'PARTIAL'}] {result.text}")


def main():
    print("Lloyd Voice Library Example")
    print("Recording for 10 seconds... Speak now!\n")

    context = SessionContext()
    transcriber = Transcriber(model_size="base")
    transcriber.on_result(print_result)

    capture = AudioCapture()
    capture.start()

    stop_event = threading.Event()

    def process_audio():
        for chunk in capture.iter_chunks(stop_event):
            transcriber.transcribe_streaming([chunk])

    thread = threading.Thread(target=process_audio, daemon=True)
    thread.start()

    try:
        time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        capture.stop()
        transcriber.cleanup()

    print(f"\n\nSession summary:")
    summary = context.summarize()
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
