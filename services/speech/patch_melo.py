from pathlib import Path

g2p_path = Path("/opt/conda/lib/python3.11/site-packages/g2p_en/g2p.py")
g2p_source = g2p_path.read_text(encoding="utf-8")

old_import = "from nltk import pos_tag\n"
new_import = """from nltk import pos_tag as _nltk_pos_tag


def pos_tag(words):
    # MeloTTS only needs a POS tag to disambiguate a small homograph list.  Keep
    # the runtime offline when the optional NLTK tagger is not preinstalled.
    try:
        return _nltk_pos_tag(words)
    except LookupError:
        return [(word, "NN") for word in words]
"""
if old_import in g2p_source:
    g2p_source = g2p_source.replace(old_import, new_import, 1)

old_downloads = """try:
    nltk.data.find('taggers/averaged_perceptron_tagger.zip')
except LookupError:
    nltk.download('averaged_perceptron_tagger')
try:
    nltk.data.find('corpora/cmudict.zip')
except LookupError:
    nltk.download('cmudict')
"""
if old_downloads in g2p_source:
    g2p_source = g2p_source.replace(
        old_downloads,
        "# NLTK corpora are optional; the constructor below uses MeloTTS's bundled cache.\n",
        1,
    )

old_cmu = "        self.cmu = cmudict.dict()\n"
new_cmu = """        try:
            self.cmu = cmudict.dict()
        except LookupError:
            cache_path = os.path.join(
                "/opt/conda/lib/python3.11/site-packages/melo/text",
                "cmudict_cache.pickle",
            )
            if os.path.isfile(cache_path):
                with open(cache_path, "rb") as cache_file:
                    cached = pickle.load(cache_file)
                self.cmu = {
                    str(word).lower(): pronunciations for word, pronunciations in cached.items()
                }
            else:
                self.cmu = {}
"""
if old_cmu in g2p_source:
    g2p_source = g2p_source.replace(old_cmu, new_cmu, 1)
if "import pickle\n" not in g2p_source:
    g2p_source = g2p_source.replace("import nltk\n", "import nltk\nimport pickle\n", 1)
g2p_path.write_text(g2p_source, encoding="utf-8")


path = Path("/opt/conda/lib/python3.11/site-packages/melo/text/english.py")
source = path.read_text(encoding="utf-8")
old = "from .japanese import distribute_phone"
replacement = """def distribute_phone(n_phone, n_word):
    phones_per_word = [0] * n_word
    for _ in range(n_phone):
        minimum = min(phones_per_word)
        phones_per_word[phones_per_word.index(minimum)] += 1
    return phones_per_word
"""
if old not in source:
    raise RuntimeError("MeloTTS english.py no longer contains the expected Japanese import")
path.write_text(source.replace(old, replacement), encoding="utf-8")
