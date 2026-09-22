import pandas as pd
import sys
import json
import time
import urllib.request
import urllib.error
from urllib.parse import quote

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        return json.load(e)


# Fetch the chemical ID via the public PubChem API
def get_chemical_id(name):
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(name, safe='')}/cids/JSON"
    result = fetch_json(url)
    if "IdentifierList" not in result:
        return None
    return result["IdentifierList"]["CID"][0]


# Resolve the gene symbol using the public HGNC REST API (the naming authority for
# human gene symbols), which also contains the UniProt accession and NCBI Gene ID.
def get_gene_hgnc(name):
    url = f"https://rest.genenames.org/fetch/symbol/{quote(name, safe='')}"
    result = fetch_json(url, headers={"Accept": "application/json"})
    docs = result.get("response", {}).get("docs", [])
    if not docs:
        return None
    doc = docs[0]
    uniprot_ids = doc.get("uniprot_ids") or []
    return {
        "hgnc_id": doc.get("hgnc_id"),
        "uniprot_id": uniprot_ids[0] if uniprot_ids else None,
        "ncbi_gene_id": doc.get("entrez_id"),
    }


ENTITY_TYPE_COLUMNS = {
    "chemical": ("pubchem_id", get_chemical_id),
    "gene": ("gene", get_gene_hgnc),
}

if len(sys.argv) != 2:
    raise ValueError("Please specify the name of the csv as an argument!")


data = pd.read_csv(sys.argv[1])

unresolved_count = 0
pubchem_ids = []
hgnc_ids = []
uniprot_ids = []
ncbi_gene_ids = []
for name, entity_type in zip(data["canonical_name"], data["entity_type"]):
    entry = ENTITY_TYPE_COLUMNS.get(entity_type)
    if entry is None:
        unresolved_count += 1
        print(name, entity_type, "unsupported entity_type")
        pubchem_ids.append(None)
        hgnc_ids.append(None)
        uniprot_ids.append(None)
        ncbi_gene_ids.append(None)
        continue
    column, handler = entry
    identifier = handler(name)
    time.sleep(0.2)
    print(name, entity_type, identifier)
    if column == "pubchem_id":
        pubchem_ids.append(identifier)
        hgnc_ids.append(None)
        uniprot_ids.append(None)
        ncbi_gene_ids.append(None)
    else:
        pubchem_ids.append(None)
        hgnc_ids.append(identifier.get("hgnc_id") if identifier else None)
        uniprot_ids.append(identifier.get("uniprot_id") if identifier else None)
        ncbi_gene_ids.append(identifier.get("ncbi_gene_id") if identifier else None)

print(f"Finished resolving. Unresolved entities: {unresolved_count}")

output_data = {
    'input_name': data["canonical_name"],
    'entity_type': data["entity_type"],
    'pubchem_id': pubchem_ids,
    'hgnc_id': hgnc_ids,
    'uniprot_id': uniprot_ids,
    'ncbi_gene_id': ncbi_gene_ids,
}
pd.DataFrame(output_data).to_csv("resolved_output.csv", index=False)