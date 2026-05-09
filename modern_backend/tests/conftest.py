import pytest


@pytest.fixture(scope="session", autouse=True)
def set_asyncio_mode(request):
    request.config.option.asyncio_mode = "auto"
