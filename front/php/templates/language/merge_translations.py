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


if __name__ == "__main__":
    current_path = os.path.dirname(os.path.abspath(__file__))
    # language codes can be found here: http://www.lingoes.net/en/translator/langcode.htm
    # ⚠ "en_us.json" has to be first!
    json_files =    ["en_us.json", "ar_ar.json", "ca_ca.json", "cs_cz.json", "de_de.json",
                     "es_es.json", "fa_fa.json", "fr_fr.json", "it_it.json", "ja_jp.json",
                     "nb_no.json", "pl_pl.json", "pt_br.json", "pt_pt.json", "ru_ru.json",
                     "sv_sv.json", "tr_tr.json", "vi_vn.json", "uk_ua.json", "zh_cn.json"]
    file_paths = [os.path.join(current_path, file) for file in json_files]
    merge_translations(file_paths[0], file_paths[1:])
