from pathlib import Path

from app.ingest.power import load_local_power


def test_load_local_power_parses_date_and_values(tmp_path: Path) -> None:
    path = tmp_path / "karachi.csv"
    path.write_text(
        "site,province,date,t2m_max,t2m_min,prectotcorr,rh2m,ws2m,allsky_sfc_sw_dwn\n"
        "karachi,Sindh,20200101,20.0,10.0,0.0,50.0,2.0,15.0\n"
        "karachi,Sindh,20200102,21.0,11.0,1.0,51.0,2.1,16.0\n",
        encoding="utf-8",
    )
    frame = load_local_power(path)
    assert len(frame) == 2
    assert frame.index[0].year == 2020
    assert float(frame.iloc[0]["t2m_max"]) == 20.0
