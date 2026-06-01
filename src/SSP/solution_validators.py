def validate_jgp(batches, n_jobs, cap, tool_req):
        """
        Verify JGP solution feasibility.
        Checks: (a) each batch fits in cap, (b) all required tools are loaded.
        """
        jobs_seen = set()
        for idx, (jobs, tools) in enumerate(batches):
            # Capacity
            if len(tools) > cap:
                raise ValueError(
                    f"Batch {idx}: {len(tools)} tools > capacity {cap}"
                )
            # Tool coverage
            required = set()
            for j in jobs:
                required.update(tool_req[j])
            tools_set = set(tools)
            if not required.issubset(tools_set):
                raise ValueError(
                    f"Batch {idx}: missing tools {required - tools_set}"
                )
            jobs_seen.update(jobs)
        # All jobs covered
        if jobs_seen != set(range(n_jobs)):
            raise ValueError(
                f"JGP missing jobs: {set(range(n_jobs)) - jobs_seen}"
            )
        return True

def validate_ssp(route, n_jobs, cap, tool_req):
    """
    Verify SSP solution feasibility.
    Checks: (a) each config fits in cap, (b) config covers job's tools,
            (c) all jobs appear exactly once.
    """
    jobs_seen = set()
    for (cfg, j) in route:
        if cfg == "DUMMY":
            continue
        if len(cfg) > cap:
            raise ValueError(
                f"Config {cfg} size {len(cfg)} > capacity {cap}"
            )
        if not set(tool_req[j]).issubset(set(cfg)):
            raise ValueError(
                f"Config {set(cfg)} cannot serve job {j}: "
                f"needs {tool_req[j]}"
            )
        if j in jobs_seen:
            raise ValueError(f"Job {j} appears more than once in route")
        jobs_seen.add(j)
    if jobs_seen != set(range(n_jobs)):
        raise ValueError(
            f"SSP route missing jobs: {set(range(n_jobs)) - jobs_seen}"
        )
    return True