"""
DEBUG SCRIPT - Test filtrování a mapování továren
==================================================
Bez komplikací - jen GPS filtrování + debug output
"""

import json
from pathlib import Path

# MSK REGION - SPRÁVNÉ MEZE
MSK_NORTH = 50.327
MSK_SOUTH = 49.39
MSK_EAST = 18.86
MSK_WEST = 17.146

def load_plants():
    """Načti továrny z JSON"""
    plants_file = Path('../plants.json')
    if not plants_file.exists():
        print(f"✗ Soubor {plants_file} neexistuje!")
        return []
    
    try:
        with open(plants_file, 'r', encoding='utf-8') as f:
            root = json.load(f)
        
        if isinstance(root, dict) and 'data' in root:
            data = root['data']
            if isinstance(data, dict) and 'Plants' in data:
                plants = data['Plants']
                print(f"✓ Načteno {len(plants)} továren z JSON\n")
                return plants
    except Exception as e:
        print(f"✗ Chyba: {e}")
    
    return []

def extract_emission(plant):
    """Extrahuj SOUČET všech emisí"""
    try:
        curr_year = plant.get('CurrentYear', {})
        if not isinstance(curr_year, dict):
            return 0.0
        
        emissions_list = curr_year.get('Emissions', [])
        if not isinstance(emissions_list, list):
            return 0.0
        
        total_emission = 0.0
        for emission_item in emissions_list:
            if isinstance(emission_item, dict):
                amount = emission_item.get('AmountRaw', 0)
                if isinstance(amount, (int, float)):
                    total_emission += float(amount)
        
        return total_emission
    except:
        return 0.0

def main():
    print("╔" + "="*68 + "╗")
    print("║" + "DEBUG: FILTROVÁNÍ A MAPOVÁNÍ TOVÁREN".center(68) + "║")
    print("╚" + "="*68 + "╝\n")
    
    plants = load_plants()
    if not plants:
        return
    
    print("="*70)
    print("FILTROVÁNÍ PODLE GPS ROZSAHU")
    print("="*70)
    
    print(f"\nRozsah MSK:")
    print(f"  Zeměpisná šířka: {MSK_SOUTH}° až {MSK_NORTH}°")
    print(f"  Zeměpisná délka: {MSK_WEST}° až {MSK_EAST}°\n")
    
    filtered = []
    total_count = 0
    out_of_bounds = 0
    
    for plant in plants:
        total_count += 1
        
        try:
            lat = float(plant.get('Lat', 0))
            lon = float(plant.get('Lon', 0))
            
            # FILTROVÁNÍ
            if MSK_SOUTH <= lat <= MSK_NORTH and MSK_WEST <= lon <= MSK_EAST:
                emission = extract_emission(plant)
                curr_year = plant.get('CurrentYear', {})
                name = curr_year.get('Name', 'Unknown') if isinstance(curr_year, dict) else 'Unknown'
                
                filtered.append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'emission': emission,
                })
            else:
                out_of_bounds += 1
        
        except Exception as e:
            print(f"✗ Chyba u továrny {total_count}: {e}")
    
    print(f"✓ Celkem továren: {total_count}")
    print(f"✓ V MSK rozsahu: {len(filtered)}")
    print(f"✓ Mimo rozsah: {out_of_bounds}\n")
    
    if filtered:
        # Sortuj podle emise (sestupně)
        filtered_sorted = sorted(filtered, key=lambda x: x['emission'], reverse=True)
        
        print("="*70)
        print("TOP 10 TOVÁREN PODLE EMISE")
        print("="*70 + "\n")
        
        for i, plant in enumerate(filtered_sorted[:10], 1):
            print(f"{i:2d}. {plant['name'][:50]}")
            print(f"    GPS: ({plant['lat']:.5f}, {plant['lon']:.5f})")
            print(f"    Emise: {plant['emission']:.3f} t/rok\n")
        
        # Statistika
        emissions = [p['emission'] for p in filtered]
        total_emission = sum(emissions)
        avg_emission = total_emission / len(emissions) if emissions else 0
        
        print("="*70)
        print("STATISTIKA EMISÍ")
        print("="*70 + "\n")
        
        print(f"Min emise:  {min(emissions):.3f} t/rok")
        print(f"Max emise:  {max(emissions):.3f} t/rok")
        print(f"Avg emise:  {avg_emission:.3f} t/rok")
        print(f"Celkem:     {total_emission:.1f} t/rok\n")
        
        # Geografické hranice filtrovaných
        lats = [p['lat'] for p in filtered]
        lons = [p['lon'] for p in filtered]
        
        print("="*70)
        print("GEOGRAFICKÉ HRANICE FILTROVANÝCH TOVÁREN")
        print("="*70 + "\n")
        
        print(f"Zeměpisná šířka: {min(lats):.5f}° až {max(lats):.5f}°")
        print(f"Zeměpisná délka: {min(lons):.5f}° až {max(lons):.5f}°\n")
        
        # Rozdělení do sektorů (4x4 mřížka)
        print("="*70)
        print("ROZDĚLENÍ DO 4×4 MŘÍŽKY (SEKTORY)")
        print("="*70 + "\n")
        
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        
        lat_step = lat_range / 4
        lon_step = lon_range / 4
        
        grid = [[0 for _ in range(4)] for _ in range(4)]
        
        for plant in filtered:
            lat_idx = min(3, int((plant['lat'] - min(lats)) / lat_step))
            lon_idx = min(3, int((plant['lon'] - min(lons)) / lon_step))
            grid[lat_idx][lon_idx] += 1
        
        print("Počet továren v každém sektoru:\n")
        print("      Západ              Východ")
        print("   ", end="")
        for j in range(4):
            print(f"  Sek{j+1}", end="")
        print()
        
        for i in range(4):
            print(f"S{i+1}: ", end="")
            for j in range(4):
                print(f"  {grid[i][j]:4d}", end="")
            print()
        
        print("\n")

if __name__ == '__main__':
    main()