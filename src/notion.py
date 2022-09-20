from ast import arg
from urllib.request import Request, urlopen
import asyncio
import json
import sys
from os import getenv
from typing import Any, Dict, Optional, List
from pprint import pprint


notion_version: str = "2022-06-28"
__version__: str = "0.0.1"
base_endpoint: str = "https://api.notion.com/v1"
search_endpoint: str = f"{base_endpoint}/search"
users_endpoint: str = f"{base_endpoint}/users"
pages_endpoint: str = f"{base_endpoint}/pages"
database_endpoint: str = f"{base_endpoint}/databases"
token: str = getenv("NOTION_API_TOKEN")
task_db_id: str = getenv("TASK_DB_ID")
note_db_id: str = getenv("NOTE_DB_ID")
note_emoji: str = getenv("NOTE_EMOJI", "📓")
task_emoji: str = getenv("TASK_EMOJI", "✅")


# Types
DatabaseProperty = Dict[str, Dict[str, str]]
AlfredObject = Dict[str, List[Dict[str, Any]]]


class Client:
    """Client for Notion API"""

    def __init__(self) -> None:
        token: str = getenv("NOTION_API_TOKEN")
        self.headers: Dict[str, str] = {
            "Notion-Version": notion_version,
            "User-Agent": f"gsornsen/notion-alfred@{__version__}",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        pass

    async def request(
        self,
        endpoint: str,
        method: str = "GET",
        auth: bool = True,
        query: Optional[Dict[Any, Any]] = None,
        body: Optional[Dict[Any, Any]] = None,
        ) -> Dict[str, Any]:
        """Send an async HTTP request"""
        request = Request(endpoint, headers=self.headers, data=query)
        with urlopen(request) as response:
            response = response.read()
            response = response.decode("utf-8")
            response = json.loads(response)
        return response

    async def _encode_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        encoded_payload = json.dumps(payload).encode("utf-8")
        return encoded_payload

    async def search_for_pages(self, query: str) -> Any:
        search_payload = {
            "query": f"{query}",
            "page_size": 10,
            "sort": {
                "direction": "ascending",
                "timestamp": "last_edited_time",
            },
        }
        encoded_payload = await self._encode_payload(search_payload)
        request = await self.request(search_endpoint, query=encoded_payload)
        pages = await self.parse_search_results(request)
        return pages

    async def get_page_property_by_ids(self, page_id: str, property_name: str) -> str:
        endpoint = f"{pages_endpoint}/{page_id}"
        request = await self.request(endpoint)
        props = request["properties"]
        icon = request["icon"]
        if "title" in property_name:
            prop: str = props["title"]["title"][0]["plain_text"]
        elif "icon" in property_name:
            prop: str = icon["emoji"]
        else:
            prop: str = props[property_name]
        return prop

    async def parse_search_results(
        self,
        search_results: Dict[str, Any]
        ) -> Dict[str, Dict[str, str]]:
        parsed_results = {}
        if len(search_results["results"]) == 0:
            return parsed_results
        for result in search_results["results"]:
            _ = {}
            # TODO: Alfred uses paths for icons only
            # https://www.alfredapp.com/help/workflows/inputs/script-filter/json/
            _["id"] = result["id"]
            _["url"] = result["url"]
            page_title = await self.get_page_property_by_ids(_["id"], "title")
            page_icon = await self.get_page_property_by_ids(_["id"], "icon")
            _["icon"] = page_icon
            parsed_results[page_title] = _
        return parsed_results

    async def translate_search_results_for_alfred(
        self,
        parsed_results) -> AlfredObject:
        alfred_object = {
            "items": []
        }
        for page_title in parsed_results:
            page = {}
            page_props = parsed_results[page_title]
            page["uid"] = page_title
            page["type"] = "default"
            page["title"] = page_title
            page["arg"] = page_props["url"]
            page["quicklookurl"] = page_props["url"]
            page["icon"] = page_props["icon"]
            page["autocomplete"] = page_title
            alfred_object["items"].append(page)
        return alfred_object

    async def add_note_db_entry(self, db_id: str, title: str, icon: str) -> None:
        # TODO: Dynamic entries
        payload = {
            "parent": {
                "database_id": f"{db_id}"
            },
            "properties": {
                "Title": {
                    "title": [
                        {
                            "text": {
                                "content": f"{title}"
                            }
                        }
                    ]
                },
                "Type": {
                    "select": {
                        "name": "Alfred",
                        # "color": "purple",
                    }
                }
            }
        }
        encoded_payload = await self._encode_payload(payload)
        await self.request(pages_endpoint, query=encoded_payload)
        return

    async def add_task_db_entry(self, db_id: str, title: str, icon: str) -> None:
        # TODO: Dynamic entries
        payload = {
            "parent": {
                "database_id": f"{db_id}"
            },
            "properties": {
                "Task": {
                    "title": [
                        {
                            "text": {
                                "content": f"{title}"
                            }
                        }
                    ]
                },
                "Kanban Status": {
                    "select": {
                        "name": "To Do"
                    }
                },
                "Priority": {
                    "select": {
                        "name": "🧀 Medium"
                    }
                }
            }
        }
        encoded_payload = await self._encode_payload(payload)
        await self.request(pages_endpoint, query=encoded_payload)
        return


async def main(action: str, data: str, debug: bool = False):
    client = Client()
    if action == "search":
        search_results = await client.search_for_pages(data)
        alfred_object = await client.translate_search_results_for_alfred(search_results)

        print(json.dumps(alfred_object, indent=2, ensure_ascii=False)) # For Alfred
    elif action == "task":
        await client.add_task_db_entry(task_db_id, data, task_emoji)
    elif action == "note":
        await client.add_note_db_entry(note_db_id, data, note_emoji)
    else:
        raise KeyError("Action not supported!")


if __name__ == "__main__":
    args = sys.argv
    if len(args) < 3:
        print("Implement the help string")
        sys.exit(1)
    else:
        action = f"{args[1]}"
        data = f"{args[2]}"
        asyncio.run(main(action, data))
