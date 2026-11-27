from __future__ import annotations

from collections.abc import Iterable, Mapping


class ReadLedger:
    """Record of the exact lines that tools returned to the model during one answer.

    Record a line only after the tool output that contains it was passed to the model.
    A page that was only listed in search results, but never read, must not be recorded.
    """

    def __init__(self) -> None:
        self._lines: dict[tuple[str, int], dict[int, str]] = {}

    def record(self, doc_id: str, page: int, lines: Mapping[int, str]) -> None:
        if page < 1:
            raise ValueError("page numbers start at 1")
        if any(number < 1 for number in lines):
            raise ValueError("line numbers start at 1")
        self._lines.setdefault((doc_id, page), {}).update(lines)

    def record_page_text(self, doc_id: str, page: int, text: str, first_line: int = 1) -> None:
        """Record a chunk of page text, numbering its lines from ``first_line``."""
        self.record(doc_id, page, {first_line + i: line for i, line in enumerate(text.splitlines())})

    def has_document(self, doc_id: str) -> bool:
        return any(doc == doc_id for doc, _ in self._lines)

    def has_page(self, doc_id: str, page: int) -> bool:
        return (doc_id, page) in self._lines

    def missing_lines(self, doc_id: str, page: int, numbers: Iterable[int]) -> list[int]:
        read = self._lines.get((doc_id, page), {})
        return [number for number in numbers if number not in read]

    def text(self, doc_id: str, page: int, numbers: Iterable[int]) -> str:
        read = self._lines.get((doc_id, page), {})
        return "\n".join(read[number] for number in numbers if number in read)
