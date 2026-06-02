"""Scale database and mapping helpers for Phase 6.

Provides a catalog of Western, Pentatonic, Arabic, and Indian scales/ragas,
along with helper functions to parse note names, get absolute MIDI pitches,
and list scale degrees.
"""

from __future__ import annotations

import re

# Database of scales and ragas
SCALES_CATALOGUE: dict[str, dict] = {
    # -- Western Modes --
    "major": {
        "name": "Major (Ionian)",
        "family": "Western",
        "intervals": [0, 2, 4, 5, 7, 9, 11],
        "mood": "happy, bright, triumphant",
    },
    "minor": {
        "name": "Natural Minor (Aeolian)",
        "family": "Western",
        "intervals": [0, 2, 3, 5, 7, 8, 10],
        "mood": "sad, melancholic, reflective",
    },
    "dorian": {
        "name": "Dorian",
        "family": "Western",
        "intervals": [0, 2, 3, 5, 7, 9, 10],
        "mood": "thoughtful, jazz-like, mystical",
    },
    "phrygian": {
        "name": "Phrygian",
        "family": "Western",
        "intervals": [0, 1, 3, 5, 7, 8, 10],
        "mood": "tense, exotic, dark",
    },
    "lydian": {
        "name": "Lydian",
        "family": "Western",
        "intervals": [0, 2, 4, 6, 7, 9, 11],
        "mood": "dreamy, ethereal, spacey",
    },
    "mixolydian": {
        "name": "Mixolydian",
        "family": "Western",
        "intervals": [0, 2, 4, 5, 7, 9, 10],
        "mood": "bluesy, positive, classic rock",
    },
    "locrian": {
        "name": "Locrian",
        "family": "Western",
        "intervals": [0, 1, 3, 5, 6, 8, 10],
        "mood": "unstable, tense, dissonant",
    },
    "harmonic_minor": {
        "name": "Harmonic Minor",
        "family": "Western",
        "intervals": [0, 2, 3, 5, 7, 8, 11],
        "mood": "dramatic, classical, middle-eastern flavor",
    },
    "melodic_minor": {
        "name": "Melodic Minor",
        "family": "Western",
        "intervals": [0, 2, 3, 5, 7, 9, 11],
        "mood": "mysterious, sophisticated, jazz minor",
    },
    # -- Pentatonics --
    "major_pentatonic": {
        "name": "Major Pentatonic",
        "family": "Pentatonic",
        "intervals": [0, 2, 4, 7, 9],
        "mood": "open, simple, folk-like",
    },
    "minor_pentatonic": {
        "name": "Minor Pentatonic",
        "family": "Pentatonic",
        "intervals": [0, 3, 5, 7, 10],
        "mood": "bluesy, earthy, rock solo staple",
    },
    # -- Arabic Maqams (12-TET Approximations) --
    "maqam_rast": {
        "name": "Maqam Rast",
        "family": "Arabic Maqam",
        "intervals": [0, 2, 4, 5, 7, 9, 11],
        "mood": "traditional, majestic, authoritative",
    },
    "maqam_bayati": {
        "name": "Maqam Bayati",
        "family": "Arabic Maqam",
        "intervals": [0, 1, 3, 5, 7, 8, 10],
        "mood": "warm, narrative, deeply emotional",
    },
    "maqam_hijaz": {
        "name": "Maqam Hijaz",
        "family": "Arabic Maqam",
        "intervals": [0, 1, 4, 5, 7, 8, 10],
        "mood": "exotic, passionate, yearning",
    },
    "maqam_saba": {
        "name": "Maqam Saba",
        "family": "Arabic Maqam",
        "intervals": [0, 1, 3, 4, 7, 8, 10],
        "mood": "sad, grieving, highly spiritual",
    },
    "maqam_nahawand": {
        "name": "Maqam Nahawand",
        "family": "Arabic Maqam",
        "intervals": [0, 2, 3, 5, 7, 8, 10],
        "mood": "romantic, dramatic, elegant",
    },
    "maqam_kurd": {
        "name": "Maqam Kurd",
        "family": "Arabic Maqam",
        "intervals": [0, 1, 3, 5, 7, 8, 10],
        "mood": "dreamy, direct, poignant",
    },
    # -- Indian Ragas: Melakarta (Parent Scales) --
    "mayamalavagowla": {
        "name": "Mayamalavagowla (Raga Bhairav Thaat)",
        "family": "Melakarta Raga",
        "intervals": [0, 1, 4, 5, 7, 8, 11],
        "mood": "devotional, peaceful, early morning",
    },
    "shankarabharanam": {
        "name": "Dheerasankarabharanam (Raga Bilawal Thaat)",
        "family": "Melakarta Raga",
        "intervals": [0, 2, 4, 5, 7, 9, 11],
        "mood": "bright, majestic, grand",
    },
    "kharaharapriya": {
        "name": "Kharaharapriya (Raga Kafi Thaat)",
        "family": "Melakarta Raga",
        "intervals": [0, 2, 3, 5, 7, 9, 10],
        "mood": "devotional, aesthetic beauty, emotional",
    },
    "kalyani": {
        "name": "MechaKalyani (Raga Yaman Thaat)",
        "family": "Melakarta Raga",
        "intervals": [0, 2, 4, 6, 7, 9, 11],
        "mood": "joyous, evening light, auspicious",
    },
    "todi": {
        "name": "Hanumatodi (Raga Bhairavi Thaat)",
        "family": "Melakarta Raga",
        "intervals": [0, 1, 3, 5, 7, 8, 10],
        "mood": "sad, yearning, deeply devotional",
    },
    "charukesi": {
        "name": "Charukesi",
        "family": "Melakarta Raga",
        "intervals": [0, 2, 4, 5, 7, 8, 10],
        "mood": "sweet, poignant, cinematic, mix of joy and sadness",
    },
    # -- Indian Ragas: Janya (Derived Scales, some with asymmetric asc/desc) --
    "mohanam": {
        "name": "Mohanam (Raga Bhupali)",
        "family": "Janya Raga",
        "intervals": [0, 2, 4, 7, 9],
        "mood": "cheerful, positive, universally appealing",
    },
    "hamsadhwani": {
        "name": "Hamsadhwani",
        "family": "Janya Raga",
        "intervals": [0, 2, 4, 7, 11],
        "mood": "bright, energetic, invocation, auspicious start",
    },
    "hindolam": {
        "name": "Hindolam (Raga Malkauns)",
        "family": "Janya Raga",
        "intervals": [0, 3, 5, 8, 10],
        "mood": "deeply meditative, calm, midnight mystery",
    },
    "abheri": {
        "name": "Abheri (Raga Bhimpalasi)",
        "family": "Janya Raga",
        "intervals_asc": [0, 3, 5, 7, 10],  # pentatonic ascending (Sa Ga Ma Pa Ni)
        "intervals_desc": [0, 2, 3, 5, 7, 9, 10],  # heptatonic descending (Sa Ni Dha Pa Ma Ga Ri)
        "mood": "tender, romantic, devotional, afternoon",
    },
    "bhairavi": {
        "name": "Bhairavi (Carnatic Bhairavi)",
        "family": "Janya Raga",
        # Asymmetric in classical Carnatic performance:
        "intervals_asc": [0, 2, 3, 5, 7, 9, 10],
        "intervals_desc": [0, 1, 3, 5, 7, 8, 10],
        "mood": "majestic, emotional depth, versatile",
    },
    "sriranjani": {
        "name": "Sriranjani",
        "family": "Janya Raga",
        "intervals": [0, 2, 3, 5, 9, 10],  # No Pa (Sa Ri Ga Ma Dha Ni)
        "mood": "scholarly, beautiful, pleasant, light",
    },
}


def parse_root_note(val: str | int) -> int:
    """Convert a note name (e.g. 'C5', 'A#4') or MIDI number to a MIDI note number."""
    if isinstance(val, int):
        if 0 <= val <= 127:
            return val
        raise ValueError(f"MIDI note {val} out of range [0, 127]")

    val_str = str(val).strip().upper()
    if not val_str:
        raise ValueError("Empty root note")

    if val_str.isdigit():
        n = int(val_str)
        if 0 <= n <= 127:
            return n
        raise ValueError(f"MIDI note {n} out of range [0, 127]")

    m = re.match(r"^([A-G]#?|D[B]?|E[B]?|G[B]?|A[B]?|B[B]?)(-?\d+)$", val_str)
    if not m:
        raise ValueError(f"Invalid note format: {val!r}. Use names like 'C5' or integers.")

    name, octave_str = m.groups()
    octave = int(octave_str)

    flats = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
    if name in flats:
        name = flats[name]

    offsets = {
        "C": 0,
        "C#": 1,
        "D": 2,
        "D#": 3,
        "E": 4,
        "F": 5,
        "F#": 6,
        "G": 7,
        "G#": 8,
        "A": 9,
        "A#": 10,
        "B": 11,
    }

    base = offsets[name]
    midi_num = base + octave * 12

    if 0 <= midi_num <= 127:
        return midi_num
    raise ValueError(f"Calculated MIDI note {midi_num} out of range [0, 127]")


def midi_to_note_name(midi_num: int) -> str:
    """Convert a MIDI note number to scientific pitch notation (e.g., 60 -> 'C5')."""
    if not (0 <= midi_num <= 127):
        return "Unknown"
    note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = midi_num // 12
    name = note_names[midi_num % 12]
    return f"{name}{octave}"


def find_scale(query: str) -> tuple[str, dict] | None:
    """Find a scale in the catalogue, using forgiving case-insensitive lookup."""
    normalized = query.strip().lower().replace(" ", "_").replace("-", "_")

    # Try exact match
    if normalized in SCALES_CATALOGUE:
        return normalized, SCALES_CATALOGUE[normalized]

    # Try match without 'raga_' or 'maqam_' prefix
    for prefix in ["raga_", "maqam_"]:
        if normalized.startswith(prefix) and normalized[len(prefix) :] in SCALES_CATALOGUE:
            k = normalized[len(prefix) :]
            return k, SCALES_CATALOGUE[k]

    # Try matching keys that contain query
    matches = [k for k in SCALES_CATALOGUE if normalized in k]
    if len(matches) == 1:
        return matches[0], SCALES_CATALOGUE[matches[0]]

    return None


def get_scale_notes(scale_name: str, root_note: str | int, octave_range: int = 1) -> dict:
    """Get MIDI note details for a scale relative to a root note and octave range."""
    found = find_scale(scale_name)
    if not found:
        raise ValueError(
            f"Scale/Raga {scale_name!r} not found. "
            f"Available scales: {list(SCALES_CATALOGUE.keys())}"
        )

    key, sdef = found
    root_midi = parse_root_note(root_note)

    # Extract intervals
    if "intervals" in sdef:
        asc_ints = sdef["intervals"]
        desc_ints = sdef["intervals"]
    else:
        asc_ints = sdef["intervals_asc"]
        desc_ints = sdef["intervals_desc"]

    # Build MIDI notes across the octave range
    notes_asc = []
    notes_desc = []

    for oct_idx in range(octave_range):
        offset = oct_idx * 12
        for val in asc_ints:
            midi = root_midi + offset + val
            if 0 <= midi <= 127:
                notes_asc.append(midi)
        for val in desc_ints:
            midi = root_midi + offset + val
            if 0 <= midi <= 127:
                notes_desc.append(midi)

    # Sort ascending notes; keep descending notes top-down.
    notes_asc = sorted(list(set(notes_asc)))

    # Descending notes are usually played top-down. Let's make desc notes descending in pitch order
    # (reversing sorted unique values)
    notes_desc = sorted(list(set(notes_desc)), reverse=True)

    return {
        "key": key,
        "scale_name": sdef["name"],
        "family": sdef["family"],
        "root_note": midi_to_note_name(root_midi),
        "root_midi": root_midi,
        "notes_asc": notes_asc,
        "notes_desc": notes_desc,
        "names_asc": [midi_to_note_name(m) for m in notes_asc],
        "names_desc": [midi_to_note_name(m) for m in notes_desc],
        "mood": sdef["mood"],
    }
