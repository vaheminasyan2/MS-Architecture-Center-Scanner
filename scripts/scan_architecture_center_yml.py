#!/usr/bin/env python3
"""Architecture Center YAML Criteria Scanner (full version)

Applies requested changes:
1) Robust image extraction from included articles (regardless of image format / reference style / relative paths).
2) criteria_passed semantics: TRUE only when there is >=1 image AND >=1 usable estimate link.
   If only Pricing Calculator tool/root links exist (no usable estimate link), criteria_passed=FALSE and
   failure_reason='calculator_tool_link_only'.
3) Adds ms_date extracted from the .yml file (metadata.ms.date or top-level ms.date).

Scans all YAML under docs-root: *.yml and *.yaml.
Outputs scan-results.json (and optional scan-debug.json).
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

# [!INCLUDE[](...md)] directive inside YAML content string
INCLUDE_RE = re.compile(r"\[!INCLUDE\s*\[\s*\]\s*\(\s*([^\)\s]+\.md)\s*\)\s*\]", re.IGNORECASE)

# Links
AZURE_E_RE = re.compile(r"https?://azure\.com/e/[^\s\)\]\\\"']+", re.IGNORECASE)
LOCALE_SEG = r"(?:[a-z]{2}-[a-z]{2}/)?"
CALC_ANY_RE = re.compile(rf"https?://azure\.microsoft\.com/{LOCALE_SEG}pricing/calculator[^\s\)\]\\\"']*", re.IGNORECASE)
CALC_ROOT_RE = re.compile(rf"https?://azure\.microsoft\.com/{LOCALE_SEG}pricing/calculator/?(?=$|[\s\)\]\\\"'])", re.IGNORECASE)
SHARED_ESTIMATE_RE = re.compile(
    rf"https?://azure\.microsoft\.com/{LOCALE_SEG}pricing/calculator/?\?[^\s\)\]\\\"']*shared-estimate=[^\s\)\]\\\"']+",
    re.IGNORECASE,
)
SERVICE_RE = re.compile(
    rf"https?://azure\.microsoft\.com/{LOCALE_SEG}pricing/calculator/?\?[^\s\)\]\\\"']*service=[^\s\)\]\\\"']+",
    re.IGNORECASE,
)

# Image extraction (extension-agnostic)
MD_INLINE_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^\)]+)\)")
MD_REF_IMG_USE_RE = re.compile(r"!\[[^\]]*\]\[([^\]]+)\]")
MD_REF_DEF_RE = re.compile(r"(?im)^\[([^\]]+)\]:\s*(\S+)")
DOCS_IMAGE_BLOCK_RE = re.compile(r"(?im)^\s*:::image\b[^\n]*")
DOCS_IMAGE_SOURCE_RE = re.compile(r"(?i)\bsource\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))")
HTML_IMG_SRC_RE = re.compile(r"(?i)<img[^>]+\bsrc\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))")
HTML_SOURCE_SRCSET_RE = re.compile(r"(?i)<source[^>]+\bsrcset\s*=\s*(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))")

THUMB_EXCLUDE_RE = re.compile(r"(?i)(/browse/thumbs/|\bthumbs/|thumbnail|social_image|/icons/)")


def load_yaml(path: Path) -> Optional[dict]:
    if yaml is None:
        return None
    try:
        return yaml.safe_load(path.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        return None


def as_list(val):
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


def strip_query_fragment(s: str) -> str:
    return s.split('#', 1)[0].split('?', 1)[0]


def clean_ref(ref: str) -> str:
    ref = (ref or '').strip()
    if ref.startswith('<') and ref.endswith('>'):
        ref = ref[1:-1].strip()
    if ref.strip():
        ref = ref.strip().split()[0]
    return ref.strip('"').strip("'").strip().strip('()<>[]')


def resolve_repo_rel(base_dir: Path, ref: str, repo_root: Path) -> Optional[str]:
    ref = clean_ref(ref)
    if not ref:
        return None
    if re.match(r"^[a-zA-Z]+://", ref):
        return None
    ref = strip_query_fragment(ref)
    while ref.startswith('./'):
        ref = ref[2:]
    ref = ref.lstrip('/')
    p = (base_dir / ref).resolve()
    try:
        return p.relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return None


def make_raw_url(repo_slug: str, branch: str, repo_rel_path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo_slug}/{branch}/{repo_rel_path.lstrip('/')}"


def make_github_blob_url(repo_slug: str, branch: str, repo_rel_path: str) -> str:
    return f"https://github.com/{repo_slug}/blob/{branch}/{repo_rel_path.lstrip('/')}"


def make_learn_url_from_docs_path(repo_rel_yml: str) -> str:
    p = repo_rel_yml.replace('\\', '/')
    if p.startswith('docs/'):
        p = p[len('docs/'):]
    for ext in ('.yml', '.yaml'):
        if p.lower().endswith(ext):
            p = p[:-len(ext)]
            break
    return f"https://learn.microsoft.com/en-us/azure/architecture/{p}"


def parse_md_front_matter(md_text: str) -> dict:
    if not md_text.startswith('---'):
        return {}
    end = md_text.find('\n---', 3)
    if end == -1:
        return {}
    fm_text = md_text[3:end]
    if yaml is None:
        return {}
    try:
        d = yaml.safe_load(fm_text)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def extract_reference_map(md_text: str) -> Dict[str, str]:
    return {k.strip().lower(): clean_ref(v) for k, v in MD_REF_DEF_RE.findall(md_text)}


def add_candidate(out: List[str], raw: str):
    raw = clean_ref(raw)
    if not raw:
        return
    if THUMB_EXCLUDE_RE.search(raw):
        return
    out.append(raw)


def extract_image_refs(md_text: str) -> List[str]:
    refs: List[str] = []

    for raw in MD_INLINE_IMG_RE.findall(md_text):
        add_candidate(refs, raw)

    for line in DOCS_IMAGE_BLOCK_RE.findall(md_text):
        m = DOCS_IMAGE_SOURCE_RE.search(line)
        if not m:
            continue
        add_candidate(refs, m.group(1) or m.group(2) or m.group(3) or '')

    for g1, g2, g3 in HTML_IMG_SRC_RE.findall(md_text):
        add_candidate(refs, g1 or g2 or g3 or '')

    for g1, g2, g3 in HTML_SOURCE_SRCSET_RE.findall(md_text):
        raw = (g1 or g2 or g3 or '')
        if raw:
            raw = raw.split(',')[0].strip().split()[0]
        add_candidate(refs, raw)

    ref_map = extract_reference_map(md_text)
    for key in MD_REF_IMG_USE_RE.findall(md_text):
        target = ref_map.get(key.strip().lower())
        if target:
            add_candidate(refs, target)

    # dedupe preserving order
    seen = set()
    out: List[str] = []
    for r in refs:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def categorize_links(md_text: str) -> dict:
    azure_experience_links = sorted(set(AZURE_E_RE.findall(md_text)))
    calc_any = sorted(set(CALC_ANY_RE.findall(md_text)))

    shared_est = sorted({u for u in calc_any if SHARED_ESTIMATE_RE.search(u)})
    service_links = sorted({u for u in calc_any if SERVICE_RE.search(u)})

    calc_root: List[str] = []
    calc_other: List[str] = []
    for u in calc_any:
        u_clean = u.rstrip(').,;')
        if CALC_ROOT_RE.match(u_clean) and ('?' not in u_clean) and ('#' not in u_clean):
            calc_root.append(u_clean)
        else:
            calc_other.append(u)

    calc_root = sorted(set(calc_root))
    calc_other = sorted(set(calc_other))

    shared_estimate_links = sorted(set(azure_experience_links + shared_est))
    all_matching_links = sorted(set(azure_experience_links + calc_any))

    usable_estimate_links = sorted(set(azure_experience_links + shared_est + service_links))

    return {
        'azure_experience_links': azure_experience_links,
        'calculator_root_links': calc_root,
        'calculator_shared_estimate_links': shared_est,
        'calculator_service_links': service_links,
        'calculator_other_links': calc_other,
        'shared_estimate_links': shared_estimate_links,
        'pricing_calculator_links': calc_any,
        'all_matching_links': all_matching_links,
        'usable_estimate_links': usable_estimate_links,
    }


def extract_yaml_meta(data: dict) -> Tuple[Optional[str], Optional[str], List[str], Optional[str], Optional[str], Optional[str]]:
    meta = data.get('metadata') if isinstance(data.get('metadata'), dict) else {}
    title = meta.get('title') or data.get('title')
    description = meta.get('description') or data.get('description')
    azure_categories = as_list(data.get('azureCategories'))
    author = meta.get('author') or data.get('author')
    ms_author = meta.get('ms.author') or data.get('ms.author')
    ms_date = meta.get('ms.date') or data.get('ms.date')
    return title, description, azure_categories, author, ms_author, ms_date


def scan(repo_root: Path, repo_slug: str, branch: str, docs_root: str, debug: bool):
    docs_path = repo_root / docs_root
    yml_files = list(docs_path.rglob('*.yml')) + list(docs_path.rglob('*.yaml'))
    # dedupe
    yml_files = sorted({p.resolve(): p for p in yml_files}.values(), key=lambda p: str(p))

    counts = {
        'yml_total': len(yml_files),
        'yml_parsed': 0,
        'has_content': 0,
        'has_include': 0,
        'include_md_exists': 0,
        'md_has_images_any': 0,
        'md_has_usable_estimate_link': 0,
        'matched': 0,
        'failed': 0,
    }

    failures = []
    results = []

    for yml_path in yml_files:
        repo_rel_yml = yml_path.relative_to(repo_root).as_posix()
        base = {
            'criteria_passed': False,
            'failure_reason': '',
            'title': None,
            'description': None,
            'azureCategories': [],
            'ms_date': None,
            'yml_url': make_learn_url_from_docs_path(repo_rel_yml),
            'yml_github_url': make_github_blob_url(repo_slug, branch, repo_rel_yml),
            'yml_path': repo_rel_yml,
            'include_md_path': None,
            'include_md_github_url': None,
            'md_author_github': None,
            'md_ms_author': None,
            'image_paths': [],
            'image_download_urls': [],
            'image_exists_in_repo': [],
            'image_formats': [],
            'azure_experience_links': [],
            'calculator_root_links': [],
            'calculator_shared_estimate_links': [],
            'calculator_service_links': [],
            'calculator_other_links': [],
            'pricing_calculator_links': [],
            'shared_estimate_links': [],
            'all_matching_links': [],
            'usable_estimate_links': [],
        }

        data = load_yaml(yml_path)
        if not isinstance(data, dict):
            base['failure_reason'] = 'yaml_parse_failed'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason']})
            continue

        counts['yml_parsed'] += 1
        title, description, azure_categories, y_author, y_ms_author, ms_date = extract_yaml_meta(data)
        base['title'] = title
        base['description'] = description
        base['azureCategories'] = azure_categories
        base['ms_date'] = ms_date

        content = data.get('content')
        if not isinstance(content, str):
            base['failure_reason'] = 'missing_content_string'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason']})
            continue

        counts['has_content'] += 1
        inc = INCLUDE_RE.search(content)
        if not inc:
            base['failure_reason'] = 'no_include_directive'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason']})
            continue

        counts['has_include'] += 1
        include_md_ref = inc.group(1)
        include_md_rel = resolve_repo_rel(yml_path.parent, include_md_ref, repo_root)
        if not include_md_rel:
            base['failure_reason'] = 'include_md_unresolvable'
            base['include_md_path'] = include_md_ref
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason'], 'include_md_ref': include_md_ref})
            continue

        md_file = repo_root / include_md_rel
        base['include_md_path'] = include_md_rel
        base['include_md_github_url'] = make_github_blob_url(repo_slug, branch, include_md_rel)
        if not md_file.exists():
            base['failure_reason'] = 'include_md_missing'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason'], 'include_md_path': include_md_rel})
            continue

        counts['include_md_exists'] += 1
        md_text = md_file.read_text(encoding='utf-8', errors='ignore')
        fm = parse_md_front_matter(md_text)
        md_author = (fm.get('author') if isinstance(fm, dict) else None) or y_author
        md_ms_author = (fm.get('ms.author') if isinstance(fm, dict) else None) or y_ms_author
        base['md_author_github'] = md_author
        base['md_ms_author'] = md_ms_author

        link_info = categorize_links(md_text)
        for k, v in link_info.items():
            if k in base:
                base[k] = v

        usable = bool(link_info.get('usable_estimate_links'))
        if usable:
            counts['md_has_usable_estimate_link'] += 1

        img_refs = extract_image_refs(md_text)
        has_images = bool(img_refs)
        if has_images:
            counts['md_has_images_any'] += 1

        if not has_images:
            base['failure_reason'] = 'no_images_found'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason'], 'include_md_path': include_md_rel})
            continue

        if not usable:
            base['failure_reason'] = 'calculator_tool_link_only'
            results.append(base)
            counts['failed'] += 1
            if debug:
                failures.append({'yml_path': repo_rel_yml, 'reason': base['failure_reason'], 'include_md_path': include_md_rel})
            continue

        # Passed criteria: build image lists
        image_paths: List[str] = []
        image_download_urls: List[str] = []
        image_exists: List[bool] = []
        image_formats: List[str] = []

        for raw in img_refs:
            cleaned = clean_ref(raw)
            img_rel = resolve_repo_rel(md_file.parent, cleaned, repo_root)
            if img_rel is None:
                img_rel = strip_query_fragment(cleaned).lstrip('/')
            image_paths.append(img_rel)
            image_download_urls.append(make_raw_url(repo_slug, branch, img_rel))
            exists = bool((repo_root / img_rel).exists())
            image_exists.append(exists)
            image_formats.append(Path(img_rel).suffix.lower().lstrip('.'))

        base['criteria_passed'] = True
        base['failure_reason'] = ''
        base['image_paths'] = image_paths
        base['image_download_urls'] = image_download_urls
        base['image_exists_in_repo'] = image_exists
        base['image_formats'] = image_formats

        results.append(base)
        counts['matched'] += 1

    return results, counts, failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--repo', default=None, help='Repo slug (default: GITHUB_REPOSITORY)')
    ap.add_argument('--branch', default='main')
    ap.add_argument('--docs-root', default='docs')
    ap.add_argument('--output', default='scan-results.json')
    ap.add_argument('--debug', action='store_true', help='Write scan-debug.json with counts + sample failures')
    args = ap.parse_args()

    repo_slug = args.repo or os.getenv('GITHUB_REPOSITORY') or 'MicrosoftDocs/architecture-center'
    repo_root = Path.cwd()

    items, counts, failures = scan(repo_root, repo_slug, args.branch, args.docs_root, args.debug)

    out = {
        'repo': repo_slug,
        'branch': args.branch,
        'docs_root': args.docs_root,
        'count': len(items),
        'items': items,
    }

    Path(args.output).write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(
        f"Scanning docs_root={args.docs_root}: found {counts['yml_total']} YAML files; wrote {len(items)} items; "
        f"criteria_passed={counts['matched']}; failed={counts['failed']}; "
        f"md_has_usable_estimate_link={counts['md_has_usable_estimate_link']}"
    )

    if args.debug:
        dbg = {
            'counts': counts,
            'failures_total': len(failures),
            'failures_sample': failures[:1000],
        }
        Path('scan-debug.json').write_text(json.dumps(dbg, indent=2), encoding='utf-8')
        print(f"Wrote debug to scan-debug.json (failures_total={len(failures)})")


if __name__ == '__main__':
    main()
