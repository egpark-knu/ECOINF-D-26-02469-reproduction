# Reproducibility Deposit: Ecological Informatics (ECOINF-D-26-02469)

This repository contains the data, code, and execution environments necessary to reproduce the specific analyses and figures related to the sensitivity of harmful cyanobacteria and chlorophyll-a to residence time (tau), Sentinel-2 extractions, event studies, and robustness branches.

## Directory Structure

- `data/`: Contains the derived analysis-ready panel data and sub-branch outputs (P2a, P2b, P2c/v4, P2d, P2e). Raw bulk datasets are omitted due to licensing/size constraints.
- `code/`: Python scripts to run the extraction and models for each branch. Legacy versions are preserved in `legacy_audit`.
- `protocols/`: Frozen protocols established prior to analysis execution to ensure integrity.

## Reproduction Steps

1. Create a Python environment and install requirements:
   `pip install -r requirements.txt`
2. Run the analyses by executing the scripts in `code/P2*` corresponding to the paper findings.
   Each folder contains standalone Python execution units mapped to specific methodological branches.
