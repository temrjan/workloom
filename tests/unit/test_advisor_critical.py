"""Critical path tests for WorkloomAdvisor: RAG pipeline and order processing.

Tests cover:
- RAG: user asks → embedding → vector search → LLM → answer
- Order: user sends order → LLM parses → sends to sales
- Safety: constraints injected, query enrichment, error fallback
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from workloom.modules.advisor.schemas import UserInfo
from workloom.modules.advisor.service import AdvisorService
from workloom.services.rag.qdrant import SearchResult

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def service() -> AdvisorService:
    """Create service with mocked external dependencies."""
    svc = AdvisorService.__new__(AdvisorService)
    svc._redis = None
    svc._redis_host = "localhost"
    svc._redis_port = 6379
    svc._extraction_agent = None
    svc._openai_client = None
    svc._openai_api_key = "sk-test"
    svc._notification_bot_token = "test-token"
    svc._sales_group_chat_id = "-100123"
    return svc


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Mock Redis with empty state."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.exists = AsyncMock(return_value=0)
    return redis


@pytest.fixture
def mock_rag() -> dict[str, MagicMock]:
    """Mock RAG services: embedding, qdrant, llm."""
    embedding = MagicMock()
    embedding.embed_text = AsyncMock(return_value=[0.1] * 3072)

    qdrant = MagicMock()
    qdrant.search = AsyncMock(
        return_value=[
            SearchResult(
                content="ACMEFLOR NEO — пробиотик нового поколения. Цена: 50 000 сум.",
                score=0.92,
                source="catalog.txt",
                metadata={"department": "advisor"},
            ),
        ]
    )

    llm = MagicMock()
    llm.generate_response = AsyncMock(
        return_value="ACMEFLOR NEO — пробиотик для восстановления микрофлоры. Цена: 50 000 сум."
    )

    return {"embedding": embedding, "qdrant": qdrant, "llm": llm}


def _patch_rag(mock_rag: dict[str, MagicMock], insight: dict | None = None):
    """Context manager patching all RAG dependencies at once."""
    import contextlib

    return contextlib.ExitStack().__enter__() or patch.multiple(
        "workloom.modules.advisor.service",
        get_embedding_service=MagicMock(return_value=mock_rag["embedding"]),
        get_qdrant_service=MagicMock(return_value=mock_rag["qdrant"]),
        get_llm_service=MagicMock(return_value=mock_rag["llm"]),
        get_active_insight=AsyncMock(return_value=insight),
    )


# =============================================================================
# RAG Pipeline
# =============================================================================


class TestRAGPipeline:
    """User asks question -> embedding -> vector search -> LLM -> answer."""

    async def test_returns_answer(
        self,
        service: AdvisorService,
        mock_redis: AsyncMock,
        mock_rag: dict[str, MagicMock],
    ) -> None:
        """Basic flow: user asks about product, gets relevant answer."""
        service._redis = mock_redis
        service._extraction_agent = MagicMock(
            process_and_save=AsyncMock(),
        )

        with (
            patch.object(
                service,
                "get_customer_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "workloom.modules.advisor.service.get_embedding_service",
                return_value=mock_rag["embedding"],
            ),
            patch(
                "workloom.modules.advisor.service.get_qdrant_service",
                return_value=mock_rag["qdrant"],
            ),
            patch(
                "workloom.modules.advisor.service.get_llm_service",
                return_value=mock_rag["llm"],
            ),
            patch(
                "workloom.modules.advisor.service.get_active_insight",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            answer = await service.get_ai_response(
                user_id="123456",
                message="Что такое ACMEFLOR NEO?",
                history_prefix="public",
                first_name="Тест",
            )

        assert "ACMEFLOR" in answer
        mock_rag["embedding"].embed_text.assert_called_once()
        mock_rag["qdrant"].search.assert_called_once()
        mock_rag["llm"].generate_response.assert_called_once()

    async def test_saves_history(
        self,
        service: AdvisorService,
        mock_redis: AsyncMock,
        mock_rag: dict[str, MagicMock],
    ) -> None:
        """After response, both user message and answer are saved to Redis."""
        service._redis = mock_redis
        service._extraction_agent = MagicMock(process_and_save=AsyncMock())

        with (
            patch.object(
                service,
                "get_customer_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "workloom.modules.advisor.service.get_embedding_service",
                return_value=mock_rag["embedding"],
            ),
            patch(
                "workloom.modules.advisor.service.get_qdrant_service",
                return_value=mock_rag["qdrant"],
            ),
            patch(
                "workloom.modules.advisor.service.get_llm_service",
                return_value=mock_rag["llm"],
            ),
            patch(
                "workloom.modules.advisor.service.get_active_insight",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await service.get_ai_response(
                user_id="test_user",
                message="расскажи про акмефлор",
                history_prefix="public",
            )

        mock_redis.set.assert_called_once()
        saved = json.loads(mock_redis.set.call_args[0][1])
        roles = [m["role"] for m in saved]
        assert "user" in roles
        assert "assistant" in roles

    async def test_error_returns_fallback(
        self,
        service: AdvisorService,
        mock_redis: AsyncMock,
    ) -> None:
        """On embedding/LLM failure, user gets a friendly error message."""
        service._redis = mock_redis
        broken = MagicMock()
        broken.embed_text = AsyncMock(side_effect=Exception("API down"))

        with (
            patch.object(
                service,
                "get_customer_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "workloom.modules.advisor.service.get_embedding_service",
                return_value=broken,
            ),
            patch(
                "workloom.modules.advisor.service.get_active_insight",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            answer = await service.get_ai_response(
                user_id="test_user",
                message="тест",
                history_prefix="public",
            )

        assert "Извините" in answer


# =============================================================================
# Query Enrichment & Safety
# =============================================================================


class TestQueryEnrichment:
    """Short/ambiguous queries are enriched before embedding search."""

    async def test_short_query_enriched_from_insight(
        self,
        service: AdvisorService,
        mock_redis: AsyncMock,
        mock_rag: dict[str, MagicMock],
    ) -> None:
        """'сколько стоит?' + DB insight with product → enriched embedding query."""
        service._redis = mock_redis
        service._extraction_agent = MagicMock(process_and_save=AsyncMock())
        insight = {"products": ["ACMEFLOR NEO"], "constraints": []}

        with (
            patch.object(
                service,
                "get_customer_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "workloom.modules.advisor.service.get_embedding_service",
                return_value=mock_rag["embedding"],
            ),
            patch(
                "workloom.modules.advisor.service.get_qdrant_service",
                return_value=mock_rag["qdrant"],
            ),
            patch(
                "workloom.modules.advisor.service.get_llm_service",
                return_value=mock_rag["llm"],
            ),
            patch(
                "workloom.modules.advisor.service.get_active_insight",
                new_callable=AsyncMock,
                return_value=insight,
            ),
        ):
            await service.get_ai_response(
                user_id="123456",
                message="сколько стоит?",
                history_prefix="public",
            )

        enriched = mock_rag["embedding"].embed_text.call_args[0][0]
        assert "ACMEFLOR NEO" in enriched

    async def test_constraints_injected_into_system_prompt(
        self,
        service: AdvisorService,
        mock_redis: AsyncMock,
        mock_rag: dict[str, MagicMock],
    ) -> None:
        """Customer constraints (allergies) appear in system prompt to LLM."""
        service._redis = mock_redis
        service._extraction_agent = MagicMock(process_and_save=AsyncMock())
        insight = {"products": [], "constraints": ["аллергия на лактозу"]}

        with (
            patch.object(
                service,
                "get_customer_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "workloom.modules.advisor.service.get_embedding_service",
                return_value=mock_rag["embedding"],
            ),
            patch(
                "workloom.modules.advisor.service.get_qdrant_service",
                return_value=mock_rag["qdrant"],
            ),
            patch(
                "workloom.modules.advisor.service.get_llm_service",
                return_value=mock_rag["llm"],
            ),
            patch(
                "workloom.modules.advisor.service.get_active_insight",
                new_callable=AsyncMock,
                return_value=insight,
            ),
        ):
            await service.get_ai_response(
                user_id="123456",
                message="что посоветуете?",
                history_prefix="public",
            )

        call_kwargs = mock_rag["llm"].generate_response.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt", "")
        assert "аллергия на лактозу" in system_prompt


# =============================================================================
# Order Parsing
# =============================================================================


def _mock_openai_response(content: str) -> MagicMock:
    """Create mock OpenAI chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


class TestParseOrder:
    """LLM-based order parsing: raw text → structured ParsedOrder."""

    async def test_parse_success(self, service: AdvisorService) -> None:
        """Order with name, phone, product → valid ParsedOrder."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                json.dumps(
                    {
                        "name": "Алишер",
                        "phone": "+15550104567",
                        "address": "Метрополис, Центр",
                        "products": [{"name": "ACMEFLOR NEO", "qty": 2}],
                    }
                )
            )
        )
        service._openai_client = mock_client

        result = await service.parse_order(
            raw_text="Закажите 2 акмефлор нео, Алишер, +15550104567, Центр",
            chat_history=[],
        )

        assert result is not None
        assert result.name == "Алишер"
        assert result.phone == "+15550104567"
        assert result.address == "Метрополис, Центр"
        assert len(result.products) == 1
        assert result.products[0].name == "ACMEFLOR NEO"
        assert result.products[0].qty == 2

    async def test_invalid_product_filtered(self, service: AdvisorService) -> None:
        """Products not in catalog are filtered out."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                json.dumps(
                    {
                        "name": "Тест",
                        "phone": "+15550104567",
                        "products": [
                            {"name": "ACMEFLOR NEO", "qty": 1},
                            {"name": "ВЫДУМАННЫЙ ПРОДУКТ", "qty": 3},
                        ],
                    }
                )
            )
        )
        service._openai_client = mock_client

        result = await service.parse_order("заказ", chat_history=[])

        assert result is not None
        assert len(result.products) == 1
        assert result.products[0].name == "ACMEFLOR NEO"

    async def test_llm_error_returns_none(self, service: AdvisorService) -> None:
        """OpenAI failure → returns None, no crash."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenAI rate limit")
        )
        service._openai_client = mock_client

        result = await service.parse_order("заказ", chat_history=[])
        assert result is None

    async def test_parse_uses_history_context(self, service: AdvisorService) -> None:
        """Chat history is included in LLM prompt for order parsing."""
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                json.dumps(
                    {
                        "name": None,
                        "phone": "+15550104567",
                        "products": [{"name": "ACMEFLOR NEO", "qty": 1}],
                    }
                )
            )
        )
        service._openai_client = mock_client

        history = [
            {"role": "user", "content": "хочу акмефлор нео"},
            {"role": "assistant", "content": "отлично, напишите телефон"},
        ]
        await service.parse_order("+15550104567", chat_history=history)

        call_args = mock_client.chat.completions.create.call_args
        user_content = call_args.kwargs["messages"][1]["content"]
        assert "акмефлор нео" in user_content


# =============================================================================
# Send Order to Sales
# =============================================================================


class TestSendOrderToSales:
    """Full flow: order detected → parsed by LLM → formatted → sent to Telegram."""

    async def test_send_success(self, service: AdvisorService) -> None:
        """Happy path: order parsed and delivered to sales group."""
        # Mock OpenAI parse_order
        mock_openai = AsyncMock()
        mock_openai.chat.completions.create = AsyncMock(
            return_value=_mock_openai_response(
                json.dumps(
                    {
                        "name": "Тест",
                        "phone": "+15550104567",
                        "products": [{"name": "ACMEFLOR NEO", "qty": 1}],
                    }
                )
            )
        )
        service._openai_client = mock_openai

        # Mock Telegram API response
        mock_tg = MagicMock(status_code=200)

        with patch("workloom.modules.advisor.service.httpx.AsyncClient") as mock_httpx:
            ctx = AsyncMock()
            ctx.post = AsyncMock(return_value=mock_tg)
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_httpx.return_value = ctx

            result = await service.send_order_to_sales(
                order_data={
                    "raw_text": "ACMEFLOR NEO, +15550104567",
                    "phone": "+15550104567",
                },
                user_info=UserInfo(user_id="123", first_name="Test", username="test"),
                history=[{"role": "user", "content": "хочу купить"}],
            )

        assert result is True
        tg_body = ctx.post.call_args.kwargs["json"]["text"]
        assert "ACMEFLOR NEO" in tg_body
        assert "+15550104567" in tg_body

    async def test_no_bot_token_returns_false(self, service: AdvisorService) -> None:
        """Without Telegram bot configured, order sending fails gracefully."""
        service._notification_bot_token = None

        result = await service.send_order_to_sales(
            order_data={"raw_text": "test", "phone": "123"},
            user_info=UserInfo(user_id="123"),
            history=[],
        )
        assert result is False
