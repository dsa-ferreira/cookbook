from sqlalchemy import text
from sqlalchemy.orm import Session


def test_select_one(db_session: Session) -> None:
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1
