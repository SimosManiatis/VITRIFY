from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2, ceil, floor
from typing import List, Optional, Literal, Dict, Tuple
import requests
import logging
from logging_config import setup_logging

# Initialize logger (will be setup in main)
logger = logging.getLogger(__name__)

# ============================================================================
# SETTINGS
# ============================================================================

GEOCODER_USER_AGENT = "igu-reuse-tool/0.1 (CHANGE_THIS_TO_YOUR_EMAIL@DOMAIN)"

# Dismantling from Building (on-site removal) energy factor:
# kg CO2e per m² of IGU surface area removed from the existing building.
E_SITE_KGCO2_PER_M2 = 0.15

REMANUFACTURING_KGCO2_PER_M2 = 7.5
DISASSEMBLY_KGCO2_PER_M2 = 0.5

REPURPOSE_LIGHT_KGCO2_PER_M2 = 0.5
REPURPOSE_MEDIUM_KGCO2_PER_M2 = 1.0
REPURPOSE_HEAVY_KGCO2_PER_M2 = 2.0

STILLAGE_MANUFACTURE_KGCO2 = 500.0
STILLAGE_LIFETIME_CYCLES = 100
INCLUDE_STILLAGE_EMBODIED = False

# Emission factors in kgCO2e per tonne·km (tkm).
# These are GWP (CO2-equivalent) intensities, where:
# - "tonne" is the transported payload mass (IGUs + stillages) in metric tonnes
# - "km" is the distance travelled between the relevant locations (origin/processor/reuse)
EMISSIONFACTOR_TRUCK = 0.04   # kgCO2e/tkm (HGV lorry)
EMISSIONFACTOR_FERRY = 0.045  # kgCO2e/tkm (ferry)

BACKHAUL_FACTOR = 1.3

TRUCK_CAPACITY_T = 20.0
FERRY_CAPACITY_T = 1000.0

DISTANCE_FALLBACK_A_KM = 100.0
DISTANCE_FALLBACK_B_KM = 100.0

# Approximate surface mass of IGUs by glazing type (kg/m²).
# Single: approx. 4 mm float glass (~10 kg/m²).
MASS_PER_M2_SINGLE = 10.0
MASS_PER_M2_DOUBLE = 20.0
MASS_PER_M2_TRIPLE = 30.0

BREAKAGE_RATE_GLOBAL = 0.05
HUMIDITY_FAILURE_RATE = 0.05
SPLIT_YIELD = 0.95
REMANUFACTURING_YIELD = 0.90

IGUS_PER_STILLAGE = 20
STILLAGE_MASS_EMPTY_KG = 300.0
MAX_TRUCK_LOAD_KG = 20000.0

# Default transport modes for A-leg (building → processor) and B-leg (processor → 2nd site).
ROUTE_A_MODE = "HGV lorry"          # Road-only
ROUTE_B_MODE = "HGV lorry+ferry"    # Road + ferry mixed mode

# Installation energy for system routes (kg CO2e per m² of glass installed)
INSTALL_SYSTEM_KGCO2_PER_M2 = 0.25

DECIMALS = 3

# ============================================================================
# MODELLING ASSUMPTIONS (SEALANT)
# ============================================================================
# Secondary seal thickness is driven by the cavity thickness:
# 1. Double glazing: secondary_seal_thickness_mm = cavity_thickness_mm
# 2. Triple glazing: secondary_seal_thickness_mm = max(cavity_thickness_mm, cavity_thickness_2_mm)
# 3. Single glazing: secondary_seal_thickness_mm = 0.0 (no gas cavity)


# RepurposePreset defines the intensity preset for repurposing IGUs.
# It is used to select the appropriate CO2e per m² factor.
RepurposePreset = Literal["light", "medium", "heavy"]

GlazingType = Literal["double", "triple", "single"]
GlassType = Literal["annealed", "tempered", "laminated"]
CoatingType = Literal["none", "hard_lowE", "soft_lowE", "solar_control"]
SealantType = Literal["polysulfide", "polyurethane", "silicone", "combination", "combi"]
SpacerMaterial = Literal["aluminium", "steel", "warm_edge_composite"]
EdgeSealCondition = Literal["acceptable", "unacceptable", "not assessed"]

# TransportMode defines the mode of transport for route configurations.
# "HGV lorry"       = road-only
# "HGV lorry+ferry" = HGV lorry plus ferry leg(s).
TransportMode = Literal["HGV lorry", "HGV lorry+ferry"]

# ProcessLevel indicates whether calculations are at component or system level.
ProcessLevel = Literal["component", "system"]

# SystemPath indicates the overall system path: reuse or repurpose.
SystemPath = Literal["reuse", "repurpose"]


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Location:
    lat: float
    lon: float


@dataclass
class TransportModeConfig:
    """
    Transport mode configuration and distances between the three key locations:
    - origin    : project origin (Dismantling from Building / on-site removal)
    - processor : main processing site
    - reuse     : second site (reuse or repurposed installation location)
    """
    lat: float = 0.0  # unused, but kept for possible extensions


@dataclass
class TransportModeConfig:
    """
    Transport configuration between:
    - origin: project origin (Dismantling from Building / on-site removal)
    - processor: main processing site
    - reuse: second site (reuse/repurposed installation site)
    """
    origin: Location
    processor: Location
    reuse: Location
    include_ferry: bool = False
    backhaul_factor: float = BACKHAUL_FACTOR
    emissionfactor_truck: float = EMISSIONFACTOR_TRUCK
    emissionfactor_ferry: float = EMISSIONFACTOR_FERRY
    capacity_truck_t: float = TRUCK_CAPACITY_T
    capacity_ferry_t: float = FERRY_CAPACITY_T
    distance_fallback_A_km: float = DISTANCE_FALLBACK_A_KM
    distance_fallback_B_km: float = DISTANCE_FALLBACK_B_KM
    travel_truck_A_km_override: Optional[float] = None
    travel_ferry_A_km_override: Optional[float] = None
    travel_truck_B_km_override: Optional[float] = None
    travel_ferry_B_km_override: Optional[float] = None


@dataclass
class ProcessSettings:
    """
    Settings controlling process assumptions and routing:
    - breakage/humidity/splitting/remanufacturing yields
    - transport modes for A-leg (building→processor) and B-leg (processor→2nd site)
    - stillage settings and truck capacity
    - process level (component vs system) and system path (reuse vs repurpose)
    - Dismantling from Building and repurposing emission factors.
    """
    breakage_rate_global: float = BREAKAGE_RATE_GLOBAL
    humidity_failure_rate: float = HUMIDITY_FAILURE_RATE
    split_yield: float = SPLIT_YIELD
    remanufacturing_yield: float = REMANUFACTURING_YIELD
    route_A_mode: TransportMode = ROUTE_A_MODE  # type: ignore[assignment]
    route_B_mode: TransportMode = ROUTE_B_MODE  # type: ignore[assignment]
    igus_per_stillage: int = IGUS_PER_STILLAGE
    stillage_mass_empty_kg: float = STILLAGE_MASS_EMPTY_KG
    max_truck_load_kg: float = MAX_TRUCK_LOAD_KG
    process_level: ProcessLevel = "component"
    system_path: SystemPath = "reuse"
    e_site_kgco2_per_m2: float = E_SITE_KGCO2_PER_M2
    include_stillage_embodied: bool = INCLUDE_STILLAGE_EMBODIED
    repurpose_preset: RepurposePreset = "medium"
    repurpose_kgco2_per_m2: float = REPURPOSE_MEDIUM_KGCO2_PER_M2


@dataclass
class IGUCondition:
    visible_edge_seal_condition: EdgeSealCondition
    visible_fogging: bool
    cracks_chips: bool
    age_years: float
    reuse_allowed: bool


@dataclass
class SealGeometry:
    """
    Global seal geometry settings (constant for all IGUs in the batch).
    - primary_thickness_mm: Thickness of the primary seal (e.g. butyl).
    - primary_width_mm: Width of the primary seal.
    - secondary_width_mm: Width of the secondary seal.
    
    Note: Secondary seal *thickness* is not constant; it is derived from the
    IGU's cavity thickness(es) using the modelling rules defined above.
    """
    primary_thickness_mm: float
    primary_width_mm: float
    secondary_width_mm: float



@dataclass
class IGUGroup:
    """
    Describes a homogeneous group of IGUs with identical geometry, build-up and condition.
    Note: cavity_thickness_mm (and cavity_thickness_2_mm) are used both for the
    IGU build-up depth and to derive the secondary seal thickness.
    """
    quantity: int
    unit_width_mm: float
    unit_height_mm: float
    glazing_type: GlazingType
    glass_type_outer: GlassType
    glass_type_inner: GlassType
    coating_type: CoatingType
    sealant_type_secondary: SealantType
    spacer_material: SpacerMaterial
    interlayer_type: Optional[str]
    condition: IGUCondition
    thickness_outer_mm: float          # pane thickness (outer)
    thickness_inner_mm: float          # pane thickness (inner)
    cavity_thickness_mm: float         # cavity thickness (first cavity)
    IGU_depth_mm: float                # overall IGU build-up depth
    mass_per_m2_override: Optional[float] = None
    thickness_centre_mm: Optional[float] = None   # pane thickness (centre, triple)
    cavity_thickness_2_mm: Optional[float] = None # second cavity thickness (triple)
    sealant_type_primary: Optional[SealantType] = None  # Metadata only


@dataclass
class BatchInput:
    """
    Wrapper for a complete calculation batch: transport config, process settings and IGU groups.
    """
    transport: TransportModeConfig
    processes: ProcessSettings
    igu_groups: List[IGUGroup]


@dataclass
class EmissionBreakdown:
    """
    Full-chain emission breakdown for a batch.
    """
    dismantling_from_building_kgco2: float
    packaging_kgco2: float
    transport_A_kgco2: float
    disassembly_kgco2: float
    remanufacturing_kgco2: float
    quality_control_kgco2: float
    transport_B_kgco2: float
    total_kgco2: float
    extra: Dict[str, float]


@dataclass
class FlowState:
    """
    Tracks the mass/count flow through the recovery process, accounting for yield losses.
    """
    igus: float
    area_m2: float
    mass_kg: float


@dataclass
class ScenarioResult:
    """
    Summary of a Scenario run.
    """
    scenario_name: str
    total_emissions_kgco2: float
    by_stage: Dict[str, float]
    initial_igus: float
    final_igus: float
    initial_area_m2: float
    final_area_m2: float
    initial_mass_kg: float
    final_mass_kg: float
    yield_percent: float


# ============================================================================
# HELPER FUNCTIONS (project-scale aggregation and routing utilities)
# ============================================================================

def f3(x: float) -> str:
    """
    Format a float with a fixed number of decimal places (DECIMALS).
    """
    return f"{x:.{DECIMALS}f}"


def haversine_km(a: Location, b: Location) -> float:
    """
    Compute great-circle distance in km between two locations (lat/lon in degrees).
    Used to estimate straight-line distances between project origin, processor and reuse sites.
    """
    r = 6371.0
    lat1 = radians(a.lat)
    lon1 = radians(a.lon)
    lat2 = radians(b.lat)
    lon2 = radians(b.lon)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(h), sqrt(1 - h))
    return r * c


def compute_route_distances(transport: TransportModeConfig) -> Dict[str, float]:
    """
    Compute baseline A-leg and B-leg distances (truck and ferry) between the three sites.
    Returns a dict (km) for:
      - truck_A_km / ferry_A_km : origin → processor
      - truck_B_km / ferry_B_km : processor → reuse
    """
    base_A = haversine_km(transport.origin, transport.processor)
    base_B = haversine_km(transport.processor, transport.reuse)

    if base_A <= 0:
        base_A = transport.distance_fallback_A_km
    if base_B <= 0:
        base_B = transport.distance_fallback_B_km

    truck_A = (
        transport.travel_truck_A_km_override
        if transport.travel_truck_A_km_override is not None
        else base_A
    )
    ferry_A = (
        transport.travel_ferry_A_km_override
        if transport.travel_ferry_A_km_override is not None
        else 0.0
    )
    truck_B = (
        transport.travel_truck_B_km_override
        if transport.travel_truck_B_km_override is not None
        else base_B
    )
    ferry_B = (
        transport.travel_ferry_B_km_override
        if transport.travel_ferry_B_km_override is not None
        else 0.0
    )

    return {
        "truck_A_km": truck_A,
        "ferry_A_km": ferry_A,
        "truck_B_km": truck_B,
        "ferry_B_km": ferry_B,
    }


def default_mass_per_m2(glazing_type: GlazingType) -> float:
    """
    Default surface mass per m² for IGUs, by glazing type.
    Used when mass_per_m2_override is not provided in IGUGroup.
    """
    if glazing_type == "single":
        return MASS_PER_M2_SINGLE
    if glazing_type == "double":
        return MASS_PER_M2_DOUBLE
    if glazing_type == "triple":
        return MASS_PER_M2_TRIPLE
    raise ValueError("Unsupported glazing_type")


def aggregate_igu_groups(
    groups: List[IGUGroup], processes: ProcessSettings
) -> Dict[str, float]:
    """
    Aggregate IGU groups at project/batch level.

    Returns counts and surface areas describing:
      - total_IGU_surface_area_m2 : total IGU exposed surface area on the project
      - acceptable_igus           : IGUs acceptable for reuse after visual checks and condition filters
      - acceptable_area_m2        : surface area of acceptable IGUs
      - remanufactured_igus       : IGUs that can be remanufactured (component route, pane-splitting logic)
      - remanufactured_area_m2    : corresponding surface area
    """
    total_igus = 0
    total_IGU_surface_area_m2 = 0.0
    acceptable_igus = 0

    for g in groups:
        area_per_igu = (g.unit_width_mm / 1000.0) * (g.unit_height_mm / 1000.0)
        total_igus += g.quantity
        total_IGU_surface_area_m2 += area_per_igu * g.quantity

        # Define "acceptable" IGUs for reuse (no cracks, acceptable edge seal, no fogging, reuse allowed).
        if g.condition.reuse_allowed and not g.condition.cracks_chips:
            if (
                g.condition.visible_edge_seal_condition != "unacceptable"
                and not g.condition.visible_fogging
            ):
                acceptable_igus += g.quantity

    # Global breakage and humidity failure applied to acceptable IGUs.
    after_breakage = acceptable_igus * (1.0 - processes.breakage_rate_global)
    after_humidity = after_breakage * (1.0 - processes.humidity_failure_rate)

    # Simple pane-count logic: single/double/triple; mixed batches are currently not supported.
    if all(g.glazing_type == "single" for g in groups):
        panes_per_igu = 1
    elif all(g.glazing_type == "double" for g in groups):
        panes_per_igu = 2
    elif all(g.glazing_type == "triple" for g in groups):
        panes_per_igu = 3
    else:
        raise ValueError("Mixed glazing types in batch are not supported.")

    total_panes = after_humidity * panes_per_igu * processes.split_yield
    remanufactured_igus_raw = floor(total_panes / panes_per_igu)
    remanufactured_igus = remanufactured_igus_raw * processes.remanufacturing_yield

    average_area_per_igu = (
        total_IGU_surface_area_m2 / total_igus if total_igus > 0 else 0.0
    )
    acceptable_area_m2 = average_area_per_igu * acceptable_igus
    remanufactured_area_m2 = average_area_per_igu * remanufactured_igus

    return {
        "total_igus": float(total_igus),
        "total_IGU_surface_area_m2": total_IGU_surface_area_m2,
        "acceptable_igus": float(acceptable_igus),
        "acceptable_area_m2": acceptable_area_m2,
        "remanufactured_igus": float(remanufactured_igus),
        "remanufactured_area_m2": remanufactured_area_m2,
        "average_area_per_igu": average_area_per_igu,
    }


def compute_igu_mass_totals(
    groups: List[IGUGroup], stats: Dict[str, float]
) -> Dict[str, float]:
    """
    Compute IGU mass totals for the project batch:
      - total_mass_kg / total_mass_t
      - acceptable_mass_kg (mass associated with acceptable_igus)
      - remanufactured_mass_kg (mass associated with remanufactured_igus)
      - avg_mass_per_igu_kg
    """
    total_mass_kg = 0.0

    for g in groups:
        area_per_igu = (g.unit_width_mm / 1000.0) * (g.unit_height_mm / 1000.0)
        m2 = area_per_igu * g.quantity
        mass_per_m2 = (
            g.mass_per_m2_override
            if g.mass_per_m2_override is not None
            else default_mass_per_m2(g.glazing_type)
        )
        total_mass_kg += m2 * mass_per_m2

    total_mass_t = total_mass_kg / 1000.0
    avg_mass_per_igu_kg = (
        total_mass_kg / stats["total_igus"] if stats["total_igus"] > 0 else 0.0
    )

    acceptable_mass_kg = avg_mass_per_igu_kg * stats["acceptable_igus"]
    remanufactured_mass_kg = avg_mass_per_igu_kg * stats["remanufactured_igus"]

    return {
        "total_mass_kg": total_mass_kg,
        "total_mass_t": total_mass_t,
        "acceptable_mass_kg": acceptable_mass_kg,
        "remanufactured_mass_kg": remanufactured_mass_kg,
        "avg_mass_per_igu_kg": avg_mass_per_igu_kg,
    }


def packaging_factor_per_igu(processes: ProcessSettings) -> float:
    """
    Compute the stillage manufacturing emission allocation per IGU (kg CO2e/IGU),
    based on stillage lifetime and IGUs per stillage. Returns 0 if stillage emissions
    are excluded or the parameters are invalid.
    """
    if not processes.include_stillage_embodied:
        return 0.0
    if processes.igus_per_stillage <= 0 or STILLAGE_LIFETIME_CYCLES <= 0:
        return 0.0
    return STILLAGE_MANUFACTURE_KGCO2 / (
        STILLAGE_LIFETIME_CYCLES * processes.igus_per_stillage
    )


# ============================================================================
# SEALANT VOLUME HELPERS
# ============================================================================

def secondary_seal_thickness_mm_for_group(g: IGUGroup) -> float:
    """
    Derive the secondary seal thickness based on glazing type and cavity thickness.
    Rules:
      - Double: equals cavity_thickness_mm
      - Triple: equals max(cavity_thickness_mm, cavity_thickness_2_mm)
      - Single: 0.0
    """
    if g.glazing_type == "single":
        return 0.0
    elif g.glazing_type == "double":
        return g.cavity_thickness_mm
    elif g.glazing_type == "triple":
        c1 = g.cavity_thickness_mm
        c2 = g.cavity_thickness_2_mm if g.cavity_thickness_2_mm is not None else 0.0
        return max(c1, c2)
    else:
        raise ValueError(f"Unsupported glazing type for seal calculation: {g.glazing_type}")


def compute_sealant_volumes(group: IGUGroup, seal: SealGeometry) -> Dict[str, float]:
    """
    Compute primary and secondary sealant volumes for an IGU group.
    Returns a dict with per-IGU and total volumes (m3).
    """
    # 1. Dimensions in metres
    W_m = group.unit_width_mm / 1000.0
    H_m = group.unit_height_mm / 1000.0
    perimeter_m = 2.0 * (W_m + H_m)

    # 2. Primary seal (constant cross-section)
    # Area = thickness * width
    A_primary_m2 = (seal.primary_thickness_mm / 1000.0) * (seal.primary_width_mm / 1000.0)
    V_primary_igu_m3 = perimeter_m * A_primary_m2

    # 3. Secondary seal (derived thickness * constant width)
    t_sec_mm = secondary_seal_thickness_mm_for_group(group)
    A_secondary_m2 = (t_sec_mm / 1000.0) * (seal.secondary_width_mm / 1000.0)
    V_secondary_igu_m3 = perimeter_m * A_secondary_m2

    # 4. Totals
    V_primary_total_m3 = V_primary_igu_m3 * group.quantity
    V_secondary_total_m3 = V_secondary_igu_m3 * group.quantity

    return {
        "primary_volume_per_igu_m3": V_primary_igu_m3,
        "secondary_volume_per_igu_m3": V_secondary_igu_m3,
        "primary_volume_total_m3": V_primary_total_m3,
        "secondary_volume_total_m3": V_secondary_total_m3,
        "secondary_thickness_mm": t_sec_mm,
    }


# ============================================================================
# DISMANTLING & TRANSPORT TO PROCESSOR STAGE
# (Previously "Phase A" – renamed to avoid confusion with LCA Stage A)
# ============================================================================

def compute_dismantling_and_transport_to_processor_stage(
    transport: TransportModeConfig,
    processes: ProcessSettings,
    groups: List[IGUGroup],
) -> Dict[str, object]:
    """
    Compute emissions and mass/area stats for the stage:
    "Dismantling from Building & transport to processor" (A-leg).

    Includes:
      - Dismantling from Building (E_site)
      - Packaging (stillage manufacturing, if included)
      - Transport A (origin → processor, truck + optional ferry)
    """
    stats = aggregate_igu_groups(groups, processes)
    masses = compute_igu_mass_totals(groups, stats)

    n_stillages_A = (
        ceil(stats["acceptable_igus"] / processes.igus_per_stillage)
        if processes.igus_per_stillage > 0
        else 0
    )
    stillage_mass_A_kg = n_stillages_A * processes.stillage_mass_empty_kg

    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"]
    ferry_A_km = distances["ferry_A_km"]

    # Route A mode: HGV-only vs HGV lorry + ferry.
    if processes.route_A_mode == "HGV lorry":
        ferry_A_km = 0.0

    truck_A_km *= transport.backhaul_factor
    ferry_A_km *= transport.backhaul_factor

    mass_A_t = (masses["acceptable_mass_kg"] + stillage_mass_A_kg) / 1000.0

    dismantling_kgco2 = (
        stats["total_IGU_surface_area_m2"] * processes.e_site_kgco2_per_m2
    )

    pkg_per_igu = packaging_factor_per_igu(processes)
    packaging_kgco2 = stats["acceptable_igus"] * pkg_per_igu

    transport_A_kgco2 = mass_A_t * (
        truck_A_km * transport.emissionfactor_truck
        + ferry_A_km * transport.emissionfactor_ferry
    )

    return {
        "stats": stats,
        "masses": masses,
        "n_stillages_A": n_stillages_A,
        "stillage_mass_A_kg": stillage_mass_A_kg,
        "truck_A_km_eff": truck_A_km,
        "ferry_A_km_eff": ferry_A_km,
        "mass_A_t": mass_A_t,
        "dismantling_kgco2": dismantling_kgco2,
        "packaging_kgco2": packaging_kgco2,
        "transport_A_kgco2": transport_A_kgco2,
        "packaging_per_igu": pkg_per_igu,
    }


# ============================================================================
# SYSTEM ROUTE – B-LEG TRANSPORT (PROCESSOR → REUSE / REPURPOSED SITE)
# ============================================================================

def compute_system_transport_B(
    transport: TransportModeConfig,
    processes: ProcessSettings,
    stats: Dict[str, float],
    masses: Dict[str, float],
) -> Dict[str, float]:
    """
    Compute emissions and mass/transport stats for the B-leg:
    processor → reuse/repurposed destination.
    """
    if processes.igus_per_stillage > 0:
        n_stillages_B = ceil(
            stats["acceptable_igus"] / processes.igus_per_stillage
        )
    else:
        n_stillages_B = 0

    stillage_mass_B_kg = n_stillages_B * processes.stillage_mass_empty_kg

    distances = compute_route_distances(transport)
    truck_B_km = distances["truck_B_km"]
    ferry_B_km = distances["ferry_B_km"]

    # Route B mode: HGV-only vs HGV lorry + ferry.
    if processes.route_B_mode == "HGV lorry":
        ferry_B_km = 0.0

    truck_B_km *= transport.backhaul_factor
    ferry_B_km *= transport.backhaul_factor

    mass_B_t = (masses["acceptable_mass_kg"] + stillage_mass_B_kg) / 1000.0

    transport_B_kgco2 = mass_B_t * (
        truck_B_km * transport.emissionfactor_truck
        + ferry_B_km * transport.emissionfactor_ferry
    )

    return {
        "transport_B_kgco2": transport_B_kgco2,
        "truck_B_km_eff": truck_B_km,
        "ferry_B_km_eff": ferry_B_km,
        "mass_B_t": mass_B_t,
        "n_stillages_B": float(n_stillages_B),
        "stillage_mass_B_kg": stillage_mass_B_kg,
    }


# ============================================================================
# FULL CHAIN (kept for later development; not used in main flow yet)
# ============================================================================

def compute_full_chain_emissions(batch: BatchInput) -> EmissionBreakdown:
    """
    Compute a full-chain emission breakdown (Dismantling from Building
    → processor → second site), for possible future integration.
    """
    stats = aggregate_igu_groups(batch.igu_groups, batch.processes)
    masses = compute_igu_mass_totals(batch.igu_groups, stats)

    n_stillages_A = (
        ceil(stats["acceptable_igus"] / batch.processes.igus_per_stillage)
        if batch.processes.igus_per_stillage > 0
        else 0
    )

    if batch.processes.igus_per_stillage > 0:
        if batch.processes.process_level == "component":
            n_stillages_B = ceil(
                stats["remanufactured_igus"] / batch.processes.igus_per_stillage
            )
        else:
            n_stillages_B = ceil(
                stats["acceptable_igus"] / batch.processes.igus_per_stillage
            )
    else:
        n_stillages_B = 0

    stillage_mass_A_kg = n_stillages_A * batch.processes.stillage_mass_empty_kg
    stillage_mass_B_kg = n_stillages_B * batch.processes.stillage_mass_empty_kg

    dismantling_kgco2 = (
        stats["total_IGU_surface_area_m2"] * batch.processes.e_site_kgco2_per_m2
    )

    pkg_per_igu = packaging_factor_per_igu(batch.processes)
    packaging_kgco2 = stats["acceptable_igus"] * pkg_per_igu

    distances = compute_route_distances(batch.transport)
    truck_A_km = distances["truck_A_km"]
    ferry_A_km = distances["ferry_A_km"]
    truck_B_km = distances["truck_B_km"]
    ferry_B_km = distances["ferry_B_km"]

    if batch.processes.route_A_mode == "HGV lorry":
        ferry_A_km = 0.0
    if batch.processes.route_B_mode == "HGV lorry":
        ferry_B_km = 0.0

    truck_A_km *= batch.transport.backhaul_factor
    ferry_A_km *= batch.transport.backhaul_factor
    truck_B_km *= batch.transport.backhaul_factor
    ferry_B_km *= batch.transport.backhaul_factor

    mass_A_t = (masses["acceptable_mass_kg"] + stillage_mass_A_kg) / 1000.0

    if batch.processes.process_level == "component":
        mass_B_t = (masses["remanufactured_mass_kg"] + stillage_mass_B_kg) / 1000.0
    else:
        mass_B_t = (masses["acceptable_mass_kg"] + stillage_mass_B_kg) / 1000.0

    transport_A_kgco2 = mass_A_t * (
        truck_A_km * batch.transport.emissionfactor_truck
        + ferry_A_km * batch.transport.emissionfactor_ferry
    )
    transport_B_kgco2 = mass_B_t * (
        truck_B_km * batch.transport.emissionfactor_truck
        + ferry_B_km * batch.transport.emissionfactor_ferry
    )

    disassembly_kgco2 = 0.0
    if batch.processes.process_level == "system":
        disassembly_kgco2 = stats["acceptable_area_m2"] * DISASSEMBLY_KGCO2_PER_M2

    remanufacturing_kgco2 = 0.0
    if batch.processes.process_level == "component":
        remanufacturing_kgco2 = (
            stats["remanufactured_area_m2"] * REMANUFACTURING_KGCO2_PER_M2
        )
    elif batch.processes.process_level == "system":
        if batch.processes.system_path == "reuse":
            remanufacturing_kgco2 = 0.0
        elif batch.processes.system_path == "repurpose":
            repurpose_area_m2 = stats["acceptable_area_m2"]
            remanufacturing_kgco2 = (
                repurpose_area_m2 * batch.processes.repurpose_kgco2_per_m2
            )

    quality_control_kgco2 = 0.0

    total_kgco2 = (
        dismantling_kgco2
        + packaging_kgco2
        + transport_A_kgco2
        + disassembly_kgco2
        + remanufacturing_kgco2
        + quality_control_kgco2
        + transport_B_kgco2
    )

    extra: Dict[str, float] = {}
    extra.update(stats)
    extra.update(masses)
    extra["n_stillages_A"] = float(n_stillages_A)
    extra["n_stillages_B"] = float(n_stillages_B)
    extra["truck_A_km_effective"] = truck_A_km
    extra["ferry_A_km_effective"] = ferry_A_km
    extra["truck_B_km_effective"] = truck_B_km
    extra["ferry_B_km_effective"] = ferry_B_km
    extra["mass_A_t"] = mass_A_t
    extra["mass_B_t"] = mass_B_t
    extra["disassembly_kgco2"] = disassembly_kgco2
    extra["process_level"] = batch.processes.process_level  # type: ignore[assignment]
    extra["system_path"] = batch.processes.system_path      # type: ignore[assignment]
    extra["packaging_per_igu_kgco2"] = pkg_per_igu
    extra["repurpose_preset"] = batch.processes.repurpose_preset  # type: ignore[assignment]
    extra["repurpose_kgco2_per_m2"] = batch.processes.repurpose_kgco2_per_m2

    return EmissionBreakdown(
        dismantling_from_building_kgco2=dismantling_kgco2,
        packaging_kgco2=packaging_kgco2,
        transport_A_kgco2=transport_A_kgco2,
        disassembly_kgco2=disassembly_kgco2,
        remanufacturing_kgco2=remanufacturing_kgco2,
        quality_control_kgco2=quality_control_kgco2,
        transport_B_kgco2=transport_B_kgco2,
        total_kgco2=total_kgco2,
        extra=extra,
    )


def apply_yield_loss(state: FlowState, loss_fraction: float) -> FlowState:
    """
    Apply a generic yield loss to the flow state.
    Returns a new FlowState with reduced quantities.
    """
    keep_factor = 1.0 - loss_fraction
    return FlowState(
        igus=state.igus * keep_factor,
        area_m2=state.area_m2 * keep_factor,
        mass_kg=state.mass_kg * keep_factor,
    )


def prompt_igu_source() -> str:
    """
    Step 2: Ask for IGU source (manual vs database).
    """
    logger.info("\n--- Step 1: IGU Source Selection ---")
    source = prompt_choice("Select IGU definition source", ["manual", "database"], default="manual")
    
    if source == "database":
        # Placeholder for DB lookup
        # db_id = input("Enter Saint-Gobain IGU product ID: ").strip()
        logger.info("Saint Gobain Database Not Found")
        logger.info("Falling back to manual definition.")
        # Fallback to manual
        return "manual"
    
    return "manual"


def define_igu_system_from_manual() -> Tuple[IGUGroup, SealGeometry]:
    """
    Step 3: Define IGU system (geometry + build-up + materials) manually.
    Prompts user for all IGU parameters and constructs the IGUGroup and SealGeometry.
    """
    logger.info("\n--- Step 2: IGU System Definition (Manual) ---")
    
    logger.info("\nDefine global seal geometry (constant for all IGUs).")
    p_th_str = input("Primary seal thickness (mm) [constant]: ").strip()
    p_wd_str = input("Primary seal width (mm) [constant]: ").strip()
    s_wd_str = input("Secondary seal width (mm) [constant]: ").strip()

    try:
        seal_p_th = float(p_th_str)
        seal_p_wd = float(p_wd_str)
        seal_s_wd = float(s_wd_str)
    except ValueError:
        logger.info("Invalid numeric input for seal geometry.")
        raise SystemExit(1)

    seal_geometry = SealGeometry(
        primary_thickness_mm=seal_p_th,
        primary_width_mm=seal_p_wd,
        secondary_width_mm=seal_s_wd,
    )

    logger.info("\nNow describe the IGU batch geometry.\n")
    total_igus_str = input("Total number of IGUs in this batch: ").strip()
    width_str = input("Width of each IGU in mm (unit_width_mm): ").strip()
    height_str = input("Height of each IGU in mm (unit_height_mm): ").strip()

    try:
        total_igus = int(total_igus_str)
        unit_width_mm = float(width_str)
        unit_height_mm = float(height_str)
    except ValueError:
        logger.info("Invalid numeric input for IGU count or dimensions.")
        raise SystemExit(1)

    glazing_type_str = prompt_choice(
        "Glazing type", ["double", "triple", "single"], default="double"
    )
    glass_outer_str = prompt_choice(
        "Outer glass type", ["annealed", "tempered", "laminated"], default="annealed"
    )
    glass_inner_str = prompt_choice(
        "Inner glass type", ["annealed", "tempered", "laminated"], default="annealed"
    )
    coating_str = prompt_choice(
        "Coating type",
        ["none", "hard_lowE", "soft_lowE", "solar_control"],
        default="none",
    )
    sealant_str = prompt_choice(
        "Secondary sealant type",
        ["polysulfide", "polyurethane", "silicone", "combination", "combi"],
        default="polysulfide",
    )
    spacer_str = prompt_choice(
        "Spacer material",
        ["aluminium", "steel", "warm_edge_composite"],
        default="aluminium",
    )

    if glazing_type_str == "single":
        pane_th_str = input("Pane thickness (mm): ").strip()
        try:
            pane_thickness_single_mm = float(pane_th_str)
        except ValueError:
            logger.info("Invalid numeric input for pane thickness.")
            raise SystemExit(1)

        pane_thickness_outer_mm = pane_thickness_single_mm
        pane_thickness_inner_mm = 0.0
        cavity_thickness_1_mm = 0.0
        thickness_centre_mm: Optional[float] = None
        cavity_thickness_2_mm: Optional[float] = None
        IGU_depth_mm_val = pane_thickness_single_mm

    elif glazing_type_str == "double":
        outer_th_str = input("Outer pane thickness (mm): ").strip()
        inner_th_str = input("Inner pane thickness (mm): ").strip()
        cavity1_str = input("Cavity thickness (mm): ").strip()
        try:
            pane_thickness_outer_mm = float(outer_th_str)
            pane_thickness_inner_mm = float(inner_th_str)
            cavity_thickness_1_mm = float(cavity1_str)
        except ValueError:
            logger.info("Invalid numeric input for pane or cavity thickness.")
            raise SystemExit(1)
        thickness_centre_mm = None
        cavity_thickness_2_mm = None
        IGU_depth_mm_val = (
            pane_thickness_outer_mm + cavity_thickness_1_mm + pane_thickness_inner_mm
        )

    else:  # glazing_type_str == "triple"
        outer_th_str = input("Outer pane thickness (mm): ").strip()
        middle_th_str = input("Centre pane thickness (mm): ").strip()
        inner_th_str = input("Inner pane thickness (mm): ").strip()
        cavity1_str = input("First cavity thickness (mm): ").strip()
        cavity2_str = input("Second cavity thickness (mm): ").strip()
        try:
            pane_thickness_outer_mm = float(outer_th_str)
            thickness_centre_mm = float(middle_th_str)
            pane_thickness_inner_mm = float(inner_th_str)
            cavity_thickness_1_mm = float(cavity1_str)
            cavity_thickness_2_mm = float(cavity2_str)
        except ValueError:
            logger.info("Invalid numeric input for pane or cavity thickness.")
            raise SystemExit(1)
        IGU_depth_mm_val = (
            pane_thickness_outer_mm
            + cavity_thickness_1_mm
            + thickness_centre_mm
            + cavity_thickness_2_mm
            + pane_thickness_inner_mm
        )
    
    # Construct a temporary condition object to satisfy IGUGroup init (will be updated later)
    # Using defaults/placeholders as condition is asked in a later step.
    temp_condition = IGUCondition(
        visible_edge_seal_condition="not assessed",
        visible_fogging=False,
        cracks_chips=False,
        age_years=20.0,
        reuse_allowed=True
    )

    group = IGUGroup(
        quantity=total_igus,
        unit_width_mm=unit_width_mm,
        unit_height_mm=unit_height_mm,
        glazing_type=glazing_type_str,  # type: ignore[arg-type]
        glass_type_outer=glass_outer_str,  # type: ignore[arg-type]
        glass_type_inner=glass_inner_str,  # type: ignore[arg-type]
        coating_type=coating_str,  # type: ignore[arg-type]
        sealant_type_secondary=sealant_str,  # type: ignore[arg-type]
        spacer_material=spacer_str,  # type: ignore[arg-type]
        interlayer_type=None,
        condition=temp_condition,
        thickness_outer_mm=pane_thickness_outer_mm,
        thickness_inner_mm=pane_thickness_inner_mm,
        cavity_thickness_mm=cavity_thickness_1_mm,
        IGU_depth_mm=IGU_depth_mm_val,
        mass_per_m2_override=None,
        thickness_centre_mm=thickness_centre_mm,
        cavity_thickness_2_mm=cavity_thickness_2_mm,
        sealant_type_primary=None,
    )
    
    logger.info("\n--- IGU System Defined ---")
    logger.info(f"  Quantity: {group.quantity}, Size: {group.unit_width_mm}x{group.unit_height_mm} mm")
    logger.info(f"  Type: {group.glazing_type}, Depth: {group.IGU_depth_mm} mm")
    logger.info(f"  Build-up: {group.thickness_outer_mm} / {group.cavity_thickness_mm} / {group.thickness_inner_mm} (plus centre if triple)")
    
    return group, seal_geometry


def print_igu_geometry_overview(group: IGUGroup, seal_geometry: SealGeometry, processes: ProcessSettings):
    """
    Step 5: Geometry information and build-up overview.
    Calculates and prints geometric properties, masses, and sealant volumes.
    """
    logger.info("\n--- Step 5: Geometry & Materials Overview ---")
    
    # 1. Compute stats
    # Note: Using a list with one group for aggregation
    stats = aggregate_igu_groups([group], processes)
    masses = compute_igu_mass_totals([group], stats)
    seal_vols = compute_sealant_volumes(group, seal_geometry)
    
    logger.info(f"IGU Geometric Properties:")
    logger.info(f"  Dimensions: {group.unit_width_mm} mm x {group.unit_height_mm} mm")
    logger.info(f"  Depth:      {group.IGU_depth_mm} mm")
    logger.info(f"  Area (1):   {stats['average_area_per_igu']:.3f} m²")
    logger.info(f"  Area (all): {stats['total_IGU_surface_area_m2']:.3f} m² (Total Batch)")
    
    logger.info(f"\nBuild-up & Materials:")
    logger.info(f"  Glazing:    {group.glazing_type}")
    logger.info(f"  Glass:      {group.glass_type_outer} (outer), {group.glass_type_inner} (inner)")
    if group.thickness_centre_mm:
         logger.info(f"              {group.thickness_centre_mm} mm (centre)")
    logger.info(f"  Cavity:     {group.cavity_thickness_mm} mm")
    if group.cavity_thickness_2_mm:
        logger.info(f"              {group.cavity_thickness_2_mm} mm (2nd cavity)")
    logger.info(f"  Spacer:     {group.spacer_material}")
    logger.info(f"  Sealants:   Primary={seal_geometry.primary_thickness_mm}x{seal_geometry.primary_width_mm}mm")
    logger.info(f"              Secondary Type={group.sealant_type_secondary}, Width={seal_geometry.secondary_width_mm}mm")
    logger.info(f"              Sec. Thickness={seal_vols['secondary_thickness_mm']} mm (derived)")
    
    logger.info(f"\nMass Information:")
    logger.info(f"  Per m²:     {default_mass_per_m2(group.glazing_type)} kg/m² (approx)")
    logger.info(f"  Per IGU:    {masses['avg_mass_per_igu_kg']:.2f} kg")
    logger.info(f"  Total Batch:{masses['total_mass_t']:.3f} tonnes")
    
    logger.info(f"\nSealant Volumes (Total Batch):")
    logger.info(f"  Primary:    {seal_vols['primary_volume_total_m3']:.4f} m³")
    logger.info(f"  Secondary:  {seal_vols['secondary_volume_total_m3']:.4f} m³")


def ask_igu_condition_and_eligibility() -> IGUCondition:
    """
    Step 6: Conditions and eligibility questions.
    """
    logger.info("\n--- Step 6: Conditions & Eligibility ---")
    
    edge_cond_str = prompt_choice(
        "Visible edge seal condition", ["acceptable", "unacceptable", "not assessed"], default="acceptable"
    )
    fogging = prompt_yes_no("Visible fogging?", default=False)
    cracks = prompt_yes_no("Cracks or chips present?", default=False)
    reuse_allowed = prompt_yes_no("Reuse allowed by owner/regulations?", default=True)

    age_str = input("Approximate age of IGUs in years (default=20): ").strip()
    try:
        age_years = float(age_str) if age_str else 20.0
    except ValueError:
        age_years = 20.0
        
    return IGUCondition(
        visible_edge_seal_condition=edge_cond_str,  # type: ignore[arg-type]
        visible_fogging=fogging,
        cracks_chips=cracks,
        age_years=age_years,
        reuse_allowed=reuse_allowed,
    )


def print_scenario_overview(result: ScenarioResult):
    """
    Common reporting for all scenarios.
    """
    logger.info(f"\n========================================================")
    logger.info(f"   SCENARIO RESULT: {result.scenario_name.upper()}")
    logger.info(f"========================================================")
    
    logger.info(f"\nYield Summary:")
    logger.info(f"  Initial Acceptable IGUs: {result.initial_igus:.0f}")
    logger.info(f"  Initial Area:            {result.initial_area_m2:.3f} m²")
    logger.info(f"  Final Output IGUs/Units: {result.final_igus:.0f}")
    logger.info(f"  Final Output Area:       {result.final_area_m2:.3f} m²")
    logger.info(f"  Yield (Area basis):      {result.yield_percent:.1f}%")
    logger.info(f"  Initial Mass:            {result.initial_mass_kg/1000.0:.3f} t")
    logger.info(f"  Final Mass:              {result.final_mass_kg/1000.0:.3f} t")
    
    logger.info(f"\nCarbon Emissions (kg CO2e):")
    for stage, val in result.by_stage.items():
        logger.info(f"  {stage:<30} : {val:.3f}")
    
    logger.info(f"--------------------------------------------------------")
    logger.info(f"  TOTAL EMISSIONS              : {result.total_emissions_kgco2:.3f} kg CO2e")
    
    if result.final_area_m2 > 0:
         logger.info(f"  Intensity (per output m²)    : {result.total_emissions_kgco2 / result.final_area_m2:.3f} kgCO2e/m²")
    logger.info(f"========================================================\n")


def run_scenario_system_reuse(
    processes: ProcessSettings,
    transport: TransportModeConfig,
    group: IGUGroup,
    flow_start: FlowState,
    initial_stats: Dict[str, float],
    initial_masses: Dict[str, float]
) -> ScenarioResult:
    """
    Scenario (a): System Reuse
    """
    logger.info("\n--- Running Scenario: System Reuse ---")
    
    # a) On-Site Removal + Yield
    yield_removal_str = input("% yield loss at on-site removal (0-100) [default=0]: ").strip()
    yield_removal = float(yield_removal_str)/100.0 if yield_removal_str else 0.0
    
    flow_post_removal = apply_yield_loss(flow_start, yield_removal)
    
    # Calculate dismantling emissions based on original area (or removed area? keeping simple: original area * factor)
    # Actually, usually 'dismantling' applies to the whole batch, but then we lose some.
    # Let's align with the previous logic: dismantling applies to the *input* area.
    dismantling_kgco2 = initial_stats["total_IGU_surface_area_m2"] * processes.e_site_kgco2_per_m2
    
    # Transport A - using flow_post_removal mass
    # We can reuse the helper but we need to override the mass. 
    # The helper 'compute_dismantling_and_transport_to_processor_stage' re-aggregates groups.
    # To use the helper properly with yield losses, we'd need to modify the group input.
    # Instead, let's implement the transport math directly here using FlowState for clarity and control.
    
    # 1. Transport A
    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"] * transport.backhaul_factor
    ferry_A_km = (distances["ferry_A_km"] * transport.backhaul_factor) if processes.route_A_mode == "HGV lorry+ferry" else 0.0
    
    # Packaging (stillages) for transported amount
    stillage_mass_A_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages = ceil(flow_post_removal.igus / processes.igus_per_stillage)
         stillage_mass_A_kg = n_stillages * processes.stillage_mass_empty_kg
    
    mass_A_t = (flow_post_removal.mass_kg + stillage_mass_A_kg) / 1000.0
    transport_A_kgco2 = mass_A_t * (truck_A_km * transport.emissionfactor_truck + ferry_A_km * transport.emissionfactor_ferry)
    
    # Packaging emissions (embodied)
    pkg_per_igu = packaging_factor_per_igu(processes)
    packaging_kgco2 = flow_post_removal.igus * pkg_per_igu
    
    # b) Repair decision
    repair_needed = prompt_yes_no("Does the IGU system require repair?", default=False)
    repair_kgco2 = 0.0
    flow_post_repair = flow_post_removal
    
    if repair_needed:
        # Yield loss 20%
        logger.info("Applying 20% yield loss for repair process.")
        flow_post_repair = apply_yield_loss(flow_post_removal, 0.20)
        
        # Emissions?
        # Assuming 0 additional emissions for now unless user specifies
        pass
    
    # c) New recipient location
    reuse_location = prompt_location("new recipient building / reuse destination")
    transport.reuse = reuse_location
    
    # d) Transport B
    distances_B = compute_route_distances(transport)
    truck_B_km = distances_B["truck_B_km"] * transport.backhaul_factor
    ferry_B_km = (distances_B["ferry_B_km"] * transport.backhaul_factor) if processes.route_B_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_B_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages_B = ceil(flow_post_repair.igus / processes.igus_per_stillage)
         stillage_mass_B_kg = n_stillages_B * processes.stillage_mass_empty_kg
         
    mass_B_t = (flow_post_repair.mass_kg + stillage_mass_B_kg) / 1000.0
    transport_B_kgco2 = mass_B_t * (truck_B_km * transport.emissionfactor_truck + ferry_B_km * transport.emissionfactor_ferry)
    
    # Installation
    install_kgco2 = flow_post_repair.area_m2 * INSTALL_SYSTEM_KGCO2_PER_M2
    
    # e) Overview
    total = dismantling_kgco2 + packaging_kgco2 + transport_A_kgco2 + repair_kgco2 + transport_B_kgco2 + install_kgco2
    
    by_stage = {
        "Dismantling (E_site)": dismantling_kgco2,
        "Packaging (Stillages)": packaging_kgco2,
        "Transport A": transport_A_kgco2,
        "Repair": repair_kgco2,
        "Transport B": transport_B_kgco2,
        "Installation": install_kgco2
    }
    
    return ScenarioResult(
        scenario_name="System Reuse",
        total_emissions_kgco2=total,
        by_stage=by_stage,
        initial_igus=flow_start.igus,
        final_igus=flow_post_repair.igus,
        initial_area_m2=flow_start.area_m2,
        final_area_m2=flow_post_repair.area_m2,
        initial_mass_kg=flow_start.mass_kg,
        final_mass_kg=flow_post_repair.mass_kg,
        yield_percent=(flow_post_repair.area_m2 / flow_start.area_m2 * 100.0) if flow_start.area_m2 > 0 else 0.0
    )


def run_scenario_component_reuse(
    processes: ProcessSettings,
    transport: TransportModeConfig,
    group: IGUGroup,
    flow_start: FlowState,
    initial_stats: Dict[str, float]
) -> ScenarioResult:
    """
    Scenario (b): Component Reuse
    """
    logger.info("\n--- Running Scenario: Component Reuse ---")
    
    # a) On-Site Removal
    yield_removal_str = input("% yield loss at on-site removal (0-100) [default=0]: ").strip()
    yield_removal = float(yield_removal_str)/100.0 if yield_removal_str else 0.0
    flow_post_removal = apply_yield_loss(flow_start, yield_removal)
    dismantling_kgco2 = initial_stats["total_IGU_surface_area_m2"] * processes.e_site_kgco2_per_m2
    
    # b) Transport A
    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"] * transport.backhaul_factor
    ferry_A_km = (distances["ferry_A_km"] * transport.backhaul_factor) if processes.route_A_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_A_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages = ceil(flow_post_removal.igus / processes.igus_per_stillage)
         stillage_mass_A_kg = n_stillages * processes.stillage_mass_empty_kg
    mass_A_t = (flow_post_removal.mass_kg + stillage_mass_A_kg) / 1000.0
    transport_A_kgco2 = mass_A_t * (truck_A_km * transport.emissionfactor_truck + ferry_A_km * transport.emissionfactor_ferry)
    
    # Packaging
    packaging_kgco2 = flow_post_removal.igus * packaging_factor_per_igu(processes)

    # c) System Disassembly (20% loss)
    logger.info("Applying 20% yield loss for disassembly.")
    DISASSEMBLY_YIELD = 0.20
    flow_post_disassembly = apply_yield_loss(flow_post_removal, DISASSEMBLY_YIELD)
    
    # Disassembly Emissions
    # Using DISASSEMBLY_KGCO2_PER_M2 on the processed area (post-removal, pre-disassembly loss? or post? usually input to process)
    disassembly_kgco2 = flow_post_removal.area_m2 * DISASSEMBLY_KGCO2_PER_M2
    
    # d) Recondition
    recondition = prompt_yes_no("Is recondition of components required?", default=True)
    recond_kgco2 = 0.0
    if recondition:
        recond_factor_str = input("Recondition emissions (kgCO2e/m²) [default=0]: ").strip()
        recond_factor = float(recond_factor_str) if recond_factor_str else 0.0
        recond_kgco2 = flow_post_disassembly.area_m2 * recond_factor
    
    # e) Assembly IGU
    assembly_factor_str = input("Assembly emissions (kgCO2e/m²) [default=0]: ").strip()
    assembly_factor = float(assembly_factor_str) if assembly_factor_str else 0.0
    assembly_kgco2 = flow_post_disassembly.area_m2 * assembly_factor
    
    # f) Next location
    next_location = prompt_location("final installation location for reused IGUs")
    transport.reuse = next_location
    
    # g) Transport B
    distances_B = compute_route_distances(transport)
    truck_B_km = distances_B["truck_B_km"] * transport.backhaul_factor
    ferry_B_km = (distances_B["ferry_B_km"] * transport.backhaul_factor) if processes.route_B_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_B_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages_B = ceil(flow_post_disassembly.igus / processes.igus_per_stillage)
         stillage_mass_B_kg = n_stillages_B * processes.stillage_mass_empty_kg
         
    mass_B_t = (flow_post_disassembly.mass_kg + stillage_mass_B_kg) / 1000.0
    transport_B_kgco2 = mass_B_t * (truck_B_km * transport.emissionfactor_truck + ferry_B_km * transport.emissionfactor_ferry)
    
    total = dismantling_kgco2 + packaging_kgco2 + transport_A_kgco2 + disassembly_kgco2 + recond_kgco2 + assembly_kgco2 + transport_B_kgco2
    
    by_stage = {
        "Dismantling (E_site)": dismantling_kgco2,
        "Packaging": packaging_kgco2,
        "Transport A": transport_A_kgco2,
        "Disassembly": disassembly_kgco2,
        "Recondition": recond_kgco2,
        "Assembly": assembly_kgco2,
        "Transport B": transport_B_kgco2
    }
    
    return ScenarioResult(
        scenario_name="Component Reuse",
        total_emissions_kgco2=total,
        by_stage=by_stage,
        initial_igus=flow_start.igus,
        final_igus=flow_post_disassembly.igus,
        initial_area_m2=flow_start.area_m2,
        final_area_m2=flow_post_disassembly.area_m2,
        initial_mass_kg=flow_start.mass_kg,
        final_mass_kg=flow_post_disassembly.mass_kg,
        yield_percent=(flow_post_disassembly.area_m2 / flow_start.area_m2 * 100.0) if flow_start.area_m2 > 0 else 0.0
    )


def run_scenario_component_repurpose(
    processes: ProcessSettings,
    transport: TransportModeConfig,
    group: IGUGroup,
    flow_start: FlowState,
    initial_stats: Dict[str, float]
) -> ScenarioResult:
    """
    Scenario (c): Component Repurpose
    """
    logger.info("\n--- Running Scenario: Component Repurpose ---")
    
    # a) On-Site Removal
    yield_removal_str = input("% yield loss at on-site removal (0-100) [default=0]: ").strip()
    yield_removal = float(yield_removal_str)/100.0 if yield_removal_str else 0.0
    flow_post_removal = apply_yield_loss(flow_start, yield_removal)
    dismantling_kgco2 = initial_stats["total_IGU_surface_area_m2"] * processes.e_site_kgco2_per_m2
    
    # Transport A
    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"] * transport.backhaul_factor
    ferry_A_km = (distances["ferry_A_km"] * transport.backhaul_factor) if processes.route_A_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_A_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages = ceil(flow_post_removal.igus / processes.igus_per_stillage)
         stillage_mass_A_kg = n_stillages * processes.stillage_mass_empty_kg
    mass_A_t = (flow_post_removal.mass_kg + stillage_mass_A_kg) / 1000.0
    transport_A_kgco2 = mass_A_t * (truck_A_km * transport.emissionfactor_truck + ferry_A_km * transport.emissionfactor_ferry)
    packaging_kgco2 = flow_post_removal.igus * packaging_factor_per_igu(processes)

    # c) Disassembly (10% loss)
    logger.info("Applying 10% yield loss for disassembly (repurpose).")
    DISASSEMBLY_YIELD = 0.10
    flow_post_disassembly = apply_yield_loss(flow_post_removal, DISASSEMBLY_YIELD)
    disassembly_kgco2 = flow_post_removal.area_m2 * DISASSEMBLY_KGCO2_PER_M2
    
    # d) Recondition included in repurpose
    
    # e) Repurpose Intensity
    logger.info("Select repurposing intensity:")
    logger.info("  light/medium/heavy")
    rep_preset = prompt_choice("Intensity", ["light", "medium", "heavy"], default="medium")
    
    rep_factor = REPURPOSE_MEDIUM_KGCO2_PER_M2
    if rep_preset == "light": rep_factor = REPURPOSE_LIGHT_KGCO2_PER_M2
    if rep_preset == "heavy": rep_factor = REPURPOSE_HEAVY_KGCO2_PER_M2
    
    repurpose_kgco2 = flow_post_disassembly.area_m2 * rep_factor
    
    # f) Next location
    repurpose_dst = prompt_location("installation location for repurposed product")
    transport.reuse = repurpose_dst
    
    # g) Transport B
    distances_B = compute_route_distances(transport)
    truck_B_km = distances_B["truck_B_km"] * transport.backhaul_factor
    ferry_B_km = (distances_B["ferry_B_km"] * transport.backhaul_factor) if processes.route_B_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_B_kg = 0.0
    if processes.igus_per_stillage > 0:
         n_stillages_B = ceil(flow_post_disassembly.igus / processes.igus_per_stillage)
         stillage_mass_B_kg = n_stillages_B * processes.stillage_mass_empty_kg
    mass_B_t = (flow_post_disassembly.mass_kg + stillage_mass_B_kg) / 1000.0
    transport_B_kgco2 = mass_B_t * (truck_B_km * transport.emissionfactor_truck + ferry_B_km * transport.emissionfactor_ferry)
    
    total = dismantling_kgco2 + packaging_kgco2 + transport_A_kgco2 + disassembly_kgco2 + repurpose_kgco2 + transport_B_kgco2
    
    by_stage = {
        "Dismantling (E_site)": dismantling_kgco2,
        "Packaging": packaging_kgco2,
        "Transport A": transport_A_kgco2,
        "Disassembly": disassembly_kgco2,
        "Repurposing": repurpose_kgco2,
        "Transport B": transport_B_kgco2
    }
    
    return ScenarioResult(
        scenario_name=f"Repurpose ({rep_preset})",
        total_emissions_kgco2=total,
        by_stage=by_stage,
        initial_igus=flow_start.igus,
        final_igus=flow_post_disassembly.igus,
        initial_area_m2=flow_start.area_m2,
        final_area_m2=flow_post_disassembly.area_m2,
        initial_mass_kg=flow_start.mass_kg,
        final_mass_kg=flow_post_disassembly.mass_kg,
        yield_percent=(flow_post_disassembly.area_m2 / flow_start.area_m2 * 100.0) if flow_start.area_m2 > 0 else 0.0
    )


def run_scenario_closed_loop_recycling(
    processes: ProcessSettings,
    transport: TransportModeConfig,
    group: IGUGroup,
    flow_start: FlowState
) -> ScenarioResult:
    """
    Scenario (d): Closed-loop Recycling
    """
    logger.info("\n--- Running Scenario: Closed-loop Recycling ---")
    
    # a) Intact decision
    send_intact = prompt_yes_no("Send IGUs intact to processor?", default=True)
    
    # b/c) On-site removal + Break IGU
    yield_removal = 0.0
    yield_break = 0.0
    
    # Standard removal yield
    yield_removal_str = input("% yield loss at on-site removal (0-100) [default=0]: ").strip()
    yield_removal = float(yield_removal_str)/100.0 if yield_removal_str else 0.0
    
    if not send_intact:
        yield_break_str = input("% yield loss at breaking (0-100) [default=0]: ").strip()
        yield_break = float(yield_break_str)/100.0 if yield_break_str else 0.0
    
    flow_step1 = apply_yield_loss(flow_start, yield_removal)
    flow_step2 = apply_yield_loss(flow_step1, yield_break)
    
    # Emissions
    dismantling_kgco2 = flow_start.area_m2 * processes.e_site_kgco2_per_m2
    breaking_kgco2 = 0.0
    if not send_intact:
        # Ask for breaking emissions
        br_factor_str = input("Breaking emissions (kgCO2e/m²) [default=0]: ").strip()
        br_factor = float(br_factor_str) if br_factor_str else 0.0
        breaking_kgco2 = flow_step1.area_m2 * br_factor
        
    # d) Transport A
    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"] * transport.backhaul_factor
    ferry_A_km = (distances["ferry_A_km"] * transport.backhaul_factor) if processes.route_A_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_A_kg = 0.0
    # Stillages only if intact? If cullet, maybe bins? Assuming bin mass ~ stillage mass for simpliciy or 0?
    # Keeping logic simple: if intact, stillages. If broken, maybe bulk?
    # Let's assume standard transport capacity/packaging for simplicity
    if send_intact and processes.igus_per_stillage > 0:
         n_stillages = ceil(flow_step2.igus / processes.igus_per_stillage)
         stillage_mass_A_kg = n_stillages * processes.stillage_mass_empty_kg
    
    mass_A_t = (flow_step2.mass_kg + stillage_mass_A_kg) / 1000.0
    transport_A_kgco2 = mass_A_t * (truck_A_km * transport.emissionfactor_truck + ferry_A_km * transport.emissionfactor_ferry)
    
    # e) Processor fractions
    CULLET_LANDFILL_SHARE = 0.10
    CULLET_GLASSWOOL_SHARE = 0.10
    CULLET_FLOAT_SHARE = 0.80
    
    flow_float = apply_yield_loss(flow_step2, 1.0 - CULLET_FLOAT_SHARE)
    
    # f) Dispatch to float plant
    float_plant = prompt_location("Second Use Processing Facility (float glass plant)")
    transport.reuse = float_plant
    
    distances_B = compute_route_distances(transport)
    truck_B_km = distances_B["truck_B_km"] * transport.backhaul_factor
    ferry_B_km = (distances_B["ferry_B_km"] * transport.backhaul_factor) if processes.route_B_mode == "HGV lorry+ferry" else 0.0
    
    mass_B_t = flow_float.mass_kg / 1000.0 # Bulk cullet, no stillages
    transport_B_kgco2 = mass_B_t * (truck_B_km * transport.emissionfactor_truck + ferry_B_km * transport.emissionfactor_ferry)
    
    total = dismantling_kgco2 + breaking_kgco2 + transport_A_kgco2 + transport_B_kgco2
    
    by_stage = {
        "Dismantling/Removal": dismantling_kgco2,
        "Breaking": breaking_kgco2,
        "Transport A": transport_A_kgco2,
        "Transport B (Float)": transport_B_kgco2
    }
    
    return ScenarioResult(
        scenario_name="Closed-Loop Recycling",
        total_emissions_kgco2=total,
        by_stage=by_stage,
        initial_igus=flow_start.igus,
        final_igus=flow_float.igus, # Pseudo-count
        initial_area_m2=flow_start.area_m2,
        final_area_m2=flow_float.area_m2,
        initial_mass_kg=flow_start.mass_kg,
        final_mass_kg=flow_float.mass_kg,
        yield_percent=CULLET_FLOAT_SHARE * 100.0
    )


def run_scenario_open_loop_recycling(
    processes: ProcessSettings,
    transport: TransportModeConfig,
    group: IGUGroup,
    flow_start: FlowState
) -> ScenarioResult:
    """
    Scenario (e): Open-loop Recycling
    """
    logger.info("\n--- Running Scenario: Open-loop Recycling ---")
    
    # a) Intact vs break
    send_intact = prompt_yes_no("Send IGUs intact to processor?", default=True)
    
    yield_removal = 0.0
    yield_break = 0.0
    yield_removal_str = input("% yield loss at on-site removal (0-100) [default=0]: ").strip()
    yield_removal = float(yield_removal_str)/100.0 if yield_removal_str else 0.0
    
    if not send_intact:
        yield_break_str = input("% yield loss at breaking (0-100) [default=0]: ").strip()
        yield_break = float(yield_break_str)/100.0 if yield_break_str else 0.0
    
    flow_step1 = apply_yield_loss(flow_start, yield_removal)
    flow_step2 = apply_yield_loss(flow_step1, yield_break)
    
    dismantling_kgco2 = flow_start.area_m2 * processes.e_site_kgco2_per_m2
    breaking_kgco2 = 0.0
    if not send_intact:
         br_factor_str = input("Breaking emissions (kgCO2e/m²) [default=0]: ").strip()
         br_factor = float(br_factor_str) if br_factor_str else 0.0
         breaking_kgco2 = flow_step1.area_m2 * br_factor

    # Transport A
    distances = compute_route_distances(transport)
    truck_A_km = distances["truck_A_km"] * transport.backhaul_factor
    ferry_A_km = (distances["ferry_A_km"] * transport.backhaul_factor) if processes.route_A_mode == "HGV lorry+ferry" else 0.0
    
    stillage_mass_A_kg = 0.0
    if send_intact and processes.igus_per_stillage > 0:
         n_stillages = ceil(flow_step2.igus / processes.igus_per_stillage)
         stillage_mass_A_kg = n_stillages * processes.stillage_mass_empty_kg

    mass_A_t = (flow_step2.mass_kg + stillage_mass_A_kg) / 1000.0
    transport_A_kgco2 = mass_A_t * (truck_A_km * transport.emissionfactor_truck + ferry_A_km * transport.emissionfactor_ferry)
    
    # Processor Fractions
    CULLET_CW_SHARE = 0.10
    CULLET_CONT_SHARE = 0.10
    CULLET_REST_SHARE = 0.80 # To landfill or other? Task says default to landfill/open
    
    # Task: "Recycle to Glasswool / Container"
    # c) Processor stage
    
    # d) Optional transport
    model_transport = prompt_yes_no("Model transport to glasswool/container plants?", default=False)
    open_loop_transport_kgco2 = 0.0
    
    if model_transport:
        gw_plant = prompt_location("Glasswool plant")
        cont_plant = prompt_location("Container glass plant")
        
        # Calculate transport B for these streams
        # Simplified: Use B-leg distance logic but to these locations
        # Glasswool
        tr_gw = TransportModeConfig(origin=transport.processor, processor=transport.processor, reuse=gw_plant)
        dist_gw = compute_route_distances(tr_gw)
        mass_gw_t = (flow_step2.mass_kg * CULLET_CW_SHARE) / 1000.0
        e_gw = mass_gw_t * (dist_gw["truck_B_km"] * transport.emissionfactor_truck) # Assume truck only
        
        # Container
        tr_cont = TransportModeConfig(origin=transport.processor, processor=transport.processor, reuse=cont_plant)
        dist_cont = compute_route_distances(tr_cont)
        mass_cont_t = (flow_step2.mass_kg * CULLET_CONT_SHARE) / 1000.0
        e_cont = mass_cont_t * (dist_cont["truck_B_km"] * transport.emissionfactor_truck)
        
        open_loop_transport_kgco2 = e_gw + e_cont

    total = dismantling_kgco2 + breaking_kgco2 + transport_A_kgco2 + open_loop_transport_kgco2
    
    by_stage = {
        "Dismantling": dismantling_kgco2,
        "Breaking": breaking_kgco2,
        "Transport A": transport_A_kgco2,
        "Open-Loop Transport": open_loop_transport_kgco2
    }
    
    final_useful_fraction = CULLET_CW_SHARE + CULLET_CONT_SHARE # 20%
    flow_final = apply_yield_loss(flow_step2, 1.0 - final_useful_fraction)
    
    return ScenarioResult(
        scenario_name="Open-Loop Recycling",
        total_emissions_kgco2=total,
        by_stage=by_stage,
        initial_igus=flow_start.igus,
        final_igus=flow_final.igus,
        initial_area_m2=flow_start.area_m2,
        final_area_m2=flow_final.area_m2,
        initial_mass_kg=flow_start.mass_kg,
        final_mass_kg=flow_final.mass_kg,
        yield_percent=final_useful_fraction * 100.0
    )


# ============================================================================
# GEOCODING AND INPUT HELPERS
# ============================================================================

def geocode_address(address: str) -> Optional[Location]:
    """
    Geocode a free-text address to a Location (lat/lon) using Nominatim/OSM.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": GEOCODER_USER_AGENT}
    try:
        logger.info(f"Geocoding '{address}' ...")
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        logger.info(f"Geocoder HTTP status: {resp.status_code}")
        resp.raise_for_status()
        data = resp.json()
        if not data:
            logger.info("No geocoding results returned.")
            return None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return Location(lat=lat, lon=lon)
    except Exception as e:
        logger.info(f"Geocoding error: {e}")
        return None


def try_parse_lat_lon(text: str) -> Optional[Location]:
    """
    Try to parse 'lat,lon' text into a Location.
    """
    parts = text.split(",")
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        return Location(lat=lat, lon=lon)
    except ValueError:
        return None


def prompt_location(label: str) -> Location:
    """
    Prompt user for either a free-text address or a 'lat,lon' pair and return a Location.
    """
    while True:
        s = input(f"Enter {label} address or 'lat,lon': ").strip()
        if not s:
            continue
        loc = try_parse_lat_lon(s)
        if loc is not None:
            logger.info(f"{label} set to {loc.lat:.6f}, {loc.lon:.6f} (manual lat,lon)")
            return loc
        loc = geocode_address(s)
        if loc is not None:
            logger.info(f"{label} geocoded to {loc.lat:.6f}, {loc.lon:.6f}")
            return loc
        logger.info("Could not geocode input. Try again with another address or 'lat,lon'.")


def prompt_choice(label: str, options: List[str], default: str) -> str:
    """
    Prompt user to pick one value from a list of options; returns the chosen option.
    """
    opts_str = "/".join(options)
    while True:
        s = input(f"{label} [{opts_str}] (default={default}): ").strip().lower()
        if not s:
            return default
        for opt in options:
            if s == opt.lower():
                return opt
        logger.info(f"Invalid choice. Please choose one of: {opts_str}")


def prompt_yes_no(label: str, default: bool) -> bool:
    """
    Prompt user for yes/no answer, returning True/False.
    """
    d = "y" if default else "n"
    while True:
        s = input(f"{label} [y/n] (default={d}): ").strip().lower()
        if not s:
            return default
        if s in ("y", "yes"):
            return True
        if s in ("n", "no"):
            return False
        logger.info("Please answer y or n.")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # 1. LOGGING SETUP
    setup_logging(console_level=logging.INFO)
    
    # 2. PROCESS START BANNER
    logger.info("IGU recovery environmental impact prototype – Start\n")
    
    processes = ProcessSettings()
    
    # 2. IGU SOURCE SELECTION
    source_mode = prompt_igu_source()
    
    # 3. IGU SYSTEM DEFINITION
    # (Since database is not implemented, we always fall through to manual)
    group, seal_geometry = define_igu_system_from_manual()
    
    # 4. LOCATION DEFINITION
    logger.info("\n--- Step 3: Locations & Transport Configuration ---")
    origin = prompt_location("project origin (Dismantling from Building / on-site removal)")
    processor = prompt_location("processor location (main processing site)")
    
    # Initial transport config (reuse destination is placeholder until scenario selection)
    transport = TransportModeConfig(origin=origin, processor=processor, reuse=processor)
    
    logger.info("\nLocations defined:")
    logger.info(f"  Origin   : {origin.lat:.6f}, {origin.lon:.6f}")
    logger.info(f"  Processor: {processor.lat:.6f}, {processor.lon:.6f}")
    
    # Transport Modes
    logger.info("\nSelect Transport Modes:")
    route_A_mode_str = prompt_choice(
        "Route A transport mode (origin → processor)",
        ["HGV lorry", "HGV lorry+ferry"],
        default=ROUTE_A_MODE,
    )
    route_B_mode_str = prompt_choice(
        "Route B transport mode (processor → second site)",
        ["HGV lorry", "HGV lorry+ferry"],
        default=ROUTE_B_MODE,
    )
    processes.route_A_mode = route_A_mode_str  # type: ignore[assignment]
    processes.route_B_mode = route_B_mode_str  # type: ignore[assignment]
    
    # Truck settings
    logger.info("\nSelect HGV lorry emission factor preset:")
    logger.info("  eu_legacy    = 0.06 kgCO2e/tkm  (older diesel HGV lorries)")
    logger.info("  eu_current   = 0.04 kgCO2e/tkm  (current EU average HGV lorry)")
    logger.info("  best_diesel  = 0.03 kgCO2e/tkm  (best-in-class diesel HGV lorry)")
    logger.info("  ze_truck     = 0.0075 kgCO2e/tkm (electric HGV lorry, grid mix)")
    
    truck_preset = prompt_choice(
        "HGV lorry emission preset",
        ["eu_legacy", "eu_current", "best_diesel", "ze_truck"],
        default="eu_current",
    )
    
    if truck_preset == "eu_legacy":
        transport.emissionfactor_truck = 0.06
    elif truck_preset == "eu_current":
        transport.emissionfactor_truck = 0.04
    elif truck_preset == "best_diesel":
        transport.emissionfactor_truck = 0.03
    elif truck_preset == "ze_truck":
        transport.emissionfactor_truck = 0.0075
    
    logger.info(f"  -> Using truck factor: {transport.emissionfactor_truck} kgCO2e/tkm")
    
    # 5. GEOMETRY REPORTING
    print_igu_geometry_overview(group, seal_geometry, processes)
    
    # 6. CONDITIONS & ELIGIBILITY QUESTIONS
    condition = ask_igu_condition_and_eligibility()
    group.condition = condition
    
    # Recalculate stats with actual condition
    stats_initial = aggregate_igu_groups([group], processes)
    masses_initial = compute_igu_mass_totals([group], stats_initial)
    
    logger.info(f"\nCondition & Eligibility Check:")
    logger.info(f"  Total IGUs:      {stats_initial['total_igus']:.0f}")
    logger.info(f"  Acceptable IGUs: {stats_initial['acceptable_igus']:.0f} ({(stats_initial['acceptable_igus']/stats_initial['total_igus']*100 if stats_initial['total_igus']>0 else 0):.1f}%)")
    
    # Optional: Configure other process settings like E_site before scenario
    logger.info("\nGlobal Process Settings:")
    e_site_str = input(
        f"Dismantling from Building factor E_site (kg CO2e/m² glass) [default={E_SITE_KGCO2_PER_M2}]: "
    ).strip()
    if e_site_str:
        try:
             processes.e_site_kgco2_per_m2 = float(e_site_str)
        except ValueError:
             logger.info("Invalid value, keeping default.")
    
    processes.include_stillage_embodied = prompt_yes_no("Include stillage manufacturing emissions?", default=INCLUDE_STILLAGE_EMBODIED)
    
    # Breakage settings
    logger.info("\nSelect global breakage rate (during Dismantling/Transport):")
    logger.info("  very_low (0.5%), low (1%), medium (3%), high (5%)")
    breakage_preset = prompt_choice("Breakage preset", ["very_low", "low", "medium", "high"], default="very_low")
    if breakage_preset == "very_low": processes.breakage_rate_global = 0.005
    elif breakage_preset == "low": processes.breakage_rate_global = 0.01
    elif breakage_preset == "medium": processes.breakage_rate_global = 0.03
    elif breakage_preset == "high": processes.breakage_rate_global = 0.05
    
    # 7. RECOVERY SCENARIO SELECTION
    logger.info("\n--- Step 7: Recovery Scenario Selection ---")
    scenario = prompt_choice(
        "Select recovery scenario", 
        ["system_reuse", "component_reuse", "component_repurpose", "closed_loop_recycling", "open_loop_recycling"], 
        default="system_reuse"
    )
    
    # 8. SCENARIO EXECUTION
    # Initialize FlowState
    # Base flow is from acceptable IGUs
    # Note: Scenario runners apply their own yields, but we start from "acceptable" batch stats usually?
    # Or do we start from TOTAL?
    # Task says: "Initialise from stats_initial...". And "On-site removal From Building... Apply yield_removal to the initial acceptable FlowState"
    # Wait, 'acceptable' usually means "visually OK".
    # If the user selects 'closed_loop_recycling', maybe even 'unacceptable' ones can be recycled?
    # Task 7: "Closed/open loop recycling can proceed with any condition".
    # Rules:
    #   Reuse/Repurpose: Require acceptable IGUs.
    #   Recycling: Can use total IGUs?
    
    # Let's decide flow start based on scenario
    if scenario in ["system_reuse", "component_reuse", "component_repurpose"]:
        start_igus = stats_initial['acceptable_igus']
        start_area = stats_initial['acceptable_area_m2']
        start_mass = masses_initial['acceptable_mass_kg']
        if start_igus <= 0:
            logger.info("\nWARNING: No acceptable IGUs available for this scenario!")
            if not prompt_yes_no("Proceed anyway (assuming 0 output)?", default=False):
                raise SystemExit(0)
    else:
        # Recycling can assume all IGUs (maybe excluding fully shattered/missing ones, but let's take total)
        # Assuming 'total' is available on site.
        start_igus = stats_initial['total_igus']
        start_area = stats_initial['total_IGU_surface_area_m2']
        start_mass = masses_initial['total_mass_kg']
    
    flow_start = FlowState(igus=start_igus, area_m2=start_area, mass_kg=start_mass)
    
    result = None
    if scenario == "system_reuse":
        result = run_scenario_system_reuse(processes, transport, group, flow_start, stats_initial, masses_initial)
    elif scenario == "component_reuse":
        result = run_scenario_component_reuse(processes, transport, group, flow_start, stats_initial)
    elif scenario == "component_repurpose":
        result = run_scenario_component_repurpose(processes, transport, group, flow_start, stats_initial)
    elif scenario == "closed_loop_recycling":
        result = run_scenario_closed_loop_recycling(processes, transport, group, flow_start)
    elif scenario == "open_loop_recycling":
        result = run_scenario_open_loop_recycling(processes, transport, group, flow_start)
    
    # 9. OVERVIEW / SUMMARY
    if result:
        print_scenario_overview(result)
    
    logger.info("\nProcess Complete.")
