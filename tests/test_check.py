from __future__ import annotations

import pytest

from citation_check import ReadLedger, Reason, check_answer


@pytest.fixture
def ledger() -> ReadLedger:
    ledger = ReadLedger()
    ledger.record("doc-a", 1, {1: "The fee is 200 baht.", 2: "Payment is due on Monday.", 3: "Late fees apply."})
    ledger.record("doc-a", 2, {4: "Only line four was read on this page."})
    return ledger


def reasons(result):
    return [item.reason for item in result.dropped]


def test_keeps_a_citation_to_lines_that_were_read(ledger):
    result = check_answer("The fee is 200 baht [doc-a p.1 L1].", ledger)
    assert result.ok
    assert result.text == "The fee is 200 baht [doc-a p.1 L1]."
    assert [c.label() for c in result.kept] == ["doc-a page 1, line 1"]
    assert result.notice() == ""


def test_keeps_a_range_when_every_line_was_read(ledger):
    result = check_answer("Fees and dates [doc-a p.1 L1-3].", ledger)
    assert result.ok


@pytest.mark.parametrize(
    ("citation", "reason"),
    [
        ("[doc-b p.1 L1]", Reason.UNKNOWN_DOCUMENT),
        ("[doc-a p.9 L1]", Reason.PAGE_NOT_READ),
        ("[doc-a p.2 L1]", Reason.LINES_NOT_READ),
        ("[doc-a p.1 L3-1]", Reason.BAD_RANGE),
        ("[doc-a p.1 L0]", Reason.BAD_RANGE),
    ],
)
def test_removes_a_citation_the_ledger_cannot_back(ledger, citation, reason):
    result = check_answer(f"A claim {citation}.", ledger)
    assert reasons(result) == [reason]
    assert citation not in result.text


def test_a_range_with_one_unread_line_is_removed(ledger):
    result = check_answer("Claim [doc-a p.2 L3-4].", ledger)
    assert reasons(result) == [Reason.LINES_NOT_READ]
    assert "missing 3" in result.notice()


def test_a_sentence_that_loses_every_citation_is_marked(ledger):
    result = check_answer("The fee is 900 baht [doc-b p.1 L1]. Payment is due on Monday [doc-a p.1 L2].", ledger)
    assert result.text == "The fee is 900 baht [unverified]. Payment is due on Monday [doc-a p.1 L2]."
    assert result.unsupported_sentences == ["The fee is 900 baht."]


def test_marking_can_be_turned_off(ledger):
    result = check_answer("The fee is 900 baht [doc-b p.1 L1].", ledger, mark_unsupported=False)
    assert result.text == "The fee is 900 baht."
    assert result.unsupported_sentences == []


def test_a_sentence_keeps_its_valid_citation_when_another_is_removed(ledger):
    result = check_answer("Fee and day [doc-a p.1 L1] [doc-z p.1 L1].", ledger)
    assert result.text == "Fee and day [doc-a p.1 L1]."
    assert result.unsupported_sentences == []


def test_a_quote_must_appear_on_the_cited_lines(ledger):
    good = check_answer('The text says "due on monday" [doc-a p.1 L2].', ledger)
    bad = check_answer('The text says "due on Friday" [doc-a p.1 L2].', ledger)
    assert good.ok
    assert reasons(bad) == [Reason.QUOTE_NOT_FOUND]


def test_each_quote_is_checked_against_the_citation_after_it(ledger):
    answer = 'It says "200 baht" [doc-a p.1 L1] and "Late fees apply" [doc-a p.1 L3].'
    assert check_answer(answer, ledger).ok


def test_quote_matching_ignores_case_width_and_spacing():
    ledger = ReadLedger()
    ledger.record("doc-c", 1, {1: "Total   ＡＭＯＵＮＴ: 1,000"})
    assert check_answer('It reads "total amount: 1,000" [doc-c p.1 L1].', ledger).ok


def test_text_without_citations_is_unchanged(ledger):
    answer = "No sources here. Just a reply."
    result = check_answer(answer, ledger)
    assert result.text == answer
    assert result.ok


def test_link_template_turns_kept_citations_into_links(ledger):
    result = check_answer("Fee [doc-a p.1 L1-2].", ledger, link_template="/d/{doc}/{page}#L{start}-L{end}")
    assert result.text == "Fee [doc-a p.1 L1-2](/d/doc-a/1#L1-L2)."


def test_notice_lists_every_removed_citation(ledger):
    result = check_answer("A [doc-b p.1 L1]. B [doc-a p.9 L1].", ledger)
    notice = result.notice()
    assert notice.startswith("2 citations removed")
    assert "doc-b page 1, line 1" in notice
    assert "doc-a page 9, line 1" in notice


def test_lines_are_numbered_from_the_chunk_start():
    ledger = ReadLedger()
    ledger.record_page_text("doc-d", 3, "first\nsecond", first_line=10)
    assert check_answer("X [doc-d p.3 L10-11].", ledger).ok
    assert not check_answer("X [doc-d p.3 L9].", ledger).ok


def test_ledger_rejects_page_zero():
    with pytest.raises(ValueError):
        ReadLedger().record("doc", 0, {1: "x"})
