import io, unittest, wave
from asciiengine.audio import AudioEvent, AudioSystem, NullBackend, WavSynthesizer

class AudioTests(unittest.TestCase):
 def test_generated_wave_is_valid(self):
  data=WavSynthesizer(16000).tone(220,0.05,0.2,"triangle")
  with wave.open(io.BytesIO(data),"rb") as w:
   self.assertEqual((w.getnchannels(),w.getsampwidth(),w.getframerate()),(1,2,16000))
   self.assertEqual(w.getnframes(),800)
 def test_channels_position_and_silent_backend(self):
  a=AudioSystem(NullBackend()); a.set_channel("sfx",0.5)
  event=AudioEvent("step",volume=0.8,channel="sfx",position=(10,0))
  out=a.emit(event,listener=(0,0),path="unused.wav")
  self.assertAlmostEqual(out["gain"],0.8*0.5*(1-10/12))
  self.assertFalse(out["played"])
  self.assertEqual(len(a.transition("music",0.0,4)),4)
  self.assertEqual(a.channels["music"],0.0)
 def test_invalid_tone(self):
  with self.assertRaises(Exception): WavSynthesizer().tone(-1)
if __name__=="__main__": unittest.main()
