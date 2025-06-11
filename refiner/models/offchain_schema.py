from pydantic import BaseModel, Field

class OffChainSchema(BaseModel):
    name: str
    version: str
    description: str
    dialect: str
    schema_data: str = Field(alias="schema")

    class Config:
        allow_population_by_field_name = True