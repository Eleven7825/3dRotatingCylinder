import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def calculate_total_volume(Radius, L, fin_outer_radii, fin_thickness, total_disks):
    """
    Calculate total volume of cylinder with annular fins
    
    Parameters:
    -----------
    Radius : float
        Inner cylinder radius (cm)
    L : float
        Length of cylinder (cm)
    fin_outer_radii : list or array
        Outer radii for each type of fin (cm)
    fin_thickness : float
        Thickness of each fin (cm)
    total_disks : int
        Total number of disks/fins (including end caps)
    
    Returns:
    --------
    total_volume : float
        Total volume in cm³
    breakdown : dict
        Volume breakdown by component
    """
    
    # Main cylinder volume
    cylinder_volume = np.pi * Radius**2 * L
    
    # Calculate fin volumes
    fin_volumes = []
    fin_descriptions = []
    
    for i, outer_radius in enumerate(fin_outer_radii):
        # Annular area = π(R_outer² - R_inner²)
        annular_area = np.pi * (outer_radius**2 - Radius**2)
        
        # Volume = area × thickness × number of fins with this radius
        if i == 0:  # End caps (typically largest)
            num_fins = 2  # Two end caps
            description = f"End cap fins (R={outer_radius} cm)"
        else:  # Internal disks
            num_fins = total_disks - 2 if total_disks > 2 else 0  # All internal disks
            description = f"Internal fins (R={outer_radius} cm)"
        
        fin_volume = annular_area * fin_thickness * num_fins
        fin_volumes.append(fin_volume)
        fin_descriptions.append(description)
    
    # Total volume
    total_fin_volume = sum(fin_volumes)
    total_volume = cylinder_volume + total_fin_volume
    
    # Create breakdown dictionary
    breakdown = {
        'cylinder_volume': cylinder_volume,
        'total_fin_volume': total_fin_volume,
        'fin_breakdown': dict(zip(fin_descriptions, fin_volumes)),
        'total_volume': total_volume
    }
    
    return total_volume, breakdown

# Clear variables (Python handles this automatically with scope)

# Mesh parameters
Lx = 100.0
Ly = 45.0
Lz = 35.0
Nx = 100 * 4 * 2 * 2
Ny = 45 * 4 * 2 * 2
Nz = 35 * 4 * 2 * 2
dx = Lx / Nx
dy = Ly / Ny
dz = Lz / Nz
L = 25.5

# Cylinder parameters
X_com = 0.0
Y_com = 0.0
Z_com = 0.0
Radius = 3.17
disk_radius = 5.75
endCap_radius = 7.0
use_disk = 1

# NEW PARAMETER: Total number of disks (including end caps)
total_disks = 2  # Change this to generate any number of equally spaced disks

# NEW PARAMETERS: Fin properties for volume calculation
fin_thickness = 0.1  # cm, thickness of fins
fin_outer_radii = [endCap_radius, disk_radius]  # Outer radii: [end_caps, internal_disks]

num_pts_x = int(np.ceil(2 * endCap_radius / dx))
num_pts_y = int(np.ceil(2 * endCap_radius / dy))
num_pts_z = int(np.ceil(L / dz))

# Calculate equally spaced disk positions
disk_positions = []
endcap_positions = []

if use_disk == 1 and total_disks >= 2:
    # Calculate equally spaced positions for ALL disks (including end caps)
    # Total disks are positioned at: 1, ?, ?, ..., num_pts_z
    spacing = (num_pts_z - 1) / (total_disks - 1)
    all_positions = [int(round(1 + i * spacing)) for i in range(total_disks)]
    
    # First and last are end caps
    endcap_positions = [all_positions[0], all_positions[-1]]
    # Middle ones are internal disks (if any)
    if total_disks > 2:
        disk_positions = all_positions[1:-1]
    else:
        disk_positions = []
elif use_disk == 1:
    # Only end caps if total_disks < 2
    endcap_positions = [1, num_pts_z]

print(f"Total disks: {total_disks}")
print(f"End cap positions (z-layer indices): {endcap_positions}")
print(f"Internal disk positions (z-layer indices): {disk_positions}")
if total_disks >= 2:
    all_disk_positions = sorted(endcap_positions + disk_positions)
    print(f"All disk positions: {all_disk_positions}")
    # Calculate and display spacing
    spacings = [all_disk_positions[i+1] - all_disk_positions[i] for i in range(len(all_disk_positions)-1)]
    print(f"Spacing between consecutive disks: {spacings}")

# Generate points inside the 3D cylinder
X_array = []
Y_array = []
Z_array = []
idx = 0

# Open indices file for writing
with open('./indices', 'w') as fid0:
    for k in range(1, num_pts_z + 1):
        z = Z_com + ((k - 1) * dz - Lz / 2)
        
        # Determine radius based on z-position
        if k in endcap_positions and use_disk == 1:
            # End caps
            a = endCap_radius
        elif k in disk_positions and use_disk == 1:
            # Internal disks
            a = disk_radius
        else:
            # Regular cylinder
            a = Radius
        
        start_idx = idx
        for i in range(1, num_pts_x + 1):
            x = X_com + ((i - 1) * dx - a)
            for j in range(1, num_pts_y + 1):
                y = Y_com + ((j - 1) * dy - a)
                if ((x - X_com)**2 + (y - Y_com)**2) <= a**2:
                    idx += 1
                    X_array.append(x)
                    Y_array.append(y)
                    Z_array.append(z)
        
        # Write to indices file for end caps
        if k in endcap_positions:
            fid0.write(f"End cap at layer {k}: {idx - 1}\n")
        # Also write indices for internal disks
        elif k in disk_positions:
            fid0.write(f"Disk at layer {k}: {idx - 1}\n")

# Convert to numpy arrays
X_array = np.array(X_array)
Y_array = np.array(Y_array)
Z_array = np.array(Z_array)

# Calculate center of mass and recenter the points
XCOM = np.sum(X_array) / len(X_array)
YCOM = np.sum(Y_array) / len(Y_array)
ZCOM = np.sum(Z_array) / len(Z_array)

X_array = X_array - XCOM
Y_array = Y_array - YCOM
Z_array = Z_array - ZCOM

# Plot the cylinder (uncomment to visualize)
fig = plt.figure(figsize=(12, 8))
ax = fig.add_subplot(111, projection='3d')

# Color points differently for visualization
colors = ['blue'] * len(X_array)  # Default cylinder color

# Highlight disk regions
for k in range(1, num_pts_z + 1):
    z_val = Z_com + ((k - 1) * dz - Lz / 2) - ZCOM  # Adjusted for recentering
    
    if k in endcap_positions:
        # End caps in red
        mask = np.abs(Z_array - z_val) < dz/2
        for i in np.where(mask)[0]:
            colors[i] = 'red'
    elif k in disk_positions:
        # Internal disks in green
        mask = np.abs(Z_array - z_val) < dz/2
        for i in np.where(mask)[0]:
            colors[i] = 'green'

ax.scatter(X_array, Y_array, Z_array, c=colors, s=1, alpha=0.6)
ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
ax.set_title(f'3D Cylinder with {total_disks} Equally Spaced Disks\n(Red: End caps, Green: Internal disks, Blue: Cylinder)')

# Set equal aspect ratio for all axes
ax.set_box_aspect([1,1,1])  # Equal aspect ratio
# Alternative method that also works:
# max_range = max(np.ptp(X_array), np.ptp(Y_array), np.ptp(Z_array)) / 2.0
# mid_x = (X_array.max() + X_array.min()) * 0.5
# mid_y = (Y_array.max() + Y_array.min()) * 0.5
# mid_z = (Z_array.max() + Z_array.min()) * 0.5
# ax.set_xlim(mid_x - max_range, mid_x + max_range)
# ax.set_ylim(mid_y - max_range, mid_y + max_range)
# ax.set_zlim(mid_z - max_range, mid_z + max_range)

plt.show()

# Write the coordinates to file
with open('./cylinder3d.vertex', 'w') as fid:
    fid.write(f'{len(X_array)}\n')
    for i in range(len(X_array)):
        fid.write(f'{X_array[i]:.6f}\t{Y_array[i]:.6f}\t{Z_array[i]:.6f}\n')

print(f"Generated {len(X_array)} points inside the 3D cylinder")
print(f"Total number of disks: {total_disks}")
print(f"Points written to './cylinder3d.vertex'")
print(f"Indices written to './indices'")
if total_disks >= 2:
    all_positions = sorted(endcap_positions + disk_positions)
    print(f"All disk z-layer positions: {all_positions}")

# Calculate and display total volume
print("\n" + "="*50)
print("VOLUME CALCULATION")
print("="*50)
total_vol, breakdown = calculate_total_volume(Radius, L, fin_outer_radii, fin_thickness, total_disks)

print(f"Main cylinder volume: {breakdown['cylinder_volume']:.3f} cm³")
print(f"Total fin volume: {breakdown['total_fin_volume']:.3f} cm³")
print(f"TOTAL SYSTEM VOLUME: {total_vol:.3f} cm³")
print()

print("Fin Volume Breakdown:")
for description, volume in breakdown['fin_breakdown'].items():
    print(f"  {description}: {volume:.3f} cm³")

print()
print("System Parameters Used:")
print(f"  Inner cylinder radius: {Radius} cm")
print(f"  Cylinder length: {L} cm")
print(f"  Fin thickness: {fin_thickness} cm")
print(f"  End cap radius: {endCap_radius} cm")
print(f"  Internal disk radius: {disk_radius} cm")
print(f"  Total number of disks: {total_disks}")
print(f"  Number of end caps: 2")
print(f"  Number of internal disks: {max(0, total_disks - 2)}")
print("="*50)
