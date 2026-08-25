<p align="center">
  <img src="https://www.nvaccess.org/files/nvda/documentation/userGuide/images/nvda.ico" alt="NVDA Logo" width="120" />
</p>

<h1 align="center">Absolute Translate</h1>

<p align="center"><em>"Elevate your perspective: Instant translation, zero friction, absolute clarity."</em></p>

<p align="center"><b>author:</b> chai chaimee</p>
<p align="center"><b>url:</b> https://github.com/chaichaimee/AbsoluteTranslate</p>

---

## • Essential Setup

Before harnessing the power of **Absolute Translate**, it is vital to configure your linguistic environment. You can quickly access the settings by performing a **Triple Tap** on the hotkey `Alt + Windows + T` or navigate via NVDA Menu > Preferences > Settings > **Absolute Translate**.

* **Primary Language Pair:** Set the Source Language to "Auto" for effortless detection and choose your preferred Target Language.
* **The Swap System (Critical):** Define your secondary language here. When you need to translate back to the original source, the add‑on uses this to flip directions instantly.
* **Auto Swap:** We highly recommend **Checking** this option. It allows the engine to intelligently flip translation directions based on the detected text without manual intervention.
* **Response Handling:** Select "Copy to Clipboard" to save your results. If you enable **"Append"** mode, new translations will be added to the end of the existing clipboard content instead of overwriting it.
* **Continuous Mode:** Keep this **Checked** to handle long‑form content through our specialized interface (automatic segmentation into chunks of up to 5,000 characters).
* **Translation Engine:** Choose between **Google Translate** (free, no API key required) and **Google AI Studio (Gemini)**. If you experience issues with Google Translate (e.g. network blocks or rate limits), you can switch to Gemini for more stable and often higher‑quality translations. To use Gemini, you need a valid API key from [Google AI Studio](https://aistudio.google.com/apikey). Enter the key and select a model in the add‑on settings.

<br>

## • Description

Eliminate the friction of switching applications to understand the world. **Absolute Translate** is a high-performance bridge between you and global information. Integrated directly into your screen reader, it provides lightning-fast translations of on-screen text, keeping you focused and productive in any language.

<br>

## • How to Use (The Multi-Tap Logic)

The add‑on uses a sophisticated single-key control system via `Alt + Windows + T`. The behavior adapts to your needs based on the number of taps:

1. **Single Tap:** Translates the **Selected Text** (highlighted text) currently on your screen.
2. **Double Tap:** Translates the **Last Spoken Text** by NVDA. Ideal for system notifications, error messages, or transient dialogs that cannot be highlighted.
3. **Triple Tap:** Your ultimate shortcut to the **Settings Dialog**. Adjust your languages, engine preferences, or API keys instantly without digging through menus.

<br>

## • Advanced Features

### Dual Translation Engines

The add‑on now supports two translation backends: the classic **Google Translate** scraping endpoint and the official **Gemini API** from Google AI Studio. You can switch between them at any time in the settings.

* **Google Translate:** Free and does not require any API key. Works well for most everyday translations, but may occasionally be affected by network restrictions or rate limiting.
* **Gemini:** Requires a free API key from Google AI Studio. It offers more reliable performance, better handling of long texts, and often superior translation quality. The add‑on automatically uses Gemini’s language detection when the source is set to “Auto”.

If you encounter issues with Google Translate, simply switch to Gemini without changing your workflow. The add‑on will cache translations to reduce API usage and speed up repeated requests.

<br>

### High-Volume Content Management

For extensive documents or long articles, the add‑on triggers **Long Translation Mode** automatically whenever the text exceeds **2,000 characters** (or when you use the continuous mode):

* **Smart Block Segmentation:** To maintain peak translation quality, the text is divided into manageable blocks of up to **5,000 characters**.
* **Sequential Translation:** Use the **"Continue"** button (or Alt+C) to process and read the next block of text in the sequence.
* **Intelligent Clipboard Integration:** If "Copy to Clipboard" is active, each block is saved. With **"Append"** enabled, the second block is seamlessly joined to the first in your clipboard, allowing you to capture a whole article in one go.
* **Dual-View Swap (Alt+S):** Toggle between the "Original Source" and the "Translated Result" within the dialog to cross-reference context.

<br>

### Contextual Intelligence

* **Automatic Language Detection:** Let the add‑on identify the source language for you with high accuracy (supports both Google Translate and Gemini detection).
* **Smart Clipboard Persistence:** Build a translated document silently in the background while you read.
* **Optimized Audio Flow:** The add‑on manages NVDA's voice to prioritize translation results, ensuring you hear every word clearly.

> **Idea Highlight:** Efficiency is about more than speed; it is about total comprehension. Absolute Translate ensures that every piece of information on your screen is accessible, regardless of the language it was written in.

<br><br>

## Support Me

If this tool has streamlined your digital life, consider supporting its continued development with a small donation.

<br>

[![Support me](https://img.shields.io/badge/Donate-Support%20Me-blue?style=for-the-badge&logo=stripe)](https://buy.stripe.com/7sY3cwa4m3Ds5eZ6VK1VK00)

<br>

Your support means the world. Let's build something great together.

<br>

&copy; 2026 Chai Chaimee NVDA Add-on Released under GNU GPL v2+