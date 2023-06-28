import time
import numpy as np
from linops import jax_fns
from linops.linalg.inverse import inverse
from linops.experiment_utils import get_data_class1
from linops.experiment_utils import print_time_taken
from linops.experiment_utils import save_object
from jax.config import config

save_output = True
case = "linops_cpu"
if case.find("cpu") >= 0:
    config.update('jax_platform_name', 'cpu')
output_path = f"./logs/timings_{case}.pkl"
xnp = jax_fns
dtype = xnp.float32
tic = time.time()
results = {}
Ns = [100, 900, 10_000, 90_000, 1_000_000]
repeat = 3
times = np.zeros(shape=(len(Ns), repeat))
res = np.zeros(shape=(len(Ns), repeat))
for idx, N in enumerate(Ns):
    K = get_data_class1(N, xnp, dtype)
    rhs = xnp.array(np.random.normal(size=(K.shape[0], )), dtype=dtype)
    for jdx in range(repeat):
        print(f"Problem size: {K.shape[0]:,d}")

        Kinv = inverse(K, method="cg", info=False, tol=1e-8)
        t0 = time.time()
        soln = Kinv @ rhs
        t1 = time.time()
        times[idx, jdx] = t1 - t0
        res[idx, jdx] = xnp.norm(K @ soln - rhs) / xnp.norm(rhs)

results["times"] = times
results["sizes"] = Ns
results["res"] = res
print(results)
print(f"\nTimes {np.mean(times[1:]):1.5e} sec")

toc = time.time()
print_time_taken(toc - tic)
if save_output:
    save_object(results, filepath=output_path)