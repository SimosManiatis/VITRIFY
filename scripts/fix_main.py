import os

file_path = r"d:\VITRIFY\src\igu_recovery\main.py"
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Keep lines 1 to 572 (indexes 0 to 571)
# Line 572 is empty newline after "print_scenario_overview(result)"
clean_lines = lines[:572]

new_code = r"""    # 8. VISUALIZATION & COMPARISON
    print("\n" + "="*60)
    print("Post-Analysis Visualization")
    print("="*60)
    print("Would you like to:")
    print("  a) Visualize emissions for this scenario only")
    print("  b) Compare this scenario with ALL other scenarios (will calculate others now)")
    print("  c) Exit")
    
    viz_choice = prompt_choice("Select option", ["a", "b", "c"], default="c")
    
    if viz_choice == "a":
        # Single Scenario Breakdown
        if 'result' in locals() and result:
            vis = Visualizer(mode="single_run")
            p_name = group.glazing_type
            vis.plot_single_scenario_breakdown(result, product_name=f"Manual Config: {p_name}")
            # print(f"Plot saved to: {vis.session_dir}")
        else:
            print("No result to visualize.")
            
    elif viz_choice == "b":
        print("\nCalculations running for comparisons...")
        
        comparison_results = []
        
        # Define the list of scenarios to run (name, func)
        all_scenarios = [
            ("System Reuse", run_scenario_system_reuse),
            ("Component Reuse", run_scenario_component_reuse),
            ("Component Repurpose", run_scenario_component_repurpose),
            ("Closed-loop Recycling", run_scenario_closed_loop_recycling),
            ("Open-loop Recycling", run_scenario_open_loop_recycling),
            ("Straight to Landfill", run_scenario_landfill)
        ]
        
        for sc_name, sc_func in all_scenarios:
            t_copy = TransportModeConfig(**transport.__dict__)
            
            # Setup Specific Destinations for non-interactive run
            if sc_name in ["System Reuse", "Component Reuse", "Component Repurpose"]:
                t_copy.reuse = reuse_dst
            elif sc_name in ["Closed-loop Recycling", "Open-loop Recycling"]:
                 t_copy.reuse = recycling_dst
            elif sc_name == "Straight to Landfill":
                t_copy.landfill = landfill_dst
            
            # Run
            try:
                # Dispatch based on signature
                res_cmp = None
                if sc_name == "System Reuse":
                    res_cmp = run_scenario_system_reuse(processes, t_copy, group, flow_start, stats, masses, interactive=False)
                elif sc_name == "Component Reuse":
                    res_cmp = run_scenario_component_reuse(processes, t_copy, group, seal_geometry, flow_start, stats, interactive=False)
                elif sc_name == "Component Repurpose":
                    res_cmp = run_scenario_component_repurpose(processes, t_copy, group, flow_start, stats, interactive=False)
                elif sc_name == "Closed-loop Recycling":
                    res_cmp = run_scenario_closed_loop_recycling(processes, t_copy, group, flow_start, interactive=False)
                elif sc_name == "Open-loop Recycling":
                    res_cmp = run_scenario_open_loop_recycling(processes, t_copy, group, flow_start, interactive=False)
                elif sc_name == "Straight to Landfill":
                    res_cmp = run_scenario_landfill(processes, t_copy, group, flow_start, interactive=False)
                
                if res_cmp:
                    comparison_results.append(res_cmp)
            except Exception as e:
                logger.error(f"Error calculating {sc_name} for comparison: {e}")
                
        # Print Text Table
        print("\n" + "-"*80)
        print(f"{'Scenario':<25} | {'Emissions (kgCO2e)':<20} | {'Yield %':<10}")
        print("-" * 60)
        for r in comparison_results:
             print(f"{r.scenario_name:<25} | {r.total_emissions_kgco2:<20.2f} | {r.yield_percent:<10.1f}")
        print("-" * 80)
        
        # Plot
        vis = Visualizer(mode="single_run")
        p_name = group.glazing_type
        vis.plot_scenario_comparison(comparison_results, product_name=f"Manual Config: {p_name}")

if __name__ == "__main__":
    main()
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.writelines(clean_lines)
    f.write(new_code)

print("Successfully repaired main.py")
