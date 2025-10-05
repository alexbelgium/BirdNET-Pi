#!/usr/bin/env bash

# Align and localize labels using:
#   1) eBird (if EBIRD_API_TOKEN is set)  -> preferred
#   2) Wikipedia (localized title)        -> fallback
#   3) English + " !"                     -> final fallback
#
# Behavior requested:
#   - If a scientific name is already in labels_nm/labels_XX.txt,
#     REUSE the existing common name (no internet lookup).
#
# Inputs:
#   - Newest BirdNET-Go_classifier* file in CWD (baseline EN "latin_common")
#   - All language files in labels_nm/labels_XX.txt
# Outputs:
#   - Overwrites/creates labels_go/labels_XX.txt (aligned to baseline order)
#
# Env:
#   EBIRD_API_TOKEN (optional)  e.g., export EBIRD_API_TOKEN="your-key"
#
# Requires: bash>=4, curl, jq

shopt -s nullglob

die() { echo "Error: $*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || die "Missing dependency: $1"; }
need curl
need jq

# --- locate baseline ---
BASELINE_FILE="$(ls -1t BirdNET-Go_classifier* 2>/dev/null | head -n 1 || true)"
[[ -n "${BASELINE_FILE:-}" ]] || die "No baseline found (BirdNET-Go_classifier*). Place it in the current directory."
echo "Baseline: $BASELINE_FILE"

# --- ensure folders ---
[[ -d "labels_nm" ]] || die "Missing input folder: labels_nm/"
mkdir -p "labels_go"

# --- read baseline (latin -> EN common) preserving order ---
declare -A EN_MAP
declare -a ORDER
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
  latin="${line%%_*}"
  common="${line#*_}"
  [[ "$latin" == "$line" ]] && continue
  EN_MAP["$latin"]="$common"
  ORDER+=("$latin")
done < "$BASELINE_FILE"

# --- helpers ---
CACHE_DIR=".cache_labels"
mkdir -p "$CACHE_DIR"

encode_uri() { printf '%s' "$1" | jq -sRr @uri; }

wiki_title() {
  # Wikipedia localized title lookup (REST Summary then core API)
  local lang="$1" latin="$2"
  local encoded body status dtype title
  encoded="$(encode_uri "$latin")"

  # REST Summary
  body="$(curl -fsS -w '\n%{http_code}' "https://${lang}.wikipedia.org/api/rest_v1/page/summary/${encoded}" || true)"
  status="$(printf '%s' "$body" | tail -n1)"
  if [[ "$status" == "200" ]]; then
    local b
    b="$(printf '%s' "$body" | head -n-1)"
    dtype="$(printf '%s' "$b" | jq -r '.type // ""')"
    if [[ "$dtype" != "disambiguation" ]]; then
      title="$(printf '%s' "$b" | jq -r '.title // empty')"
      [[ -n "$title" ]] && { printf '%s' "$title"; return 0; }
    fi
  fi

  # Core API fallback
  body="$(curl -fsS -w '\n%{http_code}' "https://${lang}.wikipedia.org/w/api.php?action=query&format=json&titles=${encoded}" || true)"
  status="$(printf '%s' "$body" | tail -n1)"
  if [[ "$status" == "200" ]]; then
    local b pageid
    b="$(printf '%s' "$body" | head -n-1)"
    pageid="$(printf '%s' "$b" | jq -r '.query.pages|to_entries[0].value.pageid // -1')"
    title="$(printf '%s' "$b" | jq -r '.query.pages|to_entries[0].value.title // empty')"
    if [[ "$pageid" != "-1" && -n "$title" ]]; then
      printf '%s' "$title"
      return 0
    fi
  fi
  return 1
}

get_ebird_taxonomy_file() {
  # Download eBird taxonomy once per language (if token present)
  local lang="$1"
  local cache_json="${CACHE_DIR}/ebird_taxonomy_${lang}.json"
  [[ -s "$cache_json" ]] && { printf '%s' "$cache_json"; return 0; }
  [[ -n "${EBIRD_API_TOKEN:-}" ]] || return 1

  echo "Fetching eBird taxonomy for locale=${lang}..." >&2
  if ! curl -fsS -H "X-eBirdApiToken: ${EBIRD_API_TOKEN}" \
        "https://api.ebird.org/v2/ref/taxonomy/ebird?fmt=json&locale=${lang}" \
        -o "${cache_json}.tmp"; then
    rm -f "${cache_json}.tmp"
    return 1
  fi
  mv "${cache_json}.tmp" "$cache_json"
  printf '%s' "$cache_json"
}

ebird_common() {
  # Return localized common name via eBird (empty if not found or no token)
  local lang="$1" latin="$2"
  local tax_json
  tax_json="$(get_ebird_taxonomy_file "$lang")" || return 1
  jq -r --arg s "$latin" '
    .[] | select(.sciName == $s) | .comName // empty
  ' "$tax_json" | sed -n '1p' | sed 's/^[[:space:]]*//; s/[[:space:]]*$//' || true
}

process_lang_file() {
  local infile="$1"
  local base="$(basename "$infile")"   # e.g., labels_fr.txt
  local lang="${base#labels_}"; lang="${lang%.txt}"

  local outfile="labels_go/labels_${lang}.txt"
  local wiki_cache="${CACHE_DIR}/wiki_${lang}.tsv"

  echo ">> Processing ${infile} (lang=${lang})"
  # Load existing names for this lang
  declare -A LANG_MAP=()
  if [[ -s "$infile" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" || "${line:0:1}" == "#" ]] && continue
      local L="${line%%_*}"
      local C="${line#*_}"
      [[ "$L" == "$line" ]] && continue
      LANG_MAP["$L"]="$C"
    done < "$infile"
  fi

  # Load wiki cache (latin\tcommon)
  declare -A WIKI_CACHE=()
  if [[ -s "$wiki_cache" ]]; then
    while IFS=$'\t' read -r L C; do
      [[ -z "${L:-}" || -z "${C:-}" ]] && continue
      WIKI_CACHE["$L"]="$C"
    done < "$wiki_cache"
  fi

  : > "$outfile"
  local kept=0 filled=0 from_ebird=0 from_wiki=0 from_en=0

  for latin in "${ORDER[@]}"; do
    local common=""
    if [[ -n "${LANG_MAP[$latin]:-}" ]]; then
      # Already present in translated labels: reuse, no lookup
      common="${LANG_MAP[$latin]}"
      ((kept++))
    else
      # Missing: try eBird (preferred if token), then Wikipedia, else English + " !"
      if [[ -n "${EBIRD_API_TOKEN:-}" ]]; then
        local eb=""
        eb="$(ebird_common "$lang" "$latin" 2>/dev/null || true)"
        if [[ -n "$eb" ]]; then
          common="$eb"; ((from_ebird++))
        fi
      fi

      if [[ -z "$common" ]]; then
        if [[ -n "${WIKI_CACHE[$latin]:-}" ]]; then
          common="${WIKI_CACHE[$latin]}"; ((from_wiki++))
        else
          local title=""
          if title="$(wiki_title "$lang" "$latin")"; then
            common="$title"
            printf '%s\t%s\n' "$latin" "$common" >> "$wiki_cache"
            ((from_wiki++))
          fi
        fi
      fi

      if [[ -z "$common" ]]; then
        common="${EN_MAP[$latin]} !"; ((from_en++))
      fi

      ((filled++))
    fi

    printf '%s_%s\n' "$latin" "$common" >> "$outfile"
  done

  echo "   Kept(no lookup): $kept | Filled(lookups): $filled | eBird: $from_ebird | Wikipedia: $from_wiki | EN fallback: $from_en"
  echo "   Wrote: $outfile"
}

# --- iterate all input language files ---
mapfile -t LANG_FILES < <(ls -1 labels_nm/*.txt 2>/dev/null || true)
[[ ${#LANG_FILES[@]} -gt 0 ]] || die "No input files in labels_nm/ (expected labels_nm/labels_xx.txt)."

for lf in "${LANG_FILES[@]}"; do
  process_lang_file "$lf"
done

echo "All done."
