# MS Architecture Center Scanner

A lightweight scanning tool used to analyzes **[Azure Architecture Center articles](https://learn.microsoft.com/en-us/azure/architecture/browse/)** to determine scenarios that include a usable **Azure pricing calculator estimate link** and compare it against a reference list of known scenarios, helping to identify cost-ready scenarios and highlight estimate gaps. 

## What the scanner evaluates

### Primary question (pass / fail)
The scanner ansswers the primary question **Does the Architecture Center article include a usable pricing estimate link?**. 

It **passes (`criteria_passed = TRUE`)** if markdown article contains **at least one** of the following:

1. **Azure Pricing Calcualtor Estimate links**  
   `https://azure.com/e/*` or `https://azure.microsoft.com/pricing/calculator?...shared-estimate=*`

2. **Service‑scoped Pricing Calculator Estimate link**  
   `https://azure.microsoft.com/pricing/calculator?...service=*`

### Failure reasons
If no usable estimate is found, the scenario fails with one of these reasons:

- **`no_estimate_link_calculator_tool_link_only`**  
  Pricing Calculator links exist, but they are **tool/root links only** (no saved or scoped estimate).

- **`no_estimate_link`**  
  No Pricing Calculator links of any kind were found in the article.

## Estimate comparison (post-scan)

For scenarios where `criteria_passed = TRUE`, the scanner compares the detected **usable estimate link** against a reference inventory in `estimate_scenarios.xlsx`. 

This comparison answers question: **Is this scenario already associated with the same estimate, or does it now reference a different estimate?**. This can help with on-going maintenace identifying scenarios with updated estimate links.

## Repository files and what they do

`scripts/scan_architecture_center_yml.py`.  
Scans Architecture Center YAML files and their included Markdown articles. Produces  `scan-results.json`.

`scripts/build_scan_results_xlsx.py`.  
Converts `scan-results.json` into a human‑readable Excel report `scan-results.xlsx`. This is the the authoritative JSON -> Excel converter. 

`estimate_scenarios.xlsx`.  
Reference inventory of known scenarios and their canonical estimate links. Used to detect new scenarios with estimates, updated estimates and gaps.

`script/run_compare_only.py`.  
Compares cost‑ready scenarios (`criteria_passed = TRUE`) against `estimate_scenarios.xlsx` and updates the `comparison_status` column in
  `scan-results.xlsx`

`.github/scan_and_compare.yml`.  
GitHub Actions workflow that runs the scanner automatically. 

## How to get started

### 1. Fork the Architecture Center repo
https://github.com/MicrosoftDocs/architecture-center.

### 2. Copy Scnaner Files
Copy scanner files into the forked Architecture Center repo, preserving the same paths.

### 3. Run via GitHub Actions
- Push changes to your fork
- Open GitHub Actions
- Select **Architecture Scan + Estimate Comparison** workflow and run it.  

## Outputs and how to interpret them
After a successful run, download the `scan-results.xlsx` from the workflow artificats. 

Key columns include: 

- title — Article title (from the YAML file)
- description — Article description (from the YAML file)
- azureCategories — Azure solution categories from the YAML file
- ms.date — Freshness / prioritization signal
- yml_url — Published Architecture Center article URL
- image_download_urls — Images found in the article (informational)
- estimate_link — Selected usable estimate link (if any)
- criteria_passed — Pricing readiness indicator
- failure_reason — Why the scenario failed (if applicable)
- yml_path — Path to the scenario YAML file
- include_md_path — Path to the included Markdown article
- md_author_name / md_ms_author_name — Ownership contextHow to use the results
- comparison_status - scenario comparison results.


| comparison_status value | Meaning |
|-------------------------|--------|
| `matched_existing_scenario_same_estimate` | Scenario exists in inventory and the scanned estimate link matches the inventory estimate link |
| `matched_existing_scenario_new_estimate` | Scenario exists in inventory, but the scanned estimate link is different |
| `new_estimate_candidate` | Scenario passed (`criteria_passed = TRUE`) but does not exist in the inventory |
| `not_applicable` | Scenario failed (`criteria_passed = FALSE`); comparison is not performed |

Only scenarios with `criteria_passed = TRUE` participate in estimate comparison.

