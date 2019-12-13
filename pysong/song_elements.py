"""A collection of classes used to define a Song."""

from copy import deepcopy
from enum import Enum
from functools import total_ordering

from pysong.exceptions import ArgumentError


class TimeSignature:
    """Represents a time signature."""
    def __init__(self, numerator=4, denominator=4):
        self.numerator = numerator
        self.denominator = denominator

    def __repr__(self):
        return '%d/%d' % (self.numerator, self.denominator)

    def __eq__(self, ts2):
        return (isinstance(ts2, TimeSignature)
                and self.numerator == ts2.numerator
                and self.denominator == ts2.denominator)

    def __ne__(self, ts2):
        return not self == ts2


class Mode(Enum):
    """Enum to represent Major/Minor mode."""
    MAJOR = 0
    MINOR = 1


# Lookup tables mapping from pitch class (0-11) to string name of key.
_PC_TO_NAME_MAJOR = ('C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B')
_PC_TO_NAME_MINOR = ('C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'Bb', 'B')

# Lookup tables mapping from # sharps to pitch class and vice versa.
_SHARPS_TO_TONIC_MAJOR = {i: (7 * i) % 12 for i in range(-6, 7)}
_SHARPS_TO_TONIC_MINOR = {i: (7 * i - 3) % 12 for i in range(-6, 7)}
_TONIC_TO_SHARPS_MAJOR = {_SHARPS_TO_TONIC_MAJOR[i]: i for i in range(-6, 7)}
_TONIC_TO_SHARPS_MINOR = {_SHARPS_TO_TONIC_MINOR[i]: i for i in range(-6, 7)}

class Key:
    """Represents a musical key signature."""
    def __init__(self, tonic_pitch_class=None, num_sharps=None, mode=Mode.MAJOR):
        """Must specify either tonic_pitch_class or num_sharps.
        tonic_pitch_class: 0-11. 0=C, 1=C#, etc.
        num_sharps: positive number for # sharps. Negative number represents # of flats.
        mode: Mode enum. MAJOR or MINOR.
        """
        if ((tonic_pitch_class is None and num_sharps is None)
                or (tonic_pitch_class is not None and num_sharps is not None)):
            raise ArgumentError('Specify exactly one of {tonic_pitch_class, num_sharps}')

        assert isinstance(mode, Mode)
        self.mode = mode

        if tonic_pitch_class is not None:
            assert tonic_pitch_class >= 0 and tonic_pitch_class < 12
            self.tonic_pitch_class = tonic_pitch_class
        else:
            assert num_sharps > -7 and num_sharps < 7
            if mode == Mode.MAJOR:
                self.tonic_pitch_class = _SHARPS_TO_TONIC_MAJOR[num_sharps]
            else:
                self.tonic_pitch_class = _SHARPS_TO_TONIC_MINOR[num_sharps]

    def __repr__(self):
        if self.mode == Mode.MAJOR:
            name_map = _PC_TO_NAME_MAJOR
        else:
            name_map = _PC_TO_NAME_MINOR
        return '%s %s' % (name_map[self.tonic_pitch_class], self.mode.name)

    def __eq__(self, key2):
        return (isinstance(key2, Key)
                and self.tonic_pitch_class == key2.tonic_pitch_class
                and self.mode == key2.mode)

    def number_of_sharps(self):
        """Returns the number of sharps in the key signature, or negative numbers for the number
        of flats, as in MIDI key signatures."""
        if self.mode == Mode.MAJOR:
            return _TONIC_TO_SHARPS_MAJOR[self.tonic_pitch_class]
        return _TONIC_TO_SHARPS_MINOR[self.tonic_pitch_class]



class TrackType(Enum):
    """Enum to represent JukeDeck-style type of a track (Melody/Harmony/etc.)"""
    UNKNOWN = 0
    MELODY = 1
    HARMONY = 2
    BASS = 3
    DRUMS = 4
    FX = 5


class Track:
    """Stores a single track (instrument) in a Song. Consists of multiple measures."""
    def __init__(self, name, program, channel, track_type, parent_song):
        self.name = name
        self.program = program  # MIDI program number
        self.channel = channel  # MIDI channel

        # Melody, harmony, bass, or drums.
        assert isinstance(track_type, TrackType)
        self.track_type = track_type

        assert isinstance(parent_song, Core.song.Song)
        self.parent_song = parent_song
        self.measures = []

    def __iter__(self):
        return iter(self.measures)

    def __eq__(self, t2):
        if (not (isinstance(t2, Track) and self.name == t2.name and self.program == t2.program
                 and self.channel == t2.channel and self.track_type == t2.track_type
                 and len(self.measures) == len(t2.measures))):
            return False
        for i, measure in enumerate(self.measures):
            if not measure == t2.measures[i]:
                return False
        return True

    def __repr__(self):
        return '%s (program:%d, channel=%d, type=%s)' % (self.name, self.program, self.channel,
                                                         self.track_type.name)

    def new_measure(self, time_signature=None):
        """Adds a new measure at the end of the track and returns the measure."""
        next_tick = 0
        if self.measures:
            prev_measure = self.measures[-1]
            next_tick = prev_measure.start_tick + prev_measure.get_duration_ticks()
        measure = Measure(next_tick, self, time_signature)
        self.measures.append(measure)
        return measure


class Measure:
    """Stores a single measure of a single track. Consists of multiple Events."""
    def __init__(self, start_tick, parent_track, time_signature=None):
        assert isinstance(parent_track, Track)
        self.events = []
        self.start_tick = start_tick
        self.parent_track = parent_track
        if time_signature:
            self.time_signature = time_signature
        else:
            self.time_signature = parent_track.parent_song.time_signature
        assert isinstance(self.time_signature, TimeSignature)

    def __iter__(self):
        return iter(self.events)

    def __eq__(self, m2):
        if not (isinstance(m2, Measure)):
            return False

        # Ignore any final rests in a measure in comparison.
        events1 = deepcopy(self.events)
        events2 = deepcopy(m2.events)
        len_events1 = len(events1)
        for i in range(len(events1) - 1, -1, -1):
            if not events1[i].notes:
                len_events1 = i
            else:
                # As soon as we see notes, break.
                break

        len_events2 = len(events2)
        for i in range(len(events2) - 1, -1, -1):
            if not events2[i].notes:
                len_events2 = i
            else:
                # As soon as we see notes, break.
                break

        if len_events1 != len_events2:
            return False

        for i in range(0, len_events1):
            if not self.events[i] == m2.events[i]:
                return False
        return True

    def __repr__(self):
        s = 'Measure:'
        for event in self:
            s += '\n\t%s' % str(event)
        return s

    def new_event(self, duration):
        event = Event(duration)
        self.events.append(event)
        return event

    def get_duration_ticks(self):
        """Returns the length of the measure in ticks, based on the time signature."""
        beats = self.time_signature.numerator * 4.0 / self.time_signature.denominator
        return int(beats * self.parent_track.parent_song.ticks_per_beat)


class Event:
    """Stores a single Event in a single track. This consists of all notes sounding at a particular
    moment in time, and a duration."""
    def __init__(self, duration=0):
        self.notes = []
        self.duration = int(duration)  # in ticks (as defined in the ancestor Song object)

    def __iter__(self):
        return iter(self.notes)

    def __eq__(self, e2):
        if not (isinstance(e2, Event) and self.duration == e2.duration
                and len(self.notes) == len(e2.notes)):
            return False

        # Don't require notes to be in same order. Treat as a set.
        for note in self.notes:
            for note2 in e2.notes:
                if note == note2:
                    break
            else:
                return False
        return True

    def __repr__(self):
        s = 'Event duration: %d [' % self.duration
        for i, note in enumerate(self.notes):
            s += str(note)
            if i < len(self.notes) - 1:
                s += ', '
        s += ']'
        return s

    def append_note(self, note):
        self.notes.append(note)

    def new_note(self, midi_pitch, velocity=-1, tie_from_previous=False):
        note = Note(midi_pitch, velocity, tie_from_previous)
        self.notes.append(note)
        return note


@total_ordering
class Note:
    """Stores a single Note. This is either a note on event or a continuation of a previously
    sounding note. Note off events are handled implicitly by the presence of a later event where
    the note is not sounding."""
    def __init__(self, midi_pitch, velocity=-1, tie_from_previous=False):
        self.midi_pitch = midi_pitch
        self.velocity = velocity  # set to -1 if tie_from_previous==True
        self.tie_from_previous = tie_from_previous

    def __eq__(self, n2):
        return (isinstance(n2, Note) and self.midi_pitch == n2.midi_pitch
                and self.velocity == n2.velocity
                and self.tie_from_previous == n2.tie_from_previous)

    def __lt__(self, n2):
        assert isinstance(n2, Note)
        return self.midi_pitch < n2.midi_pitch

    def __repr__(self):
        tie_string = ''
        if self.tie_from_previous:
            tie_string = 'TIE'
        return '%d[v=%d %s]' % (self.midi_pitch, self.velocity, tie_string)

