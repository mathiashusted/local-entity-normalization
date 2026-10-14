import math


# Decision function
# Each item  in the table will get one of six possible outcomes:
# returned_on_none: id_status was none, but returned_id still wasn't empty
# abstained_on_none: id_status was none and returned_id correctly came back empty
# abstain_no_match: id_status wasn't none, but no matches were found
# abstain_ambig: id_status wasn't none, there was more than one candidate
# correct: id_status wasn't none, there was exactly one condidate and it was in the accepted_id list
# wrong_entity: if all else fails, the classification was wrong to begin with
def decide(row):
    if row['id_status'] == "none":
        if row['returned_id'] != "":
            return "returned_on_none"
        return "abstained_on_none"
    
    if row['n_candidates'] == 0:
        return "abstain_no_match"
    
    if row['n_candidates'] > 1:
        return "abstain_multiple"
    if row['returned_id'] in row['accepted_id'].split(";"):
        return "correct"
    return "wrong_entity"


# Number of successful resolutions
# Quote: Wilson (1927), the original: E. B. Wilson, "Probable inference, the law of succession, and statistical inference," Journal of the American Statistical Association 22(158), 209–212.

def wilson_score_interval(ups, total, z=1.96): # z=1.96 -> Calculate the 95% confidence interval
    if total == 0:
        return 0

    p = ups / total
    denominator = 1 + z**2 / total
    center = (p + z**2 / (2 * total)) / denominator
    half_w = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominator
    return (max(0.0, center - half_w), min(1.0, center + half_w))
