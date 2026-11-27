from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from .ledger import ReadLedger

# A citation looks like [lease-0042 p.3 L4-6] or [lease-0042 p.3 L7].
CITATION = re.compile(r"\[(?P<doc>[A-Za-z0-9][A-Za-z0-9._-]*) p\.(?P<page>\d+) L(?P<start>\d+)(?:-(?P<end>\d+))?\]")
# Text inside straight or curly double quotes counts as a quote the citation must contain.
QUOTE = re.compile(r"[\"“]([^\"”]{3,}?)[\"”]")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
MAX_SPAN = 40


class Reason(str, Enum):
    UNKNOWN_DOCUMENT = "the assistant never read this document"
    PAGE_NOT_READ = "the assistant never read this page"
    LINES_NOT_READ = "the assistant never read these lines"
    BAD_RANGE = "the line range is not valid"
    QUOTE_NOT_FOUND = "the quoted words are not on the cited lines"


@dataclass(frozen=True)
class Citation:
    doc_id: str
    page: int
    start: int
    end: int
    raw: str

    @property
    def lines(self) -> range:
        return range(self.start, self.end + 1)

    def label(self) -> str:
        span = f"{self.start}" if self.start == self.end else f"{self.start}-{self.end}"
        return f"{self.doc_id} page {self.page}, line {span}"


@dataclass(frozen=True)
class Dropped:
    citation: Citation
    reason: Reason
    detail: str = ""


@dataclass
class CheckResult:
    text: str
    kept: list[Citation] = field(default_factory=list)
    dropped: list[Dropped] = field(default_factory=list)
    unsupported_sentences: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.dropped

    def notice(self) -> str:
        """A short message for the user. Empty when every citation was kept."""
        if not self.dropped:
            return ""
        count = len(self.dropped)
        noun = "citation" if count == 1 else "citations"
        pronoun = "it" if count == 1 else "them"
        lines = [f"{count} {noun} removed because the source did not support {pronoun}:"]
        lines += [f"- {item.citation.label()}: {item.reason.value}{item.detail}" for item in self.dropped]
        if self.unsupported_sentences:
            lines.append("Sentences marked [unverified] have no remaining source. Check them before you rely on them.")
        return "\n".join(lines)


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _parse(match: re.Match[str]) -> Citation:
    start = int(match["start"])
    end = int(match["end"] or start)
    return Citation(match["doc"], int(match["page"]), start, end, match[0])


def _verify(citation: Citation, quotes: list[str], ledger: ReadLedger) -> Dropped | None:
    if citation.start < 1 or citation.end < citation.start or citation.end - citation.start >= MAX_SPAN:
        return Dropped(citation, Reason.BAD_RANGE)
    if not ledger.has_document(citation.doc_id):
        return Dropped(citation, Reason.UNKNOWN_DOCUMENT)
    if not ledger.has_page(citation.doc_id, citation.page):
        return Dropped(citation, Reason.PAGE_NOT_READ)
    missing = ledger.missing_lines(citation.doc_id, citation.page, citation.lines)
    if missing:
        return Dropped(citation, Reason.LINES_NOT_READ, f" (missing {', '.join(map(str, missing))})")
    source = _normalize(ledger.text(citation.doc_id, citation.page, citation.lines))
    for quote in quotes:
        if _normalize(quote) not in source:
            return Dropped(citation, Reason.QUOTE_NOT_FOUND, f' ("{quote}")')
    return None


def check_answer(answer: str, ledger: ReadLedger, *, mark_unsupported: bool = True,
                 link_template: str | None = None) -> CheckResult:
    """Remove every citation that the ledger cannot back, and report what was removed.

    ``link_template`` turns each kept citation into a Markdown link. It may use
    ``{doc}``, ``{page}``, ``{start}``, and ``{end}``. Leave it as ``None`` to keep the
    citation text unchanged.

    When ``mark_unsupported`` is true, a sentence that had citations and lost all of
    them gets an ``[unverified]`` marker, so the claim does not look sourced.
    """
    result = CheckResult(text="")
    pieces: list[str] = []
    position = 0
    for boundary in [*SENTENCE_END.finditer(answer), None]:
        stop = boundary.start() if boundary else len(answer)
        sentence = answer[position:stop]
        pieces.append(_check_sentence(sentence, ledger, result, mark_unsupported, link_template))
        if boundary:
            pieces.append(boundary.group())
            position = boundary.end()
    result.text = "".join(pieces)
    return result


def _check_sentence(sentence: str, ledger: ReadLedger, result: CheckResult,
                    mark_unsupported: bool, link_template: str | None) -> str:
    matches = list(CITATION.finditer(sentence))
    if not matches:
        return sentence
    kept_here = 0
    out: list[str] = []
    position = 0
    for index, match in enumerate(matches):
        citation = _parse(match)
        problem = _verify(citation, _quotes_for(sentence, matches, index), ledger)
        out.append(sentence[position:match.start()])
        if problem:
            result.dropped.append(problem)
            # Remove the space before a removed citation, so "fact [x]." becomes "fact."
            if out[-1].endswith(" "):
                out[-1] = out[-1][:-1]
        else:
            kept_here += 1
            result.kept.append(citation)
            out.append(_render(citation, link_template))
        position = match.end()
    out.append(sentence[position:])
    text = "".join(out)
    if kept_here == 0 and mark_unsupported:
        result.unsupported_sentences.append(re.sub(r"\s+([.!?,])", r"\1", CITATION.sub("", sentence)).strip())
        text = _insert_marker(text)
    return text


def _quotes_for(sentence: str, matches: list[re.Match[str]], index: int) -> list[str]:
    """Quotes a citation must contain: those after the previous citation and up to this one.

    The last citation in a sentence also owns any quotes that follow it.
    """
    start = matches[index - 1].end() if index else 0
    end = len(sentence) if index == len(matches) - 1 else matches[index].start()
    return QUOTE.findall(sentence[start:end])


def _render(citation: Citation, link_template: str | None) -> str:
    if link_template is None:
        return citation.raw
    url = link_template.format(doc=citation.doc_id, page=citation.page, start=citation.start, end=citation.end)
    return f"[{citation.raw[1:-1]}]({url})"


def _insert_marker(sentence: str) -> str:
    stripped = sentence.rstrip()
    if stripped and stripped[-1] in ".!?":
        return f"{stripped[:-1]} [unverified]{stripped[-1]}{sentence[len(stripped):]}"
    return f"{stripped} [unverified]{sentence[len(stripped):]}"
