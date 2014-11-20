#!/usr/bin/python3

import sys, os, subprocess, distutils.dir_util, shutil

PRESQUEL_DIR = os.path.join('..', '..', '..', 'src')


def todir(*path):
    ret = os.path.join(*path)
    if not os.path.isdir(ret):
        os.makedirs(ret)
    return ret


def copy_tree(from_path, to_path):
    distutils.dir_util.copy_tree(
        from_path,
        to_path,
        preserve_symlinks=False,
        update=True,
        verbose=True,
        dry_run=False)


def run_py(script, *args):
    cmd = [sys.executable, os.path.join(PRESQUEL_DIR, script)]
    cmd.extend(args)
    env = os.environ
    env['PYTHONPATH'] = PRESQUEL_DIR
    exe = subprocess.Popen(cmd, env = env, shell = False)
    exe.wait()
    return exe.returncode


def clean():
    if os.path.exists('exports'):
        shutil.rmtree('exports', ignore_errors=False)


def generate_sql():
    ret = run_py('genBaseSql.py',
                 '-p', 'mysql',
                 '-o', os.path.join('exports', 'sql'),
                 todir('sql'))
    if ret != 0:
        sys.exit(ret)


def generate_php_dbo():
    ret = run_py('genPhpDboLayer.py', 'DboParent', 'Dbo', todir('sql'),
                 todir('exports', 'php_dbo'))
    if ret != 0:
        sys.exit(ret)


def copy_to_exports():
    copy_tree(todir('web'), todir('exports', 'web'))
    copy_tree(todir('php_lib'), todir('exports', 'php_lib'))
    copy_tree(todir('conf'), todir('exports', 'conf'))


if __name__ == '__main__':
    clean()
    generate_sql()
    generate_php_dbo()
    copy_to_exports()
