# clipboard_utils.py

import addonHandler
addonHandler.initTranslation()

import api
import winUser
import gui
import time
import keyboardHandler
import textInfos
import browseMode
import logging
import hashlib
import sys

class ClipboardHandler:
	
	def __init__(self):
		self.logger = logging.getLogger(__name__)
	
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
			self.logger.info("Clipboard set with new text")
			return True
		except Exception as e:
			self.logger.error(f"set_clipboard_text failed: {e}")
			return False
	
	def get_selected_text(self, obj_param):
		if sys.version_info >= (3, 13):
			return self._get_selected_text_2026(obj_param)
		else:
			return self._get_selected_text_2025(obj_param)
	
	def _get_selected_text_2025(self, obj_param):
		self.logger.info("SimpleCopy: get_selected_text started (2025).")
		current_obj = obj_param
		selected_text = None
		
		try:
			target_obj_for_text = None
			if hasattr(current_obj, 'treeInterceptor') and isinstance(current_obj.treeInterceptor, browseMode.BrowseModeDocumentTreeInterceptor):
				target_obj_for_text = current_obj.treeInterceptor
				self.logger.info("Using treeInterceptor for text info.")
			elif hasattr(current_obj, 'makeTextInfo'):
				target_obj_for_text = current_obj
			
			if target_obj_for_text:
				try:
					info = target_obj_for_text.makeTextInfo(textInfos.POSITION_SELECTION)
					if info and not info.isCollapsed:
						selected_text = info.clipboardText
						if selected_text:
							self.logger.info(f"makeTextInfo retrieved: {repr(selected_text[:50])}...")
							return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
				except (RuntimeError, NotImplementedError) as e:
					self.logger.warning(f"makeTextInfo selection failed: {str(e)}")
			else:
				self.logger.info("No makeTextInfo available.")
		
		except Exception as e_info:
			self.logger.error(f"Error with makeTextInfo attempt: {str(e_info)}")
		
		self.logger.info("makeTextInfo failed, attempting Ctrl+C fallback.")
		original_clipboard_data = ""
		try:
			with winUser.openClipboard(gui.mainFrame.Handle):
				original_clipboard_data = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
				winUser.emptyClipboard()
			
			keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
			time.sleep(0.05)
			
			with winUser.openClipboard(gui.mainFrame.Handle):
				clipboard_text = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
			
			if clipboard_text:
				selected_text = clipboard_text
				self.logger.info(f"Ctrl+C fallback retrieved: {repr(selected_text[:50])}...")
				return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
		
		except Exception as e_fallback:
			self.logger.error(f"Ctrl+C fallback failed: {str(e_fallback)}")
		finally:
			try:
				with winUser.openClipboard(gui.mainFrame.Handle):
					winUser.emptyClipboard()
					if original_clipboard_data:
						winUser.setClipboardData(winUser.CF_UNICODETEXT, original_clipboard_data)
			except Exception as e_restore:
				self.logger.error(f"Failed to restore clipboard: {str(e_restore)}")
		
		self.logger.info("No selected text found (2025).")
		return None
	
	def _get_selected_text_2026(self, obj_param):
		self.logger.info("SimpleCopy: get_selected_text started (2026).")
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
							self.logger.info(f"treeInterceptor.selection.clipboardText/text success: {repr(selected_text[:50])}")
							return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
		except Exception as e:
			self.logger.warning(f"treeInterceptor selection failed: {e}")
		
		try:
			target_obj_for_text = None
			if hasattr(current_obj, 'treeInterceptor') and isinstance(current_obj.treeInterceptor, browseMode.BrowseModeDocumentTreeInterceptor):
				target_obj_for_text = current_obj.treeInterceptor
				self.logger.info("Using treeInterceptor for makeTextInfo.")
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
							self.logger.info(f"makeTextInfo.clipboardText/text success: {repr(selected_text[:50])}...")
							return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
				except (RuntimeError, NotImplementedError) as e:
					self.logger.warning(f"makeTextInfo selection failed: {str(e)}")
			else:
				self.logger.info("No makeTextInfo available.")
		
		except Exception as e_info:
			self.logger.error(f"Error with makeTextInfo attempt: {str(e_info)}")
		
		self.logger.info("Falling back to Ctrl+C method (2026).")
		original_clipboard_data = ""
		for attempt in range(3):
			try:
				with winUser.openClipboard(gui.mainFrame.Handle):
					original_clipboard_data = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
					winUser.emptyClipboard()
				
				keyboardHandler.KeyboardInputGesture.fromName("control+c").send()
				time.sleep(0.1)
				
				with winUser.openClipboard(gui.mainFrame.Handle):
					clipboard_text = winUser.getClipboardData(winUser.CF_UNICODETEXT) or ""
				
				if clipboard_text:
					selected_text = clipboard_text
					self.logger.info(f"Ctrl+C fallback attempt {attempt+1} retrieved: {repr(selected_text[:50])}...")
					return selected_text.replace('\r\n', '\n').replace('\r', '\n').strip()
			except Exception as e_fallback:
				self.logger.warning(f"Ctrl+C fallback attempt {attempt+1} failed: {str(e_fallback)}")
				time.sleep(0.05)
			finally:
				try:
					with winUser.openClipboard(gui.mainFrame.Handle):
						winUser.emptyClipboard()
						if original_clipboard_data:
							winUser.setClipboardData(winUser.CF_UNICODETEXT, original_clipboard_data)
				except Exception as e_restore:
					self.logger.warning(f"Failed to restore clipboard: {str(e_restore)}")
		
		self.logger.info("No selected text found (2026).")
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
			self.logger.error(f"Error reading clipboard: {str(e)}")
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
			self.logger.error(f"Error writing to clipboard: {str(e)}")
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
					self.logger.warning("Clipboard contains non-text data, cannot append")
					return False
		except Exception as e:
			self.logger.error(f"append_text_silent: Error reading clipboard: {e}")
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
			self.logger.error(f"append_text_silent: Error writing to clipboard: {e}")
			return False