
# Predefined outlier archetypes and their behavioral effects.
# Tune these values to shape narrative outcomes.

OUTLIERS = {
    "social_justice": {
        "infection": 0.015,          # chance per day to adopt if neighbor has it
        "altruism_delta": +0.20,     # more sharing, esp. to minority
        "trust_delta": +0.03,        # small trust boost when transfers occur
        "cross_pref": +0.25,         # seeks cross-group ties
        "policy_push": +0.02,        # raises minority base resources (slowly)
        "polarization": -0.05,       # slightly reduces opinion polarization
    },
    "political_extremists": {
        "infection": 0.02,
        "altruism_delta": -0.20,     # hoard more
        "trust_delta": -0.05,        # trust erodes with conflict
        "cross_pref": -0.30,         # avoids cross-group ties
        "policy_push": -0.01,        # pushes policy reducing minority base
        "polarization": +0.15,       # increases opinion polarization
    },
    "environmentalists": {
        "infection": 0.012,
        "altruism_delta": +0.05,     # mild sharing
        "trust_delta": +0.02,
        "cross_pref": +0.10,
        "policy_push": 0.0,          # neutral on minority vs majority base
        "public_good": +0.03,        # invest into a public good that raises ALL base next day
        "polarization": -0.02,
    },
    "antivaxx_misinfo": {
        "infection": 0.018,
        "altruism_delta": -0.12,
        "trust_delta": -0.06,
        "cross_pref": -0.15,
        "policy_push": 0.0,
        "polarization": +0.10,
    },
    "religious_cult": {
        "infection": 0.01,
        "altruism_delta": 0.0,       # neutral overall, but in-group vs out-group asymmetry in sim
        "trust_delta": -0.02,        # out-group suspicion
        "cross_pref": -0.20,
        "policy_push": 0.0,
        "ingroup_bonus": +0.25,      # prefers giving to same affiliation
        "polarization": +0.05,
    },
}
