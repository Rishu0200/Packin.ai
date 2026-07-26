import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, CatalogDimension
from app.core.resolver import resolve_box, round_to_catalog


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    for axis, values in {"dim1": [15, 17, 19, 21], "dim2": [20], "dim3": [4, 6, 8]}.items():
        for v in values:
            session.add(CatalogDimension(axis=axis, value=v, active=True))
    session.commit()
    yield session
    session.close()


def test_exact_regular_size_matches_itself(db_session):
    result = resolve_box(db_session, 17, 20, 6)
    assert result["status"] == "matched"
    assert (result["dim1"], result["dim2"], result["dim3"]) == (17, 20, 6)
    assert result["was_outsize"] is False


def test_dim2_18_is_an_exact_regular_match_not_outsize(db_session):
    # dim2's valid catalog is {16, 18, 20} (confirmed: channel/basket size),
    # so 18 is already a real box size, not something that needs rounding.
    result = resolve_box(db_session, 15, 18, 4)
    assert result["status"] == "matched"
    assert (result["dim1"], result["dim2"], result["dim3"]) == (15, 18, 4)
    assert result["was_outsize"] is False


def test_outsize_dim1_rounds_up_dim2_already_valid(db_session):
    # dim1=18 isn't in {15,17,19,21} so it rounds up to 19; dim2=18 IS
    # already valid so it stays put.
    result = resolve_box(db_session, 18, 18, 6)
    assert result["status"] == "matched"
    assert (result["dim1"], result["dim2"], result["dim3"]) == (19, 18, 6)
    assert result["was_outsize"] is True


def test_outsize_dim2_17_rounds_up_to_18(db_session):
    result = resolve_box(db_session, 15, 17, 4)
    assert result["status"] == "matched"
    assert (result["dim1"], result["dim2"], result["dim3"]) == (15, 18, 4)


def test_dim1_exceeding_max_needs_review(db_session):
    result = resolve_box(db_session, 27, 20, 6)
    assert result["status"] == "needs_review"
    assert "dim1" in result["reason"]


def test_round_to_catalog_returns_none_above_max():
    assert round_to_catalog(23, [15, 17, 19, 21]) is None


def test_round_to_catalog_picks_smallest_that_fits():
    assert round_to_catalog(16, [15, 17, 19, 21]) == 17
