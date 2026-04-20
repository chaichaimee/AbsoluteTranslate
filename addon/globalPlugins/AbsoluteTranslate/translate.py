# translate.py

import json
import os
import urllib.request as urllibRequest
import urllib.parse
import urllib.error
from logHandler import log
import time
import re

LANGUAGES = {
	"auto": "Auto Detect",
	"af": "Afrikaans", "ak": "Akan", "am": "Amharic", "ar": "Arabic",
	"as": "Assamese", "ay": "Aymara", "az": "Azerbaijani", "be": "Belarusian",
	"bg": "Bulgarian", "bho": "Bhojpuri", "bm": "Bambara", "bn": "Bengali",
	"bs": "Bosnian", "ca": "Catalan", "ceb": "Cebuano", "ckb": "Kurdish (Sorani)",
	"co": "Corsican", "cs": "Czech", "cy": "Welsh", "da": "Danish",
	"de": "German", "doi": "Dogri", "dv": "Dhivehi", "ee": "Ewe",
	"el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
	"et": "Estonian", "eu": "Basque", "fa": "Persian", "fi": "Finnish",
	"fil": "Filipino", "fr": "French", "fy": "Frisian", "ga": "Irish",
	"gd": "Scots Gaelic", "gl": "Galician", "gn": "Guarani", "gom": "Konkani",
	"gu": "Gujarati", "ha": "Hausa", "haw": "Hawaiian", "he": "Hebrew",
	"hi": "Hindi", "hmn": "Hmong", "hr": "Croatian", "ht": "Haitian Creole",
	"hu": "Hungarian", "hy": "Armenian", "id": "Indonesian", "ig": "Igbo",
	"ilo": "Ilocano", "is": "Icelandic", "it": "Italian", "ja": "Japanese",
	"jv": "Javanese", "ka": "Georgian", "kk": "Kazakh", "km": "Khmer",
	"kn": "Kannada", "ko": "Korean", "kri": "Krio", "ku": "Kurdish (Kurmanji)",
	"ky": "Kyrgyz", "la": "Latin", "lb": "Luxembourgish", "lg": "Luganda",
	"ln": "Lingala", "lo": "Lao", "lt": "Lithuanian", "lus": "Mizo",
	"lv": "Latvian", "mai": "Maithili", "mg": "Malagasy", "mi": "Maori",
	"mk": "Macedonian", "ml": "Malayalam", "mn": "Mongolian", "mni-Mtei": "Meiteilon (Manipuri)",
	"mr": "Marathi", "ms": "Malay", "mt": "Maltese", "my": "Myanmar (Burmese)",
	"ne": "Nepali", "nl": "Dutch", "no": "Norwegian", "nso": "Northern Sotho",
	"ny": "Chichewa", "om": "Oromo", "or": "Odia", "pa": "Punjabi",
	"pl": "Polish", "ps": "Pashto", "pt": "Portuguese", "qu": "Quechua",
	"ro": "Romanian", "ru": "Russian", "rw": "Kinyarwanda", "sa": "Sanskrit",
	"sd": "Sindhi", "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian",
	"sm": "Samoan", "sn": "Shona", "so": "Somali", "sq": "Albanian",
	"sr": "Serbian", "st": "Sesotho", "su": "Sundanese", "sv": "Swedish",
	"sw": "Swahili", "ta": "Tamil", "te": "Telugu", "tg": "Tajik",
	"th": "Thai", "ti": "Tigrinya", "tk": "Turkmen", "tl": "Tagalog",
	"tr": "Turkish", "ts": "Tsonga", "tt": "Tatar", "ug": "Uyghur",
	"uk": "Ukrainian", "ur": "Urdu", "uz": "Uzbek", "vi": "Vietnamese",
	"xh": "Xhosa", "yi": "Yiddish", "yo": "Yoruba", "zh": "Chinese",
	"zh-CN": "Chinese (Simplified)", "zh-TW": "Chinese (Traditional)", "zu": "Zulu",
}

MAX_CHARS = 5000

_cache = {}
CACHE_PATH = None

def get_cache_path():
	global CACHE_PATH
	if CACHE_PATH:
		return CACHE_PATH
	from . import setting
	cfg_dir = setting.get_config_dir()
	if cfg_dir:
		CACHE_PATH = os.path.join(cfg_dir, "AbsoluteTranslate_cache.json")
	return CACHE_PATH

def load_cache():
	global _cache
	path = get_cache_path()
	if path and os.path.exists(path):
		try:
			with open(path, "r", encoding="utf-8") as f:
				_cache = json.load(f)
		except Exception:
			pass

def save_cache():
	path = get_cache_path()
	if path:
		try:
			os.makedirs(os.path.dirname(path), exist_ok=True)
			with open(path, "w", encoding="utf-8") as f:
				json.dump(_cache, f, ensure_ascii=False, indent=2)
		except Exception:
			pass

def detect_language(text):
	if not text or not text.strip():
		return "auto"
	try:
		url = "https://translate.googleapis.com/translate_a/single"
		params = {
			"client": "gtx",
			"sl": "auto",
			"tl": "en",
			"dt": "ld",
			"q": text[:500]
		}
		full_url = f"{url}?{urllib.parse.urlencode(params)}"
		req = urllibRequest.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
		with urllibRequest.build_opener().open(req, timeout=10) as resp:
			data = json.loads(resp.read().decode('utf-8'))
			if isinstance(data, list) and len(data) > 2 and isinstance(data[2], str):
				return data[2]
			if isinstance(data[0], list) and len(data[0]) > 0 and isinstance(data[0][0], list) and len(data[0][0]) > 1:
				return data[0][0][1]
	except Exception as e:
		log.warning(f"Language detection failed: {e}")
	return "auto"

def _clean_text_for_translate(text):
	"""Remove control characters and normalize line breaks."""
	if not text:
		return ""
	# Remove non-printable control characters except newline and tab
	cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
	# Replace carriage returns and multiple newlines with single newline
	cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
	# Trim excessive whitespace but keep structure
	return cleaned.strip()

def google_translate(text, target_lang, source_lang="auto", retry=2):
	if not text or not text.strip():
		log.debug("google_translate: empty text")
		return text
	
	cleaned_text = _clean_text_for_translate(text)
	if not cleaned_text:
		return text
	
	# Try GET first, fallback to POST on error
	for attempt in range(retry + 1):
		try:
			url = "https://translate.googleapis.com/translate_a/single"
			params = {
				"client": "gtx",
				"sl": source_lang,
				"tl": target_lang,
				"dt": "t",
				"q": cleaned_text
			}
			full_url = f"{url}?{urllib.parse.urlencode(params)}"
			req = urllibRequest.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
			
			log.debug(f"Translating: {cleaned_text[:50]}... from {source_lang} to {target_lang} (attempt {attempt+1})")
			with urllibRequest.build_opener().open(req, timeout=15) as resp:
				data = json.loads(resp.read().decode('utf-8'))
				if isinstance(data, list) and data[0]:
					translated_parts = [part[0] for part in data[0] if part and part[0]]
					result = "".join(translated_parts)
					log.info(f"Translation successful: {result[:100]}...")
					return result
				else:
					log.warning("Unexpected response format")
					if attempt < retry:
						time.sleep(0.5)
						continue
					return text
					
		except urllib.error.HTTPError as e:
			log.error(f"HTTPError {e.code}: {e.reason}")
			if e.code == 400 and attempt < retry:
				# Try POST method for 400 errors
				log.info("Retrying with POST method")
				try:
					post_params = {
						"client": "gtx",
						"sl": source_lang,
						"tl": target_lang,
						"dt": "t",
					}
					post_data = urllib.parse.urlencode({"q": cleaned_text}).encode('utf-8')
					post_url = f"{url}?{urllib.parse.urlencode(post_params)}"
					post_req = urllibRequest.Request(post_url, data=post_data, headers={
						"User-Agent": "Mozilla/5.0",
						"Content-Type": "application/x-www-form-urlencoded"
					})
					with urllibRequest.build_opener().open(post_req, timeout=15) as resp:
						data = json.loads(resp.read().decode('utf-8'))
						if isinstance(data, list) and data[0]:
							translated_parts = [part[0] for part in data[0] if part and part[0]]
							result = "".join(translated_parts)
							log.info("POST translation successful")
							return result
				except Exception as post_err:
					log.error(f"POST fallback failed: {post_err}")
			time.sleep(0.5)
			
		except urllib.error.URLError as e:
			log.error(f"Network error: {e}")
			if attempt < retry:
				time.sleep(1)
				continue
			return text
		except Exception as e:
			log.error(f"Unexpected error: {e}")
			if attempt < retry:
				time.sleep(0.5)
				continue
			return text
	
	return text

def translate_text(text, target_lang, source_lang="auto", swap_lang="en", auto_swap=False):
	if not text or not text.strip():
		log.debug("translate_text: empty input")
		return ""

	actual_source = source_lang
	actual_target = target_lang

	if auto_swap and source_lang == "auto":
		detected = detect_language(text)
		log.info(f"Detected: {detected}, target: {target_lang}, swap: {swap_lang}")
		if detected == target_lang:
			actual_target = swap_lang
			log.info(f"Auto-swap triggered: new target = {swap_lang}")
		else:
			actual_source = detected
			log.info(f"Using detected source: {actual_source}")

	cache_key = f"{actual_source}|{actual_target}|{text}"
	if cache_key in _cache:
		log.debug("Using cached translation")
		_cache[cache_key] = (_cache[cache_key][0], _cache[cache_key][1] + 1)
		return _cache[cache_key][0]

	result = google_translate(text, actual_target, actual_source)
	
	if result and result != text:
		_cache[cache_key] = (result, 0)
		if len(_cache) > 1000:
			items = sorted(_cache.items(), key=lambda x: x[1][1], reverse=True)[:800]
			_cache.clear()
			_cache.update(dict(items))
		log.info(f"Translation cached for key: {cache_key[:50]}...")
	else:
		log.warning("Translation returned same as input or empty")
	
	return result if result else text

def get_effective_languages(text, target_lang, source_lang="auto", swap_lang="en", auto_swap=False):
	actual_source = source_lang
	actual_target = target_lang
	if auto_swap and source_lang == "auto":
		detected = detect_language(text)
		if detected == target_lang:
			actual_target = swap_lang
		else:
			actual_source = detected
	return actual_source, actual_target

def split_text_into_chunks(text, max_chars=MAX_CHARS):
	if len(text) <= max_chars:
		return [text]
	
	chunks = []
	lines = text.splitlines()
	current_chunk = ""
	
	for line in lines:
		if len(current_chunk) + len(line) + 1 <= max_chars:
			if current_chunk:
				current_chunk += "\n" + line
			else:
				current_chunk = line
		else:
			if current_chunk:
				chunks.append(current_chunk)
			if len(line) > max_chars:
				start = 0
				while start < len(line):
					end = start + max_chars
					chunks.append(line[start:end])
					start = end
				current_chunk = ""
			else:
				current_chunk = line
	
	if current_chunk:
		chunks.append(current_chunk)
	
	return chunks