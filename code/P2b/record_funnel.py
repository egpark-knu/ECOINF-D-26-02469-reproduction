#!/usr/bin/env python3
"""P2b R2-m03a - reconcile the 7,612 vs 26,868 harmful-cyanobacteria record counts."""
import json, os
from pathlib import Path
import pandas as pd
REPOSITORY_ROOT=Path(__file__).resolve().parents[2]
BASE=Path(os.environ.get("P2B_SOURCE_ROOT",str(REPOSITORY_ROOT/"raw")))
OUT=Path(os.environ.get("P2B_OUT",str(REPOSITORY_ROOT/"reproduction_output/P2b")))
y=pd.read_csv(BASE/"Round_6/01_data/insitu/cyanobacteria_panel.csv",low_memory=False)
p=pd.read_csv(BASE/"Round_6/02_analysis/proxy_validation/insitu_annual_analysis_panel.csv")
ann=p[p.season_scope=="annual_all_samples"]; blo=p[p.season_scope=="bloom_season_06_10"]
tot=y[y.variable=="harmful_cyanobacteria_total"]
dup=tot.groupby(["station_code","sampling_date"]).size()
rows=[
 ("A","cyanobacteria_panel.csv rows (all variables, long format)",len(y)),
 ("B","  of which 4 genus variables (Anabaena/Aphanizomenon/Microcystis/Oscillatoria)",int((y.variable!='harmful_cyanobacteria_total').sum())),
 ("C","  of which variable == harmful_cyanobacteria_total",len(tot)),
 ("D","distinct station-date pairs within C",int(tot.groupby(['station_code','sampling_date']).ngroups)),
 ("E","duplicate station-date rows in C (C - D)",int(len(tot)-tot.groupby(['station_code','sampling_date']).ngroups)),
 ("F","sum of harmful_cyanobacteria_total_n over the 144 ANNUAL analysis weir-years",int(ann.harmful_cyanobacteria_total_n.sum())),
 ("G","sum of harmful_cyanobacteria_total_n over the 144 BLOOM analysis weir-years",int(blo.harmful_cyanobacteria_total_n.sum())),
 ("H","rows in C outside 2017-2025",int(((tot.sampling_year<2017)|(tot.sampling_year>2025)).sum())),
 ("I","distinct stations in C",int(tot.station_code.nunique())),
 ("J","MANUSCRIPT CLAIM (Section 2 and Table 1 total)",7612),
]
df=pd.DataFrame(rows,columns=["step","description","count"])
df["matches_manuscript_7612"]=df["count"].eq(7612)
df.to_csv(OUT/"m03a_record_funnel.csv",index=False)
print(df.to_string(index=False))
print("\nduplicate station-date detail:")
print(dup[dup>1].to_string())
print("\nC - F =",len(tot)-int(ann.harmful_cyanobacteria_total_n.sum()))
print("MANUSCRIPT 7,612 matches NONE of the computed quantities:",not df["count"].eq(7612).iloc[:-1].any())
print("gap J - C =",7612-len(tot))
