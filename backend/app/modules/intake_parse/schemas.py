from pydantic import BaseModel


class IngestRequest(BaseModel):
    content: str = ""
