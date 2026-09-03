// Copyright 2025 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome"
import CheckIcon from "@mui/icons-material/Check"
import CloseIcon from "@mui/icons-material/Close"
import CloseFullscreenIcon from "@mui/icons-material/CloseFullscreen"
import ContentCopyIcon from "@mui/icons-material/ContentCopy"
import DownloadIcon from "@mui/icons-material/Download"
import ExpandLessIcon from "@mui/icons-material/ExpandLess"
import ExpandMoreIcon from "@mui/icons-material/ExpandMore"
import OpenInFullIcon from "@mui/icons-material/OpenInFull"
import SendIcon from "@mui/icons-material/Send"
import {
  Box,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material"
import { styled } from "@mui/material/styles"
import React, { useEffect, useRef, useState } from "react"
import ReactMarkdown, { type Components } from "react-markdown"
import remarkGfm from "remark-gfm"

import { getRouteColor } from "../../data/common/route-color"
import { convertToGeoJSON } from "../../deck-gl/helpers"
import { useAppStore } from "../../store"
import { RouteSegment } from "../../types/route-segment"
import { getEffectivePanelWidth } from "./layout"

const DrawerContainer = styled(Paper)({
  position: "fixed",
  top: "64px",
  left: 0,
  bottom: 0,
  zIndex: 100,
  display: "flex",
  flexDirection: "column",
  backgroundColor: "#ffffff",
  boxShadow: "4px 0 20px rgba(0, 0, 0, 0.08)",
  borderRight: "1px solid #e8eaed",
  overflow: "hidden",
})

const Header = styled(Box)({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "16px 20px",
  backgroundColor: "#f8f9fa",
  borderBottom: "1px solid #e8eaed",
  boxShadow: "0 1px 2px rgba(0, 0, 0, 0.04)",
  zIndex: 1,
})

const MessagesContainer = styled(Box)({
  flex: 1,
  overflowY: "auto",
  padding: "16px",
  display: "flex",
  flexDirection: "column",
  gap: "16px",
  "&::-webkit-scrollbar": { width: "8px" },
  "&::-webkit-scrollbar-thumb": {
    backgroundColor: "#dadce0",
    borderRadius: "4px",
  },
  "&::-webkit-scrollbar-thumb:hover": { backgroundColor: "#bdc1c6" },
})

const InputContainer = styled(Box)({
  padding: "16px",
  borderTop: "1px solid #e8eaed",
  backgroundColor: "#ffffff",
  display: "flex",
  flexDirection: "column",
  gap: "12px",
})

interface ChatMessage {
  id: string
  sender: "user" | "agent"
  text: string
  thoughts?: string[]
  tools?: string[]
  status?: string
  isStreaming?: boolean
  renderedRoutes?: RouteSegment[]
  sqlQuery?: string
  tableData?: Record<string, unknown>[]
}

// Shape of a feature emitted by the server's render_agent_routes SSE event.
// The server (_extract_features_from_rows) normalizes these fields.
interface RawAgentFeatureProps {
  id?: string
  selected_route_id?: string
  name?: string
  display_name?: string
  duration?: number
  static_duration?: number
  delay_time?: number
  delay_ratio?: number
  length?: number
}

interface RawAgentFeature {
  geometry?: { coordinates?: number[][] }
  properties?: RawAgentFeatureProps
}

const QUICK_PROMPTS = [
  "Scan the network for segments where current speed deviates more than 20% from the 30-day historical norm.",
  "Which routes have the highest count of 'TRAFFIC_JAM' speed reading intervals? Return the top 10.",
  "Which active routes experienced a travel time more than double their static baseline between 2026-07-14 and 2026-07-16?",
]

export const AgentSidePanel: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState("")
  const [suggestions, setSuggestions] = useState<string[]>(QUICK_PROMPTS)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [showThoughts, setShowThoughts] = useState<Record<string, boolean>>({})
  const [showRoutes, setShowRoutes] = useState<Record<string, boolean>>({})
  const [showSql, setShowSql] = useState<Record<string, boolean>>({})
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const selectedCity = useAppStore((state) => state.selectedCity)
  const setActiveTab = useAppStore((state) => state.setActiveTab)
  const setSelectedRouteId = useAppStore((state) => state.setSelectedRouteId)
  const map = useAppStore((state) => state.refs.map)
  const agentPanelWidth = useAppStore((state) => state.agentPanelWidth)
  const agentPanelExpanded = useAppStore((state) => state.agentPanelExpanded)
  const setAgentPanelWidth = useAppStore((state) => state.setAgentPanelWidth)
  const setAgentPanelExpanded = useAppStore(
    (state) => state.setAgentPanelExpanded,
  )
  const [isResizing, setIsResizing] = useState(false)
  const isResizingRef = useRef(false)
  const effectiveWidth = getEffectivePanelWidth(
    agentPanelWidth,
    agentPanelExpanded,
  )

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close()
    }
  }, [])

  // Drag-to-resize: the panel is docked at left:0, so the pointer's X position
  // is the desired width. Listeners live on window so the drag keeps tracking
  // even when the cursor moves over the map. Width clamping/persistence is
  // handled by the store's setAgentPanelWidth.
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingRef.current) return
      setAgentPanelWidth(e.clientX)
    }
    const handleMouseUp = () => {
      if (!isResizingRef.current) return
      isResizingRef.current = false
      setIsResizing(false)
    }
    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)
    return () => {
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [setAgentPanelWidth])

  const handleResizeStart = (e: React.MouseEvent) => {
    if (agentPanelExpanded) return
    e.preventDefault()
    isResizingRef.current = true
    setIsResizing(true)
  }

  const handleCopyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  const downloadCsv = (
    rows: Record<string, unknown>[],
    filename: string,
  ) => {
    if (!rows.length) return
    const headers = Object.keys(rows[0])
    const escape = (v: unknown): string => {
      const s = v == null ? "" : String(v)
      return s.includes(",") || s.includes('"') || s.includes("\n")
        ? `"${s.replace(/"/g, '""')}"`
        : s
    }
    const lines = [
      headers.map(escape).join(","),
      ...rows.map((r) => headers.map((h) => escape(r[h])).join(",")),
    ]
    const blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const toggleThoughts = (id: string) => {
    setShowThoughts((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const toggleRoutes = (id: string) => {
    setShowRoutes((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const toggleSql = (id: string) => {
    setShowSql((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const handleRouteClick = (route: RouteSegment) => {
    setSelectedRouteId(route.id)
    useAppStore.getState().setSelectedRouteSegment(route)
    const currentMap = map || useAppStore.getState().refs.map
    if (currentMap && route.path && route.path.length > 0) {
      const bounds = new google.maps.LatLngBounds()
      route.path.forEach((pt) => bounds.extend(pt))
      currentMap.fitBounds(bounds, 100)
    }
  }

  const handleSend = (queryText: string) => {
    if (!queryText.trim()) return

    const userMsgId = `user-${Date.now()}`
    const agentMsgId = `agent-${Date.now()}`

    const newUserMsg: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: queryText,
    }

    const newAgentMsg: ChatMessage = {
      id: agentMsgId,
      sender: "agent",
      text: "",
      thoughts: [],
      tools: [],
      status: "Connecting...",
      isStreaming: true,
    }

    setMessages((prev) => [...prev, newUserMsg, newAgentMsg])
    setInputText("")
    setSuggestions([])

    const cityId = selectedCity?.id || "boston"
    const sessionParam = sessionId
      ? `&session_id=${encodeURIComponent(sessionId)}`
      : ""
    const url = `/api/agent/stream?message=${encodeURIComponent(queryText)}&city=${encodeURIComponent(cityId)}${sessionParam}`

    eventSourceRef.current?.close()
    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    const updateAgentMsg = (patch: Partial<ChatMessage>) => {
      setMessages((prev) =>
        prev.map((msg) => (msg.id === agentMsgId ? { ...msg, ...patch } : msg)),
      )
    }

    eventSource.addEventListener("status", (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.session_id) {
          setSessionId(data.session_id)
        }
        updateAgentMsg({ status: data.status })
      } catch (e) {
        console.error("Failed to parse agent status event", e)
      }
    })

    eventSource.addEventListener("thinking", (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id !== agentMsgId) return msg
            const thoughts = msg.thoughts || []
            return {
              ...msg,
              thoughts: thoughts.includes(data.text)
                ? thoughts
                : [...thoughts, data.text],
              status: "Thinking...",
            }
          }),
        )
      } catch (e) {
        console.error("Failed to parse agent thinking event", e)
      }
    })

    eventSource.addEventListener("tool_call", (event) => {
      try {
        const data = JSON.parse(event.data)
        const toolDesc = `${data.name}(${JSON.stringify(data.args || {})})`
        setMessages((prev) =>
          prev.map((msg) => {
            if (msg.id !== agentMsgId) return msg
            const tools = msg.tools || []
            return {
              ...msg,
              tools: tools.includes(toolDesc) ? tools : [...tools, toolDesc],
              status: `Querying BigQuery: ${data.name}...`,
            }
          }),
        )
      } catch (e) {
        console.error("Failed to parse agent tool_call event", e)
      }
    })

    eventSource.addEventListener("text_chunk", (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId
              ? {
                  ...msg,
                  text: msg.text + data.text,
                  status: "Generating answer...",
                }
              : msg,
          ),
        )
      } catch (e) {
        console.error("Failed to parse agent text_chunk event", e)
      }
    })

    eventSource.addEventListener("render_agent_routes", (event) => {
      try {
        const data = JSON.parse(event.data)
        const rawFeatures = data.features || []
        // The server (_extract_features_from_rows) already normalizes and
        // computes delay_ratio/delay_time, so trust those fields directly and
        // reuse the shared getRouteColor helper for coloring.
        const routeSegments: RouteSegment[] = rawFeatures.map(
          (f: RawAgentFeature) => {
            const props: RawAgentFeatureProps = f.properties || {}
            const geom = f.geometry
            let rawCoords: number[][] = []
            if (
              geom?.type === "MultiLineString" &&
              Array.isArray(geom.coordinates)
            ) {
              rawCoords = geom.coordinates.flat(1)
            } else if (Array.isArray(geom?.coordinates)) {
              rawCoords = geom.coordinates
            }
            const path = rawCoords.map((c: number[]) => ({
              lng: c[0],
              lat: c[1],
            }))
            const duration = props.duration || 0
            const staticDuration = props.static_duration || 0
            const delayTime = props.delay_time ?? 0
            const delayRatio = props.delay_ratio ?? 1
            return {
              id: props.id || props.selected_route_id || "",
              name: props.name || props.display_name || props.id,
              path,
              duration,
              staticDuration,
              delayRatio,
              delayTime,
              color: getRouteColor(delayRatio, delayTime),
              length: props.length || 0,
            }
          },
        )

        // Preserve the native GeoJSON geometry (LineString or MultiLineString)
        const geoJsonFeatures = rawFeatures.map(
          (f: RawAgentFeature, idx: number) => {
            const seg = routeSegments[idx]
            return {
              type: "Feature",
              geometry: f.geometry || {
                type: "LineString",
                coordinates: seg?.path.map((p) => [p.lng, p.lat]) || [],
              },
              properties: {
                ...(f.properties || {}),
                id: seg?.id || "unknown",
                name: seg?.name || "unknown",
                color: seg?.color || "#000000",
                delay: seg?.delayTime || 0,
                delayRatio: seg?.delayRatio || 0,
                duration: seg?.duration || 0,
                staticDuration: seg?.staticDuration || 0,
                length: seg?.length || 0,
              },
            }
          },
        )

        useAppStore.getState().setMapData({
          type: "FeatureCollection",
          features: geoJsonFeatures,
        })

        updateAgentMsg({ renderedRoutes: routeSegments })

        const currentMap = map || useAppStore.getState().refs.map
        if (currentMap && routeSegments.length > 0) {
          const bounds = new google.maps.LatLngBounds()
          let hasPoints = false
          routeSegments.forEach((seg) => {
            seg.path.forEach((pt) => {
              bounds.extend(pt)
              hasPoints = true
            })
          })
          if (hasPoints && !bounds.isEmpty()) {
            currentMap.fitBounds(bounds, 50)
          }
        }
      } catch (err) {
        console.error("Error processing agent rendered routes:", err)
      }
    })

    eventSource.addEventListener("sql_query", (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.query) {
          updateAgentMsg({ sqlQuery: data.query })
        }
      } catch (e) {
        console.error("Failed to parse sql_query event", e)
      }
    })

    eventSource.addEventListener("table_data", (event) => {
      try {
        const data = JSON.parse(event.data)
        if (Array.isArray(data.rows) && data.rows.length) {
          updateAgentMsg({ tableData: data.rows })
        }
      } catch (e) {
        console.error("Failed to parse table_data event", e)
      }
    })

    eventSource.addEventListener("suggestions", (event) => {
      try {
        const data = JSON.parse(event.data)
        if (Array.isArray(data.suggestions) && data.suggestions.length) {
          console.log("[RMI Agent] Received suggestions:", data.suggestions)
          setSuggestions(data.suggestions)
        }
      } catch (e) {
        console.error("[RMI Agent] Failed to parse suggestions event:", e)
      }
    })

    eventSource.addEventListener("done", () => {
      // Strip [SUGGESTIONS]... from the displayed text.
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === agentMsgId
            ? {
                ...msg,
                isStreaming: false,
                status: undefined,
                text: msg.text
                  .replace(/\n?\[SUGGESTIONS\][\s\S]*$/, "")
                  .trimEnd(),
              }
            : msg,
        ),
      )
      eventSource.close()
    })

    eventSource.addEventListener("error", () => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === agentMsgId
            ? {
                ...msg,
                isStreaming: false,
                status: undefined,
                text:
                  msg.text ||
                  "Sorry, an error occurred while querying the RMI agent.",
              }
            : msg,
        ),
      )
      eventSource.close()
    })
  }

  const handleClose = () => {
    setActiveTab("dashboard")
  }

  return (
    <DrawerContainer
      elevation={2}
      sx={{
        width: { xs: "100%", md: `${effectiveWidth}px` },
        transition: isResizing
          ? "none"
          : "width 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
      }}
    >
      <Header>
        <Box sx={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AutoAwesomeIcon sx={{ color: "#1a73e8" }} />
          <Box>
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 700, lineHeight: 1.2 }}
            >
              Roads AI Assistant
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {selectedCity?.name || "Boston"} Data (BigQuery)
            </Typography>
          </Box>
        </Box>
        <Box sx={{ display: "flex", alignItems: "center", gap: "4px" }}>
          <IconButton
            size="small"
            onClick={() => setAgentPanelExpanded(!agentPanelExpanded)}
            title={agentPanelExpanded ? "Collapse panel" : "Expand panel"}
            sx={{ display: { xs: "none", md: "inline-flex" } }}
          >
            {agentPanelExpanded ? (
              <CloseFullscreenIcon fontSize="small" />
            ) : (
              <OpenInFullIcon fontSize="small" />
            )}
          </IconButton>
          <IconButton size="small" onClick={handleClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        </Box>
      </Header>

      <MessagesContainer>
        {messages.length === 0 ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              gap: "16px",
              my: "auto",
              py: 2,
            }}
          >
            <Box sx={{ textAlign: "center" }}>
              <AutoAwesomeIcon
                sx={{ color: "#1a73e8", fontSize: 32, mb: 1 }}
              />
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Ask the Roads AI Assistant
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 0.5 }}
              >
                Explore historical travel times, route slowdowns, and
                congestion in {selectedCity?.name || "Boston"}.
              </Typography>
            </Box>
            <Box
              sx={{ display: "flex", flexDirection: "column", gap: "10px" }}
            >
              {QUICK_PROMPTS.map((prompt, idx) => (
                <Box
                  key={idx}
                  onClick={() => handleSend(prompt)}
                  sx={{
                    p: 1.5,
                    borderRadius: "12px",
                    border: "1px solid #e8eaed",
                    backgroundColor: "#fff",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    transition: "all 0.15s ease",
                    "&:hover": {
                      backgroundColor: "#f8f9fa",
                      borderColor: "#1a73e8",
                      transform: "translateY(-1px)",
                      boxShadow: "0 2px 8px rgba(26,115,232,0.12)",
                    },
                  }}
                >
                  <AutoAwesomeIcon
                    sx={{ color: "#1a73e8", fontSize: 18, flexShrink: 0 }}
                  />
                  <Typography variant="body2" sx={{ color: "#202124" }}>
                    {prompt}
                  </Typography>
                </Box>
              ))}
            </Box>
          </Box>
        ) : (
          messages.map((msg) => (
            <Box
              key={msg.id}
              sx={{
                alignSelf:
                  msg.sender === "user" ? "flex-end" : "stretch",
                maxWidth: msg.sender === "user" ? "85%" : "100%",
                width: msg.sender === "user" ? "auto" : "100%",
                minWidth: 0,
              }}
            >
              {msg.sender === "agent" && (
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: "6px",
                    mb: 0.75,
                  }}
                >
                  <AutoAwesomeIcon sx={{ fontSize: 16, color: "#1a73e8" }} />
                  <Typography
                    variant="caption"
                    sx={{
                      fontWeight: 700,
                      color: "#5f6368",
                      letterSpacing: "0.2px",
                      flex: 1,
                    }}
                  >
                    Assistant
                  </Typography>
                  {!msg.isStreaming && msg.text && (
                    <Tooltip
                      title={
                        copiedId === msg.id
                          ? "Copied!"
                          : "Copy response"
                      }
                    >
                      <IconButton
                        size="small"
                        onClick={() =>
                          handleCopyText(msg.id, msg.text)
                        }
                        sx={{
                          p: 0.25,
                          color:
                            copiedId === msg.id
                              ? "#34a853"
                              : "#9aa0a6",
                          "&:hover": { color: "#5f6368" },
                        }}
                      >
                        {copiedId === msg.id ? (
                          <CheckIcon sx={{ fontSize: 14 }} />
                        ) : (
                          <ContentCopyIcon
                            sx={{ fontSize: 14 }}
                          />
                        )}
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              )}
              <Box
                sx={{
                  backgroundColor:
                    msg.sender === "user" ? "#e8f0fe" : "transparent",
                  color: "#202124",
                  borderRadius:
                    msg.sender === "user"
                      ? "16px 16px 4px 16px"
                      : 0,
                  padding: msg.sender === "user" ? "12px 14px" : 0,
                  boxShadow:
                    msg.sender === "user"
                      ? "0 1px 2px rgba(0,0,0,0.08)"
                      : "none",
                  minWidth: 0,
                  overflow: "hidden",
                }}
              >
                {msg.status && (
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: "6px",
                      mb: 1,
                      backgroundColor: "#e8eaed",
                      px: 1,
                      py: 0.5,
                      borderRadius: "12px",
                      width: "fit-content",
                    }}
                  >
                    <CircularProgress size={12} />
                    <Typography variant="caption" sx={{ fontWeight: 600 }}>
                      {msg.status}
                    </Typography>
                  </Box>
                )}

                {msg.thoughts && msg.thoughts.length > 0 && (
                  <Box sx={{ mb: 1 }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        gap: 0.5,
                      }}
                    >
                      <Button
                        size="small"
                        onClick={() => toggleThoughts(msg.id)}
                        endIcon={
                          showThoughts[msg.id] ? (
                            <ExpandLessIcon fontSize="small" />
                          ) : (
                            <ExpandMoreIcon fontSize="small" />
                          )
                        }
                        sx={{
                          textTransform: "none",
                          p: 0,
                          minWidth: 0,
                          color: "text.secondary",
                          fontSize: "0.75rem",
                        }}
                      >
                        {showThoughts[msg.id]
                          ? "Hide thoughts"
                          : `Show thoughts (${msg.thoughts.length})`}
                      </Button>
                      {showThoughts[msg.id] && (
                        <Tooltip
                          title={
                            copiedId ===
                            `${msg.id}-thoughts`
                              ? "Copied!"
                              : "Copy thoughts"
                          }
                        >
                          <IconButton
                            size="small"
                            onClick={() =>
                              handleCopyText(
                                `${msg.id}-thoughts`,
                                msg.thoughts!.join("\n"),
                              )
                            }
                            sx={{
                              p: 0.25,
                              color:
                                copiedId ===
                                `${msg.id}-thoughts`
                                  ? "#34a853"
                                  : "#9aa0a6",
                              "&:hover": {
                                color: "#5f6368",
                              },
                            }}
                          >
                            {copiedId ===
                            `${msg.id}-thoughts` ? (
                              <CheckIcon
                                sx={{ fontSize: 14 }}
                              />
                            ) : (
                              <ContentCopyIcon
                                sx={{ fontSize: 14 }}
                              />
                            )}
                          </IconButton>
                        </Tooltip>
                      )}
                    </Box>
                    <Collapse in={!!showThoughts[msg.id]}>
                      <Box
                        sx={{
                          mt: 0.5,
                          p: 1,
                          backgroundColor: "#fff",
                          borderRadius: "4px",
                          borderLeft: "3px solid #1a73e8",
                          maxHeight: "300px",
                          overflowY: "auto",
                        }}
                      >
                        {msg.thoughts.map((t, i) => (
                          <Typography
                            key={i}
                            variant="caption"
                            component="div"
                            sx={{ color: "text.secondary", mb: 0.5 }}
                          >
                            • {t}
                          </Typography>
                        ))}
                      </Box>
                    </Collapse>
                  </Box>
                )}

                {msg.tools && msg.tools.length > 0 && (
                  <Box sx={{ mb: 1 }}>
                    {msg.tools.map((tool, idx) => (
                      <Chip
                        key={idx}
                        size="small"
                        label={`Query: ${tool.split("(")[0]}`}
                        color="primary"
                        variant="outlined"
                        sx={{ fontSize: "0.7rem", mr: 0.5, mb: 0.5 }}
                      />
                    ))}
                  </Box>
                )}

                {msg.sqlQuery && !msg.isStreaming && (
                  <Box sx={{ mb: 1 }}>
                    <Button
                      size="small"
                      onClick={() => toggleSql(msg.id)}
                      endIcon={
                        showSql[msg.id] ? (
                          <ExpandLessIcon fontSize="small" />
                        ) : (
                          <ExpandMoreIcon fontSize="small" />
                        )
                      }
                      sx={{
                        textTransform: "none",
                        p: 0,
                        minWidth: 0,
                        color: "text.secondary",
                        fontSize: "0.75rem",
                      }}
                    >
                      {showSql[msg.id]
                        ? "Hide SQL"
                        : "Show SQL"}
                    </Button>
                    <Collapse in={!!showSql[msg.id]}>
                      <Box
                        sx={{
                          mt: 0.5,
                          position: "relative",
                          backgroundColor: "#f8f9fa",
                          border: "1px solid #e8eaed",
                          borderRadius: "6px",
                          p: "10px 12px",
                          overflowX: "auto",
                          "&::-webkit-scrollbar": {
                            height: "8px",
                          },
                          "&::-webkit-scrollbar-thumb": {
                            backgroundColor: "#dadce0",
                            borderRadius: "4px",
                          },
                        }}
                      >
                        <Tooltip
                          title={
                            copiedId === `${msg.id}-sql`
                              ? "Copied!"
                              : "Copy SQL"
                          }
                        >
                          <IconButton
                            size="small"
                            onClick={() =>
                              handleCopyText(
                                `${msg.id}-sql`,
                                msg.sqlQuery!,
                              )
                            }
                            sx={{
                              position: "absolute",
                              top: 4,
                              right: 4,
                              p: 0.5,
                              color:
                                copiedId === `${msg.id}-sql`
                                  ? "#34a853"
                                  : "#9aa0a6",
                              "&:hover": {
                                color: "#5f6368",
                              },
                            }}
                          >
                            {copiedId === `${msg.id}-sql` ? (
                              <CheckIcon
                                sx={{ fontSize: 14 }}
                              />
                            ) : (
                              <ContentCopyIcon
                                sx={{ fontSize: 14 }}
                              />
                            )}
                          </IconButton>
                        </Tooltip>
                        <Box
                          component="pre"
                          sx={{
                            m: 0,
                            pr: 3,
                            fontFamily:
                              "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                            fontSize: "0.8rem",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                          }}
                        >
                          {msg.sqlQuery}
                        </Box>
                      </Box>
                    </Collapse>
                  </Box>
                )}

                <Box
                  sx={{
                    lineHeight: 1.5,
                    fontSize: "0.875rem",
                    overflowWrap: "anywhere",
                    wordBreak: "break-word",
                    "& p": { m: 0, mb: 1, "&:last-child": { mb: 0 } },
                    "& strong": { fontWeight: 600 },
                    "& a": {
                      color: "#1a73e8",
                      overflowWrap: "anywhere",
                      wordBreak: "break-word",
                    },
                    "& ul, & ol": { m: "4px 0 8px", pl: "20px" },
                    "& li": { mb: "2px" },
                    "& h1, & h2, & h3, & h4": {
                      m: "10px 0 6px",
                      lineHeight: 1.3,
                      fontWeight: 600,
                    },
                    "& h1": { fontSize: "1.05rem" },
                    "& h2": { fontSize: "1rem" },
                    "& h3, & h4": { fontSize: "0.92rem" },
                    "& blockquote": {
                      m: "8px 0",
                      pl: "10px",
                      borderLeft: "3px solid #dadce0",
                      color: "#5f6368",
                    },
                    "& img": { maxWidth: "100%" },
                    "& code": {
                      fontFamily:
                        "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                      backgroundColor: "#eceff1",
                      padding: "1px 5px",
                      borderRadius: "4px",
                      fontSize: "0.82em",
                      overflowWrap: "anywhere",
                    },
                    "& pre": {
                      m: "8px 0",
                      p: "10px 12px",
                      backgroundColor: "#f8f9fa",
                      border: "1px solid #e8eaed",
                      borderRadius: "6px",
                      overflowX: "auto",
                      maxWidth: "100%",
                      "&::-webkit-scrollbar": { height: "8px" },
                      "&::-webkit-scrollbar-thumb": {
                        backgroundColor: "#dadce0",
                        borderRadius: "4px",
                      },
                    },
                    "& pre code": {
                      backgroundColor: "transparent",
                      p: 0,
                      fontSize: "0.8rem",
                      whiteSpace: "pre",
                    },
                    "& table": {
                      borderCollapse: "collapse",
                      width: "max-content",
                      minWidth: "100%",
                      fontSize: "0.8rem",
                    },
                    "& th, & td": {
                      border: "1px solid #e8eaed",
                      padding: "6px 10px",
                      whiteSpace: "nowrap",
                      textAlign: "left",
                    },
                    "& th": { backgroundColor: "#f1f3f4", fontWeight: 600 },
                    "& tr:nth-of-type(even) td": {
                      backgroundColor: "#fafafa",
                    },
                  }}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      table: ({ node, ...props }) => (
                        <Box
                          sx={{
                            overflowX: "auto",
                            maxWidth: "100%",
                            my: 1,
                            "&::-webkit-scrollbar": { height: "8px" },
                            "&::-webkit-scrollbar-thumb": {
                              backgroundColor: "#dadce0",
                              borderRadius: "4px",
                            },
                          }}
                        >
                          <table {...props} />
                        </Box>
                      ),
                    } satisfies Components}
                  >
                    {msg.text.replace(/\n?\[SUGGEST[\s\S]*$/, "")}
                  </ReactMarkdown>
                  {msg.isStreaming && (
                    <Box
                      component="span"
                      sx={{
                        display: "inline-block",
                        width: "7px",
                        height: "1em",
                        ml: "2px",
                        verticalAlign: "text-bottom",
                        backgroundColor: "#1a73e8",
                        borderRadius: "1px",
                        animation: "rmiBlink 1s steps(1) infinite",
                        "@keyframes rmiBlink": {
                          "0%, 50%": { opacity: 1 },
                          "50.01%, 100%": { opacity: 0 },
                        },
                      }}
                    />
                  )}
                </Box>

                {msg.renderedRoutes && msg.renderedRoutes.length > 0 && (
                  <Box sx={{ mt: 1.5, pt: 1, borderTop: "1px solid #e8eaed" }}>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        cursor: "pointer",
                      }}
                      onClick={() => toggleRoutes(msg.id)}
                    >
                      <Chip
                        size="small"
                        icon={
                          <AutoAwesomeIcon
                            sx={{ fontSize: "14px !important" }}
                          />
                        }
                        label={`${msg.renderedRoutes.length} routes highlighted on map`}
                        color="primary"
                        variant="outlined"
                        sx={{
                          fontSize: "0.75rem",
                          fontWeight: 500,
                          cursor: "pointer",
                        }}
                      />
                      <IconButton size="small" sx={{ p: 0.5 }}>
                        {showRoutes[msg.id] ? (
                          <ExpandLessIcon fontSize="small" />
                        ) : (
                          <ExpandMoreIcon fontSize="small" />
                        )}
                      </IconButton>
                    </Box>

                    <Collapse in={!!showRoutes[msg.id]}>
                      <Box
                        sx={{
                          mt: 1,
                          display: "flex",
                          flexDirection: "column",
                          gap: 0.75,
                          maxHeight: "220px",
                          overflowY: "auto",
                          p: 0.5,
                        }}
                      >
                        {msg.renderedRoutes.map((r, i) => {
                          const delaySec = r.delayTime || r.delay || 0
                          const durSec = r.duration || 0
                          const staticSec = r.staticDuration || 0
                          return (
                            <Box
                              key={r.id || i}
                              onClick={() => handleRouteClick(r)}
                              sx={{
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "space-between",
                                p: 1,
                                borderRadius: "8px",
                                backgroundColor: "#ffffff",
                                border: "1px solid #e8eaed",
                                cursor: "pointer",
                                transition: "all 0.15s ease",
                                "&:hover": {
                                  backgroundColor: "#f8f9fa",
                                  borderColor: "#1a73e8",
                                  transform: "translateY(-1px)",
                                },
                              }}
                            >
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                  overflow: "hidden",
                                  minWidth: 0,
                                }}
                              >
                                <Box
                                  sx={{
                                    width: 10,
                                    height: 10,
                                    borderRadius: "50%",
                                    backgroundColor: r.color || "#13d68f",
                                    flexShrink: 0,
                                  }}
                                />
                                <Box sx={{ overflow: "hidden" }}>
                                  <Typography
                                    variant="caption"
                                    sx={{
                                      fontWeight: 600,
                                      color: "#202124",
                                      display: "block",
                                      overflow: "hidden",
                                      textOverflow: "ellipsis",
                                      whiteSpace: "nowrap",
                                    }}
                                    title={r.name}
                                  >
                                    {r.name || r.id}
                                  </Typography>
                                  {durSec > 0 && (
                                    <Typography
                                      variant="caption"
                                      sx={{
                                        color: "#5f6368",
                                        fontSize: "0.65rem",
                                      }}
                                    >
                                      {Math.round(durSec)}s{" "}
                                      {staticSec > 0
                                        ? `(Free flow: ${Math.round(staticSec)}s)`
                                        : ""}
                                    </Typography>
                                  )}
                                </Box>
                              </Box>
                              {delaySec > 0 && (
                                <Typography
                                  variant="caption"
                                  sx={{
                                    color: r.color || "#d93025",
                                    fontWeight: 700,
                                    fontSize: "0.7rem",
                                    flexShrink: 0,
                                    ml: 1,
                                  }}
                                >
                                  +{Math.round(delaySec)}s delay
                                </Typography>
                              )}
                            </Box>
                          )
                        })}
                      </Box>
                    </Collapse>
                  </Box>
                )}

                {msg.tableData &&
                  msg.tableData.length > 0 &&
                  !msg.isStreaming && (
                    <Box
                      sx={{
                        mt: 1,
                        pt: 1,
                        borderTop: "1px solid #e8eaed",
                      }}
                    >
                      <Button
                        size="small"
                        variant="outlined"
                        startIcon={
                          <DownloadIcon sx={{ fontSize: 16 }} />
                        }
                        onClick={() =>
                          downloadCsv(
                            msg.tableData!,
                            "rmi-query-results.csv",
                          )
                        }
                        sx={{
                          textTransform: "none",
                          fontSize: "0.75rem",
                          borderRadius: "16px",
                          borderColor: "#e8eaed",
                          color: "#1a73e8",
                          "&:hover": {
                            borderColor: "#1a73e8",
                            backgroundColor: "#f1f6ff",
                          },
                        }}
                      >
                        Download CSV ({msg.tableData.length}{" "}
                        rows)
                      </Button>
                    </Box>
                  )}
              </Box>
            </Box>
          ))
        )}
        <div ref={messagesEndRef} />
      </MessagesContainer>

      {suggestions.length > 0 && messages.length > 0 && (
        <Box
          sx={{
            px: 2,
            py: 1.5,
            borderTop: "1px solid #e8eaed",
            backgroundColor: "#f8f9fa",
            flexShrink: 0,
            maxHeight: "40%",
            overflowY: "auto",
            "&::-webkit-scrollbar": { width: "6px" },
            "&::-webkit-scrollbar-thumb": {
              backgroundColor: "#dadce0",
              borderRadius: "3px",
            },
          }}
        >
          <Typography
            variant="caption"
            sx={{
              display: "block",
              mb: 1,
              fontWeight: 700,
              color: "#5f6368",
              letterSpacing: "0.2px",
            }}
          >
            Suggested follow-ups
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {suggestions.map((s, idx) => (
              <Box
                key={idx}
                onClick={() => handleSend(s)}
                sx={{
                  p: 1.25,
                  borderRadius: "12px",
                  border: "1px solid #e8eaed",
                  backgroundColor: "#fff",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  transition: "all 0.15s ease",
                  "&:hover": {
                    backgroundColor: "#f1f6ff",
                    borderColor: "#1a73e8",
                    transform: "translateY(-1px)",
                    boxShadow: "0 2px 8px rgba(26,115,232,0.12)",
                  },
                }}
              >
                <AutoAwesomeIcon
                  sx={{ color: "#1a73e8", fontSize: 18, flexShrink: 0 }}
                />
                <Typography variant="body2" sx={{ color: "#202124" }}>
                  {s}
                </Typography>
              </Box>
            ))}
          </Box>
        </Box>
      )}

      <InputContainer>
        <Box sx={{ display: "flex", gap: "8px" }}>
          <TextField
            size="small"
            fullWidth
            placeholder="Ask about Boston traffic..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                handleSend(inputText)
              }
            }}
            sx={{
              "& .MuiOutlinedInput-root": {
                borderRadius: "20px",
              },
            }}
          />
          <IconButton
            color="primary"
            onClick={() => handleSend(inputText)}
            disabled={!inputText.trim()}
            sx={{
              backgroundColor: "#1a73e8",
              color: "#fff",
              "&:hover": {
                backgroundColor: "#1557b0",
              },
              "&.Mui-disabled": {
                backgroundColor: "#e8eaed",
                color: "#9aa0a6",
              },
            }}
          >
            <SendIcon fontSize="small" />
          </IconButton>
        </Box>
      </InputContainer>

      {!agentPanelExpanded && (
        <Box
          onMouseDown={handleResizeStart}
          sx={{
            position: "absolute",
            top: 0,
            right: 0,
            bottom: 0,
            width: "6px",
            cursor: "col-resize",
            zIndex: 20,
            display: { xs: "none", md: "block" },
            transition: "background-color 0.15s ease",
            backgroundColor: isResizing
              ? "rgba(26, 115, 232, 0.28)"
              : "transparent",
            "&:hover": { backgroundColor: "rgba(26, 115, 232, 0.16)" },
          }}
        />
      )}

      {isResizing && (
        <Box
          sx={{
            position: "fixed",
            inset: 0,
            zIndex: 2000,
            cursor: "col-resize",
            userSelect: "none",
          }}
        />
      )}
    </DrawerContainer>
  )
}
