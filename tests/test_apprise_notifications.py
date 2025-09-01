import os
import base64
import pytest
from scripts.utils.notifications import sendAppriseNotifications


@pytest.fixture(autouse=True)
def clean_up_after_each_test():
    yield
    apprise_path = os.path.expanduser('~/BirdNET-Pi/apprise.txt')
    if os.path.exists(apprise_path):
        os.remove(apprise_path)


def test_notifications(mocker):
    notify_call = mocker.patch('scripts.utils.notifications.notify')
    apprise_path = os.path.expanduser('~/BirdNET-Pi/apprise.txt')
    os.makedirs(os.path.dirname(apprise_path), exist_ok=True)
    with open(apprise_path, 'w') as fh:
        fh.write('test')
    settings_dict = {
        "APPRISE_NOTIFICATION_TITLE": "New backyard bird!",
        "APPRISE_NOTIFICATION_BODY": base64.b64encode(
            "A $comname ($sciname) was just detected with a confidence of $confidence".encode("utf-8")
        ).decode("utf-8"),
        "APPRISE_NOTIFY_EACH_DETECTION": "1",
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

    assert notify_call.call_count == 1

