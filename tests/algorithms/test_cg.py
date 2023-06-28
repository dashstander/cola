import numpy as np
from linops import jax_fns
from linops import torch_fns
from linops.linear_algebra import lazify
from linops.ops import Identity
from linops.ops import Diagonal
from linops.ops import CustomLinOp
from linops.algorithms.preconditioners import NystromPrecond
from linops.algorithms.cg import solve_cg
from linops.algorithms.cg import run_batched_cg
from linops.algorithms.cg import run_batched_tracking_cg
from linops.algorithms.cg import run_cg
from linops.utils_test import parametrize, relative_error
from linops.utils_test import generate_spectrum, generate_pd_from_diag
from linops.utils_test import generate_diagonals
# from tests.algorithms.test_lanczos import construct_tridiagonal
from jax.config import config

config.update('jax_platform_name', 'cpu')
# config.update("jax_enable_x64", True)

_tol = 1e-7


@parametrize([torch_fns, jax_fns])
def test_cg_vjp(xnp):
    dtype = xnp.float32
    diag = xnp.Parameter(xnp.array([3., 4., 5.], dtype=dtype))
    diag_soln = xnp.Parameter(xnp.array([3., 4., 5.], dtype=dtype))
    A = xnp.diag(diag)
    ones = xnp.ones(shape=(3, 1), dtype=dtype)
    max_iters, tol = 5, 1e-8
    x0 = xnp.zeros_like(ones)
    pbar, tol = False, 1e-6
    P = Identity(dtype=A.dtype, shape=A.shape)
    _, unflatten = Diagonal(diag).flatten()

    def f(theta):
        A = unflatten([theta])
        solve, *_ = run_cg(A, ones, x0, max_iters, tol, P, pbar)
        loss = xnp.sum(solve)
        return loss

    def f_alt(theta):
        X = xnp.diag(theta)
        solve = xnp.solve(X, ones)
        loss = xnp.sum(solve)
        return loss

    out = f(diag)
    if xnp.__name__.find("torch") >= 0:
        out.backward()
        approx = diag.grad.clone()
    else:
        approx = xnp.grad(f)(diag)
    assert approx is not None

    out = f_alt(diag_soln)
    if xnp.__name__.find("torch") >= 0:
        out.backward()
        soln = diag_soln.grad.clone()
    else:
        soln = xnp.grad(f_alt)(diag)

    rel_error = relative_error(soln, approx)
    assert rel_error < _tol * 10


# @parametrize([torch_fns, jax_fns])
# def test_cg_lanczos_coeffs(xnp):
#     dtype = xnp.float32
#     A = xnp.diag(xnp.array([3., 4., 5.], dtype=dtype))
#     rhs = xnp.ones(shape=(A.shape[0], 1), dtype=dtype)
#     soln = xnp.array([[1 / 3, 1 / 4, 1 / 5]]).T
#
#     max_iters, tolerance = 20, 1e-8
#     fn = xnp.jit(run_batched_tracking_cg, static_argnums=(0, 3, 4, 5, 6))
#     x0 = xnp.zeros_like(rhs)
#     precond_fn = Identity(dtype=A.dtype, shape=A.shape)
#     out = fn(lazify(A), rhs, x0, max_iters, tolerance, precond_fn, pbar=True)
#     approx, _, k, tracker, _ = out
#     alphas, betas = tracker[1][:k, 0], tracker[2][:k - 1, 0]
#     diag = 1. / alphas
#     update = diag[1:] + (betas / alphas[:k - 1])
#     diag = xnp.update_array(diag, update, slice(1, None))
#     band = xnp.sqrt(betas) / alphas[:k - 1]
#     T_approx = construct_tridiagonal(band, diag, band)
#
#     rhs = np.array(rhs[:, 0], dtype=np.float64)
#     x0 = np.zeros_like(rhs)
#     out = run_cg_lanczos(np.array(A, np.float64), rhs, x0, max_iters=5, tolerance=1e-8)
#     _, alpha, beta, _, k, _ = out
#     T_soln = construct_tri(alpha[1:k], beta[1:k + 1])
#
#     rel_error = relative_error(soln, approx)
#     assert rel_error < _tol
#
#     rel_error = relative_error(xnp.array(T_soln), T_approx)
#     assert rel_error < _tol


@parametrize([torch_fns, jax_fns])
def test_cg_complex(xnp):
    dtype = xnp.complex64
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=25, dtype=np.float32)
    A = xnp.array(generate_diagonals(diag, seed=48), dtype=dtype)
    rhs = xnp.randn(A.shape[1], 1, dtype=dtype)
    soln = xnp.solve(A, rhs)

    B = lazify(A)
    max_iters, tolerance = 100, 1e-8
    precond_fn = Identity(dtype=A.dtype, shape=A.shape)
    x0 = xnp.zeros_like(rhs)
    fn = xnp.jit(run_batched_cg, static_argnums=(0, 3, 4, 5, 6))
    approx, *_ = fn(B, rhs, x0, max_iters, tolerance, precond_fn, pbar=True)

    rel_error = relative_error(soln, approx)
    assert rel_error < 1e-5


@parametrize([torch_fns, jax_fns])
def test_cg_random(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.75, scale=1.0, size=25, dtype=np.float32)
    A = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype), dtype=dtype)
    rhs = xnp.ones(shape=(A.shape[0], 5), dtype=dtype)
    soln = xnp.solve(A, rhs)

    B = lazify(A)
    max_iters, tolerance = 100, 1e-8
    rank = 5
    precond_fn = NystromPrecond(B, rank=rank, mu=0, eps=1e-8)
    x0 = xnp.zeros_like(rhs)
    fn = xnp.jit(run_batched_cg, static_argnums=(0, 3, 4, 5, 6))
    approx, *_ = fn(B, rhs, x0, max_iters, tolerance, precond_fn, pbar=True)

    rel_error = relative_error(soln, approx)
    assert rel_error < 1e-6


@parametrize([torch_fns, jax_fns])
def test_cg_repeated_eig(xnp):
    dtype = xnp.float32
    diag = [1. for _ in range(10)] + [0.5 for _ in range(10)] + [0.25 for _ in range(10)]
    diag = np.array(diag, dtype=np.float32)
    A = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype), dtype=dtype)
    rhs = xnp.ones(shape=(A.shape[0], 1), dtype=dtype)
    soln = xnp.solve(A, rhs)

    B = lazify(A)
    max_iters, tolerance = 100, 1e-11
    fn = xnp.jit(run_batched_cg, static_argnums=(0, 3, 4, 5, 6))
    x0 = xnp.zeros_like(rhs)
    precond_fn = Identity(dtype=A.dtype, shape=A.shape)
    approx, _, k, _ = fn(B, rhs, x0, max_iters, tolerance, precond_fn, pbar=False)

    assert k < 7
    rel_error = relative_error(soln, approx)
    assert rel_error < _tol * 10


@parametrize([torch_fns, jax_fns])
def test_cg_track_easy(xnp):
    dtype = xnp.float64
    A = xnp.diag(xnp.array([3., 4., 5.], dtype=dtype))
    rhs = [[1, 3], [1, 4], [1, 5]]
    rhs = xnp.array(rhs, dtype=dtype)
    soln = [[1 / 3, 1], [1 / 4, 1], [1 / 5, 1]]
    soln = xnp.array(soln, dtype=dtype)

    max_iters, tolerance = 5, 1e-8
    fn = xnp.jit(run_batched_tracking_cg, static_argnums=(0, 3, 4, 5, 6))
    x0 = xnp.zeros_like(rhs)
    precond_fn = Identity(dtype=A.dtype, shape=A.shape)
    approx, *_ = fn(lazify(A), rhs, x0, max_iters, tolerance, precond_fn)

    rel_error = relative_error(soln, approx)
    assert rel_error < _tol


@parametrize([torch_fns, jax_fns])
def test_cg_easy_case(xnp):
    dtype = xnp.float64
    A = xnp.diag(xnp.array([3., 4., 5.], dtype=dtype))
    rhs = xnp.array([[1.0 for _ in range(A.shape[0])]], dtype=dtype).T
    soln = xnp.array([[1 / 3, 1 / 4, 1 / 5]]).T
    rhs = [[1, 3], [1, 4], [1, 5]]
    rhs = xnp.array(rhs, dtype=dtype)
    soln = [[1 / 3, 1], [1 / 4, 1], [1 / 5, 1]]
    soln = xnp.array(soln, dtype=dtype)

    out = []
    for vec in [A, rhs, soln]:
        vec = vec[None, ...]
        vec = xnp.concatenate((vec, vec), 0)
        out.append(vec)
    A, rhs, soln = out

    def matmat(x):
        v1 = A[0, :, :] @ x[0, :, :]
        v2 = A[1, :, :] @ x[1, :, :]
        return xnp.concatenate((v1[None, ...], v2[None, ...]), 0)

    A_fn = CustomLinOp(dtype=dtype, shape=A.shape, matmat=matmat)

    fn = xnp.jit(solve_cg, static_argnums=(0, 3, 4, 5, 6, 7, 8))
    approx, _ = fn(A_fn, rhs)

    rel_error = relative_error(soln, approx)
    assert rel_error < _tol

    _, info = solve_cg(A_fn, rhs, info=True)
    assert all([key in info.keys() for key in ["iterations", "residuals"]])

    approx, _ = solve_cg(lazify(A[0, :, :]), rhs[0, :, 0], info=False)
    rel_error = relative_error(soln[0, :, 0], approx)
    assert rel_error < _tol


def test_cg_lanczos():
    dtype = np.float64
    A = np.diag(np.array([3., 4., 5.], dtype=dtype))
    rhs = np.ones(shape=(A.shape[0], 1), dtype=dtype)
    soln = np.array([[1 / 3, 1 / 4, 1 / 5]]).T

    x0 = np.zeros_like(rhs[:, 0])
    max_iters, tolerance = 5, 1e-8
    out = run_cg_lanczos(A, rhs[:, 0], x0, max_iters, tolerance)
    x, alpha, beta, q, k, res = out
    approx = x[:, k]
    Q = q[:, 1:k + 1]
    T = construct_tri(alpha[1:k], beta[1:k + 1])

    assert np.linalg.norm(res[:, k]) < tolerance
    rel_error = relative_error(soln[:, 0], approx)
    assert rel_error < _tol
    rel_error = relative_error(A @ Q, Q @ T)
    assert rel_error < _tol
    rel_error = relative_error(np.eye(Q.shape[0]), Q.T @ Q)
    assert rel_error < _tol


def run_cg_lanczos(A, rhs, x0, max_iters, tolerance):
    out = initialize_cg_lanczos(A, rhs, x0, max_iters)
    x, alpha, beta, k, res, q, des, dir, nu, gamma = out

    while ((alpha[k] > tolerance) & (k < max_iters - 1)):
        q[:, k + 1] = res[:, k] / alpha[k]
        k += 1
        Aq = A @ q[:, k]
        beta[k] = q[:, k].T @ Aq
        if k == 1:
            dir[k] = beta[k]
            nu[k] = alpha[k - 1] / dir[k]
            des[:, k] = q[:, k]
        else:
            gamma[k - 1] = alpha[k - 1] / dir[k - 1]
            dir[k] = beta[k] - alpha[k - 1] * gamma[k - 1]
            nu[k] = -(alpha[k - 1] * nu[k - 1]) / dir[k]
            des[:, k] = q[:, k] - gamma[k - 1] * des[:, k - 1]
        x[:, k] = x[:, k - 1] + nu[k] * des[:, k]
        res[:, k] = Aq - beta[k] * q[:, k] - alpha[k - 1] * q[:, k - 1]
        alpha[k] = np.linalg.norm(res[:, k])
    return x, alpha, beta, q, k, res


def initialize_cg_lanczos(A, rhs, x0, max_iters):
    dtype = rhs.dtype
    k = 0
    res = np.zeros((rhs.shape[0], max_iters), dtype=dtype)
    q = np.zeros((rhs.shape[0], max_iters), dtype=dtype)
    des = np.zeros((rhs.shape[0], max_iters), dtype=dtype)
    x = np.zeros((rhs.shape[0], max_iters), dtype=dtype)
    dir = np.zeros((max_iters, ), dtype=dtype)
    gamma = np.zeros((max_iters, ), dtype=dtype)
    beta = np.zeros((max_iters, ), dtype=dtype)
    alpha = np.zeros((max_iters, ), dtype=dtype)
    nu = np.zeros((max_iters, ), dtype=dtype)

    x[:, 0] = x0.copy()
    res[:, k] = rhs - A @ x[:, k]
    alpha[k] = np.linalg.norm(res[:, k])
    return x, alpha, beta, k, res, q, des, dir, nu, gamma


def construct_tri(band, diag):
    dim = diag.shape[0]
    T = np.zeros((dim, dim), dtype=diag.dtype)
    for idx in range(dim):
        T[idx, idx] = diag[idx]
        if idx == 0:
            T[idx, idx + 1] = band[idx]
        elif idx == dim - 1:
            T[idx, idx - 1] = band[idx - 1]
        else:
            T[idx, idx + 1] = band[idx]
            T[idx, idx - 1] = band[idx - 1]
    return T