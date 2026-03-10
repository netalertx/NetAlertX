<?php
  //------------------------------------------------------------------------------
  // check if authenticated
  require_once  $_SERVER['DOCUMENT_ROOT'] . '/php/templates/security.php';
?>

<script>
  showSpinner();
</script>


<section class="content workflows col-sm-12 col-xs-12">
  <div id="workflowContainerWrap" class="bg-grey-dark color-palette  col-sm-12 col-xs-12 box-default box-info ">
    <div id="workflowContainer"></div>

  </div>
  <div id="buttons" class="bottom-buttons col-sm-12 col-xs-12">
    <div class="add-workflow col-sm-4 col-xs-12">
      <button type="button" class="btn btn-primary add-workflow-btn col-sm-12 col-xs-12" id="add">
      <i class="fa fa-fw  fa-plus"></i> <?= lang('WF_Add');?>
      </button>
    </div>
    <div class="import-wf  col-sm-4 col-xs-12">
      <button type="button" class="btn btn-primary  col-sm-12 col-xs-12" id="import">
      <i class="fa fa-fw  fa-file-import"></i> <?= lang('WF_Import');?>
      </button>
    </div>
    <div class="restart-app col-sm-4 col-xs-12">
      <button type="button" class="btn btn-primary col-sm-12 col-xs-12" id="save" onclick="askRestartBackend()">
      <i class="fa fa-fw  fa-arrow-rotate-right"></i> <?= lang('Maint_RestartServer');?>
      </button>
    </div>
    <div class="save-workflows  col-xs-12">
      <button type="button" class="btn btn-primary bg-green col-sm-12 col-xs-12" id="save" onclick="saveWorkflows()">
      <i class="fa fa-fw  fa-floppy-disk"></i> <?= lang('WF_Save');?>
      </button>
    </div>
  </div>
</section>

<script>

let workflows = [];

let fieldOptions = [
        "devName", "devMac", "devOwner", "devType", "devVendor", "devVlan", "devFavorite",
        "devGroup", "devComments", "devFirstConnection", "devLastConnection",
        "devLastIP", "devStaticIP", "devScan", "devLogEvents", "devAlertEvents",
        "devAlertDown", "devCanSleep", "devSkipRepeated", "devLastNotification", "devPresentLastScan",
        "devIsNew", "devLocation", "devIsArchived", "devParentMAC", "devParentPort",
        "devIcon", "devSite", "devSSID", "devSyncHubNode", "devSourcePlugin", "devFQDN",
        "devParentRelType", "devReqNicsOnline", "devNameSource", "devVendorSource" ,
        "devSSIDSource", "devParentMACSource" , "devParentPortSource" , "devParentRelTypeSource",
        "devVlanSource"
      ];

let triggerTypes = [
  "Devices"
];
let triggerEvents = [
  "update", "insert", "delete"
];

let wfEnabledOptions = [
  "Yes", "No"
];

let operatorTypes = [
  "equals", "contains" , "regex"
];

let actionTypes = [
  "update_field", "delete_device"
];

let emptyWorkflow = {
      "name": "New Workflow",
      "trigger": {
        "object_type": "Devices",
        "event_type": "insert"
      },
      "conditions": [
      ],
      "actions": [
      ]
    };

// --------------------------------------
// Retrieve and process the data
function getData() {

  getSetting()

  $.get('php/server/query_json.php?file=workflows.json')
  .done(function (res) {
    workflows = res;
    console.log(workflows);

    updateWorkflowsJson(workflows);
    renderWorkflows();
  })
  .fail(function (jqXHR, textStatus, errorThrown) {
    console.warn("Failed to load workflows.json:", textStatus, errorThrown);
    workflows = []; // Set a default empty array to prevent crashes
    updateWorkflowsJson(workflows);
    renderWorkflows();
  })
  .always(function () {
    hideSpinner(); // Ensure the spinner is hidden in all cases
  });
}


// --------------------------------------
// Render all workflows
function renderWorkflows() {
  let $container = $("#workflowContainer");
  $container.empty(); // Clear previous UI

  workflows = getWorkflowsJson();

  console.log("renderWorkflows");
  console.log(workflows);

  $.each(workflows, function (index, wf) {
    let $wfElement = generateWorkflowUI(wf, index);
    $container.append($wfElement);
  });
}


// --------------------------------------
// Generate UI for a single workflow
function generateWorkflowUI(wf, wfIndex) {

  let wfEnabled = (wf?.enabled ?? "No") == "Yes";

  let $wfContainer = $("<div>", {
    class: "workflow-card panel col-sm-12 col-sx-12",
    id: `wf-${wfIndex}-container`
  });

  // Workflow Name
  let $wfLinkWrap = $("<div>",
    {
      class: " ",
      id: `wf-${wfIndex}-header`
    }
  )

  let $wfEnabledIcon = $("<i>", {
      class: `alignRight fa ${wfEnabled ? "fa-dot-circle" : "fa-circle" }`
    });


  let $wfHeaderLink = $("<a>",
    {
      "class": "pointer  ",
      "data-toggle": "collapse",
      "data-parent": "#workflowContainer",
      "aria-expanded": false,
      "href" : `#wf-${wfIndex}-collapsible-panel`
    }
  )

  let $wfHeaderHeading = $("<h4>",
    {
      class: "panel-title"
    }
  ).text(wf.name)

  $wfContainer.append($wfHeaderLink.append($wfLinkWrap.append($wfHeaderHeading.append($wfEnabledIcon))));

  // Collapsible panel start

  // Get saved state from localStorage
  let panelState = localStorage.getItem(`wf-${wfIndex}-collapsible-panel`);
  let isOpen = panelState === "true"; // Convert stored string to boolean

  console.log(`panel isOpen: ${isOpen}` );


  let $wfCollapsiblePanel = $("<div>", {
    class: ` panel-collapse collapse  ${isOpen ? 'in' : ''}`,
    id: `wf-${wfIndex}-collapsible-panel`
  });

  let $wfEnabled = createEditableDropdown(
    `[${wfIndex}].enabled`,
    getString("WF_Enabled"),
    wfEnabledOptions,
    wfEnabled ? "Yes" :"No",
    `wf-${wfIndex}-enabled`
  );

  $wfCollapsiblePanel.append($wfEnabled)

  let $wfNameInput = createEditableInput(
    `[${wfIndex}].name`,
    getString("WF_Name"),
    wf.name,
    `wf-${wfIndex}-name`,
    "workflow-name-input"
  );

  $wfCollapsiblePanel.append($wfNameInput)

  let $triggersIcon = $("<i>", {
      class: "fa-solid fa-bolt"
    });

  let $triggerTitle = $("<div>",
    {
      class:"section-title"
    }
  ).append($triggersIcon).append(` ${getString("WF_Trigger")}:`)

  // Trigger Section with dropdowns
  let $triggerSection = $("<div>",
    {
      class: " col-sm-12 col-sx-12"
    }
  ).append($triggerTitle);

  let $triggerTypeDropdown = createEditableDropdown(
    `[${wfIndex}].trigger.object_type`,
    getString("WF_Trigger_type"),
    triggerTypes,
    wf.trigger.object_type,
    `wf-${wfIndex}-trigger-object-type`
  );

  let $eventTypeDropdown = createEditableDropdown(
    `[${wfIndex}].trigger.event_type`,
    getString("WF_Trigger_event_type"),
    triggerEvents,
    wf.trigger.event_type,
    `wf-${wfIndex}-trigger-event-type`
  );

  let $triggerIcon = $("<i>", {
      class: "fa-solid fa-bolt bckg-icon-2-line"
    });

  $triggerSection.append($triggerIcon);
  $triggerSection.append($triggerTypeDropdown);
  $triggerSection.append($eventTypeDropdown);

  $wfCollapsiblePanel.append($triggerSection);

  // Conditions

  let $conditionsIcon = $("<i>", {
    class: "fa-solid  fa-arrows-split-up-and-left fa-rotate-270"
  });

  let $conditionsTitle = $("<div>", {
    class: "section-title"
  }).append($conditionsIcon).append(` ${getString("WF_Conditions")}:`);

  let $conditionsContainer = $("<div>", {
    class: "col-sm-12 col-sx-12"
  }).append($conditionsTitle);


  $conditionsContainer.append(renderConditions(wfIndex, `[${wfIndex}]`, 0, wf.conditions));

  $wfCollapsiblePanel.append($conditionsContainer);

  let $actionsIcon = $("<i>", {
      class: "fa-solid fa-person-running fa-flip-horizontal"
    });

  let $actionsTitle = $("<div>",
    {
      class:"section-title"
    }
  ).append($actionsIcon).append(` ${getString("WF_Actions")}:`)

  // Actions with action.field as dropdown
  let $actionsContainer = $("<div>",
    {
      class: "actions-list col-sm-12 col-sx-12 box "
    }
  ).append($actionsTitle);

  lastActionIndex = 0
  $.each(wf.actions, function (actionIndex, action) {
    let $actionEl = $("<div>", {
      class: "col-sm-11 col-sx-12"
    });

    let $actionElWrap = $("<div>", {
      class: "panel col-sm-12 col-sx-12"
    });


    // Dropdown for action.type
    let $actionDropdown= createEditableDropdown(
      `[${wfIndex}].actions[${actionIndex}].type`,
      getString("WF_Action_type"),
      actionTypes,
      action.type,
      `wf-${wfIndex}-actionIndex-${actionIndex}-type`
    );


    $actionEl.append($actionDropdown);

    // how big should the background icon be
    let numberOfLines = 1

    if(action.type == "update_field")
    {
      numberOfLines = 3

      // Dropdown for action.field
      let $fieldDropdown = createEditableDropdown(
        `[${wfIndex}].actions[${actionIndex}].field`,
        getString("WF_Action_field"),
        fieldOptions,
        action.field,
        `wf-${wfIndex}-actionIndex-${actionIndex}-field`
      );

      // Textbox for  action.value
      let $actionValueInput = createEditableInput(
        `[${wfIndex}].actions[${actionIndex}].value`,
        getString("WF_Action_value"),
        action.value,
        `wf-${wfIndex}-actionIndex-${actionIndex}-value`,
        "action-value-input"
      );


      $actionEl.append($fieldDropdown);
      $actionEl.append($actionValueInput);

    }

    // Actions

    let $actionRemoveButtonWrap = $("<div>", { class: "button-container col-sm-1 col-sx-12" });

    let $actionRemoveIcon = $("<i>", {
      class: "fa-solid fa-trash"
    });

    let $actionRemoveButton = $("<div>", {
      class: "pointer remove-action red-hover-text",
      actionIndex: actionIndex,
      wfIndex: wfIndex
    })
    .append($actionRemoveIcon)

    $actionRemoveButtonWrap.append($actionRemoveButton);

    let $actionIcon = $("<i>", {
      class: `fa-solid  fa-person-running fa-flip-horizontal bckg-icon-${numberOfLines}-line `
    });

    $actionEl.prepend($actionIcon)

    $actionElWrap.append($actionEl)

    $actionElWrap.append($actionRemoveButtonWrap)

    $actionsContainer.append($actionElWrap);

    lastActionIndex = actionIndex
  });

  // add action button
  let $actionAddButtonWrap = $("<div>", { class: "button-container col-sm-12 col-sx-12" });
  let $actionAddIcon = $("<i>", {
      class: "fa-solid fa-plus"
    });
  let $actionAddButton = $("<div>", {
      class : "pointer add-action green-hover-text",
      lastActionIndex : lastActionIndex,
      wfIndex: wfIndex
    }).append($actionAddIcon).append(` ${getString("WF_Action_Add")}`)

  $actionAddButtonWrap.append($actionAddButton)
  $actionsContainer.append($actionAddButtonWrap)


  let $wfRemoveButtonWrap = $("<div>", { class: "button-container col-sm-4 col-sx-12" });

  let $wfRemoveIcon = $("<i>", {
    class: "fa-solid fa-trash"
  });

  let $wfRemoveButton = $("<div>", {
    class: "pointer remove-wf red-hover-text",
    wfIndex: wfIndex
  })
  .append($wfRemoveIcon) // Add icon
  .append(` ${getString("WF_Remove")}`); // Add text


  let $wfDuplicateButtonWrap = $("<div>", { class: "button-container col-sm-4 col-sx-12" });

  let $wfDuplicateIcon = $("<i>", {
    class: "fa-solid fa-copy"
  });

  let $wfDuplicateButton = $("<div>", {
    class: "pointer duplicate-wf green-hover-text",
    wfIndex: wfIndex
  })
  .append($wfDuplicateIcon) // Add icon
  .append(` ${getString("WF_Duplicate")}`); // Add text

  let $wfExportButtonWrap = $("<div>", { class: "button-container col-sm-4 col-sx-12" });

  let $wfExportIcon = $("<i>", {
    class: "fa-solid fa-file-export"
  });

  let $wfExportButton = $("<div>", {
    class: "pointer export-wf green-hover-text",
    wfIndex: wfIndex
  })
  .append($wfExportIcon) // Add icon
  .append(` ${getString("WF_Export")}`); // Add text

  $wfCollapsiblePanel.append($actionsContainer);

  $wfCollapsiblePanel.append($wfDuplicateButtonWrap.append($wfDuplicateButton))
  $wfCollapsiblePanel.append($wfExportButtonWrap.append($wfExportButton))
  $wfCollapsiblePanel.append($wfRemoveButtonWrap.append($wfRemoveButton))


  $wfContainer.append($wfCollapsiblePanel)

  return $wfContainer;
}


// --------------------------------------
// Render conditions recursively
function renderConditions(wfIndex, parentIndexPath, conditionGroupsIndex, conditions) {
  let $conditionList = $("<div>", {
    class: "condition-list panel  col-sm-12 col-sx-12",
    parentIndexPath: parentIndexPath
  });

  lastConditionIndex = 0

  let $conditionListWrap = $("<div>", {
    class: `condition-list-wrap ${conditionGroupsIndex==0?"col-sm-12":"col-sm-11"} col-sx-12`,
    conditionGroupsIndex: conditionGroupsIndex
  });

  let $deleteConditionGroupWrap = $("<div>", {
    class: "condition-group-wrap-del col-sm-1 col-sx-12"
  });

  $.each(conditions, function (conditionIndex, condition) {

    let currentPath = `${parentIndexPath}.conditions[${conditionIndex}]`;

    if (condition.logic) {
      let $nestedCondition = $("<div>",
        {
          class : "condition box  box-secondary col-sm-12 col-sx-12"
        }
      );

      let $logicDropdown = createEditableDropdown(
        `${currentPath}.logic`,
        getString("WF_Conditions_logic_rules"),
        ["AND", "OR"],
        condition.logic,
        `wf-${wfIndex}-${currentPath.replace(/\./g, "-")}-logic` // id
      );

      $nestedCondition.append($logicDropdown);

      $conditionListNested = renderConditions(wfIndex, currentPath, conditionGroupsIndex+1, condition.conditions)

      $nestedCondition.append($conditionListNested); // Recursive call for nested conditions

      $conditionList.append($nestedCondition);

    } else {
      // INDIVIDUAL CONDITIONS
      let $conditionIcon = $("<i>", {
        class: "fa-solid  fa-arrows-split-up-and-left fa-rotate-270 bckg-icon-3-line "
      });

      let $conditionItem = $("<div>",
      {
        class: "panel col-sm-12 col-sx-12",
        conditionIndex: conditionIndex,
        wfIndex: wfIndex
      });

      $conditionItem.append($conditionIcon); // Append background icon

      let $conditionItemsWrap = $("<div>",
      {
        class: "conditionItemsWrap col-sm-11 col-sx-12"
      });

      // Create dropdown for condition field
      let $fieldDropdown = createEditableDropdown(
        `${currentPath}.field`,
        getString("WF_Condition_field"),
        fieldOptions,
        condition.field,
        `wf-${wfIndex}-${currentPath.replace(/\./g, "-")}-field`
      );

      // Create dropdown for operator
      let $operatorDropdown = createEditableDropdown(
        `${currentPath}.operator`,
        getString("WF_Condition_operator"),
        operatorTypes,
        condition.operator,
        `wf-${wfIndex}-${currentPath.replace(/\./g, "-")}-operator`
      );

      // Editable input for condition value
      let $editableInput = createEditableInput(
          `${currentPath}.value`,
          getString("WF_Condition_value"),
          condition.value,
          `wf-${wfIndex}-${currentPath.replace(/\./g, "-")}-value`,
          "condition-value-input"
       );


      $conditionItemsWrap.append($fieldDropdown); // Append field dropdown
      $conditionItemsWrap.append($operatorDropdown); // Append operator dropdown
      $conditionItemsWrap.append($editableInput); // Append editable input for condition value

      let $conditionRemoveButtonWrap = $("<div>", { class: "button-container col-sm-1 col-sx-12" });
      let $conditionRemoveButtonIcon = $("<i>", {
        class: "fa-solid fa-trash"
      });
      let $conditionRemoveButton = $("<div>", {
        class : "pointer remove-condition red-hover-text",
        conditionIndex : conditionIndex,
        wfIndex: wfIndex,
        parentIndexPath: parentIndexPath
      }).append($conditionRemoveButtonIcon)

      $conditionRemoveButtonWrap .append($conditionRemoveButton);
      $conditionItem.append($conditionItemsWrap);
      $conditionItem.append($conditionRemoveButtonWrap);

      $conditionList.append($conditionItem);
    }

    lastConditionIndex = conditionIndex
  });

  let $addButtonWrap = $("<div>", {
    class: "add-button-wrap col-sm-12 col-sx-12"
  });

  if (conditionGroupsIndex != 0) {
    // Add Condition button
    let $conditionAddWrap = $("<div>", { class: "button-container col-sm-6 col-sx-12" });
    let $conditionAddIcon = $("<i>", {
      class: "fa-solid fa-plus"
    });
    let $conditionAddButton = $("<div>", {
      class: "pointer add-condition green-hover-text col-sx-12",
      wfIndex: wfIndex,
      parentIndexPath: parentIndexPath
    }).append($conditionAddIcon).append(` ${getString("WF_Add_Condition")}`);
    $conditionAddWrap.append($conditionAddButton);

    // Remove Condition Group button
    let $conditionGroupRemoveWrap = $("<div>", { class: "button-container col-sx-12" });
    let $conditionGroupRemoveIcon = $("<i>", {
      class: "fa-solid fa-trash"
    });
    let $conditionGroupRemoveButton = $("<div>", {
      class: "pointer remove-condition-group red-hover-text col-sx-12",
      lastConditionIndex: lastConditionIndex,
      wfIndex: wfIndex,
      parentIndexPath: parentIndexPath
    }).append($conditionGroupRemoveIcon);
    $conditionGroupRemoveWrap.append($conditionGroupRemoveButton);

    $addButtonWrap.append($conditionAddWrap);
    $deleteConditionGroupWrap.append($conditionGroupRemoveWrap);

  }

  // Add Condition Group button
  let $conditionsGroupAddWrap = $("<div>", { class: "button-container col-sm-6 col-sx-12" });
  let $conditionsGroupAddIcon = $("<i>", {
      class: "fa-solid fa-plus"
    });
  let $conditionsGroupAddButton = $("<div>", {
    class: "pointer add-condition-group green-hover-text col-sx-12",
    wfIndex: wfIndex,
    parentIndexPath: parentIndexPath
  }).append($conditionsGroupAddIcon).append(` ${getString("WF_Add_Group")}`);
  $conditionsGroupAddWrap.append($conditionsGroupAddButton);

  $addButtonWrap.append($conditionsGroupAddWrap);
  $conditionList.append($addButtonWrap);

  $conditionListWrap.append($conditionList)


  let $res = $("<div>", {
    class: "condition-list-res col-sm-12 col-sx-12"
  });

  $res.append($conditionListWrap)
  $res.append($deleteConditionGroupWrap)

  return $res;
}


// --------------------------------------
// Render SELECT Dropdown with Predefined Values
function createEditableDropdown(jsonPath, labelText, options, selectedValue, id) {

  let $wrapper = $("<div>", {
    class: "form-group col-sm-12 col-sx-12"
  });

  let $label = $("<label>", {
    for: id,
    class: "col-sm-4 col-xs-12 control-label "
  }).text(labelText);

  // Create select wrapper
  let $selectWrapper = $("<div>", {
    class: "col-sm-8 col-xs-12"
  });

  // Create select element
  let $select = $("<select>", {
    id: id,
    jsonPath: jsonPath,
    class: "form-control col-sm-8 col-xs-12"
  });


  // Add options to the select dropdown
  $.each(options, function (_, option) {
    let $option = $("<option>", { value: option }).text(option);
    if (option === selectedValue) {
      $option.attr("selected", "selected"); // Set the default selection
    }
    $select.append($option);
  });

  // Trigger onSave when the selection changes
  $select.on("change", function() {
    let newValue = $select.val();
    console.log(`Selected new value: ${newValue}`);
    console.log(`Selected new jsonPath: ${$select.attr("jsonPath")}`);

    updateWorkflowObject(newValue, $select.attr("jsonPath")); // Call the onSave callback with the new value

  });

  $wrapper.append($label);
  $wrapper.append($selectWrapper.append($select));
  return $wrapper;
}

// --------------------------------------
// Render INPUT HTML element
function createEditableInput(jsonPath, labelText, value, id, className = "") {

  // prepare wrapper
  $wrapper = $("<div>", {
    class: "form-group col-sm-12 col-xs-12"
  });

  let $label = $("<label>", {
    for: id,
    class: "col-sm-4 col-xs-12 control-label "
  }).text(labelText);

  // Create input wrapper
  let $inputWrapper = $("<div>", {
    class: "col-sm-8 col-xs-12"
  });

  // console.log(jsonPath);

  let $input = $("<input>", {
    type: "text",
    jsonPath: jsonPath,
    id: id,
    value: value,
    class: className + " col-sm-8 col-xs-12 form-control "
  });

  // Optional: Add a change event listener to update the workflow name
  $input.on("change", function () {
    let newValue = $input.val();
    console.log(`Value changed to: ${newValue}`);
  });

  // Trigger onSave when the user presses Enter or the input loses focus
  $input.on("blur keyup", function (e) {
    if (e.type === "blur" || e.key === "Enter") {
      let newValue = $input.val();
      console.log(`Selected new value: ${newValue}`);

      updateWorkflowObject(newValue, $input.attr("jsonPath")); // Call the onSave callback with the new value
    }
  });

  $wrapper.append($label)
  $wrapper.append($inputWrapper.append($input))
  return $wrapper;
}

// --------------------------------------
// Updating the in-memory workflow object
function updateWorkflowObject(newValue, jsonPath) {
  // Load workflows from cache if available
  let workflows = getWorkflowsJson()

  console.log("Initial workflows:", workflows);

  workflows = updateJsonByPath(workflows, jsonPath, newValue)

  console.log("Updated workflows:", workflows);

  updateWorkflowsJson(workflows)

  renderWorkflows();
}


/**
 * Updates the given JSON structure at the location specified by a JSON path.
 * @param {object|array} json - The JSON object or array to update.
 * @param {string} path - The JSON path string, e.g. "[1].conditions[0].conditions[2].conditions[0].field".
 * @param {*} newValue - The new value to set at the given path.
 * @returns {object|array} - The updated JSON.
 */
function updateJsonByPath(json, path, newValue) {
  const tokens = parsePath(path);
  recursiveUpdate(json, tokens, newValue);
  return json;
}

/**
 * Recursively traverses the JSON structure to update the property defined by tokens.
 * @param {object|array} current - The current JSON object or array.
 * @param {Array<string|number>} tokens - An array of tokens representing the path.
 * @param {*} newValue - The value to set at the target location.
 */
function recursiveUpdate(current, tokens, newValue) {
  // When only one token is left, update that property/element with newValue.
  if (tokens.length === 1) {
    const key = tokens[0];
    current[key] = newValue;
    return;
  }

  const token = tokens[0];

  // If the next level does not exist, optionally create it.
  if (current[token] === undefined) {
    // Determine if the next token is an array index or a property.
    current[token] = typeof tokens[1] === 'number' ? [] : {};
  }

  // Recursively update the next level.
  recursiveUpdate(current[token], tokens.slice(1), newValue);
}

/**
 * Parses a JSON path string into an array of tokens.
 * For example, "[1].conditions[0].conditions[2].conditions[0].field" becomes:
 * [1, "conditions", 0, "conditions", 2, "conditions", 0, "field"]
 * @param {string} path - The JSON path string.
 * @returns {Array<string|number>} - An array of tokens.
 */
function parsePath(path) {
  const tokens = [];
  const regex = /(\w+)|\[(\d+)\]/g;
  let match;
  while ((match = regex.exec(path)) !== null) {
    if (match[1]) {
      tokens.push(match[1]);
    } else if (match[2]) {
      tokens.push(Number(match[2]));
    }
  }
  return tokens;
}



// ---------------------------------------------------
// Buttons functionality
// ---------------------------------------------------

// ---------------------------------------------------
// Function to add a new Workflow
function addWorkflow(workflows) {
  workflows.push(getEmptyWorkflowJson());

  updateWorkflowsJson(workflows)

  // Re-render the UI
  renderWorkflows();
}

// ---------------------------------------------------
// Function to remove a Workflow
function removeWorkflow(workflows, wfIndex) {

  showModalWarning ('<?= lang('WF_Remove');?>', '<?= lang('WF_Remove_Copy');?>',
            '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Delete');?>', `executeRemoveWorkflow`, wfIndex);
}

// ---------------------------------------------------
// Function to execute the remove of a Workflow
function executeRemoveWorkflow() {

  workflows = getWorkflowsJson()

  workflows.splice($('#modal-warning').attr("data-myparam-triggered-by"), 1);

  updateWorkflowsJson(workflows)

  // Re-render the UI
  renderWorkflows();
}

// ---------------------------------------------------
// Function to duplicate a Workflow
function duplicateWorkflow(workflows, wfIndex) {

  workflows.push(workflows[wfIndex])

  updateWorkflowsJson(workflows)

  // Re-render the UI
  renderWorkflows();
}

// ---------------------------------------------------
// Function to export a Workflow
function exportWorkflow(workflows, wfIndex) {

// Add new icon as base64 string
showModalInput ('<i class="fa  fa-file-export pointer"></i> <?= lang('WF_Export');?>', '<?= lang('WF_Export_Copy');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', null, null,  JSON.stringify(workflows[wfIndex], null, 2));
}

// ---------------------------------------------------
// Function to import a Workflow
function importWorkflow(workflows, wfIndex) {

// Add new icon as base64 string
showModalInput ('<i class="fa  fa-file-import pointer"></i> <?= lang('WF_Import');?>', '<?= lang('WF_Import_Copy');?>',
    '<?= lang('Gen_Cancel');?>', '<?= lang('Gen_Okay');?>', 'importWorkflowExecute', null, "" );

}

function importWorkflowExecute()
{
  var json = JSON.parse($('#modal-input-textarea').val());

  workflows = getWorkflowsJson()

  workflows.push(json);

  updateWorkflowsJson(workflows)

  // Re-render the UI
  renderWorkflows();
}

// ---------------------------------------------------
// Function to add a new condition
function addCondition(workflows, wfIndex, parentIndexPath) {
    if (!parentIndexPath) return;

    workflows = getWorkflowsJson()

    // Navigate to the target nested object
    let target = getNestedObject(workflows, parentIndexPath);

    console.log("Target:", target);

    if (!target || !target.conditions) {
        console.error("❌ Invalid path or conditions array missing:", parentIndexPath);
        return;
    }

    // Add a new condition to the conditions array
    target.conditions.push({
        field: fieldOptions[0], // First option from field dropdown
        operator: operatorTypes[0], // First operator
        value: "" // Default empty value
    });

    // Ensure the workflows object is updated in memory
    workflows[wfIndex] = { ...workflows[wfIndex] };

    updateWorkflowsJson(workflows)

    // Re-render the UI
    renderWorkflows();
}

// ---------------------------------------------------
// Function to add a new condition group
function addConditionGroup(workflows, wfIndex, parentIndexPath) {
    if (!parentIndexPath) return;

    // Navigate to the target nested object
    let target = getNestedObject(workflows, parentIndexPath);

    console.log("Target:", target);

    if (!target || !target.conditions) {
        console.error("❌ Invalid path or conditions array missing:", parentIndexPath);
        return;
    }

    // Add a new condition group to the conditions array
    target.conditions.push({
        logic: "AND",
        conditions: []
    });

    // Ensure the workflows object is updated in memory
    workflows[wfIndex] = { ...workflows[wfIndex] };

    updateWorkflowsJson(workflows)

    // Re-render the UI
    renderWorkflows();
}

// ---------------------------------------------------
// Function to add a new action
function addAction(workflows, wfIndex) {
    let newAction = {
        type: actionTypes[0],
        field: fieldOptions[0],
        value: ""
    };
    workflows[wfIndex].actions.push(newAction);

    updateWorkflowsJson(workflows)

    renderWorkflows();
}

function removeCondition(workflows, wfIndex, parentIndexPath, conditionIndex) {
    if (!parentIndexPath || conditionIndex === undefined) return;

    // Navigate to the target nested object
    let target = getNestedObject(workflows, parentIndexPath);

    console.log("Target before removal:", target);

    if (!target || !Array.isArray(target.conditions)) {
        console.error("❌ Invalid path or conditions array missing:", parentIndexPath);
        return;
    }

    // Remove the specified condition
    target.conditions.splice(conditionIndex, 1);

    // Ensure the workflows object is updated in memory
    workflows[wfIndex] = { ...workflows[wfIndex] };

    updateWorkflowsJson(workflows)

    // Re-render the UI
    renderWorkflows();
}

function removeAction(workflows, wfIndex, actionIndex) {
    if (!actionIndex || actionIndex === undefined) return;

    // Navigate to the target nested object
    let target = getNestedObject(workflows, wfIndex);

    console.log("Target before removal:", target);

    if (!target || !Array.isArray(target.actions)) {
        console.error("❌ Invalid path or conditions array missing:", actionIndex);
        return;
    }

    console.log(actionIndex);

    // Remove the specified condition
    target.actions.splice(actionIndex, 1);

    // Ensure the workflows object is updated in memory
    workflows[wfIndex] = { ...workflows[wfIndex] };

    updateWorkflowsJson(workflows)

    // Re-render the UI
    renderWorkflows();
}

function removeConditionGroup(workflows, wfIndex, parentIndexPath) {
    if (!parentIndexPath) return;

    // Split the path by dots
    const parts = parentIndexPath.split('.');

    // Extract the last part (index)
    const lastIndex = parts.pop().replace(/\D/g, '');  // Remove any non-numeric characters

    // Rebuild the path without the last part
    const newPath = parts.join('.');

    console.log(parentIndexPath);
    console.log(newPath);

    // Navigate to the target nested object
    let target = getNestedObject(workflows, newPath);

    console.log("Target before removal:", target);

    if (!target || !Array.isArray(target.conditions)) {
        console.error("❌ Invalid path or conditions array missing:", parentIndexPath);
        return;
    }

    // Remove the specified condition group
    delete target.conditions.splice(lastIndex, 1);

    // Ensure the workflows object is updated in memory
    workflows[wfIndex] = { ...workflows[wfIndex] };

    updateWorkflowsJson(workflows)

    // Re-render the UI
    renderWorkflows();
}


// ---------------------------------------------------
// Helper function to navigate to a nested object using the provided path
function getNestedObject(obj, path) {
    // console.log("🔍 Getting nested object:", { obj, path });

    // Convert bracket notation to dot notation (e.g., '[1].conditions[0]' → '1.conditions.0')
    const keys = path.replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean);

    return keys.reduce((o, key, index) => {
        if (o && o[key] !== undefined) {
            // console.log(`✅ Found: ${keys.slice(0, index + 1).join('.')} ->`, o[key]);
            return o[key];
        } else {
            console.warn(`❌ Failed at: ${keys.slice(0, index + 1).join('.')}`);
            console.warn("🔍 Tried getting nested object:", { obj, path });
            return null;
        }
    }, obj);
}

// ---------------------------------------------------
// Get workflows JSON
function getWorkflowsJson()
{
  return workflows = JSON.parse(getCache('workflows')) || getEmptyWorkflowJson();
}

// ---------------------------------------------------
// Get workflows JSON
function updateWorkflowsJson(workflows)
{
    // Store the updated workflows object back into cache
    setCache('workflows', JSON.stringify(workflows));
}

// ---------------------------------------------------
// Get empty workflow JSON
function getEmptyWorkflowJson()
{
  return emptyWorkflow;
}

// ---------------------------------------------------
// Save workflows JSON
function saveWorkflows()
{
  // encode for import
  appConfBase64 = btoa(JSON.stringify(getWorkflowsJson()))

  // import
  $.post('php/server/query_replace_config.php', { base64data: appConfBase64, fileName: "workflows.json" }, function(msg) {
    console.log(msg);
    // showMessage(msg);
    write_notification(`[WF]: ${msg}`, 'interrupt');
  });
}

// ---------------------------------------------------
// Event listeners
$(document).on("click", ".add-workflow-btn", function () {
  addWorkflow(getWorkflowsJson());
});

$(document).on("click", ".remove-wf", function () {
  let wfIndex = $(this).attr("wfindex");
  removeWorkflow(getWorkflowsJson(), wfIndex);
});

$(document).on("click", ".duplicate-wf", function () {
  let wfIndex = $(this).attr("wfindex");
  duplicateWorkflow(getWorkflowsJson(), wfIndex);
});

$(document).on("click", ".export-wf", function () {
  let wfIndex = $(this).attr("wfindex");
  exportWorkflow(getWorkflowsJson(), wfIndex);
});

$(document).on("click", ".import-wf", function () {
  let wfIndex = $(this).attr("wfindex");
  importWorkflow(getWorkflowsJson(), wfIndex);
});

$(document).on("click", ".add-condition", function () {
    let wfIndex = $(this).attr("wfindex");
    let parentIndexPath = $(this).attr("parentIndexPath");
    addCondition(getWorkflowsJson(), wfIndex, parentIndexPath);
});

$(document).on("click", ".add-condition-group", function () {
    let wfIndex = $(this).attr("wfindex");
    let parentIndexPath = $(this).attr("parentIndexPath");
    addConditionGroup(getWorkflowsJson(), wfIndex, parentIndexPath);
});

$(document).on("click", ".add-action", function () {
    let wfIndex = $(this).attr("wfIndex");
    addAction(getWorkflowsJson(), wfIndex);
});

// Event Listeners for Removing Conditions
$(document).on("click", ".remove-condition", function () {
    let wfIndex = $(this).attr("wfindex");
    let parentIndexPath = $(this).attr("parentIndexPath");
    let conditionIndex = parseInt($(this).attr("conditionIndex"), 10);

    removeCondition(getWorkflowsJson(), wfIndex, parentIndexPath, conditionIndex);
});

// Event Listeners for Removing Actions
$(document).on("click", ".remove-action", function () {
    let wfIndex = $(this).attr("wfindex");
    let actionIndex = $(this).attr("actionIndex");

    removeAction(getWorkflowsJson(), wfIndex, actionIndex);
});

// Event Listeners for Removing Condition Groups
$(document).on("click", ".remove-condition-group", function () {
    let wfIndex = $(this).attr("wfindex");
    let parentIndexPath = $(this).attr("parentIndexPath");
    removeConditionGroup(getWorkflowsJson(), wfIndex, parentIndexPath);
});

// ---------------------------------------------------
// Handling open/closed state of collapsible panels
$(document).ready(function() {
    $(".panel-collapse").each(function() {
        let panelId = $(this).attr("id");
        let isOpen = localStorage.getItem(panelId) === "true";

        if (isOpen) {
            $(this).addClass("in");
        }
    });

    $(document).on("shown.bs.collapse", ".panel-collapse", function() {
    localStorage.setItem($(this).attr("id"), "true");
        console.log("Panel opened:", $(this).attr("id"));
    });

    $(document).on("hidden.bs.collapse", ".panel-collapse", function() {
        localStorage.setItem($(this).attr("id"), "false");
        console.log("Panel closed:", $(this).attr("id"));
    });
});

// --------------------------------------
// Initialize
$(document).ready(function () {
  getData();
});


</script>