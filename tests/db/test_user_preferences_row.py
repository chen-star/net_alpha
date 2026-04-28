# tests/db/test_user_preferences_row.py
from datetime import datetime

from sqlmodel import Session, select

from net_alpha.db.tables import AccountRow, UserPreferenceRow


def test_user_preference_row_persists(memory_engine):
    with Session(memory_engine) as s:
        acct = AccountRow(broker="Schwab", label="Tax")
        s.add(acct)
        s.commit()
        s.refresh(acct)

        pref = UserPreferenceRow(
            account_id=acct.id,
            profile="active",
            density="comfortable",
            updated_at=datetime(2026, 4, 27, 12, 0, 0),
        )
        s.add(pref)
        s.commit()

        loaded = s.exec(select(UserPreferenceRow).where(UserPreferenceRow.account_id == acct.id)).first()

    assert loaded is not None
    assert loaded.profile == "active"
    assert loaded.density == "comfortable"
