"""The frontend and the docs copy the help costs from backend/scoring.py.

They're shown on the buttons and in the rules, so a change to one copy must
be made to all of them.
"""

import re

from backend import scoring
from backend.config import BASE_DIR


def _js_array(source: str, name: str) -> tuple:
    match = re.search(rf"const {name} = \[([^\]]*)\];", source)
    assert match, f"{name} not found in ui.js"
    return tuple(int(n) for n in match.group(1).split(","))


def _spoken(costs: tuple) -> str:
    # (5, 10, 15) -> "5, 10 and 15"
    return ", ".join(map(str, costs[:-1])) + f" and {costs[-1]}"


def test_ui_costs_match_the_backend():
    source = (BASE_DIR / "docs" / "js" / "ui.js").read_text(encoding="utf-8")
    assert _js_array(source, "CLUE_COSTS") == scoring.CLUE_COSTS
    assert _js_array(source, "HINT_COSTS") == scoring.HINT_COSTS


def test_rules_text_quotes_the_backend_costs():
    for path in (BASE_DIR / "docs" / "index.html", BASE_DIR / "README.md"):
        text = path.read_text(encoding="utf-8")
        for costs in (scoring.CLUE_COSTS, scoring.HINT_COSTS):
            assert f"{_spoken(costs)} points" in text, (path.name, costs)
