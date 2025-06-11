from typing import Optional
from pydantic import BaseModel, Field

from refiner.models.offchain_schema import OffChainSchema

class Output(BaseModel):
    refinement_url: Optional[str] = None
    offchain_schema: Optional[OffChainSchema] = Field(default=None, alias="schema")

    class Config:
        allow_population_by_field_name = True