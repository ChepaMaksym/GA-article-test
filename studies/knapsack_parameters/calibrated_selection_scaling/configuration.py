"""Frozen study identities; no search, scoring or file access occurs here."""

CONTRACT = "calibrated-selection-v1"
LOG_SCHEMA = "ga-knapsack-calibrated-selection-log-v1"
TOTAL_EVALUATIONS = 100000
SOURCE_COMMIT = "c5bea0df8169749caaba5ce7dfcf21437aa1ca5c"
SOURCE_BASE = f"https://raw.githubusercontent.com/likr/kplib/{SOURCE_COMMIT}/"
CLASSES = (("UC", "00Uncorrelated"), ("WC", "01WeaklyCorrelated"),
           ("SC", "02StronglyCorrelated"))
PROFILES = ("k2", "k3", "adaptive")
DISPLAY_NAMES = {"k2": "Сталий відбір із двох особин",
                 "k3": "Сталий відбір із трьох особин",
                 "adaptive": "Еволюція розміру відбіркової групи",
                 "common": "Спільний сталий контроль"}


def baseline_parameters(n, profile, common=False):
    """Return a fresh parameter vector; common is a distinct n100 control."""
    if type(n) is not int or n not in (100, 500) or profile not in PROFILES:
        raise ValueError("Unregistered dimension or selection profile")
    if common and profile != "k2":
        raise ValueError("The common control always uses fixed k2")
    return {"p_m": 1 / n, "p_c": 0.9 if common or n == 500 else 1.0,
            "target_mu": 20 if common or n == 500 else 15,
            "tournament_size": 3 if profile == "k3" else 2, "elite_count": 1}


def task_descriptors(stage):
    """List exact source paths; absent files must never be substituted."""
    if stage not in ("technical", "main"):
        raise ValueError("Unknown input stage")
    specs = ((label, family) for family in range(70, 80) for label, _ in CLASSES)
    pairs = list(specs) if stage == "main" else [("UC", 0), ("WC", 1), ("SC", 5)]
    entries = []
    for n_index, n in enumerate((100, 500)):
        for local_index, (label, family) in enumerate(pairs):
            source_path = f"{dict(CLASSES)[label]}/n{n:05d}/R01000/s{family:03d}.kp"
            entries.append({"task_id": f"n{n:05d}-{label}-s{family:03d}", "n": n,
                            "class_label": label, "family": f"s{family:03d}",
                            "task_index": (63 + n_index * 30 + local_index if stage == "main"
                                           else 900 + n_index * 3 + local_index),
                            "source_path": source_path, "url": SOURCE_BASE + source_path})
    return entries


def _case(task, profile, seed, preparation_seed, common=False, stage="technical"):
    params = baseline_parameters(task["n"], profile, common)
    role = "common" if common else profile
    identity = f"{task['task_id']}-seed{seed}-{role}"
    return {"case_id": identity, "task_id": task["task_id"], "n": task["n"],
            "task_index": task["task_index"], "class_label": task["class_label"],
            "family": task["family"], "profile": profile, "role": role,
            "seed": seed, "preparation_seed": preparation_seed,
            "initial_parameters": params, "total_evaluations": TOTAL_EVALUATIONS,
            "stage": stage, "configuration_contract": CONTRACT}


def technical_cases():
    """Twenty-one calibrated pilots, including three n100 common controls."""
    cases = []
    for task in task_descriptors("technical"):
        cases.extend(_case(task, profile, 180999, 180998) for profile in PROFILES)
        if task["n"] == 100:
            cases.append(_case(task, "k2", 180999, 180998, common=True))
    return cases


def main_cases():
    """210 exploratory identities after amendment 1; no inferential replication."""
    cases = []
    for task in task_descriptors("main"):
        for seed in (181001,):
            cases.extend(_case(task, profile, seed, 181000, stage="main") for profile in PROFILES)
            if task["n"] == 100:
                cases.append(_case(task, "k2", seed, 181000, common=True, stage="main"))
    return cases


def compatibility_cases():
    """Retained legacy bank identities, with 5000 NEW evaluations, not total."""
    return [{"case_id": f"compat-{label}-s040-seed110001-{profile}",
             "task_id": f"{label}-s040", "n": 100, "profile": profile,
             "seed": 110001, "new_evaluations": 5000,
             "initial_parameters": {"p_m": 0.01, "p_c": 0.9, "target_mu": 30,
                                    "tournament_size": 3 if profile == "k3" else 2,
                                    "elite_count": 1},
             "reference_file": f"{label}-s040-bank-110001-{profile}.json.gz"}
            for label in ("UC", "SC") for profile in PROFILES]
