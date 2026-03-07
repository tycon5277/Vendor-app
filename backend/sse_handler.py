"""
SSE Handler - Server-Sent Events for real-time Genie delivery stream
Handles persistent connections with Redis pub/sub
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from starlette.responses import StreamingResponse
from redis_manager import (
    subscribe_genie, register_sse_connection, unregister_sse_connection,
    get_genie_pending_request
)

logger = logging.getLogger("sse_handler")


async def genie_delivery_stream(genie_id: str, zone_id: str = None) -> AsyncGenerator[str, None]:
    """
    SSE stream generator for a Genie.
    Subscribes to Redis pub/sub channel for this genie and yields events.
    """
    pubsub = None
    try:
        # Register connection
        await register_sse_connection(genie_id, zone_id)
        logger.info(f"SSE connected: genie {genie_id} (zone: {zone_id})")

        # Send initial connection event
        yield format_sse("connected", {
            "genie_id": genie_id,
            "zone_id": zone_id,
            "message": "Connected to delivery stream",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Check if there's a pending request already
        pending = await get_genie_pending_request(genie_id)
        if pending:
            yield format_sse("pending_request", pending)

        # Subscribe to genie's personal channel
        pubsub = await subscribe_genie(genie_id)

        # Main event loop
        heartbeat_interval = 25  # seconds
        last_heartbeat = asyncio.get_event_loop().time()

        while True:
            try:
                # Non-blocking message check
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=2.0
                )

                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    event_type = data.get("event", "update")
                    event_data = data.get("data", {})
                    yield format_sse(event_type, event_data)

                # Send heartbeat to keep connection alive
                now = asyncio.get_event_loop().time()
                if now - last_heartbeat >= heartbeat_interval:
                    yield format_sse("heartbeat", {
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    last_heartbeat = now

            except asyncio.TimeoutError:
                # Normal - no message received, send heartbeat if needed
                now = asyncio.get_event_loop().time()
                if now - last_heartbeat >= heartbeat_interval:
                    yield format_sse("heartbeat", {
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    last_heartbeat = now
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SSE error for genie {genie_id}: {e}")
                yield format_sse("error", {"message": "Connection error, please reconnect"})
                break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"SSE stream error for genie {genie_id}: {e}")
    finally:
        # Cleanup
        if pubsub:
            await pubsub.unsubscribe(f"genie:{genie_id}")
            await pubsub.aclose()
        await unregister_sse_connection(genie_id)
        logger.info(f"SSE disconnected: genie {genie_id}")


def format_sse(event: str, data: dict) -> str:
    """Format data as an SSE event string"""
    json_data = json.dumps(data)
    return f"event: {event}\ndata: {json_data}\n\n"


def create_sse_response(generator: AsyncGenerator) -> StreamingResponse:
    """Create a StreamingResponse for SSE"""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        }
    )
