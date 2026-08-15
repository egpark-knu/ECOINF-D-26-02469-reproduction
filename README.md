# Reproducibility Deposit: Ecological Informatics (ECOINF-D-26-02469)

This repository contains the data and code necessary to reproduce the specific analyses and figures related to the sensitivity of harmful cyanobacteria and chlorophyll-a to residence time (tau), as well as the Sentinel-2 extraction scripts.

## Directory Structure

- `data/`: Contains the derived analysis-ready panel data. Raw bulk datasets are omitted due to licensing/size constraints, but the finalized subsets used in the model are provided.
  - `insitu_annual_analysis_panel.csv`: The main analysis panel used for the tau specificity models.
  - `weir_inventory.json`, `control_reaches.json`: Geometry metadata used in the GEE script.
- `code/`: Python scripts to run the extraction and models.
  - `hardening_specificity_analysis.py`: Runs the primary models and generates Figure 4.
  - `extract_round5_s2_indices.py`: Extracts NDCI/FAI indices from Google Earth Engine.
- `output/`: Generated locally when scripts are run.

## Reproduction Steps

1. Create a Python environment and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the main statistical analysis (generates models, tables, and figures in `output/`):
   ```bash
   python code/hardening_specificity_analysis.py
   ```
3. To reproduce the Sentinel-2 extraction, set your GEE credentials and run:
   ```bash
   export GEE_SERVICE_ACCOUNT="your_service_account@..."
   export GEE_KEY_PATH="path/to/key.json"
   python code/extract_round5_s2_indices.py
   ```

## Missing Values / Placeholders (P2 Pending)

**Note to authors:** Certain values are currently pending final execution (P2). The following placeholders must be resolved before final submission:
- `@@PENDING_M1_BETA_CYANO@@`: Pending final M1 specific coefficient for cyano.
- `@@PENDING_M1_BETA_CHLA@@`: Pending final M1 specific coefficient for chl-a.

## Source Data URLs
- Sentinel-2 & JRC Global Surface Water: Accessed via Google Earth Engine.
- In-situ data sources (NIER, K-water) are detailed in `THIRD_PARTY_NOTICES.md`.
