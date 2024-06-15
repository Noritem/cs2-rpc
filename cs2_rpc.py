import os
import json
import time
import random
import string
from flask import Flask, request, jsonify
from pypresence import Presence
import threading
import logging

app = Flask(__name__)
CLIENT_ID = '1251184799704416396'
RPC = Presence(CLIENT_ID)
RPC.connect()
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

CONFIG_FILE = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive\\game\\csgo\\cfg\\gamestate_integration_discord.cfg'

def create_config_file():
    """Create game state integration config file if it doesn't exist."""
    cfg_directory = os.path.dirname(CONFIG_FILE)
    if not os.path.exists(cfg_directory):
        os.makedirs(cfg_directory)
    
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    config_data = f"""
"CSGO_Discord"
{{
    "uri" "http://127.0.0.1:3032"
    "timeout" "5.0"
    "buffer" "0.1"
    "throttle" "0.5"
    "heartbeat" "60.0"
    "auth"
    {{
        "token" "{token}"
    }}
    "output"
    {{
        "precision_time" "3"
        "precision_position" "1"
        "precision_vector" "3"
    }}
    "data"
    {{
        "provider" "1"
        "map" "1"
        "round" "1"
        "player_id" "1"
        "player_state" "1"
        "player_weapons" "1"
        "player_match_stats" "1"
    }}
}}
    """
    
    with open(CONFIG_FILE, 'w') as f:
        f.write(config_data.strip())
    logging.info(f'Config file created at: {CONFIG_FILE}')
    return token

if not os.path.exists(CONFIG_FILE):
    TOKEN = create_config_file()
else:
    logging.info(f'Using existing config file at: {CONFIG_FILE}')
    with open(CONFIG_FILE, 'r') as f:
        for line in f:
            if 'token' in line:
                TOKEN = line.split('"')[3]
                break
        else:
            logging.error('Token not found in config file.')
            exit(1)

game_state = {
    'map': 'Unknown',
    'team': 'T',
    'score_t': 0,
    'score_ct': 0,
    'menu_state': 'Unknown',
    'in_game': False,
    'match_phase': 'Unknown',
    'round_phase': 'Unknown'
}

last_rpc_update = int(time.time())
update_interval = 15

def update_rpc():
    global last_rpc_update, update_interval
    while True:
        try:
            current_time = int(time.time())
            if current_time - last_rpc_update >= update_interval:
                if game_state['in_game']:
                    state = f'Playing {game_state["menu_state"]} Match on {game_state["map"]}'
                    details = f'Score: T {game_state["score_t"]} - {game_state["score_ct"]} CT (Round: {game_state["round_phase"]})'
                    small_image = 't' if game_state['team'] == 'T' else 'ct'
                    RPC.update(
                        state=state,
                        details=details,
                        large_image='cs2',
                        small_image=small_image,
                        start=last_rpc_update 
                    )
                else:
                    state = 'In Main Menu'
                    details = 'Browsing Menus'
                    RPC.update(
                        state=state,
                        details=details,
                        large_image='cs2',
                        start=last_rpc_update  
                    )
                
                update_interval = 30 if update_interval == 15 else 15
                last_rpc_update = current_time
        except Exception as e:
            logging.error(f"Error updating Discord RPC: {e}")
        
        time.sleep(1)
@app.route('/', methods=['POST'])
def game_state_update():
    global game_state
    try:
        data = request.json

        if data.get('auth', {}).get('token') != TOKEN:
            return jsonify({'error': 'Unauthorized'}), 401

        if 'map' in data and data['map']['name'] != 'menu':
            game_state['map'] = data['map']['name']
            game_state['team'] = data['player']['team']
            game_state['score_t'] = data['map']['team_t']['score']
            game_state['score_ct'] = data['map']['team_ct']['score']
            game_state['match_phase'] = data['map']['phase']
            game_state['round_phase'] = data['round']['phase']
            game_state['in_game'] = True
            logging.info(f"Game state updated: In Game - Map: {game_state['map']}, Team: {game_state['team']}, Score: T {game_state['score_t']} - CT {game_state['score_ct']}")
        else:
            game_state['map'] = 'Main Menu'
            game_state['menu_state'] = data.get('match', {}).get('mode', 'Unknown')
            game_state['in_game'] = False
            logging.info("Game state updated: In Main Menu")

        return '', 200
    except KeyError as e:
        logging.error(f"KeyError: Missing key {e} in received data: {data}")
        return jsonify({'error': 'Bad Request', 'message': f'Missing key: {e}'}), 400
    except Exception as e:
        logging.error(f"Error processing game state update: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    threading.Thread(target=update_rpc, daemon=True).start()
    app.run(host='0.0.0.0', port=3032,debug=False)
