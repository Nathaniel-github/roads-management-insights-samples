# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
import os
import gzip
import re
from pathlib import Path
from brotli_asgi import BrotliMiddleware

from backend.fetch_data import (
    fetch_latest_historical_data,
    fetch_hourly_aggregated_data,
    fetch_city_details,
    fetch_route_metrics,
    fetch_average_travel_time_by_hour,
)
from backend.env_manager import create_ui_env_file

import json
import uuid
import asyncio
from sse_starlette.sse import EventSourceResponse
from absl import flags
from google.genai import types
from google.adk import runners
from google.adk.agents.run_config import StreamingMode
from backend.rmi_agent.agents.rmi_agent import ROOT_AGENT

# read .env file in os environment
load_dotenv()


application_mode = os.getenv("APPLICATION_MODE", "demo")
google_maps_api_key = os.getenv("GOOGLE_API_KEY", "")
print(f"Application Mode: {application_mode}")
print(f"Google Maps API Key: {'Set' if google_maps_api_key else 'Not set'}")

# Create the .env file on startup
create_ui_env_file(google_maps_api_key, application_mode)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

app.add_middleware(BrotliMiddleware, quality=5, minimum_size=1000)

app.mount("/assets", StaticFiles(directory="ui/dist/assets"), name="assets")

@app.get("/api/latest/{city_name}")
async def get_latest_historical_data(city_name: str):
    city_name = city_name.upper()
    geojson_data = fetch_latest_historical_data(city_name)

    if not geojson_data:
        raise HTTPException(status_code=500, detail="Error fetching latest data")

    return geojson_data


@app.post("/api/historical/{city_name}")
async def get_hourly_aggregated_data(city_name: str, request: Request):
    try:
        body = await request.json()  # get JSON as dict

        display_names = body.get("display_names", [])
        from_date = body.get("from_date")
        to_date = body.get("to_date")
        weekdays = body.get("weekdays", [])

        city_name = city_name.upper()

        aggregated_data = fetch_hourly_aggregated_data(
            city_name, display_names, from_date, to_date, weekdays
        )

        if not aggregated_data:
            raise HTTPException(status_code=500, detail="Error fetching data")

        return aggregated_data
    except Exception as e:
        print(f"DEBUGGING ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Debugging Error: {e}")


@app.post("/api/route-metrics/{city_name}")
async def get_route_metrics(city_name: str, request: Request):
    """
    API endpoint to calculate route metrics including:
    - Planning Time Index (PTI)
    - Travel Time Index (TTI)
    - Average Travel Time
    - Free Flow Time
    - 95th Percentile Travel Time

    Request body:
    {
        "display_names": ["route1", "route2"],  // Optional, empty for all routes
        "from_date": "2024-01-01",
        "to_date": "2024-01-31",
        "weekdays": [1, 2, 3, 4, 5]  // 1=Sunday, 7=Saturday
    }
    """
    try:
        body = await request.json()

        display_names = body.get("display_names", [])
        from_date = body.get("from_date")
        to_date = body.get("to_date")
        weekdays = body.get("weekdays", [])

        # Validate required parameters
        if not from_date or not to_date:
            raise HTTPException(
                status_code=400, detail="from_date and to_date are required"
            )

        if not weekdays:
            raise HTTPException(status_code=400, detail="weekdays list is required")

        city_name = city_name.upper()

        route_metrics = fetch_route_metrics(
            city_name, display_names, from_date, to_date, weekdays
        )

        if route_metrics is None:
            raise HTTPException(
                status_code=500, detail="Error calculating route metrics"
            )

        return route_metrics
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUGGING ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Debugging Error: {e}")

@app.post("/api/average-travel-time-by-hour/{city_name}")
async def get_average_travel_time_by_hour(city_name: str, request: Request):
    """
    API endpoint to calculate average travel time by hour for all routes or specific routes.
    Similar to calculateAverageTravelTimeByHour in TypeScript.

    Request body:
    {
        "display_names": ["route1", "route2"],  // Optional, empty for all routes
        "from_date": "2024-01-01",
        "to_date": "2024-01-31",
        "weekdays": [1, 2, 3, 4, 5]  // 1=Sunday, 7=Saturday
    }

    Returns:
    {
        "routeHourlyAverages": {
            "route_id_1": {0: 120.5, 1: 125.3, ...},
            "route_id_2": {0: 180.2, 1: 185.7, ...}
        },
        "hourlyTotalAverages": {
            0: {"totalDuration": 3000.5, "count": 150},
            1: {"totalDuration": 3100.2, "count": 155},
            ...
        }
    }
    """
    try:
        body = await request.json()

        display_names = body.get("display_names", [])
        from_date = body.get("from_date")
        to_date = body.get("to_date")
        weekdays = body.get("weekdays", [])

        # Validate required parameters
        if not from_date or not to_date:
            raise HTTPException(
                status_code=400, detail="from_date and to_date are required"
            )

        if not weekdays:
            raise HTTPException(status_code=400, detail="weekdays list is required")

        city_name = city_name.upper()

        average_travel_time_data = fetch_average_travel_time_by_hour(
            city_name, display_names, from_date, to_date, weekdays
        )

        if average_travel_time_data is None:
            raise HTTPException(
                status_code=500, detail="Error calculating average travel time by hour"
            )

        return average_travel_time_data
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUGGING ERROR: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Debugging Error: {e}")


@app.get("/api/data/{file_path:path}")
async def get_data_file(file_path: str):
    """
    API endpoint to serve files from data directory.
    Automatically decompresses .gz files if they exist, or serves uncompressed files.
    """
    # Construct the full path to the file
    file_full_path = Path("data") / file_path
    compressed_file_path = Path("data") / f"{file_path}.gz"

    # Security check: ensure the path is within data directory
    try:
        file_full_path = file_full_path.resolve()
        compressed_file_path = compressed_file_path.resolve()
        data_path = Path("data").resolve()
        # Ensure paths are within data_path
        file_full_path.relative_to(data_path)
        compressed_file_path.relative_to(data_path)
    except (ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Determine media type based on file extension
    media_type = "application/json" if file_path.endswith('.json') else "text/csv" if file_path.endswith('.csv') else "application/octet-stream"

    # Check if compressed version exists first
    if compressed_file_path.exists() and compressed_file_path.is_file():
        try:
            # Decompress and serve the file
            with gzip.open(compressed_file_path, 'rb') as f:
                content = f.read()
            
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'inline; filename="{file_full_path.name}"',
                    "Cache-Control": "public, max-age=3600"
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error decompressing file: {str(e)}")
    
    # Fall back to uncompressed file if it exists
    elif file_full_path.exists() and file_full_path.is_file():
        return FileResponse(
            path=str(file_full_path),
            filename=file_full_path.name,
            media_type=media_type,
        )
    
    else:
        raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/cities/metadata")
async def get_city_metadata():
    city_metadata = fetch_city_details()

    if not city_metadata:
        raise HTTPException(status_code=500, detail="Error fetching city metadata")

    return city_metadata


def _parse_geometry(geom_val: Any) -> dict[str, Any] | None:
    if not geom_val:
        return None
    try:
        import json

        if isinstance(geom_val, str):
            geom_val = json.loads(geom_val)
        if isinstance(geom_val, dict) and "coordinates" in geom_val:
            geom_type = geom_val.get("type") or "LineString"
            return {
                "type": geom_type,
                "coordinates": geom_val["coordinates"],
            }
    except Exception:
        pass
    return None


def _extract_features_from_rows(
    table_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not table_rows or not isinstance(table_rows, list):
        return []

    seen_ids = set()
    unique_route_rows = []
    for r in table_rows:
        if isinstance(r, dict) and "selected_route_id" in r:
            rid = r.get("selected_route_id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                unique_route_rows.append(r)

    if not unique_route_rows:
        return []

    features = []
    for r in unique_route_rows:
        rid = r.get("selected_route_id")
        geom = _parse_geometry(r.get("route_geometry"))
        disp_name = r.get("display_name") or rid

        if geom:
            dur = 0
            for k in (
                "duration_in_seconds",
                "avg_duration_in_seconds",
                "duration",
                "max_duration",
            ):
                if r.get(k) is not None:
                    try:
                        dur = float(r[k])
                        break
                    except (ValueError, TypeError):
                        pass

            static_dur = 0
            for k in (
                "static_duration_in_seconds",
                "avg_static_duration_in_seconds",
                "static_duration",
            ):
                if r.get(k) is not None:
                    try:
                        static_dur = float(r[k])
                        break
                    except (ValueError, TypeError):
                        pass

            d_time = 0.0
            for k in (
                "peak_delay_seconds",
                "peak_delay_in_seconds",
                "traffic_delay_seconds",
                "traffic_delay_in_seconds",
                "delay_seconds",
                "delay_in_seconds",
                "delay_time",
                "delay",
            ):
                if r.get(k) is not None:
                    try:
                        d_time = float(r[k])
                        break
                    except (ValueError, TypeError):
                        pass

            if d_time == 0.0 and dur and static_dur:
                d_time = dur - static_dur

            # Real ratio when both durations exist; otherwise 0.0 so the UI
            # renders the route grey ("no data") instead of a fake severity.
            if static_dur and static_dur > 0 and dur > 0:
                d_ratio = dur / static_dur
            else:
                d_ratio = 0.0

            features.append({
                "type": "Feature",
                "geometry": geom,
                "properties": {
                    **r,
                    "id": rid,
                    "selected_route_id": rid,
                    "name": disp_name,
                    "duration": dur,
                    "static_duration": static_dur,
                    "delay_ratio": d_ratio,
                    "delay_time": d_time,
                },
            })
    return features


@app.get("/api/agent/stream")
async def stream_agent(message: str, city: str = "boston", session_id: str = None):
    """Server-Sent Events endpoint for RMI Agent streaming responses."""
    async def event_generator():
        try:
            try:
                flags.FLAGS([""])
            except Exception:
                pass

            curr_session_id = session_id or f"session-{uuid.uuid4().hex}"
            runner = runners.InMemoryRunner(agent=ROOT_AGENT)
            if not session_id:
                await runner.session_service.create_session(
                    app_name=runner.app_name, session_id=curr_session_id, user_id="user"
                )

            run_config = runners.RunConfig(
                streaming_mode=StreamingMode.SSE
            )

            async def _route_features():
                sess = await runner.session_service.get_session(
                    app_name=runner.app_name,
                    session_id=curr_session_id,
                    user_id="user",
                )
                state = sess.state if sess else {}
                table_rows = (
                    state.get("candidate_table")
                    or state.get("_last_sql_result")
                    or []
                )
                return _extract_features_from_rows(table_rows)

            yield {
                "event": "status",
                "data": json.dumps({"status": f"Querying BigQuery ({city})..."})
            }

            routes_rendered = False
            streamed_turn_partial = False
            accumulated_text = ""

            _system_suffix = (
                "\n\n[System instruction: If this request requires"
                " finding specific routes that can be visualized"
                " on a map, your final SQL query MUST explicitly"
                " select 'selected_route_id', 'duration',"
                " 'static_duration', and 'ST_ASGEOJSON"
                "(route_geometry) AS route_geometry' so the UI"
                " can construct the visualizations. If this is"
                " purely a high-level analytical query, ignore"
                " this rule."
                "\n\nAfter your final natural-language response,"
                " on a new line emit exactly the tag"
                " [SUGGESTIONS] followed by a JSON array of 2-3"
                " short, specific follow-up questions the user"
                " might logically ask next based on what was just"
                " discussed. Example:\n[SUGGESTIONS]"
                '[\"Which of those routes had the worst delay'
                ' ratio?\", \"Show the hourly breakdown for'
                ' Route X\"]'
                "\nDo NOT wrap the JSON in a code fence.]"
            )

            async for event in runner.run_async(
                user_id="user",
                session_id=curr_session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(
                        text=message + _system_suffix
                    )],
                ),
                run_config=run_config,
            ):
                if event.content and event.content.parts:
                    is_partial = getattr(event, "is_partial", False)
                    for part in event.content.parts:
                        if getattr(part, "thought", False) and part.text:
                            yield {
                                "event": "thinking",
                                "data": json.dumps({"text": part.text})
                            }
                        elif getattr(part, "function_call", None):
                            streamed_turn_partial = False
                            tool_name = part.function_call.name
                            tool_args = (
                                dict(part.function_call.args)
                                if part.function_call.args
                                else {}
                            )
                            yield {
                                "event": "tool_call",
                                "data": json.dumps({
                                    "name": tool_name,
                                    "args": tool_args,
                                }),
                            }
                            if tool_name == "present_final_table":
                                try:
                                    features = await _route_features()
                                    if features:
                                        routes_rendered = True
                                        yield {
                                            "event": "render_agent_routes",
                                            "data": json.dumps({
                                                "features": features,
                                                "description": tool_args.get(
                                                    "description", ""
                                                ),
                                            }),
                                        }
                                    sess = await runner.session_service.get_session(
                                        app_name=runner.app_name,
                                        session_id=curr_session_id,
                                        user_id="user",
                                    )
                                    state = sess.state if sess else {}
                                    sql = (
                                        state.get("candidate_query")
                                        or state.get("_last_sql_query")
                                    )
                                    if sql:
                                        yield {
                                            "event": "sql_query",
                                            "data": json.dumps(
                                                {"query": sql}
                                            ),
                                        }
                                    table_rows = (
                                        state.get("candidate_table")
                                        or state.get("_last_sql_result")
                                        or []
                                    )
                                    if table_rows:
                                        yield {
                                            "event": "table_data",
                                            "data": json.dumps(
                                                {
                                                    "rows": table_rows,
                                                    "description": tool_args.get(
                                                        "description", ""
                                                    ),
                                                },
                                                default=str,
                                            ),
                                        }
                                except Exception as extract_err:
                                    print(
                                        "Error processing agent routes for"
                                        f" map: {extract_err}"
                                    )
                        elif part.text and not getattr(part, "thought", False):
                            if is_partial:
                                streamed_turn_partial = True
                                accumulated_text += part.text
                                yield {
                                    "event": "text_chunk",
                                    "data": json.dumps({"text": part.text}),
                                }
                            elif not streamed_turn_partial:
                                accumulated_text += part.text
                                yield {
                                    "event": "text_chunk",
                                    "data": json.dumps({"text": part.text}),
                                }

            if not routes_rendered:
                try:
                    features = await _route_features()
                    if features:
                        yield {
                            "event": "render_agent_routes",
                            "data": json.dumps({
                                "features": features,
                                "description": "Query results",
                            }),
                        }
                    sess = await runner.session_service.get_session(
                        app_name=runner.app_name,
                        session_id=curr_session_id,
                        user_id="user",
                    )
                    state = sess.state if sess else {}
                    sql = (
                        state.get("candidate_query")
                        or state.get("_last_sql_query")
                    )
                    if sql:
                        yield {
                            "event": "sql_query",
                            "data": json.dumps({"query": sql}),
                        }
                    table_rows = (
                        state.get("candidate_table")
                        or state.get("_last_sql_result")
                        or []
                    )
                    if table_rows:
                        yield {
                            "event": "table_data",
                            "data": json.dumps(
                                {
                                    "rows": table_rows,
                                    "description": "Query results",
                                },
                                default=str,
                            ),
                        }
                except Exception as render_err:
                    print(f"Error rendering fallback routes: {render_err}")

            # Parse [SUGGESTIONS] from the accumulated agent text.
            _sug_match = re.search(
                r"\[SUGGESTIONS\]\s*:?\s*(?:```(?:json)?\s*)?"
                r"(\[[\s\S]*?\])(?:\s*```)?",
                accumulated_text,
            )
            if _sug_match:
                try:
                    _sug_list = json.loads(_sug_match.group(1))
                    if isinstance(_sug_list, list) and _sug_list:
                        print(
                            f"[RMI Agent] Emitted {len(_sug_list)} suggestions:"
                            f" {_sug_list}"
                        )
                        yield {
                            "event": "suggestions",
                            "data": json.dumps({"suggestions": _sug_list}),
                        }
                except (json.JSONDecodeError, TypeError) as parse_err:
                    print(
                        "[RMI Agent] Suggestions JSON decode error:"
                        f" {parse_err}"
                    )
            else:
                print(
                    "[RMI Agent] No suggestions tag found in accumulated"
                    f" text ({len(accumulated_text)} chars)"
                )

            yield {
                "event": "done",
                "data": json.dumps({"status": "SUCCESS"})
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)})
            }

    return EventSourceResponse(event_generator())


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react_app(full_path: str):
    html = open("ui/dist/index.html", "r").read()
    if not application_mode == "demo":
        html = html.replace('window.DEMO_MODE = "true"', 'window.DEMO_MODE = "false"')
    
    # Replace Google Maps API key using regex to handle all cases
    if google_maps_api_key:
        # Replace any existing key with our API key
        # Pattern matches ?key=anything& or ?key=anything followed by end of string or space
        html = re.sub(r'(\?key=)[^&\s"]*', rf'\g<1>{google_maps_api_key}', html)
    else:
        # Remove the key parameter entirely if no API key is provided
        # Handle ?key=value& (key is first parameter)
        html = re.sub(r'\?key=[^&\s"]*&', '?', html)
        # Handle &key=value (key is not first parameter)
        html = re.sub(r'&key=[^&\s"]*', '', html)
        # Handle ?key=value (key is only parameter)
        html = re.sub(r'\?key=[^&\s"]*', '', html)
    
    return html
