# gather sets from scryfall api and save as in a file to load as a dictionary of set_id to release_date
import os
import json
import requests
import tqdm

Scryfall_API_URL = "https://api.scryfall.com/sets"
FILE_NAME = "scryfall_sets.json"
ALL_SETS_DATA_FILE = "scryfall_sets_data.json"
FILTERED_SETS_FILE = "scryfall_filtered_sets.jsonl"
SET_NAMES_FILE = "mtg-sets-data.txt"
EXCLUDED_SET_TEXT = ["Tokens", "Art Series", "Minigames", "Art Cards", "Substitute Cards", "Front Cards"]

def fetch_and_save_sets():
    if not os.path.exists(ALL_SETS_DATA_FILE):
        print("Fetching sets from Scryfall API...")
        response = requests.get(Scryfall_API_URL)
        response.raise_for_status()
        sets_data = response.json()
        with open(ALL_SETS_DATA_FILE, 'w') as f:
            json.dump(sets_data, f)
        f.close()
    else:
        print(f"Loading sets data from {ALL_SETS_DATA_FILE}...")
        with open(ALL_SETS_DATA_FILE, 'r') as f:
            sets_data = json.load(f)
        f.close()
    if not os.path.exists(FILTERED_SETS_FILE):
        print("Filtering and saving sets...")
        with open(FILTERED_SETS_FILE, 'w') as f:
            for s in tqdm.tqdm(sets_data['data'], desc="Processing sets"):
                if not any(excluded in s['name'] for excluded in EXCLUDED_SET_TEXT):
                    f.write(json.dumps(s) + '\n')
        f.close()
    sets_dict = {}
    set_names = []
    with open(FILTERED_SETS_FILE, 'r') as f:
        for line in f:
            s = json.loads(line)
            sets_dict[s['id']] = s['released_at']
            set_names.append(f"{s['name']}|{s['code'].upper()}|")
    with open(FILE_NAME, 'w') as f:
        json.dump(sets_dict, f)
    f.close()
    with open(SET_NAMES_FILE, 'w', encoding='utf-8') as f:
        set_names.sort()
        for line in set_names:
            f.write(line + '\n')
    f.close()
    print(f"Saved {len(sets_dict)} sets to {FILE_NAME}")

if __name__ == "__main__":
    fetch_and_save_sets()