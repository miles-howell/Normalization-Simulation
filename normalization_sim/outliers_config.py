
# Predefined outlier archetypes and their behavioral effects.
# Tune these values to shape narrative outcomes.
# trust_delta is added to a member's trust change whenever it asks for or gives help:
# a positive value applies to everyone, a negative one (suspicion) only toward the other opinion camp.
#
# Joining and leaving (see "Outlier groups" in the README):
# - join_threshold: share of an agent's neighbors who must be members before it can join at all (complex contagion);
#   high for high-commitment groups, low for broad low-cost movements. Agents have about 28 neighbors with the
#   default p_edge, so 0.05 means 2 member contacts and 0.08 means 3
# - infection: daily chance of joining once the threshold is met, at full ideological fit
# - position: the opinion the group stands for; it recruits mainly near it and pulls its members toward it
# - fit_width: how far from position the group still recruits; fit = exp(-((opinion - position) / fit_width)^2 / 2)
# - opinion_pull: daily share of the way a member's opinion moves toward position
# - exit_rate: daily chance that a member leaves (back to "none"); members who fit the group well leave at half
#   this rate, those who no longer fit at up to 1.5 times it
# - seed_size: members the group starts with: the agent closest to position and its neighbors closest to position

OUTLIERS = {
    "social_justice": {
        "join_threshold": 0.05,      # broad, low-cost movement
        "infection": 0.015,
        "position": -0.35,
        "fit_width": 0.25,
        "opinion_pull": 0.03,
        "exit_rate": 0.03,
        "seed_size": 10,
        "altruism_delta": +0.20,     # more sharing, esp. to minority
        "trust_delta": +0.03,        # small trust boost when help flows
        "cross_pref": +0.25,         # seeks cross-group ties
        "policy_push": +0.02,        # raises minority base resources (slowly)
        "polarization": -0.05,       # slightly reduces opinion polarization
    },
    "political_extremists": {
        "join_threshold": 0.06,      # high commitment: 2 contacts, but recruits hard
        "infection": 0.035,
        "position": +0.55,
        "fit_width": 0.25,
        "opinion_pull": 0.05,
        "exit_rate": 0.02,
        "seed_size": 10,
        "altruism_delta": -0.20,     # hoard more
        "trust_delta": -0.05,        # trust erodes with conflict
        "cross_pref": -0.30,         # avoids cross-group ties
        "policy_push": -0.01,        # pushes policy reducing minority base
        "polarization": +0.15,       # increases opinion polarization
    },
    "environmentalists": {
        "join_threshold": 0.05,      # broad, low-cost movement
        "infection": 0.012,
        "position": -0.1,
        "fit_width": 0.25,
        "opinion_pull": 0.02,
        "exit_rate": 0.04,           # low commitment, high turnover
        "seed_size": 10,
        "altruism_delta": +0.05,     # mild sharing
        "trust_delta": +0.02,
        "cross_pref": +0.10,
        "policy_push": 0.0,          # neutral on minority vs majority base
        "public_good": +0.03,        # invest into a public good that raises ALL base next day
        "polarization": -0.02,
    },
    "antivaxx_misinfo": {
        "join_threshold": 0.05,
        "infection": 0.015,
        "position": +0.3,
        "fit_width": 0.25,
        "opinion_pull": 0.04,
        "exit_rate": 0.03,
        "seed_size": 10,
        "altruism_delta": -0.12,
        "trust_delta": -0.06,
        "cross_pref": -0.15,
        "policy_push": 0.0,
        "polarization": +0.10,
    },
    "religious_cult": {
        "join_threshold": 0.08,      # highest commitment: recruits through several close ties
        "infection": 0.04,
        "position": -0.6,
        "fit_width": 0.2,
        "opinion_pull": 0.04,
        "exit_rate": 0.01,           # sticky, small and on the fringe
        "seed_size": 10,
        "altruism_delta": 0.0,       # neutral overall, but in-group vs out-group asymmetry in sim
        "trust_delta": -0.02,        # out-group suspicion
        "cross_pref": -0.20,
        "policy_push": 0.0,
        "ingroup_bonus": +0.25,      # prefers giving to same affiliation
        "polarization": +0.05,
    },
}
