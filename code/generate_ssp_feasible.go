package main

import (
	"bufio"
	"encoding/csv"
	"fmt"
	"os"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
)

// ─── Data Types ───────────────────────────────────────────────────────────────

// Solution mirrors one row of the Python DataFrame output.
type Solution struct {
	ID      int64
	JobSeq  []int
	Configs [][]int
	Cost    int
}

// ─── I/O ──────────────────────────────────────────────────────────────────────

// loadSSPInstance reads the standard SSP text format:
//
//	First line (or tokens):  J  T  C
//	Then a T × J binary incidence matrix (row-major).
//
// Returns J, T, b (capacity), and Tj[j] = list of tools required by job j.
func loadSSPInstance(path string) (J, T, b int, Tj [][]int, err error) {
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()

	var tokens []int
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		for _, tok := range strings.Fields(sc.Text()) {
			v, e := strconv.Atoi(tok)
			if e != nil {
				err = fmt.Errorf("non-integer token %q: %w", tok, e)
				return
			}
			tokens = append(tokens, v)
		}
	}
	if sc.Err() != nil {
		err = sc.Err()
		return
	}
	if len(tokens) < 3 {
		err = fmt.Errorf("file too short")
		return
	}

	J, T, b = tokens[0], tokens[1], tokens[2]
	need := 3 + T*J
	if len(tokens) < need {
		err = fmt.Errorf("expected %d tokens, got %d", need, len(tokens))
		return
	}

	// A[t][j] = tokens[3 + t*J + j]
	Tj = make([][]int, J)
	for j := 0; j < J; j++ {
		for t := 0; t < T; t++ {
			if tokens[3+t*J+j] == 1 {
				Tj[j] = append(Tj[j], t)
			}
		}
	}
	return
}

// ─── Combinatorics ────────────────────────────────────────────────────────────

// combinations returns all C(n,k) subsets of {0..n-1} in lexicographic order,
// each as a sorted []int of length k.
func combinations(n, k int) [][]int {
	if k > n || k < 0 {
		return nil
	}
	result := make([][]int, 0, binomial(n, k))
	buf := make([]int, k)
	var rec func(start, depth int)
	rec = func(start, depth int) {
		if depth == k {
			tmp := make([]int, k)
			copy(tmp, buf)
			result = append(result, tmp)
			return
		}
		for i := start; i <= n-k+depth; i++ {
			buf[depth] = i
			rec(i+1, depth+1)
		}
	}
	rec(0, 0)
	return result
}

// binomial computes C(n, k) for small n.
func binomial(n, k int) int {
	if k > n {
		return 0
	}
	if k == 0 || k == n {
		return 1
	}
	if k > n-k {
		k = n - k
	}
	result := 1
	for i := 0; i < k; i++ {
		result = result * (n - i) / (i + 1)
	}
	return result
}

// permutations generates all J! permutations of {0..n-1} via Heap's algorithm.
func permutations(n int) [][]int {
	total := factorial(n)
	result := make([][]int, 0, total)
	perm := make([]int, n)
	for i := range perm {
		perm[i] = i
	}
	c := make([]int, n)

	tmp := make([]int, n)
	copy(tmp, perm)
	result = append(result, tmp)

	i := 0
	for i < n {
		if c[i] < i {
			if i%2 == 0 {
				perm[0], perm[i] = perm[i], perm[0]
			} else {
				perm[c[i]], perm[i] = perm[i], perm[c[i]]
			}
			tmp = make([]int, n)
			copy(tmp, perm)
			result = append(result, tmp)
			c[i]++
			i = 0
		} else {
			c[i] = 0
			i++
		}
	}
	return result
}

func factorial(n int) int {
	r := 1
	for i := 2; i <= n; i++ {
		r *= i
	}
	return r
}

// ─── SSP Core ─────────────────────────────────────────────────────────────────

// switchCost returns cap - |cfgA ∩ cfgB|, i.e. the number of tool swaps needed.
// Both slices are assumed sorted (as produced by combinations()).
func switchCost(cfgA, cfgB []int, cap int) int {
	inter := 0
	i, j := 0, 0
	for i < len(cfgA) && j < len(cfgB) {
		switch {
		case cfgA[i] == cfgB[j]:
			inter++
			i++
			j++
		case cfgA[i] < cfgB[j]:
			i++
		default:
			j++
		}
	}
	return cap - inter
}

// computeCost sums the switch costs along a config sequence.
func computeCost(configs [][]int, cap int) int {
	cost := 0
	for i := 1; i < len(configs); i++ {
		cost += switchCost(configs[i-1], configs[i], cap)
	}
	return cost
}

// buildHj returns Hj[j] = sorted list of config indices (into allConfigs)
// that are feasible for job j (i.e. contain all tools in Tj[j]).
func buildHj(J int, Tj [][]int, allConfigs [][]int) [][]int {
	Hj := make([][]int, J)
	for idx, cfg := range allConfigs {
		cfgSet := make(map[int]bool, len(cfg))
		for _, t := range cfg {
			cfgSet[t] = true
		}
		for j := 0; j < J; j++ {
			ok := true
			for _, t := range Tj[j] {
				if !cfgSet[t] {
					ok = false
					break
				}
			}
			if ok {
				Hj[j] = append(Hj[j], idx)
			}
		}
	}
	return Hj
}

// ─── CSV Writer ───────────────────────────────────────────────────────────────

// formatIntSlice formats []int as "[a b c]" to match Python's array repr.
func formatIntSlice(s []int) string {
	parts := make([]string, len(s))
	for i, v := range s {
		parts[i] = strconv.Itoa(v)
	}
	return "[" + strings.Join(parts, " ") + "];"
}

// formatConfigSeq formats [][]int as "[[a b] [c d] ...]".
func formatConfigSeq(configs [][]int) string {
	parts := make([]string, len(configs))
	for i, cfg := range configs {
		parts[i] = formatIntSlice(cfg)
	}
	return "[" + strings.Join(parts, " ") + "]"
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	filepath := "./shankar-example.txt"
	if len(os.Args) > 1 {
		filepath = os.Args[1]
	}

	// ── Load instance ──
	J, numTools, b, Tj, err := loadSSPInstance(filepath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading instance: %v\n", err)
		os.Exit(1)
	}
	fmt.Printf("Instance loaded: %s\n", filepath)
	fmt.Printf("  Jobs=%d, Tools=%d, Capacity=%d\n", J, numTools, b)

	// ── Generate all tool configs (combinations) ──
	allConfigs := combinations(numTools, b)
	fmt.Printf("  Config space size: C(%d,%d) = %d\n", numTools, b, len(allConfigs))

	// ── For each job, find feasible config indices ──
	Hj := buildHj(J, Tj, allConfigs)

	// ── Generate all job sequences (permutations) ──
	allJobSeqs := permutations(J)
	fmt.Printf("Number of job sequences: %d\n", len(allJobSeqs))

	// ── Open CSV output ──
	outFile, err := os.Create("ssp_feasible_solutions.csv")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error creating output file: %v\n", err)
		os.Exit(1)
	}
	defer outFile.Close()
	bw := bufio.NewWriterSize(outFile, 1<<20) // 1 MB write buffer
	csvWriter := csv.NewWriter(bw)
	if err := csvWriter.Write([]string{"#", "Job Sequence", "Configurations", "SSP Cost"}); err != nil {
		fmt.Fprintf(os.Stderr, "Error writing CSV header: %v\n", err)
		os.Exit(1)
	}

	// ── Parallel enumeration ──────────────────────────────────────────────────
	//
	// Architecture:
	//   • A fixed-size pool of worker goroutines pulls job sequences from a
	//     channel.  Each worker iterates over ALL config sequences for that job
	//     sequence (Cartesian product of Hj[jobSeq[i]]) locally, then sends
	//     completed Solution batches to a single writer goroutine.
	//
	//   • A single writer goroutine serialises all output to the CSV so no
	//     mutex is needed on the file handle.
	//
	//   • Row IDs are assigned via an atomic counter so they remain unique
	//     (but may not be globally sorted – consistent with parallelism).
	// ─────────────────────────────────────────────────────────────────────────

	numWorkers := runtime.NumCPU()
	fmt.Printf("Spawning %d worker goroutines …\n", numWorkers)

	type Batch []Solution

	seqCh := make(chan []int, numWorkers*4)    // job sequences → workers
	resCh := make(chan Batch, numWorkers*8)    // batches of solutions → writer
	var rowID atomic.Int64
	var wg sync.WaitGroup

	// Writer goroutine
	writerDone := make(chan struct{})
	go func() {
		defer close(writerDone)
		for batch := range resCh {
			for _, sol := range batch {
				row := []string{
					strconv.FormatInt(sol.ID, 10),
					formatIntSlice(sol.JobSeq),
					formatConfigSeq(sol.Configs),
					strconv.Itoa(sol.Cost),
				}
				if err := csvWriter.Write(row); err != nil {
					fmt.Fprintf(os.Stderr, "CSV write error: %v\n", err)
				}
			}
		}
		csvWriter.Flush()
	}()

	// Worker goroutines
	for w := 0; w < numWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			const batchSize = 256
			var batch Batch

			for jobSeq := range seqCh {
				n := len(jobSeq)

				// sizes[i] = number of feasible configs for jobSeq[i]
				sizes := make([]int, n)
				for i, job := range jobSeq {
					sizes[i] = len(Hj[job])
				}

				// Skip job sequences with no feasible assignment for any job
				feasible := true
				for _, s := range sizes {
					if s == 0 {
						feasible = false
						break
					}
				}
				if !feasible {
					continue
				}

				// Iterate over Cartesian product Hj[jobSeq[0]] × … × Hj[jobSeq[n-1]]
				// using a mixed-radix counter.
				indices := make([]int, n)
				for {
					// Build config sequence for current index tuple
					configs := make([][]int, n)
					for i, job := range jobSeq {
						configs[i] = allConfigs[Hj[job][indices[i]]]
					}
					cost := computeCost(configs, b)
					id := rowID.Add(1)

					batch = append(batch, Solution{
						ID:      id,
						JobSeq:  jobSeq, // safe: seqCh elements are unique slices
						Configs: configs,
						Cost:    cost,
					})

					// Flush batch to writer when full
					if len(batch) >= batchSize {
						resCh <- batch
						batch = make(Batch, 0, batchSize)
					}

					// Increment mixed-radix counter from the right
					carry := true
					for i := n - 1; i >= 0 && carry; i-- {
						indices[i]++
						if indices[i] >= sizes[i] {
							indices[i] = 0
						} else {
							carry = false
						}
					}
					if carry {
						break // all Cartesian-product combinations exhausted
					}
				}

				// Flush remaining partial batch
				if len(batch) > 0 {
					resCh <- batch
					batch = batch[:0]
				}
			}
		}()
	}

	// Feed all job sequences into the channel, then signal workers to stop
	for _, seq := range allJobSeqs {
		seqCh <- seq
	}
	close(seqCh)

	wg.Wait()        // wait for all workers to finish
	close(resCh)     // signal writer that no more batches are coming
	<-writerDone     // wait for writer to flush

	fmt.Printf("Number of feasible solutions: %d\n", rowID.Load())
	fmt.Println("Results saved to ssp_feasible_solutions.csv")
}