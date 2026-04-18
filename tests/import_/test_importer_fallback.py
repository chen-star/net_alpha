import pytest
from pathlib import Path
from net_alpha.import_.importer import ImportContext, run_import
from net_alpha.db.repository import TradeRepository, SchemaCacheRepository
from sqlmodel import Session, create_engine, SQLModel

def test_run_import_uses_fallback_no_api_key(tmp_path):
    # Setup dummy db
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    
    session = Session(engine)
    
    # Create dummy csv
    csv_file = tmp_path / "schwab.csv"
    csv_file.write_text("Date,Symbol,Action,Quantity,Amount,Cost Basis\n10/15/2024,TSLA,Buy,10,2400.00,2400.00")
    
    ctx = ImportContext(
        csv_path=csv_file,
        broker_name="schwab",
        anthropic_client=None, # NO API KEY
        model="claude-3-5-sonnet-20240620",
        max_retries=1,
        confirm_schema=lambda *args: True,
        trade_repo=TradeRepository(session),
        schema_cache_repo=SchemaCacheRepository(session),
        session=session
    )
    
    result = run_import(ctx)
    assert result.new_imported == 1
    assert result.equities == 1
