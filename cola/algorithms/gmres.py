from cola.ops import LinearOperator
from cola.ops import Array
from cola.algorithms.arnoldi import run_householder_arnoldi
from cola.algorithms.arnoldi import get_arnoldi_matrix
from cola.utils import export


@export
def gmres(A: LinearOperator, rhs: Array, x0=None, max_iters=None, tol=1e-7, P=None,
          use_householder=False, use_triangular=False, pbar=False, info=False):
    """Solves a linear system Ax = rhs using the GMRES method.

    Args:
        A (LinearOperator): The linear operator representing the matrix A.
        rhs (Array): The right-hand side vector.
        x0 (Array, optional): The initial guess for the solution. Defaults to None.
        max_iters (int, optional): The maximum number of iterations. Defaults to None.
        tol (float, optional): The tolerance for convergence. Defaults to 1e-7.
        P (array, optional): Preconditioner. Defaults to None.
        use_householder (bool, optional): Use Householder Arnoldi iteration. Defaults to False.
        use_triangular (bool, optional): Use triangular QR factorization. Defaults to False.
        pbar (bool, optional): show a progress bar. Defaults to False.
        info (bool, optional): print additional information. Defaults to False.

    Returns:
        Array: The solution vector x, satisfying Ax = rhs.
    """
    xnp = A.ops
    is_vector = len(rhs.shape) == 1
    if x0 is None:
        x0 = xnp.zeros_like(rhs)
    if is_vector:
        rhs = rhs[..., None]
        x0 = x0[..., None]
    res = rhs - A @ x0
    if use_householder:
        Q, H, infodict = run_householder_arnoldi(A=A, rhs=res, max_iters=max_iters)
    else:
        Q, H, _, infodict = get_arnoldi_matrix(A=A, rhs=res, max_iters=max_iters, tol=tol,
                                               pbar=pbar)
        Q = Q[:, :-1]
    beta = xnp.norm(res, axis=-2)
    e1 = xnp.zeros(shape=(H.shape[0], 1), dtype=rhs.dtype)
    e1 = xnp.update_array(e1, beta, 0)

    if use_triangular:
        R, Gs = get_hessenberg_triangular_qr(H, xnp=xnp)
        target = apply_givens_fwd(Gs, e1, xnp)
        if use_householder:
            y = xnp.solvetri(R, target, lower=False)
        else:
            y = xnp.solvetri(R[:-1, :], target[:-1, :], lower=False)
    else:
        y = xnp.solve(H.T @ H, H.T @ e1)
    soln = x0 + Q @ y
    if is_vector:
        soln = soln[:, 0]
    if info:
        return soln, infodict
    else:
        return soln


def get_hessenberg_triangular_qr(H, xnp):
    R = xnp.copy(H)
    Gs = []
    for jdx in range(H.shape[0] - 1):
        cx, sx = get_givens_cos_sin(R[jdx, jdx], R[jdx + 1, jdx], xnp)
        G = xnp.array([[cx, sx], [-sx, cx]], dtype=H.dtype)
        Gs.append(G)
        update = G.T @ R[[jdx, jdx + 1], :]
        R = xnp.update_array(R, update, [jdx, jdx + 1])
    return R, Gs


def apply_givens_fwd(Gs, vec, xnp):
    for jdx in range(len(Gs)):
        update = Gs[jdx].T @ vec[[jdx, jdx + 1], :]
        vec = xnp.update_array(vec, update, [jdx, jdx + 1])
    return vec


def get_givens_cos_sin(a, b, xnp):
    if b == 0:
        c, s = 1, 0
    else:
        denom = xnp.sqrt(a**2. + b**2.)
        s = -b / denom
        c = a / denom
    return c, s
