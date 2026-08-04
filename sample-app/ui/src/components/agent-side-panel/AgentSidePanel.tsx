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

import React, { useState, useEffect, useRef } from "react"
import {
  Box,
  Paper,
  Typography,
  IconButton,
  TextField,
  Button,
  Chip,
  CircularProgress,
  Collapse,
  Divider,
} from "@mui/material"
import { styled } from "@mui/material/styles"
import SmartToyIcon from "@mui/icons-material/SmartToy"
import CloseIcon from "@mui/icons-material/Close"
import SendIcon from "@mui/icons-material/Send"
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome"
import ExpandMoreIcon from "@mui/icons-material/ExpandMore"
import ExpandLessIcon from "@mui/icons-material/ExpandLess"
import { useAppStore } from "../../store"

const ToggleButton = styled(Button)({
  position: "fixed",
  top: "5rem",
  right: "1.5rem",
  zIndex: 1900,
  backgroundColor: "#1a73e8",
  color: "#fff",
  borderRadius: "24px",
  padding: "8px 16px",
  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  textTransform: "none",
  fontWeight: 600,
  "&:hover": {
    backgroundColor: "#1557b0",
  },
})

const DrawerContainer = styled(Paper)({
  position: "fixed",
  top: 0,
  right: 0,
  bottom: 0,
  width: "390px",
  zIndex: 2000,
  display: "flex",
  flexDirection: "column",
  backgroundColor: "#ffffff",
  boxShadow: "-4px 0 20px rgba(0, 0, 0, 0.15)",
  overflow: "hidden",
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
}

const QUICK_PROMPTS = [
  "What were the average travel times for Boston routes in Oct 2025?",
  "Which Boston routes had peak traffic delays?",
  "Show the operational status of routes in Boston",
]

export const AgentSidePanel: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputText, setInputText] = useState("")
  const [showThoughts, setShowThoughts] = useState<Record<string, boolean>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const selectedCity = useAppStore((state) => state.selectedCity)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const toggleThoughts = (id: string) => {
    setShowThoughts((prev) => ({ ...prev, [id]: !prev[id] }))
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
    const url = `/api/agent/stream?message=${encodeURIComponent(queryText)}&city=${encodeURIComponent(cityId)}`

    const eventSource = new EventSource(url)

    eventSource.addEventListener("status", (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId
              ? { ...msg, status: data.status }
              : msg
          )
        )
      } catch (e) {}
    })

    eventSource.addEventListener("thinking", (event) => {
      try {
        const data = JSON.parse(event.data)
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId
              ? {
                  ...msg,
                  thoughts: [...(msg.thoughts || []), data.text],
                  status: "Thinking...",
                }
              : msg
          )
        )
      } catch (e) {}
    })

    eventSource.addEventListener("tool_call", (event) => {
      try {
        const data = JSON.parse(event.data)
        const toolDesc = `${data.name}(${JSON.stringify(data.args || {})})`
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId
              ? {
                  ...msg,
                  tools: [...(msg.tools || []), toolDesc],
                  status: `Querying BigQuery: ${data.name}...`,
                }
              : msg
          )
        )
      } catch (e) {}
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
              : msg
          )
        )
      } catch (e) {}
    })

    eventSource.addEventListener("done", () => {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === agentMsgId
            ? { ...msg, isStreaming: false, status: undefined }
            : msg
        )
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
            : msg
        )
      )
      eventSource.close()
    })
  }

  if (!isOpen) {
    return (
      <ToggleButton onClick={() => setIsOpen(true)}>
        <SmartToyIcon fontSize="small" />
        RMI Assistant
      </ToggleButton>
    )
  }

  return (
    <DrawerContainer elevation={8}>
      <Header>
        <Box sx={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <AutoAwesomeIcon sx={{ color: "#1a73e8" }} />
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.2 }}>
              Roads AI Assistant
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {selectedCity?.name || "Boston"} Data (BigQuery)
            </Typography>
          </Box>
        </Box>
        <IconButton size="small" onClick={() => setIsOpen(false)}>
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
              Ask any question about historical travel times, route slowdowns, or congestion in Boston.
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, mt: 1 }}>
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
                      {showThoughts[msg.id] ? "Hide thoughts" : `Show thoughts (${msg.thoughts.length})`}
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

                <Typography variant="body2" sx={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
                  {msg.text}
                </Typography>
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
            onKeyPress={(e) => {
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
