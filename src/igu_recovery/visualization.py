import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime
from typing import List, Dict, Optional
from .models import ScenarioResult

# ============================================================================
# VISUALIZER CLASS
# ============================================================================

class Visualizer:
    def __init__(self, mode: str = "single_run"):
        """
        Initialize Visualizer.
        mode: 'single_run' (for interactive) or 'batch_run' (for automated analysis)
        """
        self.mode = mode
        self.output_root = r"d:\VITRIFY\reports\plots"
        self._setup_style()
        self.session_dir = self._create_session_dir()

    def _setup_style(self):
        """Configure matplotlib for professional, publication-quality plots."""
        try:
            # Try to use a clean, modern style
            plt.style.use('seaborn-v0_8-whitegrid')
        except:
            # Fallback
            plt.style.use('ggplot')
        
        # Consistent font sizes
        plt.rcParams.update({
            'font.size': 11,
            'axes.titlesize': 14,
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'legend.fontsize': 10,
            'figure.titlesize': 16,
            'axes.spines.top': False,
            'axes.spines.right': False
        })
        
        # Color Palette (Professional/Muted)
        self.colors = {
            'primary': '#2C3E50',     # Dark Blue
            'secondary': '#E74C3C',   # Muted Red
            'accent': '#3498DB',      # Bright Blue
            'success': '#27AE60',     # Green
            'warning': '#F1C40F',     # Yellow/Orange
            'neutral': '#95A5A6'      # Grey
        }

    def _create_session_dir(self) -> str:
        """Create the specific directory for this session's plots."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        subdir = "batch_run" if self.mode == "batch_run" else "single_run"
        
        # For single run, we might append product name later, but for now use timestamp container
        path = os.path.join(self.output_root, subdir, timestamp)
        os.makedirs(path, exist_ok=True)
        return path

    def get_save_path(self, filename: str) -> str:
        return os.path.join(self.session_dir, filename)

    # ============================================================================
    # SINGLE RUN PLOTS
    # ============================================================================

    def plot_single_scenario_breakdown(self, result: ScenarioResult, product_name: str = ""):
        """Bar chart of emission stages for one scenario."""
        if not result.by_stage:
            return

        stages = list(result.by_stage.keys())
        values = list(result.by_stage.values())
        
        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        
        bars = ax.bar(stages, values, color=self.colors['accent'], alpha=0.9, width=0.6)
        
        # Labels
        ax.set_ylabel("Emissions (kgCO2e)", fontweight='bold')
        ax.set_title(f"Detailed Breakdown: {result.scenario_name}\n{product_name}", pad=20)
        plt.xticks(rotation=45, ha='right')
        
        # Value tags
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}',
                        ha='center', va='bottom', fontsize=9, color='#333333')

        plt.tight_layout()
        
        # Save
        safe_name = result.scenario_name.replace(" ", "_").lower()
        filepath = self.get_save_path(f"breakdown_{safe_name}.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"   [Plot] Saved breakdown to: {filepath}")

    def plot_scenario_comparison(self, results: List[ScenarioResult], product_name: str = ""):
        """Compare all scenarios (Emissions vs Yield)."""
        if not results: return

        names = [r.scenario_name.replace(" ", "\n") for r in results] # Break lines for x-labels
        emissions = [r.total_emissions_kgco2 for r in results]
        yields = [r.yield_percent for r in results]
        
        fig, ax1 = plt.subplots(figsize=(12, 7), dpi=150)
        
        # 1. Emissions (Bars)
        bars = ax1.bar(names, emissions, color=self.colors['secondary'], alpha=0.7, label='Total Emissions')
        ax1.set_ylabel('Total Emissions (kgCO2e)', color=self.colors['secondary'], fontweight='bold')
        ax1.tick_params(axis='y', labelcolor=self.colors['secondary'])
        ax1.grid(True, axis='y', alpha=0.3)
        
        # Labels on bars
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                     f'{height:.0f}',
                     ha='center', va='bottom', fontweight='bold', fontsize=9)
        
        # 2. Yield (Line)
        ax2 = ax1.twinx()
        ax2.plot(names, yields, color=self.colors['success'], marker='o', linewidth=3, markersize=8, label='Final Yield')
        ax2.set_ylabel('Yield (%)', color=self.colors['success'], fontweight='bold')
        ax2.tick_params(axis='y', labelcolor=self.colors['success'])
        ax2.set_ylim(0, 110)
        
        # Labels on line
        for i, val in enumerate(yields):
            ax2.text(i, val + 2, f'{val:.0f}%', ha='center', color=self.colors['success'], fontweight='bold', fontsize=9)

        # Title
        plt.title(f"Scenario Comparison: Environmental Impact vs Circularity\n{product_name}", pad=20)
        
        plt.tight_layout()
        filepath = self.get_save_path("scenario_comparison.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"   [Plot] Saved comparison to: {filepath}")


    # ============================================================================
    # BATCH ANALYSIS PLOTS
    # ============================================================================

    def plot_batch_summary(self, df: pd.DataFrame):
        """
        Generate summary plots for the entire batch.
        df column expectations: 'Scenario', 'Total Emissions (kgCO2e)', 'Final Yield (%)', 'Product Name'
        """
        if df.empty: return
        
        # 1. Boxplot of Emissions by Scenario (Distribution)
        self._plot_batch_distribution(df)
        
        # 2. Scatter: Yield vs Emissions (Efficiency Frontier)
        self._plot_batch_scatter(df)
        
        # 3. Intensity Comparison (kgCO2e/m2 output) - Only for scenarios with output
        self._plot_batch_intensity(df)

    def _plot_batch_distribution(self, df: pd.DataFrame):
        fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
        
        # Group by scenario to order them?
        # Use pandas boxplot wrapper or matplotlib directly
        # Let's use pandas for simplicity if avail, else manual
        
        # Pivot for boxplot: Columns = Scenarios, Rows = Products
        try:
            pivot = df.pivot_table(index='Product Name', columns='Scenario', values='Total Emissions (kgCO2e)')
            
            # Sort columns by median emission
            sorted_cols = pivot.median().sort_values().index
            pivot = pivot[sorted_cols]
            
            pivot.boxplot(ax=ax, rot=45, color=dict(boxes=self.colors['primary'], whiskers=self.colors['primary'], medians=self.colors['secondary']))
            
            ax.set_ylabel("Total Emissions (kgCO2e)")
            ax.set_title("Distribution of Emissions across Batch by Scenario")
            plt.tight_layout()
            
            filepath = self.get_save_path("batch_emissions_distribution.png")
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close(fig)
            print(f"   [Plot] Saved batch distribution to: {filepath}")
            
        except Exception as e:
            print(f"Could not generate distribution plot: {e}")

    def _plot_batch_scatter(self, df: pd.DataFrame):
        """Scatter plot of Yield (X) vs Emissions (Y), colored by Scenario."""
        fig, ax = plt.subplots(figsize=(10, 7), dpi=150)
        
        scenarios = df['Scenario'].unique()
        # Simple color map
        cmap = plt.get_cmap('tab10')
        
        for i, sc in enumerate(scenarios):
            subset = df[df['Scenario'] == sc]
            ax.scatter(subset['Final Yield (%)'], subset['Total Emissions (kgCO2e)'], 
                       label=sc, alpha=0.7, edgecolors='w', s=100)
            
        ax.set_xlabel("Material Yield (%)")
        ax.set_ylabel("Total Emissions (kgCO2e)")
        ax.set_title("Eco-Efficiency Frontier: Yield vs Carbon")
        ax.grid(True, linestyle='--', alpha=0.4)
        ax.legend(title="Scenario", bbox_to_anchor=(1.05, 1), loc='upper left')
        
        plt.tight_layout()
        filepath = self.get_save_path("batch_yield_vs_carbon.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"   [Plot] Saved batch scatter to: {filepath}")

    def _plot_batch_intensity(self, df: pd.DataFrame):
        """Bar chart of average Intensity (kgCO2e/m2 output) where yield > 0."""
        # Filter where yield > 0
        subset = df[df['Final Yield (%)'] > 1.0] # > 1%
        
        if subset.empty: return

        # Calc mean intensity per scenario
        grouped = subset.groupby('Scenario')['Intensity (kgCO2e/m2 output)'].mean().sort_values()
        
        if grouped.empty: return

        fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
        
        bars = ax.barh(grouped.index, grouped.values, color=self.colors['success'], alpha=0.8)
        
        ax.set_xlabel("Avg Intensity (kgCO2e per m² recovered)")
        ax.set_title("Carbon Intensity of Recovered Glass/Units")
        
        # Labels
        for bar in bars:
            width = bar.get_width()
            ax.text(width, bar.get_y() + bar.get_height()/2, 
                    f' {width:.2f}', 
                    va='center', color='black', fontsize=9)
            
        plt.tight_layout()
        filepath = self.get_save_path("batch_avg_intensity.png")
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f"   [Plot] Saved intensity plot to: {filepath}")
