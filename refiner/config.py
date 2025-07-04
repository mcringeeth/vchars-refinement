from pydantic import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    """Global settings configuration using environment variables"""
    
    INPUT_DIR: str = Field(
        default="/input",
        description="Directory containing input files to process"
    )
    
    OUTPUT_DIR: str = Field(
        default="/output",
        description="Directory where output files will be written"
    )
    
    REFINEMENT_ENCRYPTION_KEY: str = Field(
        default=None,
        description="Key to symmetrically encrypt the refinement. This is derived from the original file encryption key"
    )

    HASH_SALT: str = Field(
        default=None,
        description="Hash salt for the PII data"
    )

    SCHEMA_NAME: str = Field(
        default="vChars Chats",
        description="Name of the schema"
    )
    
    SCHEMA_VERSION: str = Field(
        default="0.0.1",
        description="Version of the schema"
    )
    
    SCHEMA_DESCRIPTION: str = Field(
        default="Schema for Telegram and AI chats from vChars DataDAO",
        description="Description of the schema"
    )
    
    SCHEMA_DIALECT: str = Field(
        default="sqlite",
        description="Dialect of the schema"
    )
    
    # Optional, required if using https://pinata.cloud (IPFS pinning service)
    PINATA_API_KEY: Optional[str] = Field(
        default=None,
        description="Pinata API key"
    )
    
    PINATA_API_SECRET: Optional[str] = Field(
        default=None,
        description="Pinata API secret"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings() 