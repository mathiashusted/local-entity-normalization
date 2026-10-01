import pandas as pd
import sys
import json
import time
import urllib.request
import urllib.error
from urllib.parse import quote

def fetch_json(url, headers=None, retries=3):
    for attempt in range(retries):
        time.sleep(0.2)
        req = urllib.request.Request(url, headers=headers or {})
        try:
            with urllib.request.urlopen(req) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            result = json.load(e)
            if e.code in (429, 503) and attempt < retries - 1:
                time.sleep(4)
                continue
            return result

def hgnc_query(path):
    result = fetch_json(f"https://rest.genenames.org/{path}", {"Accept": "application/json"})
    if result is None or "response" not in result:
        return []
    return result["response"]["docs"]

# Resolve a gene symbol to every HGNC ID the public HGNC symbol search returns
def get_gene_ids(name):
    docs = hgnc_query(f"search/symbol/{quote(name, safe='')}")
    return [d["hgnc_id"] for d in docs if d.get("hgnc_id")]

# Verify the symbol against the HGNC record for the given (freshly resolved) hgnc_id
def hgnc_verify(symbol, hgnc_id):
    docs = hgnc_query(f"fetch/hgnc_id/{quote(hgnc_id, safe='')}")
    if not docs:
        return {"flag": "NO_ID_FOUND"}
    doc = docs[0]

    return {
        "hgnc_symbol":  doc.get("symbol"),
        "title":        doc.get("name"),
        "status":       doc.get("status"),
        "locus_type":   doc.get("locus_type"),
        "uniprot_ids":  ";".join(doc.get("uniprot_ids", [])),
        "entrez_id":    doc.get("entrez_id"),
        "prev_symbol":  ";".join(doc.get("prev_symbol", [])),
        "alias_symbol": ";".join(doc.get("alias_symbol", [])),
        "symbol_match": doc.get("symbol") == symbol,
        "approved":     doc.get("status") == "Approved",
    }

# Resolve a chemical name to every CID the public PubChem name search returns
def get_chemical_ids(name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name, safe='')}/cids/JSON"
    result = fetch_json(url)
    if "IdentifierList" not in result:
        return []
    return result["IdentifierList"]["CID"]

# Fetch the PubChem title for a CID, for display in the review queue
def pubchem_get_title(cid):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/Title/JSON"
    result = fetch_json(url)
    if "PropertyTable" not in result:
        return None
    return result["PropertyTable"]["Properties"][0]["Title"]

# Verify the canonical_name against the synonym list of a (freshly resolved) CID
def pubchem_verify_title(canonical_name, cid):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/synonyms/JSON"
    result = fetch_json(url)
    if "InformationList" not in result:
        raise ValueError("API did not return the expected format")
    synonyms = result["InformationList"]["Information"][0]["Synonym"]

    return canonical_name.lower() in (s.lower() for s in synonyms)


def resolve_chemical(name):
    id_hits = get_chemical_ids(name)
    if not id_hits:
        return None
    cid = id_hits[0]
    synonym_match = pubchem_verify_title(name, cid)

    if len(id_hits) > 1:
        flag = "AMBIGUOUS"
    elif synonym_match:
        flag = "OK"
    else:
        flag = "MISMATCH"

    return {
        "cid": cid,
        "title": pubchem_get_title(cid),
        "synonym_match": synonym_match,
        "n_name_hits": len(id_hits),
        "name_hit_ids": ";".join(map(str, id_hits)),
        "flag": flag,
    }

def resolve_gene(name):
    id_hits = get_gene_ids(name)
    if not id_hits:
        return None
    hgnc_id = id_hits[0]
    result = hgnc_verify(name, hgnc_id)
    not_found_flag = result.pop("flag", None)

    if not_found_flag:
        flag = not_found_flag
    elif len(id_hits) > 1:
        flag = "AMBIGUOUS"
    elif result["symbol_match"]:
        flag = "OK"
    elif name.lower() in {s.lower() for s in (result["alias_symbol"] + ";" + result["prev_symbol"]).split(";") if s}:
        flag = "ALIAS_OR_PREVIOUS_SYMBOL"
    elif not result["approved"]:
        flag = "WITHDRAWN_OR_UNAPPROVED"
    else:
        flag = "MISMATCH"

    return {
        "hgnc_id": hgnc_id,
        "n_name_hits": len(id_hits),
        "name_hit_ids": ";".join(id_hits),
        **result,
        "flag": flag,
    }

# The given CSV will either be a benchmark set which is to be matched against the APIs
# or an actual output from ECO-ID, in which case the produced (possibly hallucinated) IDs need to be verified as well
def resolve_csv_types(data):
    if "Refined Entity Name" in data.columns and "Entity Type" in data.columns:
        # If the LLM made no spelling correction, the input name is chosen instead of the empty LLM output
        name = data["Refined Entity Name"].fillna(data["Input Entity"])
        return "eco-id", name, data["Entity Type"]
    if "canonical_name" in data.columns and "entity_type" in data.columns:
        return "benchmark", data["canonical_name"], data["entity_type"]
    return "unknown", [None] * len(data), [None] * len(data)

def main():

    if len(sys.argv) != 2:
        print("Please specify the name of the csv as an argument!")
        return

    data = pd.read_csv(sys.argv[1], dtype=str)

    file_type, input_name, entity_types = resolve_csv_types(data)

    has_pubchem_cid = file_type == "eco-id" and "PubChem CID" in data.columns
    has_uniprot = file_type == "eco-id" and "UniProt" in data.columns
    pubchem_cids = data["PubChem CID"] if has_pubchem_cid else [None] * len(data)
    uniprot_ids = data["UniProt"] if has_uniprot else [None] * len(data)

    rows = []

    for name, entity_type, stored_cid, stored_uniprot in zip(input_name, entity_types, pubchem_cids, uniprot_ids):
        if pd.isna(name) or name == "N/A":
            rows.append({"canonical_name": name, "entity_type": entity_type, "flag": "MISSING_NAME"})
            continue
        

        unknown_type = pd.isna(entity_type)
        if unknown_type:
            print(f"Verifying name {name} of unknown type.")
        else:
            print(f"Verifying input {name} of type {entity_type}")

        result, resolved_type = None, entity_type

        # If the type is unknown, both will get checked, prioritizing type gene search, due to less abundance of false positive genes
        if unknown_type or entity_type == "gene":
            result = resolve_gene(name)
            resolved_type = "gene"
            # A real gene-symbol collision is a handful of hits. hundreds means the search likely
            # was unsuccessful and resolved to fuzzy matching
            if unknown_type and result and result["n_name_hits"] > 10:
                result = None
        if result is None and (unknown_type or entity_type == "chemical"):
            result = resolve_chemical(name)
            resolved_type = "chemical"

        if result is not None:
            match = "N/A"
            if entity_type == "chemical" and stored_cid is not None and not pd.isna(stored_cid):
                match = str(result["cid"]) == str(stored_cid).strip()
            elif entity_type == "gene" and stored_uniprot is not None and not pd.isna(stored_uniprot):
                match = stored_uniprot.strip() in result["uniprot_ids"].split(";")
            rows.append({"canonical_name": name, "entity_type": resolved_type, "eco_id_cid": stored_cid, "eco_id_uniprot": stored_uniprot, "match_eco_id": match, **result})
        else:
            flag = "UNRESOLVED_NAME" if unknown_type or entity_type in ("chemical", "gene") else "UNSUPPORTED_ENTITY_TYPE"
            rows.append({"canonical_name": name, "entity_type": entity_type, "flag": flag})

    pd.DataFrame(rows).to_csv("auditor_output.csv", index=False)


if __name__ == "__main__":
    main()
