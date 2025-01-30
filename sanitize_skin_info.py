import json
import os

def sanitize_skin_data(input_file: str = 'skin_info.json', output_file: str = 'skin_info_sanitized.json'):
    """
    Read the skin info JSON file, remove specified fields, and add wear/rarity integers.
    
    Fields to remove:
    - description
    - category
    - team
    - legacy_model
    
    Fields to add:
    - wears: Add integer to each wear dictionary based on its position (0-4)
    - rarity: Add integer based on rarity.name mapping
    
    Args:
        input_file: Path to the input JSON file
        output_file: Path where the sanitized JSON will be saved
    """
    # Rarity mapping based on rarity ID
    rarity_mapping = {
        'rarity_ancient_weapon': 0,     # covert
        'rarity_legendary_weapon': 1,   # classified
        'rarity_mythical_weapon': 2,    # restricted
        'rarity_rare_weapon': 3,        # mil-spec
        'rarity_uncommon_weapon': 4,    # industrial grade
        'rarity_common_weapon': 5       # consumer grade
    }
    
    try:
        # Read the input JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Fields to remove
        fields_to_remove = ['description', 'category', 'team', 'legacy_model']
        
        # Process each item
        for item in data:
            # Remove specified fields
            for field in fields_to_remove:
                if field in item:
                    del item[field]
            
            # Add wear integer to each wear in the wears array
            if 'wears' in item and isinstance(item['wears'], list):
                for i, wear in enumerate(item['wears']):
                    if isinstance(wear, dict):
                        wear['int'] = i
            
            # Add rarity integer based on mapping
            if 'rarity' in item and isinstance(item['rarity'], dict) and 'id' in item['rarity']:
                rarity_id = item['rarity']['id']
                item['rarity']['int'] = rarity_mapping.get(rarity_id)
        
        # Save the sanitized data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully sanitized {input_file}")
        print(f"Saved sanitized data to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: Could not find the input file {input_file}")
    except json.JSONDecodeError:
        print(f"Error: {input_file} is not a valid JSON file")
    except Exception as e:
        print(f"Error: An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    sanitize_skin_data()