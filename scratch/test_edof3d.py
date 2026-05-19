import numpy as np

def build_edof_3d(nelx, nely, nelz):
    elx, ely, elz = np.meshgrid(np.arange(nelx), np.arange(nely), np.arange(nelz), indexing="ij")
    elx = elx.ravel()
    ely = ely.ravel()
    elz = elz.ravel()
    
    def node(x, y, z):
        return z * (nelx + 1) * (nely + 1) + x * (nely + 1) + y
        
    n1 = node(elx,   ely,   elz)
    n2 = node(elx+1, ely,   elz)
    n3 = node(elx+1, ely+1, elz)
    n4 = node(elx,   ely+1, elz)
    n5 = node(elx,   ely,   elz+1)
    n6 = node(elx+1, ely,   elz+1)
    n7 = node(elx+1, ely+1, elz+1)
    n8 = node(elx,   ely+1, elz+1)
    
    edof = np.column_stack([
        3*n1, 3*n1+1, 3*n1+2,
        3*n2, 3*n2+1, 3*n2+2,
        3*n3, 3*n3+1, 3*n3+2,
        3*n4, 3*n4+1, 3*n4+2,
        3*n5, 3*n5+1, 3*n5+2,
        3*n6, 3*n6+1, 3*n6+2,
        3*n7, 3*n7+1, 3*n7+2,
        3*n8, 3*n8+1, 3*n8+2,
    ]).astype(np.int64)
    return edof

edof = build_edof_3d(2, 2, 2)
print(edof.shape)
print(edof[0])
