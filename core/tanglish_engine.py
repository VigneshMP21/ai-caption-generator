import os
import re
import time
import json
import logging
from typing import List, Dict, Any, Optional

try:
    import tamil.utf8
except ImportError:
    tamil = None

logger = logging.getLogger(__name__)

# Common colloquial vocabulary and English loanwords in Tamil speech
COMMON_VOCAB = {
    'வணக்கம்': 'Vanakkam',
    'நண்பர்களே': 'nanbargale',
    'நண்பா': 'nanba',
    'எப்படி': 'eppadi',
    'இருக்கீங்க': 'irukkeenga',
    'இருக்கீங்களா': 'irukkeengkala',
    'இருக்கேன்': 'irukken',
    'நல்லா': 'nalla',
    'வீடியோ': 'video',
    'வீடியோவை': 'videovai',
    'வீடியோல': 'videola',
    'சூப்பர்': 'super',
    'சூப்பரா': 'super-aa',
    'சேனல்': 'channel',
    'சப்ஸ்கிரைப்': 'subscribe',
    'லைக்': 'like',
    'ஷேர்': 'share',
    'கமெண்ட்': 'comment',
    'இன்னைக்கு': 'innaiku',
    'நாளைக்கு': 'naalaiku',
    'பாருங்க': 'paarunga',
    'பார்க்க': 'paarka',
    'போறோம்': 'porom',
    'சொல்றேன்': 'solren',
    'தெரியுமா': 'theriyuma',
    'கண்டிப்பா': 'kandippa',
    'ரொம்ப': 'romba',
    'நன்றி': 'nandri'
}

BASE_CONSONANTS = {
    'க்': 'k', 'ங்': 'ng', 'ச்': 'ch', 'ஞ்': 'gn', 'ட்': 't', 'ண்': 'n',
    'த்': 'th', 'ந்': 'n', 'ப்': 'p', 'ம்': 'm', 'ய்': 'y', 'ர்': 'r',
    'ல்': 'l', 'வ்': 'v', 'ழ்': 'zh', 'ள்': 'l', 'ற்': 'r', 'ன்': 'n',
    'ஜ்': 'j', 'ஷ்': 'sh', 'ஸ்': 's', 'ஹ்': 'h', 'க்ஷ்': 'ksh',
    'க': 'k', 'ங': 'ng', 'ச': 's', 'ஞ': 'gn', 'ட': 't', 'ண': 'n',
    'த': 'th', 'ந': 'n', 'ப': 'p', 'ம': 'm', 'ய': 'y', 'ர': 'r',
    'ல': 'l', 'வ': 'v', 'ழ': 'zh', 'ள': 'l', 'ற': 'r', 'ன': 'n',
    'ஜ': 'j', 'ஷ': 'sh', 'ஸ': 's', 'ஹ': 'h', 'க்ஷ': 'ksh'
}

UYIR_MAP = {
    'அ': 'a', 'ஆ': 'aa', 'இ': 'i', 'ஈ': 'ee', 'உ': 'u', 'ஊ': 'oo',
    'எ': 'e', 'ஏ': 'ae', 'ஐ': 'ai', 'ஒ': 'o', 'ஓ': 'oa', 'ஔ': 'au'
}

PUNCT_CHARS = ".,!?:;\"'()[]{}-_/\\~`@#$%^&*+="

def is_tamil_char(char: str) -> bool:
    """Checks if a character belongs to the Tamil Unicode block (0x0B80 - 0x0BFF)."""
    return any(0x0B80 <= ord(c) <= 0x0BFF for c in char)

def offline_transliterate_word(word: str) -> str:
    """
    Transliterates a single Tamil word to phonetic Tanglish.
    Preserves punctuation, numbers, and English words safely.
    """
    if not word:
        return ""

    # Split leading/trailing punctuation cleanly without affecting Unicode combining marks
    prefix = ""
    suffix = ""
    w = word
    while w and w[0] in PUNCT_CHARS:
        prefix += w[0]
        w = w[1:]
    while w and w[-1] in PUNCT_CHARS:
        suffix = w[-1] + suffix
        w = w[:-1]
    core = w

    if not core:
        return word

    # Check common dictionary first for natural colloquial spelling
    if core in COMMON_VOCAB:
        return prefix + COMMON_VOCAB[core] + suffix

    if not tamil or not is_tamil_char(core):
        return word

    try:
        letters = tamil.utf8.get_letters(core)
        result = []
        for l in letters:
            if not is_tamil_char(l):
                result.append(l)
                continue

            try:
                p = tamil.utf8.splitMeiUyir(l)
                if isinstance(p, (tuple, list)) and len(p) == 2:
                    m, u = p
                    result.append(BASE_CONSONANTS.get(m, m) + UYIR_MAP.get(u, u))
                elif isinstance(p, str):
                    if p in UYIR_MAP:
                        result.append(UYIR_MAP[p])
                    elif p in BASE_CONSONANTS:
                        result.append(BASE_CONSONANTS[p])
                    else:
                        result.append(p)
                else:
                    result.append(l)
            except Exception:
                if l in UYIR_MAP:
                    result.append(UYIR_MAP[l])
                elif l in BASE_CONSONANTS:
                    result.append(BASE_CONSONANTS[l])
                else:
                    result.append(l)

        res_str = ''.join(result)

        # Conversational phonetic adjustments (intervocalic softening)
        res_str = re.sub(r'nanpar', 'nanbar', res_str)
        res_str = re.sub(r'eppati', 'eppadi', res_str)
        res_str = re.sub(r'aaka', 'aaga', res_str)
        res_str = re.sub(r'kalai', 'galai', res_str)
        res_str = re.sub(r'kalae', 'gale', res_str)
        res_str = re.sub(r'kaalam', 'kaalam', res_str)
        res_str = re.sub(r'choo', 'soo', res_str)

        return prefix + res_str + suffix

    except Exception:
        # Failsafe: return word as-is rather than crashing
        return word

def offline_transliterate_text(text: str) -> str:
    """
    Transliterates a sentence or phrase of Tamil to Tanglish safely.
    """
    if not text:
        return ""
    words = text.split(" ")
    converted_words = [offline_transliterate_word(w) for w in words]
    return " ".join(converted_words)

def gemini_transliterate_batch(texts: List[str]) -> List[str]:
    """
    Uses Gemini API to convert Tamil sentences into natural, colloquial Tanglish.
    Includes automatic retries for transient 503 spikes and seamless fallback to offline engine.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.info("No GEMINI_API_KEY found. Using high-speed offline transliterator.")
        return [offline_transliterate_text(t) for t in texts]

    prompt = f"""You are an expert Tamil-to-Tanglish subtitle transliterator.
Convert each of the following spoken Tamil subtitle segments into natural, modern, colloquial Tanglish (Tamil phonetically written in English Latin alphabet, exactly like how people text and read on social media, e.g., 'Vanakkam nanbargale', 'epdi irukkeenga', 'innaiku namma paaka porom').

STRICT RULES:
1. Do NOT translate into English meaning. For example, 'வணக்கம்' must become 'Vanakkam', NOT 'Hello'.
2. Keep existing English loanwords in English (e.g., 'video', 'AI', 'subscribe', 'channel').
3. You MUST return a JSON list of strings with EXACTLY {len(texts)} elements, matching the input order 1-to-1.
4. Capitalize appropriately for subtitles.

Input Tamil lines:
{json.dumps(texts, ensure_ascii=False)}
"""

    candidate_models = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]

    try:
        import google.genai as genai
        client = genai.Client()

        response_text = None
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=dict(response_mime_type="application/json")
                    )
                    if response and response.text:
                        response_text = response.text.strip()
                        break
                except Exception as me:
                    err_msg = str(me)
                    if "404" in err_msg or "not found" in err_msg.lower():
                        break
                    if "503" in err_msg and attempt == 0:
                        time.sleep(1.2)
                        continue
                    break

            if response_text:
                break

        if response_text:
            parsed = json.loads(response_text)
            if isinstance(parsed, list) and len(parsed) == len(texts):
                return [str(p).strip() for p in parsed]
            elif isinstance(parsed, dict) and "subtitles" in parsed and len(parsed["subtitles"]) == len(texts):
                return [str(p).strip() for p in parsed["subtitles"]]

    except Exception as e:
        logger.warning(f"Gemini API conversion encountered an issue ({e}). Using offline phonetic engine.")

    # Always fallback cleanly to offline engine
    return [offline_transliterate_text(t) for t in texts]

def gemini_transliterate_words_batch(word_lists: List[List[str]]) -> Optional[List[Optional[List[str]]]]:
    """
    Word-aligned Gemini transliteration.

    Returns one Tanglish word per input Tamil word (same order, same count) so
    every displayed word can carry its own Whisper acoustic timestamp.  This is
    what makes the highlight follow the actual voice instead of drifting.

    Returns None when the API is unavailable / failed.  Individual segments that
    violate the 1:1 word-count contract are returned as None so the caller can
    fall back to the offline per-word engine for just those segments.
    """
    if not word_lists:
        return []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = f"""You are an expert Tamil-to-Tanglish subtitle transliterator.
You receive a JSON object where each element of "segments" is a list of Tamil words.

For EACH segment, transliterate EVERY Tamil word individually into natural,
colloquial Tanglish (Tamil spoken words written phonetically in Latin letters,
e.g. 'வணக்கம்' -> 'Vanakkam', 'நண்பர்களே' -> 'nanbargale', 'இன்னைக்கு' -> 'innaiku').

STRICT RULES:
1. Do NOT translate meaning into English. 'வணக்கம்' -> 'Vanakkam', NOT 'Hello'.
2. Keep existing English loanwords in English (e.g. 'video', 'AI', 'subscribe', 'channel').
3. Each output inner list MUST contain EXACTLY the same number of words as the
   corresponding input inner list, in the same order. Never merge, split, add or
   drop words — this is critical for audio sync.
4. Keep any punctuation that is attached to a word.
5. Return ONLY a JSON array of arrays of strings.

Input:
{json.dumps({"segments": word_lists}, ensure_ascii=False)}
"""

    candidate_models = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"]

    try:
        import google.genai as genai
        client = genai.Client()

        response_text = None
        for model_name in candidate_models:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=dict(response_mime_type="application/json")
                    )
                    if response and response.text:
                        response_text = response.text.strip()
                        break
                except Exception as me:
                    err_msg = str(me)
                    if "404" in err_msg or "not found" in err_msg.lower():
                        break
                    if "503" in err_msg and attempt == 0:
                        time.sleep(1.2)
                        continue
                    break
            if response_text:
                break

        if response_text:
            parsed = json.loads(response_text)
            if isinstance(parsed, dict) and "segments" in parsed:
                parsed = parsed["segments"]
            if isinstance(parsed, list) and len(parsed) == len(word_lists):
                aligned: List[Any] = []
                for src_words, out_words in zip(word_lists, parsed):
                    if not isinstance(out_words, list) or len(out_words) != len(src_words):
                        aligned.append(None)
                        continue
                    cleaned = [str(w).strip() for w in out_words]
                    if any(not w for w in cleaned):
                        aligned.append(None)
                    else:
                        aligned.append(cleaned)
                return aligned
    except Exception as e:
        logger.warning(f"Gemini word-level conversion failed ({e}). Using offline phonetic engine.")

    return None


def _build_timed_words(
    words: List[str],
    whisper_words: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Pair an authoritative word list with Whisper's acoustic timestamps.

    When counts match we get exact 1:1 timings.  Otherwise the words are
    distributed across the acoustic anchor points so the displayed word list and
    the timed word list are always identical (the highlight can never point at a
    word that isn't shown).
    """
    if not words or not whisper_words:
        return []

    n_words = len(words)
    n_wsp = len(whisper_words)

    if n_words == n_wsp:
        result = []
        for i, (word, ww) in enumerate(zip(words, whisper_words)):
            start = ww["start"]
            end = ww["end"]
            if i < n_wsp - 1:
                next_start = whisper_words[i + 1]["start"]
                if next_start > end:
                    end = next_start
            result.append({"word": word, "start": round(start, 3), "end": round(end, 3)})
        return result

    # N:M — interpolate across acoustic anchors (start of each spoken word + end)
    anchors = [w["start"] for w in whisper_words] + [whisper_words[-1]["end"]]
    for k in range(1, len(anchors)):
        if anchors[k] < anchors[k - 1]:
            anchors[k] = anchors[k - 1]

    result = []
    for i, word in enumerate(words):
        pos = i * n_wsp / max(1, n_words - 1) if n_words > 1 else 0.0
        lo = int(pos)
        hi = min(lo + 1, n_wsp)
        frac = pos - lo
        start = anchors[lo] * (1.0 - frac) + anchors[hi] * frac

        if i < n_words - 1:
            next_pos = (i + 1) * n_wsp / max(1, n_words - 1)
            nlo = int(next_pos)
            nhi = min(nlo + 1, n_wsp)
            nfrac = next_pos - nlo
            end = anchors[nlo] * (1.0 - nfrac) + anchors[nhi] * nfrac
        else:
            end = anchors[-1]

        if end <= start:
            end = start + 0.05
        result.append({"word": word, "start": round(start, 3), "end": round(end, 3)})
    return result


def convert_segments_to_tanglish(segments: List[Dict[str, Any]], batch_size: int = 15) -> List[Dict[str, Any]]:
    """
    Converts all segments to Tanglish while guaranteeing that the exact words
    shown in the captions are the same words that carry Whisper's acoustic
    timestamps.

    This is the key to correct word-by-word highlighting: the previous version
    transliterated whole sentences (so Gemini could split/merge words) and then
    discarded the precise per-word timings whenever the word count differed,
    causing the highlight to lag/lead the voice.
    """
    if not segments:
        return []

    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        tamil_word_lists = [seg["text"].split() for seg in batch]

        aligned = gemini_transliterate_words_batch(tamil_word_lists)
        if aligned is None:
            aligned = [None] * len(batch)

        for seg, tamil_words, tanglish_words in zip(batch, tamil_word_lists, aligned):
            if tanglish_words is None:
                tanglish_words = [offline_transliterate_word(w) for w in tamil_words]

            # ASS override delimiters must not leak into caption text
            tanglish_words = [w.replace("{", "(").replace("}", ")") for w in tanglish_words]

            # The joined sentence is exactly the same words we time below,
            # so SRT/preview and the burned highlight always agree.
            seg["tanglish"] = " ".join(tanglish_words)

            timed = _build_timed_words(tanglish_words, seg.get("words", []))
            if timed:
                seg["tanglish_words"] = timed
            else:
                seg.pop("tanglish_words", None)

    return segments
