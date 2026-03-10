<?php

// ###################################
// ## Languages
// ## Look-up here: http://www.lingoes.net/en/translator/langcode.htm
// ###################################

$defaultLang = "en_us";

// Load the canonical language list from languages.json — do not hardcode here.
$_langJsonPath = dirname(__FILE__) . '/language_definitions/languages.json';
$_langJson     = json_decode(file_get_contents($_langJsonPath), true);
$allLanguages  = array_column($_langJson['languages'], 'code');

global $db;

$result = $db->querySingle("SELECT setValue FROM Settings WHERE setKey = 'UI_LANG'");

// Extract the language code from the display value, e.g. "English (en_us)" => "en_us".
// This regex means lang.php never needs updating when a new language is added.
preg_match('/\(([a-z]{2}_[a-z]{2})\)\s*$/i', (string) $result, $_langMatch);
$pia_lang_selected = isset($_langMatch[1]) ? strtolower($_langMatch[1]) : $defaultLang;

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


