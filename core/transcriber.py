import logging
from typing import List, Dict, Any
from faster_whisper import WhisperModel
import config

logger = logging.getLogger(__name__)

class AudioTranscriber:
    def __init__(self, model_size: str = config.WHISPER_MODEL_SIZE, device: str = config.WHISPER_DEVICE, compute_type: str = config.WHISPER_COMPUTE_TYPE):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            self._model = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Transcribes Tamil audio with exact millisecond timestamps and VAD filtering.
        """
        model = self._get_model()
        
        # Transcribe the entire video duration without aggressive VAD truncation
        # condition_on_previous_text=False prevents stopping early on repetitive phrases
        segments_generator, info = model.transcribe(
            audio_path,
            language="ta",
            task="transcribe",
            vad_filter=False,
            condition_on_previous_text=False,
            word_timestamps=True,
            beam_size=5,
            temperature=[0.0, 0.2, 0.4]
        )

        segments = []
        for seg in segments_generator:
            clean_text = seg.text.strip()
            if not clean_text:
                continue

            words_data = []
            if seg.words:
                for w in seg.words:
                    words_data.append({
                        "word": w.word.strip(),
                        "start": round(w.start, 3),
                        "end": round(w.end, 3),
                        "probability": round(w.probability, 3)
                    })

            segments.append({
                "id": seg.id,
                "start": round(seg.start, 3),
                "end": round(seg.end, 3),
                "text": clean_text,
                "words": words_data
            })

        return segments

