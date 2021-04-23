"""
Extracts all the .gz archives in INPUT_DIR to OUTPUT_DIR using gunzip. The original archives are unmodified
Note: Tries to extract everything in INPUT_DIR, with gunzip handling any invalid .gz archives. 
"""
import subprocess
from os import listdir, makedirs
INPUT_DIR = './cputraces'
OUTPUT_DIR = './cputraces_unpacked'
try:
    makedirs(OUTPUT_DIR) #make the output directory if it isn't there
except FileExistsError:
    print(f"Output directory {OUTPUT_DIR} already exists, skipping creation")
    
for packed_name in listdir(INPUT_DIR):
    command = f'gunzip -dkc {INPUT_DIR}/{packed_name}'
    
    unpacked_name = packed_name.replace('.gz', '')
    print(command)
    with open(f"{OUTPUT_DIR}/{unpacked_name}", "w") as out_fp:
        subprocess.run(command.split(' '), stdout=out_fp)