CREATE TABLE Events (eveMac STRING (50) NOT NULL COLLATE NOCASE, eveIp STRING (50) NOT NULL COLLATE NOCASE, eveDateTime DATETIME NOT NULL, eveEventType STRING (30) NOT NULL COLLATE NOCASE, eveAdditionalInfo STRING (250) DEFAULT (''), evePendingAlertEmail BOOLEAN NOT NULL CHECK (evePendingAlertEmail IN (0, 1)) DEFAULT (1), evePairEventRowid INTEGER);
CREATE TABLE Sessions (sesMac STRING (50) COLLATE NOCASE, sesIp STRING (50) COLLATE NOCASE, sesEventTypeConnection STRING (30) COLLATE NOCASE, sesDateTimeConnection DATETIME, sesEventTypeDisconnection STRING (30) COLLATE NOCASE, sesDateTimeDisconnection DATETIME, sesStillConnected BOOLEAN, sesAdditionalInfo STRING (250));
CREATE TABLE IF NOT EXISTS Online_History (
            "index"     INTEGER,
            scanDate TEXT,
            onlineDevices    INTEGER,
            downDevices      INTEGER,
            allDevices       INTEGER,
            archivedDevices INTEGER,
            offlineDevices INTEGER,
            PRIMARY KEY("index" AUTOINCREMENT)
          );
CREATE TABLE Devices (
              devMac STRING (50) PRIMARY KEY NOT NULL COLLATE NOCASE,
              devName STRING (50) NOT NULL DEFAULT "(unknown)",
              devOwner STRING (30) DEFAULT "(unknown)" NOT NULL,
              devType STRING (30),
              devVendor STRING (250),
              devFavorite BOOLEAN CHECK (devFavorite IN (0, 1)) DEFAULT (0) NOT NULL,
              devGroup STRING (10),
              devComments TEXT,
              devFirstConnection DATETIME NOT NULL,
              devLastConnection DATETIME NOT NULL,
              devLastIP STRING (50) NOT NULL COLLATE NOCASE,
              devPrimaryIPv4 TEXT,
              devPrimaryIPv6 TEXT,
              devVlan TEXT,
              devForceStatus TEXT,
              devStaticIP BOOLEAN DEFAULT (0) NOT NULL CHECK (devStaticIP IN (0, 1)),
              devScan INTEGER DEFAULT (1) NOT NULL,
              devLogEvents BOOLEAN NOT NULL DEFAULT (1) CHECK (devLogEvents IN (0, 1)),
              devAlertEvents BOOLEAN NOT NULL DEFAULT (1) CHECK (devAlertEvents IN (0, 1)),
              devAlertDown BOOLEAN NOT NULL DEFAULT (0) CHECK (devAlertDown IN (0, 1)),
              devSkipRepeated INTEGER DEFAULT 0 NOT NULL,
              devLastNotification DATETIME,
              devPresentLastScan BOOLEAN NOT NULL DEFAULT (0) CHECK (devPresentLastScan IN (0, 1)),
              devIsNew BOOLEAN NOT NULL DEFAULT (1) CHECK (devIsNew IN (0, 1)),
              devLocation STRING (250) COLLATE NOCASE,
              devIsArchived BOOLEAN NOT NULL DEFAULT (0) CHECK (devIsArchived IN (0, 1)),
              devParentMAC TEXT,
              devParentPort INTEGER,
              devParentRelType TEXT,
              devIcon TEXT,
              devGUID TEXT,
              devSite TEXT,
              devSSID TEXT,
              devSyncHubNode TEXT,
              devSourcePlugin TEXT,
              devFQDN TEXT,
              devMacSource TEXT,
              devNameSource TEXT,
              devFQDNSource TEXT,
              devLastIPSource TEXT,
              devVendorSource TEXT,
              devSSIDSource TEXT,
              devParentMACSource TEXT,
              devParentPortSource TEXT,
              devParentRelTypeSource TEXT,
              devVlanSource TEXT,
              devCustomProps TEXT);
CREATE TABLE IF NOT EXISTS Settings (
            setKey            TEXT,
            setName           TEXT,
            setDescription    TEXT,
            setType         TEXT,
            setOptions      TEXT,
            setGroup            TEXT,
            setValue        TEXT,
            setEvents         TEXT,
            setOverriddenByEnv INTEGER
            );
CREATE TABLE IF NOT EXISTS Parameters (
            parID TEXT PRIMARY KEY,
            parValue TEXT
          );
CREATE TABLE Plugins_Objects(
                                    "index"               INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        );
CREATE TABLE Plugins_Events(
                                    "index"               INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        );
CREATE TABLE Plugins_History(
                                    "index"               INTEGER,
                                    plugin TEXT NOT NULL,
                                    objectPrimaryId TEXT NOT NULL,
                                    objectSecondaryId TEXT NOT NULL,
                                    dateTimeCreated TEXT NOT NULL,
                                    dateTimeChanged TEXT NOT NULL,
                                    watchedValue1 TEXT NOT NULL,
                                    watchedValue2 TEXT NOT NULL,
                                    watchedValue3 TEXT NOT NULL,
                                    watchedValue4 TEXT NOT NULL,
                                    "status" TEXT NOT NULL,
                                    extra TEXT NOT NULL,
                                    userData TEXT NOT NULL,
                                    foreignKey TEXT NOT NULL,
                                    syncHubNodeName TEXT,
                                    helpVal1 TEXT,
                                    helpVal2 TEXT,
                                    helpVal3 TEXT,
                                    helpVal4 TEXT,
                                    objectGuid TEXT,
                                    PRIMARY KEY("index" AUTOINCREMENT)
                        );
CREATE TABLE Plugins_Language_Strings(
                                "index"           INTEGER,
                                languageCode TEXT NOT NULL,
                                stringKey TEXT NOT NULL,
                                stringValue TEXT NOT NULL,
                                extra TEXT NOT NULL,
                                PRIMARY KEY("index" AUTOINCREMENT)
                        );
CREATE TABLE CurrentScan (
                                scanMac STRING(50) NOT NULL COLLATE NOCASE,
                                scanLastIP STRING(50) NOT NULL COLLATE NOCASE,
                                scanVendor STRING(250),
                                scanSourcePlugin STRING(10),
                                scanName STRING(250),
                                scanLastQuery STRING(250),
                                scanLastConnection STRING(250),
                                scanSyncHubNode STRING(50),
                                scanSite STRING(250),
                                scanSSID STRING(250),
                                scanVlan STRING(250),
                                scanParentMAC STRING(250),
                                scanParentPort STRING(250),
                                scanType STRING(250),
                                UNIQUE(scanMac)
                            );
CREATE TABLE IF NOT EXISTS AppEvents (
                "index" INTEGER PRIMARY KEY AUTOINCREMENT,
                guid TEXT UNIQUE,
                appEventProcessed BOOLEAN,
                dateTimeCreated TEXT,
                objectType TEXT,
                objectGuid TEXT,
                objectPlugin TEXT,
                objectPrimaryId TEXT,
                objectSecondaryId TEXT,
                objectForeignKey TEXT,
                objectIndex TEXT,
                objectIsNew BOOLEAN,
                objectIsArchived BOOLEAN,
                objectStatusColumn TEXT,
                objectStatus TEXT,
                appEventType TEXT,
                helper1 TEXT,
                helper2 TEXT,
                helper3 TEXT,
                extra TEXT
            );
CREATE TABLE IF NOT EXISTS Notifications (
            "index"           INTEGER,
            guid            TEXT UNIQUE,
            dateTimeCreated TEXT,
            dateTimePushed  TEXT,
            "status"          TEXT,
            "json"            TEXT,
            "text"            TEXT,
            html            TEXT,
            publishedVia    TEXT,
            extra           TEXT,
            PRIMARY KEY("index" AUTOINCREMENT)
        );
CREATE INDEX IDX_eve_DateTime ON Events (eveDateTime);
CREATE INDEX IDX_eve_EventType ON Events (eveEventType COLLATE NOCASE);
CREATE INDEX IDX_eve_MAC ON Events (eveMac COLLATE NOCASE);
CREATE INDEX IDX_eve_PairEventRowid ON Events (evePairEventRowid);
CREATE INDEX IDX_ses_EventTypeDisconnection ON Sessions (sesEventTypeDisconnection COLLATE NOCASE);
CREATE INDEX IDX_ses_EventTypeConnection ON Sessions (sesEventTypeConnection COLLATE NOCASE);
CREATE INDEX IDX_ses_DateTimeDisconnection ON Sessions (sesDateTimeDisconnection);
CREATE INDEX IDX_ses_MAC ON Sessions (sesMac COLLATE NOCASE);
CREATE INDEX IDX_ses_DateTimeConnection ON Sessions (sesDateTimeConnection);
CREATE INDEX IDX_dev_PresentLastScan ON Devices (devPresentLastScan);
CREATE INDEX IDX_dev_FirstConnection ON Devices (devFirstConnection);
CREATE INDEX IDX_dev_AlertDeviceDown ON Devices (devAlertDown);
CREATE INDEX IDX_dev_StaticIP ON Devices (devStaticIP);
CREATE INDEX IDX_dev_ScanCycle ON Devices (devScan);
CREATE INDEX IDX_dev_Favorite ON Devices (devFavorite);
CREATE INDEX IDX_dev_LastIP ON Devices (devLastIP);
CREATE INDEX IDX_dev_NewDevice ON Devices (devIsNew);
CREATE INDEX IDX_dev_Archived ON Devices (devIsArchived);
CREATE UNIQUE INDEX IF NOT EXISTS idx_events_unique
ON Events (
    eveMac,
    eveIp,
    eveEventType,
    eveDateTime
);
CREATE VIEW Events_Devices AS
                            SELECT *
                            FROM Events
                            LEFT JOIN Devices ON eveMac = devMac;
CREATE VIEW LatestEventsPerMAC AS
                                WITH RankedEvents AS (
                                    SELECT
                                        e.*,
                                        ROW_NUMBER() OVER (PARTITION BY e.eveMac ORDER BY e.eveDateTime DESC) AS row_num
                                    FROM Events AS e
                                )
                                SELECT
                                    e.*,
                                    d.*,
                                    c.*
                                FROM RankedEvents AS e
                                LEFT JOIN Devices AS d ON e.eveMac = d.devMac
                                INNER JOIN CurrentScan AS c ON e.eveMac = c.scanMac
                                WHERE e.row_num = 1;
CREATE VIEW Sessions_Devices AS SELECT * FROM Sessions LEFT JOIN Devices ON sesMac = devMac;
CREATE VIEW Convert_Events_to_Sessions AS  SELECT EVE1.eveMac,
                                      EVE1.eveIp,
                                      EVE1.eveEventType AS eveEventTypeConnection,
                                      EVE1.eveDateTime AS eveDateTimeConnection,
                                      CASE WHEN EVE2.eveEventType IN ('Disconnected', 'Device Down') OR
                                                EVE2.eveEventType IS NULL THEN EVE2.eveEventType ELSE '<missing event>' END AS eveEventTypeDisconnection,
                                      CASE WHEN EVE2.eveEventType IN ('Disconnected', 'Device Down') THEN EVE2.eveDateTime ELSE NULL END AS eveDateTimeDisconnection,
                                      CASE WHEN EVE2.eveEventType IS NULL THEN 1 ELSE 0 END AS eveStillConnected,
                                      EVE1.eveAdditionalInfo
                                  FROM Events AS EVE1
                                      LEFT JOIN
                                      Events AS EVE2 ON EVE1.evePairEventRowid = EVE2.RowID
                                WHERE EVE1.eveEventType IN ('New Device', 'Connected','Down Reconnected')
                            UNION
                                SELECT eveMac,
                                      eveIp,
                                      '<missing event>' AS eveEventTypeConnection,
                                      NULL AS eveDateTimeConnection,
                                      eveEventType AS eveEventTypeDisconnection,
                                      eveDateTime AS eveDateTimeDisconnection,
                                      0 AS eveStillConnected,
                                      eveAdditionalInfo
                                  FROM Events AS EVE1
                                WHERE (eveEventType = 'Device Down' OR
                                        eveEventType = 'Disconnected') AND
                                      EVE1.evePairEventRowid IS NULL;
