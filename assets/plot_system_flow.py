import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_system_flow():
    # Set up clean, modern figure
    fig, ax = plt.subplots(figsize=(8, 10), dpi=300)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)
    ax.axis('off')
    
    # Custom color palette (matching modern HSL/zero-trust UI system)
    color_bg = '#f8f9fa'
    color_border = '#cbd5e1'
    
    # Component colors
    colors = {
        'biometrics': {'bg': '#e0f2fe', 'border': '#0284c7', 'text': '#0369a1'},
        'crypto': {'bg': '#fef3c7', 'border': '#d97706', 'text': '#b45309'},
        'stego': {'bg': '#ecfdf5', 'border': '#059669', 'text': '#047857'},
        'monitor': {'bg': '#fee2e2', 'border': '#dc2626', 'text': '#b91c1c'}
    }
    
    # 1. Main Background Box for the Security Layer Compartment
    bg_box = patches.FancyBboxPatch(
        (0.5, 0.5), 9.0, 11.0,
        boxstyle="round,pad=0.2",
        facecolor=color_bg,
        edgecolor=color_border,
        linestyle='--',
        linewidth=1.5,
        zorder=1
    )
    ax.add_patch(bg_box)
    
    # Label for the main box
    ax.text(
        5.0, 11.4,
        "MODULAR SECURITY CORE SERVICE LAYER",
        ha='center', va='center',
        fontsize=11, fontweight='bold',
        color='#64748b'
    )
    
    # Define vertical centers for each step
    y_positions = {
        'biometrics': 9.8,
        'crypto': 7.0,
        'stego': 4.2,
        'monitor': 1.4
    }
    
    # Width and height of component boxes
    box_w = 7.0
    box_h = 1.6
    
    # Draw Component 1: Edge Biometrics
    y = y_positions['biometrics']
    box1 = patches.FancyBboxPatch(
        (5.0 - box_w/2, y - box_h/2), box_w, box_h,
        boxstyle="round,pad=0.1",
        facecolor=colors['biometrics']['bg'],
        edgecolor=colors['biometrics']['border'],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(box1)
    ax.text(5.0, y + 0.3, "1. EDGE BIOMETRIC AUTHENTICATION", ha='center', va='center', fontsize=12, fontweight='bold', color=colors['biometrics']['text'])
    ax.text(5.0, y - 0.2, "dlib 128D Face Embeddings \u2022 Active Liveness Detection\nReal-time Haar Cascade Eyes/Mouth Landmarks Validation", ha='center', va='center', fontsize=9, color='#334155')
    
    # Draw Component 2: Threshold Crypto
    y = y_positions['crypto']
    box2 = patches.FancyBboxPatch(
        (5.0 - box_w/2, y - box_h/2), box_w, box_h,
        boxstyle="round,pad=0.1",
        facecolor=colors['crypto']['bg'],
        edgecolor=colors['crypto']['border'],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(box2)
    ax.text(5.0, y + 0.3, "2. THRESHOLD CRYPTOGRAPHIC CORE", ha='center', va='center', fontsize=12, fontweight='bold', color=colors['crypto']['text'])
    ax.text(5.0, y - 0.2, "AES-128-GCM Symmetric Encryption \u2022 PBKDF2 Key Derivation\n(k, n) Shamir Secret Sharing Key Shattering over GF(2^8)", ha='center', va='center', fontsize=9, color='#334155')
    
    # Draw Component 3: Stego Hiding
    y = y_positions['stego']
    box3 = patches.FancyBboxPatch(
        (5.0 - box_w/2, y - box_h/2), box_w, box_h,
        boxstyle="round,pad=0.1",
        facecolor=colors['stego']['bg'],
        edgecolor=colors['stego']['border'],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(box3)
    ax.text(5.0, y + 0.3, "3. DUAL-DOMAIN STEGO HIDING ENGINE", ha='center', va='center', fontsize=12, fontweight='bold', color=colors['stego']['text'])
    ax.text(5.0, y - 0.2, "Discrete Wavelet Transform (2D Haar DWT) Frequency Hiding\nSpatial-Domain Least Significant Bit (LSB) Decoy Trap", ha='center', va='center', fontsize=9, color='#334155')
    
    # Draw Component 4: Security Monitor
    y = y_positions['monitor']
    box4 = patches.FancyBboxPatch(
        (5.0 - box_w/2, y - box_h/2), box_w, box_h,
        boxstyle="round,pad=0.1",
        facecolor=colors['monitor']['bg'],
        edgecolor=colors['monitor']['border'],
        linewidth=2,
        zorder=2
    )
    ax.add_patch(box4)
    ax.text(5.0, y + 0.3, "4. CONTEXTUAL SECURITY MONITOR", ha='center', va='center', fontsize=12, fontweight='bold', color=colors['monitor']['text'])
    ax.text(5.0, y - 0.2, "Geofencing IP Audits \u2022 Impossible Travel Risk Evaluation\nDynamic Step-up Authorization with Hardware RSA-2048 Signatures", ha='center', va='center', fontsize=9, color='#334155')
    
    # Draw connecting arrows between boxes
    arrow_props = dict(
        arrowstyle="-|>",
        color='#64748b',
        lw=2.5,
        mutation_scale=20,
        zorder=3
    )
    
    # Arrow 1 -> 2
    ax.annotate("", xy=(5.0, y_positions['crypto'] + box_h/2), xytext=(5.0, y_positions['biometrics'] - box_h/2), arrowprops=arrow_props)
    
    # Arrow 2 -> 3
    ax.annotate("", xy=(5.0, y_positions['stego'] + box_h/2), xytext=(5.0, y_positions['crypto'] - box_h/2), arrowprops=arrow_props)
    
    # Arrow 3 -> 4
    ax.annotate("", xy=(5.0, y_positions['monitor'] + box_h/2), xytext=(5.0, y_positions['stego'] - box_h/2), arrowprops=arrow_props)
    
    # Save to high-res PNG image
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_path = os.path.join(base_dir, 'assets', 'system_flow.png')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved system flow diagram to: {output_path}")

if __name__ == "__main__":
    draw_system_flow()
