# setting.py

import wx
import gui
import os
import json
import globalVars
from gui.settingsDialogs import SettingsPanel
from gui import guiHelper
from logHandler import log
import addonHandler

addonHandler.initTranslation()

from . import translate

CONFIG_FILE = None
config = {
	"source_lang": "auto",
	"target_lang": "en",
	"auto_swap": False,
	"swap_lang": "en",
	"copy_to_clipboard": False,
	"continuous_translation": False,
	"append_translations": False,
}

def get_config_dir():
	user_config_dir = globalVars.appArgs.configPath
	if not user_config_dir:
		user_config_dir = os.path.join(os.environ.get("APPDATA", ""), "nvda")
	chai_dir = os.path.join(user_config_dir, "ChaiChaimee", "AbsoluteTranslate")
	try:
		os.makedirs(chai_dir, exist_ok=True)
		log.debug(f"Config dir: {chai_dir}")
	except Exception as e:
		log.error(f"Failed to create config dir: {e}")
		return None
	return chai_dir

def get_config_path():
	global CONFIG_FILE
	if CONFIG_FILE:
		return CONFIG_FILE
	cfg_dir = get_config_dir()
	if cfg_dir:
		CONFIG_FILE = os.path.join(cfg_dir, "AbsoluteTranslate.json")
		log.debug(f"Config file: {CONFIG_FILE}")
	return CONFIG_FILE

def load_config():
	global config
	path = get_config_path()
	if path and os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				saved = json.load(f)
				config.update(saved)
				log.info("Config loaded from JSON")
		except Exception as e:
			log.error(f"Load config failed: {e}")
	else:
		log.info("No config file, using defaults and creating new")
		save_config()

def save_config():
	path = get_config_path()
	if not path:
		return
	try:
		os.makedirs(os.path.dirname(path), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			json.dump(config, f, ensure_ascii=False, indent=2)
		log.debug("Config saved to JSON")
	except Exception as e:
		log.error(f"Save config failed: {e}")

class AbsoluteTranslateSettingsPanel(SettingsPanel):
	title = _("Absolute Translate")

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		lang_items = [(translate.LANGUAGES[code], code) for code in translate.LANGUAGES]
		lang_items.sort(key=lambda x: x[0])
		lang_choices = [item[0] for item in lang_items]
		lang_codes = [item[1] for item in lang_items]

		self.source_lang_ctrl = helper.addLabeledControl(
			_("Source language (Auto Detect = auto):"),
			wx.Choice, choices=lang_choices
		)
		src_idx = lang_codes.index(config.get("source_lang", "auto"))
		self.source_lang_ctrl.SetSelection(src_idx)

		self.target_lang_ctrl = helper.addLabeledControl(
			_("Target language:"),
			wx.Choice, choices=lang_choices
		)
		tgt_idx = lang_codes.index(config.get("target_lang", "en"))
		self.target_lang_ctrl.SetSelection(tgt_idx)

		self.auto_swap_cb = helper.addItem(
			wx.CheckBox(self, label=_("Automatically swap when source matches target"))
		)
		self.auto_swap_cb.SetValue(config.get("auto_swap", False))

		self.swap_lang_container = wx.BoxSizer(wx.HORIZONTAL)
		swap_label = wx.StaticText(self, label=_("Swap to language:"))
		self.swap_lang_ctrl = wx.Choice(self, choices=lang_choices)
		swap_idx = lang_codes.index(config.get("swap_lang", "en"))
		self.swap_lang_ctrl.SetSelection(swap_idx)
		self.swap_lang_container.Add(swap_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
		self.swap_lang_container.Add(self.swap_lang_ctrl, 1, wx.EXPAND)
		helper.addItem(self.swap_lang_container)
		self.swap_lang_container.ShowItems(config.get("auto_swap", False))

		self.auto_swap_cb.Bind(wx.EVT_CHECKBOX, self._on_auto_swap_toggle)

		self.copy_to_clipboard_cb = helper.addItem(
			wx.CheckBox(self, label=_("Save translations to clipboard"))
		)
		self.copy_to_clipboard_cb.SetValue(config.get("copy_to_clipboard", False))

		helper.addItem(wx.StaticLine(self, wx.ID_ANY))

		self.continuous_translation_cb = helper.addItem(
			wx.CheckBox(self, label=_("Continuous translation"))
		)
		self.continuous_translation_cb.SetValue(config.get("continuous_translation", False))

		# Updated label to clarify this option only applies to long translation and requires text >2000 chars
		self.append_translations_cb = helper.addItem(
			wx.CheckBox(self, label=_("Append translations only in long translation (if text >2000 chars)"))
		)
		self.append_translations_cb.SetValue(config.get("append_translations", False))

	def _on_auto_swap_toggle(self, event):
		show = self.auto_swap_cb.GetValue()
		self.swap_lang_container.ShowItems(show)
		self.Layout()
		self.GetSizer().Layout()

	def onSave(self):
		lang_items = [(translate.LANGUAGES[code], code) for code in translate.LANGUAGES]
		lang_items.sort(key=lambda x: x[0])
		lang_codes = [item[1] for item in lang_items]

		config["source_lang"] = lang_codes[self.source_lang_ctrl.GetSelection()]
		config["target_lang"] = lang_codes[self.target_lang_ctrl.GetSelection()]
		config["auto_swap"] = self.auto_swap_cb.GetValue()
		config["swap_lang"] = lang_codes[self.swap_lang_ctrl.GetSelection()]
		config["copy_to_clipboard"] = self.copy_to_clipboard_cb.GetValue()
		config["continuous_translation"] = self.continuous_translation_cb.GetValue()
		config["append_translations"] = self.append_translations_cb.GetValue()
		save_config()