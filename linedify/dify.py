from enum import Enum
import json
from logging import getLogger, NullHandler
from typing import Dict, Tuple
import aiohttp


logger = getLogger(__name__)
logger.addHandler(NullHandler())


class DifyType(Enum):
    Agent = "Agent"
    Chatbot = "Chatbot"
    TextGenerator = "TextGenerator"
    Workflow = "Workflow"


class DifyAgent:
    def __init__(self, *, api_key: str, base_url: str, user: str, type: DifyType = DifyType.Agent, verbose: bool = False) -> None:
        self.verbose = verbose
        self.api_key = api_key
        self.base_url = base_url
        self.user = user
        self.type = type
        self.response_processors = {
            DifyType.Agent: self.process_agent_response,
            DifyType.Chatbot: self.process_chatbot_response,
            DifyType.TextGenerator: self.process_textgenerator_response,
            DifyType.Workflow: self.process_workflow_response
        }
        self.conversation_ids = {}

    async def make_payloads(self, text: str, image_bytes: bytes = None, inputs: dict = None) -> Dict:
        payloads = {
            "inputs": inputs or {},
            "query": text,
            "response_mode": "streaming" if self.type == DifyType.Agent or self.type == DifyType.Workflow else "blocking",
            "user": self.user,
            "auto_generate_name": False,
        }

        if image_bytes:
            uploaded_image_id = await self.upload_image(image_bytes)
            if uploaded_image_id:
                payloads["files"] = [{
                    "type": "image",
                    "transfer_method": "local_file",
                    "upload_file_id": uploaded_image_id
                }]
                if not payloads["query"]:
                    payloads["query"] = "." # Set dummy to prevent query empty error
        
        return payloads

    async def upload_image(self, image_bytes: str) -> str:
        form_data = aiohttp.FormData()
        form_data.add_field("file",
            image_bytes,
            filename="image.png",
            content_type="image/png")
        form_data.add_field('user', self.user)

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url + "/files/upload",
                headers={"Authorization": f"Bearer {self.api_key}"},
                data=form_data
            ) as response:
                response_json = await response.json()
                if self.verbose:
                    logger.info(f"File upload response: {json.dumps(response_json, ensure_ascii=False)}")
                response.raise_for_status()
                return response_json["id"]

    async def process_agent_response(self, response: aiohttp.ClientResponse) -> Tuple[str, str, Dict]:
        conversation_id = ""
        response_text = ""
        response_data = {}

        buffer = b""
        async for r in response.content.iter_any():
            buffer += r
            if b"\n\n" in buffer:
                data, buffer = buffer.split(b"\n\n", 1)
                try:
                    decoded_r = data.decode("utf-8")
                except UnicodeDecodeError:
                    buffer = data + "\n\n" + buffer
                    continue
            else:
                continue

            if not decoded_r.startswith("data:"):
                continue

            try:
                chunk = json.loads(decoded_r[5:])
            except json.JSONDecodeError:
                continue

            if self.verbose:
                logger.debug(f"Chunk from Dify: {json.dumps(chunk, ensure_ascii=False)}")

            event_type = chunk["event"]

            if event_type == "agent_message":
                conversation_id = chunk["conversation_id"]
                response_text += chunk["answer"]

            elif event_type == "agent_thought":
                if tool := chunk.get("tool"):
                    response_data["tool"] = tool
                if tool_input := chunk.get("tool_input"):
                    response_data["tool_input"] = tool_input
    
            elif event_type == "message_end":
                if retriever_resources := chunk["metadata"].get("retriever_resources"):
                    response_data["retriever_resources"] = retriever_resources

            elif event_type == "message_file":
                file_obj = {
                    "base_url": self.base_url.rstrip("/"), # Remove trailing slash
                    "url": chunk["url"] if chunk.get("url") else None,
                    "id": chunk["id"] if chunk.get("id") else None,
                    "type": chunk["type"] if chunk.get("type") else None,
                    "belongs_to": chunk["belongs_to"] if chunk.get("belongs_to") else None,
                    "conversation_id": chunk["conversation_id"] if chunk.get("conversation_id") else None,
                }
                response_data["files"] = response_data.get("files", []) + [file_obj]

        return conversation_id, response_text, response_data

    async def process_chatbot_response(self, response: aiohttp.ClientResponse) -> Tuple[str, str, Dict]:
        response_json = await response.json()

        if self.verbose:
            logger.info(f"Response from Dify: {json.dumps(response_json, ensure_ascii=False)}")

        conversation_id = response_json["conversation_id"]
        response_text = response_json["answer"]
        return conversation_id, response_text, {}

    async def process_textgenerator_response(self, response: aiohttp.ClientResponse) -> Tuple[str, str, Dict]:
        if self.verbose:
            logger.info(f"Response from Dify: {json.dumps(await response.json(), ensure_ascii=False)}")

        raise Exception("TextGenerator is not supported for now.")

    async def process_workflow_response(self, response: aiohttp.ClientResponse) -> Tuple[str, str, Dict]:
        conversation_id = ""
        response_text = ""
        response_data = {}

        buffer = b""
        async for r in response.content.iter_any():
            buffer += r
            if b"\n\n" in buffer:
                data, buffer = buffer.split(b"\n\n", 1)
                try:
                    decoded_r = data.decode("utf-8")
                except UnicodeDecodeError:
                    buffer = data + "\n\n" + buffer
                    continue
            else:
                continue

            if not decoded_r.startswith("data:"):
                continue

            try:
                chunk = json.loads(decoded_r[5:])
            except json.JSONDecodeError:
                continue

            if self.verbose:
                logger.debug(f"Chunk from Dify: {json.dumps(chunk, ensure_ascii=False)}")

            event_type = chunk["event"]

            if event_type == "message":
                conversation_id = chunk["conversation_id"]
                response_text += chunk["answer"]
    
            elif event_type == "message_end":
                if retriever_resources := chunk["metadata"].get("retriever_resources"):
                    response_data["retriever_resources"] = retriever_resources
            
            elif event_type == "workflow_started":
                response_data["workflow_started"] = {
                    "task_id": chunk["task_id"] if chunk.get("task_id") else None,
                    "workflow_run_id": chunk["workflow_run_id"] if chunk.get("workflow_run_id") else None,
                    "data": chunk["data"] if chunk.get("data") else None,
                    "id": chunk["id"] if chunk.get("id") else None,
                    "workflow_id": chunk["workflow_id"] if chunk.get("workflow_id") else None,
                    "sequence_number": chunk["sequence_number"] if chunk.get("sequence_number") else None,
                    "created_at": chunk["created_at"] if chunk.get("created_at") else None,
                }

            elif event_type == "workflow_ended":
                response_data["workflow_ended"] = {
                    "task_id": chunk["task_id"] if chunk.get("task_id") else None,
                    "workflow_run_id": chunk["workflow_run_id"] if chunk.get("workflow_run_id") else None,
                    "data": chunk["data"] if chunk.get("data") else None,
                    "id": chunk["id"] if chunk.get("id") else None,
                    "workflow_id": chunk["workflow_id"] if chunk.get("workflow_id") else None,
                    "status": chunk["status"] if chunk.get("status") else None,
                    "outputs": chunk["outputs"] if chunk.get("outputs") else None,
                    "error": chunk["error"] if chunk.get("error") else None,
                    "elapsed_time": chunk["elapsed_time"] if chunk.get("elapsed_time") else None,
                    "total_tokens": chunk["total_tokens"] if chunk.get("total_tokens") else None,
                    "total_steps": chunk["total_steps"] if chunk.get("total_steps") else None,
                    "created_at": chunk["created_at"] if chunk.get("created_at") else None,
                    "finished_at": chunk["finished_at"] if chunk.get("finished_at") else None,
                }

            elif event_type == "node_started":
                response_data["node_started"] = response_data.get("node_started", []) + [{
                    "task_id": chunk["task_id"] if chunk.get("task_id") else None,
                    "workflow_run_id": chunk["workflow_run_id"] if chunk.get("workflow_run_id") else None,
                    "data": chunk["data"] if chunk.get("data") else None,
                    "id": chunk["id"] if chunk.get("id") else None,
                    "node_id": chunk["node_id"] if chunk.get("node_id") else None,
                    "node_type": chunk["node_type"] if chunk.get("node_type") else None,
                    "title": chunk["title"] if chunk.get("title") else None,
                    "index": chunk["index"] if chunk.get("index") else None,
                    "predecessor_node_id": chunk["predecessor_node_id"] if chunk.get("predecessor_node_id") else None,
                    "inputs": chunk["inputs"] if chunk.get("inputs") else None,
                    "created_at": chunk["created_at"] if chunk.get("created_at") else None,
                }]

            elif event_type == "node_finished":
                response_data["node_finished"] = response_data.get("node_finished", []) + [{
                    "task_id": chunk["task_id"] if chunk.get("task_id") else None,
                    "workflow_run_id": chunk["workflow_run_id"] if chunk.get("workflow_run_id") else None,
                    "data": chunk["data"] if chunk.get("data") else None,
                    "id": chunk["id"] if chunk.get("id") else None,
                    "node_id": chunk["node_id"] if chunk.get("node_id") else None,
                    "node_type": chunk["node_type"] if chunk.get("node_type") else None,
                    "title": chunk["title"] if chunk.get("title") else None,
                    "index": chunk["index"] if chunk.get("index") else None,
                    "predecessor_node_id": chunk["predecessor_node_id"] if chunk.get("predecessor_node_id") else None,
                    "inputs": chunk["inputs"] if chunk.get("inputs") else None,
                    "process_data": chunk["process_data"] if chunk.get("process_data") else None,
                    "outputs": chunk["outputs"] if chunk.get("outputs") else None,
                    "status": chunk["status"] if chunk.get("status") else None,
                    "error": chunk["error"] if chunk.get("error") else None,
                    "elapsed_time": chunk["elapsed_time"] if chunk.get("elapsed_time") else None,
                    "execution_metadata": chunk["execution_metadata"] if chunk.get("execution_metadata") else None,
                    "total_tokens": chunk["total_tokens"] if chunk.get("total_tokens") else None,
                    "total_price": chunk["total_price"] if chunk.get("total_price") else None,
                    "currency": chunk["currency"] if chunk.get("currency") else None,
                    "created_at": chunk["created_at"] if chunk.get("created_at") else None,
                }]            

        return conversation_id, response_text, response_data

    async def invoke(self, conversation_id: str, text: str = None, image: bytes = None, inputs: dict = None, start_as_new: bool = False) -> Tuple[str, Dict]:
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        payloads = await self.make_payloads(text, image, inputs)

        if conversation_id and not start_as_new:
            payloads["conversation_id"] = conversation_id

        async with aiohttp.ClientSession() as session:
            if self.verbose:
                logger.info(f"Request to Dify: {json.dumps(payloads, ensure_ascii=False)}")

            async with session.post(
                self.base_url + "/chat-messages",
                headers=headers,
                json=payloads
            ) as response:

                if response.status != 200:
                    logger.error(f"Error response from Dify: {json.dumps(await response.json(), ensure_ascii=False)}")
                response.raise_for_status()

                response_processor = self.response_processors[self.type]
                conversation_id, response_text, response_data = await response_processor(response)

                return conversation_id, response_text, response_data
