#!/usr/bin/env python3
"""
Comprehensive AGLC beverage list for Arrow Limousine
Includes all major brands and varieties with pricing hints and descriptions
"""

AGLC_BEVERAGES = {
    # BEER - Local & Popular
    "BEER": {
        "domestic": [
            {"name": "Budweiser", "variants": ["355ml", "473ml", "24-pack"], "desc": "American lager, classic and smooth"},
            {"name": "Bud Light", "variants": ["355ml", "473ml", "24-pack"], "desc": "Light American lager, low calories"},
            {"name": "Coors Light", "variants": ["355ml", "473ml", "24-pack"], "desc": "Crisp light lager, refreshing"},
            {"name": "Molson Canadian", "variants": ["355ml", "473ml", "24-pack"], "desc": "Canadian classic, balanced taste"},
            {"name": "Labatt Blue", "variants": ["355ml", "473ml", "24-pack"], "desc": "Canadian lager, premium quality"},
        ],
        "imported": [
            {"name": "Corona", "variants": ["355ml", "473ml", "24-pack"], "desc": "Mexican lager with lime appeal"},
            {"name": "Heineken", "variants": ["355ml", "473ml", "24-pack"], "desc": "Dutch pilsner, balanced hops"},
            {"name": "Guinness", "variants": ["355ml", "473ml", "24-pack"], "desc": "Irish stout, rich and creamy"},
            {"name": "Modelo", "variants": ["355ml", "473ml", "24-pack"], "desc": "Mexican pilsner, smooth"},
            {"name": "Stella Artois", "variants": ["355ml", "473ml", "24-pack"], "desc": "Belgian pilsner, premium"},
        ],
        "craft": [
            {"name": "Big Rock Brewery", "variants": ["355ml", "473ml", "6-pack", "24-pack"], "desc": "Alberta craft brewery"},
            {"name": "Tool Shed Brewing", "variants": ["355ml", "473ml", "6-pack", "24-pack"], "desc": "Calgary craft beers"},
            {"name": "Moose Jaw Brewing", "variants": ["355ml", "473ml", "6-pack", "24-pack"], "desc": "Saskatchewan craft brewery"},
        ]
    },
    
    # WINE
    "WINE": {
        "red": [
            {"name": "Robert Mondavi Cabernet Sauvignon", "variants": ["750ml", "1L", "1.75L"], "desc": "Bold Californian red, berry notes"},
            {"name": "Yellow Tail Cabernet", "variants": ["750ml", "1L", "1.75L"], "desc": "Australian red, fruit-forward"},
            {"name": "Barefoot Merlot", "variants": ["750ml", "1L", "1.75L"], "desc": "California merlot, smooth"},
            {"name": "Santa Margherita Barbera", "variants": ["750ml", "1L", "1.75L"], "desc": "Italian red, earthy"},
            {"name": "Woodbridge Cabernet", "variants": ["750ml", "1L", "1.75L"], "desc": "Budget-friendly red blend"},
        ],
        "white": [
            {"name": "Kendall Jackson Chardonnay", "variants": ["750ml", "1L", "1.75L"], "desc": "California white, buttery"},
            {"name": "Santa Margherita Pinot Grigio", "variants": ["750ml", "1L", "1.75L"], "desc": "Italian white, crisp"},
            {"name": "Barefoot Sauvignon Blanc", "variants": ["750ml", "1L", "1.75L"], "desc": "California white, herbal"},
            {"name": "Chablis", "variants": ["750ml", "1L", "1.75L"], "desc": "French Chardonnay, mineral"},
            {"name": "Fiddlehead Sauvignon Blanc", "variants": ["750ml", "1L", "1.75L"], "desc": "New Zealand white, tropical"},
        ],
        "sparkling": [
            {"name": "Moët & Chandon Champagne", "variants": ["750ml", "1.75L"], "desc": "French champagne, celebratory"},
            {"name": "Veuve Clicquot", "variants": ["750ml", "1.75L"], "desc": "Premium French champagne"},
            {"name": "Barefoot Bubbly", "variants": ["750ml", "1.75L"], "desc": "California sparkling, affordable"},
        ]
    },
    
    # SPIRITS - Vodka
    "VODKA": [
        {"name": "Absolut", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Swedish vodka, smooth"},
        {"name": "Smirnoff", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Russian vodka, versatile"},
        {"name": "Grey Goose", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Premium French vodka"},
        {"name": "Ketel One", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Dutch vodka, refined"},
        {"name": "Skyy", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "American vodka, clean"},
    ],
    
    # SPIRITS - Rum
    "RUM": [
        {"name": "Bacardi", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "White rum, light"},
        {"name": "Captain Morgan", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Spiced rum, sweet"},
        {"name": "Havana Club", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Cuban rum, tropical"},
        {"name": "Mount Gay", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Barbados rum, aged"},
        {"name": "Myers's", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Dark rum, full-bodied"},
    ],
    
    # SPIRITS - Whiskey
    "WHISKEY": [
        {"name": "Jack Daniel's", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Tennessee whiskey, classic"},
        {"name": "Jameson", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Irish whiskey, smooth"},
        {"name": "Crown Royal", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Canadian whisky, premium"},
        {"name": "Jim Beam", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Bourbon, affordable"},
        {"name": "Macallan", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Scotch whisky, single malt"},
    ],
    
    # SPIRITS - Gin
    "GIN": [
        {"name": "Tanqueray", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "British gin, juniper forward"},
        {"name": "Beefeater", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "London dry gin, classic"},
        {"name": "Gordons", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "British gin, traditional"},
        {"name": "Bombay Sapphire", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Premium gin, smooth"},
        {"name": "Hendrick's", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Botanical gin, cucumber"},
    ],
    
    # SPIRITS - Tequila
    "TEQUILA": [
        {"name": "José Cuervo", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Mexican tequila, mixable"},
        {"name": "Patrón", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Premium tequila, smooth"},
        {"name": "Don Julio", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Mexican tequila, crisp"},
        {"name": "Espolòn", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Agave-forward tequila"},
        {"name": "Sauza", "variants": ["50ml", "375ml", "750ml", "1L", "1.75L"], "desc": "Mexican tequila, spicy"},
    ],
    
    # COOLERS & SELTZERS
    "COOLERS": [
        {"name": "White Claw", "variants": ["12-pack", "19-pack"], "desc": "Hard seltzer, light"},
        {"name": "Smirnoff Ice", "variants": ["6-pack", "12-pack"], "desc": "Vodka cooler, fruity"},
        {"name": "Twisted Tea", "variants": ["6-pack", "12-pack"], "desc": "Malt drink with tea flavor"},
        {"name": "Mike's Hard Lemonade", "variants": ["6-pack", "12-pack"], "desc": "Malt cooler, sweet"},
        {"name": "Bud Light Seltzer", "variants": ["12-pack"], "desc": "Beer seltzer, crisp"},
    ],
    
    # NON-ALCOHOLIC
    "NON-ALCOHOLIC": [
        {"name": "Evian Water", "variants": ["Sparkling", "Still"], "desc": "Premium bottled water"},
        {"name": "Perrier Water", "variants": ["Sparkling", "Still"], "desc": "French sparkling water"},
        {"name": "Tropicana Juice", "variants": ["Orange", "Apple", "Cranberry"], "desc": "Fresh juice"},
        {"name": "Coca-Cola", "variants": ["Can", "Bottle"], "desc": "Soft drink, classic"},
        {"name": "Starbucks Coffee", "variants": ["Ready-to-drink"], "desc": "Premium bottled coffee"},
    ],
    
    # MISSING IN CURRENT INVENTORY - PRIORITY TO ADD
    "PRIORITY_ADDS": [
        {"category": "Wine", "name": "Apothic Red", "variants": ["750ml", "1L"], "desc": "Red blend, fruit-forward"},
        {"category": "Wine", "name": "Apothic Decadent", "variants": ["750ml", "1L"], "desc": "Premium red blend"},
        {"category": "Wine", "name": "Barefoot Cabernet", "variants": ["750ml", "1L"], "desc": "California red"},
        {"category": "Liqueurs", "name": "Jägermeister", "variants": ["50ml", "750ml"], "desc": "German herbal liqueur"},
        {"category": "Cognac", "name": "Hennessy", "variants": ["50ml", "750ml", "1.75L"], "desc": "Premium French brandy"},
    ]
}

print("AGLC Beverage Inventory Reference")
print("=" * 60)
print(f"\nTotal categories: {len(AGLC_BEVERAGES)}")
print("\nMajor categories:")
for cat in list(AGLC_BEVERAGES.keys())[:8]:
    if isinstance(AGLC_BEVERAGES[cat], list):
        count = len(AGLC_BEVERAGES[cat])
    else:
        count = sum(len(v) if isinstance(v, list) else 1 for v in AGLC_BEVERAGES[cat].values())
    print(f"  - {cat}: {count} brands")

print(f"\nPriority items to add: {len(AGLC_BEVERAGES['PRIORITY_ADDS'])}")
for item in AGLC_BEVERAGES['PRIORITY_ADDS']:
    print(f"  - {item['name']} ({item['category']})")
