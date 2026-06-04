#!/usr/bin/env python3
import subprocess
import os


def run_sqlite_command(command):
    # Use environment variable with fallback
    db_path = os.path.join(
        os.getenv('NETALERTX_DB', '/data/db'),
        'app.db'
    )
    full_command = f"sudo docker exec -i netalertx sqlite3 {db_path} \"{command}\""
    try:
        result = subprocess.run(full_command, shell=True, text=True, capture_output=True)
        if result.stderr:
            print(f"Error: {result.stderr}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        return None


def check_and_clean_device():
    while True:
        print("\nDevice Cleanup Tool")
        print("1. Check/Clean by MAC address")
        print("2. Check/Clean by IP address")
        print("3. Exit")

        choice = input("\nSelect option (1-3): ")

        if choice == "1":
            mac = input("Enter MAC address (format: xx:xx:xx:xx:xx:xx): ").lower()

            # Check all tables for MAC
            tables_checks = [
                f"SELECT 'Events' as source, * FROM Events WHERE eveMac='{mac}'",
                f"SELECT 'Devices' as source, * FROM Devices WHERE devMac='{mac}'",
                f"SELECT 'CurrentScan' as source, * FROM CurrentScan WHERE scanMac='{mac}'",
                f"SELECT 'Notifications' as source, * FROM Notifications WHERE JSON LIKE '%{mac}%'",
                f"SELECT 'AppEvents' as source, * FROM AppEvents WHERE objectPrimaryId LIKE '%{mac}%' OR objectSecondaryId LIKE '%{mac}%'",
                f"SELECT 'Plugins_Objects' as source, * FROM Plugins_Objects WHERE objectPrimaryId LIKE '%{mac}%'"
            ]

            found = False
            for check in tables_checks:
                result = run_sqlite_command(check)
                if result and result.strip():
                    found = True
                    print(f"\nFound entries:\n{result}")

            if found:
                confirm = input("\nWould you like to clean these entries? (y/n): ")
                if confirm.lower() == 'y':
                    # Delete from all tables
                    deletes = [
                        f"DELETE FROM Events WHERE eveMac='{mac}'",
                        f"DELETE FROM Devices WHERE devMac='{mac}'",
                        f"DELETE FROM CurrentScan WHERE scanMac='{mac}'",
                        f"DELETE FROM Notifications WHERE JSON LIKE '%{mac}%'",
                        f"DELETE FROM AppEvents WHERE objectPrimaryId LIKE '%{mac}%' OR objectSecondaryId LIKE '%{mac}%'",
                        f"DELETE FROM Plugins_Objects WHERE objectPrimaryId LIKE '%{mac}%'"
                    ]

                    for delete in deletes:
                        run_sqlite_command(delete)
                    print("Cleanup completed!")
            else:
                print("\nNo entries found for this MAC address")

        elif choice == "2":
            ip = input("Enter IP address (format: xxx.xxx.xxx.xxx): ")

            # Check all tables for IP
            tables_checks = [
                f"SELECT 'Events' as source, * FROM Events WHERE eveIp='{ip}'",
                f"SELECT 'Devices' as source, * FROM Devices WHERE devLastIp='{ip}'",
                f"SELECT 'CurrentScan' as source, * FROM CurrentScan WHERE scanLastIP='{ip}'",
                f"SELECT 'Notifications' as source, * FROM Notifications WHERE JSON LIKE '%{ip}%'",
                f"SELECT 'AppEvents' as source, * FROM AppEvents WHERE objectSecondaryId LIKE '%{ip}%'",
                f"SELECT 'Plugins_Objects' as source, * FROM Plugins_Objects WHERE objectSecondaryId LIKE '%{ip}%'"
            ]

            found = False
            for check in tables_checks:
                result = run_sqlite_command(check)
                if result and result.strip():
                    found = True
                    print(f"\nFound entries:\n{result}")

            if found:
                confirm = input("\nWould you like to clean these entries? (y/n): ")
                if confirm.lower() == 'y':
                    # Delete from all tables
                    deletes = [
                        f"DELETE FROM Events WHERE eveIp='{ip}'",
                        f"DELETE FROM Devices WHERE devLastIp='{ip}'",
                        f"DELETE FROM CurrentScan WHERE scanLastIP='{ip}'",
                        f"DELETE FROM Notifications WHERE JSON LIKE '%{ip}%'",
                        f"DELETE FROM AppEvents WHERE objectSecondaryId LIKE '%{ip}%'",
                        f"DELETE FROM Plugins_Objects WHERE objectSecondaryId LIKE '%{ip}%'"
                    ]

                    for delete in deletes:
                        run_sqlite_command(delete)
                    print("Cleanup completed!")
            else:
                print("\nNo entries found for this IP address")

        elif choice == "3":
            print("\nExiting...")
            break

        else:
            print("\nInvalid option, please try again")


if __name__ == "__main__":
    check_and_clean_device()
