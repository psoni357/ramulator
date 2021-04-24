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
    BASE_STATS_DIR = './base_stats_8channel'
    TRACE_DIR = './cputraces_unpacked'
    INSTR_RECORD = 200000000 #the value of expected_limit_insts TODO: read this from trace file maybe?
    TEST_GROUPS = [['libquantum','leslie3d','milc','cactusADM'],
                   ['GemsFDTD','lbm','astar','milc'],
                   ['libquantum', 'leslie3d', 'milc', 'h264ref'],
                   ['libquantum', 'leslie3d', 'GemsFDTD', 'h264ref'],
                   ['wrf', 'gcc', 'lbm', 'libquantum'],
                   ['gcc', 'bzip2', 'astar', 'zeusmp'],
                   ['wrf', 'bzip2', 'gcc', 'astar'],
                   ['wrf', 'bzip2', 'gcc', 'zeusmp'],
                   ['libquantum','leslie3d','milc','cactusADM','GemsFDTD','lbm','astar','zeusmp'],
                   ['libquantum','leslie3d','milc','cactusADM','GemsFDTD','lbm','soplex','xalancbmk'],
                   ['libquantum','leslie3d','milc','cactusADM','wrf','bzip2','gcc','namd'],
                   ['GemsFDTD','lbm','astar','milc','wrf','bzip2','gcc','gobmk']
                    ]
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
            command = f"./ramulator configs/DDR3-config.cfg --mode=cpu --stats {BASE_STATS_DIR}/{trace_name}.txt {TRACE_DIR}/{trace_name}"
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
        import matplotlib.pyplot as plt
    except ImportError: #no pandas, can't do data processing 
        print("ERROR: No Pandas/matplotlib installation - run 'pip install pandas' and 'pip install matplotlib' if you want to process the trace files")
        exit(1)
    
    stat_names = ['ramulator.record_insts_core_0', 'ramulator.record_cycs_core_0', 'ramulator.L3_cache_read_miss', 'ramulator.L3_cache_write_miss', 'ramulator.L3_cache_total_miss'] #stats we are interested in?
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
                field = stat_name.replace('ramulator.', '').replace('record_', '')
                trace_stats_dict[field] = stat_val
        
        trace_stat_dicts.append(trace_stats_dict)
    
    trace_stat_df = pd.DataFrame(trace_stat_dicts, index = trace_stat_names)
    #trace_stat_df['total_misses'] = trace_stat_df['read_misses'] + trace_stat_df['write_misses']
    #trace_stat_df['total_hits'] = trace_stat_df['read_hits'] + trace_stat_df['write_hits']
    #trace_stat_df['total_conflicts'] = trace_stat_df['read_conflicts'] + trace_stat_df['write_conflicts']
    trace_stat_df['MPKI'] = trace_stat_df['L3_cache_total_miss']/((INSTR_RECORD)/1000)
    trace_stat_df['IPC'] = trace_stat_df['insts_core_0']/trace_stat_df['cycs_core_0']
    #trace_stat_df['MPKI w/ Conflict'] = (trace_stat_df['total_misses'] + trace_stat_df['total_conflicts']) /((INSTR_RECORD)/1000)
    trace_stat_df.index = trace_stat_df.index.rename("app")
    print("Individual App Statistics")
    print(trace_stat_df.head(200))

    #plot output MPKI
    trace_stat_df[['MPKI']].sort_index(key = lambda v : v.str.lower()).plot.bar()

    plt.xticks(rotation='vertical')
    plt.savefig(f"{BASE_STATS_DIR}/MPKI_plot.png", dpi = 400, bbox_inches='tight')

    #plot output IPC
    trace_stat_df[['IPC']].sort_index(key = lambda v : v.str.lower()).plot.bar()
    plt.xticks(rotation='vertical')
    plt.savefig(f"{BASE_STATS_DIR}/IPC_plot.png", dpi = 400, bbox_inches='tight')

    #save entire dataframe as CSV
    out_path = f"{BASE_STATS_DIR}/hit_stats_individual.csv"
    print(f"Saving individual app data dataframe as CSV at {out_path}")
    trace_stat_df.to_csv(out_path)
    trace_stat_groups_strs = [" | ".join(group) for group in TEST_GROUPS]
    trace_stat_group_dict = {}
    for group_num, group_apps in enumerate(TEST_GROUPS):
        group_str = trace_stat_groups_strs[group_num]
        trace_stat_group_dict[group_str] = []
        for group_app in group_apps:
            trace_stat_group_dict[group_str].append(float(trace_stat_df[trace_stat_df.index == group_app]['IPC']))
    
    trace_stat_group_df = pd.DataFrame.from_dict(trace_stat_group_dict, orient='index')
    core_names_map ={num:f"Core {num}" for num in trace_stat_group_df.columns}
    trace_stat_group_df = trace_stat_group_df.rename(columns=core_names_map)
    print("IPC Statistics by test group")
    print(trace_stat_group_df.head(2000))
    out_path = f"{BASE_STATS_DIR}/hit_stats_groups.csv"
    print(f"Saving test group statistics as CSV at {out_path}")
    trace_stat_group_df.to_csv(out_path)
