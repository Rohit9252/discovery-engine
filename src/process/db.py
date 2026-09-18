from sqlalchemy import create_engine, Column, String, Text, DateTime, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

Base = declarative_base()

class ReviewMetadata(Base):
    """
    SQLAlchemy ORM model for storing cleaned metadata of the reviews.
    This acts as the relational backbone before we embed text into ChromaDB.
    """
    __tablename__ = 'reviews_metadata'

    id = Column(String, primary_key=True) # Unique ID from the source platform
    source = Column(String, nullable=False) # e.g., 'play_store', 'reddit'
    text = Column(Text, nullable=False) # The actual review text
    author = Column(String) 
    created_at = Column(DateTime)
    rating = Column(Float)
    url = Column(String)
    
    def __repr__(self):
        return f"<Review(id='{self.id}', source='{self.source}')>"

def get_engine(db_path="data/processed/reviews.db"):
    """Create and return an SQLAlchemy engine."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")
    return engine

def init_db(engine):
    """Initialize the database schema."""
    logging.info("Initializing SQLite database schema...")
    Base.metadata.create_all(engine)
    logging.info("Database initialized.")

def get_session(engine):
    """Return an SQLAlchemy session."""
    Session = sessionmaker(bind=engine)
    return Session()

if __name__ == "__main__":
    engine = get_engine()
    init_db(engine)
