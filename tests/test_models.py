from shortsfactory.models import Episode, suggest_title

def test_paragraphs_become_scenes():
    episode = Episode(title="test", script="Primera escena.\n\nSegunda escena.")
    assert episode.scene_list() == ["Primera escena.", "Segunda escena."]

def test_explicit_scenes_take_precedence():
    episode = Episode(title="test", script="Ignorado", scenes=["Una", "Dos"])
    assert episode.scene_list() == ["Una", "Dos"]

def test_suggest_title_uses_first_sentence_and_limits_words():
    assert suggest_title("La puerta se abrió. Nadie estaba allí.") == "La puerta se abrió"
    assert suggest_title("") == "Nuevo Short"
