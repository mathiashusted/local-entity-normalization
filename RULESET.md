# Benchmark annotation ruleset

*This rulset was developed under AI assistance as described in the thesis appendix.*

Annotation rules for `data/dataset/control.csv` (189 entities: 109 chemicals, 80 genes) and
`data/dataset/benchmark.csv` (319 rows: 162 chemical, 157 gene), in their final state. Rule numbers are
referenced in the thesis (Appendix, annotation ruleset and corrections table).

## 1. Design

`control.csv` holds one row per entity in its canonical form; `benchmark.csv` holds noisy variants
derived from these entities. Every benchmark row except the non-existent items (R3.4) is derived from
exactly one control entity. The set is a purposive challenge set, not a random sample: entities and
perturbations were chosen to cover specific phenomena, such as cross-namespace collisions,
spreadsheet-induced symbol corruption and encoding damage.

| Column | Definition |
|---|---|
| `id` | Row identifier with entity-type prefix (e.g. `CHEM-001`). Unique and immutable; removed rows leave gaps. |
| `input` | The string presented to the system under test, byte-exact. |
| `clean_form` | The intended form after removing the noise (R2.2). |
| `canonical_name` | The standard name of the target entity (R2.1). |
| `entity_type` | `chemical` or `gene`; populated on every row, including non-existent items. |
| `noise_type` | The perturbation class (R3.1). |
| `noise_detail` | Finer description of the perturbation; documentation only (R6.1). |
| `id_status` | `single`, `ambiguous` or `none` (R4.1). |
| `accepted_id` | Semicolon-separated identifiers scored as correct (PubChem CID or HGNC ID). |
| `note` | Curation rationale and documented exceptions. |

## 2. Names

**R2.1 Naming authority.** For genes, `canonical_name` is the HGNC approved symbol. Chemicals have no
naming authority; their `canonical_name` is the preferred name within the benchmark and must be a
registered synonym of the gold identifier.

**R2.2 Two-stage annotation.** `clean_form` is the form a competent reader would write after removing
the noise, before canonicalization. It carries a qualifier only if the input designates it
(`dextrose` → D-glucose, `vitamin H` → D-biotin, but `glucosse` → glucose). In the class
`underspecification`, dropping the qualifier is the perturbation, so `clean_form` restores it
(`lactate` → (S)-lactate).

## 3. Perturbation classes

**R3.1 The class describes the operation.** `noise_type` records the operation applied to the string
between `clean_form` and `input`, never a failure mode of a system. A row belongs to a class only if
the defining operation was applied:

| Class | Constraint |
|---|---|
| `casing` | string unchanged under case folding |
| `separator` | alphanumeric core preserved, separators changed |
| `word_order` | token multiset preserved, order changed |
| `typo` | character-level edit producing a non-word |
| `abbreviation` | input and clean form are the short and long form of the same name, in either direction |
| `synonym` | input is an alternative registered name, including orthographic variants |
| `underspecification` | a qualifier present in the canonical name is absent from the input |
| `tool_artifact` | damage introduced by software: encoding, truncation, spreadsheet coercion, appended tokens |
| `unperturbed` | input identical to the canonical name (R3.3) |
| `non_existent` | no referent exists (R3.4) |

Greek-to-Latin transliteration (`β-carotene` → beta-carotene) is a `synonym`; encoding damage of the
same characters (`Î²-carotene`) is a `tool_artifact`.

**R3.2 No composite perturbations.** Noise is defined only on the step from `input` to `clean_form`.
The step from `clean_form` to `canonical_name` is the normalization task, not a second perturbation
(`dmso` is a `casing` item; DMSO → dimethyl sulfoxide is normalization).

**R3.3 Unperturbed items.** Rows in which input, clean form and canonical name are identical are
negative controls. All seven are chemicals whose canonical name resolves to a single identifier.

**R3.4 Non-existent entities.** Fifteen items are plausible but unassigned names (impossible locants,
unnamed derivatives, unassigned gene family numbers). Each returns no match under case-insensitive
lookup in the PubChem synonym file, in all six HGNC name fields (all record statuses) and in the API
lookups used in the evaluation. `canonical_name`, `clean_form` and `accepted_id` are empty.

## 4. Gold determinacy

**R4.1 `id_status`.** `id_status` is a property of the input string, not of the entity, and is not
derived from what a retrieval service returns.

- `single`: the input determines exactly one identifier.
- `ambiguous`: a source entity exists, but the input does not uniquely determine an identifier.
- `none`: no source entity is recoverable.

A row is `ambiguous` if (1) the de-noised input omits a qualifier that distinguishes separate records
(stereochemistry, isomer, position, redox or protonation state, hydrate, family member; e.g. `glucose`,
`NAD`, `AMPK`), or (2) the input is a registered designation of a different entity, in the same
namespace (`PBS`, `VEGF`, `C9orf7`), in the other namespace (`CAMP`, `PETN`) or under another
organism's nomenclature (`Brca1`). A trivial name that uniquely designates a qualified form is `single`
(`dextrose`, `L-DOPA`); a typo of an ambiguous name is ambiguous (`glucosse`).

**R4.2 Reachability.** A gold identifier must be returnable by the retrieval layer for at least one
accepted name of the entity. Entities sharing an identifier are merged (`2-oxoglutarate` into
`2-oxoglutaric acid`, CID 51). An entity without a database record is `none`.

**R4.3 Use of `none`.** `none` covers only non-existent items (R3.4), inputs whose information was
destroyed by the perturbation, and class terms without a record. Family- and complex-level gene names
are `ambiguous`.

**R4.5 Variation within an entity.** Rows of the same entity may differ in `id_status`
(`BRAC1` single, `Brca1` ambiguous) but must agree on `canonical_name` and, where `single`, on
`accepted_id`.

**R4.6 Once per name.** Whether an unqualified name is ambiguous is decided once, recorded in `note`
and applied to every row reducing to that name (`glucose` and `lactose` are ambiguous throughout;
`ascorbic acid` denotes the L form and is not). Acid and conjugate-base forms are separate records; the
gold follows the record the canonical name resolves to, and an input designating the other form is
`ambiguous`.

## 5. Namespaces and retrieval

**R5.1 Inputs valid in both namespaces.** Such inputs (`CAMP`, `PETN`) keep one `entity_type` and are
`ambiguous` under R4.1 (2). The case-distinct form `cAMP` is `single`.

**R5.2 Synonym pruning.** A synonym is removed from an entity's accepted names if it is the approved
symbol or canonical name of another benchmark entity (`HTT`: previous symbol of SLC6A4, approved symbol
of huntingtin).

**R5.3 Gene field order.** Gene lookups query HGNC in the order `symbol`, `prev_symbol`,
`alias_symbol`, `name`, `prev_name`, `alias_name`. The first field with a match decides; if it matches
more than one gene, the lookup abstains. The fuzzy-matching baseline B2 pools all six fields.

## 6. Scope

**R6.1 `noise_detail`.** `noise_detail` takes 61 values and is documentation only; all quantitative
breakdowns use `noise_type`.

**R6.2 Coverage and scope.** Entities are common metabolites, reagents, drugs and well-studied human
genes; results are an upper bound for rarely annotated entities. Genes are human and resolved against
HGNC, chemicals against PubChem.

## 7. Verification

Candidate entities and perturbations were generated with the assistance of a large language model from
ECO-ID Supplementary Table S1, then filtered, annotated and verified by the author. Gold identifiers
were resolved against the PubChem PUG REST and HGNC REST services and checked by a verification script:
for chemicals, whether `canonical_name` is the title or a registered synonym of the accepted identifier
and how many identifiers the name lookup returns; for genes, the approved symbol, record status and
cross-references of the record. Because identifiers were obtained and checked through the same
services, this establishes consistency, not correctness. As an independent check, 25 control chemicals
(4 flagged during review, 21 drawn at random from three strata, seed 42) were compared with ChEBI by
InChIKey; all 21 random entities were confirmed, and the findings for the flagged entities are
documented in `note`. The output of the exact-lookup baseline B1 served as an additional audit: rows on
which it returned a non-gold identifier were reviewed against the services and, where they conflicted
with these rules, corrected under the applicable rule.

## 8. Integrity constraints

Constraints 1, 2, 4, 6, 10 and 14 are enforced by the validation scripts; the others were checked
manually.

1. `id` values are unique and immutable; removed rows leave gaps.
2. Every `canonical_name` in the benchmark exists in the control file.
3. No identifier is duplicated within a namespace in the control file.
4. `canonical_name` and `accepted_id` are empty if and only if `id_status` is `none`.
5. An entity that is `none` in the control file is `none` in every benchmark row derived from it.
6. `entity_type` is populated on every row.
7. `input` equals `canonical_name` for every control row.
8. Inputs with significant whitespace or non-ASCII characters match their expected byte strings.
9. No synonym equals another entity's canonical name (R5.2).
10. Rows sharing an entity agree on `canonical_name`, and on `accepted_id` wherever `id_status` is
    `single` (R4.5).
11. Rows whose `clean_form` reduces to the same unqualified name agree on `id_status` (R4.6).
12. Each row satisfies the constraint of its `noise_type` (R3.1).
13. No `noise_detail` value occurs under more than one `noise_type`.
14. No row is empty.
