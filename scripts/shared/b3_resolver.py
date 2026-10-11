import json
import urllib.request
import urllib.error
from urllib.parse import quote
import time

FIELD_ORDER = ["symbol", "prev_symbol", "alias_symbol", "name", "prev_name", "alias_name"] # Ruleset fallback order

def fetch_json(url, headers=None, retries=3):
    for attempt in range(retries):
        time.sleep(0.2)
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(4)
                continue
            if e.code == 404:
                try:
                    return json.load(e)
                except json.JSONDecodeError:
                    return {} # This happened once in testing and lead to the run being invalid
            raise Exception("Error")
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(4)
                continue # This error happened to a network dropout in testing. Trying to catch it this way
            raise Exception("Error")


def hgnc_query(path):
    result = fetch_json(f"https://rest.genenames.org/{path}", {"Accept": "application/json"})
    if result == {}:
        return None
    if result is None or "response" not in result:
        raise ValueError("Unexpected response type")
    return result["response"]["docs"]

def get_gene_ids(name):
    result = []
    matched_field = ""
    for field in FIELD_ORDER:
        docs = hgnc_query(f"fetch/{field}/{quote(name, safe='')}")
        if docs is None:
            return [], "error_query"
        for doc in docs:
            values = doc.get(field)
            if isinstance(values, str):
                values = [values]
            for value in values:
                if doc.get("status") == "Approved" and value.lower() == name.lower():
                    result.append(doc["hgnc_id"])
        if result:
            matched_field = field
            break
    return result, matched_field


# Resolve a chemical name to every CID the public PubChem name search returns
def get_chemical_ids(name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name, safe='')}/cids/JSON"
    result = fetch_json(url)
    if "IdentifierList" not in result:
        return []
    return result["IdentifierList"]["CID"]


def resolve_chemical(name):
    id_hits = get_chemical_ids(name)
    distinct_ids = []
    for hit in id_hits:
        if hit not in distinct_ids:
            distinct_ids.append(hit)

    return {
        "n_candidates": len(distinct_ids) if distinct_ids is not None else 0,
        "returned_id": str(distinct_ids[0]) if len(distinct_ids) == 1 else "",
        "candidate_ids": ";".join(map(str, distinct_ids)),
    }

def resolve_gene(name):
    id_hits, matched_field = get_gene_ids(name)
    distinct_ids = []
    for hit in id_hits:
        if hit not in distinct_ids:
            distinct_ids.append(hit)

    return {
        "n_candidates": len(distinct_ids),
        "returned_id": distinct_ids[0] if len(distinct_ids) == 1 else "",
        "candidate_ids": ";".join(distinct_ids),
        "matched_field": matched_field,
    }

def handle_api_lookup(input, entity_type):
    result = None
    if entity_type == "chemical":
        result = resolve_chemical(input)
    elif entity_type == "gene":
        result = resolve_gene(input)
    else:
        raise ValueError(f"Invalid entity type: {entity_type}")
    return result
