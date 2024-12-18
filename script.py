import gradio as gr
import modules.shared as shared
from pathlib import Path
import re
import json
from functools import partial
from modules.text_generation import stop_everything_event
from modules import chat
from modules import ui as main_ui
from modules.utils import gradio
from modules.extensions import apply_extensions
import random

right_symbol = '\U000027A1'
left_symbol = '\U00002B05'
refresh_symbol = '\U0001f504'  # 🔄

def atoi(text):
    return int(text) if text.isdigit() else text.lower()

def natural_keys(text):
    return [atoi(c) for c in re.split(r'(\d+)', text)]

def get_file_path(filename):
    return "extensions/StoryCrafter/"+filename

last_save = get_file_path("last.json")
save_proj_path = get_file_path("Projects")
save_proj_path_txt = get_file_path("Text")
state_save = get_file_path("state.json")

params = {
        "display_name": "StoryCrafter",
        "is_tab": True,
        "selectA": [0,0],
        'projectname':"temp_project",
        'auto_clear': True,
        'include_history': True,
        'include_history_nr':5,
        'lorebook':'',
        'system':'You are experienced fiction writer. Develop the plot slowly. Describe all actions in full, elaborate and vivid detail.',
        'world':''

}



help_str = """
**Help**

This is for writing and generating stories beat by beat (short passages of scenes, paragraphs). At each generation all the previously written/edited beats will be dynamically inserted into LLM as a memory. You can edit the beats any time you wish as both final text and the text LLM see is dynamically generated from the beats each time. 

Versions

Each beat can also have multiple versions and you can then choose which version to include in the final text.

Cross variation to prompt. In the Instruct mode you can specify [V1], [V2] or [V3] in the prompt and it will insert the text from that version. This way you can instruct to rewrite the text without copying the text to prompt. 
For example: Rewrite the following text using first person POV [V1] or Summarrize the following text: [V2]

Future Cues

Each beat can also have Future Cues - unlike Prompt, which are directions for the currently generated text, Future Cues are for the text that will be generated after the current one, down the page. Here you can specify changes and twists that are valid AFTER this test.
For example if in this block of text the character is changing their hairstyle, in the Future Cues you might specify: from this point refer to Anna as having short pink hair
"""


# Define the global data_structure

selected_item = "Beat 1"
selected_item_title = "Beat 1"
selected_item_prompt = "Write a paragraph where ..."
selected_item_scenetext = ""
selected_scene_version = "v1"
selected_item_notes = ""
full_text_until = ""
full_text = ""

#load from lorebook
dynamic_lore = []
dynamic_lore_changed = False

data_structure = [{"outline": selected_item, "outline_title": selected_item_title, "prompt": selected_item_prompt, "scenetext_v1": selected_item_scenetext,"scenetext_v2": "","scenetext_v3": "", "version": selected_scene_version,"notes":selected_item_notes, "is_summary": False}]

def does_outline_exist(outline_name):
    global data_structure
    return any(item["outline"] == outline_name for item in data_structure)

def get_first_outline_name():
    global data_structure
    if data_structure:
        return data_structure[0]["outline"]
    else:
        return ""  # Return None if data_structure is empty

def get_first_outline_name_title(default_title):
    global data_structure
    if data_structure and len(data_structure) > 0:
         return data_structure[0].get("outline_title", default_title)
    else:
        return default_title 


def get_data_by_outline(outline_title):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_title:
            key = "scenetext_"+item["version"]
            return item["prompt"], item[key], item["version"], item["notes"]
    return None, None  # Return None if the outline_title is not found

def get_title_by_outline(outline_title):
    global data_structure
    def_out = outline_title
    for item in data_structure:
        if item["outline"] == outline_title:
            return item.get("outline_title", def_out)
    return None, None  # Return None if the outline_title is not found



def delete_item_by_outline(outline_title):
    global data_structure
    global selected_item
    next_selected_item = ""
    for item in data_structure:
        if item["outline"] == outline_title:
            data_structure.remove(item)
            selected_item = next_selected_item
            if selected_item=="" and len(data_structure)>0:
                selected_item = data_structure[0]["outline"]

            return True  # Item deleted successfully
        next_selected_item = item["outline"]
    return False  # Item not found

def generate_unique_outline_name_old(scene_string):
    global data_structure
    # Initialize a counter to create unique names
    counter = 1
    while True:
        outline_title = f"{scene_string} {counter}"
        # Check if the generated name is already in use
        if not any(item["outline"] == outline_title for item in data_structure):
            return outline_title
        counter += 1


def generate_unique_outline_name(base_name):
    global data_structure
    
    # Initialize the max number as 0
    max_number = 0
    
    # Iterate through all items in data_structure
    for item in data_structure:
        try:
            # Extract the number from the end of the outline (e.g., "Beat 23")
            number = int(item["outline"].split()[-1])
            max_number = max(max_number, number)
        except ValueError:
            # Ignore outlines that don't end with a number
            continue
    
    # Generate a new unique outline name
    new_outline_name = f"{base_name} {max_number + 1}"
    return new_outline_name

def add_item(outline_title, prompt_string, scene_string):
    global data_structure
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global selected_item_notes    
    outline_name2 = outline_title

    
    new_item = {"outline": outline_title, "outline_title": outline_name2, "prompt": prompt_string, "scenetext_v1": scene_string,"scenetext_v2": "","scenetext_v3": "", "version": "v1", "notes": "", "is_summary": False}

    selected_item = outline_title
    selected_item_title = outline_name2
    selected_item_prompt = prompt_string
    selected_item_scenetext = scene_string
    selected_scene_version = new_item["version"]
    selected_item_notes = ""
    
    data_structure.append(new_item)


def add_item_auto(scene_prefix, prompt_string, scene_text):
    global data_structure
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global selected_item_notes
    # Check if data_structure has any data
    if len(data_structure)>0:
        # Get the last item in data_structure
        last_item = data_structure[-1]

        # Check if the last item has "prompt" == '' and "scenetext_v1" == ''
        if last_item["prompt"] == '' and last_item["scenetext_v1"] == '':
            # Overwrite the last item with new values
            last_item["prompt"] = prompt_string
            last_item["scenetext_v1"] = scene_text
            last_item["scenetext_v2"] = ""
            last_item["scenetext_v3"] = ""
            last_item["is_summary"] = False
            last_item["version"] = "v1"
            last_item["notes"] = ""

            # Update selected_item, selected_item_prompt, and selected_item_scenetext
            selected_item = last_item["outline"]
            selected_item_title = last_item["outline_title"]
            selected_item_prompt = last_item["prompt"]
            selected_item_scenetext = last_item["scenetext_v1"]
            selected_scene_version = last_item["version"]
            selected_item_notes = last_item["notes"]
            # Update data_structure with the modified last_item
            data_structure[-1] = last_item
            return  # Exit the function without adding a new item


    outline_title = generate_unique_outline_name(scene_prefix)
    outline_name2 = outline_title

    new_item = {"outline": outline_title, "outline_title": outline_name2, "prompt": prompt_string, "scenetext_v1": scene_text,"scenetext_v2": "","scenetext_v3": "", "version": "v1", "notes":"", "is_summary": False}

    selected_item = outline_title
    selected_item_title = outline_name2
    selected_item_prompt = prompt_string
    selected_item_scenetext = scene_text
    selected_scene_version = new_item["version"]
    selected_item_notes = ""
    

    data_structure.append(new_item)


def set_version_by_outline(outline_title, scene_version):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_title:
            item["version"] = scene_version
            return True  # Item updated successfully
    return False  # Item not found

def update_item_by_outline(outline_title, scene_version, new_prompt, new_scene_text):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_title:
            item["prompt"] = new_prompt
            item["version"] = scene_version
            key = "scenetext_"+item["version"]
            item[key] = new_scene_text
            return True  # Item updated successfully
    return False  # Item not found

def update_item_title_by_outline(outline_name, new_outline_title):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_name:
            item["outline_title"] = new_outline_title
            return True  # Item updated successfully
    return False  # Item not found

def update_prompt_by_outline(outline_title, new_prompt):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_title:
            item["prompt"] = new_prompt
            return True  # Item updated successfully
    return False  # Item not found

def update_scenetext_by_outline(outline_title, new_scene_text):
    global data_structure
    for item in data_structure:
        if item["outline"] == outline_title:
            key = "scenetext_"+item["version"]
            item[key] = new_scene_text
            return True  # Item updated successfully
    return False  # Item not found

def update_notes_by_outline(outline_title, new_notes_text):
    global data_structure
    for item in data_structure:
            item['notes'] = new_notes_text
            return True  # Item updated successfully
    return False  # Item not found


def generate_combined_text():
    global data_structure
    global full_text
    full_text = ""
    for item in data_structure:
        key = "scenetext_"+item["version"]
        full_text += item[key]+'\n\n'

    #full_text = '\n\n'.join(item["scenetext"] for item in data_structure)
    full_text = full_text.strip()
    return full_text

# used in generate 
def generate_combined_text_until_current_with_history(max_last):
    global data_structure
    global selected_item
    outline_title = selected_item
    count_before_outline = 0
    temp_hist = []

    if max_last > 0:
        for item in data_structure:
            if item["outline"] == outline_title:
                break  # Stop when the specified outline_title is reached

            # Check if we've reached the limit of history_number
            if count_before_outline < max_last:
                key = "scenetext_"+item["version"]
                temp_hist.append(item[key])
            else:
                # If we've reached the limit, remove the oldest entry
                temp_hist.pop(0)
                key = "scenetext_"+item["version"]
                temp_hist.append(item[key])

            if item["notes"]!='':
                note_txt = "Note: "+item["notes"]
                temp_hist.append(note_txt)

            count_before_outline += 1


    combined_text = ""
    for item_txt in temp_hist:
        combined_text += item_txt + '\n\n'
    text_until = combined_text.rstrip('\n\n')  # Remove trailing newline if any

    return text_until 

# used for preview
def generate_combined_text_until_current():
    global data_structure
    global selected_item
    global full_text_until
    combined_text = ""
    outline_title = selected_item
    for item in data_structure:
        if item["outline"] == outline_title:
            break  # Stop when the specified outline_title is reached
        key = "scenetext_"+item["version"]
        combined_text += item[key] + '\n\n'
    full_text_until = combined_text.rstrip('\n\n')  # Remove trailing newline if any

    if full_text_until =='':
        full_text_until = '[Beginning]'
    return full_text_until 


def move_item_up(outline_title):
    global data_structure
    for i in range(len(data_structure)):
        if data_structure[i]["outline"] == outline_title and i > 0:
            # Swap the item with the preceding one
            data_structure[i], data_structure[i - 1] = data_structure[i - 1], data_structure[i]
            return True  # Item moved up successfully
    return False  # Item not found or already at the top

def move_item_down(outline_title):
    global data_structure
    for i in range(len(data_structure) - 1):
        if data_structure[i]["outline"] == outline_title and i < len(data_structure) - 1:
            # Swap the item with the following one
            data_structure[i], data_structure[i + 1] = data_structure[i + 1], data_structure[i]
            return True  # Item moved down successfully
    return False  # Item not found or already at the bottom


class ToolButton(gr.Button, gr.components.FormComponent):
    """Small button with single emoji as text, fits inside gradio forms"""

    def __init__(self, **kwargs):
        super().__init__(variant="tool", **kwargs)

    def get_block_name(self):
        return "button"


def create_refresh_button(refresh_component, refresh_method, refreshed_args, elem_class):
    def refresh():
        refresh_method()
        args = refreshed_args() if callable(refreshed_args) else refreshed_args

        for k, v in args.items():
            setattr(refresh_component, k, v)

        return gr.update(**(args or {}))

    refresh_button = ToolButton(value=refresh_symbol, elem_classes=elem_class)
    refresh_button.click(
        fn=refresh,
        inputs=[],
        outputs=[refresh_component]
    )
    return refresh_button


def read_file_to_string(file_path):
    data = ''
    try:
        with open(file_path, 'r') as file:
            data = file.read()
    except FileNotFoundError:
        data = ''

    return data

# lore format
# keyword, keyword: Lore text
def parse_dynamic_lore(lore_string):
    memories = []
    entries = lore_string.strip().split('\n\n')  # Split the input string into entries separated by blank lines
    
    print("Parsing lore")

    for entry in entries:
        lines = entry.strip().split('\n')  # Split each entry into lines
        if len(lines) < 2:  # Ensure there are at least two lines (keywords and memory text)
            continue
        
        keywords_part = lines[0].strip()  # First line contains keywords
        memory_text = '\n'.join(lines[1:]).strip()  # Combine the rest as memory text
        
        # Remove colons and process keywords
        keywords = [kw.replace(':', '').strip().lower() for kw in keywords_part.split(',')]
        
        # Append the parsed data to the memories list
        memories.append({
            'keywords': ','.join(keywords),  # Join keywords with commas
            'memory': memory_text
        })
       
    return memories


def atoi(text):
    return int(text) if text.isdigit() else text.lower()

def save_string_to_file(file_path, string):
    try:
        with open(file_path, 'w') as file:
            file.write(string)
        print("String saved to file successfully.")
    except Exception as e:
        print("Error occurred while saving string to file:", str(e))

#last_save
def save_to_json(path_to_file):
    global data_structure
    try:
        with open(Path(path_to_file), 'w') as json_file:
            json.dump(data_structure, json_file, indent=2)
        return True    
    except:
        print(f"Saving to {path_to_file} failed")
        return False  # File not found or invalid JSON

def load_from_json(path_to_file):
    global data_structure
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global selected_item_notes
    global full_text_until
    global full_text

    print(f"Loading project: {path_to_file}")
    try:
        with open(Path(path_to_file), 'r') as json_file:
            data_structure.clear()  # Clear existing data
            data_structure.extend(json.load(json_file))

            # Ensure all entries in data_structure have the required keys
            default_values = {
                "outline": "Beat 1",
                "outline_title": "Untitled",
                "prompt": "",
                "scenetext_v1": "",
                "scenetext_v2": "",
                "scenetext_v3": "",
                "version":"v1",
                "notes": "",
                "is_summary": False
            }
            for entry in data_structure:
                for key, default in default_values.items():
                    if key not in entry:
                        entry[key] = default
    


            generate_combined_text()
            selected_item = get_first_outline_name()
            selected_item_title = get_first_outline_name_title(selected_item)
            generate_combined_text_until_current()
            selected_item_prompt,selected_item_scenetext, selected_scene_version, selected_item_notes = get_data_by_outline(selected_item)
            

        return True  # Loading successful
    except (FileNotFoundError, json.JSONDecodeError):
        return False  # File not found or invalid JSON

def save_state():
    global params
    global state_save
    
    try:
        with open(Path(state_save), 'w') as json_file:
            json.dump(params, json_file, indent=4)
    except:
        print("Can't save last state..")

def load_state():
    global params
    global state_save
    global dynamic_lore_changed
    
    try:
        with open(Path(state_save), 'r') as json_file:
            new_params = json.load(json_file)
            dynamic_lore_changed = True
            for item in new_params:
                params[item] = new_params[item]
    except:
        pass


def save_proj_state(path_to_file):
    global params
    
    try:
        with open(Path(path_to_file), 'w') as json_file:
            json.dump(params, json_file, indent=4)
    except:
        print("Can't save last state..")        

def load_proj_state(path_to_file):
    global params
    global dynamic_lore_changed
    try:
        with open(Path(path_to_file), 'r') as json_file:
            new_params = json.load(json_file)
            dynamic_lore_changed = True
            for item in new_params:
                params[item] = new_params[item]
    except:
        pass



last_history_visible = []
last_history_internal = []
last_undo = ""  



def get_scene_list():
    global data_structure
    return [item["outline"] for item in data_structure]


#def generate_reply_wrapperMY(question, textBoxB, context_replace, extra_context, extra_prefix, state, quick_instruction, _continue=False, _genwithResponse = False, _continue_sel = False, _postfix = '', _addstop = []):

def replace_placeholder(text, placeholder, replacement):
    return text.replace(placeholder, replacement)

# Generates a response in chat mode, focusing on turn-based interactions.
# Uses a structured history (last_history) to provide context from previous exchanges.
# This function is intended for chat-like interactions where the model responds to individual prompts.
# Contrast with generate_reply_wrapperMY_NP, which focuses on continuous narrative generation.
# Uses chat.generate_chat_prompt for prompt construction and chat.generate_reply with is_chat=True for generation.
# Handles streaming and interruption logic.

def generate_reply_wrapperMY(text_prompt, existing_text_in_output, state, _continue=False):

    global params
    global last_history_visible
    global last_history_internal
    global last_undo
    global last_save
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global full_text_until
    global full_text
    global data_structure
    global dynamic_lore_changed
    global dynamic_lore

    selF = params['selectA'][0]
    selT = params['selectA'][1]
 
    params['selectA'] = [0,0]
   
    new_version = True
    if 'turn_template' in state:
        new_version = False
    
    visible_text = None

    if "[V1]" in text_prompt or "[V2]" in text_prompt or "[V3]" in text_prompt:
        for item in data_structure:
            if item["outline"] == selected_item:
                if "[V1]" in text_prompt:
                    text_prompt = replace_placeholder(text_prompt, "[V1]", item['scenetext_v1'])
                if "[V2]" in text_prompt:
                    text_prompt = replace_placeholder(text_prompt, "[V2]", item['scenetext_v2'])
                if "[V3]" in text_prompt:
                    text_prompt = replace_placeholder(text_prompt, "[V3]", item['scenetext_v3'])
                break    



    user_prompt = text_prompt

    text_to_keep = ""

    if params['lorebook']!='' and not dynamic_lore:
        dynamic_lore_changed=True

    if dynamic_lore_changed==True:
        dynamic_lore = parse_dynamic_lore(params['lorebook'])
        dynamic_lore_changed = False

    generate_combined_text()

    if new_version:
       if state['instruction_template_str']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return
    else:
        if state['turn_template']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return



    state['mode'] = 'instruct'
    
    _iswriting = "..."

    #context = state['context']
        
    if new_version:
        context_instruct = state['custom_system_message']
        contest_instruct_bk = context_instruct

        #state['custom_system_message'] = context_instruct

    else:        
        context_instruct = state['context_instruct']
        contest_instruct_bk = context_instruct

        #state['context_instruct'] = context_instruct
        

    state = apply_extensions('state', state)
    if shared.model_name == 'None' or shared.model is None:
        print("No model is loaded! Select one in the Model tab.")
        yield text_to_keep, full_text
        return
    
    output = {'visible': [], 'internal': []}    
    output['internal'].append(['', ''])
    output['visible'].append(['', ''])

    last_history = {'visible': [], 'internal': []} 

    # fill history with previous text
    outline_title = selected_item
    count_before_outline = 0

    if params['include_history_nr'] > 0 and params['include_history']:
        for item in data_structure:
            if item["outline"] == outline_title:
                break  # Stop when the specified outline_title is reached

            hist_prompt = item["prompt"]
            key = "scenetext_"+item["version"]
            hist_response = item[key]

            hist_notes = item["notes"]
            # Check if we've reached the limit of history_number
            if count_before_outline < params['include_history_nr']:
                last_history['internal'].append([hist_prompt, hist_response])
                last_history['visible'].append([hist_prompt, hist_response])
            else:
                # If we've reached the limit, remove the oldest entry
                last_history['internal'].pop(0)
                last_history['visible'].pop(0)
                last_history['internal'].append([hist_prompt, hist_response])
                last_history['visible'].append([hist_prompt, hist_response])

            if hist_notes!='':
                note_text = 'Note: '+hist_notes
                note_response = "(Understood. I’ll keep this note in mind as I write further.)"
                last_history['internal'].append([note_text, note_response])
                last_history['visible'].append([note_text, note_response])


            count_before_outline += 1

  
    #for item in data_structure:
    #    if item["outline"] == outline_title:
    #        break  # Stop when the specified outline_title is reached

    #    hist_prompt = item["prompt"]
    #    hist_response = item["scenetext"]    
    #    last_history['internal'].append([hist_prompt, hist_response])
    #    last_history['visible'].append([hist_prompt, hist_response])
           
    


    # simple
    #story_so_far = generate_combined_text_until_current()
    #if story_so_far!="":
    #    hist_response = "Thank you, I will remember that."
    #    hist_prompt = "Here is the story so far:\n"+story_so_far
    #    last_history['internal'].append([hist_prompt, hist_response])
    #    last_history['visible'].append([hist_prompt, hist_response])

    stopping_strings = chat.get_stopping_strings(state)

    is_stream = state['stream']

  # Prepare the input
    if not _continue:
        visible_text = user_prompt

        # Apply extensions
        user_prompt, visible_text = apply_extensions('chat_input', user_prompt, visible_text, state)
        user_prompt = apply_extensions('input', user_prompt, state, is_chat=True)

        outtext = _iswriting
        yield outtext, full_text

    else:
        visible_text = user_prompt 

        if _continue:
            text_to_keep = existing_text_in_output
            # continue sel can span across squiglies
            
            # fill history for generate_chat_prompt
            #user_msg, assistant_msg
            last_history['internal'].append([user_prompt, existing_text_in_output])
            last_history['visible'].append([user_prompt, existing_text_in_output])

            outtext = text_to_keep + _iswriting   
            yield outtext, full_text


        # Generate the prompt
    kwargs = {
        '_continue': _continue,
        'history': last_history,
    }


    system_message = contest_instruct_bk
    world_msg = ''
    lore_msg = ''

    if params['system']!='':
        system_message = params['system']
        system_message = system_message.rstrip('\n')

    if params['world']!='':
        world_msg = "\n\n"+params['world']

    #add dynamic lore from prompt
    if dynamic_lore:
        user_input_lower = text_prompt.lower()
        for dyn_mem_item in dynamic_lore:
                # Check to see if keywords are present.
            keywords = dyn_mem_item["keywords"].lower().split(",")
            for keyword in keywords:
                keywordsimp = keyword.strip()
                if keywordsimp!='' and keywordsimp in user_input_lower:
                    print(f"Found Lore keyword: {keywordsimp}")
                    # keyword is present in user_input
                    lore_msg += "\n\n"+ dyn_mem_item["memory"]



    if new_version:
        state['custom_system_message'] = system_message+world_msg+lore_msg
    else:    
        state['context_instruct'] = system_message+world_msg+lore_msg


    #prompt = apply_extensions('custom_generate_chat_prompt', question, state, **kwargs)

    
    prompt = chat.generate_chat_prompt(user_prompt, state, **kwargs)

   #put it back, just in case
    if new_version:
        state['custom_system_message'] = contest_instruct_bk
    else:    
        state['context_instruct'] = contest_instruct_bk

    # Generate
    reply = None
    for j, reply in enumerate(chat.generate_reply(prompt, state, stopping_strings=stopping_strings, is_chat=True)):

        visible_reply = reply #re.sub("(<USER>|<user>|{{user}})", state['name1'], reply)
        
        if shared.stop_everything:
            output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=True)

            output_text = output['visible'][-1][1]
            print("--Interrupted--")
            update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
            generate_combined_text()
            save_to_json(last_save)

            yield  text_to_keep + output_text, full_text

            return

        if _continue:
            output['internal'][-1] = [user_prompt,  reply]
            output['visible'][-1] = [visible_text, visible_reply]
            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
                yield text_to_keep + output_text, full_text
        elif not (j == 0 and visible_reply.strip() == ''):
            output['internal'][-1] = [user_prompt, reply.lstrip(' ')]
            output['visible'][-1] = [visible_text, visible_reply.lstrip(' ')]

            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
                yield  text_to_keep + output_text, full_text

    output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=True)
    
    output_text = output['visible'][-1][1]
    
    # not really used for anything
    last_history_visible = output['visible'][-1]
    last_history_internal = output['internal'][-1]
    
    update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
    generate_combined_text()
    save_to_json(last_save)
    save_state()

    yield  text_to_keep + output_text, full_text

# Generates a response in narrative mode, focusing on continuous text generation.
# Combines all previous block text (using generate_combined_text_until_current_with_history) into a single context.
# This function is designed for generating longer, more narrative-driven text, as opposed to the turn-based interactions of generate_reply_wrapperMY.
# Uses chat.generate_reply with is_chat=False for generation.

def generate_reply_wrapperMY_NP(text_prompt, existing_text_in_output, state, _continue=False):

    global params
    global last_history_visible
    global last_history_internal
    global last_undo
    global last_save
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global full_text_until
    global full_text
    global data_structure
    global dynamic_lore_changed
    global dynamic_lore


    selF = params['selectA'][0]
    selT = params['selectA'][1]
 
    params['selectA'] = [0,0]
   
    new_version = True
    if 'turn_template' in state:
        new_version = False
    
    visible_text = None

    user_prompt = text_prompt

    text_to_keep = ""

    if params['lorebook']!='' and not dynamic_lore:
        dynamic_lore_changed=True

    if dynamic_lore_changed==True:
        dynamic_lore = parse_dynamic_lore(params['lorebook'])
        dynamic_lore_changed = False


    generate_combined_text()

    if new_version:
       if state['instruction_template_str']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return
    else:
        if state['turn_template']=='':
            print("Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction Template]")
            text_to_keep = existing_text_in_output + "\n Instruction template is empty! Select Instruct template in tab [Parameters] - [Instruction template]"
            yield text_to_keep, full_text
            return



    state['mode'] = 'instruct'
    
    _iswriting = "..."

    #context = state['context']
        
    if new_version:
        context_instruct = state['custom_system_message']
        contest_instruct_bk = context_instruct

        #state['custom_system_message'] = context_instruct

    else:        
        context_instruct = state['context_instruct']
        contest_instruct_bk = context_instruct

        #state['context_instruct'] = context_instruct
        

    state = apply_extensions('state', state)
    if shared.model_name == 'None' or shared.model is None:
        print("No model is loaded! Select one in the Model tab.")
        yield text_to_keep, full_text
        return
    
    output = {'visible': [], 'internal': []}    
    output['internal'].append(['', ''])
    output['visible'].append(['', ''])

    last_history = {'visible': [], 'internal': []} 

    # fill history with previous text
    if params['include_history_nr']>0 and params['include_history']:
        story_so_far = generate_combined_text_until_current_with_history(params['include_history_nr'])
    else:
        story_so_far = ''

    stopping_strings = chat.get_stopping_strings(state)

    is_stream = state['stream']

  # Prepare the input
    if not _continue:
        visible_text = user_prompt

        outtext = _iswriting
        yield outtext, full_text

    else:
        visible_text = user_prompt 

        if _continue:
            text_to_keep = existing_text_in_output+'\n'
            # continue sel can span across squiglies
            story_so_far = story_so_far +"\n"+ existing_text_in_output
            outtext = text_to_keep + _iswriting   
            yield outtext, full_text


        # Generate the prompt
    kwargs = {
        '_continue': _continue,
        'history': last_history,
    }

    #prompt = apply_extensions('custom_generate_chat_prompt', question, state, **kwargs)

    system_message = contest_instruct_bk
    world_msg = ''
    lore_msg = ''

    if params['system']!='':
        system_message = params['system']
        system_message = system_message.rstrip('\n')

    if params['world']!='':
        world_msg = "\n\n"+params['world']+"\n\n"

   #add dynamic lore from prompt
    if dynamic_lore:
        user_input_lower = text_prompt.lower()
        for dyn_mem_item in dynamic_lore:
                # Check to see if keywords are present.
            keywords = dyn_mem_item["keywords"].lower().split(",")
            
            for keyword in keywords:
                keywordsimp = keyword.strip()
                if keywordsimp!='' and keywordsimp in user_input_lower:
                    # keyword is present in user_input
                    print(f"Found Lore keyword: {keywordsimp}")
                    lore_msg += "\n\n"+ dyn_mem_item["memory"]


    prompt = system_message + world_msg + lore_msg
    prompt = prompt+ story_so_far+"\n" 
    if text_prompt!='':
        prompt = prompt + "(Editor's Note: Continue writing the story using the following direction. "+ text_prompt+")\n"

    #put it back, just in case
    if new_version:
        state['custom_system_message'] = contest_instruct_bk
    else:    
        state['context_instruct'] = contest_instruct_bk

    # Generate
    reply = None
    for j, reply in enumerate(chat.generate_reply(prompt, state, stopping_strings=stopping_strings, is_chat=False)):

        #visible_reply = re.sub("(<USER>|<user>|{{user}})", state['name1'], reply)
        visible_reply = reply
        
        if shared.stop_everything:
            output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=False)

            output_text = output['visible'][-1][1]
            print("--Interrupted--")
            update_item_by_outline(selected_item, selected_scene_version,text_prompt, text_to_keep + output_text)
            generate_combined_text()
            save_to_json(last_save)

            yield  text_to_keep + output_text, full_text

            return

        if _continue:
            output['internal'][-1] = [user_prompt,  reply]
            output['visible'][-1] = [visible_text, visible_reply]
            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, selected_scene_version,text_prompt, text_to_keep + output_text)
                yield text_to_keep + output_text, full_text
        elif not (j == 0 and visible_reply.strip() == ''):
            output['internal'][-1] = [user_prompt, reply.lstrip(' ')]
            output['visible'][-1] = [visible_text, visible_reply.lstrip(' ')]

            if is_stream:
                output_text = output['visible'][-1][1]
                update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
                yield  text_to_keep + output_text, full_text

    output['visible'][-1][1] = apply_extensions('output', output['visible'][-1][1], state, is_chat=False)
    
    output_text = output['visible'][-1][1]
    
    # not really used for anything
    last_history_visible = output['visible'][-1]
    last_history_internal = output['internal'][-1]
    
    update_item_by_outline(selected_item, selected_scene_version, text_prompt, text_to_keep + output_text)
    generate_combined_text()
    save_to_json(last_save)
    save_state()

    yield  text_to_keep + output_text, full_text

def custom_css():
    return """
.preview-text textarea {
    background-color: #071407 !important;
    --input-text-size: 16px !important;
    color: #4dc66a !important;
    --body-text-color: #4dc66a !important;
    font-family: monospace
    
}
.scene-text textarea {
    background-color: #301919 !important;
    color: #f19999 !important;
    --body-text-color: #f19999 !important;
    font-family: monospace
    
}
.scene-text2 textarea {
    background-color: #192930 !important;
    color: #99CCFF !important;
    --body-text-color: #99CCFF !important;
    font-family: monospace
    
}
    """

def custom_js():
    java = '''
const blockwriterElement = document.querySelector('#textbox-blockwriter textarea');
let blockwriterScrolled = false;

blockwriterElement.addEventListener('scroll', function() {
  let diff = blockwriterElement.scrollHeight - blockwriterElement.clientHeight;
  if(Math.abs(blockwriterElement.scrollTop - diff) <= 1 || diff == 0) {
    blockwriterScrolled = false;
  } else {
    blockwriterScrolled = true;
  }
});

const blockwriterObserver = new MutationObserver(function(mutations) {
  mutations.forEach(function(mutation) {
    if(!blockwriterScrolled) {
      blockwriterElement.scrollTop = playgroundAElement.scrollHeight;
    }
  });
});

blockwriterObserver.observe(blockwriterElement.parentNode.parentNode.parentNode, config);

'''
    return java


def create_action_button(button_label, main_function, update_function, outputs, variant = 'primary'):

    _ishow = False

    def show():
        nonlocal _ishow
        if _ishow:
            _ishow = False
            return gr.Button.update(visible=False),gr.Button.update(visible=False)
        else:
            _ishow = True
            return gr.Button.update(visible=True),gr.Button.update(visible=True)

    def hide():
        nonlocal _ishow
        _ishow = False
        return gr.Button.update(visible=False),gr.Button.update(visible=False)
    
    def process():
        nonlocal _ishow
        _ishow = False
        main_function()
        return gr.Button.update(visible=False),gr.Button.update(visible=False)

    _intMain = gr.Button(button_label, interactive=True, variant = variant)
    with gr.Row():
        _intAction = gr.Button(value= 'Continue?',variant="primary",visible=False,interactive=True)
        _intCancel = gr.Button(value='Cancel',visible=False,interactive=True)

   
    _intMain.click(show,None,[_intAction,_intCancel])
    _intCancel.click(hide,None,[_intAction,_intCancel])
    _intAction.click(process,None,[_intAction,_intCancel]).then(update_function,None,outputs)

    return _intMain

def create_save_button(button_label, save_method, defaultname_variable, default_key, save_method_inputs = None, variant = 'secondary'):

    def show():
        defname = defaultname_variable[default_key] if defaultname_variable is not None else default_key
        return gr.Textbox.update(value = defname, interactive= True, visible=True),gr.Button.update(visible=True),gr.Button.update(visible=True),gr.Button.update(visible=False)

    def hide():
        return gr.Textbox.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=True)
    
    _intMain = gr.Button(button_label, interactive=True,variant=variant)
    _edit_name = gr.Textbox(value='',lines=1,max_lines=1,visible=False, label='Name',interactive=True)
    with gr.Row():
        _intAction = gr.Button(value=button_label,variant="primary",visible=False,interactive=True)
        _intCancel = gr.Button(value='Cancel',visible=False,interactive=True)

    _intMain.click(show,None,[_edit_name,_intAction,_intCancel,_intMain])
    _intCancel.click(hide,None,[_edit_name,_intAction,_intCancel,_intMain])
    inputs = [_edit_name] + save_method_inputs if save_method_inputs is not None else _edit_name
    _intAction.click(save_method,inputs,None).then(hide,None,[_edit_name,_intAction,_intCancel,_intMain])

    return _intMain


def create_load_button(button_label, load_method, file_list_method, update_function, outputs, variant = 'secondary'):

    def show():
        choices = file_list_method()
        return gr.Dropdown.update(choices=choices, value='None', visible = True),gr.Button.update(visible=True),gr.Button.update(visible=True),gr.Button.update(visible=False)

    def hide():
        return gr.Textbox.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=True)
    
    def process(text):
        load_method(text)
        return gr.Textbox.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=False),gr.Button.update(visible=True)

    _intMain = gr.Button(button_label, interactive=True,variant=variant)
    _drop = gr.Dropdown(choices=['None'], label= button_label, value='None',visible=False,interactive=True)
    with gr.Row():
        _intAction = gr.Button(value='Load',variant="primary",visible=False,interactive=True)
        _intCancel = gr.Button(value='Cancel',visible=False,interactive=True)

   
    _intMain.click(show,None,[_drop,_intAction,_intCancel,_intMain])
    _intCancel.click(hide,None,[_drop,_intAction,_intCancel,_intMain])
    _intAction.click(process,_drop,[_drop,_intAction,_intCancel,_intMain]).then(update_function,None,outputs)

    return _intMain

#font-family: monospace
def get_available_projects():
    templpath = save_proj_path
    paths = (x for x in Path(templpath).iterdir() if x.suffix in ('.json'))
    sortedlist = sorted(set((k.stem for k in paths)), key=natural_keys)
    sortedlist.insert(0, "None")
    return sortedlist

# Example usage:
def lorebook_save_action(name, text):
    # Replace this with your save logic
    print(f"Saving file: {name}")
    print(f"Saving file: {text}")

def project_save(projname):
    global params
    global last_save
    params['projectname'] = projname
    projpath = save_proj_path +"/"+ projname+".json"
    projpath2 = save_proj_path +"/"+ projname+".jsonw"

    save_to_json(projpath)
    save_to_json(last_save)
    save_proj_state(projpath2)
    save_state()
    print(f"Project saved to: {projpath}")
    return projname

def quick_project_save():
    global params
    global last_save
    projname = params['projectname']
    projpath = save_proj_path +"/"+ projname+".json"
    projpath2 = save_proj_path +"/"+ projname+".jsonw"

    save_to_json(projpath)
    save_proj_state(projpath2)

    save_to_json(last_save)
    save_state()
    print(f"Project saved to: {projpath}")


def load_project(projname):
    global params
    params['projectname'] = projname
    projpath = save_proj_path +"/"+ projname+".json"
    projpath2 = save_proj_path +"/"+ projname+".jsonw"
    load_from_json(projpath)
    load_proj_state(projpath2)
    print(f"Project loaded: {projpath}")

def rename_scene(scene_name):
    global params
    print(f"Saving file: {scene_name}")

def full_update_ui():
    global selected_item
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global full_text_until
    global full_text
    global selected_item_notes
    global params

    return gr.Radio.update(choices=get_scene_list(), value=selected_item), selected_item, selected_item_prompt, selected_item_scenetext, selected_scene_version, full_text_until, full_text, selected_item_notes, params['projectname'], params['projectname'], params['system'],params['world'],params['lorebook']      

def create_new_project():
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global full_text_until
    global full_text
    global data_structure
    global last_save
    global params

    selected_item = "Beat 1"
    selected_item_title = "Beat 1"

    selected_item_prompt = "Write a paragraph where ..."
    selected_item_scenetext = ""
    full_text_until = ""
    full_text = ""
    params['projectname'] = 'new_project'
    data_structure = [{"outline": selected_item,"outline_title": selected_item_title, "prompt": selected_item_prompt, "scenetext_v1": selected_item_scenetext, "scenetext_v2": "", "scenetext_v3": "","version":"v1","notes":"","is_summary": False}]

    params['world']=''
    params['lorebook']=''
    save_to_json(last_save)
    save_state()

def delete_beat_funct():
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global selected_scene_version
    global full_text_until
    global full_text
    global data_structure
    global last_save

    delete_item_by_outline(selected_item)


def ui():
    global params
    global selected_item
    global selected_item_title
    global selected_item_prompt
    global selected_item_scenetext
    global full_text
    global full_text_until


    params['selectA'] = [0,0]

    load_state()
    load_from_json(last_save)

    with gr.Row():
        with gr.Column():

            with gr.Tab('Scenes'):
                with gr.Row():
                    with gr.Column(scale = 1):
                        with gr.Row():
                            gr_btn_addnew_scene = gr.Button(value='+ New Beat',visible=True,variant="primary")
                        with gr.Row():    
                            gr_scenes_radio = gr.Radio(choices=get_scene_list(), value=selected_item, label='Beats', interactive=True, elem_classes='checkboxgroup-table')
                    with gr.Column(scale = 3):
                        with gr.Row():
                            gr_itemname = gr.Textbox(value=selected_item_title, lines = 1, visible = True, label = 'Beat Title', interactive=True, elem_classes=['scene-text'])
                        with gr.Row():    
                            gr_prompt = gr.Textbox(value=selected_item_prompt ,lines=4,visible=True, label='Prompt')
                        with gr.Row():
                            with gr.Tab('Instruct Mode'):
                                with gr.Row():
                                    gr_btn_generate = gr.Button(value='Generate',visible=True,variant="primary")
                                    gr_btn_generate_continue = gr.Button(value='Continue',visible=True)
                                    gr_btn_stop = gr.Button(value='Stop',visible=True) #elem_classes="small-button")
                                with gr.Row():
                                    gr.Markdown('The text will be generated from the prompt using model instruction template.')                                     
                            with gr.Tab('Narrative Mode'):
                                with gr.Row():
                                    gr_btn_generate_np = gr.Button(value='Generate (Narrative)',variant="primary", visible=True)
                                    gr_btn_generate_continue_np = gr.Button(value='Continue (Narrative)',visible=True)
                                    gr_btn_stop_np = gr.Button(value='Stop',visible=True)
                                with gr.Row():
                                    gr.Markdown('The text will be generated as a Narrative completion of the scenes before. Prompt can be used to steer the generation but is used without adding instruction template.')    
                            with gr.Tab('Future Cues'):
                                with gr.Row():        
                                    gr_notes = gr.Textbox(value=selected_item_notes ,lines=4,visible=True,interactive=True, label='Future Cues will be visible to the text model and will shape further text generation', elem_classes=['scene-text2'])
                            with gr.Tab('Settings'):
                                with gr.Row():        
                                    #gr_auto_clear = gr.Checkbox(label = "Auto Clear Prompt", value = params['auto_clear'])    
                                    gr_include_history = gr.Checkbox(label = "Include Previous Scenes and Notes in the prompt", value = params['include_history']) 
                                    include_last_history = gr.Slider(value = params['include_history_nr'],step = 1, minimum=0, maximum=50, label='Max Number of newset Scenes to Include')
                            with gr.Tab('Tools'):
                                with gr.Row():
                                    gr_tools_swap = gr.Button(value='<> Swap',visible=True, elem_classes="small-button")

                        with gr.Row():
                            gr_generated_text_version = gr.Radio(choices = ['v1','v2','v3'], value= selected_scene_version , visible=True, label='Version')    
                        with gr.Row():
                            gr_generated_text = gr.Textbox(value=selected_item_scenetext ,lines=10,visible=True, label='Text',elem_classes=['textbox', 'add_scrollbar'],elem_id='textbox-blockwriter')
   
                        with gr.Row():
                            gr_btn_save_Quick = gr.Button(value='Quick Save',visible=True,variant="primary")
                            gr_itemUp = gr.Button("Move Up")
                            gr_itemDown = gr.Button("Move Down")  
                            delete_beat = gr.Button('Delete Current Beat', interactive=True)
                            delete_confirm = gr.Button('Are you Sure?', variant='stop', visible=False) #,elem_classes=['refresh-button']
                            delete_cancel = gr.Button('Cancel', visible=False)
                    with gr.Column(scale = 3):
                        with gr.Row():
                            gr_prevtext = gr.Textbox(value=full_text_until, lines = 35, visible = True, label = 'Story to this point', interactive=False,elem_classes=['preview-text', 'add_scrollbar'])

            with gr.Tab('Full Text'):
                with gr.Row():
                    with gr.Column(scale = 1):
                        gr_project_name_txt = gr.Textbox(value =  params['projectname'], lines=1, label='Text Name') 
                        gr_btn_save_Text = gr.Button(value='Save Text',visible=True,variant="primary")
                    with gr.Column(scale = 4):    
                        gr_fulltext = gr.Textbox(value=full_text,lines=25,visible=True, label='Full Text', elem_classes=['preview-text', 'add_scrollbar'])
                    with gr.Column(scale = 1):
                        gr.Markdown('')         
            with gr.Tab('Lore book'):
                with gr.Row():
                    with gr.Column(scale=4):
                        gr_text_SYSTEM = gr.Textbox(value = params['system'], lines=2, label='System Prompt') 
                    with gr.Column(scale=1):
                        gr.Markdown('Set System message. This will be always send as the first thing to the text model') 
                with gr.Row():        
                    with gr.Column(scale=4):    
                        gr_text_WOORLD = gr.Textbox(value = params['world'], lines=10, label='Story Description and World (always present in prompt)') 
                    with gr.Column(scale=1):
                        gr.Markdown('Description of the story, world, characters. This will be alwayspresent on the top of the prompt below the system prompt') 
                with gr.Row():        
                    with gr.Column(scale=4):    
                        gr_text_DYNAMEMORY = gr.Textbox(value = params['lorebook'], lines=10, label='Dynamic Lore') 
                    with gr.Column(scale=1):
                        gr.Markdown('Lore triggered by a keywords in the prompt. The Lore will be only used if a keyword in the prompt triggers it.') 
                        gr_lore_example = gr.Button(value='Load Example', visible=True)

            with gr.Tab('Project'):
                with gr.Row():
                    with gr.Column(scale=1):
                        
                        gr_project_name = gr.Textbox(value =  params['projectname'], lines=1, label='Current Project') 
                        gr_project_save = gr.Button('Save Project', interactive=True)
                        gr_project_saveA = gr.Button('Save?', visible=False)
                        gr_project_saveC = gr.Button('Cancel', variant='stop', visible=False)
                        #create_save_button( 'Save Project', project_save,params, params['projectname'])  
                        create_load_button( 'Load project', load_project, get_available_projects, full_update_ui, [gr_scenes_radio,gr_itemname,gr_prompt,gr_generated_text,gr_generated_text_version, gr_prevtext,gr_fulltext,gr_notes, gr_project_name,gr_project_name_txt,gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY] )  
                        gr.Markdown('---') 
                        create_action_button('New Project',create_new_project,full_update_ui,[gr_scenes_radio,gr_itemname,gr_prompt,gr_generated_text,gr_generated_text_version,gr_prevtext,gr_fulltext,gr_notes,gr_project_name,gr_project_name_txt,gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY])
                    with gr.Column(scale=4): 
                    
                        gr.Markdown(help_str)

    def update_state_param(sysmsg, world, lore):
        global params
        global dynamic_lore_changed
        params['system'] = sysmsg
        params['world'] = world
        lore_before = params['lorebook']
        params['lorebook'] = lore

        if lore_before!=lore: 
            dynamic_lore_changed = True


    gr_text_SYSTEM.input(update_state_param,[gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY],None)
    gr_text_WOORLD.input(update_state_param,[gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY],None)
    gr_text_DYNAMEMORY.input(update_state_param,[gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY],None)

    def write_lore():
        global params
        global dynamic_lore_changed

        lore = """rimmer,arnold:
Arnold Judas Rimmer - A hologram of a deceased crew member, painfully neurotic, insufferably pompous, and obsessed with climbing the ranks of the Space Corps despite being utterly incompetent. Known for his pedantic obsession with Space Corps directives and his strained relationship with Lister.

cat:
The Cat - A highly evolved humanoid descendant of the ship's original pet cat. Vain, flamboyant, and obsessed with fashion, he moves with feline grace but is utterly self-centered. Lives for his looks and has a hilariously tenuous grasp of the crew's perilous reality.

lister,dave:
Dave Lister - The last human alive, a slobby, curry-loving everyman with a big heart and a dream of returning to Earth. Despite his laziness and crude manners, he's the emotional core of the crew, often finding himself at odds with Rimmer's uptight personality but deeply loyal to his companions."""

 
        params['lorebook'] = lore
        dynamic_lore_changed = True

        return lore

    gr_lore_example.click(write_lore,None,gr_text_DYNAMEMORY)

    def update_item_ui():
        global selected_item_title
        global selected_item_prompt
        global selected_item_scenetext
        global selected_scene_version
        global selected_item_notes
        global full_text_until
        return selected_item_title, selected_item_prompt, selected_item_scenetext, selected_scene_version, full_text_until, selected_item_notes


    def update_scenes_ui():
        global selected_item
        return gr.Radio.update(choices=get_scene_list(), value=selected_item)

    def select_scene(scene_name):
        global selected_item
        global selected_item_title
        global selected_item_prompt
        global selected_item_scenetext
        global selected_scene_version
        global selected_item_notes

        if does_outline_exist(scene_name):
            selected_item = scene_name
            selected_item_prompt, selected_item_scenetext, selected_scene_version, selected_item_notes = get_data_by_outline(scene_name)
            selected_item_title = get_title_by_outline(scene_name)
            generate_combined_text_until_current()
        

    gr_scenes_radio.change(select_scene,gr_scenes_radio,None).then(update_item_ui,None,[gr_itemname,gr_prompt,gr_generated_text,gr_generated_text_version, gr_prevtext,gr_notes],show_progress=False)

    def change_version(version):
        global selected_item
        global selected_item_title
        global selected_item_prompt
        global selected_item_scenetext
        global selected_scene_version
        global selected_item_notes

        selected_scene_version = version

        set_version_by_outline(selected_item,version)
        selected_item_prompt, selected_item_scenetext, selected_scene_version, selected_item_notes = get_data_by_outline(selected_item)
        generate_combined_text_until_current()
        generate_combined_text()  




    def update_text_version_change():
        global selected_item_scenetext
        global full_text_until
        global full_text
        return selected_item_scenetext,full_text_until,full_text


    gr_generated_text_version.change(change_version,gr_generated_text_version,None).then(update_text_version_change, None, [gr_generated_text,gr_prevtext,gr_fulltext],show_progress=False)


    clear_arr = [delete_confirm, delete_beat, delete_cancel]
    delete_beat.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, clear_arr)
    delete_cancel.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, clear_arr)
    delete_confirm.click(delete_beat_funct,None,None).then(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, clear_arr).then(
        full_update_ui, None,[gr_scenes_radio,gr_itemname,gr_prompt,gr_generated_text,gr_generated_text_version, gr_prevtext,gr_fulltext,gr_notes,gr_project_name,gr_project_name_txt,gr_text_SYSTEM,gr_text_WOORLD,gr_text_DYNAMEMORY])


    save_arr = [gr_project_saveA, gr_project_save, gr_project_saveC]
    gr_project_save.click(lambda: [gr.update(visible=True), gr.update(visible=False), gr.update(visible=True)], None, save_arr)
    gr_project_saveC.click(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, save_arr)
    gr_project_saveA.click(project_save,gr_project_name,gr_project_name_txt).then(lambda: [gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)], None, save_arr)

    gr_btn_save_Quick.click(quick_project_save,None,None)

    def full_text_save(savename):
        text = generate_combined_text()
        projpath = save_proj_path_txt +"/"+ savename+".txt"  
        try:
       
            # Save the text to the file
            with open(projpath, 'w', encoding='utf-8') as file:
                file.write(text)
            
            print(f"Text successfully saved to: {projpath}")
        except Exception as e:
            print(f"Failed to save text to file. Error: {e}")        


    gr_btn_save_Text.click(full_text_save,gr_project_name_txt,None)

    def add_new_item():
        add_item_auto("Beat","","")
        generate_combined_text_until_current()

    gr_btn_addnew_scene.click(add_new_item,None,None).then(update_scenes_ui, None, gr_scenes_radio,show_progress=False).then(update_item_ui, None,[gr_itemname,gr_prompt,gr_generated_text,gr_generated_text_version, gr_prevtext, gr_notes],show_progress=False)

    def change_prompt(text):
        global selected_item
        global selected_item_prompt
        selected_item_prompt = text
        update_prompt_by_outline(selected_item,selected_item_prompt)


    gr_prompt.input(change_prompt,gr_prompt,None)

    def change_scenetext(text):
        global selected_item
        global selected_item_scenetext
        selected_item_scenetext = text
        update_scenetext_by_outline(selected_item,selected_item_scenetext)
        return generate_combined_text()

    gr_generated_text.input(change_scenetext,gr_generated_text,gr_fulltext,show_progress=False)

    def change_notes(text):
        global selected_item_notes
        global selected_item
        selected_item_notes = text
        update_notes_by_outline(selected_item,selected_item_notes)

    gr_notes.input(change_notes,gr_notes,None,show_progress=False)

    def change_title(text):
        global selected_item
        global selected_item_title
        update_item_title_by_outline(selected_item,text)
        selected_item_title = text


    gr_itemname.input(change_title,gr_itemname,None)

    def moveitemup():
        global selected_item
        move_item_up(selected_item)

        return gr.Radio.update(choices=get_scene_list(), value=selected_item), generate_combined_text(), generate_combined_text_until_current()
    
    gr_itemUp.click(moveitemup,None,[gr_scenes_radio,gr_fulltext,gr_prevtext])


    def moveitemdown():
        global selected_item
        move_item_down(selected_item)

        return gr.Radio.update(choices=get_scene_list(), value=selected_item), generate_combined_text(), generate_combined_text_until_current()
    
    gr_itemDown.click(moveitemdown,None,[gr_scenes_radio,gr_fulltext,gr_prevtext])

  
    input_paramsA = [gr_prompt, gr_generated_text, shared.gradio['interface_state']]
    output_paramsA =[gr_generated_text,gr_fulltext]


    disable_struct = [gr_scenes_radio,gr_btn_addnew_scene,gr_itemUp,gr_itemDown,gr_btn_generate,gr_btn_generate_continue,gr_btn_generate_np,gr_btn_generate_continue_np]

    def update_full_text_ui():
        global full_text_until
        return full_text_until
    
    def disable_radio():
        return gr.Radio.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False), gr.Button.update(interactive=False)

    def enable_radio():
        return gr.Radio.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True), gr.Button.update(interactive=True)

    gr_btn_generate.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(disable_radio,None,disable_struct).then(
        generate_reply_wrapperMY, inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(enable_radio,None,disable_struct) 

    gr_btn_generate_np.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(disable_radio,None,disable_struct).then(
        generate_reply_wrapperMY_NP, inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(enable_radio,None,disable_struct)
 
    gr_btn_generate_continue_np.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(disable_radio,None,disable_struct).then(
        partial(generate_reply_wrapperMY_NP, _continue=True), inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(enable_radio,None,disable_struct)

    gr_btn_generate_continue.click(main_ui.gather_interface_values, gradio(shared.input_elements), gradio('interface_state')).then(disable_radio,None,disable_struct).then(
         partial(generate_reply_wrapperMY, _continue=True), inputs=input_paramsA, outputs= output_paramsA, show_progress=False).then(enable_radio,None,disable_struct)

    def stop_everything_eventMy():
        shared.stop_everything = True

    gr_btn_stop.click(stop_everything_eventMy, None, None, queue=False)    
    gr_btn_stop_np.click(stop_everything_eventMy, None, None, queue=False)

    include_last_history.change(lambda x: params.update({"include_history_nr": x}), include_last_history,None)
    #gr_auto_clear.change(lambda x: params.update({"auto_clear": x}), gr_auto_clear, None)
    gr_include_history.change(lambda x: params.update({"include_history": x}), gr_include_history, None) 

    def swap_current():
        global selected_item
        global data_structure
        global selected_item_prompt
        global selected_item_scenetext
        global selected_scene_version
        global selected_item_notes
        global full_text
        for item in data_structure:
            if item["outline"] == selected_item:
                key = "scenetext_"+item["version"]
                prompt = item["prompt"]
                item["prompt"] = item[key]
                item[key] = prompt
                break

        generate_combined_text()
        selected_item_prompt, selected_item_scenetext, selected_scene_version, selected_item_notes = get_data_by_outline(selected_item)
        return selected_item_prompt, selected_item_scenetext, full_text        


    gr_tools_swap.click(swap_current,None,[gr_prompt,gr_generated_text,gr_fulltext])