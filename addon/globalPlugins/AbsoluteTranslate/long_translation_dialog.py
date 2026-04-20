# long_translation_dialog.py

import wx
import threading
import winsound
import os
import json
from logHandler import log
import ui
import globalVars

from . import translate
from . import setting

class LongTranslationDialog(wx.Dialog):
	def __init__(self, parent, chunks, target_lang, source_lang, swap_lang, auto_swap, copy_to_clipboard, append_translations, clipboard_handler):
		style = wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER | wx.STAY_ON_TOP
		super().__init__(parent, title=_("Continuous Translation"), style=style)
		self.chunks = chunks
		self.current_chunk_index = 0
		self.target_lang = target_lang
		self.source_lang = source_lang
		self.swap_lang = swap_lang
		self.auto_swap = auto_swap
		self.copy_to_clipboard = copy_to_clipboard
		self.append_translations = append_translations
		self.clipboard_handler = clipboard_handler
		self.translation_in_progress = False
		self.cancelled = False
		self.closed = False
		self.accumulated_clipboard_text = ""
		self.chunk_pairs = []
		self.showing_original = False
		self.line_indices = {}
		
		# Calculate effective source and target languages based on full document
		self._calculate_effective_languages()
		
		self._init_storage()
		self._load_or_init_pairs()
		self._create_ui()
		self.CenterOnParent()
		
		self.Bind(wx.EVT_CLOSE, self._on_close)
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
		self.Bind(wx.EVT_SHOW, self._on_show)

	def _calculate_effective_languages(self):
		"""Determine the actual source and target languages for the entire document."""
		full_text = "\n".join(self.chunks)
		
		if self.source_lang != "auto":
			self.effective_source_lang = self.source_lang
			self.effective_target_lang = self.target_lang
			log.debug(f"Using manual source: {self.effective_source_lang}")
			return
		
		# Auto-detect main language of the full document
		detected_main = translate.detect_language(full_text)
		log.info(f"Detected main document language: {detected_main}")
		
		if self.auto_swap and detected_main == self.target_lang:
			# Document language matches target, swap to swap_lang
			self.effective_source_lang = detected_main
			self.effective_target_lang = self.swap_lang
			ui.message(_("Document language ({}) matches target. Auto-swapping to {}.").format(
				translate.LANGUAGES.get(detected_main, detected_main),
				translate.LANGUAGES.get(self.swap_lang, self.swap_lang)
			))
			log.info(f"Auto-swap triggered: source={detected_main}, target={self.swap_lang}")
		else:
			# Normal case: source is detected, target as configured
			self.effective_source_lang = detected_main if detected_main != "auto" else "en"
			self.effective_target_lang = self.target_lang
			if self.auto_swap and detected_main != self.target_lang:
				log.debug(f"No swap needed: detected={detected_main}, target={self.target_lang}")
		
		log.info(f"Effective languages for long translation: source={self.effective_source_lang}, target={self.effective_target_lang}")

	def _on_show(self, event):
		if event.IsShown():
			self.Raise()
			self.SetFocus()
			self.text_ctrl.SetFocus()

	def _init_storage(self):
		cfg_dir = setting.get_config_dir()
		if not cfg_dir:
			user_config = globalVars.appArgs.configPath or os.path.join(os.environ.get("APPDATA", ""), "nvda")
			cfg_dir = os.path.join(user_config, "ChaiChaimee", "AbsoluteTranslate")
		self.storage_dir = cfg_dir
		try:
			os.makedirs(self.storage_dir, exist_ok=True)
		except Exception as e:
			log.error(f"Cannot create storage dir: {e}")

	def _get_pairs_path(self):
		return os.path.join(self.storage_dir, f"chunk_pairs_{len(self.chunks)}.json")

	def _load_or_init_pairs(self):
		path = self._get_pairs_path()
		if os.path.exists(path):
			try:
				with open(path, "r", encoding="utf-8") as f:
					data = json.load(f)
					if data.get("chunk_count") == len(self.chunks):
						self.chunk_pairs = data.get("pairs", [])
						return
			except Exception:
				pass
		self.chunk_pairs = [None] * len(self.chunks)

	def _save_pairs(self):
		path = self._get_pairs_path()
		try:
			with open(path, "w", encoding="utf-8") as f:
				data = {"chunk_count": len(self.chunks), "pairs": self.chunk_pairs}
				json.dump(data, f)
		except Exception as e:
			log.error(f"Save pairs failed: {e}")

	def _cleanup_files(self):
		try:
			os.remove(self._get_pairs_path())
		except Exception:
			pass

	def _on_char_hook(self, event):
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self._on_cancel(None)
		else:
			event.Skip()

	def _create_ui(self):
		main_layout = wx.BoxSizer(wx.VERTICAL)
		self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		self.text_ctrl.SetMinSize((600, 400))
		main_layout.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

		btn_layout = wx.BoxSizer(wx.HORIZONTAL)
		self.continue_btn = wx.Button(self, label=_("&Continue\tAlt+C"))
		self.continue_btn.Bind(wx.EVT_BUTTON, self._on_continue)
		self.continue_btn.Enable(False)
		btn_layout.Add(self.continue_btn, 0, wx.ALL, 5)

		self.swap_btn = wx.Button(self, label=_("&Swap\tAlt+S"))
		self.swap_btn.Bind(wx.EVT_BUTTON, self._on_swap_language)
		self.swap_btn.Enable(False)
		btn_layout.Add(self.swap_btn, 0, wx.ALL, 5)

		self.cancel_btn = wx.Button(self, label=_("Cancel\tAlt+X"))
		self.cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
		btn_layout.Add(self.cancel_btn, 0, wx.ALL, 5)

		main_layout.Add(btn_layout, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 10)
		self.SetSizer(main_layout)
		self.Fit()

	def _save_current_line(self):
		if self.current_chunk_index is None:
			return
		pos = self.text_ctrl.GetInsertionPoint()
		result = self.text_ctrl.PositionToXY(pos)
		line_no = result[-1] if isinstance(result, (tuple, list)) else 0
		mode = 'original' if self.showing_original else 'translated'
		if self.current_chunk_index not in self.line_indices:
			self.line_indices[self.current_chunk_index] = {'original': 0, 'translated': 0}
		self.line_indices[self.current_chunk_index][mode] = line_no

	def _restore_line(self):
		if self.current_chunk_index not in self.line_indices:
			return
		mode = 'original' if self.showing_original else 'translated'
		target_line = self.line_indices[self.current_chunk_index].get(mode, 0)
		max_lines = self.text_ctrl.GetNumberOfLines()
		if target_line >= max_lines:
			target_line = max_lines - 1 if max_lines > 0 else 0
		pos = self.text_ctrl.XYToPosition(0, target_line)
		if pos != wx.ID_ANY:
			self.text_ctrl.SetInsertionPoint(pos)
			self.text_ctrl.ShowPosition(pos)

	def _on_swap_language(self, event):
		if not self.chunk_pairs or self.chunk_pairs[self.current_chunk_index] is None:
			return
		try:
			self._save_current_line()
			pair = self.chunk_pairs[self.current_chunk_index]
			if self.showing_original:
				self.text_ctrl.SetValue(pair['translated'])
				self.showing_original = False
			else:
				self.text_ctrl.SetValue(pair['original'])
				self.showing_original = True
			current_mode = 'original' if self.showing_original else 'translated'
			prev_mode = 'translated' if self.showing_original else 'original'
			if self.current_chunk_index in self.line_indices:
				self.line_indices[self.current_chunk_index][current_mode] = self.line_indices[self.current_chunk_index][prev_mode]
			self._restore_line()
			self.text_ctrl.SetFocus()
			ui.message(_("Swapped"))
		except Exception as e:
			log.error(f"Swap failed: {e}")

	def start_translation(self):
		self._translate_chunk(0)

	def _translate_chunk(self, index):
		if index >= len(self.chunks) or self.cancelled or self.closed:
			self._finish_translation()
			return
		self.translation_in_progress = True
		self.continue_btn.Enable(False)
		self.swap_btn.Enable(False)
		self.current_chunk_index = index
		self._update_status()
		def worker():
			try:
				text = self.chunks[index]
				# Use pre-calculated effective languages for consistency
				src = self.effective_source_lang
				target = self.effective_target_lang
				res = translate.google_translate(text, target, src)
				if not self.closed:
					wx.CallAfter(self._on_translation_complete, index, res, text)
			except Exception as e:
				log.error(f"Translation thread failed: {e}")
				if not self.closed:
					wx.CallAfter(self._on_error)
		threading.Thread(target=worker, daemon=True).start()

	def _on_translation_complete(self, index, translated, original):
		if self.closed or self.cancelled:
			return
		self.translation_in_progress = False
		if not translated:
			ui.message(_("Translation failed."))
			self._finish_translation()
			return
		self.chunk_pairs[index] = {'original': original, 'translated': translated}
		self._save_pairs()
		self.showing_original = False
		self.text_ctrl.SetValue(translated)
		self.text_ctrl.SetInsertionPoint(0)
		self.line_indices[index] = {'original': 0, 'translated': 0}
		self._handle_clipboard(translated, index)
		if index + 1 < len(self.chunks):
			self.continue_btn.Enable(True)
			self.swap_btn.Enable(True)
			self.text_ctrl.SetFocus()
		else:
			self._finish_translation()
		self.text_ctrl.SetFocus()

	def _handle_clipboard(self, text, index):
		if not self.copy_to_clipboard:
			return
		if index == 0:
			self.clipboard_handler.set_clipboard_text(text)
			self.accumulated_clipboard_text = text if self.append_translations else ""
		elif self.append_translations:
			if len(text) > 2000:
				self.clipboard_handler.append_text_silent(text)
				self.accumulated_clipboard_text += f"\n{text}"
				log.debug(f"Appended chunk of length {len(text)} to clipboard")
			else:
				log.debug(f"Skipped append: chunk length {len(text)} <= 2000")
		else:
			self.clipboard_handler.set_clipboard_text(text)

	def _update_status(self):
		total = len(self.chunks)
		current = self.current_chunk_index + 1
		if current < total:
			self.continue_btn.SetLabel(_("&Continue\tAlt+C ({} / {})").format(current, total))

	def _on_error(self):
		self.translation_in_progress = False
		ui.message(_("Error during translation process."))
		self._finish_translation()

	def _finish_translation(self):
		if self.closed:
			return
		self.continue_btn.Enable(False)
		self.swap_btn.Enable(True)
		self.cancel_btn.SetLabel(_("Close\tAlt+X"))
		self.text_ctrl.SetFocus()
		self._cleanup_files()

	def _on_continue(self, event):
		if not self.translation_in_progress and self.current_chunk_index + 1 < len(self.chunks):
			winsound.Beep(440, 100)
			self._translate_chunk(self.current_chunk_index + 1)

	def _on_cancel(self, event):
		self.closed = True
		self._cleanup_files()
		self.Destroy()

	def _on_close(self, event):
		self._on_cancel(None)