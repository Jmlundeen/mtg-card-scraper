"""
Generate set files for MTG cards using local Scryfall bulk data.
Mimics functionality of mtg set parser but uses local data instead of API.
"""
import json
import os
import re
import unicodedata

# Configuration
SKIP_NAMES = {
    "Sticker sheet", "Discord, Lord of Disharmony", "Blacker Lotus", "Applejack",
    "Fluttershy", "Pinkie Pie", "Rainbow Dash", "Sleight of Mind", "Orcish Conscripts",
    "Orcish Farmer", "Sacred Boon", "Magical Hack", "Illusionary Mask", "Contract from Below",
    "Darkpact", "Demonic Attorney", "Bronze Tablet", "Rebirth", "Tempest Efreet", "Undergrowth",
    "Taste of Paradise", "Suffocation", "Scars of the Veteran", "Primitive Justice", "Shahrazad",
    "Jeweled Bird", 'Bloomvine Regent // Claim Territory // Bloomvine Regent',
    'Marang River Regent // Coil and Catch // Marang River Regent',
    'Scavenger Regent // Exude Toxin // Scavenger Regent', 'Who // What // When // Where // Why',
    'The Celestial Toymaker', 'The Fifteenth Doctor', 'Nathan Drake, Treasure Hunter', 'Mechtitan',
    'Jin Sakai, Ghost of Tsushima', 'Crystal Spray', 'Deadpool, Trading Card', 'Brisela, Voice of Nightmares'
}

CAMEL_CASE_OVERRIDES = {
    "K'rrik, Son of Yawgmoth": "KrrikSonOfYawgmoth",
    "Suq'Ata Lancer": "SuqAta Lancer",
    "Captain N'ghathrod" : "CaptainNghathrod"
}

SKIP_NUMBERS = {}

BASIC_TYPES = {
    "Swamp", "Plains", "Forest", "Mountain", "Island"
}

LAND_TYPES = {
    "Wastes",
    "Snow-Covered Plains", "Snow-Covered Swamp", "Snow-Covered Forest",
    "Snow-Covered Mountain", "Snow-Covered Island", "Snow-Covered Wastes"
}

# Set codes to process - modify this list as needed
SET_CODES = [
    "SLD"
]

BULK_DATA_FILE = "scryfall_default_cards_sorted.jsonl"

# Helper functions

def fix_collector_number(num):
    """Fix collector number by replacing special characters."""
    replacements = {'★': '*', 'Φ': 'Ph', '†': '+'}
    for old, new in replacements.items():
        num = num.replace(old, new)
    return f'"{num}"' if re.search(r'\D', num) else num


def remove_accents(text):
    """Remove accents from text."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')


def to_camel_case(name):
    """Convert name to CamelCase for class references."""
    if name in CAMEL_CASE_OVERRIDES:
        return CAMEL_CASE_OVERRIDES[name]
    name = remove_accents(name)
    name = re.sub(r"\b([A-Za-z])'(?=[A-Za-z])", r"\1 ", name)
    name = re.sub(r"[^\w\s'-]", '', name)
    words = re.split(r"[\s\-]+", name)

    def clean(word):
        word = word.replace("'", '')
        return word if word.isupper() else word.capitalize()

    return ''.join(clean(word) for word in words if word)


def get_various_text(card, use_various):
    """Generate the various text suffix based on card properties."""
    suffix = "_USE_VARIOUS" if use_various else ""

    if card.get('retro') and not card.get("layout") == "split":
        return f", RETRO_ART{suffix}"

    if card.get('full_art') and "poster" in card.get('promo_types', []):
        # Check if it's a basic land
        if any(t in BASIC_TYPES for t in card.get("subtypes", [])):
            return f", FULL_ART_BFZ{suffix.replace('_USE', '')}"
        else:
            return f", FULL_ART{suffix}"

    return f", NON_FULL_USE_VARIOUS" if use_various else ""


def parse_type_line(type_line):
    """Parse type line to extract types and subtypes."""
    types = []
    subtypes = []
    
    if not type_line:
        return types, subtypes
    
    # Handle double-faced cards - take first face only
    if ' // ' in type_line:
        type_line = type_line.split(' // ')[0]
    
    # Split on em-dash to separate types from subtypes
    if ' — ' in type_line:
        type_part, subtype_part = type_line.split(' — ', 1)
        types = type_part.split()
        subtypes = subtype_part.split()
    elif ' -- ' in type_line:
        type_part, subtype_part = type_line.split(' -- ', 1)
        types = type_part.split()
        subtypes = subtype_part.split()
    else:
        types = type_line.split()
    
    return types, subtypes


def determine_layout(card):
    """Determine the layout type from Scryfall card data."""
    layout = card.get('layout', 'normal')
    
    # Map Scryfall layouts to expected format
    layout_mapping = {
        'normal': 'normal',
        'split': 'split',
        'flip': 'flip',
        'transform': 'transform',
        'modal_dfc': 'modal_dfc',
        'meld': 'meld',
        'leveler': 'leveler',
        'saga': 'saga',
        'adventure': 'adventure',
        'planar': 'planar',
        'scheme': 'scheme',
        'vanguard': 'vanguard',
        'token': 'token',
        'double_faced_token': 'double_faced_token',
        'emblem': 'emblem',
        'augment': 'augment',
        'host': 'host',
        'art_series': 'art_series',
        'reversible_card': 'reversible_card',
        'case': 'case',
        'battle': 'battle',
        'prototype': 'prototype',
    }
    
    return layout_mapping.get(layout, layout)


def is_retro_frame(card):
    """Check if card has retro frame."""
    frame = card.get('frame', '')
    return frame in ['1993', '1997']


def load_bulk_data():
    """Load all cards from the bulk data file."""
    if not os.path.exists(BULK_DATA_FILE):
        print(f"Error: Bulk data file '{BULK_DATA_FILE}' not found.")
        print("Please run Scryfall_Parser.py first to generate the sorted bulk data.")
        return []
    
    cards = []
    print(f"Loading bulk data from {BULK_DATA_FILE}...")
    with open(BULK_DATA_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            cards.append(json.loads(line))
    print(f"Loaded {len(cards)} cards.")
    return cards


def filter_cards_by_set(cards, set_code):
    """Filter cards by set code."""
    set_cards = [card for card in cards if card.get('set', '').upper() == set_code.upper() and not card.get('layout', '') in ['token', 'double_faced_token', 'emblem', 'art_series']]
    set_cards.sort(key=lambda x: x.get('name', ''))
    return set_cards

def process_card_data(set_code, cards):
    """Process card data and return structured card info."""
    cards_info = []
    
    for card in cards:
        name = card.get('name', 'Unknown')
        type_line = card.get('type_line', '')
        types, subtypes = parse_type_line(type_line)
        
        cards_info.append({
            "name": name,
            "number": card.get('collector_number', 'Unknown'),
            "rarity": card.get('rarity', 'common').upper(),
            "layout": determine_layout(card),
            "retro": is_retro_frame(card),
            "fullart": card.get('full_art', False),
            "border_color": card.get('border_color', ''),
            "types": types,
            "subtypes": subtypes
        })
    
    cards_info.sort(key=lambda x: x['name'])
    return cards_info

def is_meld_result(card):
    """Check if card is a meld result."""
    for part in card.get('all_parts', []):
        if part.get('id', '') == card.get('id') and part.get('component') == 'meld_result':
            return True
    return False

def get_meld_number(card, cards_info):
    """Get meld card number if applicable."""
    for face in card.get('all_parts', []):
        if face.get('component') == 'meld_result':
            # Find the meld result card in cards_info
            for c in cards_info:
                if c['id'] == face.get('id'):
                    return c['collector_number']
    return 'Unknown'

CHUNK_SIZE = 1000  # Number of cards per addPart function


def write_output(set_code, cards_info):
    """Write the output file for the set, chunked into addPart functions."""
    os.makedirs("card_info", exist_ok=True)
    lines = []
    prev_name, prev_number = "", ""

    for idx, card in enumerate(cards_info):
        types, subtypes = parse_type_line(card.get('type_line', ''))
        card["types"] = types
        card["subtypes"] = subtypes
        card["retro"] = is_retro_frame(card)
        card['rarity'] = card.get('rarity', 'common').upper()
        name = remove_accents(card.get('name', 'Unknown')).replace('"', '\\"')
        if name in SKIP_NAMES or card["collector_number"] in SKIP_NUMBERS:
            continue
        if 'Basic' in types:
            card['rarity'] = 'LAND'
        number = fix_collector_number(card["collector_number"])
        if prev_number == number:
            continue

        layout = card["layout"]
        use_various = (
            (idx > 0 and cards_info[idx - 1]["name"] == name and cards_info[idx - 1]["collector_number"] != card["collector_number"]) or
            (idx + 1 < len(cards_info) and cards_info[idx + 1]["name"] == name and cards_info[idx + 1]["collector_number"] != card["collector_number"]) or
            layout == 'reversible_card'
        )
        various_text = get_various_text(card, use_various)
        
        if layout != 'split':
            camel_name = to_camel_case(name.split(" // ")[0])
        else:
            camel_name = ""
        if layout == 'meld':
            if is_meld_result(card):
                continue
            base = f'cards.add(new SetCardInfo("{name}", "{number}", "{get_meld_number(card, cards_info)}", Rarity.{card["rarity"]}, mage.cards.{name[0].lower()}.{camel_name}.class{various_text}));'
        else:
            base = f'cards.add(new SetCardInfo("{name.split(" // ")[0]}", {number}, Rarity.{card["rarity"]}, mage.cards.{name[0].lower()}.{camel_name}.class{various_text}));'
        
        if name in BASIC_TYPES:
            lines.append(f'cards.add(new SetCardInfo("{name}", {number}, Rarity.LAND, mage.cards.basiclands.{camel_name}.class{various_text}));')
        elif layout == 'reversible_card':
            # Handle reversible cards but don't create separate file
            name_2 = name.split(" // ")[1] if " // " in name else name
            camel_2 = to_camel_case(name_2)
            number_b = number.replace('"', '') + 'b'
            lines.append(base)
            lines.append(f'cards.add(new SetCardInfo("{name_2}", "{number_b}", Rarity.{card["rarity"]}, mage.cards.{name_2[0].lower()}.{camel_2}.class{various_text}));')
        elif layout == 'split':
            part1, part2 = name.split(" // ")
            combined_camel = to_camel_case(part1) + to_camel_case(part2)
            base = f'cards.add(new SetCardInfo("{name}", {number}, Rarity.{card["rarity"]}, mage.cards.{part1[0].lower()}.{combined_camel}.class{various_text}));'
            lines.append(base)
        else:
            lines.append(base)

        prev_name, prev_number = name, number

    # Sort all lines alphabetically by card name
    sorted_lines = sorted(lines, key=lambda x: re.search(r'"(.*?)"', x).group(1).lower())
    
    # Chunk into groups of CHUNK_SIZE
    chunks = [sorted_lines[i:i + CHUNK_SIZE] for i in range(0, len(sorted_lines), CHUNK_SIZE)]
    
    txt_path = f'card_info/{set_code}.txt'
    with open(txt_path, 'w', encoding='utf-8') as f:
        for part_num, chunk in enumerate(chunks, start=1):
            f.write(f'private void addPart{part_num}() {{\n')
            for line in chunk:
                f.write(f'    {line}\n')
            f.write('}\n\n')
    
    num_parts = len(chunks)
    print(f"Output written to {txt_path} ({len(lines)} cards in {num_parts} part(s))")


def main():
    """Main processing function."""
    # Load all bulk data once
    all_cards = load_bulk_data()
    if not all_cards:
        return
    
    for set_code in SET_CODES:
        print(f"\nProcessing set: {set_code}")
        
        # Filter cards for this set
        set_cards = filter_cards_by_set(all_cards, set_code)
        if not set_cards:
            print(f"No cards found for set code: {set_code}")
            continue
        
        print(f"Found {len(set_cards)} cards in set {set_code}")
        
        # Process and write output
        write_output(set_code, set_cards)
    
    print("\nProcessing complete.")


if __name__ == "__main__":
    main()
