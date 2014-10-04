#!/usr/bin/python3

import sys, os, subprocess

PRESQUEL_DIR = os.path.join('..', '..', '..', 'src')

def todir(*path):
    ret = os.path.join(*path)
    if not os.path.isdir(ret):
        os.makedirs(ret)
    return ret


def run_py(script, *args):
    cmd = [sys.executable, os.path.join(PRESQUEL_DIR, script)]
    cmd.extend(args)
    env = os.environ
    env['PYTHONPATH'] = PRESQUEL_DIR
    exe = subprocess.Popen(cmd, env = env, shell = False)
    exe.wait()
    return exe.returncode


def generate_sql():
    outdir = todir('.', 'exports', 'sql')
    run_py('genBaseSql.py', 'mysql', 'sql', outdir)



if __name__ == '__main__':
    generate_sql()