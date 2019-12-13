import os
import unittest
import tempfile

from mido import MidiFile
from mido.messages import Message
from mido.midifiles.meta import MetaMessage
from pretty_midi import PrettyMIDI

from Core.pretty_midi_utils import is_monophonic, get_all_time_signatures
from Core.song import Song
from Core.song_elements import TrackType, TimeSignature, Key, Mode, Measure, Event, Note
from Core.song_midi_converter import SongMidiConverter

class Test_song(unittest.TestCase):
    @staticmethod
    def make_song_empty():
        s = Song('Test2')
        s.time_signature = TimeSignature(3, 8)
        s.key = Key(num_sharps=-2, mode=Mode.MINOR)
        s.new_track('Flute', 1, 1, TrackType.MELODY)
        return s

    @staticmethod
    def make_song_monophonic():
        s = Song('TestMonophonic')
        track = s.new_track('Flute', 1, 1, TrackType.MELODY)
        for j in range(7):
            measure = track.new_measure()
            for k in range(4):
                event = measure.new_event(k+1)
                if k % 3 == 0:
                    event.new_note(41 - j, 64)
        return s

    @staticmethod
    def make_song_polyphonic():
        return Test_song.make_song(1, 4)

    @staticmethod
    def make_song(num_tracks, num_measures, include_drums=False):
        s = Song('Random Song')
        for i in range(num_tracks):
            if include_drums and i == num_tracks-1:
                # Make a drum track.
                track = s.new_track('Drums', 0, 9, TrackType.DRUMS)
                for j in range(num_measures):
                    measure = track.new_measure()
                    for k in range(num_tracks):
                        event = measure.new_event(s.ticks_per_beat / (2**k))
                        for m in range(k):
                            if k % (1+m) == 0:
                                event.new_note(41 - m, 64 + 16 * m)
            else:
                # Make a pitched track.
                track = s.new_track('Track %d' % i, i, i)
                for j in range(num_measures):
                    measure = track.new_measure()
                    for k in range(i+1):
                        event = measure.new_event(s.ticks_per_beat / (2**k))
                        if k % 3 < 1:
                            event.new_note(72 - 3 * i, 64 + 16 * i)
                        if k % 3 < 2:
                            event.new_note(72 - 3 * i - 3 * (k+1), 64 + 16 * i)
        return s

    @staticmethod
    def make_song_with_ties():
        s = Song('Song with Ties')
        track = s.new_track('Track 0', 0, 0)

        for i in range(12):
            if i % 4 == 0:
                measure = track.new_measure()
            event = measure.new_event(s.ticks_per_beat)
            event.new_note(48 + 2*i, 64)
            if i > 0:
                event.new_note(48+2*(i-1), tie_from_previous=True)
            if i > 1:
                event.new_note(48+2*(i-2), tie_from_previous=True)

        return s

    @staticmethod
    def make_song_with_ties_2():
        s = Song('Song with Ties', ticks_per_beat=192)
        track = s.new_track('Track 0', 0, 0)

        measure = track.new_measure()
        event = measure.new_event(10)
        event = measure.new_event(185)
        event.new_note(33, 127)
        event = measure.new_event(1)
        event = measure.new_event(154)
        event.new_note(33, 127)
        event = measure.new_event(145)
        event.new_note(33, 127)
        event = measure.new_event(172)
        event.new_note(33, 127)
        event = measure.new_event(96)
        event.new_note(33, 127)
        event = measure.new_event(5)
        event.new_note(29, 127)

        measure = track.new_measure()
        event = measure.new_event(202)
        event.new_note(29, tie_from_previous=True)
        event = measure.new_event(146)
        event.new_note(29, 127)
        event = measure.new_event(140)
        event.new_note(31, 127)
        event = measure.new_event(1)
        event = measure.new_event(167)
        event.new_note(31, 127)
        event = measure.new_event(1)
        event = measure.new_event(83)
        event.new_note(31, 127)
        event = measure.new_event(28)
        event.new_note(33, 127)

        return s

    def test_song_str(self):
        song1 = Song('Test')
        self.assertEqual(str(song1), 'Song: Test. 0 tracks. Time signature: 4/4. Key: C MAJOR')

        song2 = self.make_song_empty()
        self.assertEqual(str(song2), 'Song: Test2. 1 track. Time signature: 3/8. Key: G MINOR')

    def test_song_save_load(self):
        """Make a Song and save to a temp file."""
        song1 = self.make_song_empty()
        filename = tempfile.mktemp()
        song1.save(filename)

        # Delete the original!
        del song1

        # Load, make sure it worked.
        song2 = Song.load(filename)

        # Clean up.
        os.remove(filename)

        self.assertEqual(str(song2), 'Song: Test2. 1 track. Time signature: 3/8. Key: G MINOR')

    def song_to_midi_to_song(self, song):
        """Make a song and export to midi."""
        filename = tempfile.mktemp() + '.mid'
        SongMidiConverter.export_midi(song, filename)

        # Read back from MIDI.
        song2 = SongMidiConverter.create_song_from_midi(filename)
        song2.name = song.name

        # Clean up.
        os.remove(filename)

        print ('imported song:')
        song2.print_tracks(True)

        # Compare the two versions.
        self.assertEqual(song, song2)

    def test_empty_song_to_midi_to_song(self):
        self.song_to_midi_to_song(Song())

    def test_song_to_midi_to_song_2_3(self):
        self.song_to_midi_to_song(self.make_song(2, 3, True))

    def test_song_to_midi_to_song_4_1(self):
        self.song_to_midi_to_song(self.make_song(4, 2, True))

    def test_song_to_midi_to_song_5_8(self):
        self.song_to_midi_to_song(self.make_song(5, 8, True))

    def test_song_to_midi_to_song_ties(self):
        self.song_to_midi_to_song(self.make_song_with_ties())

    def test_song_to_midi_to_song_ties_2(self):
        self.song_to_midi_to_song(self.make_song_with_ties_2())

    @staticmethod
    def create_midi_file():
        midifile = MidiFile(ticks_per_beat=192)
        track = midifile.add_track('main bass')
        track.append(Message('program_change', channel=0, program=3, time=0))
        track.append(MetaMessage('time_signature', numerator=4, denominator=4))

        track.append(Message('note_on', channel=0, note=33, velocity=127, time=6154))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=185))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=1))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=154))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=145))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=172))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=96))

        track.append(Message('note_on', channel=0, note=29, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=29, velocity=0, time=207))
        track.append(Message('note_on', channel=0, note=29, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=29, velocity=0, time=146))

        track.append(Message('note_on', channel=0, note=31, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=31, velocity=0, time=140))
        track.append(Message('note_on', channel=0, note=31, velocity=127, time=1))
        track.append(Message('note_off', channel=0, note=31, velocity=0, time=167))
        track.append(Message('note_on', channel=0, note=31, velocity=127, time=1))
        track.append(Message('note_off', channel=0, note=31, velocity=0, time=83))

        track.append(Message('note_on', channel=0, note=33, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=216))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=1))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=162))
        track.append(Message('note_on', channel=0, note=33, velocity=127, time=1))
        track.append(Message('note_off', channel=0, note=33, velocity=0, time=140))

        return midifile

    @staticmethod
    def create_midi_file_with_time_signatures():
        midifile = MidiFile(ticks_per_beat=4)  # 1 tick = 1/16th note
        track = midifile.add_track('main track')

        # 1 empty measure

        # Measure 2: half rest, then 1 quarter notes, then quarter rest
        track.append(Message('note_on', channel=0, note=60, velocity=127, time=16 + 8))
        track.append(Message('note_off', channel=0, note=60, velocity=0, time=4))

        # Measure 3: Time signature change to 3/4, then 3 quarter notes
        track.append(MetaMessage('time_signature', numerator=3, denominator=4, time=4))
        track.append(Message('note_on', channel=0, note=63, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=63, velocity=0, time=4))
        track.append(Message('note_on', channel=0, note=64, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=64, velocity=0, time=4))
        track.append(Message('note_on', channel=0, note=65, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=65, velocity=0, time=4))

        # Measure 4: Time signature change to 5/8, then quarter rest, then 3 eighth notes
        track.append(MetaMessage('time_signature', numerator=5, denominator=8, time=0))
        track.append(Message('note_on', channel=0, note=63, velocity=127, time=4))
        track.append(Message('note_off', channel=0, note=63, velocity=0, time=2))
        track.append(Message('note_on', channel=0, note=64, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=64, velocity=0, time=2))
        track.append(Message('note_on', channel=0, note=65, velocity=127, time=0))
        track.append(Message('note_off', channel=0, note=65, velocity=0, time=2))

        return midifile

    @staticmethod
    def create_song_with_ties():
        s = Song('Song with Ties', ticks_per_beat=4)
        track = s.new_track('Track 0', 0, 0)
        m = track.new_measure(TimeSignature())

        m.new_event(1)

        e = m.new_event(1)
        e.new_note(69, 100)

        m.new_event(1)

        e = m.new_event(1)
        e.new_note(76, 100)


        e = m.new_event(1)
        e.new_note(76, 100, True)

        e = m.new_event(1)
        e.new_note(74, 100)

        e = m.new_event(1)
        e.new_note(74, 100, True)

        e = m.new_event(1)
        e.new_note(72, 100)


        e = m.new_event(1)
        e.new_note(69, 100)

        m.new_event(1)

        e = m.new_event(1)
        e.new_note(76, 100)

        e = m.new_event(1)


        e = m.new_event(1)
        e.new_note(74, 100)

        m.new_event(1)

        e = m.new_event(1)
        e.new_note(72, 100)

        e = m.new_event(1)
        e.new_note(74, 100)

        #e = m.new_event(1)
        #e.new_note(72, 100)

        return s

    def test_midi_to_song_to_midi(self):
        # Create MIDI file object in memory.
        midifile = Test_song.create_midi_file()

        # Write to file.
        tmp_midi_orig = tempfile.mktemp() + '.mid'
        midifile.save(tmp_midi_orig)

        # Import to Song object.
        s = SongMidiConverter.create_song_from_midi(tmp_midi_orig)

        # Export to midi.
        tmp_midi_new = tempfile.mktemp() + '.mid'
        SongMidiConverter.export_midi(s, tmp_midi_new)

        # Compare original MIDI with exported MIDI.
        midifile_new = MidiFile(tmp_midi_new)

        self.assertEqual(len(midifile.tracks), len(midifile_new.tracks))
        new_track = midifile_new.tracks[0]
        for i, msg in enumerate(midifile.tracks[0]):
            self.assertEqual(str(msg), str(new_track[i]))

        # Clean up.
        os.remove(tmp_midi_orig)
        os.remove(tmp_midi_new)

    def test_instrument_is_monophonic(self):
        """Test is_monophonic function, True case."""
        # Make mono song, convert to midi, load in pretty_midi, extract instrument.
        s_mono = self.make_song_monophonic()
        filename = tempfile.mktemp() + '.mid'
        SongMidiConverter.export_midi(s_mono, filename)
        midi = PrettyMIDI(filename)
        instrument = midi.instruments[0]
        self.assertTrue(is_monophonic(instrument))

    def test_instrument_is_polyphonic(self):
        """Test is_monophonic function, False case."""
        # Make poly song, convert to midi, load in pretty_midi, extract instrument.
        s_poly = self.make_song_polyphonic()
        filename = tempfile.mktemp() + '.mid'
        SongMidiConverter.export_midi(s_poly, filename)
        midi = PrettyMIDI(filename)
        instrument = midi.instruments[0]
        self.assertFalse(is_monophonic(instrument))

    def verify_time_signatures(self, time_signatures):
        self.assertEqual(len(time_signatures), 4)

        self.assertEqual(time_signatures[0].numerator, 4)
        self.assertEqual(time_signatures[0].denominator, 4)

        self.assertEqual(time_signatures[1].numerator, 4)
        self.assertEqual(time_signatures[1].denominator, 4)

        self.assertEqual(time_signatures[2].numerator, 3)
        self.assertEqual(time_signatures[2].denominator, 4)

        self.assertEqual(time_signatures[3].numerator, 5)
        self.assertEqual(time_signatures[3].denominator, 8)

    def test_get_all_time_signatures(self):
        midifile = Test_song.create_midi_file_with_time_signatures()

        tmp_midi_orig = tempfile.mktemp() + '.mid'
        midifile.save(tmp_midi_orig)

        pm = PrettyMIDI(tmp_midi_orig)
        time_signatures = get_all_time_signatures(pm)
        os.remove(tmp_midi_orig)

        self.verify_time_signatures(time_signatures)

    def test_export_time_signatures_midi(self):
        # Create a midifile with time signature changes.
        midifile = Test_song.create_midi_file_with_time_signatures()

        tmp_midi_orig = tempfile.mktemp() + '.mid'
        midifile.save(tmp_midi_orig)

        # Load it into a Song object.
        s = SongMidiConverter.create_song_from_midi(tmp_midi_orig)

        # Export to midi.
        tmp_midi_new = tempfile.mktemp() + '.mid'
        SongMidiConverter.export_midi(s, tmp_midi_new)

        # Get time signatures from new MIDI file using PrettyMIDI.
        pm = PrettyMIDI(tmp_midi_new)
        time_signatures = get_all_time_signatures(pm)

        os.remove(tmp_midi_orig)

        # Verify time signatures.
        self.verify_time_signatures(time_signatures)

    def test_song_to_midi_to_song_ties_3(self):
        s = self.create_song_with_ties()
        s.print_tracks(True)
        self.song_to_midi_to_song(s)


if __name__ == '__main__':
    unittest.main()
