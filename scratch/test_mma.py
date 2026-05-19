import numpy as np
import mmapy.mma

m = 1
n = 10
iter = 1
xval = np.full((n, 1), 0.5)
xmin = np.zeros((n, 1))
xmax = np.ones((n, 1))
xold1 = xval.copy()
xold2 = xval.copy()
f0val = 100.0
df0dx = -np.ones((n, 1))
fval = np.array([[np.mean(xval) / 0.5 - 1.0]])
dfdx = np.array([[1.0 / (0.5 * n)] * n])
low = xmin.copy()
upp = xmax.copy()
a0 = 1.0
a = np.zeros((m, 1))
c = np.full((m, 1), 1000.0)
d = np.zeros((m, 1))

res = mmapy.mma.mmasub(m, n, iter, xval, xmin, xmax, xold1, xold2, 
                       f0val, df0dx, fval, dfdx, low, upp, a0, a, c, d)
xmma, ymma, zmma, lam, xsi, eta, mu, zet, s, low, upp = res
print("xmma shape:", xmma.shape)
print("xmma:", xmma.flatten())
