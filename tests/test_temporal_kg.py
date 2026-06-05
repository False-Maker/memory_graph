"""Focused tests for the temporal knowledge graph core."""

from pathlib import Path

import pytest

from src.core.temporal_kg import TemporalKnowledgeGraph


class TestTemporalKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_upsert_query_and_delete_temporal_triple(self, temp_dir):
        db_path = Path(temp_dir) / "temporal-graph.db"
        kg = TemporalKnowledgeGraph(db_path=db_path)
        try:
            kg._conn.execute(
                """
                INSERT INTO entities (id, name, type, properties, source_text, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("entity-1", "Alice", "person", "{}", "", 1.0, "2026-04-16T00:00:00+00:00"),
            )
            kg._conn.execute(
                """
                INSERT INTO entities (id, name, type, properties, source_text, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("entity-2", "Memory Graph", "project", "{}", "", 1.0, "2026-04-16T00:00:00+00:00"),
            )
            kg._conn.commit()

            triple = await kg.upsert_triple(
                triple_id="triple-1",
                entity_id="entity-1",
                relation_type="works_on",
                target_entity_id="entity-2",
                valid_from="2026-04-01",
                valid_to="2026-04-30",
                confidence=0.8,
                source="manual",
                metadata={"ticket": "MG-2"},
            )

            assert triple.id == "triple-1"
            assert triple.valid_from == "2026-04-01T00:00:00+00:00"
            assert triple.valid_to == "2026-04-30T00:00:00+00:00"

            timeline = await kg.get_entity_timeline("entity-1")
            assert len(timeline) == 1
            assert timeline[0].relation_type == "works_on"

            as_of_state = await kg.get_entity_state_as_of("entity-1", "2026-04-16")
            assert len(as_of_state) == 1
            assert as_of_state[0].target_entity_id == "entity-2"

            stats = await kg.get_stats()
            assert stats.total_triples == 1
            assert stats.entities_with_temporal_data == 1
            assert stats.open_intervals == 0
            assert stats.bounded_intervals == 1

            deleted = await kg.delete_triple("triple-1")
            assert deleted is True
            assert await kg.get_entity_timeline("entity-1") == []
        finally:
            kg.close()
