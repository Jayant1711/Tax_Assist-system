"""Block 6 port — crash-safety contract (legacy checks E01-E08).

The contract under test: NLPEngine.process_message must never raise on
adversarial input and must return a dict carrying a str "response".
"""
import pytest

from nlp_engine import NLPEngine

nlp = NLPEngine()

EDGE_INPUTS = [
    ("E01", ""),                             # Empty input
    ("E02", "   "),                          # Whitespace only
    ("E03", "abcdef random text"),           # No numbers
    ("E04", "I earn 0"),                     # Zero value
    ("E05", "I earn -5 lakhs"),              # Negative
    ("E06", "my income is 5 and 10 lakhs"),  # Mixed small + large number
    ("E07", "????"),                         # Garbage input
    ("E08", "/end"),                         # Immediate /end
]


@pytest.mark.parametrize(
    "text",
    [text for _, text in EDGE_INPUTS],
    ids=[edge_id for edge_id, _ in EDGE_INPUTS],
)
def test_process_message_never_crashes(text: str) -> None:
    sess = {"id": f"pytest_edge_{id(text)}"}
    result = nlp.process_message(text, sess)
    assert isinstance(result, dict)
    assert isinstance(result.get("response"), str)
