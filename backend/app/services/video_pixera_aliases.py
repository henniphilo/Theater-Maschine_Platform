"""Map catalog pixera names to OSC cue names when they differ.

OSC lists under media/video/OSCBefehlliste*.txt are the Pixera source of truth.
Catalog entries that already use those spellings need no alias.
"""

from __future__ import annotations

# catalog pixera_name → OSC pixera_name (from OSCBefehlliste*.txt)
CATALOG_TO_OSC_PIXERA: dict[str, str] = {
    "Ipad": "IPad",
}

# Former wrong send aliases — still accepted when reading OSC/QLab cue names.
_LEGACY_OSC_TO_CATALOG: dict[str, str] = {
    "BAK1_Nicolas_Pflanzen": "BAK1_NicolasPflanzen3",
    "BKO_Waren": "BK0_Waran",
    "MO1_Seb_Musik": "MO1_SebMusik",
    "MO3_Dachs_Caro": "MO3_Caro",
    "PETO_Baer_Thomas": "PET0_Baer_Thomas",
    "SCH2_AzariaAlsSchaf": "SCH2_Azaria_als_Schaf",
    "SCH2_AzariaWirdSchaf": "SCH2_AzariawirdSchaf",
    "SCH3_IngeWirdSchaf": "SCH3_IngewirdSchaf",
    "SCH5_SchafSoloMavie": "SCH5_SchafSolo_Mavie",
    "SCH7_SchafSingleSebastian": "SCH7_Schaf_Single_Sebastian",
    "SCH8_VieleSchafeCaro": "SCH8_Viele_Schafe_Caro",
}

_OSC_TO_CATALOG: dict[str, str] = {
    **{osc: catalog for catalog, osc in CATALOG_TO_OSC_PIXERA.items()},
    **_LEGACY_OSC_TO_CATALOG,
}


def catalog_pixera_to_osc_name(pixera_name: str) -> str:
    return CATALOG_TO_OSC_PIXERA.get(pixera_name, pixera_name)


def osc_pixera_to_catalog_name(pixera_name: str) -> str:
    return _OSC_TO_CATALOG.get(pixera_name, pixera_name)
