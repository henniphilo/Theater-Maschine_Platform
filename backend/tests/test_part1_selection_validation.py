import pytest

from app.schemas.part1_selection import MediaSelectionLists
from app.services.part1_selection_validation import Part1SelectionValidationError, validate_media_lists


def test_validate_media_lists_minimums() -> None:
    with pytest.raises(Part1SelectionValidationError):
        validate_media_lists(MediaSelectionLists(sounds=["a"], music=["b"], videos=["c"], lights=["d"]))
