# download scryfall default cards bulk data if out of date
import os
import requests
import json
from datetime import datetime, timedelta, timezone
from tqdm import tqdm
import unicodedata
import re

# when downloading data, file will be in format of 'default-cards-20251205100953.json'
# bulk data URL returns as follows:
# {
#   "object": "bulk_data",
#   "id": "27bf3214-1271-490b-bdfe-c0be6c23d02e",
#   "type": "oracle_cards",
#   "updated_at": "2025-12-05T10:03:17.356+00:00",
#   "uri": "https://api.scryfall.com/bulk-data/27bf3214-1271-490b-bdfe-c0be6c23d02e",
#   "name": "Oracle Cards",
#   "description": "A JSON file containing one Scryfall card object for each Oracle ID on Scryfall. The chosen sets for the cards are an attempt to return the most up-to-date recognizable version of the card.",
#   "size": 166369523,
#   "download_uri": "https://data.scryfall.io/oracle-cards/oracle-cards-20251205100317.json",
#   "content_type": "application/json",
#   "content_encoding": "gzip"
# }
# save response json and use updated_at to determine if we need to download new data
# if no response json or updated_at 12 hours old, download new data
# use download_uri to download the actual bulk data
#  save bulk data to 'scryfall_default_cards.json'
SPECIFIC_SET_CODE = None # update a specific set only, e.g. for spoiler time where bulk data is out of date
SET_URL = "https://api.scryfall.com/cards/search?include_extras=true&include_variations=true&order=set&q=e%3A=$set_code$=&unique=prints"
OUTPUT_FILE = "mtg-cards-data.txt"
BULK_DATA_URL = "https://api.scryfall.com/bulk-data/default-cards"
BULK_DATA_INFO_FILE = "scryfall_bulk_data_info.json"
BULK_DATA_FILE = "scryfall_default_cards.jsonl"
UPDATE_THRESHOLD_HOURS = 12
RARITY_MAP = {
    "common": 'C',
    "uncommon": 'U',
    "rare": 'R',
    "mythic": 'M'
}
SETS_FILE_NAME = "scryfall_sets.json"
FILTERED_SETS_FILE = "scryfall_filtered_sets.jsonl"
SPOILER_STALE_DATA = True
NEED_TO_SORT = True
BULK_CARDS_DATA = []


def is_data_out_of_date():
    if SPECIFIC_SET_CODE is not None:
        return True
    if not os.path.exists(BULK_DATA_INFO_FILE) or not os.path.exists(BULK_DATA_FILE):
        print("Bulk data info file or bulk data file not found. Need to download new data.")
        return True
    print("Bulk data info file found. Checking last updated time.")
    with open(BULK_DATA_INFO_FILE, 'r') as f:
        info = json.load(f)
    updated_at = datetime.fromisoformat(info['updated_at'].replace('Z', '+00:00'))
    need_update = SPOILER_STALE_DATA and (datetime.now(timezone.utc) - updated_at > timedelta(hours=UPDATE_THRESHOLD_HOURS))
    if need_update:
        print("Bulk data is out of date. Need to download new data.")
        return True
    else:
        print("Bulk data is up to date.")
        return False

def download_bulk_data():
    global NEED_TO_SORT
    if SPECIFIC_SET_CODE is not None:
        # Fetch cards for the specific set
        response = requests.get(SET_URL.replace("=$set_code$=", SPECIFIC_SET_CODE))
        response.raise_for_status()
        cards_data = response.json().get('data', [])
        missing_cards = []
        existing_ids = [card.get('id') for card in cards_data]
        # Load existing bulk data (it's expected to be a JSON array). If the file
        # doesn't exist or is malformed, start from an empty list and write a new file.
        print(f"Loading existing bulk data from {BULK_DATA_FILE}...")
        if os.path.exists(BULK_DATA_FILE):
            try:
                global BULK_CARDS_DATA
                BULK_CARDS_DATA = load_bulk_cards_from_file(BULK_DATA_FILE)
                for card_data in BULK_CARDS_DATA:
                    cid = card_data.get('id')
                    if cid in existing_ids:
                        existing_ids.remove(cid)
            except Exception as e:
                # Fall back to empty list if parsing fails
                print("Failed to parse existing bulk data. ")
                print(e)
                BULK_CARDS_DATA = []
        for card in cards_data:
            if len(existing_ids) == 0 or len(existing_ids) == len(missing_cards):
                break
            if card.get('id') in existing_ids:
                missing_cards.append(card)
        if not missing_cards:
            # Nothing to add
            print("No new cards to add.")
            return

        # Append missing cards and write the entire JSON array back to disk.
        NEED_TO_SORT = True
        print(f"Adding {len(missing_cards)} new cards from set {SPECIFIC_SET_CODE} to bulk data.")
        BULK_CARDS_DATA.extend(missing_cards)
        with open(BULK_DATA_FILE, 'w', encoding='utf-8') as f:
            for card in BULK_CARDS_DATA:
                f.write(json.dumps(card, ensure_ascii=False) + '\n')
        return

    response = requests.get(BULK_DATA_URL)
    response.raise_for_status()
    bulk_data_info = response.json()

    download_uri = bulk_data_info['download_uri']
    updated_at = bulk_data_info['updated_at']
    total_size = bulk_data_info.get('size', 0)

    # Stream the download with progress tracking
    bulk_data_response = requests.get(download_uri, stream=True)
    bulk_data_response.raise_for_status()

    # Use Content-Length header if available, otherwise use size from API
    total_size = int(bulk_data_response.headers.get('content-length', total_size))

    with open(BULK_DATA_FILE, 'wb') as f:
        with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc="Downloading") as pbar:
            for chunk in bulk_data_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    with open(BULK_DATA_INFO_FILE, 'w') as f:
        json.dump({'updated_at': updated_at}, f)
    NEED_TO_SORT = True
    print("Bulk data downloaded and saved.")

def normalize_collector_number(cn):
    """Replace special characters in collector number."""
    if not cn:
        return cn
    return cn.replace('★', '*').replace('Φ', 'Ph').replace('†', '+')

def normalize_name(name):
    """Normalize accented characters to ASCII equivalents."""
    if not name:
        return name
    # Decompose accented characters and remove combining marks
    normalized = unicodedata.normalize('NFKD', name)
    # Keep only ASCII characters (removes combining accents)
    return ''.join(c for c in normalized if not unicodedata.combining(c))

def parse_collector_number(cn):
    """Parse collector number, handling formats like '1', '1a', '★1', etc."""
    if not cn:
        return (float('inf'), '')
    cn = normalize_collector_number(cn)
    # Extract leading number if present
    match = re.match(r'^(\d+)(.*)', cn)
    if match:
        return (int(match.group(1)), match.group(2))
    # No leading number - sort alphabetically after numbered cards
    return (float('inf'), cn)


def load_bulk_cards_from_file(path):
    """Load bulk cards from a file that may be JSON Lines or a single JSON array/object.
    Returns a list of card dicts. Skips blank lines and logs parse warnings.
    """
    cards = []
    if not os.path.exists(path):
        return cards
    with open(path, 'r', encoding='utf-8') as f:
        # Peek first non-whitespace character to determine format
        pos = f.tell()
        first = f.read(1)
        while first and first.isspace():
            first = f.read(1)
        if not first:
            return cards
        # If it's a JSON array or object, load whole file
        if first in ('[', '{'):
            f.seek(pos)
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    # Some bulk responses may wrap the array in a dict under 'data'
                    return data.get('data', [])
                return []
            except json.JSONDecodeError as e:
                print(f"Failed to parse whole-file JSON from {path}: {e}")
                # Fall back to line-by-line parsing below
                f.seek(pos)

        # Treat as JSON Lines (one JSON object per line). Be tolerant of blank lines and trailing commas.
        f.seek(pos)
        for i, line in enumerate(f, start=1):
            s = line.strip()
            if not s:
                continue
            # Remove trailing commas (common if someone saved an array with commas)
            if s.endswith(','):
                s = s[:-1].rstrip()
            try:
                cards.append(json.loads(s))
            except json.JSONDecodeError as e:
                print(f"Warning: failed to parse JSON on line {i} of {path}: {e}. Skipping line.")
                continue
    return cards

def sort_cards_data():
    global BULK_CARDS_DATA
    if not os.path.exists(BULK_DATA_FILE):
        print("Bulk data file not found. Cannot sort cards.")
        exit(1)
    if not os.path.exists(SETS_FILE_NAME):
        print(f"Sets file {SETS_FILE_NAME} not found. run scryfall_sets.py to generate it first.")
        exit(1)
    if not os.path.exists(FILTERED_SETS_FILE):
        print(f"Filtered sets file {FILTERED_SETS_FILE} not found. run scryfall_sets.py to generate it first.")
        exit(1)

    print("Loading filtered sets data...")
    with open(FILTERED_SETS_FILE, 'r', encoding='utf-8') as f:
        filtered_sets = [json.loads(line)["name"] for line in f]

    print("Loading bulk data for sorting...")
    if not len(BULK_CARDS_DATA):
        BULK_CARDS_DATA = load_bulk_cards_from_file(BULK_DATA_FILE)

    # Sort cards by set release date then collector number as integer
    print("Sorting cards by set release date...")
    
    def sort_key(card):
        set_id = card.get('set_id', '')
        # Load set release dates from sets file
        with open(SETS_FILE_NAME, 'r') as f:
            sets_dict = json.load(f)
        released_at = sets_dict.get(set_id, '9999-12-31')
        collector_number = card.get('collector_number', '9999')
        set_name = card.get('set_name', '')
        num_part, suffix = parse_collector_number(collector_number)
        return (released_at, set_name, num_part, suffix)
    BULK_CARDS_DATA.sort(key=sort_key)

    # Save as JSON Lines format (one card per line)
    sorted_file = "scryfall_default_cards_sorted.jsonl"
    print("Saving sorted cards...")
    with open(sorted_file, 'w', encoding='utf-8') as f:
        for card in tqdm(BULK_CARDS_DATA, desc="Writing"):
            # Exclude cards from sets not in filtered sets
            if card.get('set_name', '') not in filtered_sets:
                continue
            # Normalize collector number in saved data
            if 'collector_number' in card:
                card['collector_number'] = normalize_collector_number(card['collector_number'])
            # Normalize accented names to ASCII
            if 'name' in card:
                card['name'] = normalize_name(card['name'])
            f.write(json.dumps(card, ensure_ascii=False) + '\n')

    print(f"Cards sorted by release date and saved to {sorted_file}.")

def gather_card_data():
    if is_data_out_of_date():
        download_bulk_data()
    if NEED_TO_SORT:
        sort_cards_data()

def parse_scryfall_data():
    sorted_file = "scryfall_default_cards_sorted.jsonl"
    if SPECIFIC_SET_CODE is not None:
        print(f"Specific set code {SPECIFIC_SET_CODE} provided. Gathering data for this set only.")
        gather_card_data()
    elif not os.path.exists(sorted_file):
        print("Sorted bulk data file not found. Gathering card data first.")
        gather_card_data()

    card_lines = []
    print("Parsing sorted card data...")
    with open(sorted_file, 'r', encoding='utf-8') as f:
        for line in tqdm(f, desc="Parsing"):
            card = json.loads(line)
            full_name = normalize_name(card.get('name', 'Unknown'))
            if ' // ' in full_name:
                main_face_card = card['card_faces'][0]
                second_face_card = card['card_faces'][1] if len(card['card_faces']) > 1 else {}
            else:
                main_face_card = card
                second_face_card = {}
            set_name = card.get('set_name', 'Unknown Set')
            num, suffix = parse_collector_number(card.get('collector_number', ''))
            collector_number = (num if suffix == '' 
                                else suffix if num == float('inf')
                                else f"{num}{suffix}")
            rarity = RARITY_MAP.get(card.get('rarity', 'common'), 'C')
            main_face_cost = main_face_card.get('mana_cost', '')
            main_face_type = main_face_card.get('type_line', '')
            main_face_oracle = (main_face_card.get('oracle_text', '')
                                .replace('\n', '$')
                                .replace('—', '--')
                                .replace('•', '*')
                                .strip())
            if "Planeswalker" in main_face_type:
                main_face_power = main_face_card.get('loyalty', '')
            else:
                main_face_power = main_face_card.get('power', '')
            main_face_toughness = main_face_card.get('toughness', '')
            second_face_cost = second_face_card.get('mana_cost', '')
            second_face_type = second_face_card.get('type_line', '')
            second_face_oracle = (second_face_card.get('oracle_text', '')
                                 .replace('\n', '$')
                                 .replace('—', '--')
                                 .replace('•', '*')
                                 .strip())
            if "Planeswalker" in second_face_type:
                second_face_power = second_face_card.get('loyalty', '')
            else:
                second_face_power = second_face_card.get('power', '')
            second_face_toughness = second_face_card.get('toughness', '')
            card_line = f"{full_name}|{set_name}|{collector_number}|{rarity}|{main_face_cost}|{main_face_type}|{main_face_power}|{main_face_toughness}|{main_face_oracle}|{second_face_cost}|{second_face_type}|{second_face_power}|{second_face_toughness}|{second_face_oracle}|"
            card_lines.append(card_line)
    print(f"Saving parsed card data to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.writelines('\n'.join(card_lines))
    print("Parsing complete.")

gather_card_data()
parse_scryfall_data()
    
