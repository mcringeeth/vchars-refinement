from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from refiner.models.refined import Base
import sqlite3
import os
import logging

class DataTransformer(ABC):
    """
    Base class for transforming JSON data into SQLAlchemy models.
    Users should extend this class and override the transform method
    to customize the transformation process for their specific data.
    """
    
    def __init__(self, db_path: str):
        """Initialize the transformer with a database path."""
        self.db_path = db_path
    
    def process(self, data: Dict[str, Any], session: Optional[Session] = None) -> None:
        """
        Processes the raw data and stores it in the database.
        Manages the DB session and transaction.
        If an external session is provided, it will be used directly.
        """
        manage_session = session is None

        if manage_session:
            if self.db_path == ":memory:":
                engine = create_engine("sqlite:///:memory:")
            else:
                engine = create_engine(f"sqlite:///{self.db_path}")

            Base.metadata.create_all(engine)
            Session = sessionmaker(bind=engine)
            session = Session()

        try:
            self.transform(data, session)
            if manage_session:
                session.commit()
        except Exception as e:
            if manage_session:
                session.rollback()
            raise e
        finally:
            if manage_session:
                session.close()
    
    @abstractmethod
    def transform(self, data: Dict[str, Any], session: Session) -> None:
        """
        The core transformation logic to be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement transform method")
    
    def get_schema(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all table definitions in order
        schema = []
        for table in cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' ORDER BY name"):
            schema.append(table[0] + ";")
        
        conn.close()
        return "\n\n".join(schema)