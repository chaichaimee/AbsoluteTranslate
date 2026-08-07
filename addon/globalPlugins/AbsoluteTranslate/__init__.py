# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import addonHandler
import globalPluginHandler
from scriptHandler import script
import api
import ui
import time
import wx
import speech
import gui
import core
from logHandler import log
import threading
import weakref

from . import translate
from . import setting
from .clipboard_utils import ClipboardHandler
from .speech_utils import SpeechHistoryHandler
from .long_translation_dialog import LongTranslationDialog

addonHandler.initTranslation()

# Safety-net timeout: if a translation cycle never reports back (unexpected
# exception inside a background thread, a hung dialog, etc.) the plugin would
# otherwise stay locked in "Translation in progress" until NVDA is restarted.
# This watchdog force-releases the lock after this many milliseconds.
PROCESSING_WATCHDOG_MS = 45000


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = "Absolute Translate"

	def __init__(self):
		super().__init__()
		log.info("AbsoluteTranslate: Initializing")

		self.clipboard_handler = ClipboardHandler()
		self.speech_history = SpeechHistoryHandler(maxlen=100)
		self._original_speak = speech.speak
		self._suppress_speech = False
		self._tap_count = 0
		self._last_tap_time = 0
		self._double_tap_threshold = 0.5
		self._action_timer = None
		self._is_processing = False
		self._processing_watchdog = None

		translate.load_cache()
		setting.load_config()
		self._register_settings_panel()

		log.info("AbsoluteTranslate: Initialized successfully")

	def _register_settings_panel(self):
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			panels = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
			if AbsoluteTranslateSettingsPanel not in panels:
				panels.append(AbsoluteTranslateSettingsPanel)
				log.debug("Settings panel registered")
		except Exception as e:
			log.error(f"Failed to register settings panel: {e}")

	def terminate(self):
		log.info("AbsoluteTranslate: Terminating")
		if hasattr(self, 'speech_history'):
			self.speech_history.restore_patch()
		translate.save_cache()
		if self._action_timer:
			self._action_timer.Stop()
		self._clear_processing_watchdog()
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			panels = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
			if AbsoluteTranslateSettingsPanel in panels:
				panels.remove(AbsoluteTranslateSettingsPanel)
		except Exception:
			pass
		self._is_processing = False

	# --- Processing-state helpers -------------------------------------------------
	# Centralizing every mutation of `_is_processing` here fixes the root cause of
	# the "Translation in progress, please wait" lock-up: previously several early
	# `return` statements inside `_execute_translate_action` skipped resetting the
	# flag entirely, so a single "no text selected" or "no spoken text" event was
	# enough to permanently freeze the add-on until NVDA was restarted.

	def _clear_processing_watchdog(self):
		if self._processing_watchdog:
			try:
				self._processing_watchdog.Stop()
			except Exception:
				pass
			self._processing_watchdog = None

	def _processing_watchdog_expired(self):
		self._processing_watchdog = None
		if self._is_processing:
			log.warning("AbsoluteTranslate: processing watchdog expired, force-releasing stuck state")
			self._is_processing = False
			ui.message(_("Translation timed out."))

	def _start_processing_watchdog(self):
		self._clear_processing_watchdog()
		self._processing_watchdog = wx.CallLater(PROCESSING_WATCHDOG_MS, self._processing_watchdog_expired)

	def _finish_processing(self):
		"""Safe to call from the main thread only."""
		self._is_processing = False
		self._clear_processing_watchdog()

	def _finish_processing_from_worker(self):
		"""Safe to call from a background thread."""
		self._is_processing = False
		core.callLater(0, self._clear_processing_watchdog)

	# --------------------------------------------------------------------------------

	def _get_selected_text_async(self, callback):
		def worker():
			try:
				obj = api.getFocusObject()
				text = self.clipboard_handler.get_selected_text(obj)
				core.callLater(0, callback, text)
			except Exception as e:
				log.error(f"Get selected text failed: {e}")
				core.callLater(0, callback, "")

		threading.Thread(target=worker, daemon=True).start()

	def _get_selected_text(self):
		obj = api.getFocusObject()
		return self.clipboard_handler.get_selected_text(obj)

	def _get_last_spoken_text(self):
		text = self.speech_history.get_latest()
		if text:
			log.info(f"Last spoken: {text[:100]}...")
			return text
		return ""

	def _output_translation(self, translated_text, do_copy=False, do_append=False):
		if not translated_text:
			ui.message(_("No translation result."))
			return

		self._suppress_speech = True
		ui.message(translated_text)
		self._suppress_speech = False

		if do_append:
			try:
				self.clipboard_handler.append_to_clipboard(translated_text)
				log.debug("Translation appended to clipboard")
			except Exception as e:
				log.error(f"Clipboard append failed: {e}")
		elif do_copy:
			try:
				api.copyToClip(translated_text)
				log.debug("Translation copied to clipboard")
			except Exception as e:
				log.error(f"Clipboard copy failed: {e}")

	def _execute_translate_action(self):
		if self._is_processing:
			# Already busy: don't let a leftover tap count leak into the next
			# legitimate attempt once processing finishes.
			self._tap_count = 0
			ui.message(_("Translation in progress, please wait."))
			return

		# Snapshot and clear the tap count immediately so a stray keypress that
		# arrives while we're working can't corrupt the count read below.
		tap_count = self._tap_count
		self._tap_count = 0

		self._is_processing = True
		self._start_processing_watchdog()
		async_started = False

		try:
			if tap_count == 1:
				log.info("Single tap: selected text")
				full_text = self._get_selected_text()
				if not full_text:
					ui.message(_("No text selected."))
					return

				src = setting.config.get("source_lang", "auto")
				tgt = setting.config["target_lang"]
				swap = setting.config.get("swap_lang", "en")
				auto_swap = setting.config.get("auto_swap", False)
				copy_mode = setting.config.get("copy_to_clipboard", False)
				continuous = setting.config.get("continuous_translation", False)
				append_mode = setting.config.get("append_translations", False)

				if continuous and len(full_text) > 1500:
					def show_dialog():
						try:
							dlg = LongTranslationDialog(
								None, [full_text], tgt, src, swap, auto_swap,
								copy_mode, append_mode, self.clipboard_handler
							)
							dlg.start_translation()
							dlg.ShowModal()
						except Exception as e:
							log.error(f"Long translation dialog failed: {e}")
							ui.message(_("Cannot open translation window."))
						finally:
							self._finish_processing()
					wx.CallAfter(show_dialog)
					async_started = True
				else:
					self._translate_and_output(full_text, tgt, src, swap, auto_swap, copy_mode)
					async_started = True

			elif tap_count == 2:
				log.info("Double tap: last spoken")
				full_text = self._get_last_spoken_text()
				if not full_text:
					ui.message(_("No spoken text captured."))
					return

				src = setting.config.get("source_lang", "auto")
				tgt = setting.config["target_lang"]
				swap = setting.config.get("swap_lang", "en")
				auto_swap = setting.config.get("auto_swap", False)
				copy_mode = setting.config.get("copy_to_clipboard", False)

				self._translate_and_output(full_text, tgt, src, swap, auto_swap, copy_mode)
				async_started = True

			elif tap_count >= 3:
				log.info("Triple tap: open settings")
				self._open_settings()
				async_started = True
		except Exception as e:
			log.error(f"Execute translate action failed: {e}")
		finally:
			# Only auto-release here when nothing was handed off to a worker
			# thread or dialog; those paths own the release from now on.
			if not async_started:
				self._finish_processing()

	def _translate_and_output(self, text, target_lang, source_lang, swap_lang, auto_swap, copy_mode):
		def worker():
			try:
				translated = translate.translate_text(text, target_lang, source_lang, swap_lang, auto_swap)
				core.callLater(0, self._output_translation, translated, copy_mode, False)
			except Exception as e:
				log.error(f"Translation worker failed: {e}")
				core.callLater(0, ui.message, _("Translation failed. Please check your network connection."))
			finally:
				self._finish_processing_from_worker()

		threading.Thread(target=worker, daemon=True).start()

	def _open_settings(self):
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			wx.CallAfter(gui.mainFrame._popupSettingsDialog,
						 gui.settingsDialogs.NVDASettingsDialog,
						 AbsoluteTranslateSettingsPanel)
		except Exception as e:
			log.error(f"Open settings failed: {e}")
			ui.message(_("Cannot open settings dialog"))
		finally:
			self._finish_processing()

	@script(
		description=_("Translates Selected Text (Single Tap), Translates Last Speech (Double Tap), Open Absolute Translate Settings (Tripple Tap)"),
		gesture="kb:alt+windows+t",
		category=scriptCategory
	)
	def script_translate(self, gesture):
		current_time = time.time()
		if current_time - self._last_tap_time > self._double_tap_threshold:
			self._tap_count = 0
		self._tap_count += 1
		self._last_tap_time = current_time
		if self._action_timer:
			self._action_timer.Stop()
		self._action_timer = wx.CallLater(
			int(self._double_tap_threshold * 1000),
			self._execute_translate_action
		)
