from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.process.db import Phase1CatalogRow
from src.process.catalog_store import current_catalog_assessments
from src.process.catalog_schema import CatalogAssessment
from collections import Counter

engine = create_engine('sqlite:///src/data/research.db')
Session = sessionmaker(bind=engine)
session = Session()

rows = session.query(Phase1CatalogRow).filter_by(active=1).all()
stored = current_catalog_assessments(session, rows)

# Get successful assessments
results = [CatalogAssessment.model_validate_json(item.result_json) for item in stored.values() if item.status == 'succeeded']

# We are focusing on candidates (direct_memory_issue or observed_retrieval_issue)
candidates = [r for r in results if r.issue_class in {'direct_memory_issue', 'observed_retrieval_issue'}]

print(f"Total Rows: {len(rows)}")
print(f"Total Successful Assessments: {len(results)}")
print(f"Total Candidates (Direct/Observed Issues): {len(candidates)}")

print("\n--- Confidence Distribution ---")
conf_counts = Counter(c.confidence for c in candidates)
for k, v in conf_counts.most_common():
    print(f"{k}: {v}")

print("\n--- Search Methods ---")
search_counts = Counter(method for c in candidates for method in c.search_methods)
for k, v in search_counts.most_common():
    print(f"{k}: {v}")

print("\n--- Journey Stages ---")
journey_counts = Counter(stage for c in candidates for stage in c.journey_stages)
for k, v in journey_counts.most_common():
    print(f"{k}: {v}")
