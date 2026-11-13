import json
from pathlib import Path

from motocheck.catalog import SOURCES


KNOWLEDGE_PATH = Path(__file__).parent / "data" / "knowledge.json"
with KNOWLEDGE_PATH.open(encoding="utf-8") as knowledge_file:
    TOPICS = json.load(knowledge_file)


def search_topics(query="", category=""):
    query = query.strip().casefold()
    category = category.strip()
    results = []
    for topic in TOPICS:
        searchable = " ".join(
            [topic["title"], topic["category"], topic["description"], *topic["symptoms"]]
        ).casefold()
        if query and query not in searchable:
            continue
        if category and topic["category"] != category:
            continue
        results.append(
            {
                **topic,
                "references": [SOURCES[source_id] for source_id in topic["reference_ids"]],
            }
        )
    return results


def categories():
    return sorted({topic["category"] for topic in TOPICS})
