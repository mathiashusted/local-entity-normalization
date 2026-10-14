import json
import urllib.request
import urllib.error
from urllib.parse import quote
import time
import os.path
import datetime

FIELD_ORDER = ["symbol", "prev_symbol", "alias_symbol", "name", "prev_name", "alias_name"] # Ruleset fallback order

def load_cache(path):
    if path is None:
        raise TypeError("Path must be specified")
    if not os.path.isfile(path):
        return {} # File does not exist
    data = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip() == "":
                continue
            entity = json.loads(line)
            data[entity["url"]] = entity
    return data

def append_cache(data, path):
    if path is None:
        raise TypeError("Path must be specified")
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data) + "\n")

def status_resolution(status, body):
    if status == 200:
        return json.loads(body)
    if status == 404:
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {}
        
    raise ValueError("Could not resolve")

def fetch_json(url, cache, cache_path, headers=None, retries=3):
    # Check cache first
    if cache is None or cache_path is None:
        raise TypeError("Cache and its path must be passed as an argument")
    if url in cache:
            return status_resolution(cache[url]["status"], cache[url]["body"])
    for attempt in range(retries):
        time.sleep(0.2)
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read().decode("utf-8")
                entity = {
                    "url": url,
                    "status": 200,
                    "body": data,
                    "fetched": datetime.datetime.now().isoformat()
                }
                cache[url] = entity
                append_cache(entity, cache_path)
                return status_resolution(200, data)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(4)
                continue
            if e.code == 404:
                data = e.read().decode("utf-8")
                entity = {
                    "url": url,
                    "status": 404,
                    "body": data,
                    "fetched": datetime.datetime.now().isoformat()
                }
                cache[url] = entity
                append_cache(cache[url], cache_path)
                return status_resolution(404, data)
            raise Exception(f"HTTP Error: {e}")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt < retries - 1:
                time.sleep(4)
                continue # This error happened to a network dropout in testing. Trying to catch it this way
            raise Exception(f"Network error: {e}")


def hgnc_query(path, cache, cache_path):
    result = fetch_json(f"https://rest.genenames.org/{path}", cache, cache_path, {"Accept": "application/json"})
    if result == {}:
        return None
    if result is None or "response" not in result:
        raise ValueError("Unexpected response type")
    return result["response"]["docs"]

def get_gene_ids(name, cache, cache_path):
    result = []
    matched_field = ""
    for field in FIELD_ORDER:
        docs = hgnc_query(f"fetch/{field}/{quote(name, safe='')}", cache, cache_path)
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
def get_chemical_ids(name, cache, cache_path):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name, safe='')}/cids/JSON"
    result = fetch_json(url, cache, cache_path, {"Accept": "application/json"})
    if result.get("Fault", {}).get("Code") == "PUGREST.NotFound":
        return []
    if "IdentifierList" not in result:
        raise ValueError("Unexpected response type")
    return result["IdentifierList"]["CID"]


def resolve_chemical(name, cache, cache_path):
    id_hits = get_chemical_ids(name, cache, cache_path)
    distinct_ids = []
    for hit in id_hits:
        if hit not in distinct_ids:
            distinct_ids.append(hit)

    return {
        "n_candidates": len(distinct_ids) if distinct_ids is not None else 0,
        "returned_id": str(distinct_ids[0]) if len(distinct_ids) == 1 else "",
        "candidate_ids": ";".join(map(str, distinct_ids)),
    }

def resolve_gene(name, cache, cache_path):
    id_hits, matched_field = get_gene_ids(name, cache, cache_path)
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

def handle_api_lookup(input, entity_type, cache, cache_path):
    result = None
    if entity_type == "chemical":
        result = resolve_chemical(input, cache, cache_path)
    elif entity_type == "gene":
        result = resolve_gene(input, cache, cache_path)
    else:
        raise ValueError(f"Invalid entity type: {entity_type}")
    return result


def verify_chemical_id(cid, cache, cache_path):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
    result = fetch_json(url, cache, cache_path)
    if result.get("Fault", {}).get("Code", {}) == "PUGREST.NotFound":
        return { "found": False, "status": "", "names": [] }
    if "InformationList" not in result:
        raise ValueError("Return schema does not match the expected")
    return { "found": True, "status": "", "names": result["InformationList"]["Information"][0].get("Synonym", []) }

def verify_gene_id(hgnc_id, cache, cache_path):
    url = f"https://rest.genenames.org/fetch/hgnc_id/{quote(hgnc_id, safe='')}"
    result = fetch_json(url, cache, cache_path, {"Accept": "application/json"})
    if result == {}:
        raise ValueError("Unexpected response type")

    docs = result["response"]["docs"]
    if len(docs) == 0:
        return {"found": False, "status": "", "names": [] }
    doc = docs[0]
    result = []
    for field in ["symbol", "prev_symbol", "alias_symbol", "name", "prev_name", "alias_name"]:
        values = doc.get(field, [])
        if isinstance(values, str):
            values = [values]
        for value in values:
            result.append(value)
    return { "found": True, "status": doc.get("status", ""), "names": result}