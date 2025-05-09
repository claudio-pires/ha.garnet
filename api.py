"""API Placeholder."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from random import choice, randrange

from .garnetapi import GarnetAPI

_LOGGER = logging.getLogger(__name__)


class DeviceType(StrEnum):
    """Device types."""

    TEMP_SENSOR = "temp_sensor"
    TAMPER = "tamper_sensor"
    OTHER = "other"

@dataclass
class Device:
    """API device."""
    device_id: int
    device_unique_id: str
    device_type: DeviceType
    name: str
    state: int | bool


class API:
    """Class for example API."""


    def __init__(self, user: str, passw: str, account: str) -> None:
        """Initialise."""
        _LOGGER.info("**** Initialise")
        self.user = user
        self.passw = passw
        self.account = account
        self.connected: bool = False

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.account.replace(".", "_")

    def connect(self) -> bool:
        """Connect to api."""
        try:
            self.api = GarnetAPI(email = self.user, password = self.passw, client = self.account)
            self.connected = True
            return True
        except Exception as err:
            raise APIConnectionError(err)
            return False


    def disconnect(self) -> bool:
        """Disconnect from api."""
        self.api.finalize
        self.connected = False
        return True


    def get_devices(self) -> list[Device]:
        """Get devices from garnet api."""
        return [
            Device(
                device_id=device.id,
                device_unique_id=self.get_device_unique_id(
                    device.id, DeviceType.TAMPER
                ),
                device_type=DeviceType.TAMPER,
                name=device.name,
                state=self.get_device_value(device, DeviceType.TAMPER),
            )
            for device in self.api.get_enabled_zones()
        ]

    def get_device_unique_id(self, device_id: str, device_type: DeviceType) -> str:
        """Return a unique device id."""
        if device_type == DeviceType.TAMPER:
            return f"{self.controller_name}_D{device_id}"
        if device_type == DeviceType.TEMP_SENSOR:
            return f"{self.controller_name}_T{device_id}"
        return f"{self.controller_name}_Z{device_id}"

    def get_device_name(self, device_id: str, device_type: DeviceType) -> str:
        """Return the device name."""
        if device_type == DeviceType.TAMPER:
            return f"DoorSensor{device_id}"
        if device_type == DeviceType.TEMP_SENSOR:
            return f"TempSensor{device_id}"
        return f"OtherSensor{device_id}"

    def get_device_value(self, device_id: str, device_type: DeviceType) -> int | bool:
        """Get device random value."""
        #TODO: Devolver el valor de la zona
        if device_type == DeviceType.TAMPER:
            return choice([True, False])
        if device_type == DeviceType.TEMP_SENSOR:
            return randrange(15, 28)
        return randrange(1, 10)


class APIAuthError(Exception):
    """Exception class for auth error."""


class APIConnectionError(Exception):
    """Exception class for connection error."""
