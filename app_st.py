import os
import json
import streamlit as st
from google import genai
from google.genai import types

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Playable Anime Engine",
    page_icon="🎬",
    layout="wide"
)

# --- STRICT DIRECTORY ANCHORING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NPC_DIR = os.path.join(BASE_DIR, "npcs")
PLAYER_FILE = os.path.join(BASE_DIR, "player_card.txt")
WORLD_FILE = os.path.join(BASE_DIR, "world_lore.txt")
SCENE_FILE = os.path.join(BASE_DIR, "scene_state.json")
MINOR_NPC_FILE = os.path.join(NPC_DIR, "minor_npcs.json")
ROSTER_FILE = os.path.join(BASE_DIR, "roster.json")
CONFIG_FILE = os.path.join(BASE_DIR, "game_config.json")
CHAT_SAVE_FILE = os.path.join(BASE_DIR, "chat_save.json")

os.makedirs(NPC_DIR, exist_ok=True)

# --- LOADERS & SAVERS ---
def load_file(filepath, default_content=""):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    return content
        except Exception:
            pass
    if default_content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(default_content)
    return default_content

def load_world_lore():
    return load_file(WORLD_FILE, "World: Aethelgard\nCapital: Oakhaven\nWasteland: Ashen Wasteland")

def load_player():
    return load_file(PLAYER_FILE, "Name: Ren\nAppearance: Dust-caked traveler.\nBackground: Wasteland drifter.")

def load_scene_state():
    if os.path.exists(SCENE_FILE):
        try:
            with open(SCENE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    default_state = {"location": "Oakhaven - Rust Quarter", "present_npcs": ["Aria"]}
    save_scene_state(default_state)
    return default_state

def save_scene_state(state):
    with open(SCENE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def load_minor_npcs():
    if os.path.exists(MINOR_NPC_FILE):
        try:
            with open(MINOR_NPC_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_minor_npcs(data):
    with open(MINOR_NPC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_roster():
    if os.path.exists(ROSTER_FILE):
        try:
            with open(ROSTER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    default_roster = {
        "Aria": "A veteran wasteland scavenger with silver hair and tactical gear.",
        "Kaelen": "A cynical fixer operating out of the Oakhaven underground taverns.",
        "Lyra": "A mysterious tech-adept who trades in pre-collapse data chips."
    }
    save_roster(default_roster)
    return default_roster

def save_roster(data):
    with open(ROSTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_game_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    default_config = {
        "opening_prompt": "Begin the roleplay engine. The player character (Ren) is standing in the dim, rain-slicked alleys of Oakhaven's Rust Quarter. Aria is leaning against a rusted bulkhead nearby, watching the street. Set the atmospheric scene and invite the player to take their first action."
    }
    save_game_config(default_config)
    return default_config

def save_game_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# Chat Save / Load Functions
def save_chat_session():
    data = {
        "messages": st.session_state.get("messages", []),
        "api_history": st.session_state.get("api_history", [])
    }
    with open(CHAT_SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def load_chat_session():
    if os.path.exists(CHAT_SAVE_FILE):
        try:
            with open(CHAT_SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("messages", []), data.get("api_history", [])
        except Exception:
            pass
    return None, None

def get_major_npc_data(npc_name):
    safe_name = npc_name.strip().lower().replace(" ", "_")
    card_path = os.path.join(NPC_DIR, f"{safe_name}_card.txt")
    memory_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt")
    
    card = load_file(card_path, f"Name: {npc_name.capitalize()}\nRole: Companion\nPersonality: Capable and alert.")
    memory = load_file(memory_path, f"- First encountered the player character at {load_scene_state().get('location', 'the wasteland')}.")
    return card, memory

def save_major_npc_memory(npc_name, updated_memory):
    safe_name = npc_name.strip().lower().replace(" ", "_")
    memory_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt")
    backup_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt.bak")
    
    if os.path.exists(memory_path) and os.path.getsize(memory_path) > 0:
        with open(memory_path, "r", encoding="utf-8") as f_orig:
            old_data = f_orig.read()
        with open(backup_path, "w", encoding="utf-8") as f_bak:
            f_bak.write(old_data)
            
    with open(memory_path, "w", encoding="utf-8") as f:
        f.write(updated_memory)

# --- SYSTEM INSTRUCTION BUILDER ---
def build_system_instruction():
    world_lore = load_world_lore()
    player_persona = load_player()
    scene_state = load_scene_state()
    minor_npcs = load_minor_npcs()
    roster = load_roster()

    active_major_text = ""
    for npc_name in scene_state.get("present_npcs", []):
        card, memory = get_major_npc_data(npc_name)
        active_major_text += f"""
        ==================================================
        CRITICAL CHARACTER DATA FOR: {npc_name.upper()}
        [Official Character Card]:
        {card}
        
        [STRICT ISOLATED MEMORY - YOU MUST ROLEPLAY ACCORDING TO THIS]:
        {memory}
        ==================================================
        """

    system_content = f"""
    You are running an interactive anime roleplay webnovel engine.

    === WORLD LORE ===
    {world_lore}

    === PLAYER PROFILE ===
    {player_persona}

    === AVAILABLE WORLD ROSTER (Characters the Director can introduce into scenes) ===
    {json.dumps(roster, indent=2)}

    === CURRENT SCENE ===
    Location: {scene_state.get('location')}
    Present Major NPCs: {', '.join(scene_state.get('present_npcs', []))}

    {active_major_text}

    === MINOR NPC CACHE ===
    {json.dumps(minor_npcs, indent=2)}

    MANDATORY RULES:
    1. Character Memories are Absolute: If an NPC has past events logged in their [STRICT ISOLATED MEMORY], they absolutely remember them and must react accordingly.
    2. Dynamic Integration: You may seamlessly bring characters from the [AVAILABLE WORLD ROSTER] into the scene when narrative pacing dictates.
    3. Style: Vivid anime prose. Never control player choices.
    """
    return system_content

# --- INITIALIZE GEMINI CLIENT & SESSION STATE ---
try:
    client = genai.Client()
except Exception as e:
    st.error(f"Failed to initialize Gemini Client: {e}")

# Check for existing save file on startup
saved_messages, saved_history = load_chat_session()

if "messages" not in st.session_state:
    if saved_messages:
        st.session_state.messages = saved_messages
    else:
        st.session_state.messages = []

if "api_history" not in st.session_state:
    if saved_history:
        st.session_state.api_history = saved_history
    else:
        st.session_state.api_history = []
        # Trigger AI-Initiated Opening on first clean load
        config_data = load_game_config()
        opening_instruction = config_data.get("opening_prompt", "Begin roleplay.")
        
        try:
            init_system = build_system_instruction()
            init_config = types.GenerateContentConfig(
                system_instruction=init_system,
                temperature=0.8,
                max_output_tokens=800,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
            res = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[{"role": "user", "parts": [{"text": f"[System Opening Command]: {opening_instruction}"}]}],
                config=init_config
            )
            opening_text = res.text
            st.session_state.messages.append({"role": "assistant", "content": opening_text})
            st.session_state.api_history.append({"role": "user", "parts": [{"text": f"[Opening Command]: {opening_instruction}"}]})
            st.session_state.api_history.append({"role": "model", "parts": [{"text": opening_text}]})
            save_chat_session() # Auto-save the opening
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"[Error generating opening hook: {e}]"})

# --- SIDEBAR CONTROLS ---
with st.sidebar:
    st.subheader("🗺️ Scene & World Controls")
    scene = load_scene_state()
    
    st.write(f"**Current Location:** {scene.get('location')}")
    st.write(f"**Present NPCs:** {scene.get('present_npcs', [])}")

    st.markdown("---")
    st.markdown("### 💾 Game Save & Progress")
    if st.button("💾 Save Progress Now"):
        save_chat_session()
        st.success("Chat session and progress saved to disk!")

    st.markdown("---")
    st.markdown("### 🎬 Customizable Opening Hook")
    config_data = load_game_config()
    new_opening_prompt = st.text_area("Initial Prompt / Scenario", value=config_data.get("opening_prompt", ""), height=120)
    if st.button("Save Opening Prompt"):
        config_data["opening_prompt"] = new_opening_prompt
        save_game_config(config_data)
        st.success("Opening prompt updated! Reset chat to apply.")

    st.markdown("---")
    st.markdown("### 👥 World Roster & Scene Management")
    roster = load_roster()
    
    roster_choices = list(roster.keys())
    selected_roster_char = st.selectbox("Select Character from Roster", roster_choices)
    if st.button("➕ Add Roster Character to Scene"):
        current_present = scene.get("present_npcs", [])
        if selected_roster_char not in current_present:
            current_present.append(selected_roster_char)
            scene["present_npcs"] = current_present
            save_scene_state(scene)
            
            safe_name = selected_roster_char.lower().replace(" ", "_")
            card_path = os.path.join(NPC_DIR, f"{safe_name}_card.txt")
            memory_path = os.path.join(NPC_DIR, f"{safe_name}_memory.txt")
            
            if not os.path.exists(card_path):
                with open(card_path, "w", encoding="utf-8") as f:
                    f.write(f"Name: {selected_roster_char}\nDescription: {roster[selected_roster_char]}")
            if not os.path.exists(memory_path):
                with open(memory_path, "w", encoding="utf-8") as f:
                    f.write(f"- First encountered the player character at {scene.get('location')}.")
            
            st.success(f"Added {selected_roster_char} to the active scene!")
            st.rerun()
        else:
            st.warning(f"{selected_roster_char} is already present.")

    current_present = scene.get("present_npcs", [])
    if current_present:
        npc_to_remove = st.selectbox("Select Character to Remove", current_present, key="remove_select")
        if st.button("➖ Remove Character"):
            current_present.remove(npc_to_remove)
            scene["present_npcs"] = current_present
            save_scene_state(scene)
            st.success(f"Removed {npc_to_remove} from scene.")
            st.rerun()

    st.markdown("---")
    if st.button("💾 Save Session & Sync Director"):
        if not st.session_state.api_history:
            st.warning("No chat history to save yet.")
        else:
            with st.spinner("Syncing scene state and updating NPC memories..."):
                try:
                    director_config = types.GenerateContentConfig(
                        max_output_tokens=600,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                        response_mime_type="application/json"
                    )
                    roster_keys = list(load_roster().keys())
                    director_prompt = f'[System: Analyze transcript and available roster {roster_keys}. Return ONLY valid JSON: {{"location": "...", "present_npcs": [...], "new_minor_npcs": {{}}}}]'
                    
                    res = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=st.session_state.api_history + [{"role": "user", "parts": [{"text": director_prompt}]}],
                        config=director_config
                    )
                    
                    raw_text = res.text.strip()
                    try:
                        parsed = json.loads(raw_text)
                    except json.JSONDecodeError:
                        sanitized_text = raw_text.replace('\n', ' ').replace('\r', '')
                        parsed = json.loads(sanitized_text)

                    save_scene_state({
                        "location": parsed.get("location", scene.get("location")),
                        "present_npcs": parsed.get("present_npcs", scene.get("present_npcs"))
                    })
                    if parsed.get("new_minor_npcs"):
                        minors = load_minor_npcs()
                        minors.update(parsed.get("new_minor_npcs"))
                        save_minor_npcs(minors)

                    summary_config = types.GenerateContentConfig(max_output_tokens=600)
                    for npc_name in scene.get("present_npcs", []):
                        _, current_mem = get_major_npc_data(npc_name)
                        mem_prompt = f"""[System: Review conversation. Return ONLY 1 to 3 short bullet points summarizing NEW significant events witnessed by {npc_name}. Do NOT repeat existing points. Return NOTHING if no major new event occurred.]"""
                        
                        mem_res = client.models.generate_content(
                            model="gemini-3.8-flash",
                            contents=st.session_state.api_history + [{"role": "user", "parts": [{"text": mem_prompt}]}],
                            config=summary_config
                        )
                        
                        new_bullets = mem_res.text.strip() if mem_res.text else ""
                        if len(new_bullets) > 5 and not new_bullets.lower().startswith("none"):
                            full_updated_mem = current_mem + "\n" + new_bullets
                            save_major_npc_memory(npc_name, full_updated_mem)

                    save_chat_session()
                    st.success("State synchronized, memories appended, and game saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync error: {e}")

    st.markdown("---")
    if st.button("🔄 Reset Chat & Clear History"):
        if os.path.exists(CHAT_SAVE_FILE):
            os.remove(CHAT_SAVE_FILE)
        st.session_state.messages = []
        st.session_state.api_history = []
        st.success("Chat history cleared & fresh game started!")
        st.rerun()

# --- MAIN CHAT INTERFACE ---
st.title("🎬 Playable Anime Engine")
st.caption("Local persistent multi-character webnovel running on Gemini 3.8 Flash & Streamlit")

for message in st.session_state.messages:
    role = message["role"]
    avatar_icon = "👤" if role == "user" else "🤖"
    with st.chat_message(role, avatar=avatar_icon):
        st.markdown(message["content"])

if user_input := st.chat_input("Type your character's actions or dialogue..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.api_history.append({"role": "user", "parts": [{"text": user_input}]})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            system_instruction = build_system_instruction()
            config = types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.8,
                max_output_tokens=800,
                thinking_config=types.ThinkingConfig(thinking_budget=0)
            )

            response = client.models.generate_content_stream(
                model="gemini-3.8-flash",
                contents=st.session_state.api_history,
                config=config
            )

            for chunk in response:
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.api_history.append({"role": "model", "parts": [{"text": full_response}]})
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
            # Automatically save progress after every successful turn
            save_chat_session()

        except Exception as e:
            error_msg = f"[Error generating response: {e}]"
            message_placeholder.markdown(error_msg)