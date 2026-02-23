# MS Architecture Center Scanner

A lightweight scanning tool used to analyze **Azure Architecture Center scenarios** and determine whether each article includes a **usable Azure pricing estimate**.

The tool is designed to support:
- Pricing coverage audits
- Identification of estimate gaps
- Prioritization of estimate creation work
- Reporting for PMMs, pricing, and content owners

---

## What the scanner evaluates

### Primary question (pass / fail)
**Does the Architecture Center article include a usable pricing estimate link?**

A scenario **passes (`criteria_passed = TRUE`)** if the included `.md` article contains **at least one** of the following:

1. **Azure Experience link**  
   `https://azure.com/e/*`

2. **Shared Pricing Calculator estimate**  
   `https://azure.microsoft.com/pricing/calculator?...shared-estimate=*`

3. **Service‑scoped Pricing Calculator link**  
   `https://azure.microsoft.com/pricing/calculator?...service=*`

---

### Failure reasons
If no usable estimate is found, the scenario fails with one of these reasons:

- **`no_estimate_link_calculator_tool_link_only`**  
  Pricing Calculator links exist, but they are **tool/root links only** (no saved or scoped estimate).

- **`no_estimate_link`**  
  No Pricing Calculator links of any kind were found.

---

### Images (informational only)
- Images are detected for **every article**
- Image URLs are captured and included in the output
- **Images do NOT affect pass/fail**
- This avoids false negatives while still providing visual context

---

### Metadata captured
For each scenario, the scanner also captures:
- `ms.date` (from YAML metadata)
- Article author (`author`)
- Microsoft author (`ms.author`)
- Detected pricing links
- Image download URLs

---

## Repository files

### Required files (core workflow)

These are the **only files required** to run the scanner end‑to‑end:

``
