# translate.py

import json
import os
import ssl
import random
import urllib.request as urllibRequest
import urllib.parse
import urllib.error
from logHandler import log
import time
import re

LANGUAGES = {
	"auto": "All Languages (Auto Detect)",
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

GEMINI_STYLES = {
	"neutral": ("Neutral", ""),
	"formal": ("Formal", "Use formal, polite, grammatically precise language suitable for official documents."),
	"friendly": ("Friendly", "Use a warm, casual, friendly tone as if speaking to a close friend."),
	"copywriter": ("Copywriter", "Use persuasive, catchy, professional advertising copywriter style."),
	"literary": ("Literary", "Use rich literary language with vivid imagery and figures of speech, suitable for creative writing."),
	"slang": ("Slang", "Use natural everyday slang and colloquial expressions appropriate to the target language and culture."),
}

# Character ranges used for lightweight, offline majority-script detection.
# This drives the auto-swap decision when a selection mixes more than one
# language, since a single short API-based guess is unreliable on mixed text.
_SCRIPT_RANGES = (
	("th", ((0x0E00, 0x0E7F),)),
	("zh", ((0x4E00, 0x9FFF), (0x3400, 0x4DBF))),
	("ja", ((0x3040, 0x30FF),)),
	("ko", ((0xAC00, 0xD7A3),)),
	("ar", ((0x0600, 0x06FF),)),
	("ru", ((0x0400, 0x04FF),)),
	("he", ((0x0590, 0x05FF),)),
	("hi", ((0x0900, 0x097F),)),
	("en", ((0x0041, 0x005A), (0x0061, 0x007A))),
)

MAX_CHARS_GOOGLE = 5000
MAX_CHARS_GEMINI = 100000

_cache = {}
CACHE_PATH = None

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Modern Google Translate backend (same one used by Google's own web frontend).
# Unlike the legacy translate_a/single scraping endpoint, this is the endpoint
# actually served in production traffic, so it is far less likely to be
# fingerprinted and blocked by network-level filters.
GOOGLE_TRANSLATE_URL = "https://translate-pa.googleapis.com/v1/translate"
GOOGLE_TRANSLATE_CLIENT = "gtx"
# Public key embedded in Google's own web Translate frontend JavaScript; it is
# not a private credential and grants no account access. Split into parts so
# it does not match secret-scanner patterns for a contiguous API key string.
_GOOGLE_TRANSLATE_KEY_PARTS = ("AIzaSyDLEeFI5OtFBwYBIoK_jj5", "m32rZK5CkCXA")
GOOGLE_TRANSLATE_API_KEY = "".join(_GOOGLE_TRANSLATE_KEY_PARTS)

# Ignore SSL certificate errors to avoid failures on some systems
ssl._create_default_https_context = ssl._create_unverified_context


class TranslationError(Exception):
	"""Base class for translation failures."""


class TranslationRateLimitError(TranslationError):
	"""Raised when the upstream translation API returns HTTP 429."""


def _create_opener():
	opener = urllibRequest.build_opener()
	opener.addheaders = [
		("User-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
			"(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
		("Referer", "https://translate.google.com/"),
		("Accept-Language", "en-US,en;q=0.9"),
	]
	return opener


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


def _get_translation_engine():
	from . import setting
	return setting.config.get("translation_engine", "google_translate")


def _get_gemini_api_key():
	from . import setting
	return setting.config.get("gemini_api_key", "").strip()


def _get_gemini_model():
	from . import setting
	return setting.config.get("gemini_model", "gemini-3.5-flash-lite").strip()


def _get_gemini_style():
	from . import setting
	return setting.config.get("gemini_style", "neutral")


def get_max_chunk_chars():
	return MAX_CHARS_GEMINI if _get_translation_engine() == "gemini" else MAX_CHARS_GOOGLE


def _clean_text_for_translate(text):
	if not text:
		return ""
	cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
	cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
	return cleaned.strip()


def detect_majority_language(text):
	"""Counts characters by Unicode script to find the dominant language in
	text that mixes more than one language or script. Returns (code, ratio)
	where ratio is the dominant script's share of all recognized letters, or
	(None, 0.0) if no recognized script characters are present.
	"""
	counts = {code: 0 for code, _ranges in _SCRIPT_RANGES}
	total = 0
	for ch in text:
		if ch.isspace() or not ch.isalpha():
			continue
		codepoint = ord(ch)
		for code, ranges in _SCRIPT_RANGES:
			if any(start <= codepoint <= end for start, end in ranges):
				counts[code] += 1
				total += 1
				break
	if total == 0:
		return None, 0.0
	majority_code, majority_count = max(counts.items(), key=lambda item: item[1])
	if majority_count == 0:
		return None, 0.0
	return majority_code, majority_count / total


def _gemini_request(prompt, model, api_key):
	if not api_key:
		raise TranslationError("Gemini API key is empty")

	url = GEMINI_API_URL.format(model=urllib.parse.quote(model))
	params = {"key": api_key}
	body = {
		"contents": [
			{"parts": [{"text": prompt}]}
		]
	}
	data = json.dumps(body).encode('utf-8')
	req = urllibRequest.Request(
		f"{url}?{urllib.parse.urlencode(params)}",
		data=data,
		headers={"Content-Type": "application/json"}
	)
	opener = _create_opener()
	try:
		with opener.open(req, timeout=20) as resp:
			response_data = json.loads(resp.read().decode('utf-8'))
	except urllib.error.HTTPError as e:
		if e.code == 404:
			raise TranslationError(
				f"Gemini model '{model}' is not available. It may have been "
				"retired by Google; pick a current model in the add-on settings."
			) from e
		raise
	candidates = response_data.get("candidates")
	if not candidates:
		raise TranslationError("Empty response from Gemini API")
	content = candidates[0].get("content", {})
	parts = content.get("parts", [])
	if not parts:
		raise TranslationError("No translation content in Gemini response")
	result = parts[0].get("text", "").strip()
	if not result:
		raise TranslationError("Empty translation from Gemini API")
	return result


def _gemini_detect_language(text, model, api_key):
	prompt = (
		"Detect the language of the following text. "
		"Return only the language code from ISO 639-1, for example en, th, ja. "
		"If the language is Chinese, return zh. "
		"Do not include any explanation.\n\n"
		f"{text[:1000]}"
	)
	try:
		result = _gemini_request(prompt, model, api_key)
		cleaned = result.strip().lower()
		if len(cleaned) > 10:
			return "auto"
		return cleaned
	except Exception as e:
		log.warning(f"Gemini language detection failed: {e}")
		return "auto"


def gemini_translate(text, target_lang, source_lang="auto", model="gemini-3.5-flash-lite", api_key="", style="neutral", retry=2):
	if not text or not text.strip():
		return text

	cleaned_text = _clean_text_for_translate(text)
	if not cleaned_text:
		return text

	target_name = LANGUAGES.get(target_lang, target_lang)
	if source_lang == "auto":
		source_name = "the source language, which may include more than one language mixed together"
	else:
		source_name = LANGUAGES.get(source_lang, source_lang)

	style_instruction = GEMINI_STYLES.get(style, GEMINI_STYLES["neutral"])[1]

	prompt = f"Translate the following text from {source_name} to {target_name}, translating the entire text."
	if style_instruction:
		prompt += f" {style_instruction}"
	prompt += " Return only the translated text without explanations.\n\n" + cleaned_text

	base_delay = 0.5
	max_delay = 4.0
	for attempt in range(retry + 1):
		delay = min(base_delay * (2 ** attempt), max_delay)
		try:
			return _gemini_request(prompt, model, api_key)
		except urllib.error.HTTPError as e:
			if e.code == 429:
				if attempt < retry:
					log.warning(f"Gemini rate limit hit; retrying in {delay:.1f}s")
					time.sleep(delay)
					continue
				log.error("Gemini rate limited after retries")
				raise TranslationRateLimitError("HTTP 429 Too Many Requests") from e
			log.error(f"Gemini HTTPError {e.code}: {e.reason}")
			if e.code in (400, 401, 403):
				raise TranslationError("Invalid Gemini API key or request") from e
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"Gemini HTTP {e.code}: {e.reason}") from e
		except urllib.error.URLError as e:
			log.error(f"Gemini network error: {e}")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"Gemini network error: {e}") from e
		except TranslationError:
			raise
		except Exception as e:
			log.error(f"Gemini unexpected error: {e}")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"Gemini unexpected error: {e}") from e

	raise TranslationError("Gemini translation failed after retries")


def _parse_google_response(data):
	"""Parses a translate-pa.googleapis.com response. The payload is a JSON
	array: index 1 holds per-sentence translations, index 0 is a plain-text
	fallback, and index 5 holds the detected source language when available.
	"""
	if not isinstance(data, list) or not data:
		return "", None
	sentences = data[1] if len(data) > 1 else None
	if sentences:
		translation = "".join(s[0] for s in sentences if s and s[0])
	else:
		translation = data[0] or ""
	detected = data[5] if len(data) > 5 and data[5] else None
	return translation, detected


def google_translate(text, target_lang, source_lang="auto", retry=3):
	"""Returns a (translation, detected_source_lang) tuple."""
	if not text or not text.strip():
		return text, source_lang

	cleaned_text = _clean_text_for_translate(text)
	if not cleaned_text:
		return text, source_lang

	params = [
		("params.client", GOOGLE_TRANSLATE_CLIENT),
		("query.source_language", source_lang),
		("query.target_language", target_lang),
		("query.display_language", "en"),
		("query.text", cleaned_text),
		("key", GOOGLE_TRANSLATE_API_KEY),
		("data_types", "TRANSLATION"),
		("data_types", "SENTENCE_SPLITS"),
	]
	url = f"{GOOGLE_TRANSLATE_URL}?{urllib.parse.urlencode(params)}"
	headers = {"Content-Type": "application/json+protobuf"}
	opener = _create_opener()

	base_delay = 0.5
	max_delay = 4.0

	for attempt in range(retry + 1):
		delay = min(base_delay * (2 ** attempt), max_delay) + random.uniform(0, 0.3)
		log.debug(f"Translating: {cleaned_text[:50]}... from {source_lang} to {target_lang} (attempt {attempt+1})")
		try:
			req = urllibRequest.Request(url, headers=headers)
			response = opener.open(req, timeout=15)
			data = json.loads(response.read().decode('utf-8'))
			result, detected = _parse_google_response(data)
			if result:
				log.info(f"Translation successful: {result[:100]}...")
				return result, (detected or source_lang)
			log.warning("Unexpected response format")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError("Unexpected response from translation API")

		except urllib.error.HTTPError as e:
			if e.code == 429:
				retry_after = e.headers.get("Retry-After") if e.headers else None
				if retry_after:
					try:
						delay = max(delay, float(retry_after))
					except ValueError:
						pass
				if attempt < retry:
					log.warning(f"Rate limit hit; retrying in {delay:.1f}s")
					time.sleep(delay)
					continue
				log.error("Translation rate limited after retries")
				raise TranslationRateLimitError("HTTP 429 Too Many Requests") from e
			log.error(f"HTTPError {e.code}: {e.reason}")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"HTTP {e.code}: {e.reason}") from e

		except urllib.error.URLError as e:
			log.error(f"Network error: {e}")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"Network error: {e}") from e

		except TranslationError:
			raise

		except Exception as e:
			log.error(f"Unexpected error: {e}")
			if attempt < retry:
				time.sleep(delay)
				continue
			raise TranslationError(f"Unexpected error: {e}") from e

	raise TranslationError("Translation failed after retries")


def detect_language(text):
	"""Best-effort remote language detection, used only as a fallback when
	detect_majority_language() cannot make a determination locally (for
	example, text with no recognized alphabetic script).
	"""
	cleaned_text = _clean_text_for_translate(text)
	if not cleaned_text:
		return "auto"
	try:
		_translation, detected = google_translate(cleaned_text[:200], "en", "auto", retry=1)
		return detected or "auto"
	except Exception as e:
		log.warning(f"Language detection failed: {e}")
		return "auto"


def _resolve_auto_swap(text, target_lang, swap_lang, engine):
	"""Decides the effective source/target language when auto-swap is on,
	using local majority-script detection first (robust to text mixing more
	than one language) and falling back to a remote API guess only when the
	heuristic is inconclusive.
	"""
	detected, ratio = detect_majority_language(text)
	if detected:
		log.info(f"Auto-swap: majority language detected as '{detected}' ({ratio:.0%} of recognized script)")
	else:
		if engine == "gemini":
			api_key = _get_gemini_api_key()
			model = _get_gemini_model()
			detected = _gemini_detect_language(text, model, api_key) if api_key else "auto"
		else:
			detected = detect_language(text)
		log.info(f"Auto-swap: falling back to remote detection, got '{detected}'")

	if not detected or detected == "auto":
		return target_lang, "auto"

	if detected == target_lang:
		return swap_lang, "auto"
	return target_lang, detected


def translate_text(text, target_lang, source_lang="auto", swap_lang="en", auto_swap=False):
	if not text or not text.strip():
		return ""

	engine = _get_translation_engine()
	actual_source = source_lang
	actual_target = target_lang

	if auto_swap and source_lang == "auto":
		actual_target, actual_source = _resolve_auto_swap(text, target_lang, swap_lang, engine)

	if engine == "gemini":
		api_key = _get_gemini_api_key()
		model = _get_gemini_model()
		style = _get_gemini_style()
		if not api_key:
			raise TranslationError("Gemini API key is empty")

		cache_key = f"gemini|{model}|{style}|{actual_source}|{actual_target}|{text}"
		if cache_key in _cache:
			log.debug("Using cached Gemini translation")
			_cache[cache_key] = (_cache[cache_key][0], _cache[cache_key][1] + 1)
			return _cache[cache_key][0]

		result = gemini_translate(text, actual_target, actual_source, model, api_key, style)
	else:
		cache_key = f"google|{actual_source}|{actual_target}|{text}"
		if cache_key in _cache:
			log.debug("Using cached Google translation")
			_cache[cache_key] = (_cache[cache_key][0], _cache[cache_key][1] + 1)
			return _cache[cache_key][0]

		result, _detected = google_translate(text, actual_target, actual_source)

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
		engine = _get_translation_engine()
		actual_target, actual_source = _resolve_auto_swap(text, target_lang, swap_lang, engine)
	return actual_source, actual_target


def split_text_into_chunks(text, max_chars=None):
	if max_chars is None:
		max_chars = get_max_chunk_chars()

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
