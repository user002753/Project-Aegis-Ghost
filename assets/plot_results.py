import os
import matplotlib.pyplot as plt
import numpy as np

# Set clean, modern design styling
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['DejaVu Sans', 'Arial', 'Helvetica', 'sans-serif']
plt.rcParams['axes.edgecolor'] = '#b0bec5'
plt.rcParams['axes.linewidth'] = 0.8

# Data
methods = ['Spatial LSB\nBaseline', 'Frequency\nDWT Only', 'Proposed\nSystem']
psnr_values = [38.4, 41.2, 44.2]
evasion_values = [0.0, 92.4, 100.0]

# Create Figure
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5), dpi=300)

# Colors matching the system palette (Teal and warm orange-gold)
color_teal = '#1abc9c'
color_teal_dark = '#16a085'
color_orange = '#f39c12'
color_orange_dark = '#d35400'

# --- Subplot 1: Imperceptibility (PSNR in dB) ---
bars1 = ax1.bar(
    methods, 
    psnr_values, 
    color=color_teal, 
    edgecolor=color_teal_dark, 
    width=0.45, 
    linewidth=1.2,
    zorder=3
)
ax1.set_title('Imperceptibility Analysis (PSNR)', fontsize=12, fontweight='bold', pad=15, color='#2c3e50')
ax1.set_ylabel('Peak Signal-to-Noise Ratio (dB)', fontsize=10, fontweight='bold', color='#34495e')
ax1.set_ylim(0, 55)
ax1.set_yticks(np.arange(0, 56, 10))
ax1.tick_params(axis='both', labelsize=9, colors='#2c3e50')

# Gridlines behind bars
ax1.grid(True, which='both', axis='y', linestyle='--', alpha=0.5, color='#dcdde1', zorder=0)
ax1.grid(False, axis='x')

# Remove top and right spines
for spine in ['top', 'right']:
    ax1.spines[spine].set_visible(False)

# Add value labels above the bars
for bar in bars1:
    height = bar.get_height()
    ax1.annotate(
        f'{height:.1f} dB',
        xy=(bar.get_x() + bar.get_width() / 2, height),
        xytext=(0, 4),  # 4 points vertical offset
        textcoords="offset points",
        ha='center', va='bottom', fontsize=9, fontweight='bold', color='#2c3e50'
    )

# --- Subplot 2: Steganalysis Evasion Rate (%) ---
bars2 = ax2.bar(
    methods, 
    evasion_values, 
    color=color_orange, 
    edgecolor=color_orange_dark, 
    width=0.45, 
    linewidth=1.2,
    zorder=3
)
ax2.set_title('Steganalysis Evasion Rate', fontsize=12, fontweight='bold', pad=15, color='#2c3e50')
ax2.set_ylabel('Evasion Rate (%)', fontsize=10, fontweight='bold', color='#34495e')
ax2.set_ylim(0, 120)
ax2.set_yticks(np.arange(0, 101, 20))
ax2.tick_params(axis='both', labelsize=9, colors='#2c3e50')

# Gridlines behind bars
ax2.grid(True, which='both', axis='y', linestyle='--', alpha=0.5, color='#dcdde1', zorder=0)
ax2.grid(False, axis='x')

# Remove top and right spines
for spine in ['top', 'right']:
    ax2.spines[spine].set_visible(False)

# Add value labels above the bars
for bar in bars2:
    height = bar.get_height()
    ax2.annotate(
        f'{height:.1f}%',
        xy=(bar.get_x() + bar.get_width() / 2, height),
        xytext=(0, 4),  # 4 points vertical offset
        textcoords="offset points",
        ha='center', va='bottom', fontsize=9, fontweight='bold', color='#2c3e50'
    )

# Adjust layout and save
plt.tight_layout()

# Resolve path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_path = os.path.join(base_dir, 'assets', 'results_plot.png')
os.makedirs(os.path.dirname(output_path), exist_ok=True)

plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"[OK] Saved results plot to: {output_path}")
