"""Base autorater abstract class for RMI Agent Evaluation."""

from __future__ import annotations

import abc
from typing import Any


class BaseAutorater(abc.ABC):
  """Abstract base class for all autoraters."""

  @abc.abstractmethod
  def get_eval_metrics(self) -> list[Any]:
    """Returns the custom metrics for this autorater."""

  def extract_candidate_data(self, session: Any) -> dict[str, Any]:
    """Extracts required candidate data from the session."""
    del session
    return {}
