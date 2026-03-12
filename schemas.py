from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ParticipantRecordBase(BaseModel):
    participant_name: str = Field(min_length=1)
    company: str = Field(min_length=1)
    department: str = Field(min_length=1)
    type_of_training: str = Field(min_length=1)
    training_date: date


class ParticipantRecordCreate(ParticipantRecordBase):
    pass


class ParticipantRecordRead(ParticipantRecordBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CertificateRequest(BaseModel):
    modules: list[str] = Field(default_factory=list)
