## Am I running the latest released version?

Since version 23.01.14 NetAlertX uses a simple timestamp-based version check to verify if a new version is available. You can check the [current and past releases here](https://github.com/netalertx/NetAlertX/releases), or have a look at what I'm [currently working on](https://github.com/netalertx/NetAlertX/issues/138).

If you are not on the latest version, the app will notify you, that a new released version is avialable the following way:

### 📧 Via email on a notification event

If any notification occurs and an email is sent, the email will contain a note that a new version is available. See the sample email below:

![Sample email if a new version is available](./img/VERSIONS/new-version-available-email.png)

### 🆕 In the UI

In the UI via a notification Icon and via a custom message in the Maintenance section.

![UI screenshot if a new version is available](./img/VERSIONS/new-version-available-maintenance.png)

For a comparison, this is how the UI looks like if you are on the latest stable image:

![UI screenshot if on latest version](./img/VERSIONS/latest-version-maintenance.png)

## Implementation details

During build a [/app/front/buildtimestamp.txt](https://github.com/netalertx/NetAlertX/blob/092797e75ccfa8359444ad149e727358ac4da05f/Dockerfile#L44) file is created. The app then periodically checks if a new release is available with a newer timestamp in GitHub's rest-based JSON endpoint (check the `def isNewVersion:` method for details).