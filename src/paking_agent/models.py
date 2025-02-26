from pydantic import BaseModel
from typing import List

class ParkingData(BaseModel):
    """ Class to handle the parking data """
    parking_name: str
    location: str
    services: List[str]
    additional_services: List[str]
    additional_information: str
    confirmation: bool
