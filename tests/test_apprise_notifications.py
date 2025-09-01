import os
import sqlite3
import base64
import pytest
from scripts.utils.notifications import sendAppriseNotifications
from datetime import datetime


def create_test_db(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        sql_create_detections_table = """ CREATE TABLE IF NOT EXISTS detections (
                                        id integer PRIMARY KEY,
                                        Com_Name text NOT NULL,
                                        Date date NULL,
                                        Time time NULL
                                    ); """
        cur = conn.cursor()
        cur.execute(sql_create_detections_table)
        sql = ''' INSERT INTO detections(Com_Name, Date)
              VALUES(?,?) '''

        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")  # SQLite stores date as YYYY-MM-DD
        cur.execute(sql, ["Great Crested Flycatcher", today])
        conn.commit()

    except Exception as e:
        print(e)
    finally:
        if conn:
            conn.close()


@pytest.fixture(autouse=True)
def clean_up_after_each_test():
    yield
    if os.path.exists("test.db"):
        os.remove("test.db")
    apprise_dir = os.path.expanduser('~') + '/BirdNET-Pi'
    apprise_file = apprise_dir + '/apprise.txt'
    if os.path.exists(apprise_file):
        os.remove(apprise_file)
    if os.path.exists(apprise_dir):
        try:
            os.rmdir(apprise_dir)
        except OSError:
            pass


def test_notifications(mocker):
    notify_call = mocker.patch('scripts.utils.notifications.notify')
    create_test_db("test.db")
    apprise_dir = os.path.expanduser('~') + '/BirdNET-Pi'
    os.makedirs(apprise_dir, exist_ok=True)
    with open(apprise_dir + '/apprise.txt', 'w') as f:
        f.write('mailto://example@example.com')
    body_template = "A $comname ($sciname) was just detected with a confidence of $confidencepct ($reason)"
    settings_dict = {
        "APPRISE_NOTIFICATION_TITLE": "New backyard bird!",
        "APPRISE_NOTIFICATION_BODY": base64.b64encode(body_template.encode("utf-8")).decode("utf-8"),
        "APPRISE_NOTIFY_EACH_DETECTION": "0",
        "APPRISE_NOTIFY_NEW_SPECIES": "0",
        "APPRISE_NOTIFY_NEW_SPECIES_EACH_DAY": "0",
        "APPRISE_MINIMUM_SECONDS_BETWEEN_NOTIFICATIONS_PER_SPECIES": "0",
    }
    sendAppriseNotifications("Myiarchus crinitus_Great Crested Flycatcher",
                             "0.91",
                             "91",
                             "filename",
                             "1666-06-06",
                             "06:06:06",
                             "06",
                             "-1",
                             "-1",
                             "0.7",
                             "1.25",
                             "0.0",
                             settings_dict,
                             "test.db")

    # No active apprise notifcations configured. Confirm no notifications.
    assert (notify_call.call_count == 0)  # No notification should be sent.

    # Add daily notification.
    notify_call.reset_mock()
    settings_dict["APPRISE_NOTIFY_NEW_SPECIES_EACH_DAY"] = "1"
    sendAppriseNotifications("Myiarchus crinitus_Great Crested Flycatcher",
                             "0.91",
                             "91",
                             "filename",
                             "1666-06-06",
                             "06:06:06",
                             "06",
                             "-1",
                             "-1",
                             "0.7",
                             "1.25",
                             "0.0",
                             settings_dict,
                             "test.db")

    assert (notify_call.call_count == 1)
    assert (
        notify_call.call_args_list[0][0][0] == "A Great Crested Flycatcher (Myiarchus crinitus) was just detected with a confidence of 91 (first time today)"
    )

    # Add new species notification.
    notify_call.reset_mock()
    settings_dict["APPRISE_NOTIFY_NEW_SPECIES"] = "1"
    sendAppriseNotifications("Myiarchus crinitus_Great Crested Flycatcher",
                             "0.91",
                             "91",
                             "filename",
                             "1666-06-06",
                             "06:06:06",
                             "06",
                             "-1",
                             "-1",
                             "0.7",
                             "1.25",
                             "0.0",
                             settings_dict,
                             "test.db")

    assert (notify_call.call_count == 2)
    assert (
        notify_call.call_args_list[0][0][0] == "A Great Crested Flycatcher (Myiarchus crinitus) was just detected with a confidence of 91 (first time today)"
    )
    assert (
        notify_call.call_args_list[1][0][0] == "A Great Crested Flycatcher (Myiarchus crinitus) was just detected with a confidence of 91 (only seen 1 times in last 7d)"
    )

    # Add each species notification.
    notify_call.reset_mock()
    settings_dict["APPRISE_NOTIFY_EACH_DETECTION"] = "1"
    sendAppriseNotifications("Myiarchus crinitus_Great Crested Flycatcher",
                             "0.91",
                             "91",
                             "filename",
                             "1666-06-06",
                             "06:06:06",
                             "06",
                             "-1",
                             "-1",
                             "0.7",
                             "1.25",
                             "0.0",
                             settings_dict,
                             "test.db")

    assert (notify_call.call_count == 3)

