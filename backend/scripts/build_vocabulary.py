import wordfreq
import spacy
import nltk
from nltk.corpus import wordnet
from better_profanity import profanity
from tqdm import tqdm

def generate_sorted_dictionary_nouns(target_count=20000):
    # --- 1. SETUP & DOWNLOADS ---
    print("Initializing resources...")
    
    # Download WordNet (Dictionary Database)
    try:
        nltk.data.find('corpora/wordnet.zip')
    except LookupError:
        print("Downloading WordNet data...")
        nltk.download('wordnet')

    # Load Spacy (Grammar Engine) - Disable parser/ner for speed
    # Ensure you ran: python -m spacy download en_core_web_sm
    nlp = spacy.load("en_core_web_sm", disable=['parser', 'ner'])
    
    # Load Profanity Filter
    profanity.load_censor_words()
    
    unique_lemmas = set()
    final_list = []
    
    # Iterate through English words, most popular first
    iterator = wordfreq.iter_wordlist('en', wordlist='best')
    
    print(f"Mining top {target_count} nouns from frequency database...")
    
    try:
        pbar = tqdm(total=target_count)
    except ImportError:
        pbar = None

    for word in iterator:
        # Stop once we have enough words
        if len(final_list) >= target_count:
            break

        # --- LAYER 1: FAST STRING FILTERS ---
        if len(word) < 4:
            continue       # Min length 4
        if '-' in word:
            continue         # No hyphens
        if not word.isalpha():
            continue  # No numbers/punctuation
        
        # --- LAYER 2: PROFANITY CHECK (Raw Word) ---
        if profanity.contains_profanity(word):
            continue

        # --- LAYER 3: GRAMMAR CHECK (Spacy) ---
        doc = nlp(word)
        token = doc[0]
        
        # Must be a Common Noun (excludes Verbs, Adjectives, Proper Nouns)
        if token.pos_ != 'NOUN':
            continue
        if token.pos_ == 'PROPN':
            continue
        
        lemma = token.lemma_.lower()
        
        # Double-check lemma length (e.g., 'eyes' -> 'eye' (3 chars) -> Skip)
        if len(lemma) < 4:
            continue
        
        # Double-check profanity on the root word
        if profanity.contains_profanity(lemma):
            continue

        # --- LAYER 4: DICTIONARY CHECK (WordNet) ---
        # Checks if the word exists in the standard English Dictionary as a Noun.
        # This removes "internet junk" (e.g., 'sdcc', 'ishaq')
        synsets = wordnet.synsets(lemma, pos=wordnet.NOUN)
        if not synsets:
            continue

        # --- ADD TO LIST ---
        if lemma not in unique_lemmas:
            unique_lemmas.add(lemma)
            final_list.append(lemma)
            if pbar:
                pbar.update(1)

    if pbar:
        pbar.close()
    
    # --- FINAL STEP: ALPHABETICAL SORT ---
    print("Sorting list alphabetically...")
    final_list.sort()
    
    return final_list

if __name__ == "__main__":
    # Generate
    num_words = 20000
    words = generate_sorted_dictionary_nouns(num_words)
    
    # Save
    filename = f"words_{num_words}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        for w in words:
            f.write(w + "\n")
            
    print(f"\nSuccess! Saved {len(words)} sorted words to {filename}")
    print(f"First 10: {words[:10]}")
    print(f"Last 10:  {words[-10:]}")