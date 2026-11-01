import json
import time
from pathlib import Path

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "qwen3:4b-instruct-2507-q8_0"

INPUT_FILE = Path("data/similarity.txt")
OUTPUT_FILE = Path("data/big_hints.json")


def extract_words():
    words = []
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            # Split on tab → first column is target word
            word = line.split("\t", 1)[0].strip()
            words.append(word)
            if len(words) == 100:
                break
    return words


def generate_hints_for_word(word: str):
    """Generate EXACTLY 3 riddle-style hints, hardest → easiest"""

    prompt = f"""
You are creating high-quality riddles to help a player guess a target word.

Secret word: "{word}"

Create 3 hints that:
- Are short, clever riddles
- Do NOT mention the secret word or obvious synonyms
- First hint = most cryptic (hardest)
- Second = moderately difficult
- Third = the easiest while still indirect

📌 Output format: a valid **JSON array** of 3 strings ONLY.
Example:
["Hard riddle", "Medium riddle", "Easy riddle"]

Now generate the 3 hints:
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 1.0,
                "num_predict": 200,
            },
        },
        timeout=120,
    )

    raw = response.json()["response"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(f"⚠️ JSON decode failed for '{word}' → raw output:")
        print(raw)
        return []


def main():
    print("🔍 Extracting first 100 target words...")
    words = extract_words()
    print(f"📦 Loaded {len(words)} words")

    hints_dict = {}

    for i, word in enumerate(words, start=1):
        print(f"✍️ [{i}/100] Generating hints for: {word}")
        hints = generate_hints_for_word(word)

        if len(hints) != 3:
            print(f"❌ Skipping {word}, incorrect hint count: {hints}")
            continue

        hints_dict[word] = hints

        # Avoid stressing CPU / model — small cooldown
        time.sleep(0.3)

        # Save progress every 10 words
        if i % 10 == 0:
            OUTPUT_FILE.write_text(
                json.dumps(hints_dict, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print("💾 Progress saved")

    # Final save
    OUTPUT_FILE.write_text(
        json.dumps(hints_dict, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"🎉 Done! Hints saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
