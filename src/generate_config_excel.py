import pandas as pd
import xlsxwriter

# Output file path
OUTPUT_FILE = "d:\\VITRIFY\\src\\IGU_CO2_Config.xlsx"

def create_excel_template():
    # 1. Constants Sheet
    constants_data = {
        "Variable Name": [
            "E_SITE_KGCO2_PER_M2", "REMANUFACTURING_KGCO2_PER_M2", "DISASSEMBLY_KGCO2_PER_M2",
            "STILLAGE_MANUFACTURE_KGCO2", "STILLAGE_LIFETIME_CYCLES",
            "EMISSIONFACTOR_FERRY", "BACKHAUL_FACTOR",
            "TRUCK_CAPACITY_T", "FERRY_CAPACITY_T",
            "DISTANCE_FALLBACK_A_KM", "DISTANCE_FALLBACK_B_KM",
            "BREAKAGE_RATE_GLOBAL", "HUMIDITY_FAILURE_RATE", "SPLIT_YIELD", "REMANUFACTURING_YIELD",
            "IGUS_PER_STILLAGE", "STILLAGE_MASS_EMPTY_KG"
        ],
        "Value": [
            0.15, 7.5, 0.5,
            500.0, 100,
            0.045, 1.3,
            20.0, 1000.0,
            100.0, 100.0,
            0.05, 0.05, 0.95, 0.90,
            20, 300.0
        ],
        "Unit": [
            "kg CO2e/m²", "kg CO2e/m²", "kg CO2e/m²",
            "kg CO2e", "cycles",
            "kg CO2e/tkm", "-",
            "tonnes", "tonnes",
            "km", "km",
            "% (0-1)", "% (0-1)", "% (0-1)", "% (0-1)",
            "count", "kg"
        ],
        "Description": [
            "On-site dismantling emissions", "Remanufacturing emissions", "System disassembly emissions",
            "Stillage manufacturing emissions", "Stillage lifetime",
            "Ferry emission factor", "Return trip factor",
            "Truck capacity", "Ferry capacity",
            "Fallback distance (Origin->Proc)", "Fallback distance (Proc->Reuse)",
            "Global breakage rate", "Humidity failure rate", "Split yield", "Remanufacturing yield",
            "IGUs per stillage", "Empty stillage mass"
        ]
    }
    df_constants = pd.DataFrame(constants_data)

    # 2. TruckPresets Sheet
    truck_data = {
        "Preset Name": ["eu_legacy", "eu_current", "best_diesel", "ze_truck"],
        "Emission Factor": [0.06, 0.04, 0.03, 0.0075],
        "Description": ["Older diesel trucks", "Current EU average", "Best-in-class diesel", "Electric truck (grid mix)"]
    }
    df_trucks = pd.DataFrame(truck_data)

    # 3. GlazingDefaults Sheet
    glazing_data = {
        "Glazing Type": ["double", "triple"],
        "Mass per m² (kg)": [20.0, 30.0]
    }
    df_glazing = pd.DataFrame(glazing_data)

    # Create Excel Writer
    writer = pd.ExcelWriter(OUTPUT_FILE, engine='xlsxwriter')
    workbook = writer.book

    # Write Sheets
    df_constants.to_excel(writer, sheet_name='Constants', index=False)
    df_trucks.to_excel(writer, sheet_name='TruckPresets', index=False)
    df_glazing.to_excel(writer, sheet_name='GlazingDefaults', index=False)

    # Formatting
    worksheet_constants = writer.sheets['Constants']
    worksheet_trucks = writer.sheets['TruckPresets']
    worksheet_glazing = writer.sheets['GlazingDefaults']

    # Column Widths
    worksheet_constants.set_column(0, 0, 30) # Var Name
    worksheet_constants.set_column(1, 1, 15) # Value
    worksheet_constants.set_column(2, 2, 15) # Unit
    worksheet_constants.set_column(3, 3, 40) # Desc

    worksheet_trucks.set_column(0, 0, 15)
    worksheet_trucks.set_column(1, 1, 15)
    worksheet_trucks.set_column(2, 2, 30)

    worksheet_glazing.set_column(0, 0, 15)
    worksheet_glazing.set_column(1, 1, 20)

    writer.close()
    print(f"Excel parameters database created at: {OUTPUT_FILE}")

if __name__ == "__main__":
    create_excel_template()
