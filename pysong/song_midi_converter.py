"""Utility class for converting Song to/from MIDI.

TODO: implement time signature export to MIDI. Currently there are no time signature change
      messages in the output MIDI file.

TODO: refactor to simplify computation of "delta" values in midi export.
"""

from collections import defaultdict
from enum import IntEnum

from mido import Message, MetaMessage, MidiFile, MidiTrack
from pretty_midi import PrettyMIDI, Instrument

from pysong.pretty_midi_utils import get_all_time_signatures
from pysong.song import Song
from pysong.song_elements import TrackType, Note, Event, Measure


_DRUM_CHANNEL = 9


class _EventType(IntEnum):
    """This ordering is intentional, as it is used to sort events in get_events below."""
    NOTE_OFF = 1
    MEASURE_START = 2
    NOTE_ON = 3


class SongMidiConverter():
    """Class providing Song to/from MIDI conversion routines."""

    @staticmethod
    def _turn_off_notes(midi_track, channel, tick, prev_tick, notes_to_turn_off,  # pylint: disable=dangerous-default-value
                        notes_to_ignore=[]):
        """Create add MIDI messages to turn off all given notes except those in the ignore list."""
        for pitch in notes_to_turn_off:
            if pitch not in notes_to_ignore:
                delta = tick - prev_tick
                prev_tick = tick
                midi_track.append(Message('note_off', channel=channel, note=pitch,
                                          velocity=0, time=delta))
        return prev_tick

    @staticmethod
    def export_midi(song, file_name):
        """Creates a midi file representing the current song and saves the result to a file."""
        midi_file = MidiFile(ticks_per_beat=song.ticks_per_beat)

        # TODO: Output key signature changes to track 0.

        for track_idx, track in enumerate(song):
            midi_track = MidiTrack()
            midi_track.name = track.name
            midi_file.tracks.append(midi_track)
            channel = track.channel
            if channel > 15:
                print('Warning: too many channels for song %s. Skipping extra channel #%d.'
                      % (song.name, channel))
                continue
            midi_track.append(Message('program_change', channel=channel, program=track.program,
                                      time=0))
            measure_number = 0
            prev_tick = 0
            tick = 0
            prev_sounding_notes = set()  # contains MIDI numbers of previously-sounding notes
            previous_time_signature = None

            for measure in track:
                tick = measure.start_tick  # Jump to the start of this measure.

                # Write a time signature message if it has changed.
                # Only do this for track 0.
                if track_idx == 0 and measure.time_signature != previous_time_signature:
                    previous_time_signature = measure.time_signature
                    delta = tick - prev_tick
                    prev_tick = tick
                    midi_track.append(MetaMessage(
                        'time_signature',
                        numerator=measure.time_signature.numerator,
                        denominator=measure.time_signature.denominator,
                        time=delta))

                for event in measure:
                    sounding_notes = set()  # Notes that are sounding at this moment.

                    # First send a note off for all previously-sounding notes EXCEPT those
                    # which show up in the current event with the "tie_from_previous" flag set.
                    tied_from_previous = set(n.midi_pitch for n in event if n.tie_from_previous)
                    prev_tick = SongMidiConverter._turn_off_notes(midi_track, channel, tick,
                                                                  prev_tick, prev_sounding_notes,
                                                                  tied_from_previous)

                    for note in event:
                        pitch = note.midi_pitch
                        velocity = note.velocity
                        tie_from_previous = note.tie_from_previous
                        assert pitch >= 0 and pitch < 128
                        assert tie_from_previous or (velocity >= 0 and velocity < 128)

                        if velocity > 0 and not tie_from_previous:
                            # Handle note-on events.
                            delta = tick - prev_tick
                            prev_tick = tick
                            midi_track.append(Message('note_on', channel=channel, note=pitch,
                                                      velocity=note.velocity, time=delta))
                            sounding_notes.add(pitch)
                        elif not tie_from_previous:
                            # Handle explicit note-off events (note with velocity 0)
                            delta = tick - prev_tick
                            prev_tick = tick
                            midi_track.append(Message('note_off', channel=channel, note=pitch,
                                                      velocity=0, time=delta))
                        else:
                            # Handle tie_from_previous.
                            sounding_notes.add(pitch)

                    prev_sounding_notes = sounding_notes
                    tick += event.duration

                # We processed all events in the measure.  If not at the end of the measure yet,
                # turn off all notes.
                if tick < measure.start_tick + measure.get_duration_ticks():
                    prev_tick = SongMidiConverter._turn_off_notes(midi_track, channel, tick,
                                                                  prev_tick, prev_sounding_notes)
                    prev_sounding_notes = set()

                measure_number += 1

            # Turn off all notes at end of track.
            SongMidiConverter._turn_off_notes(midi_track, channel, tick, prev_tick,
                                              prev_sounding_notes)

            # End of track message.
            midi_track.append(MetaMessage('end_of_track'))

        midi_file.save(file_name)

    @staticmethod
    def create_song_from_midi(file_name):
        """This method creates a new Song object by reading a MIDI file, and parsing the tracks,
        and converting them to song.Track objects. Also sets other Song metadata that can be
        derived from the MIDI."""

        # Load MIDI file into PrettyMIDI object
        try:
            midi = PrettyMIDI(file_name)
        except IndexError as e:
            print("Exception: %s" % e)
            print("Error loading MIDI file in PrettyMIDI. Ensure the file has at least 1 track.")
            return Song()

        instrument_and_type_list = []
        for instrument in midi.instruments:
            if instrument.is_drum:
                instrument_and_type_list.append((instrument, TrackType.DRUMS))
            else:
                instrument_and_type_list.append((instrument, TrackType.UNKNOWN))

        return SongMidiConverter.create_song_from_pretty_midi_instruments(midi,
                                                                          instrument_and_type_list)

    @staticmethod
    def _get_measure_number(time, downbeats):
        for i, downbeat in enumerate(downbeats):
            if time >= downbeat:
                return i - 1
        # Not found.
        raise Exception('measure number not found for time %f\nDownbeats: %s' % (time, downbeats))

    @staticmethod
    def _get_events(instrument, downbeats, midi):
        """Return a sorted list of tuples of (tick, _EventType, note). note is optional.
        Notes here are pretty_mid notes, not Song notes."""
        event_list = []
        #note_starts = defaultdict(list)  # key is start tick, key is Note
        #note_ends = defaultdict(list)  # key is end tick, key is Note
        for note in instrument.notes:
            start_tick = midi.time_to_tick(note.start)
            end_tick = midi.time_to_tick(note.end)
            event_list.append((start_tick, _EventType.NOTE_ON, note))
            event_list.append((end_tick, _EventType.NOTE_OFF, note))
        for downbeat in downbeats:
            tick = midi.time_to_tick(downbeat)
            event_list.append((tick, _EventType.MEASURE_START, None))

        # Sort the list first by tick and second by event type. Thus, for events at the same tick,
        # NOTE_OFF events are listed first, then MEASURE_START, and finally NOTE_ON.

        def get_key(event):
            if event[2] is not None:
                return (event[0], event[1], event[2].pitch)
            return (event[0], event[1])

        return sorted(event_list, key=get_key)

    @staticmethod
    def _write_event(delta_duration, current_measure, notes_to_add, sounding_notes):
        event = current_measure.new_event(delta_duration)
        pitches_written = defaultdict(bool)
        for note in notes_to_add:
            event.append_note(note)
            pitches_written[note.midi_pitch] = True
        for pitch in sounding_notes:
            if sounding_notes[pitch]:
                if not pitches_written[pitch]:
                    event.append_note(Note(pitch, tie_from_previous=True))
                    pitches_written[pitch] = True

    #TODO: add metadata (midi_path, h5_path, original key?), add to song Class
    @staticmethod
    def create_song_from_pretty_midi_instruments(midi, instrument_and_type_list, name=''):
        """Create a new Song using the given list of Instrument objects.

        params:
            midi: a PrettyMidi object that owns the instruments to be added. Used for time to tick
                  conversion.
            instrument_and_type_list: a list of tuples of
                                      (pretty_midi.Instrument, song_elements.TrackType)

        returns: a Song object containing the given Instruments as Tracks.
        """
        assert isinstance(midi, PrettyMIDI)

        downbeats = midi.get_downbeats()
        song = Song(name, midi.resolution)

        # Convert each pretty_midi Instrument into a Song track.
        # N.B. This may change the order of tracks relative to the original MIDI file, and it
        # forces each instrument onto a different channel, which might make us run out of MIDI
        # channels.
        channel = 0
        for instrument, track_type in instrument_and_type_list:
            assert isinstance(instrument, Instrument)
            assert isinstance(track_type, TrackType)

            if instrument.is_drum:
                this_channel = _DRUM_CHANNEL
            else:
                this_channel = channel

            track = song.new_track(instrument.name, instrument.program, this_channel, track_type)

            # Generate set of event times with associated events.
            events = SongMidiConverter._get_events(instrument, downbeats, midi)

            # Get the list of time signatures, one for each measure.
            time_signatures = get_all_time_signatures(midi, downbeats)

            # The events have been sorted by tick and by event type, so for each tick, we can
            # easily process all note-off events, then all measure boundaries, and then all note on
            # events. This allows us to chop up long notes into notes that restart at each measure
            # boundary with a "tie-to-previous" marker. Similarly, all notes are split (with a
            # tie-to previous marker) any time other notes end. The effect is that there is a new
            # Song event at any point that the set of notes changes or we cross a measure boundary.
            #   We keep track of all currently-sounding notes so that we can generate any required
            # tie-to-previous notes at each event time point.

            # key is the midi pitch; value is True if sounding
            sounding_notes = defaultdict(bool)
            prev_tick = 0
            measure_idx = -1
            current_measure = None
            notes_to_add = []  # list of song_elements.Note objects

            first_note_off_at_tick = True
            for tick, event_type, note in events:  # note is a pretty_midi note
                if tick > prev_tick:
                    # We have moved on to a new tick. Generate the event in the previous measure.
                    delta_duration = tick - prev_tick
                    SongMidiConverter._write_event(delta_duration, current_measure, notes_to_add,
                                                   sounding_notes)

                    # Make new notes_to_add list of song_elements.Note objects.
                    notes_to_add = []

                    # Reset first-note-off flag.
                    first_note_off_at_tick = True

                if event_type == _EventType.NOTE_OFF:
                    # This is like a Measure start event, but we don't know how many notes
                    # will be turned off.
                    #   We need to record all note-off events, and then prepare a new note
                    # event with tie_from_previous set for all pitches.
                    if first_note_off_at_tick:
                        first_note_off_at_tick = False
                        # Add all currently sounding notes to notes_to_add, but then start removing
                        # them for each note_off. Added notes will tie-from-previous. This is just
                        # like a measure break.
                        for pitch in sounding_notes:
                            if sounding_notes[pitch]:
                                notes_to_add.append(Note(pitch, tie_from_previous=True))

                    # Remove note from notes_to_add if it exists (it might have been deleted
                    # already if there are multiple NOTE_ON MIDI events with a single NOTE_OFF);
                    # pretty midi will result in multiple NOTE_OFF events in this case at the
                    # same time.
                    for i, note_to_add in enumerate(notes_to_add):
                        if note_to_add.midi_pitch == note.pitch:
                            del notes_to_add[i]
                            break

                    sounding_notes[note.pitch] = False

                elif event_type == _EventType.MEASURE_START:
                    # Move to next measure.
                    measure_idx += 1
                    current_measure = track.new_measure(time_signatures[measure_idx])

                elif event_type == _EventType.NOTE_ON:
                    # New note.
                    # If note was already sounding, replace any existing tie_from_previous version.
                    remove_idx = None
                    for idx, added_note in enumerate(notes_to_add):
                        if added_note.midi_pitch == note.pitch:
                            remove_idx = idx
                    if remove_idx is not None:
                        del notes_to_add[remove_idx]
                    notes_to_add.append(Note(note.pitch, note.velocity))
                    sounding_notes[note.pitch] = True

                prev_tick = tick

            # Make sure no notes are still sounding.
            for sounding in sounding_notes.values():
                assert not sounding

            channel += 1
            if channel == _DRUM_CHANNEL:  # skip drum channel
                channel = _DRUM_CHANNEL + 1
            if channel > 15:
                print('Warning: too many tracks. Using channel %d for song %s' % (channel, name))

        return song
