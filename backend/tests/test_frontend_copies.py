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


def _csp(html: str) -> dict:
    match = re.search(r'http-equiv="Content-Security-Policy" content="([^"]*)"', html)
    assert match, "no Content-Security-Policy meta tag in index.html"
    directives = (d.split() for d in match.group(1).split(";") if d.strip())
    return {d[0]: d[1:] for d in directives}


def test_csp_allows_the_configured_api():
    # The page may only call the server config.js names, so the two must agree.
    html = (BASE_DIR / "docs" / "index.html").read_text(encoding="utf-8")
    config = (BASE_DIR / "docs" / "js" / "config.js").read_text(encoding="utf-8")
    url = re.search(r'^\s*API_BASE_URL:\s*"([^"]+)"', config, re.MULTILINE)
    assert url, "API_BASE_URL not found in config.js"
    assert _csp(html)["connect-src"] == [url.group(1)]


def test_page_has_nothing_the_csp_would_block():
    # script-src and style-src are 'self' only: no inline scripts, handlers or styles.
    html = (BASE_DIR / "docs" / "index.html").read_text(encoding="utf-8")
    policy = _csp(html)
    assert policy["script-src"] == ["'self'"] and policy["style-src"] == ["'self'"]
    assert re.search(r"<script(?![^>]*\bsrc=)", html) is None, "inline <script>"
    assert re.search(r"<style\b|\sstyle=|\son[a-z]+=", html) is None, "inline style or handler"
