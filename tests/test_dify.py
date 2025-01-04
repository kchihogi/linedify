import pytest
import os
from linedify import DifyAgent, DifyType

@pytest.fixture
def dify_agent():
    return DifyAgent(
        api_key=os.environ.get("DIFY_API_KEY"),
        base_url=os.environ.get("DIFY_BASE_URL"),
        user=os.environ.get("DIFY_USER"),
        type=DifyType.Agent,
        verbose=True
    )

@pytest.fixture
def image_bytes():
    with open(os.environ.get("DIFY_IMAGE_PATH"), 'rb') as image_file:
        return image_file.read()

@pytest.mark.asyncio
async def test_make_payloads_without_image(dify_agent):
    payloads = await dify_agent.make_payloads("test query")
    expected_payloads = {
        "inputs": {},
        "query": "test query",
        "response_mode": "streaming",
        "user": os.environ.get("DIFY_USER"),
        "auto_generate_name": False,
    }
    assert payloads == expected_payloads


@pytest.mark.asyncio
async def test_make_payloads_with_image(dify_agent, image_bytes):
    payloads = await dify_agent.make_payloads("test query", image_bytes=image_bytes)
    expected_payloads_without_image = {
        "inputs": {},
        "query": "test query",
        "response_mode": "streaming",
        "user": os.environ.get("DIFY_USER"),
        "auto_generate_name": False,
    }

    for k, v in payloads.items():
        if k == "files":
            assert len(v) == 1
            assert v[0]["transfer_method"] == "local_file"
        else:
            assert v == expected_payloads_without_image[k]


@pytest.mark.asyncio
async def test_invoke(dify_agent):
    conversation_id, response_text, response_data = await dify_agent.invoke(conversation_id=None, text="This is a test. Respond success.")

    assert "success" in response_text.lower()
    assert response_data == {}
    assert conversation_id is not None

    conversation_id2, response_text, response_data = await dify_agent.invoke(conversation_id=conversation_id, text="This is a test. Respond success again.")

    assert "success" in response_text.lower()
    assert response_data == {}
    assert conversation_id2 == conversation_id


@pytest.mark.asyncio
async def test_invoke_with_image(dify_agent, image_bytes):
    conversation_id, response_text, response_data = await dify_agent.invoke(conversation_id=None, text="what's this? Answer in English.", image=image_bytes)

    assert "cat" in response_text.lower()
    assert "girl" in response_text.lower()
    assert response_data == {}
    assert conversation_id is not None

@pytest.mark.asyncio
async def test_invoke_and_download_image(dify_agent):
    conversation_id, response_text, response_data = await dify_agent.invoke(conversation_id=None, text="Create an image of cat girl.")

    assert response_data["files"] is not None
    assert len(response_data["files"]) > 0
    for file in response_data["files"]:
        assert file["url"] is not None
        assert file["id"] is not None