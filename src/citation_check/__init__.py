"""Check that every page-and-line citation in an LLM answer points at text a tool really read."""

from .check import CheckResult, Citation, Dropped, Reason, check_answer
from .ledger import ReadLedger

__all__ = ["CheckResult", "Citation", "Dropped", "Reason", "ReadLedger", "check_answer"]
