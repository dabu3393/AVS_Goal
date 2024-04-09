import requests
import uuid
import json
import time
import pygame
from datetime import datetime
from threading import Thread

api_key = '' # your api_key

devices = [
    {'model_sku': '', 'device_id': '', 'scene_value': }, # Fill with yours
]

team_abbrev = "COL"  # Replace with "COL" for the Colorado Avalanche
last_score = None
last_game_id = None


def get_govee_devices():
    url = 'https://openapi.api.govee.com/router/api/v1/user/devices'
    headers = {
        'Content-Type': 'application/json',
        'Govee-API-Key': api_key,
    }

    response = requests.get(url, headers=headers)
    print(response.json())


def get_device_state(model_sku, device_id):
    url = 'https://openapi.api.govee.com/router/api/v1/device/state'
    headers = {
        'Content-Type': 'application/json',
        'Govee-API-Key': api_key,
    }
    payload = {
        "requestId": str(uuid.uuid4()),
        "payload": {
            "sku": model_sku,
            "device": device_id
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        scenes = response.json()
        return scenes
        # print(json.dumps(scenes, indent=4))  # Print the list of scenes in a formatted manner
        # You might want to parse these scenes and store them for later use
    else:
        print(f"Failed to get current state. Status code: {response.status_code}, Response: {response.text}")


def revert_to_previous_state(previous_state):
    url = 'https://openapi.api.govee.com/router/api/v1/device/control'
    headers = {
        'Content-Type': 'application/json',
        'Govee-API-Key': api_key,
    }

    for capability in previous_state["payload"]["capabilities"]:
        # Filter out capabilities that do not have a value or cannot be directly set
        if capability["state"]["value"] == "" or capability["type"] in ["devices.capabilities.online"]:
            continue

        payload = {
            "requestId": str(uuid.uuid4()),
            "payload": {
                "sku": previous_state["payload"]["sku"],
                "device": previous_state["payload"]["device"],
                "capability": {
                    "type": capability["type"],
                    "instance": capability["instance"],
                    "value": capability["state"]["value"]
                }
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(
                f"Failed to set {capability['instance']} state. Status code: {response.status_code}, Response: {response.text}")
        else:
            print(f"Successfully set {capability['instance']} to its previous state.")


def query_diy_scenes():
    device_id = '5C:1A:D7:30:38:36:2F:0F'  # Use the correct device ID for which you want the scenes
    model_sku = 'H617A'  # The SKU of your device model

    url = 'https://openapi.api.govee.com/router/api/v1/device/diy-scenes'
    headers = {
        'Content-Type': 'application/json',
        'Govee-API-Key': api_key,
    }
    payload = {
        "requestId": str(uuid.uuid4()),  # Generating a unique request ID
        "payload": {
            "sku": model_sku,
            "device": device_id
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        scenes = response.json()
        print(json.dumps(scenes, indent=4))  # Print the list of scenes in a formatted manner
        # You might want to parse these scenes and store them for later use
    else:
        print(f"Failed to query dynamic scenes. Status code: {response.status_code}, Response: {response.text}")


def play_audio(file_path):
    # Initialize Pygame Mixer
    pygame.mixer.init()
    # Load your audio file
    pygame.mixer.music.load(file_path)

    # Play the audio
    pygame.mixer.music.play()


def set_dynamic_scene(model_sku, device_id, scene_value):
    # Example of setting a scene; replace '4' with the specific value for your desired scene
    # current_state = get_device_state(model_sku, device_id)
    print(f"Setting dynamic scene for device {device_id} with model {model_sku} and scene value {scene_value}")
    url = 'https://openapi.api.govee.com/router/api/v1/device/control'
    headers = {
        'Content-Type': 'application/json',
        'Govee-API-Key': api_key,
    }

    payload = {
        "requestId": str(uuid.uuid4()),
        "payload": {
            "sku": model_sku,
            "device": device_id,
            "capability": {
                "type": "devices.capabilities.dynamic_scene",
                "instance": "diyScene",
                "value": scene_value
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        print(f"Dynamic scene set successfully for device {device_id}!")
    else:
        print(f"Failed to set dynamic scene for device {device_id}. Status code: {response.status_code}, Response: {response.text}")


def apply_scene_to_all_devices():
    for device in devices:
        set_dynamic_scene(device["model_sku"], device["device_id"])


def apply_scene_temporarily(duration):
    previous_state = []
    for device in devices:
        state = get_device_state(device["model_sku"], device["device_id"])
        if state:
            previous_state.append((device, state))

    audio_thread = Thread(target=play_audio, args=('avs_goal_song.wav',))
    audio_thread.start()

    for device in devices:
        set_dynamic_scene(device["model_sku"], device["device_id"], device["scene_value"])

    time.sleep(duration)

    for device, state in previous_state:
        revert_to_previous_state(state)

    audio_thread.join()


def check_avalanche_score(team_abbrev):
    url = 'https://api-web.nhle.com/v1/scoreboard/COL/now'  # Example URL, adjust as needed
    response = requests.get(url)
    data = response.json()

    # Get today's date in the same format as the game dates in the API response
    today_str = datetime.now().strftime('%Y-%m-%d')

    for date_section in data["gamesByDate"]:
        # Check if the date section is for today
        if date_section["date"] == today_str:
            for game in date_section["games"]:
                if game["awayTeam"]["abbrev"] == team_abbrev or game["homeTeam"]["abbrev"] == team_abbrev:
                    team_role = "awayTeam" if game["awayTeam"]["abbrev"] == team_abbrev else "homeTeam"
                    return {
                        "game_id": game["id"],
                        "score": game[team_role].get("score", 0)
                    }
    return None


while True:
    current_game_score = check_avalanche_score(team_abbrev)

    if current_game_score:
        if last_game_id is not None and current_game_score["game_id"] != last_game_id:
            print("New game detected, resetting score tracking.")
            last_score = None  # Reset score for a new game

        if last_score is None or current_game_score["score"] > last_score:
            if last_score is not None:  # Avoid triggering at the first check
                print("Goal detected! Executing light and sound effects.")
                time.sleep(30)
                apply_scene_temporarily(50)  # Trigger your effects

            last_score = current_game_score["score"]

        last_game_id = current_game_score["game_id"]
    else:
        print("No current game found for team.")

    time.sleep(5)


