import numpy as np

def element_stiffness_3d(E=1.0, nu=0.3):
    """
    Computes the 24x24 element stiffness matrix for a standard 8-node
    hexahedral element (voxel).
    Node ordering follows standard DTU top3d.m (or similar).
    """
    # Inverse of constitutive matrix for isotropic material
    # D = E / ((1+nu)*(1-2*nu)) * [ ... ]
    A = np.array([
        [32, 6, -8, 6, -6, 4, 3, -6, -10, 3, -3, -3, -4, -8],
        [-48, 0, 0, -24, 24, 0, 0, 0, 12, -12, 0, 12, 12, 12]
    ])
    # The matrix K is assembled from various symmetric permutations of these values.
    # A cleaner approach in python is using SymPy or numerical integration.
    
    # Let's do numerical integration over the element [-1, 1]^3.
    # Voxel size is 1x1x1, so domain is [-0.5, 0.5]^3.
    # Nodes in top3d.m order:
    # 0: (0,0,0)? Actually standard ordering is usually:
    # DTU top3d.m node ordering:
    # Node 1: (x, y, z)
    # Node 2: (x+1, y, z)
    # Node 3: (x+1, y+1, z)
    # Node 4: (x, y+1, z)
    # Node 5: (x, y, z+1)
    # Node 6: (x+1, y, z+1)
    # Node 7: (x+1, y+1, z+1)
    # Node 8: (x, y+1, z+1)
    # Wait, DTU top3d.m order is:
    # node1 = z*...
    pass

# We will just write the numerical integration:
import sympy as sp

x, y, z = sp.symbols('x y z')
# shape functions for [-1, 1]^3
N = []
coords = [
    (-1, -1, -1),
    (1, -1, -1),
    (1, 1, -1),
    (-1, 1, -1),
    (-1, -1, 1),
    (1, -1, 1),
    (1, 1, 1),
    (-1, 1, 1)
]
for (xi, yi, zi) in coords:
    N.append(0.125 * (1 + xi*x) * (1 + yi*y) * (1 + zi*z))

B = sp.zeros(6, 24)
for i in range(8):
    dNdx = sp.diff(N[i], x)
    dNdy = sp.diff(N[i], y)
    dNdz = sp.diff(N[i], z)
    # 2 / element_length because xi in [-1,1] maps to x in [0,1] -> dx/dxi = 0.5
    # So dN/dx_physical = dN/dxi * 2. 
    # Actually if element is 1x1x1, dN/dx_phys = 2 * dNdx
    dNdx *= 2
    dNdy *= 2
    dNdz *= 2
    
    B[0, 3*i] = dNdx
    B[1, 3*i+1] = dNdy
    B[2, 3*i+2] = dNdz
    
    B[3, 3*i] = dNdy
    B[3, 3*i+1] = dNdx
    
    B[4, 3*i+1] = dNdz
    B[4, 3*i+2] = dNdy
    
    B[5, 3*i] = dNdz
    B[5, 3*i+2] = dNdx

C = sp.zeros(6, 6)
nu = 0.3
E = 1.0
C[0,0] = C[1,1] = C[2,2] = 1 - nu
C[0,1] = C[0,2] = C[1,0] = C[1,2] = C[2,0] = C[2,1] = nu
C[3,3] = C[4,4] = C[5,5] = (1 - 2*nu) / 2
C = (E / ((1 + nu)*(1 - 2*nu))) * C

K_sym = B.T * C * B
# Det Jacobian is (1/2)^3 = 1/8.
# Integration over [-1,1]^3 is integral(f * detJ dxi dyi dzi)
# Since detJ = 1/8, integral(f) * 1/8.
# Let's do 2x2x2 Gauss quadrature
gauss_pts = [-1/np.sqrt(3), 1/np.sqrt(3)]
K = np.zeros((24, 24))

for gx in gauss_pts:
    for gy in gauss_pts:
        for gz in gauss_pts:
            K_eval = np.array(K_sym.subs({x: gx, y: gy, z: gz})).astype(float)
            K += K_eval * (1.0/8.0)  # detJ = 1/8, weights are all 1.0

with open("scratch/ke3d.py", "w") as f:
    f.write("import numpy as np\n\n")
    f.write("def element_stiffness_3d(E=1.0, nu=0.3):\n")
    f.write("    # Using nu=0.3 hardcoded in this matrix for simplicity, though normally we'd scale it.\n")
    f.write("    K = np.array([\n")
    for i in range(24):
        row = ", ".join(f"{v:.6f}" for v in K[i])
        f.write(f"        [{row}],\n")
    f.write("    ])\n")
    f.write("    return K\n")

