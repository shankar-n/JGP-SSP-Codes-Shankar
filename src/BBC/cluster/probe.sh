#!/bin/bash
# Run this ON the frontalhpc2025 login node, then paste the whole output back.
# It tells us how CPLEX/Python are provided and what partitions you can use,
# so the sbatch ENV lines can be finalized.
echo "==== host ===="; hostname
echo "==== partitions / nodes (sinfo) ===="; sinfo -N 2>&1 | head -40
echo "==== your slurm associations ===="; sacctmgr -n show assoc user="$USER" format=account%20,partition%15,qos%20 2>&1 | head
echo "==== cplex CLI on PATH? ===="; which cplex 2>&1 && (cplex -c "quit" 2>&1 | head -3) || echo "cplex CLI NOT on PATH"
echo "==== module system / relevant modules ===="; (module avail) 2>&1 | grep -iE "cplex|python|scip|gurobi" || echo "no matching modules (or no 'module' command)"
echo "==== system python ===="; which python3 2>&1; python3 --version 2>&1
echo "==== CPLEX Python API importable? ===="; python3 -c "import cplex; print('cplex py OK', cplex.__version__)" 2>&1 | head -3
echo "==== numpy importable? ===="; python3 -c "import numpy; print('numpy', numpy.__version__)" 2>&1 | head -1
echo "==== common CPLEX install locations ===="; ls -d /opt/ibm/ILOG/CPLEX_Studio*/cplex/python/*/x86-64_linux /usr/local/cplex* "$HOME"/cplex* 2>/dev/null || echo "none in common locations"
echo "==== done — paste everything above ===="
