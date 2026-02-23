import unittest

from app.ai.grounding import validate_citations


class GroundingValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk_text_by_id = {
            "chunk-1": "We decided to ship Friday and Alice owns QA.",
            "chunk-2": "Budget was approved after legal review.",
        }

    def test_valid_citation_passes(self) -> None:
        citations = [{"chunk_id": "chunk-1", "quote": "ship Friday"}]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(valid, [{"chunk_id": "chunk-1", "quote": "ship Friday"}])
        self.assertEqual(invalid, [])

    def test_invalid_chunk_id_rejected(self) -> None:
        citations = [{"chunk_id": "chunk-999", "quote": "ship Friday"}]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(valid, [])
        self.assertEqual(invalid[0]["reason"], "chunk_id_not_allowed")

    def test_empty_quote_rejected(self) -> None:
        citations = [{"chunk_id": "chunk-1", "quote": "   "}]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(valid, [])
        self.assertEqual(invalid[0]["reason"], "missing_quote")

    def test_quote_too_long_rejected(self) -> None:
        long_quote = "x" * 2001
        citations = [{"chunk_id": "chunk-1", "quote": long_quote}]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(valid, [])
        self.assertEqual(invalid[0]["reason"], "quote_too_long")

    def test_quote_not_found_rejected(self) -> None:
        citations = [{"chunk_id": "chunk-1", "quote": "completely unrelated text"}]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(valid, [])
        self.assertEqual(invalid[0]["reason"], "quote_not_in_chunk")

    def test_normalization_handles_case_and_whitespace(self) -> None:
        citations = [
            {"chunk_id": "chunk-1", "quote": "WE   decided \n to ship   friday"},
        ]
        valid, invalid = validate_citations(citations, self.chunk_text_by_id)
        self.assertEqual(invalid, [])
        self.assertEqual(valid[0]["chunk_id"], "chunk-1")


if __name__ == "__main__":
    unittest.main()
