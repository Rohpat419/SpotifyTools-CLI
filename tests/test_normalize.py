# Super basic tests to ensure the normalize functions work correctly
import pytest
from src.spotify_tools.normalize import normalize_title, normalize_artists, _has_cjk


def test_normalize_title_relaxed():
    assert normalize_title("Song (feat. Drake) - Remastered 2012") == "song"

# Birds of a feather contains the word "feat"
def test_normalize_title_false_positive(): 
    assert normalize_title("Birds of a feather") == "birds of a feather"

def test_normalize_artists_set():
    assert normalize_artists(["Drake", "21 Savage"]) == ["21 savage", "drake"]

def test_has_cjk_positive():
    assert _has_cjk("スーパー") == True

def test_has_cjk_negative():
    assert _has_cjk("Kendrick") == False

