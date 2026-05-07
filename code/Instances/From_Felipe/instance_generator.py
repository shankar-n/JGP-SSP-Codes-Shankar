import random
import os

BASE_DIR = "/home/local.isima.fr/fsotiai/shared/Project_Tool_Switching/Implementation/Instances/data/Otiai/"

MEDIUM_DIR = os.path.join(BASE_DIR, "medium")
LARGE_DIR = os.path.join(BASE_DIR, "large")

INSTANCES_PER_CLASS = 5

MEDIUM_CLASSES = {
    "M1": (200, 120, 55, 0.27),
    "M2": (250, 150, 90, 0.25),
    "M3": (300, 180, 110, 0.20)
}

LARGE_CLASSES = {
    "L1": (300, 180, 110, 0.20),
    "L2": (350, 210, 150, 0.20),
    "L3": (400, 240, 180, 0.20)
}


# -------------------------
# GENERATION (columns = jobs)
# -------------------------
def generate_instance(N, L, C, r):
    while True:
        # matrix: L rows (tools) × N columns (jobs)
        matrix = [[0 for _ in range(N)] for _ in range(L)]

        # generate each job (column)
        for j in range(N):
            while True:
                col = [1 if random.random() <= r else 0 for _ in range(L)]
                k = sum(col)

                if 1 <= k < C:
                    break

            for t in range(L):
                matrix[t][j] = col[t]

        # check each tool is used at least once
        tool_used = [any(matrix[t][j] for j in range(N)) for t in range(L)]

        if all(tool_used):
            return matrix


# -------------------------
# WRITE (C++ compatible)
# -------------------------
def write_instance(path, matrix, N, L, C):
    with open(path, "w") as f:
        # IMPORTANT: order must be N L C
        f.write(f"{N} {L} {C}\n\n")

        # L rows, each with N values
        for row in matrix:
            f.write(" ".join(map(str, row)) + "\n")


# -------------------------
# VALIDATION (columns = jobs)
# -------------------------
def validate_instance(matrix, N, L, C, r=None, tol=0.05, verbose=True):

    errors = []

    # --- Dimensions ---
    if len(matrix) != L:
        errors.append(f"Invalid number of rows: expected {L}, got {len(matrix)}")

    for t, row in enumerate(matrix):
        if len(row) != N:
            errors.append(f"Row {t} has length {len(row)} instead of {N}")

    if errors:
        return False, errors

    # --- Column sums (jobs) ---
    col_sums = [sum(matrix[t][j] for t in range(L)) for j in range(N)]
    min_k = min(col_sums)
    max_k = max(col_sums)

    for j, k in enumerate(col_sums):
        if k == 0:
            errors.append(f"Job {j} uses no tools")
        if k >= C:
            errors.append(f"Job {j} uses {k} tools (>= C={C})")

    # --- Tool coverage (rows) ---
    for t in range(L):
        if not any(matrix[t][j] for j in range(N)):
            errors.append(f"Tool {t} is never used")

    # --- Optional statistical check ---
    if r is not None:
        total_ones = sum(col_sums)
        empirical_r = total_ones / (N * L)

        if abs(empirical_r - r) > tol:
            errors.append(
                f"Empirical r={empirical_r:.3f} differs from expected r={r}"
            )

    is_valid = len(errors) == 0

    if verbose:
        print(f"Column sum stats (jobs) → min: {min_k}, max: {max_k}")
        if is_valid:
            print("Instance is VALID")
        else:
            print("Instance is INVALID:")
            for e in errors[:10]:
                print(" -", e)
            if len(errors) > 10:
                print(f"... ({len(errors)} errors total)")

    return is_valid, errors


# -------------------------
# GENERATION LOOP
# -------------------------
def generate_group(classes, directory):
    os.makedirs(directory, exist_ok=True)

    MAX_ATTEMPTS = 50

    for name, (N, L, C, r) in classes.items():
        for i in range(INSTANCES_PER_CLASS):

            filename = f"{name}-{i}.txt"
            path = os.path.join(directory, filename)

            # avoid overwriting
            if os.path.exists(path):
                print("Skipped (already exists):", path)
                continue

            for attempt in range(MAX_ATTEMPTS):
                matrix = generate_instance(N, L, C, r)

                is_valid, _ = validate_instance(
                    matrix, N, L, C, r=r, verbose=False
                )

                if is_valid:
                    break
            else:
                raise RuntimeError(f"Failed to generate valid instance {name}-{i}")

            print(f"\n{name}-{i}:")
            validate_instance(matrix, N, L, C, r=r, verbose=True)

            write_instance(path, matrix, N, L, C)
            print("Saved:", path)


# -------------------------
# MAIN
# -------------------------
def main():
    random.seed(42)
    generate_group(MEDIUM_CLASSES, MEDIUM_DIR)
    generate_group(LARGE_CLASSES, LARGE_DIR)


if __name__ == "__main__":
    main()