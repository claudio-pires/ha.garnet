"""API Placeholder."""

from dataclasses import dataclass
from enum import StrEnum
import logging
from random import choice, randrange
import socket
import threading

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


class SIAData:
    def __init__(self, data: bytearray) -> None:
        """Initialise."""



        self.valid: bool = False
        self.token: str = ""
        self.sequence: str = ""
        self.receiver: str = ""
        self.prefix: str = ""
        self.account: str = ""
        self.mdata: str = ""
        self.timestamp: str = ""
        self.qualifier: int = 0
        self.eventcode: int = 0
        self.partition: int = 0
        self.zone: int = 0

        if (
            data[:1].decode("utf-8") == "\n"
        ):  # Si el paquete no comienza con /n se descarta
            self.ExpectedCRC = int.from_bytes(
                data[1:3], byteorder="big", signed=False
            )  # Se separa el CRC del paquete

            self.l = int(
                data[4:7].decode("utf-8"), 16
            )  # Se obtiene el largo del bloque de datos
            self.DataBlock = data[7 : self.l + 7]  # Se obtiene el bloque de datos

            if (
                self.crc16(self.DataBlock) == self.ExpectedCRC
            ):  # Calcula CRC del bloque de datos y lo compara con el recibido
                self.valid = True  # Si llega aca el paquete ya es valido

                self.message_str = self.DataBlock.decode()

                #                _LOGGER.debug("Message is " + self.message_str)

                self.n = self.message_str.find('"', 1) + 1
                self.token = self.message_str[: self.n].replace('"', "")

                self.message_str = self.message_str[self.n :]
                self.n = self.message_str.find("R")
                self.sequence = self.message_str[: self.n]

                self.message_str = self.message_str[self.n :]

                self.n = self.message_str.find("L")
                self.receiver = self.message_str[: self.n]

                self.message_str = self.message_str[self.n :]

                self.n = self.message_str.find("#")
                self.prefix = self.message_str[: self.n]

                self.message_str = self.message_str[self.n :]

                self.n = self.message_str.find("[")
                self.account = self.message_str[: self.n]

                self.message_str = self.message_str[self.n :]

                self.n = self.message_str.find("_")
                self.mdata = self.message_str[: self.n]

                self.timestamp = self.message_str[self.n + 1 :]

    def crc16(self, data: bytearray):
        if data is None:
            return 0
        crcx = 0x0000
        for i in range(len(data)):
            crcx ^= data[i]
            for j in range(8):
                crcx = ((crcx >> 1) ^ 0xA001) if ((crcx & 0x0001) > 0) else (crcx >> 1)
        return crcx

    def replyMessage(self):
        replymessage = (
            '"ACK"' + self.sequence + self.receiver + self.prefix + self.account + "[]"
        )
        replyCRC = self.crc16(bytearray(replymessage.encode()))
        return (
            "\n"
            + format(replyCRC, "#04x")
            + "0"
            + str(len(replymessage))
            + replymessage
            + "\r"
        )

    def parseADMCID(self):
        if self.mdata.find("][") > 1:
            (_messagedata, self.optionalExtendedData) = self.mdata.split("][")
        else:
            _messagedata = self.mdata
            self.optionalExtendedData = None
        if self.optionalExtendedData is not None:
            self.optionalExtendedData = self.optionalExtendedData.replace(
                "]", ""
            ).replace("[", "")
        _messagedata = _messagedata.replace("]", "").replace("[", "")
        if _messagedata.find("|") > 1:
            (_acc, _d) = _messagedata.split("|")
        else:
            _acc = None
            _d = _messagedata
        (_a, _b, _c) = _d.split(" ")

        self.qualifier = int(_a[0], 10)
        self.eventcode = int(_a[1:], 10)
        self.partition = int(_b, 10)
        self.zone = int(_c, 10)

    def toString(self):
        _LOGGER.info(
            "Token: "
            + self.token
            + ", Sequence: "
            + self.sequence
            + ", Receiver: "
            + self.receiver
            + ", Account prefix: "
            + self.prefix
            + ", Account: "
            + self.account
            + ", Timestamp: "
            + self.timestamp
        )


class API:
    """Class for example API."""

    def __init__(self, client: str, zones: str) -> None:
        """Initialise."""
        _LOGGER.error("**** Initialise")
        self.client = client
        self.zones = zones
        self.bufferSize = 1024
        self.account = "#1031"
        self.connected: bool = False

    def task(self):
        _LOGGER.debug("**** Ejecutando la tarea de conexion al socket")
        if(False):
        # TODO: si ya esta conectado no debe reconectar
            UDPServerSocket = socket.socket(
                family=socket.AF_INET, type=socket.SOCK_DGRAM
            )  # Create a datagram UDP socket
            UDPServerSocket.bind(("", int(self.port)))  # Bind to address and ip
            while True:
                (datagram, senderAddr) = UDPServerSocket.recvfrom(
                    self.bufferSize
                )  # Listen for incoming datagrams
                data = SIAData(bytearray(datagram))
                if data.valid:  # Valid packet
                    UDPServerSocket.sendto(str.encode(data.replyMessage()), senderAddr)
                    if data.account == self.account:
                        if data.token != "ADM-CID":
                            _LOGGER.info("KeepAlive...")
                        else:
                            data.parseADMCID()
                            if data.eventcode == 602:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se activa test periodico (eventcode: "
                                        + str(data.eventcode)
                                        + ")"
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se desactiva test periodico (eventcode: "
                                        + str(data.eventcode)
                                        + ")"
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa test periodico (eventcode: "
                                        + str(data.eventcode)
                                        + ")"
                                    )
                            elif data.eventcode == 570:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se activa BYPASS de zona(eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y zona: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se desactiva BYPASS de zona(eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y zona: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de BYPASS de zona(eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y zona: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 574:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se activa BYPASS de GRUPO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se desactiva BYPASS de GRUPO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de BYPASS de GRUPO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                    )
                            elif data.eventcode == 441:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se desactiva ARMADO PRESENTE(eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se activa ARMADO PRESENTE (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de ARMADO PRESENTE (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 407:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se desactiva ARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se activa ARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de ARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 406:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se desactiva ARMADO ALARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se activa ARMADO ALARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de ARMADO ALARMADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 401:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se desactiva ARMADO usando TECLADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se activa ARMADO usando TECLADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de ARMADO usando TECLADO (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 130:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se dispara ZONA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se recupera ZONA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de disparo de ZONA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            elif data.eventcode == 459:
                                if data.qualifier == 1:
                                    _LOGGER.info(
                                        "Se dispara ALARMA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                elif data.qualifier == 3:
                                    _LOGGER.info(
                                        "Se recupera ALARMA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                                else:
                                    _LOGGER.info(
                                        "Se informa condicion de disparo de ALARMA (eventcode: "
                                        + str(data.eventcode)
                                        + ") de la particion: "
                                        + str(data.partition)
                                        + " y usuario: "
                                        + str(data.zone)
                                    )
                            else:
                                _LOGGER.error(
                                    "El panel esta notificando eventcode: "
                                    + str(data.eventcode)
                                    + ", qualifier: "
                                    + str(data.qualifier)
                                    + ", particion: "
                                    + str(data.partition)
                                    + ", zona: "
                                    + str(data.zone)
                                    + " con optionalExtendedData: "
                                    + data.optionalExtendedData
                                )
                    else:
                        _LOGGER.info(
                            "LLEGO UN MENSAJE QUE NO CORRESPONDE A LA CUENTA DEL USUARIO"
                        )
                        data.toString()
                else:
                    _LOGGER.error("Paquete invalido")

    @property
    def controller_name(self) -> str:
        """Return the name of the controller."""
        return self.client.replace(".", "_")

    def connect(self) -> bool:
        """Connect to api."""
        self.connected = True
        return True
#        if self.client == "2023" and self.zones == "6":
#            self.connected = True
#            thread = threading.Thread(target=self.task, args=())
#            thread.start()
#            return True
#        raise APIConnectionError("Monitoring socket Instantiation Error.")

    def disconnect(self) -> bool:
        """Disconnect from api."""
        self.connected = False
        return True

    def get_devices(self) -> list[Device]:
        """Get devices on api TODO: estudiar."""
        _LOGGER.error("Running get_devices." + self.zones)
        return [
            Device(
                device_id=device,
                device_unique_id=self.get_device_unique_id(
                    device, DeviceType.TAMPER
                ),
                device_type=DeviceType.TAMPER,
                name=self.get_device_name(device, DeviceType.TAMPER),
                state=self.get_device_value(device, DeviceType.TAMPER),
            )
            for device in range(1, int(self.zones) + 1)
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
