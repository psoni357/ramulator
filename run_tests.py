"""
Runs ramulator with specified groups of trace files

Note: Expects trace files to not be in archives

Usage: python run_tests.py [--existing] [--scheduler scheduler]
"""
import subprocess #for running ramulator in shell
import sys
from os import listdir, makedirs, path
import argparse
from collections import defaultdict
import pprint
import glob
if __name__ == '__main__':
    STATS_DIR = './test_stats'
    TRACE_DIR = './cputraces_unpacked'
    INSTR_RECORD = 200000000 #the value of expected_limit_insts TODO: read this from trace file maybe?
    GROUP_SIZE = 8
    TEST_GROUPS_4_CORE = [
                   ['libquantum','leslie3d','milc','cactusADM'],
                   ['GemsFDTD','lbm','astar','milc'],
                   ['libquantum', 'leslie3d', 'milc', 'h264ref'],
                   ['libquantum', 'leslie3d', 'GemsFDTD', 'h264ref'],
                   ['wrf', 'gcc', 'lbm', 'libquantum'],
                   ['gcc', 'bzip2', 'astar', 'zeusmp'],
                   ['wrf', 'bzip2', 'gcc', 'astar'],
                   ['wrf', 'bzip2', 'gcc', 'zeusmp']
                ]
    TEST_GROUPS_8_CORE = [
                   ['libquantum','leslie3d','milc','cactusADM','GemsFDTD','lbm','astar','zeusmp'],
                   ['libquantum','leslie3d','milc','cactusADM','GemsFDTD','lbm','soplex','xalancbmk'],
                   ['libquantum','leslie3d','milc','cactusADM','wrf','bzip2','gcc','namd'],
                   ['GemsFDTD','lbm','astar','milc','wrf','bzip2','gcc','gobmk']
                   ]
    TEST_GROUPS = []
    TEST_GROUPS.extend(TEST_GROUPS_4_CORE)
    TEST_GROUPS.extend(TEST_GROUPS_8_CORE)

    arg_parser = argparse.ArgumentParser(description=None)
    arg_parser.add_argument("--existing", action='store_true', help= "don't run new tests, process old ones in STATS_DIR instead") #
    arg_parser.add_argument("--scheduler", type=str, help = "for appending to trace statistics name") 
    arg_parser.add_argument("--pivot", action='store_true', help = "output a dataframe omitting specific test applications, only showing policy, test number, and core IPC values")    
    arg_parser.add_argument("--recursive", action='store_true', help = "go through all directories in STATS_DIR when looking for traces DOES NOT REALLY WORK SO LONG AS TRACE FILES START WITH SAME POLICY NAME") #
    arg_parser.add_argument("--only_8_core", action='store_true', help = "only run the tests in TEST_GROUPS_8_CORE") #
    arg_parser.add_argument("--only_4_core", action='store_true', help = "only run the tests in TEST_GROUPS_4_CORE")
    args = arg_parser.parse_args()

    if(args.only_8_core):
        blacklisted_tests = [num for num in range(len(TEST_GROUPS_4_CORE))]
    elif(args.only_4_core):
        blacklisted_tests = [num for num in range(len(TEST_GROUPS_4_CORE), len(TEST_GROUPS))]
    else:
        blacklisted_tests = []
    print(f"Skipping tests {blacklisted_tests}!!")
    try:
        makedirs(STATS_DIR) #make the output directory if it isn't there
    except FileExistsError:
        print(f"Output directory {STATS_DIR} already exists, skipping creation")
    """1. Simulate all test files in ramulator"""
    trace_procs = []
    if(not args.existing): #pass --existing to skip the ramulator simulations and go straight to trace file processing
        # Match Trace filename and tracenames
        trace_file_dict = {}
        for trace_file_name in listdir(TRACE_DIR):
            real_name = trace_file_name.split('.')[1]
            trace_file_dict[real_name] = trace_file_name
        # Start all the trace simulations
        for test_num, test_group in enumerate(TEST_GROUPS):# limiting test sets here
            if(test_num in blacklisted_tests): 
                continue
            traces_str = ' '.join([f'{TRACE_DIR}/{trace_file_dict[test]}' for test in test_group])
            test_str = '_'.join([f'{test}' for test in test_group])
            if(args.scheduler): 
                test_str = f'{args.scheduler}_{test_num}_{test_str}'    #output stats format is test_num_{listOfTraces}_{scheduler}.txt
            else:
                test_str = f'NONE_{test_num}_{test_str}'                #output statsformat is test_num_{listOfTraces}.txt
            command = f"./ramulator configs/DDR3-config.cfg --mode=cpu --stats {STATS_DIR}/{test_str}.txt {traces_str}"
            print(command)
            trace_ram_p = subprocess.Popen(command.split(" "))
            trace_procs.append(trace_ram_p)
        # Wait for all the simulations to finish
        for trace_p in trace_procs:
            trace_p.wait()
    
        print("All simulations finished")
    print("Starting Processing")
    """2. Process stats in STATS_DIR, creating Pandas dataframe that is then displayed"""
    def get_stat_file_dict(stat_filename):
        # Given a stat file name in format SCHEDULER_NUM_{listOfTests}.txt, output a dict with:
        stats = stat_filename.split('_')
        # scheduler: scheduler, test_num: test_num, apps = [list of tests in this group]
        stat_file_dict = { 'scheduler': stats[0],
                           'test_num' : stats[1],
                           'apps' : stats[2::],
                           'raw_results': {}, #stat_name : val
                           'apps_results': defaultdict(dict) #app_name : {}, where {} is stat_name : val
                        }
        return stat_file_dict
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        pd.set_option("display.max_rows", None, "display.max_columns", None) #let pandas print all rows/columns of dfs
    except ImportError: #no pandas, can't do data processing 
        print("ERROR: No Pandas/matplotlib installation - run 'pip install pandas' and 'pip install matplotlib' if you want to process the trace files")
        exit(1)
    base_stat_names = ['ramulator.record_insts_core', 'ramulator.record_cycs_core'] #stats we are interested in
    stat_names = [ f'{base_stat_name}_{group_num}' for group_num in range(GROUP_SIZE) for base_stat_name in base_stat_names] #make copies of stats, appending core #s
    #trace_stats_files = sorted([file_name for file_name in listdir(STATS_DIR) if ".txt" in file_name and path.getsize(f"{STATS_DIR}/{file_name}") != 0]) #don't include .csv file from previous run
    if(not args.recursive):
        trace_stats_files = glob.glob(f"{STATS_DIR}/*.txt")
    else: 
        trace_stats_files = glob.glob(f"{STATS_DIR}/**/*.txt", recursive=True)
    if(len(trace_stats_files) == 0):
        print(f"ERROR: No trace stats found in {STATS_DIR} with --recursive set to {args.recursive}")
        exit(1)
    trace_stats_files = [file_path for file_path in trace_stats_files if path.getsize(file_path) != 0] #remove empty traces
    if(len(trace_stats_files) == 0):
        print(f"ERROR: All traces found in {STATS_DIR} with were empty with --recursive set to {args.recursive}")
        exit(1)
    pprint.pprint(trace_stats_files)
    #trace_stat_names = [trace_stat.replace('.txt', '').split('_')[1] for trace_stat in trace_stats_files]
    trace_stat_dicts = [] #list of dictionaries, each one holding stats for a matching trace in trace_stats_files
    for trace_path in trace_stats_files:
        trace_stat_f = path.basename(trace_path)
        trace_stats_dict = get_stat_file_dict(trace_stat_f)
        for line in open(trace_path, 'r'):
            stat_name, stat_val = line.split()[0], float(line.split()[1])
            #print(repr(stat_name))
            if(stat_name in stat_names): #if it's a stat we are interested in, save it (remove the ramulator part)
                field = stat_name.replace('ramulator.', '').replace('record_', '')
                trace_stats_dict['raw_results'][field] = stat_val
        trace_stat_dicts.append(trace_stats_dict)
    #
    for stat_dict in trace_stat_dicts:
        for stat_name, stat_val in stat_dict['raw_results'].items():
            coreid = int(stat_name.split('_')[2])
            app = stat_dict['apps'][coreid]
            stat_name_no_num = '_'.join(stat_name.split('_')[:-1])
            stat_dict['apps_results'][app]["scheduler"] = stat_dict['scheduler']
            stat_dict['apps_results'][app]["core"] = f"Core {coreid}"
            stat_dict['apps_results'][app][stat_name_no_num] = stat_val
            
            stat_dict['apps_results'][app]["test_num"] = stat_dict['test_num']
            
    #schedulers = [(stat_dict['scheduler']) for stat_dict in trace_stat_dicts]
    trace_stat_dfs = [pd.DataFrame(stat_dict['apps_results']).transpose() for stat_dict in trace_stat_dicts]
    for trace_stat_df in trace_stat_dfs:
        trace_stat_df['IPC'] = trace_stat_df['insts_core']/trace_stat_df['cycs_core']
    trace_stat_df = pd.concat(trace_stat_dfs)
    if(args.pivot):
        #trace_stat_df
        #trace_stat_df = trace_stat_df[['IPC']]
        #print(trace_stat_df.head(20))
        #trace_stat_df = trace_stat_df.unstack(level = 1)
        #trace_stat_df = trace_stat_df.drop(['cycs_core', 'insts_core'], axis=1)
        trace_stat_df = trace_stat_df.pivot(index=['scheduler','test_num'], columns = ['core'], values=['IPC'])
        
        #trace_stat_df = trace_stat_df.unstack(level=["Policy"])
    print(trace_stat_df.head(200))
    """
    #plot output IPC
    trace_stat_df[['IPC']].sort_index(key = lambda v : v.str.lower()).plot.bar()
    plt.xticks(rotation='vertical')
    plt.savefig(f"{STATS_DIR}/IPC_plot.png", dpi = 400, bbox_inches='tight')
    """

    #save entire dataframe as CSV
    out_path = f"{STATS_DIR}/test_stats.csv"
    print(f"Saving dataframe as CSV at {out_path}")
    trace_stat_df.to_csv(out_path)

