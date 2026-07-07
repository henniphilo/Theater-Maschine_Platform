"""Map catalog pixera names to OSC cue names when they differ."""

from __future__ import annotations

# catalog pixera_name → OSC pixera_name (from OSCBefehllisteAvatare.txt)
CATALOG_TO_OSC_PIXERA: dict[str, str] = {
    "BAK1_NicolasPflanzen3": "BAK1_Nicolas_Pflanzen",
    "BK0_Waran": "BKO_Waren",
    "MO1_SebMusik": "MO1_Seb_Musik",
    "MO3_Caro": "MO3_Dachs_Caro",
    "PET0_Baer_Thomas": "PETO_Baer_Thomas",
    "SCH2_Azaria_als_Schaf": "SCH2_AzariaAlsSchaf",
    "SCH2_AzariawirdSchaf": "SCH2_AzariaWirdSchaf",
    "SCH3_IngewirdSchaf": "SCH3_IngeWirdSchaf",
    "SCH5_SchafSolo_Mavie": "SCH5_SchafSoloMavie",
    "SCH7_Schaf_Single_Sebastian": "SCH7_SchafSingleSebastian",
    "SCH8_Viele_Schafe_Caro": "SCH8_VieleSchafeCaro",
}

_OSC_TO_CATALOG: dict[str, str] = {osc: catalog for catalog, osc in CATALOG_TO_OSC_PIXERA.items()}


def catalog_pixera_to_osc_name(pixera_name: str) -> str:
    return CATALOG_TO_OSC_PIXERA.get(pixera_name, pixera_name)


def osc_pixera_to_catalog_name(pixera_name: str) -> str:
    return _OSC_TO_CATALOG.get(pixera_name, pixera_name)
