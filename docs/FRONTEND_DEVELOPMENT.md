# Frontend development

This page contains tips for frontend development when extending NetAlertX. Guiding principles are:

1. Maintainability
2. Extendability
3. Reusability
4. Placing more functionality into Plugins and enhancing core Plugins functionality

That means that, when writing code, focus on reusing what's available instead of writing quick fixes. Or creating reusable functions, instead of bespoke functionaility.

## 🔍 Examples

Some examples how to apply the above:

> Example 1
>
> I want to implement a scan fucntion. Options would be:
>
> 1. To add a manual scan functionality to the `deviceDetails.php` page.
> 2. To create a separate page that handles the execution of the scan.
> 3. To create a configurable Plugin.
>
> From the above, number 3 would be the most appropriate solution. Then followed by number 2. Number 1 would be approved only in special circumstances.

> Example 2
>
> I want to change the behavior of the application. Options to implement this could be:
>
> 1. Hard-code the changes in the code.
> 2. Implement the changes and add settings to influence the behavior in the `initialize.py` file so the user can adjust these.
> 3. Implement the changes and add settings via a setting-only plugin.
> 4. Implement the changes in a way so the behavior can be toggled on each plugin so the core capabilities of Plugins get extended.
>
> From the above, number 4 would be the most appropriate solution. Then followed by number 3. Number 1 or 2 would be approved only in special circumstances.

## 💡 Frontend tips

Some useful frontend JavaScript functions:

- `getDevDataByMac(macAddress, devicesColumn)` - method to retrieve any device data (database column) based on MAC address in the frontend
- `getString(string stringKey)` - method to retrieve translated strings in the frontend
- `getSetting(string stringKey)` - method to retrieve settings in the frontend


Check the [common.js](https://github.com/netalertx/NetAlertX/blob/main-2023-06-10/front/js/common.js) file for more frontend functions.