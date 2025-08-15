#!/usr/bin/env python3
"""
Chainlit Application with LLM Integration - REST MCP VERSION
Enhanced with detailed logging and debug info.
"""

import json
import logging
from typing import Dict, Any, List, Optional
import chainlit as cl
import openai
import os
import httpx
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("chainlit-app")



def extract_json_from_text(text):
    """
    Extract the first JSON object from a string, even if surrounded by other text.
    """
    # This regex finds the first {...} block in the string
    match = re.search(r'(\{.*\})', text, re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            return None
    return None


class MCPClient:
    def __init__(self, base_url="http://127.0.0.1:8001"):
        self.base_url = base_url
        self.connected = False
        self.available_tools = []

    async def connect(self):
        """Check connection and fetch available tools from REST MCP server."""
        try:
            self.available_tools = await self.list_tools()
            self.connected = True
            logger.info(f"Connected to MCP REST server with {len(self.available_tools)} tools")
        except Exception as e:
            logger.error(f"Failed to connect to MCP REST server: {e}")
            self.connected = False

    async def disconnect(self):
        """No persistent connection to close for REST API."""
        self.connected = False
        logger.info("Disconnected from MCP REST server.")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on the MCP REST server."""
        logger.info(f"Calling tool: {tool_name} with arguments: {arguments}")
        if not self.connected:
            await self.connect()
        try:
            async with httpx.AsyncClient() as client:
                if tool_name == "search_news":
                    resp = await client.get(f"{self.base_url}/news/search", params=arguments)
                elif tool_name == "get_top_headlines":
                    resp = await client.get(f"{self.base_url}/news/headlines", params=arguments)
                elif tool_name == "search_web":
                    resp = await client.get(f"{self.base_url}/web/search", params=arguments)
                elif tool_name == "parse_rss_feed":
                    resp = await client.get(f"{self.base_url}/rss/parse", params=arguments)
                elif tool_name == "add_event":
                    resp = await client.post(f"{self.base_url}/events", json=arguments)
                elif tool_name == "get_events":
                    resp = await client.get(f"{self.base_url}/events", params=arguments)
                elif tool_name == "delete_event":
                    event_id = arguments.get("event_id")
                    if not event_id:
                        logger.error("Missing event_id for delete_event")
                        return {"error": "event_id is required"}
                    resp = await client.delete(f"{self.base_url}/events/{event_id}")
                elif tool_name == "update_config":
                    resp = await client.post(f"{self.base_url}/config", json=arguments)
                else:
                    logger.error(f"Unknown tool: {tool_name}")
                    return {"error": f"Unknown tool: {tool_name}"}
                resp.raise_for_status()
                logger.debug(f"Tool {tool_name} response: {resp.text}")
                return resp.json()
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools from the MCP REST server."""
        print("Connecting to MCP Server")

        try:
            async with httpx.AsyncClient() as client:
                endpoint= f"{self.base_url}/resources"
                print("Connecting to Endpoint:", endpoint);
                resp = await client.get(endpoint)
                resp.raise_for_status()
                logger.debug(f"Tools listed: {resp.json}")
                return [
                    {"name": "search_news", "description": "Search for news articles using NewsAPI"},
                    {"name": "get_top_headlines", "description": "Get top headlines from NewsAPI"},
                    {"name": "search_web", "description": "Search the web using SerpAPI"},
                    {"name": "parse_rss_feed", "description": "Parse and retrieve articles from RSS feed"},
                    {"name": "add_event", "description": "Add an event to the calendar"},
                    {"name": "get_events", "description": "Get events from the calendar"},
                    {"name": "delete_event", "description": "Delete an event from the calendar"},
                    {"name": "update_config", "description": "Update server configuration"},
                ]
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return []

class LLMClient:
    def __init__(self):
        # Configure OpenAI client to use LM Studio
        self.base_url = os.getenv("LM_STUDIO_BASE_URL", "http://192.168.68.110:23232/v1")
        self.api_key = os.getenv("LM_STUDIO_API_KEY", "lm-studio")
        self.model = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-14b")

        logger.info(f"LLM Config - Base URL: {self.base_url}, Model: {self.model}")

        self.client = openai.AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    async def test_connection(self) -> bool:
        """Test connection to LM Studio"""
        try:
            logger.info("Testing LLM connection...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "Hello, are you working?"}],
                max_tokens=10
            )
            logger.info("LLM connection successful!")
            return True
        except Exception as e:
            logger.error(f"LLM connection failed: {e}")
            return False

    async def generate_response(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response using LM Studio"""
        try:
            logger.info(f"Generating response for {len(messages)} messages with {len(tools) if tools else 0} tools")

            # Create system message with tool information
            system_message = {
                "role": "system",
                "content": f"""You are a helpful AI assistant that can access various tools for news, web search, RSS feeds, and event management.

Available tools:
{json.dumps([{"name": t["name"], "description": t["description"]} for t in tools], indent=2) if tools else "No tools available"}

When a user asks for something that requires using a tool, respond with a JSON object in this exact format:
{{"action": "use_tool", "tool": "tool_name", "arguments": {{"param": "value"}}}}

Available tools and their usage:
- search_news: Search for news articles (arguments: query, language, sort_by, page_size)
- get_top_headlines: Get top headlines (arguments: country, category, page_size)
- search_web: Search the web (arguments: query, num_results, location)
- parse_rss_feed: Parse RSS feed (arguments: url, max_entries)
- add_event: Add calendar event (arguments: title, date, description, time, location)
- get_events: Get calendar events (arguments: date, days_ahead)
- delete_event: Delete calendar event (arguments: event_id)

For general conversation or when providing results, respond normally in markdown format.

Examples:
User: "What's the latest news about AI?"
Response: {{"action": "use_tool", "tool": "search_news", "arguments": {{"query": "artificial intelligence", "page_size": 5}}}}

User: "Search for Python tutorials"
Response: {{"action": "use_tool", "tool": "search_web", "arguments": {{"query": "Python tutorials", "num_results": 5}}}}

User: "Show me upcoming events"
Response: {{"action": "use_tool", "tool": "get_events", "arguments": {{"days_ahead": 7}}}}

Be helpful, concise, and friendly. Always try to understand the user's intent and use the appropriate tool when needed."""
            }

            # Prepare messages
            full_messages = [system_message] + messages

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                temperature=0.3,
                max_tokens=1000
            )

            content = response.choices[0].message.content.strip()
            logger.info(f"LLM Response: {content[:100]}...")

            # Try to parse as JSON for tool calls
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict) and parsed.get("action") == "use_tool":
                    logger.info(f"Tool call detected: {parsed.get('tool')}")
                    return {
                        "type": "tool_call",
                        "tool": parsed.get("tool"),
                        "arguments": parsed.get("arguments", {})
                    }
            except json.JSONDecodeError:
                logger.info("Regular text response (not a tool call)")
                pass

            # Regular text response
            return {
                "type": "text",
                "content": content
            }

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return {
                "type": "text",
                "content": f"I'm having trouble connecting to the language model. Error: {str(e)}\n\nPlease check:\n1. LM Studio is running on {self.base_url}\n2. Model '{self.model}' is loaded\n3. Server is accessible"
            }

# Global instances
mcp_client = MCPClient(base_url="http://127.0.0.1:8001")
llm_client = LLMClient()

@cl.on_chat_start
async def start():
    """Initialize the chat session"""
    cl.user_session.set("messages", [])

    llm_connected = await llm_client.test_connection()

    if llm_connected:
        try:
            await mcp_client.connect()
        except Exception as e:
            logger.error(f"MCP connection failed: {e}")

    status_msg = "🌟 **Welcome to the AI News & Search Assistant!**\n\n"

    if llm_connected:
        status_msg += "✅ **LLM Status**: Connected to Qwen3-14B\n"
    else:
        status_msg += "❌ **LLM Status**: Not connected - check LM Studio\n"

    if mcp_client.connected:
        status_msg += f"✅ **MCP Status**: Connected with {len(mcp_client.available_tools)} tools\n\n"
        status_msg += """I can help you with:

📰 **News**: Search articles, get top headlines
🔍 **Web Search**: Search the internet using SerpAPI
📡 **RSS Feeds**: Parse and read RSS feeds
📅 **Events**: Manage your calendar events

Just ask me anything in natural language - I'll understand and use the right tools!

**Examples:**
• "What's the latest news about climate change?"
• "Search for Python machine learning tutorials"
• "Parse this RSS feed: https://feeds.bbci.co.uk/news/rss.xml"
• "Add an event: Team meeting tomorrow at 2 PM\""""
    else:
        status_msg += "❌ **MCP Status**: Not connected - tools unavailable\n\n"
        status_msg += """**LLM-Only Mode**: I can still chat with you, but news/search tools are unavailable.

To enable tools:
1. Check that `mcp_server.py` runs: `python3 mcp_server.py`
2. Ensure API keys are set in `.env` file
3. Install dependencies: `pip install mcp python-dotenv httpx feedparser`

**You can still:**
• Ask general questions
• Get help and explanations
• Have conversations"""

    status_msg += f"""

**Debug Info:**
• LM Studio URL: {llm_client.base_url}
• Model: {llm_client.model}
• Available Tools: {len(mcp_client.available_tools)}"""

    await cl.Message(content=status_msg).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle incoming messages"""
    logger.info(f"User message: {message.content}")
    messages = cl.user_session.get("messages", [])
    messages.append({"role": "user", "content": message.content})

    thinking_msg = cl.Message(content="🤔 Thinking...")
    await thinking_msg.send()

    response = await llm_client.generate_response(messages, mcp_client.available_tools)
    logger.info(f"LLM response: {response}")

    await thinking_msg.remove()
    print("Thinkig message is :",response)
   
    parsed = extract_json_from_text(response["content"])  # Use the string content
    response = parsed
    if response["action"] == "use_tool":
        print("Handling tool call with messages:", messages);
        await handle_tool_call(response["tool"], response["arguments"], messages)
    else:
        await cl.Message(content=response["content"]).send()
        messages.append({"role": "assistant", "content": response["content"]})

    cl.user_session.set("messages", messages)

async def handle_tool_call(tool_name: str, arguments: Dict[str, Any], messages: List[Dict[str, str]]):
    logger.info(f"Handling tool call: {tool_name} with arguments: {arguments}")
    loading_msg = cl.Message(content=f"🔧 Using {tool_name}...")
    await loading_msg.send()

    try:
        result = await mcp_client.call_tool(tool_name, arguments)
        logger.info(f"Result from {tool_name}: {result}")
        await loading_msg.remove()

        if tool_name == "search_news" or tool_name == "get_top_headlines":
            await display_news_results(result, tool_name, arguments)
        elif tool_name == "search_web":
            await display_search_results(result, arguments.get("query", ""))
        elif tool_name == "parse_rss_feed":
            await display_rss_results(result, arguments.get("url", ""))
        elif tool_name == "get_events":
            await display_events(result)
        elif tool_name == "add_event":
            await display_event_added(result)
        elif tool_name == "delete_event":
            await display_event_deleted(result)
        else:
            await cl.Message(content=f"**Result from {tool_name}:**\n\n```json\n{json.dumps(result, indent=2)}\n```").send()

        messages.append({
            "role": "assistant", 
            "content": f"I used {tool_name} with arguments {arguments} and got results."
        })

    except Exception as e:
        logger.error(f"Exception in handle_tool_call: {e}")
        await loading_msg.remove()
        await cl.Message(content=f"❌ Error using {tool_name}: {str(e)}").send()

async def display_news_results(result: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]):
    try:
        logger.debug(f"News result: {json.dumps(result, indent=2)}")
        await cl.Message(content=f"DEBUG: {json.dumps(result, indent=2)}").send()  # For debugging, remove if not needed
        if "error" in result:
            await cl.Message(content=f"❌ Error: {result['error']}").send()
            return

        articles = result.get("articles", [])
        logger.info(f"Found {len(articles)} articles.")
        if not articles:
            await cl.Message(content="No news articles found.").send()
            return

        # For get_top_headlines, use country/category in title if present
        country = arguments.get("country", "")
        category = arguments.get("category", "")
        title = "Top Headlines"
        if country:
            title += f" from {country.upper()}"
        if category:
            title += f" - {category.title()}"

        content = f"## 📰 {title}\n\n"

        for i, article in enumerate(articles[:5], 1):
            logger.debug(f"Article {i}: {article}")
            content += f"**{i}. {article.get('title', 'No title')}**\n"
            content += f"*Source: {article.get('source', {}).get('name', 'Unknown')}*\n"
            content += f"{article.get('description', 'No description')}\n"
            if article.get('url'):
                content += f"[Read more]({article['url']})\n"
            if article.get('publishedAt'):
                content += f"*Published: {article['publishedAt']}*\n"
            content += "\n---\n\n"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_news_results: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

async def display_search_results(result: Dict[str, Any], query: str):
    try:
        logger.debug(f"Search result: {json.dumps(result, indent=2)}")
        if "error" in result:
            await cl.Message(content=f"❌ Error: {result['error']}").send()
            return

        organic_results = result.get("organic_results", [])
        logger.info(f"Found {len(organic_results)} search results.")
        if not organic_results:
            await cl.Message(content="No search results found.").send()
            return

        content = f"## 🔍 Search Results for: {query}\n\n"

        for i, result_item in enumerate(organic_results[:5], 1):
            logger.debug(f"Search result {i}: {result_item}")
            content += f"**{i}. {result_item.get('title', 'No title')}**\n"
            content += f"{result_item.get('snippet', 'No description')}\n"
            if result_item.get('link'):
                content += f"[Visit page]({result_item['link']})\n"
            content += "\n---\n\n"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_search_results: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

async def display_rss_results(result: Dict[str, Any], url: str):
    try:
        logger.debug(f"RSS result: {json.dumps(result, indent=2)}")
        if "error" in result:
            await cl.Message(content=f"❌ Error: {result['error']}").send()
            return

        entries = result.get("entries", [])
        logger.info(f"Found {len(entries)} RSS entries.")
        if not entries:
            await cl.Message(content="No RSS entries found.").send()
            return

        feed_title = result.get("feed_title", "RSS Feed")
        content = f"## 📡 {feed_title}\n\n"

        for i, entry in enumerate(entries[:5], 1):
            logger.debug(f"RSS entry {i}: {entry}")
            content += f"**{i}. {entry.get('title', 'No title')}**\n"
            content += f"{entry.get('description', 'No description')}\n"
            if entry.get('link'):
                content += f"[Read more]({entry['link']})\n"
            if entry.get('published'):
                content += f"*Published: {entry['published']}*\n"
            content += "\n---\n\n"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_rss_results: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

async def display_events(result: Dict[str, Any]):
    try:
        logger.debug(f"Events result: {json.dumps(result, indent=2)}")
        if "error" in result:
            await cl.Message(content=f"❌ Error: {result['error']}").send()
            return

        events = result.get("events", [])
        logger.info(f"Found {len(events)} events.")
        if not events:
            await cl.Message(content="📅 No upcoming events found.").send()
            return

        content = "## 📅 Upcoming Events\n\n"

        for event in events:
            logger.debug(f"Event: {event}")
            content += f"**{event.get('title', 'No title')}**\n"
            content += f"📅 Date: {event.get('date', 'No date')}\n"
            if event.get('time'):
                content += f"🕐 Time: {event['time']}\n"
            if event.get('location'):
                content += f"📍 Location: {event['location']}\n"
            if event.get('description'):
                content += f"📝 Description: {event['description']}\n"
            content += "\n---\n\n"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_events: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

async def display_event_added(result: Dict[str, Any]):
    try:
        logger.debug(f"Event added result: {json.dumps(result, indent=2)}")
        if result.get("success"):
            event = result.get("event", {})
            content = f"✅ **Event Added Successfully!**\n\n"
            content += f"**{event.get('title', 'No title')}**\n"
            content += f"📅 Date: {event.get('date', 'No date')}\n"
            if event.get('time'):
                content += f"🕐 Time: {event['time']}\n"
            if event.get('location'):
                content += f"📍 Location: {event['location']}\n"
            if event.get('description'):
                content += f"📝 Description: {event['description']}\n"
        else:
            content = f"❌ Failed to add event: {result.get('error', 'Unknown error')}"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_event_added: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

async def display_event_deleted(result: Dict[str, Any]):
    try:
        logger.debug(f"Event deleted result: {json.dumps(result, indent=2)}")
        if result.get("success"):
            content = "✅ **Event deleted successfully!**"
        else:
            content = f"❌ Failed to delete event: {result.get('error', 'Unknown error')}"

        await cl.Message(content=content).send()
    except Exception as e:
        logger.error(f"Exception in display_event_deleted: {e}")
        await cl.Message(content=f"❌ Exception: {e}").send()

@cl.on_stop
async def stop():
    logger.info("Stopping session, disconnecting MCP client.")
    await mcp_client.disconnect()

if __name__ == "__main__":
    cl.run()
