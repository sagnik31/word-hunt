import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from backend.game import WordGameEngine

def test_manual():
    try:
        engine = WordGameEngine()
        res = engine.make_guess("dog")
        print(f"Guess: {res['guess']}")
        print(f"Rank: {res['rank']}")
        print(f"Similarity: {res['similarity']}")
        print(f"Hotness: {res['hotness']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_manual()
