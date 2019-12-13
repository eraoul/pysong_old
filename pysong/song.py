"""Classes for representing a song in a MIDI-like format."""

# Requires the following pacakges:
#   * mido        -- for MIDI export
#   * pretty_midi -- for MIDI import
#
# Install:
#   pip install pretty_midi    (includes mido)
#
# Measures consist of events and durations. To make an event mid-measure, there must be a "rest"
# event to fill in the space before the event. A rest is simply an Event with an empty note
# collection.

import gzip
import pickle

from Core.song_elements import Track, TimeSignature, Key, TrackType
import Core


class Song:
    """Stores an entire symbolic score for a song. Contains multiple tracks."""
    def __init__(self, name='', ticks_per_beat=480): #TODO: add other params (midi_path, h5_path, original key?)
        self.version = '0.2'
        self.name = name
        self.time_signature = TimeSignature()
        self.key = Key(tonic_pitch_class=0)
        self.tracks = []
        #self.midi_path = midi_path
        # ticks_per_beat represents the finest granularity of time slices that we can represent.
        # If reading from MIDI, can be set to the same value as in the source MIDI file
        self.ticks_per_beat = ticks_per_beat

        self.time_signature_changes = []

        # TODO: represent mid-score key signature changes

    def __str__(self):
        return "Song: %s. %d track%s. Time signature: %s. Key: %s" % (
            self.name, len(self.tracks), '' if len(self.tracks) == 1 else 's',
            str(self.time_signature), str(self.key))

    def __iter__(self):
        return iter(self.tracks)

    def __eq__(self, s2):
        if not (isinstance(s2, Song) and
                self.name == s2.name and
                self.time_signature == s2.time_signature and
                self.key == s2.key and
                len(self.tracks) == len(s2.tracks) and
                self.ticks_per_beat == s2.ticks_per_beat):
            return False
        # Verify all tracks from self show up in s2. order does not matter; allow permutations.
        for track in self.tracks:
            for track2 in s2.tracks:
                if track == track2:
                    break
            else:
                return False
        return True

    def print_tracks(self, verbose=False, max_measures=4):
        """Prints list of all tracks. If verbose==True prints all measures and events."""
        for track in self:
            print(track)
            if verbose:
                for i, measure in enumerate(track.measures):
                    if i >= max_measures:
                        break
                    print(measure)
                print()

    def new_track(self, name, program, channel, track_type=TrackType.UNKNOWN):
        """Creates and appends a new Track to this song. Returns the new track."""
        track = Track(name, program, channel, track_type, self)
        self.tracks.append(track)
        return track

    def save(self, output_filename):
        """Save this Song object to a zipped pickle file."""
        with gzip.open(output_filename, 'wb') as f:
            pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)

    #def export_to_midi(self, output_filename):
    #    """Export this song to a MIDI file."""
    #    Core.song_midi_converter.SongMidiConverter.export_midi(self, output_filename)

    #@staticmethod
    #def create_song_from_midi(midi_filename):
    #    """Returns a new Song object improted from the given MIDI file."""
    #    return Core.song_midi_converter.SongMidiConverter.create_song_from_midi(midi_filename)

    @staticmethod
    def load(filename):
        """Load a Song object from a Song zipped pickle file. Returns the Song object."""
        with gzip.open(filename, 'rb') as f:
            return pickle.load(f)

    def export_vector(self):
        raise NotImplementedError()

    def import_vector(self):
        raise NotImplementedError()

    def adjust_ties_(self, clean_up, smooth_harmony):
        """Provides cleaning and smoothing options for ties."""
        for track in self:
            if smooth_harmony and track.track_type != TrackType.HARMONY:
                continue
            prev_sounding_notes = set()
            for measure in track:
                for event in measure:
                    sounding_notes = set()
                    for note in event:
                        if note.midi_pitch in prev_sounding_notes:
                            if smooth_harmony:
                                note.tie_from_previous = True
                        elif clean_up:
                            note.tie_from_previous = False
                        sounding_notes.add(note.midi_pitch)
                    prev_sounding_notes = sounding_notes

    def clean_ties(self):
        """Remove any tie_from_previous Note parameters where the note wasn't previously sounding."""
        self.adjust_ties_(clean_up=True, smooth_harmony=False)

    def force_smooth_harmony(self):
        """Add ties for any harmony tracks between repeated notes, so that the harmony part has
        minimal rearticulations."""
        self.adjust_ties_(clean_up=True, smooth_harmony=True)


