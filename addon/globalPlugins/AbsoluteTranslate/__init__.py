# __init__.py
# Copyright (C) 2026 Chai Chaimee
# Licensed under GNU General Public License. See COPYING.txt for details.

import os
import json
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

PROCESSING_WATCHDOG_MS = 45000
HISTORY_FILE_NAME = "AbsoluteTranslate_history.json"
MAX_HISTORY_ENTRIES = 200


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
		self._translation_history = []
		self._history_cursor = None

		translate.load_cache()
		setting.load_config()
		self._clear_history_file()
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

	def _get_history_path(self):
		cfg_dir = setting.get_config_dir()
		if not cfg_dir:
			return None
		return os.path.join(cfg_dir, HISTORY_FILE_NAME)

	def _clear_history_file(self):
		"""History only covers the current NVDA session, so any file left
		over from a previous run is discarded on startup."""
		path = self._get_history_path()
		if path and os.path.exists(path):
			try:
				os.remove(path)
			except Exception as e:
				log.error(f"Failed to clear history file: {e}")

	def _save_history_file(self):
		path = self._get_history_path()
		if not path:
			return
		try:
			with open(path, "w", encoding="utf-8") as f:
				json.dump(self._translation_history, f, ensure_ascii=False, indent=2)
		except Exception as e:
			log.error(f"Failed to save history file: {e}")

	def _add_to_history(self, translated_text):
		if not translated_text:
			return
		self._translation_history.append(translated_text)
		if len(self._translation_history) > MAX_HISTORY_ENTRIES:
			self._translation_history = self._translation_history[-MAX_HISTORY_ENTRIES:]
		self._history_cursor = None
		threading.Thread(target=self._save_history_file, daemon=True).start()

	def _speak_history_step(self):
		"""Called on a single tap with no text selected: steps backward
		through past translations, most recent first."""
		if not self._translation_history:
			ui.message(_("No translation history yet."))
			return

		if self._history_cursor is None:
			self._history_cursor = len(self._translation_history) - 1
		else:
			if self._history_cursor <= 0:
				ui.message(_("This is the oldest translation in history."))
				return
			self._history_cursor -= 1

		entry = self._translation_history[self._history_cursor]
		self._suppress_speech = True
		ui.message(entry)
		self._suppress_speech = False

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

		self._add_to_history(translated_text)

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

	def _process_selected_text(self, full_text):
		try:
			if not full_text:
				self._speak_history_step()
				self._finish_processing()
				return

			src = setting.config.get("source_lang", "auto")
			tgt = setting.config["target_lang"]
			swap = setting.config.get("swap_lang", "en")
			auto_swap = setting.config.get("auto_swap", False)
			copy_mode = setting.config.get("copy_to_clipboard", False)
			continuous = setting.config.get("continuous_translation", False)
			append_mode = setting.config.get("append_translations", False)
			engine = setting.config.get("translation_engine", "google_translate")
			long_threshold = 1500 if engine == "google_translate" else 50000

			if continuous and len(full_text) > long_threshold:
				self._open_long_translation_async(full_text, tgt, src, swap, auto_swap, copy_mode, append_mode)
			else:
				self._translate_and_output(full_text, tgt, src, swap, auto_swap, copy_mode)
		except Exception as e:
			log.error(f"Process selected text failed: {e}")
			self._finish_processing()

	def _execute_translate_action(self):
		if self._is_processing:
			self._tap_count = 0
			ui.message(_("Translation in progress, please wait."))
			return

		tap_count = self._tap_count
		self._tap_count = 0

		self._is_processing = True
		self._start_processing_watchdog()
		async_started = False

		try:
			if tap_count == 1:
				log.info("Single tap: selected text")
				obj = api.getFocusObject()
				self.clipboard_handler.get_selected_text_async(obj, self._process_selected_text)
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
			if not async_started:
				self._finish_processing()

	def _translate_and_output(self, text, target_lang, source_lang, swap_lang, auto_swap, copy_mode):
		def worker():
			try:
				translated = translate.translate_text(text, target_lang, source_lang, swap_lang, auto_swap)
				core.callLater(0, self._output_translation, translated, copy_mode, False)
			except translate.TranslationRateLimitError:
				log.error("Translation rate limited")
				core.callLater(0, ui.message, _("Translation API blocked due to rate limits. Please try again later."))
			except translate.TranslationError as e:
				log.error(f"Translation worker failed: {e}")
				core.callLater(0, ui.message, _("Translation failed: {error}").format(error=str(e)))
			except Exception as e:
				log.error(f"Translation worker failed: {e}")
				core.callLater(0, ui.message, _("Translation failed. Please check your network connection."))
			finally:
				self._finish_processing_from_worker()

		threading.Thread(target=worker, daemon=True).start()

	def _open_long_translation_async(self, full_text, target_lang, source_lang, swap_lang, auto_swap, copy_mode, append_mode):
		def worker():
			try:
				chunks = translate.split_text_into_chunks(full_text)
				core.callLater(
					0,
					self._show_long_translation_dialog,
					chunks, target_lang, source_lang, swap_lang, auto_swap,
					copy_mode, append_mode
				)
			except Exception as e:
				log.error(f"Long translation preparation failed: {e}")
				core.callLater(0, self._finish_processing)

		threading.Thread(target=worker, daemon=True).start()

	def _show_long_translation_dialog(self, chunks, target_lang, source_lang, swap_lang, auto_swap, copy_mode, append_mode):
		try:
			dlg = LongTranslationDialog(
				None,
				chunks,
				target_lang,
				source_lang,
				swap_lang,
				auto_swap,
				copy_mode,
				append_mode,
				self.clipboard_handler,
			)
			dlg.start_translation()
			dlg.ShowModal()
		except Exception as e:
			log.error(f"Long translation dialog failed: {e}")
			ui.message(_("Cannot open translation window."))
		finally:
			self._finish_processing()

	def _open_settings(self):
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			wx.CallAfter(gui.mainFrame.popupSettingsDialog,
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
