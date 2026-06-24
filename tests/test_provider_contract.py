from hyperspace.providers.base import (
    BaseProvider,
    CostTier,
    ProviderCapabilities,
    ProviderHealth,
    ProviderRequest,
    ProviderResponse,
    ProviderStatus,
    ProviderType,
)


class DummyProvider(BaseProvider):
    def __init__(self):
        self.id = "dummy"
        self.type = ProviderType.API
        self.capabilities = ProviderCapabilities(text=True)
        self.cost_tier = CostTier.FREE

    async def health_check(self):
        return ProviderHealth(status=ProviderStatus.AVAILABLE, score=100.0, message="ok")

    async def chat(self, request):
        return ProviderResponse(answer="ok", provider_id=self.id, provider_type=self.type)

    async def upload_file(self, request):
        return {"id": "file-1"}


async def test_provider_contract_types_and_methods():
    provider = DummyProvider()
    request = ProviderRequest(prompt="hello", provider_id="dummy")
    response = await provider.chat(request)

    assert response.answer == "ok"
    assert response.provider_id == "dummy"
    assert response.provider_type == ProviderType.API
    assert provider.capabilities.text is True
    assert provider.cost_tier == CostTier.FREE


async def test_provider_response_legacy_fields_are_compatible():
    response = ProviderResponse(
        text="legacy answer",
        provider="zhipu",
        model="glm-4.7-flash",
        prompt_tokens=10,
        completion_tokens=20,
    )

    assert response.text == "legacy answer"
    assert response.provider == "zhipu"
    assert response.model == "glm-4.7-flash"
    assert response.prompt_tokens == 10
    assert response.completion_tokens == 20
    assert response.answer == "legacy answer"
    assert response.provider_id == "zhipu"
