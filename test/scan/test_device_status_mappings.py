import pytest
from pydantic import ValidationError

from server.api_server.openapi.schemas import DeviceListRequest
from server.db.db_helper import get_device_condition_by_status


def test_device_list_request_accepts_offline():
    req = DeviceListRequest(status="offline")
    assert req.status == "offline"


def test_get_device_condition_by_status_offline():
    cond = get_device_condition_by_status("offline")
    assert "devPresentLastScan=0" in cond and "devIsArchived=0" in cond


def test_device_list_request_rejects_unknown_status():
    with pytest.raises(ValidationError):
        DeviceListRequest(status="my_devices")
