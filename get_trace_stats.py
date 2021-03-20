"""
Runs ramulator on specified trace files individually in order to gather basic miss/hit information beforehand
-> stats for each run are stored in BASE_STATS_DIR, where a trace file named 'trace_name' is saved as trace_name_stats.txt

Note: Expects trace files to not be in archives

Usage: python get_trace_stats.py [--existing]
"""
import subprocess #for running ramulator in shell
import sys
from os import listdir, makedirs
import argparse

if __name__ == '__main__':
    BASE_STATS_DIR = './base_stats'
    TRACE_DIR = './cputraces'
    INSTR_RECORD = 200000000 #the value of expected_limit_insts TODO: read this from trace file maybe?

    arg_parser = argparse.ArgumentParser(description=None)
    arg_parser.add_argument("--existing", action='store_true')
    args = arg_parser.parse_args()

    try:
        makedirs(BASE_STATS_DIR) #make the output directory if it isn't there
    except FileExistsError:
        print(f"Output directory {BASE_STATS_DIR} already exists, skipping creation")
    """1. Simulate all test files in ramulator"""
    trace_procs = []
    if(not args.existing): #pass --existing to skip the ramulator simulations and go straight to trace file processing

        # Start all the trace simulations
        for trace_name in listdir(TRACE_DIR):
            command = f"./ramulator configs/DDR3-config.cfg --mode=cpu --stats {BASE_STATS_DIR}/{trace_name}.txt cputraces/{trace_name}"
            print(command)
            trace_ram_p = subprocess.Popen(command.split(" "))
            trace_procs.append(trace_ram_p)
        
        # Wait for all the simulations to finish
        for trace_p in trace_procs:
            trace_p.wait()
    
    print("All simulations finished, starting processing")
    
    """2. Process stats in BASE_STATS_DIR, creating Pandas dataframe that is then displayed"""
    try:
        import pandas as pd
    except ImportError: #no pandas, can't do data processing 
        print("ERROR: No Pandas installation - run 'pip install pandas' if you want to process the trace files")
        exit(1)
    
    stat_names = ['ramulator.record_read_hits', 'ramulator.record_read_misses', 'ramulator.record_read_conflicts', 'ramulator.record_write_hits', 'ramulator.record_write_misses', 'ramulator.record_write_conflicts'] #stats we are interested in?
    trace_stats_files = [file_name for file_name in listdir(BASE_STATS_DIR) if ".txt" in file_name] #don't include .csv file from previous run
    trace_stat_names = [trace_stat.replace('.txt', '').split('.')[1] for trace_stat in trace_stats_files]
    trace_stat_dicts = [] #list of dictionaries, each one holding stats for a matching trace in trace_stats_files
    for trace_stat_f in trace_stats_files:
        trace_path = f"{BASE_STATS_DIR}/{trace_stat_f}"
        trace_stats_dict = {}
        for line in open(trace_path, 'r'):
            print(trace_path)
            stat_name, stat_val = line.split()[0], float(line.split()[1])
            #print(repr(stat_name))
            if(stat_name in stat_names): #if it's a stat we are interested in, save it (remove the ramulator part)
                field = stat_name.replace('ramulator.record_', '')
                trace_stats_dict[field] = stat_val
        trace_stat_dicts.append(trace_stats_dict)
    
    trace_stat_df = pd.DataFrame(trace_stat_dicts, index = trace_stat_names)
    trace_stat_df['total_misses'] = trace_stat_df['read_misses'] + trace_stat_df['write_misses']
    trace_stat_df['total_hits'] = trace_stat_df['read_hits'] + trace_stat_df['write_hits']
    trace_stat_df['total_conflicts'] = trace_stat_df['read_conflicts'] + trace_stat_df['write_conflicts']
    trace_stat_df['MPKI'] = trace_stat_df['total_misses']/((INSTR_RECORD)/1000)
    trace_stat_df['MPKI w/ Conflict'] = (trace_stat_df['total_misses'] + trace_stat_df['total_conflicts']) /((INSTR_RECORD)/1000)
    print(trace_stat_df.head(200))
    out_path = f"{BASE_STATS_DIR}/hit_stats.csv"
    print(f"Saving dataframe as CSV at {out_path}")
    trace_stat_df.to_csv(out_path)

