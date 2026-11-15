import os
from pathlib import Path


class LocalTranslator:
    def __init__(self, root: Path):
        from ctranslate2 import Translator
        from sentencepiece import SentencePieceProcessor

        self.source = SentencePieceProcessor(model_file=str(root / "source.spm"))
        self.target = SentencePieceProcessor(model_file=str(root / "target.spm"))
        self.engine = Translator(str(root), device="cpu", compute_type="int8",
                                 intra_threads=min(4, os.cpu_count() or 1))

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        tokens = [self.source.encode(text, out_type=str, add_eos=True) for text in texts]
        results = self.engine.translate_batch(tokens, beam_size=2, max_batch_size=512,
                                              batch_type="tokens", max_input_length=512,
                                              max_decoding_length=200)
        return [self.target.decode(result.hypotheses[0]).strip() for result in results]
