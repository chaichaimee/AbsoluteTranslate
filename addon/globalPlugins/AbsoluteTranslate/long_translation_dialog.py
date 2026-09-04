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
	def __init__(self, parent, chunks, target_lang, source_lang, swap_lang, auto_swap, copy_to_clipboard, append_translations, clipboard_handler, on_close=None):
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
		self._on_close_callback = on_close
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
		"""Effective source/target languages are resolved by the caller
		(GlobalPlugin._open_long_translation_async) on a background thread
		before this dialog is ever constructed. Auto-swap detection can
		involve a network call, and doing that here - in __init__, on the
		main thread - blocked the main thread before the dialog could even
		appear (Section 5.1). This method must never perform network I/O;
		it only records the values it was given."""
		self.effective_source_lang = self.source_lang
		self.effective_target_lang = self.target_lang
		log.debug(f"Using pre-resolved languages: source={self.effective_source_lang}, target={self.effective_target_lang}")

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
		keyCode = event.GetKeyCode()
		if keyCode == wx.WXK_ESCAPE:
			self._on_cancel(None)
		elif keyCode in (wx.WXK_MENU, wx.WXK_WINDOWS_MENU) or (keyCode == wx.WXK_F10 and event.ShiftDown()):
			# wx.TextCtrl backed by the native Windows RichEdit control
			# (TE_RICH2) is a long-confirmed wx/MSW limitation: it does not
			# reliably deliver EVT_CONTEXT_MENU, because the native control's
			# own WM_CONTEXTMENU handling intercepts the Menu key / Shift+F10
			# / right-click before wx can translate it into that event - so
			# the custom menu bound there never actually replaced the native
			# Undo/Copy/Paste one. Catch the keyboard-triggered case here
			# instead, ahead of the native control, and consume it (no
			# event.Skip()) so the native menu never gets a chance to show.
			if self.FindFocus() is self.text_ctrl:
				self._show_text_context_menu()
				return
			event.Skip()
		else:
			event.Skip()

	def _create_ui(self):
		main_layout = wx.BoxSizer(wx.VERTICAL)
		self.text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
		self.text_ctrl.SetMinSize((600, 400))
		self.text_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_text_context_menu)
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

	def _on_text_context_menu(self, event):
		# Kept bound as a fallback in case EVT_CONTEXT_MENU does fire on some
		# system/build - the reliable path for the Menu key / Shift+F10 is
		# the interception in _on_char_hook, since this event is not
		# guaranteed to fire at all for a TE_RICH2 control (see notes there).
		self._show_text_context_menu(event.GetPosition())

	def _show_text_context_menu(self, screenPos=None):
		"""Custom context menu on the translation display. The control is
		read-only, so the standard Undo/Redo/Cut/Paste/Delete items are
		always unavailable here and just add noise - replaced with Select
		All/Copy plus the two actions requested as faster to reach than
		tabbing down to the buttons: Continue and Swap."""
		menu = wx.Menu()

		select_all_item = menu.Append(wx.ID_ANY, _("Select All\tCtrl+A"))
		self.text_ctrl.Bind(wx.EVT_MENU, lambda evt: self.text_ctrl.SelectAll(), select_all_item)

		copy_item = menu.Append(wx.ID_ANY, _("Copy\tCtrl+C"))
		copy_item.Enable(bool(self.text_ctrl.GetStringSelection()))
		self.text_ctrl.Bind(wx.EVT_MENU, lambda evt: self.text_ctrl.Copy(), copy_item)

		menu.AppendSeparator()

		continue_item = menu.Append(wx.ID_ANY, _("Continue\tAlt+C"))
		continue_item.Enable(self.continue_btn.IsEnabled())
		self.text_ctrl.Bind(wx.EVT_MENU, self._on_continue, continue_item)

		swap_item = menu.Append(wx.ID_ANY, _("Swap\tAlt+S"))
		swap_item.Enable(self.swap_btn.IsEnabled())
		self.text_ctrl.Bind(wx.EVT_MENU, self._on_swap_language, swap_item)

		# A keyboard-invoked menu (from _on_char_hook, or a mouse event
		# reporting DefaultPosition) has no screen coordinate; let PopupMenu
		# pick its own default placement rather than guessing one.
		if screenPos is None or screenPos == wx.DefaultPosition:
			self.text_ctrl.PopupMenu(menu)
		else:
			self.text_ctrl.PopupMenu(menu, self.text_ctrl.ScreenToClient(screenPos))
		menu.Destroy()

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
			# The Swap button can become reachable/enabled while the current
			# chunk is still translating in the background (it's enabled
			# ahead of the previous chunk's display, not gated on the current
			# one finishing). Previously this returned silently, which is
			# indistinguishable from the button doing nothing at all -
			# reported as "swapping doesn't work" - so speak the actual
			# reason instead of staying quiet (Section 5.11 spirit: no
			# silent failures where a blind user gets zero feedback).
			ui.message(_("This chunk is still translating, please wait."))
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
		resume_index = next(
			(i for i, pair in enumerate(self.chunk_pairs) if pair is None),
			len(self.chunks)
		)
		if resume_index <= 0:
			self._translate_chunk(0)
			return
		self._resume_from_saved_progress(resume_index)

	def _resume_from_saved_progress(self, resume_index):
		"""Restores the view to the last chunk translated in a previous,
		interrupted run (e.g. one stopped by a rate limit or an exhausted
		daily quota), then continues from the first untranslated chunk
		instead of re-translating and re-spending quota on work already
		done."""
		last_done_index = resume_index - 1
		pair = self.chunk_pairs[last_done_index]
		self.current_chunk_index = last_done_index
		self.showing_original = False
		self.text_ctrl.SetValue(pair['translated'])
		self.text_ctrl.SetInsertionPoint(0)
		self.line_indices[last_done_index] = {'original': 0, 'translated': 0}
		self.swap_btn.Enable(True)

		if resume_index >= len(self.chunks):
			ui.message(_("All chunks were already translated in a previous run."))
			self._finish_translation()
			return

		ui.message(_("Resuming saved progress: chunk {current} of {total} already translated.").format(
			current=resume_index, total=len(self.chunks)
		))
		self._translate_chunk(resume_index)

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
				src = self.effective_source_lang
				target = self.effective_target_lang
				engine = translate._get_translation_engine()
				if engine == "gemini":
					api_key = translate._get_gemini_api_key()
					model = translate._get_gemini_model()
					style = translate._get_gemini_style()
					if not api_key:
						raise translate.TranslationError("Gemini API key is empty")
					res = translate.gemini_translate(text, target, src, model, api_key, style)
				else:
					res, _detected = translate.google_translate(text, target, src)
				if not self.closed:
					wx.CallAfter(self._on_translation_complete, index, res, text)
			except translate.TranslationQuotaExceededError:
				log.error(f"Long translation stopped at chunk {index}: Gemini daily quota exceeded")
				if not self.closed:
					wx.CallAfter(self._on_translation_blocked, _(
						"Gemini daily quota exceeded. Translation paused before chunk {current} of "
						"{total} to avoid replacing untranslated text with English text. Progress has "
						"been saved - run this translation again after the quota resets to continue "
						"where it left off."
					).format(current=index + 1, total=len(self.chunks)))
			except translate.TranslationRateLimitError:
				log.error(f"Long translation rate limited at chunk {index}")
				if not self.closed:
					wx.CallAfter(self._on_translation_blocked, _(
						"Translation service is rate limited. Translation paused before chunk {current} "
						"of {total} to avoid replacing untranslated text with English text. Progress has "
						"been saved - run this translation again shortly to continue where it left off."
					).format(current=index + 1, total=len(self.chunks)))
			except translate.TranslationError as e:
				log.error(f"Long translation failed: {e}")
				if not self.closed:
					wx.CallAfter(self._on_error, _("Translation failed: {error}").format(error=str(e)))
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

	def _on_error(self, message=None):
		self.translation_in_progress = False
		ui.message(message or _("Error during translation process."))
		self._finish_translation()

	def _on_translation_blocked(self, message):
		"""Handles a stop caused by a 429 rate limit or an exhausted Gemini
		daily quota. Unlike _on_error, the saved chunk progress is kept on
		disk (cleanup=False) so the run can resume without re-translating,
		and re-spending quota on, chunks already completed."""
		self.translation_in_progress = False
		ui.message(message)
		winsound.Beep(220, 400)
		self._finish_translation(cleanup=False)

	def _finish_translation(self, cleanup=True):
		if self.closed:
			return
		self.continue_btn.Enable(False)
		self.swap_btn.Enable(True)
		self.cancel_btn.SetLabel(_("Close\tAlt+X"))
		self.text_ctrl.SetFocus()
		if cleanup:
			self._cleanup_files()

	def _on_continue(self, event):
		if not self.translation_in_progress and self.current_chunk_index + 1 < len(self.chunks):
			winsound.Beep(440, 100)
			self._translate_chunk(self.current_chunk_index + 1)

	def _on_cancel(self, event):
		self.closed = True
		self._cleanup_files()
		self.Destroy()
		if self._on_close_callback:
			callback = self._on_close_callback
			self._on_close_callback = None
			callback()

	def _on_close(self, event):
		self._on_cancel(None)


