from backend.utils.word_forms import inflections, plural_forms, verb_forms


def test_plural_rules():
    assert "cats" in plural_forms("cat")
    assert "boxes" in plural_forms("box")
    assert "babies" in plural_forms("baby")
    assert "geese" in plural_forms("goose")
    assert "toies" not in plural_forms("toy")


def test_verb_rules():
    assert {"baked", "baking"} <= verb_forms("bake")
    assert {"hopped", "hopping"} <= verb_forms("hop")
    assert {"carried", "carrying"} <= verb_forms("carry")
    assert "seeing" in verb_forms("see")


def test_inflections_exclude_the_word_itself():
    assert "cat" not in inflections("cat")
