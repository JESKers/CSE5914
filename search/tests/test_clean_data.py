from pathlib import Path

from search.clean_data import clean


def test_clean_supports_craigslist_style_columns(tmp_path: Path):
    csv_path = tmp_path / "vehicles.csv"
    csv_path.write_text(
        "id,manufacturer,model,year,price,fuel,transmission,type,size\n"
        "1,ford,focus,2012,8000,gas,automatic,coupe,compact\n",
        encoding="utf-8",
    )

    df = clean(csv_path)

    assert "make" in df.columns
    assert df.loc[0, "make"] == "ford"
    assert df.loc[0, "msrp"] == 8000
    assert df.loc[0, "engine_fuel_type"] == "gas"
    assert df.loc[0, "transmission_type"] == "automatic"
    assert df.loc[0, "vehicle_style"] == "coupe"
    assert df.loc[0, "vehicle_size"] == "compact"
    assert "text" in df.columns
    assert "ford focus coupe" in df.loc[0, "text"]
