from importlib import import_module

from .symbols import *  # noqa: F403


_symbol_to_id = {symbol: index for index, symbol in enumerate(symbols)}  # noqa: F405


def cleaned_text_to_sequence(cleaned_text, tones, language, symbol_to_id=None):
    symbol_to_id_map = symbol_to_id if symbol_to_id else _symbol_to_id
    phones = [symbol_to_id_map[symbol] for symbol in cleaned_text]
    tone_start = language_tone_start_map[language]  # noqa: F405
    tones = [tone + tone_start for tone in tones]
    language_id = language_id_map[language]  # noqa: F405
    return phones, tones, [language_id for _ in phones]


def get_bert(norm_text, word2ph, language, device):
    modules = {
        "ZH": "chinese_bert",
        "EN": "english_bert",
        "JP": "japanese_bert",
        "ZH_MIX_EN": "chinese_mix",
        "FR": "french_bert",
        "SP": "spanish_bert",
        "ES": "spanish_bert",
        "KR": "korean",
    }
    module = import_module(f"{__package__}.{modules[language]}")
    return module.get_bert_feature(norm_text, word2ph, device)
