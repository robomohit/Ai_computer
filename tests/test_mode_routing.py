"""Mode routing must never send an innocent chat question into desktop control
or a coding workflow. Regression for the bug where a substring verb match
("clean eating tips", "should I buy a Tesla") forced `computer` mode, and where
detect_task_mode's default fell through to `coding`."""
from app.providers import detect_task_mode


CHAT = [
    "give me 3 quick tips to focus better",
    "write a haiku about the sea",
    "should I buy a Tesla",
    "clean eating tips for beginners",
    "book recommendations for sci-fi",
    "how do I move on from a breakup",
    "tips on how to run faster",
    "what is the capital of Japan",
    "explain recursion",
    "summarize the theory of relativity",
    "give me advice on productivity",
]

CODING = [
    "write a python function to sort a list",
    "fix the bug in app.py",
    "create a react component for a navbar",
    "refactor this code",
    "debug my script",
    "set up a flask server with an api endpoint",
    "build me a todo app",
]

DESKTOP = [
    ("open notepad and write hello", "computer_isolated"),
    ("open calculator and compute 5 times 9", "computer_isolated"),
    ("open the start menu and click the settings button", "computer"),
]


def test_innocent_questions_route_to_chat():
    for g in CHAT:
        assert detect_task_mode(g) == "chat", f"{g!r} should be chat, got {detect_task_mode(g)!r}"


def test_genuine_coding_routes_to_coding():
    for g in CODING:
        assert detect_task_mode(g) == "coding", f"{g!r} should be coding, got {detect_task_mode(g)!r}"


def test_desktop_actions_route_to_computer():
    for g, expected in DESKTOP:
        assert detect_task_mode(g) == expected, f"{g!r} should be {expected!r}, got {detect_task_mode(g)!r}"


def test_explicit_mode_is_respected():
    assert detect_task_mode("anything at all", explicit_mode="chat") == "chat"
    assert detect_task_mode("anything at all", explicit_mode="coding") == "coding"
    assert detect_task_mode("anything at all", explicit_mode="computer") == "computer"
