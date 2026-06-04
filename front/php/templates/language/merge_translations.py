import json
import os


def merge_translations(main_file, other_files):
    # Load main file
    with open(main_file, 'r', encoding='utf-8') as f:
        main_data = json.load(f)

    # Get keys and sort them alphabetically
    keys = sorted(main_data.keys())

    # Sort the keys alphabetically in the main file
    main_data = {k: main_data[k] for k in keys}

    # Rewrite sorted main file
    with open(main_file, 'w', encoding='utf-8') as f:
        json.dump(main_data, f, indent=4, ensure_ascii=False)

    # Merge keys into other files
    for file_name in other_files:
        with open(file_name, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            for key in keys:
                if key not in data:
                    data[key] = ""
            # Sort the keys alphabetically for each language
            data = {k: data[k] for k in sorted(data.keys())}
            f.seek(0)
            json.dump(data, f, indent=4, ensure_ascii=False)
            f.truncate()


def load_language_codes(languages_json_path):
    """Read language codes from languages.json, guaranteeing en_us is first."""
    with open(languages_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    codes = [entry["code"] for entry in data["languages"]]
    # Ensure en_us (the master) is always first
    if "en_us" in codes:
        codes.remove("en_us")
        codes.insert(0, "en_us")
    return codes



# Languages
# Look-up here: http://www.lingoes.net/en/translator/langcode.htm
if __name__ == "__main__":
    current_path = os.path.dirname(os.path.abspath(__file__))
    # language codes are loaded from languages.json — add a new language there
    languages_json = os.path.join(current_path, "language_definitions/languages.json")
    codes = load_language_codes(languages_json)
    file_paths = [os.path.join(current_path, f"{code}.json") for code in codes]
    merge_translations(file_paths[0], file_paths[1:])
