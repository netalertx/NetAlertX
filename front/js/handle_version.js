//--------------------------------------------------------------
// Handle the UI changes to show or hide notifications about a new version
function versionUpdateUI(){

  isNewVersion = getCookie("isNewVersion")

  // console.log(isNewVersion)

  // if the release_timestamp is older by 10 min or more as the build timestamp then there is a new release available 
  if(isNewVersion != "false")
  {
    console.log("New release!")
    // handling the navigation menu icon
    $('#version').attr("class", $('#version').attr("class").replace("myhidden", ""))

    maintenanceDiv = $('#new-version-text')
  }
  else{
    console.log("All up-to-date!")    

    maintenanceDiv = $('#current-version-text')  
  }

  // handling the maintenance section message
  if(emptyArr.includes(maintenanceDiv) == false && $(maintenanceDiv).length != 0)
  {
    $(maintenanceDiv).attr("class", $(maintenanceDiv).attr("class").replace("myhidden", ""))
  }

  updateNavPendingDot();

}

//--------------------------------------------------------------
// Checks if a new version is available via the global app_state.json
function checkIfNewVersionAvailable()
{
  $.get('php/server/query_json.php', { file: 'app_state.json', nocache: Date.now() }, function(appState) {   
    
    // console.log(appState["isNewVersionChecked"])
    // console.log(appState["isNewVersion"])
    
    // cache value
    setCookie("isNewVersion", appState["isNewVersion"], 30);
    setCookie("isNewVersionChecked", appState["isNewVersionChecked"], 30);

    versionUpdateUI();

  })
}

// handle the dispaly of the NEW icon
checkIfNewVersionAvailable()
