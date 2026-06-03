# MTG Card Scraper

A utility for gathering Magic: The Gathering card data from Scryfall to support the [XMage](https://github.com/magefree/mage) project.

## Overview

This tool fetches and parses card and set data from the Scryfall API, producing structured output files used to populate or update card information in XMage.


data print in the format:
<br>`{full_name}|{set_name}|{collector_number}|{rarity}|{main_face_cost}|{main_face_type}|{main_face_power}|{main_face_toughness}|{main_face_oracle}|{second_face_cost}|{second_face_type}|{second_face_power}|{second_face_toughness}|{second_face_oracle}|`
<br>example:<br>
> Ashling, Rekindled // Ashling, Rimebound|Lorwyn Eclipsed|124|R|{1}{R}|Legendary Creature — Elemental Sorcerer|1|3|Whenever this creature enters or transforms into Ashling, Rekindled, you may discard a card. If you do, draw a card.$At the beginning of your first main phase, you may pay {U}. If you do, transform Ashling.||Legendary Creature — Elemental Wizard|1|3|Whenever this creature transforms into Ashling, Rimebound and at the beginning of your first main phase, add two mana of any one color. Spend this mana only to cast spells with mana value 4 or greater.$At the beginning of your first main phase, you may pay {R}. If you do, transform Ashling.|


## Usage
1. Create a virtual environment: `python -m venv mtgenv`
2. Activate the virtual environment: `.\mtgenv\Scripts\Activate.ps1`
3. Install requirements `pip install requirements.txt`
2. Run the desired script (e.g., `python Scryfall_Parser.py`)
