"""
SSP Instance Generator - Utility Script

This script provides command-line utilities for generating SSP instances
and batch generation of the Crama et al. (1994) test suite.

Usage:
    python ssp_generate_instances.py --help
    python ssp_generate_instances.py --single -M 10 -N 10 -C 5 --min-tools 2 --max-tools 4
    python ssp_generate_instances.py --crama --output-dir ./instances
"""

import argparse
import os
import json
import numpy as np
from pathlib import Path
from ssp_instance_generator import SSPInstanceGenerator


def generate_single_instance(M: int, N: int, C: int, min_tools: int, 
                           max_tools: int, output_dir: str = None, seed: int = None):
    """Generate a single Crama-style instance and optionally save it."""
    generator = SSPInstanceGenerator(seed=seed)
    A, metadata = generator.generate_instance(M, N, C, min_tools, max_tools)
    
    print(f"\nGenerated instance:")
    print(f"  Tools: {metadata['M']} (original) → {metadata['M_after_filtering']} (after filtering)")
    print(f"  Jobs: {metadata['N']}")
    print(f"  Capacity: {metadata['C']}")
    print(f"  Tools per job: [{metadata['min_tools']}, {metadata['max_tools']}]")
    print(f"  Matrix shape: {A.shape}")
    print(f"\nMatrix (first 5 rows, all columns):")
    print(A[:min(5, A.shape[0]), :])
    
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        filename = os.path.join(output_dir, 
                               f"ssp_M{metadata['M']}_N{metadata['N']}_C{metadata['C']}.txt")
        generator.save_instance(A, metadata, filename)
        print(f"\nInstance saved to: {filename}")
    
    return A, metadata

def generate_small_overlap_suite(output_dir: str = "./ssp_small_overlap",
                                 num_instances: int = 10,
                                 max_total_size: int = 50,
                                 min_tools: int = 2,
                                 max_tools: int = None,
                                 C: int = None,
                                 seed: int = None):
    """Generate a set of small high-overlap Laporte-style instances."""
    os.makedirs(output_dir, exist_ok=True)
    generator = SSPInstanceGenerator(seed=seed)
    instances = generator.generate_small_overlap_instances(
        num_instances=num_instances,
        max_total_size=max_total_size,
        min_tools=min_tools,
        max_tools=max_tools,
        C=C
    )

    for meta_idx, (A, metadata) in enumerate(instances, 1):
        filename = os.path.join(output_dir, f"small_overlap_instance_{meta_idx:02d}.txt")
        generator.save_instance(A, metadata, filename)
        meta_filename = os.path.join(output_dir, f"small_overlap_instance_{meta_idx:02d}_metadata.json")
        with open(meta_filename, 'w') as f:
            meta_copy = metadata.copy()
            meta_copy['tool_sets'] = [list(ts) for ts in meta_copy['tool_sets']]
            json.dump(meta_copy, f, indent=2)

    print(f"\nSaved {len(instances)} small high-overlap instances to: {output_dir}")
    return instances


def generate_crama_suite(output_dir: str = "./ssp_instances", 
                        num_per_type: int = 10, seed: int = None):
    """Generate the full Crama et al. (1994) test suite."""
    os.makedirs(output_dir, exist_ok=True)
    
    generator = SSPInstanceGenerator(seed=seed)
    instance_types = SSPInstanceGenerator.get_crama_instance_types()
    
    print(f"\nGenerating Crama et al. (1994) test suite...")
    print(f"  Instance types: {len(instance_types)}")
    print(f"  Instances per type: {num_per_type}")
    print(f"  Total instances: {len(instance_types) * num_per_type}")
    print(f"  Output directory: {output_dir}\n")
    
    all_instances = []
    instance_count = 0
    
    for type_idx, (M, N, C, min_t, max_t) in enumerate(instance_types, 1):
        print(f"Type {type_idx:2d}/{len(instance_types)}: "
              f"M={M:2d}, N={N:2d}, C={C:2d}, min={min_t:2d}, max={max_t:2d} ...", end="")
        
        type_dir = os.path.join(output_dir, f"type_{type_idx:02d}_M{M}_N{N}_C{C}")
        os.makedirs(type_dir, exist_ok=True)
        
        for inst_idx in range(num_per_type):
            A, metadata = generator.generate_instance(M, N, C, min_t, max_t)
            metadata['type_index'] = type_idx
            metadata['instance_index'] = inst_idx + 1
            
            # Save matrix
            filename = os.path.join(type_dir, f"instance_{inst_idx+1:02d}.txt")
            generator.save_instance(A, metadata, filename)
            
            # Save metadata as JSON
            meta_filename = os.path.join(type_dir, f"instance_{inst_idx+1:02d}_metadata.json")
            with open(meta_filename, 'w') as f:
                # Convert non-serializable objects to serializable
                meta_copy = metadata.copy()
                meta_copy['tool_sets'] = [list(ts) for ts in meta_copy['tool_sets']]
                json.dump(meta_copy, f, indent=2)
            
            all_instances.append((A, metadata))
            instance_count += 1
        
        print(f" {num_per_type} instances")
    
    # Save summary
    summary_path = os.path.join(output_dir, "SUMMARY.txt")
    with open(summary_path, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("Job Sequencing and Tool Switching Problem (SSP)\n")
        f.write("Crama et al. (1994) Test Suite\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Total instances generated: {instance_count}\n")
        f.write(f"Instance types: {len(instance_types)}\n")
        f.write(f"Instances per type: {num_per_type}\n\n")
        f.write("Instance types (M, N, C, min_tools, max_tools):\n")
        for i, (M, N, C, min_t, max_t) in enumerate(instance_types, 1):
            f.write(f"  {i:2d}. ({M:2d}, {N:2d}, {C:2d}, {min_t:2d}, {max_t:2d})\n")
        f.write("\n" + "=" * 80 + "\n")
        f.write("References:\n")
        f.write("1. Crama, Y., Kolen, A.W.J., Oerlemans, A.G., & Spieksma, F.C.R. (1994)\n")
        f.write("   'Minimizing the Number of Tool Switches on a Flexible Machine'\n")
        f.write("   The International Journal of Flexible Manufacturing Systems, 6, 33-54.\n")
        f.write("\n2. Laporte, G., Salazar-González, J.J., & Semet, F. (2004)\n")
        f.write("   'Exact algorithms for the job sequencing and tool switching problem'\n")
        f.write("   IIE Transactions, 36:1, 37-45.\n")
    
    print(f"\nSummary saved to: {summary_path}")
    print(f"\nAll instances generated successfully!")
    
    return all_instances


def analyze_instance(filename: str):
    """Analyze and display statistics for an instance."""
    A, metadata = SSPInstanceGenerator.load_instance(filename)
    
    print(f"\n" + "=" * 70)
    print(f"Instance Analysis: {filename}")
    print("=" * 70)
    
    print(f"\nParameters:")
    print(f"  Number of tools (M): {metadata['M']}")
    print(f"  Number of jobs (N): {metadata['N']}")
    print(f"  Magazine capacity (C): {metadata['C']}")
    print(f"  Tools per job range: [{metadata['min_tools']}, {metadata['max_tools']}]")
    
    print(f"\nMatrix Statistics:")
    print(f"  Matrix shape: {A.shape}")
    print(f"  Sparsity: {1 - np.count_nonzero(A) / A.size:.2%}")
    
    # Tools per job
    tools_per_job = np.sum(A, axis=0)
    print(f"\n  Tools per job:")
    print(f"    Min: {np.min(tools_per_job)}")
    print(f"    Max: {np.max(tools_per_job)}")
    print(f"    Mean: {np.mean(tools_per_job):.2f}")
    print(f"    Std: {np.std(tools_per_job):.2f}")
    
    # Jobs per tool
    jobs_per_tool = np.sum(A, axis=1)
    print(f"\n  Jobs per tool:")
    print(f"    Min: {np.min(jobs_per_tool)}")
    print(f"    Max: {np.max(jobs_per_tool)}")
    print(f"    Mean: {np.mean(jobs_per_tool):.2f}")
    print(f"    Std: {np.std(jobs_per_tool):.2f}")
    
    print(f"\nMatrix (first 10x10 block):")
    print(A[:min(10, A.shape[0]), :min(10, A.shape[1])])
    
    print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Job Sequencing and Tool Switching Problem (SSP) - Instance Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a single instance
  python ssp_generate_instances.py --single -M 10 -N 10 -C 5 --min-tools 2 --max-tools 4
  
  # Generate full Crama et al. (1994) test suite
  python ssp_generate_instances.py --crama --output-dir ./ssp_instances --num-per-type 10
  
  # Analyze an instance
  python ssp_generate_instances.py --analyze ./ssp_instances/type_01_M10_N10_C4/instance_01.txt

References:
  1. Crama et al. (1994) - Minimizing the Number of Tool Switches on a Flexible Machine
  2. Laporte et al. (2004) - Exact algorithms for the job sequencing and tool switching problem
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Single instance generation
    single_parser = subparsers.add_parser('single', help='Generate a single instance')
    single_parser.add_argument('-M', type=int, required=True, help='Number of tools')
    single_parser.add_argument('-N', type=int, required=True, help='Number of jobs')
    single_parser.add_argument('-C', type=int, required=True, help='Magazine capacity')
    single_parser.add_argument('--min-tools', type=int, required=True, 
                             help='Minimum tools per job')
    single_parser.add_argument('--max-tools', type=int, required=True, 
                             help='Maximum tools per job')
    single_parser.add_argument('--output-dir', type=str, default=None,
                             help='Output directory for saving instance')
    single_parser.add_argument('--seed', type=int, default=None,
                             help='Random seed for reproducibility')
    
    # Crama test suite generation
    crama_parser = subparsers.add_parser('crama', 
                                        help='Generate Crama et al. (1994) test suite')
    crama_parser.add_argument('--output-dir', type=str, default='./ssp_instances',
                            help='Output directory')
    crama_parser.add_argument('--num-per-type', type=int, default=10,
                            help='Number of instances per type')
    crama_parser.add_argument('--seed', type=int, default=None,
                            help='Random seed for reproducibility')

    # Overlapping instance generation
    overlapping_parser = subparsers.add_parser('overlapping', help='Generate a high-overlap SSP instance')
    overlapping_parser.add_argument('-M', type=int, required=True, help='Number of tools')
    overlapping_parser.add_argument('-N', type=int, required=True, help='Number of jobs')
    overlapping_parser.add_argument('-C', type=int, required=True, help='Magazine capacity')
    overlapping_parser.add_argument('--min-tools', type=int, required=True, 
                               help='Minimum tools per job')
    overlapping_parser.add_argument('--max-tools', type=int, required=True, 
                               help='Maximum tools per job')
    overlapping_parser.add_argument('--overlap-factor', type=float, default=0.75,
                               help='Overlap factor for shared tools across jobs')
    overlapping_parser.add_argument('--output-dir', type=str, default=None,
                               help='Output directory for saving instance')
    overlapping_parser.add_argument('--seed', type=int, default=None,
                               help='Random seed for reproducibility')

    # Small overlap instance generation
    small_parser = subparsers.add_parser('small', help='Generate a small high-overlap test set')
    small_parser.add_argument('--output-dir', type=str, default='./ssp_small_overlap',
                              help='Output directory')
    small_parser.add_argument('--num-instances', type=int, default=10,
                              help='Number of small instances to generate')
    small_parser.add_argument('--max-total-size', type=int, default=50,
                              help='Maximum product of tools and jobs (M*N)')
    small_parser.add_argument('--min-tools', type=int, default=2,
                              help='Minimum tools per job')
    small_parser.add_argument('--max-tools', type=int, default=None,
                              help='Maximum tools per job')
    small_parser.add_argument('--capacity', type=int, default=None,
                              help='Optional fixed capacity for all small instances')
    small_parser.add_argument('--seed', type=int, default=None,
                              help='Random seed for reproducibility')

    # Instance analysis
    analyze_parser = subparsers.add_parser('analyze', help='Analyze an instance')
    analyze_parser.add_argument('filename', type=str, help='Instance file to analyze')
    
    args = parser.parse_args()
    
    if args.command == 'single':
        generate_single_instance(
            M=args.M,
            N=args.N,
            C=args.C,
            min_tools=args.min_tools,
            max_tools=args.max_tools,
            output_dir=args.output_dir,
            seed=args.seed
        )
    elif args.command == 'crama':
        generate_crama_suite(
            output_dir=args.output_dir,
            num_per_type=args.num_per_type,
            seed=args.seed
        )
    elif args.command == 'small':
        generate_small_overlap_suite(
            output_dir=args.output_dir,
            num_instances=args.num_instances,
            max_total_size=args.max_total_size,
            min_tools=args.min_tools,
            max_tools=args.max_tools,
            C=args.capacity,
            seed=args.seed
        )
    elif args.command == 'analyze':
        analyze_instance(args.filename)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
