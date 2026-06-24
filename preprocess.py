import os
import re
import yaml
import pymupdf
from os.path import join as pjoin
from tqdm import tqdm

root = '.'
data_folder = 'data'
script_folder = 'scripts'
dialogue_folder = 'dialogues'
config_file = 'config.yaml'

with open(pjoin(root, config_file), 'r') as f:
    config = yaml.safe_load(f)

list_of_superheroes = config['LIST_OF_SUPERHEROES']
superhero_synonyms = config['SUPERHERO_SYNONYMS']
movies_list_of_superheroes = config['MOVIES_LIST_OF_SUPERHEROES']
dialogues_joiner = config.get('DIALOGUES_JOINER', "\n|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|_/-|\n\n")
max_context_length = 100

data_folder_path = pjoin(root, data_folder)

def extract_text(script_path):
    if script_path.lower().endswith('.txt'):
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            pass
    pdf = pymupdf.open(script_path)
    text = ''
    for page in pdf:
        text += page.get_text()
    return text

def get_all_superhero_names(superhero, superhero_synonyms):
    superhero_synonym = superhero_synonyms.get(superhero, [superhero])[0]
    names = [
        superhero.upper(),
        superhero.title(),
        superhero,
        superhero_synonym.upper(),
        superhero_synonym.title(),
        superhero_synonym,
        superhero_synonym.replace(' ', '-').upper(),
    ]
    for part in superhero_synonym.split():
        if len(part) > 2:
            names.extend([part.upper(), part.title(), part])
    return list(set(names))

def split_script_by_superhero_dialogue(script_text, superhero_names):
    pattern = r'\b(?:' + '|'.join(map(re.escape, superhero_names)) + r')\b'
    matches = list(re.finditer(pattern, script_text))
    if not matches:
        return []
    split_points = [m.start() for m in matches] + [len(script_text)]
    return [script_text[split_points[i]:split_points[i+1]] for i in range(len(split_points) - 1)]

def remove_extra_charachters_dialogue_from_each_split(extrcated_split_script_text, max_extra_dialogues=3):
    pattern = re.compile(r'^[A-Z\s\'().,-]{2,}$', re.MULTILINE)
    filtered = []
    for text_block in extrcated_split_script_text:
        matches = list(re.finditer(pattern, text_block))
        indices = [m.start() for m in matches]
        if len(indices) >= 1:
            max_idx = len(text_block) if len(indices) <= 1 else indices[:max_extra_dialogues][-1]
            filtered.append(text_block[:max_idx].strip())
        elif text_block.strip():
            filtered.append(text_block[:500].strip())
    return filtered

def combine_dialogue_with_context(script_text, filtered_dialogues, max_context_length):
    combined = []
    for dialogue in filtered_dialogues:
        if not dialogue:
            continue
        idx = script_text.find(dialogue)
        if idx != -1:
            start_ctx = max(0, idx - max_context_length)
            context = script_text[start_ctx:idx]
            combined.append(context + dialogue)
        else:
            combined.append(dialogue)
    return combined

def main():
    print(f"Preprocessing dialogues for {len(list_of_superheroes)} superheroes...")
    # Cache extracted scripts so we don't reload the same pdf multiple times
    script_cache = {}
    
    for superhero in tqdm(list_of_superheroes, desc="Characters"):
        superhero_dialogue_save_path = pjoin(data_folder_path, dialogue_folder, superhero)
        os.makedirs(superhero_dialogue_save_path, exist_ok=True)
        movies = movies_list_of_superheroes.get(superhero, [])

        for script in movies:
            save_script_name = ".".join(script.split('.')[:-1]) + '.txt'
            target_file = pjoin(superhero_dialogue_save_path, save_script_name)
            
            # If already processed, continue
            if os.path.exists(target_file) and os.path.getsize(target_file) > 100:
                continue

            script_path = pjoin(data_folder_path, script_folder, script)
            if not os.path.exists(script_path):
                print(f"Warning: Script {script_path} not found.")
                continue

            if script_path not in script_cache:
                script_cache[script_path] = extract_text(script_path)
            
            script_text = script_cache[script_path]
            superhero_names = get_all_superhero_names(superhero, superhero_synonyms)
            splits = split_script_by_superhero_dialogue(script_text, superhero_names)
            filtered = remove_extra_charachters_dialogue_from_each_split(splits)
            dialogues_with_ctx = combine_dialogue_with_context(script_text, filtered, max_context_length)
            
            if dialogues_with_ctx:
                combined_text = dialogues_joiner.join(dialogues_with_ctx)
            else:
                combined_text = ""

            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(combined_text)

    print("Preprocessing completed successfully!")

if __name__ == '__main__':
    main()
