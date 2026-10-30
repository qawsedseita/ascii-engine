"""Audio events, routing, synthesis, and optional OS playback.

WAV synthesis is pure standard library. Device playback depends on an external OS command
and is deliberately not exercised by the automated tests/sandbox.
"""
from __future__ import annotations
import math, shutil, struct, subprocess, tempfile, wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from ..core.errors import EngineError

@dataclass
class AudioEvent:
    name: str
    frequency: float = 440.0
    duration: float = 0.12
    volume: float = 0.25
    channel: str = "sfx"
    position: Optional[tuple[int,int]] = None

class AudioBackend:
    def play(self, wav_path: str, *, volume: float = 1.0):
        raise NotImplementedError

class NullBackend(AudioBackend):
    def play(self, wav_path: str, *, volume: float = 1.0): return {"played": False, "reason": "silent backend"}

class CommandPlaybackBackend(AudioBackend):
    """Delegates to a local player command (afplay, aplay, or paplay)."""
    COMMANDS = ("afplay", "aplay", "paplay")
    def __init__(self, command: Optional[str] = None):
        self.command = command or next((shutil.which(c) for c in self.COMMANDS if shutil.which(c)), None)
    def play(self, wav_path: str, *, volume: float = 1.0):
        if not self.command: raise EngineError("No supported audio player found", "Install afplay, aplay, or paplay", "no_audio_backend")
        # Volume is intentionally not imposed on backend commands because their flags differ.
        subprocess.Popen([self.command, str(wav_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"played": True, "command": self.command}

class WavSynthesizer:
    """Generate small mono 16-bit PCM tones with an optional attack/release envelope."""
    def __init__(self, sample_rate: int = 22050):
        if sample_rate < 8000: raise EngineError("Sample rate is too low", "Use at least 8000 Hz", "bad_sample_rate")
        self.sample_rate = sample_rate
    def tone(self, frequency: float = 440.0, duration: float = 0.12, volume: float = 0.25, waveform: str = "sine") -> bytes:
        if frequency <= 0 or duration <= 0 or duration > 30 or not 0 <= volume <= 1:
            raise EngineError("Invalid tone parameters", "Use positive frequency, duration ≤30s and volume 0..1", "bad_audio_parameters")
        if waveform not in ("sine", "square", "triangle"):
            raise EngineError("Unsupported waveform", "Choose sine, square, or triangle", "bad_waveform")
        count = int(self.sample_rate * duration); frames = bytearray()
        attack = max(1, int(self.sample_rate * 0.005)); release = max(1, int(self.sample_rate * 0.02))
        for i in range(count):
            phase = 2 * math.pi * frequency * i / self.sample_rate
            if waveform == "sine": value = math.sin(phase)
            elif waveform == "square": value = 1.0 if math.sin(phase) >= 0 else -1.0
            else: value = 2.0 / math.pi * math.asin(math.sin(phase))
            env = min(1.0, i / attack, (count - i) / release)
            sample = max(-32767, min(32767, int(value * volume * max(0.0, env) * 32767)))
            frames.extend(struct.pack("<h", sample))
        from io import BytesIO
        out=BytesIO()
        with wave.open(out,"wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(self.sample_rate); wf.writeframes(bytes(frames))
        return out.getvalue()
    def save_tone(self, path, **kwargs):
        data=self.tone(**kwargs); Path(path).write_bytes(data); return str(path)

class AudioSystem:
    def __init__(self, backend: Optional[AudioBackend] = None, synthesizer: Optional[WavSynthesizer] = None):
        self.backend = backend or NullBackend(); self.synth = synthesizer or WavSynthesizer()
        self.channels = {"music": 1.0, "sfx": 1.0, "ui": 1.0, "ambience": 1.0}
        self.events: list[AudioEvent] = []; self._transition = {k: 1.0 for k in self.channels}
    def set_channel(self, channel: str, volume: float):
        if channel not in self.channels or not 0 <= volume <= 1: raise EngineError("Invalid audio channel/volume", "Known channels: music, sfx, ui, ambience; volume 0..1", "bad_channel")
        self.channels[channel] = volume
    def transition(self, channel: str, target: float, steps: int = 10):
        if channel not in self.channels or not 0 <= target <= 1 or steps < 1: raise EngineError("Invalid transition", "Use a known channel, target 0..1, steps≥1", "bad_transition")
        current = self._transition[channel]; delta = (target-current)/steps
        levels = [current + delta*(i+1) for i in range(steps)]
        self._transition[channel] = target; self.channels[channel] = target
        return levels
    def positional_gain(self, event: AudioEvent, listener: Optional[tuple[int,int]], radius: float = 12.0):
        if event.position is None or listener is None: return 1.0
        dist=math.hypot(event.position[0]-listener[0], event.position[1]-listener[1])
        return max(0.0, 1.0-dist/max(0.001,radius))
    def emit(self, event: AudioEvent, *, listener=None, path=None):
        self.events.append(event); gain=self.channels.get(event.channel, 0.0)*event.volume*self.positional_gain(event,listener)
        if gain <= 0: return {"ok": True, "played": False, "gain": 0.0}
        wav_path = path
        if wav_path is None:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(self.synth.tone(event.frequency,event.duration,min(1,gain))); wav_path=f.name
        return {"ok": True, "gain": gain, **self.backend.play(str(wav_path), volume=gain)}
