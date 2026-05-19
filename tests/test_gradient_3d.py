import numpy as np
from core.fea import element_stiffness_3d, compliance_and_sensitivity
from core.problem import cantilever_3d

def test_fd_gradient_3d():
    # Setup small problem
    prob = cantilever_3d(2, 2, 2)
    ndof = prob.ndof
    
    from core.fea import build_edof_3d, build_assembly_indices, assemble_K, solve_displacement
    KE = element_stiffness_3d()
    edof = build_edof_3d(prob.nelx, prob.nely, prob.nelz)
    iK, jK = build_assembly_indices(edof)
    
    np.random.seed(42)
    x = np.random.uniform(0.1, 1.0, size=prob.nelx * prob.nely * prob.nelz)
    
    # Analytic grad
    K = assemble_K(x, KE, iK, jK, ndof, 3.0, 1.0, 1e-9)
    U = solve_displacement(K, prob.F, prob.free_dofs)
    c, dc, _ = compliance_and_sensitivity(x, U, edof, KE, 3.0, 1.0, 1e-9)
    
    # FD grad for one element
    idx = 3 # test 4th element
    dx = 1e-6
    x_plus = x.copy()
    x_plus[idx] += dx
    K_plus = assemble_K(x_plus, KE, iK, jK, ndof, 3.0, 1.0, 1e-9)
    U_plus = solve_displacement(K_plus, prob.F, prob.free_dofs)
    
    # C = F^T U
    c_plus = np.dot(prob.F, U_plus)
    
    x_minus = x.copy()
    x_minus[idx] -= dx
    K_minus = assemble_K(x_minus, KE, iK, jK, ndof, 3.0, 1.0, 1e-9)
    U_minus = solve_displacement(K_minus, prob.F, prob.free_dofs)
    
    c_minus = np.dot(prob.F, U_minus)
    
    fd_dc = (c_plus - c_minus) / (2 * dx)
    
    assert np.isclose(dc[idx], fd_dc, rtol=1e-3, atol=1e-5), f"Analytic: {dc[idx]}, FD: {fd_dc}"
