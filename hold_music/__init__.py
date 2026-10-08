"""Offline Hold Music planning. No game, network, or persistence side effects."""

from .repertoire import Snapshot, plan

__all__ = ["Snapshot", "plan"]
