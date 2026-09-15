"""Repeatable fictional names for generated portfolio data, using English letters."""

import random


ARABIC_GIVEN_NAMES = (
    "Ahmed", "Omar", "Khalid", "Yousef", "Hassan", "Ali", "Ibrahim", "Faisal",
    "Saeed", "Rashid", "Abdullah", "Hamdan", "Mansour", "Tariq", "Nasser", "Zayed",
    "Sultan", "Kareem", "Adel", "Majid", "Aisha", "Fatima", "Maryam", "Layla",
    "Noor", "Sara", "Amal", "Hessa", "Latifa", "Reem", "Salma", "Hana",
    "Maha", "Dana", "Noura", "Yasmin", "Amina", "Lina", "Hind", "Wafa",
)
ARABIC_FAMILY_NAMES = (
    "Al Mansoori", "Al Nuaimi", "Al Shamsi", "Al Mazrouei", "Al Hammadi",
    "Al Suwaidi", "Al Ketbi", "Al Dhaheri", "Al Ameri", "Al Qasimi",
    "Al Zaabi", "Al Kaabi", "Al Marri", "Al Hosani", "Al Balushi",
    "Al Mehairi", "Al Falasi", "Al Otaibi", "Al Saadi", "Al Habsi",
    "Hassan", "Saleh", "Khalil", "Mansour", "Nasser", "Darwish",
    "Farouk", "Hamdan", "Sabbagh", "Haddad", "Abboud", "Najjar",
)
ENGLISH_GIVEN_NAMES = (
    "James", "Oliver", "William", "Thomas", "Daniel", "Henry", "Samuel", "Jack",
    "Adam", "David", "Emma", "Olivia", "Charlotte", "Amelia", "Sophie", "Grace",
    "Emily", "Lucy", "Alice", "Isabella",
)
ENGLISH_FAMILY_NAMES = (
    "Bennett", "Parker", "Collins", "Morgan", "Turner", "Mitchell", "Walker",
    "Clarke", "Hughes", "Edwards", "Campbell", "Reed", "Foster", "Brooks",
    "Hayes", "Ward", "Cooper", "Palmer", "Spencer", "Sullivan",
)


def generated_tenant_name(key):
    """Keep each record's name stable without changing the financial-data RNG."""
    rng = random.Random(f"enginex-tenant-v1:{key}")
    if rng.random() < 0.8:
        given, family = ARABIC_GIVEN_NAMES, ARABIC_FAMILY_NAMES
    else:
        given, family = ENGLISH_GIVEN_NAMES, ENGLISH_FAMILY_NAMES
    return f"{rng.choice(given)} {rng.choice(family)}"
