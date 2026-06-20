import asyncio
import sys
import logging

import click

from lloyd_voice.ui.app import LloydVoiceServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0", prog_name="lloyd-voice")
def main():
    """Lloyd Voice — Open-source voice dictation with real-time transcription,
    voice editing commands, and a rainbow waveform UI."""
    pass


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
@click.option("--port", default=8765, help="Port to bind to (default: 8765)")
@click.option("--model", default="base", help="Whisper model size: tiny, base, small, medium, large-v3 (default: base)")
@click.option("--device", default="auto", help="Device: auto, cpu, cuda (default: auto)")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def serve(host, port, model, device, debug):
    """Start the Lloyd Voice web server with the rainbow waveform UI."""
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = LloydVoiceServer(
        host=host,
        port=port,
        model_size=model,
        device=device,
    )

    try:
        asyncio.run(server.start())
        click.echo("Press Ctrl+C to stop")
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        click.echo("\nShutting down...")
        asyncio.run(server.stop())
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--model", default="base", help="Whisper model size")
@click.option("--device", default="auto", help="Device: auto, cpu, cuda")
@click.option("--file", type=click.Path(exists=True), help="Transcribe an audio file instead of microphone")
@click.option("--language", default=None, help="Language code (auto-detect if not set)")
def transcribe(model, device, file, language):
    """Transcribe audio from microphone or file."""
    from lloyd_voice.core.transcriber import Transcriber

    transcriber = Transcriber(model_size=model, device=device)
    transcriber.load_model()

    if file:
        click.echo(f"Transcribing {file}...")
        import soundfile as sf
        audio, sr = sf.read(file)
        if len(audio.shape) > 1:
            audio = audio.mean(axis=1)
        result = transcriber.transcribe_sync(audio)
        click.echo(result)
    else:
        click.echo("Recording from microphone... Press Ctrl+C to stop")
        click.echo(f"Model: {model} on {device}")
    from lloyd_voice.core.audio import AudioCapture
        import threading

        capture = AudioCapture()

        def on_result(result):
            if result.text.strip():
                click.echo(result.text, nl=False)

        transcriber.on_result(on_result)
        capture.start()
        stop_event = threading.Event()

        try:
            for chunk in capture.iter_chunks(stop_event):
                transcriber.transcribe_streaming([chunk])
        except KeyboardInterrupt:
            pass
        finally:
            capture.stop()
            transcriber.cleanup()


@main.command()
@click.option("--host", default="127.0.0.1", help="Server host")
@click.option("--port", default=8765, help="Server port")
@click.option("--inject", is_flag=True, help="Auto-inject transcribed text into active window")
def listen(host, port, inject):
    """CLI-only listening mode (no web UI). Transcribes to stdout."""
    import threading
    from lloyd_voice.core.audio import AudioCapture
    from lloyd_voice.core.transcriber import Transcriber

    capture = AudioCapture()
    transcriber = Transcriber()

    def on_result(result):
        if result.text.strip():
            click.echo(result.text)

    def on_level(level):
        bars = int(level.rms * 100)
        bar_str = "█" * min(bars, 40)
        sys.stdout.write(f"\r{bar_str}")
        sys.stdout.flush()

    transcriber.on_result(on_result)
    capture.on_level(on_level)
    capture.start()
    stop_event = threading.Event()

    click.echo(f"Lloyd Voice listening... Press Ctrl+C to stop")
    try:
        for chunk in capture.iter_chunks(stop_event):
            transcriber.transcribe_streaming([chunk])
    except KeyboardInterrupt:
        click.echo("\nStopped.")
    finally:
        capture.stop()
        transcriber.cleanup()


@main.command()
def version():
    """Show version information."""
    from lloyd_voice import __version__
    click.echo(f"Lloyd Voice v{__version__}")


if __name__ == "__main__":
    main()
