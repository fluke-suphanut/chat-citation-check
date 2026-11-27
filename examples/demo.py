"""Run a scripted chat turn: tools read pages, the model answers, and the checker cleans the answer.

The model answer is a fixed string, so the demo needs no API key and gives the same output every time.
Run it from the repository root:

    PYTHONPATH=src python3 examples/demo.py
"""

from __future__ import annotations

from documents import DOCUMENTS

from citation_check import ReadLedger, check_answer


def read_page(ledger: ReadLedger, doc_id: str, page: int, first: int = 1, last: int | None = None) -> str:
    """A stand-in for the assistant's page-reading tool. It records what it returns."""
    lines = DOCUMENTS[doc_id][page]
    last = last or len(lines)
    chunk = {number: lines[number - 1] for number in range(first, last + 1)}
    ledger.record(doc_id, page, chunk)
    return "\n".join(f"L{number}: {text}" for number, text in chunk.items())


def main() -> None:
    ledger = ReadLedger()
    # The assistant read page 2 of the lease in full, and only lines 1-2 of page 3.
    read_page(ledger, "lease-0042", 2)
    read_page(ledger, "lease-0042", 3, 1, 2)

    # A scripted model answer. Three citations are wrong on purpose.
    answer = (
        "The monthly rent is 15,000 baht, due on the 5th [lease-0042 p.2 L2]. "
        "A late fee of \"500 baht\" applies after the 10th day [lease-0042 p.2 L3]. "
        "The deposit is \"three months of rent\" [lease-0042 p.2 L5]. "
        "Either party can end the lease with 60 days of written notice [lease-0042 p.3 L2]. "
        "If the tenant leaves in the first 6 months, the deposit is kept [lease-0042 p.3 L3]. "
        "The first invoice is due on 5 February [invoice-7781 p.1 L4]."
    )

    result = check_answer(answer, ledger, link_template="/docs/{doc}/pages/{page}#L{start}-L{end}")

    print("MODEL ANSWER\n" + answer + "\n")
    print("CHECKED ANSWER\n" + result.text + "\n")
    print("NOTICE FOR THE USER\n" + (result.notice() or "(none)") + "\n")
    print(f"kept {len(result.kept)}, removed {len(result.dropped)}")


if __name__ == "__main__":
    main()
