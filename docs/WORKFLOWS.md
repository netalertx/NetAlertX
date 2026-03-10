# Workflows Overview

The workflows module in allows to automate repetitive tasks, making network management more efficient. Whether you need to assign newly discovered devices to a specific Network Node, auto-group devices from a given vendor, unarchive a device if detected online, or automatically delete devices, this module provides the flexibility to tailor the automations to your needs.

![Workflows diagram](./img/WORKFLOWS/workflows_diagram.png)

Below are a few examples that demonstrate how this module can be used to simplify network management tasks.

## Updating Workflows

> [!NOTE]
> In order to apply a workflow change, you must first **Save** the changes and then reload the application by clicking **Restart server**.

## Workflow components

### Triggers

![Trigger example](./img/WORKFLOWS/trigger.jpg)

Triggers define the event that activates a workflow. They monitor changes to objects within the system, such as updates to devices or the insertion of new entries. When the specified event occurs, the workflow is executed.

> [!TIP]
> Workflows not running? Check the [Workflows debugging](./WORKFLOWS_DEBUGGING.md) guide how to troubleshoot triggers and conditions.

#### Example Trigger:
- **Object Type**: `Devices`
- **Event Type**: `update`

This trigger will activate when a `Device` object is updated.

### Conditions

![Conditions example](./img/WORKFLOWS/conditions.png)

Conditions determine whether a workflow should proceed based on certain criteria. These criteria can be set for specific fields, such as whether a device is from a certain vendor, or whether it is new or archived. You can combine conditions using logical operators (`AND`, `OR`).

> [!TIP]
> To better understand how to use specific Device fields, please read through the [Database overview](./DATABASE.md) guide.

#### Example Condition:
- **Logic**: `AND`
  - **Field**: `devVendor`
  - **Operator**: `contains` (case in-sensitive)
  - **Value**: `Google`

  This condition checks if the device's vendor is `Google`. The workflow will only proceed if the condition is true.

### Actions

![Actions example](./img/WORKFLOWS/actions.jpg)

Actions define the tasks that the workflow will perform once the conditions are met. Actions can include updating fields or deleting devices.

You can include multiple actions that should execute once the conditions are met.

#### Example Action:
- **Action Type**: `update_field`
  - **Field**: `devIsNew`
  - **Value**: `0`

  This action updates the `devIsNew` field to `0`, marking the device as no longer new.


# Examples

You can find a couple of configuration examples in [Workflow Examples](WORKFLOW_EXAMPLES.md).


> [!TIP]
> Share your workflows in [Discord](https://discord.com/invite/NczTUTWyRr) or [GitHub Discussions](https://github.com/netalertx/NetAlertX/discussions).
