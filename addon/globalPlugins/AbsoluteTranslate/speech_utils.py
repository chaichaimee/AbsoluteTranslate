# speech_utils.py

import speech
import speechViewer
from collections import deque
from logHandler import log
from eventHandler import FocusLossCancellableSpeechCommand

class SpeechHistoryHandler:
	def __init__(self, maxlen=50, callback=None):
		self.history = deque(maxlen=maxlen)
		self.callback = callback
		self._orig_speak = None
		self._patched = False
		self.patch_speech()

	def patch_speech(self):
		try:
			if hasattr(speech, 'speech') and hasattr(speech.speech, 'speak'):
				self._orig_speak = speech.speech.speak
				speech.speech.speak = self._my_speak
				self._patched = True
			elif hasattr(speech, 'speak'):
				self._orig_speak = speech.speak
				speech.speak = self._my_speak
				self._patched = True
			log.debug("SpeechHistoryHandler: speech interception active")
		except Exception as e:
			log.error(f"Failed to patch speech: {e}")

	def restore_patch(self):
		if self._patched:
			if hasattr(speech, 'speech'):
				speech.speech.speak = self._orig_speak
			else:
				speech.speak = self._orig_speak
			self._patched = False
			log.debug("SpeechHistoryHandler: speech restored")

	def _my_speak(self, sequence, *args, **kwargs):
		if self._orig_speak:
			self._orig_speak(sequence, *args, **kwargs)
		
		# Filter out special commands
		filtered_seq = [item for item in sequence if not isinstance(item, FocusLossCancellableSpeechCommand)]
		text_parts = [item for item in filtered_seq if isinstance(item, str)]
		text = speechViewer.SPEECH_ITEM_SEPARATOR.join(text_parts)
		
		if text:
			self.history.appendleft(text)
			if self.callback:
				self.callback(text)

	def get_latest(self):
		return self.history[0] if self.history else ""