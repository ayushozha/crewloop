"""Seed bar inventory + generate one Gemini product photo per item.

Run after the SSH tunnel to projects-db is open:
    ssh -fN -L 5433:127.0.0.1:5433 ayush@72.62.82.57
    cd backend
    .venv/bin/python scripts/seed_inventory.py

- Idempotent: upserts by SKU, skips image generation when the JPEG
  already exists on disk.
- Images come from gemini-3.1-flash-image-preview (same model used for
  contractor portraits).
- Concurrency bounded to 6 parallel image requests.
"""
from __future__ import annotations

import asyncio
import base64
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Allow `python backend/scripts/seed_inventory.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app import db
from app.config import settings


IMAGES_DIR = Path(__file__).resolve().parents[1] / "app" / "static" / "inventory"
IMAGE_MODEL = "gemini-3.1-flash-image-preview"
IMAGE_CONCURRENCY = 6


@dataclass(frozen=True)
class Item:
    name: str
    category: str
    unit: str
    par_level: float       # quantity needed to fully stock for service
    on_hand_ratio: float   # fraction of par currently in stock (0.4 → low, 1.1 → over)
    reorder_ratio: float   # fraction of par that triggers reorder
    unit_cost: float
    supplier: str
    location: str
    description: str
    image_description: str
    qty_notes: str = ""    # short justification of the par level
    sku_prefix: str = ""   # auto-computed if blank

    @property
    def on_hand(self) -> float:
        return round(self.par_level * self.on_hand_ratio, 2)

    @property
    def reorder_point(self) -> float:
        return round(self.par_level * self.reorder_ratio, 2)

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")

    @property
    def sku(self) -> str:
        prefix = self.sku_prefix or CATEGORY_PREFIX.get(self.category, "BAR")
        # Stable 4-digit suffix from the slug.
        h = sum(ord(c) for c in self.slug) % 10000
        return f"{prefix}-{h:04d}"


CATEGORY_PREFIX = {
    "spirit": "SPR",
    "liqueur": "LIQ",
    "beer": "BR",
    "wine": "WN",
    "mixer": "MX",
    "garnish": "GR",
    "tool": "TL",
    "glassware": "GL",
    "consumable": "CN",
    "syrup": "SY",
}


# par_level reasoning: assumes a mid-size SF event bar serving roughly 80–150
# guests/night. Spirits well-bottles ≈ 4–6 per shift; backups for rail items.
# Beer in cases (24/case). Wine in bottles. Mixers in liters. Garnish in counts
# or pounds. Bar tools and glassware in pieces. Consumables in packs or sleeves.

ROSTER: list[Item] = [
    # ============================== SPIRITS — VODKA ==============================
    Item("Tito's Handmade Vodka", "spirit", "750ml bottle", par_level=8, on_hand_ratio=0.6, reorder_ratio=0.35, unit_cost=22.0,
         supplier="Southern Glazer's", location="Back bar · well",
         description="Workhorse well vodka. Used in the majority of cocktails.",
         image_description="a tall clear glass vodka bottle with a clean white label and minimal silver lettering, premium spirit",
         qty_notes="Well spirit, depletes fastest at ~1.5 bottles/shift."),
    Item("Grey Goose Vodka", "spirit", "750ml bottle", par_level=4, on_hand_ratio=0.75, reorder_ratio=0.4, unit_cost=38.0,
         supplier="Southern Glazer's", location="Back bar · top shelf",
         description="Premium call vodka, ordered for martinis.",
         image_description="a tall frosted clear vodka bottle with an elegant pale blue label, ultra-premium presentation"),
    Item("Ketel One Vodka", "spirit", "750ml bottle", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=30.0,
         supplier="Southern Glazer's", location="Back bar · top shelf",
         description="Dutch wheat vodka, popular for vodka sodas.",
         image_description="a clear glass vodka bottle with a navy and red label, narrow neck, premium spirit"),
    Item("Stolichnaya Vodka", "spirit", "1L bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=24.0,
         supplier="Breakthru Beverage", location="Back bar",
         description="Russian vodka used in seasonal cocktails.",
         image_description="a clear vodka bottle with a red and gold label, slightly taller liter bottle"),

    # ============================== SPIRITS — GIN ==============================
    Item("Tanqueray London Dry Gin", "spirit", "1L bottle", par_level=4, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=28.0,
         supplier="Southern Glazer's", location="Back bar · well",
         description="Classic juniper-forward gin for G&Ts and martinis.",
         image_description="a tall green glass gin bottle with a red wax seal at the neck and gold lettering"),
    Item("Bombay Sapphire Gin", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=30.0,
         supplier="Southern Glazer's", location="Back bar",
         description="Botanical gin, lighter style.",
         image_description="a clear sapphire blue glass gin bottle with a silver and white label"),
    Item("Hendrick's Gin", "spirit", "750ml bottle", par_level=3, on_hand_ratio=0.8, reorder_ratio=0.4, unit_cost=36.0,
         supplier="Republic National", location="Back bar · top shelf",
         description="Cucumber-forward gin for premium cocktails.",
         image_description="a black ceramic-looking gin bottle with old apothecary style label and embossed lettering"),

    # ============================== SPIRITS — RUM ==============================
    Item("Bacardi Superior White Rum", "spirit", "1L bottle", par_level=4, on_hand_ratio=0.55, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Republic National", location="Back bar · well",
         description="Workhorse light rum for daiquiris and mojitos.",
         image_description="a clear glass rum bottle with a familiar bat-style logo on the label, light spirit visible inside"),
    Item("Bacardi Gold Rum", "spirit", "1L bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=22.0,
         supplier="Republic National", location="Back bar",
         description="Amber rum for tropical drinks.",
         image_description="a clear glass rum bottle filled with golden amber liquid, glossy label"),
    Item("Captain Morgan Spiced Rum", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.65, reorder_ratio=0.4, unit_cost=24.0,
         supplier="Breakthru Beverage", location="Back bar",
         description="Spiced rum for rum & cokes.",
         image_description="a brown spiced rum bottle with a vintage label featuring a captain illustration"),
    Item("Mount Gay Eclipse Rum", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=26.0,
         supplier="Republic National", location="Back bar",
         description="Barbadian rum for sophisticated cocktails.",
         image_description="a slender amber rum bottle with a deep navy and copper label"),
    Item("Diplomático Reserva Rum", "spirit", "750ml bottle", par_level=2, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=42.0,
         supplier="Specialty Wine & Spirits", location="Back bar · top shelf",
         description="Premium aged rum for sipping and old fashioneds.",
         image_description="an elegant short aged rum bottle with rich amber liquid and a brown label"),

    # ============================== SPIRITS — TEQUILA / MEZCAL ==============================
    Item("Patrón Silver Tequila", "spirit", "750ml bottle", par_level=4, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=48.0,
         supplier="Southern Glazer's", location="Back bar · top shelf",
         description="Premium blanco tequila for margaritas and palomas.",
         image_description="a short squat clear tequila bottle with a thick cork stopper, white label with bee logo"),
    Item("Patrón Reposado Tequila", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=54.0,
         supplier="Southern Glazer's", location="Back bar · top shelf",
         description="Aged tequila for premium cocktails.",
         image_description="a squat clear tequila bottle with golden amber liquid and a thick cork stopper"),
    Item("Don Julio Blanco", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=52.0,
         supplier="Republic National", location="Back bar · top shelf",
         description="Premium tequila for top-shelf margaritas.",
         image_description="a tall elegant clear tequila bottle with a long neck, gold and black label"),
    Item("Casamigos Blanco", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=58.0,
         supplier="Breakthru Beverage", location="Back bar · top shelf",
         description="Premium tequila, popular call brand.",
         image_description="a tall clear glass tequila bottle with a black and silver minimal label"),
    Item("Espolòn Reposado", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=28.0,
         supplier="Southern Glazer's", location="Back bar",
         description="Mid-shelf reposado for everyday margaritas.",
         image_description="a tall clear tequila bottle with a bright graphic label featuring an Aztec design"),
    Item("Del Maguey Vida Mezcal", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=38.0,
         supplier="Specialty Wine & Spirits", location="Back bar",
         description="Smoky mezcal for craft cocktails.",
         image_description="a clear glass mezcal bottle with a traditional handwritten-style label and rustic feel"),

    # ============================== SPIRITS — WHISKEY / BOURBON / SCOTCH ==============================
    Item("Jameson Irish Whiskey", "spirit", "1L bottle", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=32.0,
         supplier="Republic National", location="Back bar",
         description="Popular Irish whiskey for shots and highballs.",
         image_description="a green-tinted glass whiskey bottle with a black label and gold lettering"),
    Item("Jack Daniel's Tennessee Whiskey", "spirit", "1L bottle", par_level=4, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=32.0,
         supplier="Southern Glazer's", location="Back bar",
         description="Workhorse whiskey for whiskey cokes.",
         image_description="a tall square-shouldered whiskey bottle with a black label and white serif lettering"),
    Item("Maker's Mark Bourbon", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=34.0,
         supplier="Southern Glazer's", location="Back bar",
         description="Wheated bourbon for old fashioneds.",
         image_description="a squat square bourbon bottle with red wax dripping down the neck and a cream label"),
    Item("Bulleit Bourbon", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=32.0,
         supplier="Breakthru Beverage", location="Back bar",
         description="High-rye bourbon for cocktails.",
         image_description="a vintage-style clear glass whiskey bottle with embossed lettering and an orange label"),
    Item("Buffalo Trace Bourbon", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=30.0,
         supplier="Specialty Wine & Spirits", location="Back bar · top shelf",
         description="Allocated bourbon, popular for whiskey flights.",
         image_description="a clear bourbon bottle with a green label featuring a buffalo illustration"),
    Item("Woodford Reserve Bourbon", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=42.0,
         supplier="Southern Glazer's", location="Back bar · top shelf",
         description="Premium bourbon for old fashioneds and manhattans.",
         image_description="a tall elegant bourbon bottle with a brown label and a wax seal"),
    Item("Glenlivet 12 Year Scotch", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=58.0,
         supplier="Specialty Wine & Spirits", location="Back bar · top shelf",
         description="Speyside single malt for scotch lovers.",
         image_description="a tall green scotch bottle with a gold and white label, premium presentation"),
    Item("Johnnie Walker Black Label", "spirit", "1L bottle", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=46.0,
         supplier="Republic National", location="Back bar",
         description="Blended scotch for whiskey sodas.",
         image_description="a tall square scotch bottle with a black label and a walking man illustration"),
    Item("Macallan 12 Year Scotch", "spirit", "750ml bottle", par_level=2, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=85.0,
         supplier="Specialty Wine & Spirits", location="Locked cabinet",
         description="Premium single malt, sold by the pour.",
         image_description="an elegant short scotch decanter with rich amber liquid and an embossed cream label"),
    Item("Hennessy VS Cognac", "spirit", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=48.0,
         supplier="Breakthru Beverage", location="Back bar · top shelf",
         description="French cognac for sidecars and digestifs.",
         image_description="a tall elegant cognac bottle with a black and gold label, rich amber liquid"),

    # ============================== LIQUEURS / CORDIALS ==============================
    Item("Cointreau", "liqueur", "750ml bottle", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=35.0,
         supplier="Southern Glazer's", location="Back bar · well",
         description="Orange liqueur for margaritas and cosmopolitans.",
         image_description="a square amber glass liqueur bottle with a clear orange label"),
    Item("Grand Marnier", "liqueur", "750ml bottle", par_level=2, on_hand_ratio=0.7, reorder_ratio=0.5, unit_cost=42.0,
         supplier="Republic National", location="Back bar",
         description="Premium orange liqueur for premium margaritas.",
         image_description="a round squat orange-tinted liqueur bottle with a red ribbon and red wax seal"),
    Item("Kahlúa Coffee Liqueur", "liqueur", "1L bottle", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Breakthru Beverage", location="Back bar",
         description="Coffee liqueur for white russians and espresso martinis.",
         image_description="a tall slim coffee liqueur bottle with a brown label and dark liquid"),
    Item("Baileys Irish Cream", "liqueur", "1L bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=24.0,
         supplier="Republic National", location="Walk-in cooler",
         description="Cream liqueur, kept cold.",
         image_description="a cream-colored opaque liqueur bottle with a brown and gold label"),
    Item("Campari", "liqueur", "1L bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=28.0,
         supplier="Specialty Wine & Spirits", location="Back bar",
         description="Bitter Italian aperitif for negronis.",
         image_description="a clear liqueur bottle filled with deep red liquid and a white retro label"),
    Item("Aperol", "liqueur", "1L bottle", par_level=3, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=26.0,
         supplier="Specialty Wine & Spirits", location="Back bar",
         description="Italian aperitif for spritzes.",
         image_description="a tall slim liqueur bottle with bright orange liquid and a clean white label"),
    Item("Sweet Vermouth (Dolin)", "liqueur", "750ml bottle", par_level=3, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="Italian vermouth for manhattans and negronis.",
         image_description="a tall green wine-style bottle with a red and gold label, deep red liquid"),
    Item("Dry Vermouth (Noilly Prat)", "liqueur", "750ml bottle", par_level=3, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="French dry vermouth for martinis.",
         image_description="a tall green wine-style bottle with a vintage French label, pale liquid"),
    Item("St-Germain Elderflower Liqueur", "liqueur", "750ml bottle", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=38.0,
         supplier="Republic National", location="Back bar",
         description="Floral liqueur for craft cocktails.",
         image_description="a tall elegant clear liqueur bottle with a pale floral label and a long neck"),
    Item("Triple Sec", "liqueur", "1L bottle", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=12.0,
         supplier="Breakthru Beverage", location="Back bar · well",
         description="Budget orange liqueur for high-volume margaritas.",
         image_description="a clear liqueur bottle with a simple orange and white label"),
    Item("Frangelico", "liqueur", "750ml bottle", par_level=2, on_hand_ratio=0.4, reorder_ratio=0.5, unit_cost=26.0,
         supplier="Republic National", location="Back bar",
         description="Hazelnut liqueur for nutty cocktails.",
         image_description="a brown glass bottle shaped like a monk with a rope tied around the neck"),
    Item("Amaretto Disaronno", "liqueur", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=28.0,
         supplier="Breakthru Beverage", location="Back bar",
         description="Almond liqueur for amaretto sours.",
         image_description="a square stout brown liqueur bottle with a square label and a cap"),
    Item("Chartreuse Green", "liqueur", "750ml bottle", par_level=1, on_hand_ratio=1.0, reorder_ratio=0.6, unit_cost=68.0,
         supplier="Specialty Wine & Spirits", location="Back bar · top shelf",
         description="Herbal French liqueur, expensive and allocated.",
         image_description="a tall slim liqueur bottle with a yellow-green hue and an old French label"),

    # ============================== BEER ==============================
    Item("Modelo Especial (case)", "beer", "case (24 cans)", par_level=4, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=32.0,
         supplier="Crown Imports", location="Walk-in cooler",
         description="High-volume Mexican lager.",
         image_description="a case of golden Mexican lager cans, neatly stacked with bright gold and white label design"),
    Item("Corona Extra (case)", "beer", "case (24 bottles)", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=34.0,
         supplier="Crown Imports", location="Walk-in cooler",
         description="Classic clear-bottle Mexican lager.",
         image_description="a case of clear glass beer bottles with the iconic blue and gold Mexican lager label"),
    Item("Heineken (case)", "beer", "case (24 bottles)", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=36.0,
         supplier="Heineken USA", location="Walk-in cooler",
         description="Dutch pilsner, premium import.",
         image_description="a case of dark green glass beer bottles with a red star label, stacked"),
    Item("Stella Artois (case)", "beer", "case (24 bottles)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=38.0,
         supplier="Anheuser-Busch", location="Walk-in cooler",
         description="Belgian pilsner for elevated events.",
         image_description="a case of clear glass beer bottles with a gold foil label, premium look"),
    Item("Guinness Draught (case)", "beer", "case (24 cans)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=42.0,
         supplier="Diageo", location="Walk-in cooler",
         description="Irish stout with a nitrogen widget.",
         image_description="a case of black aluminum beer cans with a golden harp design, premium Irish stout"),
    Item("Lagunitas IPA (case)", "beer", "case (24 cans)", par_level=3, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=38.0,
         supplier="Heineken USA", location="Walk-in cooler",
         description="California IPA, local favorite.",
         image_description="a case of bright colored beer cans with hand-drawn label art, California craft IPA"),
    Item("Anchor Steam Beer (case)", "beer", "case (24 bottles)", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=36.0,
         supplier="Anchor Brewing", location="Walk-in cooler",
         description="SF original steam beer.",
         image_description="a case of amber glass beer bottles with a vintage label and a steam train illustration"),
    Item("Pacifico Clara (case)", "beer", "case (24 bottles)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=32.0,
         supplier="Crown Imports", location="Walk-in cooler",
         description="Mexican pilsner, popular for beach-style events.",
         image_description="a case of clear glass beer bottles with a yellow and blue Pacific Ocean themed label"),
    Item("Sierra Nevada Pale Ale (case)", "beer", "case (24 bottles)", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=36.0,
         supplier="Sierra Nevada", location="Walk-in cooler",
         description="Classic American pale ale.",
         image_description="a case of brown glass beer bottles with green labels, craft pale ale design"),
    Item("Coors Light (case)", "beer", "case (24 cans)", par_level=2, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=26.0,
         supplier="Anheuser-Busch", location="Walk-in cooler",
         description="Light lager for budget service.",
         image_description="a case of silver and red beer cans, light lager design"),
    Item("Athletic Brewing NA (case)", "beer", "case (12 cans)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=24.0,
         supplier="Local distributor", location="Walk-in cooler",
         description="Non-alcoholic craft beer, increasingly requested.",
         image_description="a case of dark blue beer cans with bold athletic-themed design, non-alcoholic beer"),
    Item("White Claw Variety (case)", "beer", "case (24 cans)", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=36.0,
         supplier="Mark Anthony Brands", location="Walk-in cooler",
         description="Hard seltzer variety pack.",
         image_description="a case of slim cans in pastel colors, hard seltzer variety pack on a wooden bar surface"),

    # ============================== WINE ==============================
    Item("Bay Events House Red (Cabernet)", "wine", "750ml bottle", par_level=12, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=16.0,
         supplier="Vintage Wine Estates", location="Wine rack",
         description="House cabernet for events.",
         image_description="a tall dark green wine bottle with a clean minimal cream colored label, red wine inside"),
    Item("Pinot Noir (Oregon)", "wine", "750ml bottle", par_level=8, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Pacific Highway Wine", location="Wine rack",
         description="Mid-shelf pinot for upgraded pours.",
         image_description="a tall slender green wine bottle with an Oregon-themed label, deep ruby liquid"),
    Item("Bay Events House White (Chardonnay)", "wine", "750ml bottle", par_level=12, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=15.0,
         supplier="Vintage Wine Estates", location="Walk-in cooler",
         description="House chardonnay, served chilled.",
         image_description="a tall clear glass wine bottle with a minimal cream label, pale golden white wine"),
    Item("Sauvignon Blanc (NZ)", "wine", "750ml bottle", par_level=6, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Pacific Highway Wine", location="Walk-in cooler",
         description="Crisp Marlborough sauv blanc.",
         image_description="a clear glass wine bottle with a green and silver Kiwi-themed label, pale wine"),
    Item("Pinot Grigio (Veneto)", "wine", "750ml bottle", par_level=6, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=16.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="Italian pinot grigio for everyday glass pours.",
         image_description="a tall slender clear wine bottle with a classic Italian label, pale straw wine"),
    Item("Rosé (Provence)", "wine", "750ml bottle", par_level=6, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="Dry Provençal rosé.",
         image_description="a tall clear glass wine bottle with pale pink wine inside and an elegant Provence label"),
    Item("Prosecco DOC", "wine", "750ml bottle", par_level=8, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=14.0,
         supplier="Republic National", location="Walk-in cooler",
         description="Italian sparkling wine for toasts.",
         image_description="a tall green sparkling wine bottle with a foil-wrapped neck and a cream label"),
    Item("Champagne (Brut NV)", "wine", "750ml bottle", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=48.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="French champagne for premium events.",
         image_description="an elegant dark green champagne bottle with gold foil neck wrap and a black and gold label"),
    Item("Tempranillo (Rioja)", "wine", "750ml bottle", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Specialty Wine & Spirits", location="Wine rack",
         description="Spanish red for dinner service.",
         image_description="a tall dark green wine bottle with a traditional Spanish label and deep red wine"),
    Item("Malbec (Mendoza)", "wine", "750ml bottle", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Pacific Highway Wine", location="Wine rack",
         description="Argentinian malbec, popular red.",
         image_description="a tall dark green wine bottle with a bold modern label, deep inky red wine"),

    # ============================== MIXERS ==============================
    Item("Fever-Tree Tonic Water", "mixer", "200ml bottle (case of 24)", par_level=6, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=42.0,
         supplier="Fever-Tree USA", location="Walk-in cooler",
         description="Premium tonic for G&Ts.",
         image_description="a case of small clear glass tonic water bottles with a pale yellow label, premium mixer"),
    Item("Q Mixers Club Soda", "mixer", "200ml bottle (case of 24)", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=36.0,
         supplier="Q Mixers", location="Walk-in cooler",
         description="Premium club soda for highballs.",
         image_description="a case of small clear glass club soda bottles with a bright Q-themed label"),
    Item("Fever-Tree Ginger Beer", "mixer", "200ml bottle (case of 24)", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=42.0,
         supplier="Fever-Tree USA", location="Walk-in cooler",
         description="Spicy ginger beer for mules.",
         image_description="a case of small clear glass ginger beer bottles with an orange and gold label"),
    Item("Schweppes Ginger Ale", "mixer", "1L bottle", par_level=3, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=4.0,
         supplier="Coca-Cola Distributor", location="Walk-in cooler",
         description="Bulk ginger ale.",
         image_description="a tall plastic ginger ale bottle with a green and yellow label"),
    Item("Coca-Cola Bottles", "mixer", "case (24 bottles)", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Coca-Cola Distributor", location="Walk-in cooler",
         description="Glass-bottle Coca-Cola, served at events.",
         image_description="a case of small classic curved Coca-Cola style glass bottles with red labels"),
    Item("Diet Coke Cans", "mixer", "case (24 cans)", par_level=3, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Coca-Cola Distributor", location="Walk-in cooler",
         description="Diet cola in cans.",
         image_description="a case of silver and red diet cola aluminum cans, neatly arranged"),
    Item("Sprite Cans", "mixer", "case (24 cans)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Coca-Cola Distributor", location="Walk-in cooler",
         description="Lemon-lime soda.",
         image_description="a case of green and white lemon-lime soda aluminum cans"),
    Item("Cranberry Juice", "mixer", "1L bottle", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=6.0,
         supplier="Sysco", location="Walk-in cooler",
         description="100% cranberry for cosmos and vodka cranberry.",
         image_description="a tall plastic juice bottle filled with deep red cranberry juice"),
    Item("Orange Juice (fresh)", "mixer", "1 gallon", par_level=4, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Freshly squeezed OJ for mimosas and screwdrivers.",
         image_description="a clear gallon container of fresh orange juice with pulp visible, bright orange liquid"),
    Item("Pineapple Juice", "mixer", "46oz can", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=5.0,
         supplier="Sysco", location="Dry storage",
         description="For piña coladas and tropical drinks.",
         image_description="a tall metal can of pineapple juice with a yellow and green tropical label"),
    Item("Fresh Lime Juice", "mixer", "32oz bottle", par_level=6, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=8.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Fresh-squeezed for margaritas, depletes nightly.",
         image_description="a clear bottle of fresh lime juice with a pale green color, simple label"),
    Item("Fresh Lemon Juice", "mixer", "32oz bottle", par_level=4, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=8.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Fresh-squeezed for whiskey sours.",
         image_description="a clear bottle of fresh lemon juice with a pale yellow color, simple label"),
    Item("Simple Syrup", "mixer", "750ml bottle", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=4.0,
         supplier="House-made", location="Bar well",
         description="House 1:1 simple syrup, made daily.",
         image_description="a clear bottle of clear simple syrup with a minimal handwritten-style label"),

    # ============================== SYRUPS ==============================
    Item("Orgeat Syrup", "syrup", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=14.0,
         supplier="Specialty Wine & Spirits", location="Back bar",
         description="Almond syrup for mai tais.",
         image_description="a clear bottle of pale almond syrup with a cream label"),
    Item("Demerara Syrup", "syrup", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=10.0,
         supplier="House-made", location="Back bar",
         description="Rich brown sugar syrup for old fashioneds.",
         image_description="a clear bottle of golden brown syrup with a handwritten-style label"),
    Item("Grenadine", "syrup", "750ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=6.0,
         supplier="Sysco", location="Back bar",
         description="Pomegranate syrup for tequila sunrises.",
         image_description="a clear bottle of bright red grenadine syrup with a red and gold label"),
    Item("Honey Syrup", "syrup", "500ml bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=12.0,
         supplier="House-made", location="Back bar",
         description="Honey-water blend for bee's knees and gold rushes.",
         image_description="a clear bottle of golden honey syrup with a kraft paper label"),

    # ============================== BITTERS ==============================
    Item("Angostura Aromatic Bitters", "syrup", "4oz bottle", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=12.0,
         supplier="Angostura", location="Bar well",
         description="Workhorse bitters for old fashioneds and manhattans.",
         image_description="a small dark glass bitters bottle with an oversized yellow paper label"),
    Item("Peychaud's Bitters", "syrup", "5oz bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=14.0,
         supplier="Sazerac", location="Bar well",
         description="Anise-forward bitters for sazeracs.",
         image_description="a small clear glass bottle of red-tinted bitters with a vintage label"),
    Item("Orange Bitters", "syrup", "5oz bottle", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=12.0,
         supplier="Regan's", location="Bar well",
         description="Orange bitters for martinis and manhattans.",
         image_description="a small dark glass bottle of bitters with an orange-themed label"),

    # ============================== GARNISHES ==============================
    Item("Lemons (per case)", "garnish", "case (36 count)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=22.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Daily prep for twists and wedges.",
         image_description="a wooden crate filled with bright yellow fresh lemons, photographed from above"),
    Item("Limes (per case)", "garnish", "case (48 count)", par_level=3, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=24.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Daily prep, depletes fastest.",
         image_description="a wooden crate filled with bright green fresh limes, photographed from above"),
    Item("Oranges (per case)", "garnish", "case (40 count)", par_level=1, on_hand_ratio=0.7, reorder_ratio=0.5, unit_cost=26.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Wheels and peels for old fashioneds.",
         image_description="a wooden crate filled with fresh oranges, photographed from above"),
    Item("Maraschino Cherries (Luxardo)", "garnish", "400g jar", par_level=3, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=22.0,
         supplier="Specialty Wine & Spirits", location="Bar well",
         description="Premium Italian cherries for cocktails.",
         image_description="a glass jar of dark cherries in syrup with a cream Italian-style label"),
    Item("Green Olives (Castelvetrano)", "garnish", "1kg jar", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Specialty Wine & Spirits", location="Walk-in cooler",
         description="Premium olives for dirty martinis.",
         image_description="a tall glass jar of bright green olives in brine"),
    Item("Mint (bunch)", "garnish", "bunch", par_level=10, on_hand_ratio=0.4, reorder_ratio=0.4, unit_cost=2.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="Fresh mint for mojitos and juleps.",
         image_description="a bundle of fresh green mint leaves tied with twine"),
    Item("English Cucumber", "garnish", "each", par_level=6, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=3.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="For Hendrick's G&Ts and cucumber martinis.",
         image_description="a long fresh English cucumber on a wooden cutting board"),
    Item("Grapefruit (per case)", "garnish", "case (24 count)", par_level=1, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=22.0,
         supplier="Local Produce Co-op", location="Walk-in cooler",
         description="For palomas and grapefruit cocktails.",
         image_description="a crate of fresh ruby red grapefruits, photographed from above"),
    Item("Pickled Jalapeños", "garnish", "32oz jar", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=12.0,
         supplier="Sysco", location="Bar well",
         description="For spicy margaritas and bloody marys.",
         image_description="a glass jar of sliced pickled jalapeños in brine"),
    Item("Cocktail Salt (smoked)", "garnish", "500g container", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=8.0,
         supplier="Local Spice Co.", location="Bar well",
         description="For rimming margarita glasses.",
         image_description="a small ceramic container of flaky smoked salt with a wooden spoon"),
    Item("Cocktail Sugar (turbinado)", "garnish", "500g container", par_level=2, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=6.0,
         supplier="Local Spice Co.", location="Bar well",
         description="For rimming sweet cocktails.",
         image_description="a small ceramic container of golden coarse turbinado sugar"),

    # ============================== BAR TOOLS ==============================
    Item("Boston Cocktail Shaker", "tool", "each", par_level=4, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=28.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Two-piece weighted Boston shaker.",
         image_description="a polished stainless steel two-piece cocktail shaker on a wooden bar"),
    Item("Hawthorne Strainer", "tool", "each", par_level=4, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=12.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Standard cocktail strainer.",
         image_description="a stainless steel Hawthorne cocktail strainer with a coiled spring rim"),
    Item("Fine Mesh Strainer", "tool", "each", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=10.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Double-straining tool for pulp removal.",
         image_description="a small fine mesh stainless steel strainer with a wooden handle"),
    Item("Japanese Jigger (1oz/2oz)", "tool", "each", par_level=4, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=14.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Tall Japanese-style double jigger.",
         image_description="a tall stainless steel double-sided cocktail jigger on a marble counter"),
    Item("Mixing Glass (yarai)", "tool", "each", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=38.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Diamond-cut Japanese mixing glass for stirred drinks.",
         image_description="a thick crystal cocktail mixing glass with a diamond-cut pattern"),
    Item("Bar Spoon", "tool", "each", par_level=4, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=8.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="Twisted long-handled bar spoon.",
         image_description="a long twisted-handle stainless steel cocktail bar spoon"),
    Item("Muddler (wooden)", "tool", "each", par_level=2, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=10.0,
         supplier="Cocktail Kingdom", location="Bar well",
         description="For mojitos and old fashioneds.",
         image_description="a smooth wooden cocktail muddler with a tapered shape"),
    Item("Channel Knife / Citrus Peeler", "tool", "each", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=6.0,
         supplier="Mercer Culinary", location="Bar well",
         description="For citrus twists.",
         image_description="a stainless steel channel knife / citrus peeler with a black handle"),
    Item("Ice Scoop (stainless)", "tool", "each", par_level=2, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=12.0,
         supplier="Cambro", location="Ice well",
         description="Bar ice scoop.",
         image_description="a polished stainless steel ice scoop next to a mound of cubed ice"),
    Item("Wine Key (waiter's corkscrew)", "tool", "each", par_level=6, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=14.0,
         supplier="Pulltex", location="Bar well",
         description="Pocket wine key for table service.",
         image_description="a black handled waiter's corkscrew wine key on a white surface"),
    Item("Cutting Board (small)", "tool", "each", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Mercer Culinary", location="Bar prep",
         description="Bar prep board for garnishes.",
         image_description="a small wooden bar cutting board on a stainless prep table"),
    Item("Paring Knife", "tool", "each", par_level=3, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=16.0,
         supplier="Mercer Culinary", location="Bar prep",
         description="For citrus and garnish prep.",
         image_description="a small paring knife with a wooden handle on a clean cutting board"),

    # ============================== GLASSWARE ==============================
    Item("Old Fashioned Rocks Glass", "glassware", "each", par_level=48, on_hand_ratio=0.8, reorder_ratio=0.4, unit_cost=4.0,
         supplier="Libbey", location="Glassware rack",
         description="Double rocks glass for old fashioneds.",
         image_description="a thick-walled crystal old fashioned rocks glass with a heavy base"),
    Item("Highball Glass", "glassware", "each", par_level=48, on_hand_ratio=0.75, reorder_ratio=0.4, unit_cost=4.0,
         supplier="Libbey", location="Glassware rack",
         description="Tall highball for G&Ts and tall drinks.",
         image_description="a tall slender highball glass with a clean cylindrical shape"),
    Item("Collins Glass", "glassware", "each", par_level=36, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=4.5,
         supplier="Libbey", location="Glassware rack",
         description="Tall narrow glass for tom collins.",
         image_description="a tall narrow Collins-style glass on a marble counter"),
    Item("Coupe Glass", "glassware", "each", par_level=36, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=8.0,
         supplier="Schott Zwiesel", location="Glassware rack",
         description="Stemmed coupe for cocktails up.",
         image_description="an elegant stemmed coupe cocktail glass with a wide shallow bowl"),
    Item("Martini Glass", "glassware", "each", par_level=24, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=8.0,
         supplier="Schott Zwiesel", location="Glassware rack",
         description="Classic V-shaped martini.",
         image_description="a classic V-shaped martini glass with a long thin stem"),
    Item("Champagne Flute", "glassware", "each", par_level=48, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=6.0,
         supplier="Schott Zwiesel", location="Glassware rack",
         description="Tall flute for sparkling wine.",
         image_description="an elegant tall champagne flute with a slender bowl and long stem"),
    Item("Red Wine Glass", "glassware", "each", par_level=48, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=9.0,
         supplier="Schott Zwiesel", location="Glassware rack",
         description="Large-bowl glass for red wine.",
         image_description="a large-bowled red wine glass on a black background"),
    Item("White Wine Glass", "glassware", "each", par_level=48, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=8.0,
         supplier="Schott Zwiesel", location="Glassware rack",
         description="Smaller-bowl glass for white wine.",
         image_description="a slim white wine glass with a tulip-shaped bowl"),
    Item("Pint Glass (16oz)", "glassware", "each", par_level=36, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=3.5,
         supplier="Libbey", location="Glassware rack",
         description="Standard pint for draft beer.",
         image_description="a standard pint glass with a clean conical shape"),
    Item("Shot Glass (1.5oz)", "glassware", "each", par_level=48, on_hand_ratio=0.8, reorder_ratio=0.4, unit_cost=2.0,
         supplier="Libbey", location="Glassware rack",
         description="Heavy-bottom shot glass.",
         image_description="a thick heavy-bottom shot glass with a clean rim"),
    Item("Margarita Glass", "glassware", "each", par_level=24, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=7.0,
         supplier="Libbey", location="Glassware rack",
         description="Stemmed wide-rim glass for margaritas.",
         image_description="a stemmed margarita glass with a wide rounded rim and short stem"),
    Item("Mule Mug (copper)", "glassware", "each", par_level=24, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=14.0,
         supplier="Cocktail Kingdom", location="Glassware rack",
         description="Hammered copper mug for Moscow mules.",
         image_description="a hammered copper Moscow mule mug on a wooden bar surface"),

    # ============================== CONSUMABLES ==============================
    Item("Cocktail Napkins (250 pack)", "consumable", "pack of 250", par_level=8, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=6.0,
         supplier="WebstaurantStore", location="Dry storage",
         description="Branded napkins for table service.",
         image_description="a stack of folded cream cocktail napkins on a wooden bar"),
    Item("Paper Straws (500 pack)", "consumable", "pack of 500", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=18.0,
         supplier="Aardvark Straws", location="Dry storage",
         description="Compostable paper straws.",
         image_description="a tall jar of striped paper straws in various colors"),
    Item("Cocktail Picks (500 pack)", "consumable", "pack of 500", par_level=3, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=14.0,
         supplier="WebstaurantStore", location="Bar well",
         description="Bamboo picks for olives and cherries.",
         image_description="a small ceramic jar of bamboo cocktail picks"),
    Item("Coasters (200 pack)", "consumable", "pack of 200", par_level=4, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=22.0,
         supplier="WebstaurantStore", location="Dry storage",
         description="Branded paper pulp coasters.",
         image_description="a stack of round kraft paper coasters with embossed branding"),
    Item("Bar Towels", "consumable", "each", par_level=12, on_hand_ratio=0.7, reorder_ratio=0.4, unit_cost=6.0,
         supplier="WebstaurantStore", location="Bar well",
         description="Cotton bar towels, laundered nightly.",
         image_description="a neatly folded stack of cream cotton bar towels with red stripes"),
    Item("Ice (10lb bag)", "consumable", "10lb bag", par_level=12, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=3.0,
         supplier="Reddy Ice", location="Ice well",
         description="Crushed cocktail ice, replenished hourly.",
         image_description="a clear plastic bag of clear cocktail ice cubes"),
    Item("Sanitizer Wipes (canister)", "consumable", "canister (160 wipes)", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.5, unit_cost=8.0,
         supplier="Sysco", location="Under-counter",
         description="Food-grade sanitizer for prep surfaces.",
         image_description="a cylindrical canister of sanitizer wipes with a green and white label"),
    Item("Receipt Paper Rolls", "consumable", "case (50 rolls)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=28.0,
         supplier="Square", location="POS station",
         description="Thermal paper for POS receipts.",
         image_description="a stack of thermal receipt paper rolls on a black surface"),
    Item("Trash Bags (heavy duty)", "consumable", "case (100 bags)", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.4, unit_cost=24.0,
         supplier="Sysco", location="Dry storage",
         description="55-gallon trash bags.",
         image_description="a roll of black heavy-duty trash bags"),
    Item("Wine Stoppers", "consumable", "each", par_level=8, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=4.0,
         supplier="WebstaurantStore", location="Bar well",
         description="Reusable wine stoppers for open bottles.",
         image_description="a row of stainless steel and rubber wine bottle stoppers"),
    Item("Disposable Gloves (box of 100)", "consumable", "box (100 ct)", par_level=4, on_hand_ratio=0.6, reorder_ratio=0.4, unit_cost=14.0,
         supplier="Sysco", location="Bar prep",
         description="Nitrile gloves for garnish prep.",
         image_description="a blue box of disposable black nitrile gloves"),
    Item("Sharpies (12 pack)", "consumable", "pack of 12", par_level=2, on_hand_ratio=1.0, reorder_ratio=0.5, unit_cost=18.0,
         supplier="Staples", location="Office",
         description="For labeling cocktail batches and date marking.",
         image_description="a pack of black Sharpie markers on a clean white surface"),
    Item("Stir Sticks (1000 pack)", "consumable", "pack of 1000", par_level=2, on_hand_ratio=0.5, reorder_ratio=0.5, unit_cost=8.0,
         supplier="WebstaurantStore", location="Bar well",
         description="Plastic stir sticks for cocktails.",
         image_description="a jar of clear plastic cocktail stir sticks"),
]


PROMPT_TEMPLATE = (
    "Editorial product photograph of {description}. Centered composition, soft natural studio "
    "lighting, soft cream background, sharp focus, photorealistic, magazine quality. No text "
    "labels visible, no logos, no watermarks."
)


def build_prompt(item: Item) -> str:
    return PROMPT_TEMPLATE.format(description=item.image_description)


async def generate_image(client: httpx.AsyncClient, item: Item, sem: asyncio.Semaphore) -> Path | None:
    out_path = IMAGES_DIR / f"{item.slug}.jpg"
    if out_path.exists():
        return out_path
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}"
        f":generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": build_prompt(item)}]}],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    async with sem:
        for attempt in range(3):
            try:
                r = await client.post(url, json=payload, timeout=120)
                if r.status_code == 200:
                    data = r.json()
                    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    b64 = next((p["inlineData"]["data"] for p in parts if "inlineData" in p), None)
                    if b64:
                        out_path.write_bytes(base64.b64decode(b64))
                        return out_path
                    print(f"  no image in response for {item.name}: {str(data)[:200]}")
                else:
                    print(f"  HTTP {r.status_code} for {item.name}: {r.text[:200]}")
            except httpx.HTTPError as e:
                print(f"  attempt {attempt + 1} failed for {item.name}: {e}")
            await asyncio.sleep(2 + attempt * 3)
    return None


async def upsert_item(item: Item, image_path: str | None) -> None:
    sql = """
        INSERT INTO inventory_items
          (sku, name, category, unit, par_level, on_hand, reorder_point,
           unit_cost, supplier, location, description, image_path)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        ON CONFLICT (sku) DO UPDATE SET
          name = EXCLUDED.name,
          category = EXCLUDED.category,
          unit = EXCLUDED.unit,
          par_level = EXCLUDED.par_level,
          on_hand = EXCLUDED.on_hand,
          reorder_point = EXCLUDED.reorder_point,
          unit_cost = EXCLUDED.unit_cost,
          supplier = EXCLUDED.supplier,
          location = EXCLUDED.location,
          description = EXCLUDED.description,
          image_path = COALESCE(EXCLUDED.image_path, inventory_items.image_path)
    """
    async with db.pool().acquire() as conn:
        await conn.execute(
            sql,
            item.sku, item.name, item.category, item.unit, item.par_level,
            item.on_hand, item.reorder_point, item.unit_cost, item.supplier,
            item.location, item.description, image_path,
        )


async def main() -> None:
    print(f"Roster size: {len(ROSTER)} items")
    await db.connect()
    try:
        sem = asyncio.Semaphore(IMAGE_CONCURRENCY)
        async with httpx.AsyncClient() as http:
            async def process(i: int, item: Item) -> None:
                tag = f"[{i + 1:3d}/{len(ROSTER)}] {item.category:11s} {item.name}"
                print(tag)
                img = await generate_image(http, item, sem)
                avatar = f"/static/inventory/{img.name}" if img else None
                await upsert_item(item, avatar)
            await asyncio.gather(*[process(i, item) for i, item in enumerate(ROSTER)])
        async with db.pool().acquire() as conn:
            total = await conn.fetchval("SELECT count(*) FROM inventory_items")
            cats = await conn.fetch("SELECT category, count(*) FROM inventory_items GROUP BY category ORDER BY count(*) DESC")
        print(f"\nDone. {total} inventory items.")
        for row in cats:
            print(f"  {row['category']:11s} {row['count']}")
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
