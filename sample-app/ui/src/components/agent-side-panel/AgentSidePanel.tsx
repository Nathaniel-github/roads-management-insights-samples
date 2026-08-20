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
import CloseIcon from "@mui/icons-material/Close"
import ExpandLessIcon from "@mui/icons-material/ExpandLess"
import ExpandMoreIcon from "@mui/icons-material/ExpandMore"
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
  Typography,
} from "@mui/material"
import { styled } from "@mui/material/styles"
import React, { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { getRouteColor } from "../../data/common/route-color"
import { convertToGeoJSON } from "../../deck-gl/helpers"
import { useAppStore } from "../../store"
import { RouteSegment } from "../../types/route-segment"

const DrawerContainer = styled(Paper)({
  position: "fixed",
  top: "64px",
  left: 0,
  bottom: 0,
  width: "420px",
  zIndex: 100,
  display: "flex",
  flexDirection: "column",
  backgroundColor: "#ffffff",
  boxShadow: "4px 0 20px rgba(0, 0, 0, 0.08)",
  borderRight: "1px solid #e8eaed",
  overflow: "hidden",
  "@media (max-width: 768px)": {
    width: "100%",
  },
})

const Header = styled(Box)({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "16px 20px",
  backgroundColor: "#f8f9fa",
  borderBottom: "1px solid #e8eaed",
})

const MessagesContainer = styled(Box)({
  flex: 1,
  overflowY: "auto",
  padding: "16px",
  display: "flex",
  flexDirection: "column",
  gap: "16px",
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
}

const QUICK_PROMPTS = [
  "What were the average travel times for Boston routes in Oct 2025?",
  "Which Boston routes had peak traffic delays?",
  "Show the operational status of routes in Boston",
]

export const AgentSidePanel: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState("")
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [showThoughts, setShowThoughts] = useState<Record<string, boolean>>({})
  const [showRoutes, setShowRoutes] = useState<Record<string, boolean>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const selectedCity = useAppStore((state) => state.selectedCity)
  const setActiveTab = useAppStore((state) => state.setActiveTab)
  const setSelectedRouteId = useAppStore((state) => state.setSelectedRouteId)
  const map = useAppStore((state) => state.refs.map)

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

  const toggleThoughts = (id: string) => {
    setShowThoughts((prev) => ({ ...prev, [id]: !prev[id] }))
  }

  const toggleRoutes = (id: string) => {
    setShowRoutes((prev) => ({ ...prev, [id]: !prev[id] }))
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
        const routeSegments: RouteSegment[] = rawFeatures.map((f: any) => {
          const props = f.properties || {}
          const path = (f.geometry?.coordinates || []).map((c: number[]) => ({
            lng: c[0],
            lat: c[1],
          }))
          const duration = props.duration || 0
          const staticDuration = props.static_duration || 0
          const delayTime = props.delay_time ?? 0
          const delayRatio = props.delay_ratio ?? 1
          return {
            id: props.id || props.selected_route_id,
            name: props.name || props.display_name || props.id,
            path,
            duration,
            staticDuration,
            delayRatio,
            delayTime,
            color: getRouteColor(delayRatio, delayTime),
            length: props.length || 0,
          }
        })

        useAppStore.getState().setMapData(convertToGeoJSON(routeSegments))

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

    eventSource.addEventListener("done", () => {
      updateAgentMsg({ isStreaming: false, status: undefined })
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
    <DrawerContainer elevation={2}>
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
        <IconButton size="small" onClick={handleClose}>
          <CloseIcon fontSize="small" />
        </IconButton>
      </Header>

      <MessagesContainer>
        {messages.length === 0 ? (
          <Box
            sx={{
              display: "flex",
              flexDirection: "column",
              gap: "12px",
              my: "auto",
              py: 2,
            }}
          >
            <Typography variant="body2" color="text.secondary" align="center">
              Ask any question about historical travel times, route slowdowns,
              or congestion in Boston.
            </Typography>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ fontWeight: 600, mt: 1 }}
            >
              Suggested queries:
            </Typography>
            {QUICK_PROMPTS.map((prompt, idx) => (
              <Chip
                key={idx}
                label={prompt}
                onClick={() => handleSend(prompt)}
                sx={{
                  justifyContent: "flex-start",
                  height: "auto",
                  py: 1,
                  px: 0.5,
                  "& .MuiChip-label": {
                    whiteSpace: "normal",
                    textAlign: "left",
                  },
                }}
              />
            ))}
          </Box>
        ) : (
          messages.map((msg) => (
            <Box
              key={msg.id}
              sx={{
                alignSelf: msg.sender === "user" ? "flex-end" : "flex-start",
                maxWidth: "88%",
              }}
            >
              <Box
                sx={{
                  backgroundColor:
                    msg.sender === "user" ? "#e8f0fe" : "#f1f3f4",
                  color: "#202124",
                  borderRadius:
                    msg.sender === "user"
                      ? "16px 16px 4px 16px"
                      : "16px 16px 16px 4px",
                  padding: "10px 14px",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
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
                    <Collapse in={!!showThoughts[msg.id]}>
                      <Box
                        sx={{
                          mt: 0.5,
                          p: 1,
                          backgroundColor: "#fff",
                          borderRadius: "4px",
                          borderLeft: "3px solid #1a73e8",
                          maxHeight: "150px",
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

                <Box
                  sx={{
                    "& p": { m: 0, mb: 1, "&:last-child": { mb: 0 } },
                    "& strong": { fontWeight: 600 },
                    lineHeight: 1.5,
                    fontSize: "0.875rem",
                  }}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.text}
                  </ReactMarkdown>
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
              </Box>
            </Box>
          ))
        )}
        <div ref={messagesEndRef} />
      </MessagesContainer>

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
    </DrawerContainer>
  )
}
