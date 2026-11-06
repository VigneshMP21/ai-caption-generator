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
    'நன்றி': 'nandri',
    'நேற்று': 'nethu',
    'நேது': 'nethu',
    'இன்று': 'innaiku',
    'இன்றுக்கு': 'innaiku',
    'இன்னுக்கு': 'innaiku',
    'சுறுக்கமா': 'surukkama',
    'சுறுக்கமாக': 'surukkama',
    'சொன்னால்': 'sonna',
    'சொன்னா': 'sonna',
    'பழைய': 'pazhaya',
    'பல்ல': 'pala',
    'மேலும்': 'melum',
    'இரண்டும்': 'irandum',
    'சேர்ந்து': 'serndhu',
    'தொடர்ந்து': 'thodarnthu',
    'பாலோப்': 'follow',
    'பாலோப்புண்ணுங்க': 'followpannunga',
    'பண்ணுங்கள்': 'pannunga',
    'பண்ணுங்க': 'pannunga',
    'வேலை': 'velai',
    'செய்யலாம்': 'seyyalaam',
    'செயலாம்': 'seyyalaam',
    'பார்க்கலாம்': 'paarkkalaam',
    'பாக்கலாம்': 'paarkkalaam',
    'வித்தியாசம்': 'vithiyaasam',
    'வித்தியாசத்தை': 'vithiyaasathai',
    'உதவும்': 'udhavum',
    'சேமிக்கும்': 'semikkum',
    'சேமிக்க': 'semikka',
    'பகிரவும்': 'pagiravum',
    'பகிரலாம்': 'pagiralaam',
    'மற்றவருடன்': 'matravarudan',
    'மற்றவர்களுடன்': 'matravargaludan',
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

def is_pure_english_token(token: str) -> bool:
    """
    Checks if a token contains purely English/Latin characters, numbers, or symbols,
    with ZERO Tamil Unicode characters.
    """
    clean = re.sub(r'^[^\w]+|[^\w]+$', '', token)
    if not clean:
        return True
    if is_tamil_char(clean):
        return False
    return any(('a' <= c <= 'z' or 'A' <= c <= 'Z') for c in clean)

def offline_transliterate_word(word: str) -> str:
    """
    Transliterates a single Tamil word to phonetic Tanglish.
    Preserves English words, numbers, and punctuation 100% untouched.
    """
    if not word:
        return ""

    # Split leading/trailing punctuation cleanly
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

    # CRITICAL: If the word contains no Tamil characters (already English/Latin/numeric),
    # preserve it 100% exactly as-is. NEVER translate English to Tamil.
    if not is_tamil_char(core):
        return prefix + core + suffix

    # Check common dictionary first for natural colloquial spelling
    if core in COMMON_VOCAB:
        return prefix + COMMON_VOCAB[core] + suffix

    if not tamil:
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
        return word

def offline_transliterate_text(text: str) -> str:
    """
    Transliterates a sentence of Tamil to Tanglish safely,
    guaranteeing English words remain in English.
    """
    if not text:
        return ""
    words = text.split(" ")
    converted_words = [offline_transliterate_word(w) for w in words]
    return " ".join(converted_words)

def gemini_transliterate_words_batch(word_lists: List[List[str]]) -> Optional[List[Optional[List[str]]]]:
    """
    Word-aligned Gemini transliteration with Strict Language Preservation.

    Rules enforced:
    1. Tamil words -> Tanglish (phonetic Latin spelling)
    2. English words -> PRESERVED 100% in original English spelling (NEVER translated to Tamil)
    3. Technical terms, product names, programming languages -> PRESERVED in English
    """
    if not word_lists:
        return []

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    prompt = f"""You are an expert Tamil-to-Tanglish transliteration engine, NOT a translation engine.
Your task is to convert Tamil-language speech into natural Romanized Tanglish.

STRICT RULES:
1. Convert Tamil words into Tanglish (e.g. 'வணக்கம்' -> 'Vanakkam', 'நண்பர்களே' -> 'nanbargale').
2. PRESERVE English words in their original English spelling.
3. NEVER translate English words into Tamil meanings.
   - 'Happy' MUST remain 'Happy', NEVER translate to 'Sandhosam'.
   - 'Good morning' MUST remain 'Good morning', NEVER translate to 'Kaalai vanakkam'.
   - 'project' MUST remain 'project', NEVER translate to 'thittam'.
4. Preserve programming terminology, technical vocabulary, and product names:
   Python, GitHub, Git, API, application, software, project, create, develop, install, online, database, code.
5. Mixed Tamil-English sentences must preserve English words while transliterating Tamil words:
   'Naan happy ah irukken' -> 'Naan happy ah irukken'
6. Return a JSON object with a single key "segments": a list of word lists with EXACTLY the same number of words in the exact same order.

Input segments:
{json.dumps({"segments": word_lists}, ensure_ascii=False)}
"""

    candidate_models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash"]

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
                        time.sleep(1.0)
                        continue
                    break

            if response_text:
                break

        if response_text:
            parsed = json.loads(response_text)
            raw_segments = None
            if isinstance(parsed, dict) and "segments" in parsed:
                raw_segments = parsed["segments"]
            elif isinstance(parsed, list):
                raw_segments = parsed

            if raw_segments and len(raw_segments) == len(word_lists):
                aligned = []
                for in_words, out_words in zip(word_lists, raw_segments):
                    if not isinstance(out_words, list) or len(out_words) != len(in_words):
                        aligned.append(None)
                        continue

                    cleaned = []
                    for in_w, out_w in zip(in_words, out_words):
                        # SAFETY GUARD: If input word was already pure English, NEVER let LLM translate it!
                        if is_pure_english_token(in_w):
                            cleaned.append(in_w)
                        else:
                            cleaned.append(str(out_w).strip())

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
    Pair authoritative words with Whisper's acoustic timestamps.
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

    # N:M — interpolate across acoustic anchors
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
    Converts all segments to Tanglish with:
    1. Language Preservation: English words stay strictly in English
    2. Complete Speech Coverage: Processes every detected segment
    3. 1:1 acoustic timestamp matching for word highlight
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
                # Use offline transliterator with English token preservation
                tanglish_words = [offline_transliterate_word(w) for w in tamil_words]

            # Enforce English preservation safety check
            for idx, orig_w in enumerate(tamil_words):
                if is_pure_english_token(orig_w):
                    tanglish_words[idx] = orig_w

            tanglish_words = [w.replace("{", "(").replace("}", ")") for w in tanglish_words]

            seg["tanglish"] = " ".join(tanglish_words)

            timed = _build_timed_words(tanglish_words, seg.get("words", []))
            if timed:
                seg["tanglish_words"] = timed
            else:
                seg.pop("tanglish_words", None)

    return segments
