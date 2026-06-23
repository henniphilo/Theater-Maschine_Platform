"""Teil-2 scene filter — corpus without Bärenklau."""

from __future__ import annotations

import re

from app.schemas.inszenierung import AnimalScene, SceneCorpus

_BAERENKLAU_RE = re.compile(r"bärenklau|baerenklau|bärenklauer|baerenklauer", re.IGNORECASE)


def is_baerenklau_scene(scene: AnimalScene) -> bool:
    return bool(_BAERENKLAU_RE.search(scene.animal))


def filter_teil2_scenes(corpus: SceneCorpus) -> list[AnimalScene]:
    return [scene for scene in corpus.scenes if not is_baerenklau_scene(scene)]


def teil2_corpus_view(corpus: SceneCorpus) -> SceneCorpus:
    """Return a shallow copy with only Teil-2 scenes."""
    filtered = filter_teil2_scenes(corpus)
    return corpus.model_copy(update={"scenes": filtered})
