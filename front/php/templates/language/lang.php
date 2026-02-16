<?php

// ###################################
// ## Languages
// ###################################

$defaultLang = "en_us";
$allLanguages = [ "ar_ar", "ca_ca", "cs_cz", "de_de",
                  "en_us", "es_es", "fa_fa", "fr_fr",
                  "it_it", "ja_jp", "nb_no", "pl_pl",
                  "pt_br", "pt_pt", "ru_ru", "sv_sv",
                  "tr_tr", "uk_ua", "vi_vn", "zh_cn"];


global $db;

$result = $db->querySingle("SELECT setValue FROM Settings WHERE setKey = 'UI_LANG'");

// below has to match exactly the values in /front/php/templates/language/lang.php & /front/js/common.js
switch($result){
    case 'Arabic (ar_ar)': $pia_lang_selected = 'ar_ar'; break;
    case 'Catalan (ca_ca)': $pia_lang_selected = 'ca_ca'; break;
    case 'Czech (cs_cz)': $pia_lang_selected = 'cs_cz'; break;
    case 'German (de_de)': $pia_lang_selected = 'de_de'; break;
    case 'English (en_us)': $pia_lang_selected = 'en_us'; break;
    case 'Spanish (es_es)': $pia_lang_selected = 'es_es'; break;
    case 'Farsi (fa_fa)': $pia_lang_selected = 'fa_fa'; break;
    case 'French (fr_fr)': $pia_lang_selected = 'fr_fr'; break;
    case 'Italian (it_it)': $pia_lang_selected = 'it_it'; break;
    case 'Japanese (ja_jp)': $pia_lang_selected = 'ja_jp'; break;
    case 'Norwegian (nb_no)': $pia_lang_selected = 'nb_no'; break;
    case 'Polish (pl_pl)': $pia_lang_selected = 'pl_pl'; break;
    case 'Portuguese (pt_br)': $pia_lang_selected = 'pt_br'; break;
    case 'Portuguese (pt_pt)': $pia_lang_selected = 'pt_pt'; break;
    case 'Russian (ru_ru)': $pia_lang_selected = 'ru_ru'; break;
    case 'Swedish (sv_sv)': $pia_lang_selected = 'sv_sv'; break;
    case 'Turkish (tr_tr)': $pia_lang_selected = 'tr_tr'; break;
    case 'Ukrainian (uk_ua)': $pia_lang_selected = 'uk_ua'; break;
    case 'Vietnamese (vi_vn)': $pia_lang_selected = 'vi_vn'; break;
    case 'Chinese (zh_cn)': $pia_lang_selected = 'zh_cn'; break;
    default: $pia_lang_selected = 'en_us'; break;
}

if (isset($pia_lang_selected) == FALSE or (strlen($pia_lang_selected) == 0)) {$pia_lang_selected = $defaultLang;}

$result = $db->query("SELECT * FROM Plugins_Language_Strings");
$strings = array();
while ($row = $result->fetchArray(SQLITE3_ASSOC)) {
    $strings[$row['String_Key']] = $row['String_Value'];
}


function getLanguageDataFromJson()
{
    global $allLanguages;

    // Array to hold the language data from the JSON files
    $languageData = [];

    foreach ($allLanguages as $language) {
        // Load and parse the JSON data from .json files
        $jsonFilePath = dirname(__FILE__) . '/' . $language . '.json';

        if (file_exists($jsonFilePath)) {
            $data = json_decode(file_get_contents($jsonFilePath), true);

            // Adjusting for the changed JSON format
            $languageData[$language] = $data;
        } else {
            // Handle the case where the JSON file doesn't exist
            // For example, you might want to log an error message
            echo 'File not found: ' . $jsonFilePath;
        }
    }

    return $languageData;
}

// Merge the JSON data with the SQL data, giving priority to SQL data for overlapping keys
function mergeLanguageData($jsonLanguageData, $sqlLanguageData)
{
    // Loop through the JSON language data and check for overlapping keys
    foreach ($jsonLanguageData as $languageCode => $languageStrings) {
        foreach ($languageStrings as $key => $value) {
            // Check if the key exists in the SQL data, if yes, use the SQL value
            if (isset($sqlLanguageData[$key])) {
                $jsonLanguageData[$languageCode][$key] = $sqlLanguageData[$key];
            }
        }
    }

    return $jsonLanguageData;
}

function lang($key)
{
    global $pia_lang_selected, $strings;

    // Get the data from JSON files
    $languageData = getLanguageDataFromJson();

    // Get the data from SQL query
    $sqlLanguageData = $strings;

    // Merge JSON data with SQL data
    $mergedLanguageData = mergeLanguageData($languageData, $sqlLanguageData);

    // Check if the key exists in the selected language
    if (isset($mergedLanguageData[$pia_lang_selected][$key]) && $mergedLanguageData[$pia_lang_selected][$key] != '') {
        $result = $mergedLanguageData[$pia_lang_selected][$key];
    } else {
        // If key not found in selected language, use "en_us" as fallback
        if (isset($mergedLanguageData['en_us'][$key])) {
            $result = $mergedLanguageData['en_us'][$key];
        } else {
            // If key not found in "en_us" either, use a default string
            $result = "String Not found for key " . $key;
        }
    }

    // HTML encode the result before returning
    return str_replace("'", '&#39;', $result);
}


