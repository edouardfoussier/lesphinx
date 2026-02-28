"""Generate simple SFX WAV files for LeSphinx using synthesis."""

import math
import struct
import wave
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "lesphinx" / "static" / "sfx"
SAMPLE_RATE = 44100


def write_wav(filename: str, samples: list[float], sample_rate: int = SAMPLE_RATE):
    path = OUTPUT_DIR / filename
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            f.writeframes(struct.pack("<h", int(clamped * 32767)))
    print(f"  Created {path.name} ({len(samples) / sample_rate:.2f}s)")


def envelope(t: float, attack: float, sustain: float, release: float, total: float) -> float:
    if t < attack:
        return t / attack
    elif t < attack + sustain:
        return 1.0
    elif t < total:
        return max(0, 1.0 - (t - attack - sustain) / release)
    return 0.0


def generate_tick():
    duration = 0.08
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 60)
        s = env * math.sin(2 * math.pi * 800 * t) * 0.7
        samples.append(s)
    write_wav("tick.wav", samples)


def generate_ding():
    duration = 0.6
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 5)
        s = env * (
            0.5 * math.sin(2 * math.pi * 880 * t) +
            0.3 * math.sin(2 * math.pi * 1320 * t) +
            0.2 * math.sin(2 * math.pi * 1760 * t)
        )
        samples.append(s * 0.6)
    write_wav("ding.wav", samples)


def generate_whoosh():
    import random
    random.seed(42)
    duration = 0.4
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.sin(math.pi * t / duration) ** 2
        noise = random.uniform(-1, 1)
        freq = 200 + 800 * (t / duration)
        tone = 0.3 * math.sin(2 * math.pi * freq * t)
        samples.append(env * (0.4 * noise + tone) * 0.5)
    write_wav("whoosh.wav", samples)


def generate_fanfare():
    duration = 1.2
    n = int(SAMPLE_RATE * duration)
    notes = [
        (523.25, 0.0, 0.3),   # C5
        (659.25, 0.15, 0.3),  # E5
        (783.99, 0.3, 0.3),   # G5
        (1046.5, 0.5, 0.7),   # C6 (held)
    ]
    samples = [0.0] * n
    for freq, start, dur in notes:
        for i in range(int(start * SAMPLE_RATE), min(n, int((start + dur) * SAMPLE_RATE))):
            t = (i - int(start * SAMPLE_RATE)) / SAMPLE_RATE
            env = envelope(t, 0.02, dur * 0.5, dur * 0.5, dur)
            s = env * (
                0.5 * math.sin(2 * math.pi * freq * t) +
                0.2 * math.sin(2 * math.pi * freq * 2 * t) +
                0.1 * math.sin(2 * math.pi * freq * 3 * t)
            )
            samples[i] += s * 0.4
    write_wav("fanfare.wav", samples)


def generate_gong():
    duration = 2.0
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        env = math.exp(-t * 1.5)
        s = env * (
            0.4 * math.sin(2 * math.pi * 100 * t) +
            0.3 * math.sin(2 * math.pi * 150 * t) +
            0.15 * math.sin(2 * math.pi * 200 * t * (1 + 0.01 * math.sin(5 * t))) +
            0.1 * math.sin(2 * math.pi * 300 * t) +
            0.05 * math.sin(2 * math.pi * 450 * t)
        )
        samples.append(s * 0.7)
    write_wav("gong.wav", samples)


def generate_ambient_loop():
    """Generate a simple ambient drone loop (~8 seconds)."""
    duration = 8.0
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        fade_in = min(1.0, t / 1.0)
        fade_out = min(1.0, (duration - t) / 1.0)
        env = fade_in * fade_out

        drone = (
            0.25 * math.sin(2 * math.pi * 55 * t) +
            0.15 * math.sin(2 * math.pi * 82.5 * t) +
            0.10 * math.sin(2 * math.pi * 110 * t) +
            0.08 * math.sin(2 * math.pi * 165 * t + math.sin(0.3 * t) * 0.5)
        )
        shimmer = 0.04 * math.sin(2 * math.pi * 440 * t + 2 * math.sin(0.5 * t))
        pad = 0.06 * math.sin(2 * math.pi * 220 * t * (1 + 0.002 * math.sin(0.2 * t)))

        samples.append(env * (drone + shimmer + pad) * 0.5)
    write_wav("ambient.wav", samples)


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Generating SFX...")
    generate_tick()
    generate_ding()
    generate_whoosh()
    generate_fanfare()
    generate_gong()
    generate_ambient_loop()
    print("Done!")
