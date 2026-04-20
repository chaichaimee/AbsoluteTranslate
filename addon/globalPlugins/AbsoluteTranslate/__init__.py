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
from logHandler import log

from . import translate
from . import setting
from .clipboard_utils import ClipboardHandler
from .speech_utils import SpeechHistoryHandler
from .long_translation_dialog import LongTranslationDialog

addonHandler.initTranslation()

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
		self.speech_history.restore_patch()
		translate.save_cache()
		if self._action_timer:
			self._action_timer.Stop()
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			panels = gui.settingsDialogs.NVDASettingsDialog.categoryClasses
			if AbsoluteTranslateSettingsPanel in panels:
				panels.remove(AbsoluteTranslateSettingsPanel)
		except Exception:
			pass

	def _get_selected_text(self):
		obj = api.getFocusObject()
		text = self.clipboard_handler.get_selected_text(obj)
		if text:
			log.info(f"Selected text: {text[:100]}...")
			return text
		return ""

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
		try:
			if self._tap_count == 1:
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
					self._translate_long_text_with_prompt(
						full_text, tgt, src, swap, auto_swap,
						copy_to_clipboard=copy_mode,
						append_translations=append_mode
					)
				else:
					translated = translate.translate_text(full_text, tgt, src, swap, auto_swap)
					self._output_translation(translated, do_copy=copy_mode, do_append=False)
					
			elif self._tap_count == 2:
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
				continuous = setting.config.get("continuous_translation", False)
				append_mode = setting.config.get("append_translations", False)
				
				if continuous and len(full_text) > 1500:
					self._translate_long_text_with_prompt(
						full_text, tgt, src, swap, auto_swap,
						copy_to_clipboard=copy_mode,
						append_translations=append_mode
					)
				else:
					translated = translate.translate_text(full_text, tgt, src, swap, auto_swap)
					self._output_translation(translated, do_copy=copy_mode, do_append=False)
					
			elif self._tap_count >= 3:
				log.info("Triple tap: open settings")
				self._open_settings()
		finally:
			self._tap_count = 0

	def _translate_long_text_with_prompt(self, full_text, target_lang, source_lang, swap_lang, auto_swap, copy_to_clipboard, append_translations):
		chunks = translate.split_text_into_chunks(full_text, max_chars=translate.MAX_CHARS)
		if not chunks:
			ui.message(_("No text to translate."))
			return
		
		dlg = LongTranslationDialog(
			None, chunks, target_lang, source_lang, swap_lang, auto_swap,
			copy_to_clipboard, append_translations, self.clipboard_handler
		)
		dlg.start_translation()
		dlg.ShowModal()

	def _open_settings(self):
		try:
			from .setting import AbsoluteTranslateSettingsPanel
			wx.CallAfter(gui.mainFrame._popupSettingsDialog,
						 gui.settingsDialogs.NVDASettingsDialog,
						 AbsoluteTranslateSettingsPanel)
		except Exception as e:
			log.error(f"Open settings failed: {e}")
			ui.message(_("Cannot open settings dialog"))

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