<div align="center">

<img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120" style="display: block; margin: 0 auto 20px; height: auto;">

# Absolute Translate

*"Elevate your perspective: Instant translation, zero friction, absolute clarity."*

**Author:** Chai Chaimee

**URL:** [https://github.com/chaichaimee/AbsoluteTranslate](https://github.com/chaichaimee/AbsoluteTranslate)

</div>

<hr>

## Introduction

**Absolute Translate** is a high‑performance NVDA add‑on that brings instant, friction‑free translation directly into your screen reader. Whether you need to translate selected text, the last spoken utterance, or quickly revisit a previous translation, this add‑on does it with a single, intuitive multi‑tap gesture — no need to switch applications or interrupt your workflow.

With support for two translation engines (Google Translate and Google Gemini), automatic language detection, intelligent clipboard management, and a powerful long‑document mode, Absolute Translate is the complete translation solution for NVDA users.

<br>

## Hotkey & Step‑by‑Step Operation

The entire functionality is controlled by a single hotkey: `Alt + Windows + T`. The action performed depends on the number of times you tap this key combination within a short interval (about 0.5 seconds). Follow these steps to get the most out of the add‑on:

1. **Single Tap:**
   * **If text is selected** on the screen (highlighted), the add‑on translates that selected text and speaks the result.
   * **If no text is selected**, the add‑on speaks the **most recent translation** from the current NVDA session. Tapping *again* without selection cycles backward through the translation history, allowing you to review older translations one by one.

   *Note:* The translation history is limited to 200 entries and is cleared each time NVDA restarts.

2. **Double Tap:** Translates the **last text spoken by NVDA**. This is perfect for capturing system messages, notifications, or dialog boxes that cannot be selected with the mouse or cursor.

3. **Triple Tap:** Opens the **Absolute Translate Settings** dialog directly, so you can adjust languages, engine preferences, or API keys without navigating through NVDA's menu tree.

This step‑by‑step logic is designed to be fast and context‑sensitive — you never have to remember multiple gestures.

<br>

## Essential Setup

Before you start translating, configure your preferred language pair and other options. You can access the settings via **Triple Tap** or through *NVDA Menu → Preferences → Settings → Absolute Translate*.

* **Source Language:** Choose from a wide list of languages, or select **"Auto"** (now a dedicated option) to let the add‑on detect the source language automatically.
* **Target Language:** Your desired output language.
* **Swap Language:** The fallback language used when **Auto Swap** is enabled. This allows the add‑on to intelligently flip translation direction based on detected text.
* **Auto Swap (recommended):** When checked, the add‑on will automatically swap source and target if the detected language matches the target. This is especially useful when working with mixed content.
* **Copy to Clipboard:** Saves the translation result to the clipboard automatically.
* **Append Translations:** When enabled, new translations are appended to the existing clipboard content instead of overwriting it.
* **Continuous Translation:** Enables handling of long texts through a dedicated dialog (segmented into manageable chunks).
* **Translation Engine:** Choose between **Google Translate** (free, no API key) and **Google AI Studio (Gemini)** (requires a free API key from [Google AI Studio](https://aistudio.google.com/apikey)).
* **Gemini Style:** When using Gemini, you can select a stylistic tone for the output:
  * **Neutral:** Balanced, standard translation.
  * **Formal:** Professional and polite, suitable for business or academic contexts.
  * **Friendly:** Warm and conversational, like a message to a friend.
  * **Copywriter:** Persuasive and punchy, ideal for marketing content.
  * **Literary:** Evocative and expressive, with a novel‑like quality.
  * **Slang:** Informal and idiomatic, using current everyday language.

<br>

## Advanced Features

### Dual Translation Engines

Absolute Translate now supports two backends: **Google Translate** (classic scraping endpoint) and the official **Gemini API**. You can switch between them in the settings at any time.

* **Google Translate:** Free, no API key required. Works well for everyday translations, but may occasionally be affected by network restrictions or rate limits.
* **Gemini:** Requires a free API key. Offers more reliable performance, better handling of long texts, and often superior quality. The add‑on uses Gemini's own language detection when source is set to "Auto".

If you experience issues with Google Translate, simply switch to Gemini without changing your workflow. The add‑on caches translations to reduce API usage and speed up repeated requests.

### High‑Volume Content Management

For texts longer than the threshold, the add‑on automatically triggers **Long Translation Mode** (or you can enable it manually via the Continuous setting). The threshold and chunk size depend on the selected engine:

* **With Google Translate:**
  * Long mode activates when the text exceeds **1,500 characters**.
  * The text is split into blocks of at most **5,000 characters** per translation request.
* **With Gemini:**
  * Long mode activates when the text exceeds **50,000 characters**.
  * The text is split into blocks of at most **100,000 characters** per request — far more generous, thanks to Gemini's higher capacity.

Once in Long Translation mode, the dialog offers:

* **Sequential Translation:** Use the **Continue** button (or Alt+C) to process the next block.
* **Intelligent Clipboard Integration:** If "Copy to Clipboard" is active, each block is saved. With **"Append"** enabled, blocks are joined together in the clipboard, letting you capture entire articles.
* **Dual‑View Swap (Alt+S):** Toggle between original and translated text within the dialog to cross‑reference context.

### Contextual Intelligence

* **Automatic Language Detection:** High‑accuracy detection using either Google or Gemini (when selected).
* **Smart Clipboard Persistence:** Build a translated document in the background while you read.
* **Optimized Audio Flow:** Manages NVDA's speech to prioritize translation output, ensuring you hear every word clearly.
* **Translation History:** Single‑tap without selection gives you instant access to the last translation, and repeated taps walk you backwards through the history.

> **Idea Highlight:** Efficiency is about more than speed; it is about total comprehension. Absolute Translate ensures that every piece of information on your screen is accessible, regardless of the language it was written in.

<br>

## Support Me

If this tool has streamlined your digital life, consider supporting its continued development with a small donation.

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/7sY3cwa4m3Ds5eZ6VK1VK00)

Your support means the world. Let's build something great together.

<br>

© 2026 Chai Chaimee NVDA Add‑on – Released under GNU GPL v2+