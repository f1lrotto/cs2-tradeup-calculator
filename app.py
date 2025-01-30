# skin info retrieved from https://bymykel.github.io/CSGO-API/api/en/skins.json

import httpx
import json
import time
import logging
import random
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('market_data.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class RateLimitedClient:
    """Client with rate limiting to prevent 429 errors"""
    def __init__(self, min_delay=1.5, max_delay=3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
        self.client = httpx.Client()
    
    def wait_if_needed(self):
        """Wait the appropriate amount of time since the last request"""
        if self.last_request_time > 0:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            if elapsed < delay:
                wait_time = delay - elapsed
                logger.debug(f"Rate limit: waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
    
    def get(self, url: str) -> httpx.Response:
        """Make a GET request with rate limiting"""
        self.wait_if_needed()
        try:
            response = self.client.get(url)
            self.last_request_time = time.time()
            return response
        except httpx.HTTPError as e:
            if e.response and e.response.status_code == 429:
                logger.warning("Rate limit hit, waiting longer...")
                time.sleep(5)  # Wait longer if we hit the rate limit
                return self.get(url)  # Retry the request
            raise
    
    def close(self):
        """Close the underlying client"""
        self.client.close()

def get_hashname(item: str, skin: str, wear: int, stat: int = 0) -> str:
    """
    Generate Steam market hashname for an item
    
    Args:
        item: Weapon name
        skin: Skin name
        wear: Wear value (0-4)
        stat: StatTrak (0 or 1)
    
    Returns:
        Steam market hashname
    """
    item = item.replace(" ", "%20")
    skin = skin.replace(" ", "%20")
    float_conditions = {
        0: "%20%28Factory%20New%29",
        1: "%20%28Minimal%20Wear%29",
        2: "%20%28Field-Tested%29",
        3: "%20%28Well-Worn%29",
        4: "%20%28Battle-Scarred%29"
    }
    wear = float_conditions[wear]
    if stat == 1:
        item = "StatTrak™%20" + item
    return item + "%20%7C%20" + skin + wear

def get_nameid(hashname: str, client: RateLimitedClient) -> int:
    """Get Steam market item nameid"""
    logger.debug(f"Getting nameid for {hashname}")
    response = client.get(f"https://steamcommunity.com/market/listings/730/{hashname}")
    html = response.text
    nameid = html.split('Market_LoadOrderSpread( ')[1]
    nameid = nameid.split(' ')[0]
    logger.debug(f"Got nameid: {nameid}")
    return int(nameid)

def item_data(hashname: str, client: RateLimitedClient) -> dict:
    """
    Get market data for an item
    
    Args:
        hashname: Steam market hashname
        client: Rate-limited client to use for requests
    
    Returns:
        Dictionary containing market data
    """
    logger.info(f"Fetching market data for {hashname}")
    start_time = time.time()
    
    nameid = str(get_nameid(hashname, client))
    data = {}

    # Get order data
    order_response = client.get(
        f"https://steamcommunity.com/market/itemordershistogram?country=US&currency=1&language=english&two_factor=0&item_nameid={nameid}"
    )
    order_data = order_response.text
    
    # Extract basic price data
    data["buy_req"] = int((order_data.split('"highest_buy_order":"')[1]).split('"')[0])/100
    data["sell_req"] = int((order_data.split('"lowest_sell_order":"')[1]).split('"')[0])/100
    
    logger.debug(f"Prices - Buy: ${data['buy_req']}, Sell: ${data['sell_req']}")
    
    # Extract buy order graph
    buy_graph_start = order_data.find('"buy_order_graph":') + len('"buy_order_graph":')
    buy_graph_end = order_data.find(']],', buy_graph_start) + 2
    buy_graph_str = order_data[buy_graph_start:buy_graph_end]
    
    # Extract sell order graph
    sell_graph_start = order_data.find('"sell_order_graph":') + len('"sell_order_graph":')
    sell_graph_end = order_data.find(']],', sell_graph_start) + 2
    sell_graph_str = order_data[sell_graph_start:sell_graph_end]
    
    # Parse the graphs
    try:
        buy_graph = eval(buy_graph_str)  # Safe to use eval here as we know the format
        sell_graph = eval(sell_graph_str)
        
        # Convert to list of dictionaries
        data["buy_orders"] = [
            {"price": float(order[0]), "count": order[1]} 
            for order in buy_graph
        ]
        data["sell_orders"] = [
            {"price": float(order[0]), "count": order[1]}
            for order in sell_graph
        ]
        logger.debug(f"Parsed {len(data['buy_orders'])} buy orders and {len(data['sell_orders'])} sell orders")
    except Exception as e:
        logger.error(f"Failed to parse order graphs: {str(e)}")
        data["buy_orders"] = []
        data["sell_orders"] = []
    
    # Get volume data
    try:
        volume_response = client.get(
            f"https://steamcommunity.com/market/priceoverview/?appid=730&currency=1&market_hash_name={hashname}"
        )
        data["volume"] = int((volume_response.text.split('volume":"')[1]).split('"')[0])
        logger.debug(f"Volume: {data['volume']}")
    except Exception as e:
        logger.warning(f"Failed to get volume data: {str(e)}")
        data["volume"] = None
        
    data["nameid"] = nameid
    
    elapsed_time = time.time() - start_time
    logger.info(f"Completed fetching market data for {hashname} in {elapsed_time:.2f} seconds")
    
    return data

def get_weapon_data(gun: str, skin: str, wear: int, stat: int = 0, client: RateLimitedClient = RateLimitedClient()) -> dict:
    """
    Get market data for a weapon skin
    
    Args:
        gun: Weapon name
        skin: Skin name
        wear: Wear value (0-4)
        stat: StatTrak (0 or 1)
        client: Rate-limited client to use for requests
    
    Returns:
        Market data dictionary
    """
    hashname = get_hashname(gun, skin, wear, stat)
    try:
        return item_data(hashname, client)
    except Exception as e:
        return {"error": f"Item data not available: {str(e)}"}

def get_case_data(case: str, client: RateLimitedClient) -> dict:
    """
    Get market data for a case
    
    Args:
        case: Case name
        client: Rate-limited client to use for requests
    
    Returns:
        Market data dictionary
    """
    hashname = case.replace(' ', '%20')
    try:
        return item_data(hashname, client)
    except Exception as e:
        return {"error": f"Item data not available: {str(e)}"}

def save_item_data(data: dict, filename: str = "market_data.json"):
    """Save item data to a JSON file in a readable format"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Data saved to {filename}")

def process_all_skins(input_file: str = 'skin_info_sanitized.json', output_file: str = 'complete_skin_info.json'):
    """
    Process all skins from the sanitized JSON file, fetch market data for each,
    and save the complete information to a new file.
    
    Args:
        input_file: Path to the sanitized skin info JSON
        output_file: Path where the complete data will be saved
    """
    start_time = time.time()
    logger.info(f"Starting skin processing - Input: {input_file}, Output: {output_file}")
    
    try:
        # Read the input JSON file
        with open(input_file, 'r', encoding='utf-8') as f:
            skins = json.load(f)
        
        total_skins = len(skins)
        logger.info(f"Found {total_skins} skins to process")
        
        # Create/clear the output file with an empty array
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
        logger.info(f"Created/cleared output file: {output_file}")
        
        # Create rate-limited client
        client = RateLimitedClient()
        
        try:
            # Process each skin
            processed_skins = []
            for i, skin in enumerate(skins, 1):
                try:
                    # Create hashname from skin name
                    if 'name' not in skin:
                        logger.warning(f"Skipping skin {i}/{total_skins}: No name found")
                        continue
                    
                    # Get market data
                    skin_names = skin['name'].split(' | ')
                    hashname = get_hashname(skin_names[0], skin_names[1], skin.get('wear', 0), skin.get('stat', 0))
                    market_data = item_data(hashname, client)
                    
                    # Add market data to skin info
                    skin['market_data'] = market_data
                    logger.info(f"Processed skin {i}/{total_skins}: {skin['name']}")
                    
                    # Add to processed skins and update file
                    processed_skins.append(skin)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(processed_skins, f, indent=2)
                    
                    progress = (i/total_skins)*100
                    logger.info(f"Progress: {i}/{total_skins} skins processed ({progress:.1f}%)")
                    
                except Exception as e:
                    logger.error(f"Error processing skin {i}/{total_skins} ({skin.get('name', 'Unknown')}): {str(e)}")
                    skin['market_data'] = {"error": str(e)}
                    # Still save the skin with error info
                    processed_skins.append(skin)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(processed_skins, f, indent=2)
                    continue
        
        finally:
            # Make sure we close the client
            client.close()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Processing complete! Time taken: {elapsed_time:.2f} seconds")
        logger.info(f"All data saved to {output_file}")
        
    except FileNotFoundError:
        logger.error(f"Could not find the input file {input_file}")
    except json.JSONDecodeError:
        logger.error(f"{input_file} is not a valid JSON file")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    logger.info("Starting market data collection")
    process_all_skins()
