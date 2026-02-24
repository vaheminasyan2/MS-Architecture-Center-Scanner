# MS Architecture Center Scanner

A lightweight scanning tool used to analyze **[Azure Architecture Center articles](https://learn.microsoft.com/en-us/azure/architecture/browse/)** and determine which article includes a **Azure pricing calculator estimate link**.

## What the scanner evaluates

### Primary question (pass / fail)
**Does the Architecture Center article include a usable pricing estimate link?**

A scenario **passes (`criteria_passed = TRUE`)** if the included `.md` article contains **at least one** of the following:

1. **Azure Pricing Calcualtor Estimate link in this format**  
   `https://azure.com/e/*`
   `https://azure.microsoft.com/pricing/calculator?...shared-estimate=*`

2. **Service‑scoped Pricing Calculator Estimate link**  
   `https://azure.microsoft.com/pricing/calculator?...service=*`

### Failure reasons
If no usable estimate is found, the scenario fails with one of these reasons:

- **`no_estimate_link_calculator_tool_link_only`**  
  Pricing Calculator links exist, but they are **tool/root links only** (no saved or scoped estimate).

- **`no_estimate_link`**  
  No Pricing Calculator links of any kind were found.

## Repository files and what they do

- `scripts/build_scan_results_xlsx.py`  
  Converts JSON results into a human‑readable Excel file

  - `script/run_compare_only.py`
  Helper that compares scan output against `estimate_scenarios.xlsx`

- `scripts/scan_architecture_center_yml.py`  
  Scans YAML + included MD articles and produces `scan-results.json`

- `.github/scan_and_compare.yml`  
  GitHub Actions workflow that runs the scanner automatically

 - `estimate_scenarios.xlsx`**
   Reference list of known or submitted estimate scenarios used for comparison, validation, or tracking progress over time

## How to get started

### 1. Clone the Architecture Center repo
Clone https://github.com/MicrosoftDocs/architecture-center

### 2. Copy Scnaner Files
Copy scanner files into the cloned Architecture Center repo, preserving paths.

### 3. Run via GitHub Actions
- Push changes to your fork
- Open GitHub Actions
- Manually trigger the scan_and_compare workflow

## Outputs and how to interpret them
Upon successfully running workflow with GitHub actions you can download the `scan-results.xlsx` file, a human‑readable report for analysis and sharing.
Key columns include: 
- title - a title of the article from the yml file
- description - a description of the article from the yml file
- azureCategories - categories from the yml file
- ms.date — freshness / prioritization signal
- yml_URL - article URL
- image_download_urls — images found in the article
- estimate_link — selected usable estimate (if any)
- criteria_passed — pricing readiness indicator
- failure_reason — why the scenario failed
- yml_path - article yml file path
- include_md_path - article .md file path
- md_author_name / md_ms_author_name — ownership context
- comparison_status - result comparison 


