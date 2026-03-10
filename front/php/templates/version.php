<?php
#---------------------------------------------------------------------------------#
#  NetAlertX                                                                       #
#  Open Source Network Guard / WIFI & LAN intrusion detector                      #
#                                                                                 #
#  version.php - Templates module Template to display the current version         #
#---------------------------------------------------------------------------------#
#    Puche      2021        pi.alert.application@gmail.com   GNU GPLv3            #
#    jokob-sk   2022        jokob.sk@gmail.com               GNU GPLv3            #
#    leiweibau  2022        https://github.com/leiweibau     GNU GPLv3            #
#    cvc90      2023        https://github.com/cvc90         GNU GPLv3            #
#---------------------------------------------------------------------------------#

$filename = "/app/.VERSION";

if(file_exists($filename)) {
    $fileContents = file_get_contents($filename);
    if(trim($fileContents) === 'Dev') {
        echo date('H:i:s') . " - " . $fileContents;
    } else {
        echo trim($fileContents);
    }
}
else {
    echo date('H:i:s') . " - N/A";
}

?>
