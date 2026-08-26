# clipboard_utils.py

import addonHandler
addonHandler.initTranslation()

import api
import winUser
import gui
import keyboardHandler
import textInfos
import browseMode
import logHandler
import hashlib
import sys
import threading
import core
from logHandler import log


class ClipboardHandler:

	def __init__(self):
		self._logger = log
		self._original_clipboard_data = ""

	def normalize_text(self, text):
		if not text:
			return ""
		text = "".join(char for char in text if char.isprintable() or char in {"\r", "\n", " "})
		text = text.replace("\r\n", "\n").replace("\r", "\n")
		return text

	def calculate_sha256(self, text):
		normalized_text = self.normalize_text(text)
		return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()

	def set_clipboard_text(self, text):
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				winUser.emptyClipboard()
				winUser.setClipboardData(winUser.CF_UNICODETEXT, text.replace('\n', '\r\n'))
			self._logger.info("Clipboard set with new text")
			return True
		except Exception as e:
			self._logger.error(f"set_clipboard_text failed: {e}")
			return False

	def get_selected_text_async(self, obj_param, callback):
		text = self._extract_selected_text_sync(obj_param)
		if text:
			core.callLater(0, callback, text)
			return
		self._fallback_ctrl_c_async(callback)

	def _extract_selected_text_sync(self, obj_param):
		current_obj = obj_param
		selected_text = None

		try:
			if hasattr(current_obj, 'treeInterceptor') and current_obj.treeInterceptor:
				ti = current_obj.treeInterceptor
				if hasattr(ti, 'selection'):
					sel = ti.selection
					if sel and hasattr(sel, 'isCollapsed') and not sel.isCollapsed:
						if hasattr(sel, 'clipboardText'):
							selected_text = sel.clipboardText
						elif hasattr(sel, 'text'):
							selected_text = sel.text
						if selected_text:
							return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
		except Exception as e:
			self._logger.warning(f"treeInterceptor selection failed: {e}")

		try:
			target_obj_for_text = None
			if hasattr(current_obj, 'treeInterceptor') and isinstance(current_obj.treeInterceptor, browseMode.BrowseModeDocumentTreeInterceptor):
				target_obj_for_text = current_obj.treeInterceptor
			elif hasattr(current_obj, 'makeTextInfo'):
				target_obj_for_text = current_obj

			if target_obj_for_text:
				try:
					info = target_obj_for_text.makeTextInfo(textInfos.POSITION_SELECTION)
					if info and not info.isCollapsed:
						if hasattr(info, 'clipboardText'):
							selected_text = info.clipboardText
						elif hasattr(info, 'text'):
							selected_text = info.text
						if selected_text:
							return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
				except (RuntimeError, NotImplementedError) as e:
					self._logger.warning(f"makeTextInfo selection failed: {str(e)}")
		except Exception as e_info:
			self._logger.error(f"Error with makeTextInfo attempt: {str(e_info)}")

		value_text = self._get_value_from_object(current_obj)
		if value_text:
			return value_text

		caret_text = self._get_text_from_caret(current_obj)
		if caret_text:
			return caret_text

		return None

	def _fallback_ctrl_c_async(self, callback):
		self._original_clipboard_data = ""
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				self._original_clipboard_data = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
				winUser.emptyClipboard()
		except Exception as e:
			self._logger.warning(f"Cannot access clipboard for backup: {e}")

		try:
			keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
		except Exception as e:
			self._logger.warning(f"Ctrl+C gesture failed: {e}")
			self._restore_clipboard(self._original_clipboard_data)
			core.callLater(0, callback, None)
			return

		core.callLater(50, self._check_clipboard_after_copy, callback, 0)

	def _check_clipboard_after_copy(self, callback, attempt):
		clipboard_text = ""
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				clipboard_text = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
		except Exception as e:
			self._logger.warning(f"Clipboard read attempt failed: {e}")

		if clipboard_text:
			self._restore_clipboard(self._original_clipboard_data)
			core.callLater(0, callback, clipboard_text.replace('\r\n', '\n').replace('\r', '\n').strip())
			return

		if attempt + 1 < 2:
			try:
				keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
			except Exception as e:
				self._logger.warning(f"Ctrl+C retry failed: {e}")
				self._restore_clipboard(self._original_clipboard_data)
				core.callLater(0, callback, None)
				return
			core.callLater(50, self._check_clipboard_after_copy, callback, attempt + 1)
		else:
			self._restore_clipboard(self._original_clipboard_data)
			core.callLater(0, callback, None)

	def _restore_clipboard(self, original_text):
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				winUser.emptyClipboard()
				if original_text:
					winUser.setClipboardData(winUser.CF_UNICODETEXT, original_text)
		except Exception as e:
			self._logger.warning(f"Failed to restore clipboard: {e}")

	def _get_value_from_object(self, obj):
		try:
			if hasattr(obj, 'value') and obj.value:
				value_text = str(obj.value)
				if value_text and len(value_text.strip()) > 0:
					self._logger.info(f"Retrieved value from object: {value_text[:50]}...")
					return value_text.strip()
		except Exception as e:
			self._logger.warning(f"Failed to get value from object: {e}")
		return None

	def _get_text_from_caret(self, obj):
		try:
			if hasattr(obj, 'makeTextInfo') and hasattr(textInfos, 'POSITION_CARET'):
				caret_info = obj.makeTextInfo(textInfos.POSITION_CARET)
				if caret_info and hasattr(caret_info, 'text'):
					caret_text = caret_info.text
					if caret_text and len(caret_text.strip()) > 0:
						self._logger.info(f"Retrieved caret text: {caret_text[:50]}...")
						return caret_text.strip()
		except Exception as e:
			self._logger.warning(f"Failed to get caret text: {e}")
		return None

	def append_to_clipboard(self, text_to_append):
		clipData = ""
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				clipData = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
				if clipData and not isinstance(clipData, str):
					return {
						"success": False,
						"appended": False,
						"message": _("Cannot append to non-text clipboard content")
					}
		except Exception as e:
			self._logger.error(f"Error reading clipboard: {str(e)}")
			clipData = ""

		processed_text_to_append = text_to_append

		if clipData:
			clipData_normalized = clipData.replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')
			processed_text_to_append_normalized = processed_text_to_append.replace('\r\n', '\n').replace('\r', '\n').lstrip('\n')
			newText = clipData_normalized + "\n" + processed_text_to_append_normalized
			appended = True
		else:
			newText = processed_text_to_append.replace('\r\n', '\n').replace('\r', '\n')
			appended = False

		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				winUser.emptyClipboard()
				winUser.setClipboardData(winUser.CF_UNICODETEXT, newText.replace('\n', '\r\n'))
			return {
				"success": True,
				"appended": appended,
				"message": _("Appended") if appended else _("Copied")
			}
		except Exception as e:
			self._logger.error(f"Error writing to clipboard: {str(e)}")
			return {
				"success": False,
				"appended": False,
				"message": _("Error writing to clipboard")
			}

	def append_text_silent(self, text_to_append):
		clipData = ""
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				clipData = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
				if clipData and not isinstance(clipData, str):
					self._logger.warning("Clipboard contains non-text data, cannot append")
					return False
		except Exception as e:
			self._logger.error(f"append_text_silent: Error reading clipboard: {e}")
			clipData = ""

		processed_text_to_append = text_to_append

		if clipData:
			clipData_normalized = clipData.replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')
			processed_text_to_append_normalized = processed_text_to_append.replace('\r\n', '\n').replace('\r', '\n').lstrip('\n')
			newText = clipData_normalized + "\n" + processed_text_to_append_normalized
		else:
			newText = processed_text_to_append.replace('\r\n', '\n').replace('\r', '\n')

		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				winUser.emptyClipboard()
				winUser.setClipboardData(winUser.CF_UNICODETEXT, newText.replace('\n', '\r\n'))
			return True
		except Exception as e:
			self._logger.error(f"append_text_silent: Error writing to clipboard: {e}")
			return False