import os
import sys
import json
from google import genai
from google.genai import types

# --- PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NPC_DIR = os.path.join(BASE_DIR, "npcs")
PLAYER_FILE = os.path.join(BASE_DIR, "player_card.txt")
WORLD_FILE = os.path.join(BASE_DIR, "world_lore.txt")
SCENE_FILE = os.path.join(BASE_DIR, "scene_state.json")
MINOR_NPC_FILE = os.path.join(NPC_DIR, "minor_npcs.json")

os.makedirs(NPC_DIR, exist_ok=True)

# --- LOADERS ---

def load_world_lore():
    """Loads world setting, geography, and faction information."""
    if os.path.exists(WORLD_FILE):
        try:
            with open(WORLD_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            print(f"[Warning: Could not read world lore: {e}]")
    
    # Default fallback if world_lore.txt doesn't exist yet
    default_lore = "World: Aethelgard.\nCapital: Oakhaven (Spire District, Rust Quarter).\nWasteland: Ashen Wasteland."
    with open(WORLD_FILE, "w", encoding="utf-8") as f:
        f.write(default_lore)
    return default_lore

def load_player():
    if os.path.exists(PLAYER_FILE):
        try:
            with open(PLAYER_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    
    default_template = (
        "Name: Ren\n"
        "Appearance: A travel-worn wanderer wearing a heavy, dust-caked cloak.\n"
        "Background: A lone drifter surviving the magical wasteland."
    )
    with open(PLAYER_FILE, "w", encoding="utf-8") as f:
        f.write(default_template)
    return default_template

def load_scene_state():
    if os.path.exists(SCENE_FILE):
        try:
            with open(SCENE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    default_state = {
        "location": "Oakhaven - Rust Quarter",
        "present_npcs": ["Aria"]
    }
    save_scene_state(default_state)
    return default_state

def save_scene_state(state):
    try:
        with open(SCENE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"[Error saving scene state: {e}]")

def load_minor_npcs():
    if os.path.exists(MINOR_NPC_FILE):
        try:
            with open(MINOR_NPC_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_minor_npcs(minor_data):
    try:
        with open(MINOR_NPC_FILE, "w", encoding="utf-8") as f:
            json.dump(minor_data, f, indent=4)
    except Exception as e:
        print(f"[Error saving minor NPCs: {e}]")

# --- NPC MANAGEMENT ---

def get_major_npc_data(npc_name):
    """Loads card and memory for persistent Major NPCs."""
    safe_name = npc_name.strip().lower().replace(" ", "_")
    card_path = os.path.join(NPC_DIR, f"{safe_name}_card.txt")
    memory_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt")

    if not os.path.exists(card_path):
        default_card = f"Name: {npc_name.capitalize()}\nRole: Companion / Major Character\nPersonality: Loyal and capable."
        with open(card_path, "w", encoding="utf-8") as f:
            f.write(default_card)

    if not os.path.exists(memory_path):
        default_memory = f"Met the player character."
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(default_memory)

    with open(card_path, "r", encoding="utf-8") as f:
        card = f.read().strip()
    with open(memory_path, "r", encoding="utf-8") as f:
        memory = f.read().strip()

    return card, memory

def save_major_npc_memory(npc_name, updated_memory):
    safe_name = npc_name.strip().lower().replace(" ", "_")
    memory_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt")
    try:
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(updated_memory)
    except Exception as e:
        print(f"[Error saving memory for {npc_name}: {e}]")

# --- SCENE DIRECTOR & MEMORY SYNC ---

def update_scene_and_memories(client, history, current_scene_state):
    """Analyzes the scene to update present characters, cache minor NPCs, and update major memories."""
    director_config = types.GenerateContentConfig(
        max_output_tokens=1000,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        response_mime_type="application/json"
    )

    minor_npcs_cache = load_minor_npcs()

    director_prompt = f"""
    [System: Analyze the recent conversation transcript.
    Return a JSON object with this exact structure:
    {{
        "location": "Current location name",
        "present_npcs": ["List of major or significant NPC names in the room/space"],
        "new_minor_npcs": {{
            "NPC Name": "Short 1-sentence description of role/appearance (e.g. 'Tom: Gruff tavern keeper')"
        }}
    }}
    Rules:
    - Capitalize character names.
    - Only record minor NPCs (shopkeepers, guards, patrons) in new_minor_npcs if they interacted with the player.
    ]
    """

    try:
        res = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=history + [{"role": "user", "parts": [{"text": director_prompt}]}],
            config=director_config
        )

        parsed_state = json.loads(res.text)
        location = parsed_state.get("location", current_scene_state["location"])
        present_npcs = parsed_state.get("present_npcs", current_scene_state["present_npcs"])
        new_minors = parsed_state.get("new_minor_npcs", {})

        # 1. Update Minor NPC Cache
        if new_minors:
            minor_npcs_cache.update(new_minors)
            save_minor_npcs(minor_npcs_cache)
            print(f"✨ [Cached {len(new_minors)} Minor NPC(s) to minor_npcs.json]")

        # 2. Update Scene State
        new_scene_state = {"location": location, "present_npcs": present_npcs}
        save_scene_state(new_scene_state)
        print(f"\n[Scene Director State]: Location: '{location}' | Active NPCs: {present_npcs}")

        # 3. Update Isolated Memories for Present Major NPCs
        summary_config = types.GenerateContentConfig(
            max_output_tokens=300,
            thinking_config=types.ThinkingConfig(thinking_budget=0)
        )

        for npc_name in present_npcs:
            # Check if character has a major card file
            safe_name = npc_name.strip().lower().replace(" ", "_")
            if os.path.exists(os.path.join(NPC_DIR, f"{safe_name}_card.txt")) or npc_name in ["Aria"]:
                _, current_mem = get_major_npc_data(npc_name)
                mem_prompt = f"""
                [System: Update the isolated long-term memory for {npc_name}.
                Existing memory:
                {current_mem}
                
                Summarize new events from this session that {npc_name} witnessed or participated in. Maintain strict isolated knowledge.]
                """
                mem_res = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=history + [{"role": "user", "parts": [{"text": mem_prompt}]}],
                    config=summary_config
                )
                save_major_npc_memory(npc_name, mem_res.text)
                print(f" - Updated Major Memory: {npc_name}")

    except Exception as e:
        print(f"[Error in Scene Director: {e}]")

# --- MAIN ENGINE ---

def run_anime_engine():
    try:
        client = genai.Client()
    except Exception as e:
        print(f"Error initializing client: {e}")
        sys.exit(1)

    world_lore = load_world_lore()
    player_persona = load_player()
    scene_state = load_scene_state()
    minor_npcs = load_minor_npcs()

    # Compile present Major NPCs
    active_major_text = ""
    for npc_name in scene_state["present_npcs"]:
        card, memory = get_major_npc_data(npc_name)
        active_major_text += f"\n--- MAJOR NPC: {npc_name} ---\n[Profile]:\n{card}\n[Isolated Memory]:\n{memory}\n"

    # Compile lightweight Minor NPC Cache
    minor_npc_text = json.dumps(minor_npcs, indent=2) if minor_npcs else "None recorded yet."

    system_instruction = f"""
    You are running an advanced interactive anime webnovel engine.

    === WORLD LORE & SETTING ===
    {world_lore}
    ===========================

    === PLAYER PROFILE ===
    {player_persona}
    ======================

    === CURRENT SCENE ===
    Location: {scene_state['location']}
    Present Major Characters: {', '.join(scene_state['present_npcs'])}
    =====================

    === ACTIVE MAJOR CHARACTERS ===
    {active_major_text}
    ===============================

    === KNOWN MINOR NPCS CACHE ===
    {minor_npc_text}
    ==============================

    RULES:
    1. **World Consistency**: Anchor all scenes within the locations and rules described in World Lore.
    2. **Isolated Knowledge**: Major NPCs only know what is in their personal memory file or what occurs in front of them.
    3. **Minor NPC Handling**: Side characters (guards, shopkeepers, bartenders) use the Minor NPCs Cache. Introduce new ones naturally when necessary.
    4. **Prose Style**: Rich, vivid anime/webnovel prose. Do not control the player's choices.
    """

    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.8,
        max_output_tokens=3000,
        thinking_config=types.ThinkingConfig(thinking_budget=0)
    )

    print("=" * 60)
    print("🎬 PLAYABLE ANIME ENGINE: WORLD & TIERED NPC MODE 🎬")
    print(f"Location: {scene_state['location']}")
    print(f"Present: {scene_state['present_npcs']}")
    print("Type your actions. Type 'quit' to save and exit.")
    print("=" * 60)

    history = []
    history.append({"role": "user", "parts": [{"text": "[Start the scene dynamically based on current location, world lore, and present characters.]"}]})

    try:
        print("\n[Narrator / Scene]: ", end="", flush=True)
        response = client.models.generate_content_stream(
            model="gemini-3.8-flash",
            contents=history,
            config=config
        )
        full_text = ""
        for chunk in response:
            if chunk.text:
                print(chunk.text, end="", flush=True)
                full_text += chunk.text
        print("\n")
        history.append({"role": "model", "parts": [{"text": full_text}]})
    except Exception as e:
        print(f"\n[Error starting scene: {e}]")
        return

    while True:
        try:
            user_input = input("Your Action > ").strip()
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n[Updating world state, caching NPCs & saving memory...]")
                update_scene_and_memories(client, history, scene_state)
                print("\n[Game Saved. See you next episode!]")
                break

            if not user_input:
                continue

            history.append({"role": "user", "parts": [{"text": user_input}]})

            print("\n[Narrator / Scene]: ", end="", flush=True)
            response = client.models.generate_content_stream(
                model="gemini-3.8-flash",
                contents=history,
                config=config
            )

            full_text = ""
            for chunk in response:
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_text += chunk.text
            print("\n")

            history.append({"role": "model", "parts": [{"text": full_text}]})

        except KeyboardInterrupt:
            print("\n\n[Session ended.]")
            break

if __name__ == "__main__":
    run_anime_engine()