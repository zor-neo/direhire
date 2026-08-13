import json

from direhire.ai.providers import ProviderResponse, ProviderUsage
from direhire.models import AiModelPolicy, AiOperation, OutboxEvent, User
from direhire.watches.expansion_orchestrator import WatchExpansionOrchestrator
from direhire.watches.expansion_service import expanded_search_keywords
from direhire.watches.schemas import WatchCreate
from direhire.watches.service import WatchService
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.conftest import USER_A


class StaticExpansionProvider:
    def generate(self, **kwargs: object) -> ProviderResponse:
        return ProviderResponse(
            text=json.dumps(
                {
                    "target_expansions": [
                        {"original": "Python", "variants": ["Python developer", "Python 3"]},
                        {"original": "Java", "variants": ["JVM engineer"]},
                    ],
                    "location_variants": ["Bangkok Metropolitan Area"],
                    "experience_keywords": ["mid-level"],
                    "schema_version": 1,
                }
            ),
            provider="OPENROUTER",
            route_key="approved-private",
            model=str(kwargs["model"]),
            usage=ProviderUsage(80, 30, 110),
        )


def test_watch_creation_queues_nonblocking_private_expansion_and_worker_stores_result(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        database.add_all(
            [
                User(
                    id=str(USER_A),
                    cognito_subject="watch-expansion-user",
                    email="watch-expansion@example.invalid",
                ),
                AiModelPolicy(
                    provider="OPENROUTER",
                    capability="AI_STANDARD",
                    model="approved/private-model",
                    max_output_tokens=1200,
                    input_cost_microusd_per_million=1000,
                    output_cost_microusd_per_million=2000,
                    enabled=True,
                ),
            ]
        )
        database.commit()

        watch = WatchService(database).create(
            str(USER_A),
            WatchCreate(
                name="Python roles",
                target_terms=["Python"],
                locations=["Bangkok"],
                experience_level="MID",
            ),
        )
        event = database.scalar(
            select(OutboxEvent).where(OutboxEvent.event_type == "watch.query-expansion.requested")
        )

        assert watch.search_expansion is None
        assert event is not None
        WatchExpansionOrchestrator(database, StaticExpansionProvider()).process(
            watch.id,
            str(event.payload["input_hash"]),
            correlation_id=event.correlation_id,
        )

        database.refresh(watch)
        assert expanded_search_keywords(watch) == ("Python", "Python developer", "Python 3")
        operation = database.scalar(
            select(AiOperation).where(AiOperation.task == "WATCH_QUERY_EXPANSION")
        )
        assert operation is not None
        assert operation.data_class == "PRIVATE_USER_DATA"
        assert operation.status == "SUCCEEDED"


def test_cosmetic_watch_rename_does_not_queue_another_expansion(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as database:
        database.add(
            User(
                id=str(USER_A),
                cognito_subject="watch-rename-user",
                email="watch-rename@example.invalid",
            )
        )
        database.commit()
        watch = WatchService(database).create(
            str(USER_A), WatchCreate(name="Original", target_terms=["Python"])
        )

        WatchService(database).replace(
            watch.id,
            str(USER_A),
            WatchCreate(name="Renamed", target_terms=["Python"]),
        )

        count = database.scalar(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "watch.query-expansion.requested")
        )
        assert count == 1
