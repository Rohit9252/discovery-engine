from sqlalchemy import create_engine, Column, String, Text, DateTime, Float, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from pathlib import Path
from src.process.paths import REVIEW_DATABASE
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


class ReviewExclusion(Base):
    """Reversible source-context exclusions; original feedback remains intact."""
    __tablename__ = 'review_exclusions'
    review_id = Column(String, primary_key=True)
    reason = Column(String, nullable=False)


class CsvImportLedger(Base):
    """Provenance and screening decision for each positive-label CSV source row."""
    __tablename__ = 'csv_import_ledger'
    row_id = Column(String, primary_key=True)
    source_file = Column(String, nullable=False)
    source = Column(String, nullable=False)
    url = Column(String, nullable=False)
    original_content = Column(Text, nullable=False)
    manual_relevance = Column(String, nullable=False)
    manual_category = Column(String, nullable=False)
    item_type = Column(String, nullable=False)
    disposition = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    review_id = Column(String, index=True)
    imported_at = Column(String, nullable=False)


class Phase1CatalogRow(Base):
    """One CSV row, including reports, summaries, and generated scenarios."""
    __tablename__ = 'phase1_catalog_rows'
    id = Column(String, primary_key=True)
    row_number = Column(Integer, nullable=False)
    source_file = Column(String, nullable=False)
    source_type = Column(String, nullable=False)
    source = Column(String, nullable=False)
    url = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    raw_json = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False)
    active = Column(Integer, nullable=False, default=1)
    imported_at = Column(String, nullable=False)


class Phase1CatalogAssessment(Base):
    """Versioned AI result for any row in the full Phase 1 catalog."""
    __tablename__ = 'phase1_catalog_assessments'
    row_id = Column(String, primary_key=True)
    version = Column(String, primary_key=True)
    content_hash = Column(String, nullable=False)
    status = Column(String, nullable=False)
    model = Column(String, nullable=False)
    result_json = Column(Text)
    error = Column(String)
    updated_at = Column(DateTime, nullable=False)


class ResearchAnalysis(Base):
    """Current versioned AI assessment, separate from preserved source feedback."""
    __tablename__ = 'research_analysis'
    review_id = Column(String, primary_key=True)
    version = Column(String, primary_key=True)
    source_hash = Column(String, nullable=False)
    status = Column(String, nullable=False)
    model = Column(String, nullable=False)
    result_json = Column(Text)
    error = Column(String)
    updated_at = Column(DateTime, nullable=False)


class IssueAnalysis(Base):
    """Versioned Part One issue decision, independent of broad research labels."""
    __tablename__ = 'issue_analysis'
    review_id = Column(String, primary_key=True)
    version = Column(String, primary_key=True)
    source_hash = Column(String, nullable=False)
    status = Column(String, nullable=False)
    model = Column(String, nullable=False)
    result_json = Column(Text)
    error = Column(String)
    updated_at = Column(DateTime, nullable=False)


class ResearchRun(Base):
    """Durable progress and terminal state for an analysis execution."""
    __tablename__ = 'research_runs'
    id = Column(String, primary_key=True)
    version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    started_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    error = Column(String)


class ResearchRunProgress(Base):
    """Phase-specific progress, created without altering existing review tables."""
    __tablename__ = 'research_run_progress'
    run_id = Column(String, primary_key=True)
    phase = Column(String, nullable=False)
    scheduled = Column(Integer, nullable=False)
    completed = Column(Integer, nullable=False)
    failed = Column(Integer, nullable=False)

def get_engine(db_path=None):
    """Create and return an SQLAlchemy engine."""
    db_path = Path(db_path).resolve() if db_path is not None else REVIEW_DATABASE
    db_path.parent.mkdir(parents=True, exist_ok=True)
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
