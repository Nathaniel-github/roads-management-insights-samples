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

// Single source of truth for the agent side panel's docking geometry, shared
// by the panel itself (AgentSidePanel) and the map layout (demo/page.tsx) so
// the two never desync when the user resizes or expands the panel.

export const AGENT_PANEL_MIN_WIDTH = 380
export const AGENT_PANEL_MAX_WIDTH = 900
export const AGENT_PANEL_DEFAULT_WIDTH = 460
export const AGENT_PANEL_EXPANDED_WIDTH = 760

export const AGENT_PANEL_WIDTH_STORAGE_KEY = "rmi.agentPanel.width"
export const AGENT_PANEL_EXPANDED_STORAGE_KEY = "rmi.agentPanel.expanded"

// Never let the panel eat more than this fraction of the viewport when the
// user drags the resize handle or expands it.
const MAX_VIEWPORT_FRACTION = 0.8

/** Clamp a candidate width to the allowed range and the current viewport. */
export const clampPanelWidth = (width: number): number => {
  const viewportCap =
    typeof window !== "undefined"
      ? window.innerWidth * MAX_VIEWPORT_FRACTION
      : AGENT_PANEL_MAX_WIDTH
  const upper = Math.min(AGENT_PANEL_MAX_WIDTH, viewportCap)
  return Math.round(Math.min(upper, Math.max(AGENT_PANEL_MIN_WIDTH, width)))
}

/** The effective docked width, accounting for the expanded reading mode. */
export const getEffectivePanelWidth = (
  width: number,
  expanded: boolean,
): number => (expanded ? clampPanelWidth(AGENT_PANEL_EXPANDED_WIDTH) : width)

/** Read the persisted width from localStorage, falling back to the default. */
export const readStoredPanelWidth = (): number => {
  if (typeof window === "undefined") return AGENT_PANEL_DEFAULT_WIDTH
  const raw = window.localStorage.getItem(AGENT_PANEL_WIDTH_STORAGE_KEY)
  const parsed = raw ? Number(raw) : NaN
  return Number.isFinite(parsed)
    ? clampPanelWidth(parsed)
    : AGENT_PANEL_DEFAULT_WIDTH
}

/** Read the persisted expanded flag from localStorage. */
export const readStoredPanelExpanded = (): boolean => {
  if (typeof window === "undefined") return false
  return window.localStorage.getItem(AGENT_PANEL_EXPANDED_STORAGE_KEY) === "true"
}
