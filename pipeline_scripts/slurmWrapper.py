import os, getopt, sys
import utils
from hashlib import sha256

def monitor(configs):
    pass

def submit(configs):
    workspace = sha256('{}{}'.format(os.getenv('WORKSPACE'), os.getenv('BUILD_NUMBER')).encode('utf-8')).hexdigest()
    utils.heavyLogging('workspace: {}, {} -> {}'.format(os.getenv('WORKSPACE'), os.getenv('BUILD_NUMBER'), workspace))
    # prepare remote workspace
    cmdPieces = ['ssh', '-o', 'StrictHostKeyChecking=no', '-i', os.getenv('SLURM_KEY'), \
                    '{}@{}'.format(os.getenv('SLURM_USER'), configs['slurmHost']), 'mkdir -p ~/jenkins_workspace/{}'.format(workspace)]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    cmdPieces = ['ssh', '-o', 'StrictHostKeyChecking=no', '-i', os.getenv('SLURM_KEY'), \
                    '{}@{}'.format(os.getenv('SLURM_USER'), configs['slurmHost']), 'mkdir -p ~/jenkins_workspace/{}/.pf-scripts'.format(workspace)]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    cmdPieces = ['ssh', '-o', 'StrictHostKeyChecking=no', '-i', os.getenv('SLURM_KEY'), \
                    '{}@{}'.format(os.getenv('SLURM_USER'), configs['slurmHost']), 'mkdir -p ~/jenkins_workspace/{}/.pf-configs'.format(workspace)]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    # copy script, config to slurm node
    cmdPieces = ['scp', '-o', 'StrictHostKeyChecking=no', '-i', os.getenv('SLURM_KEY'), configs['script'], \
                    '{}@{}:~/jenkins_workspace/{}/.pf-scripts/{}'.format(os.getenv('SLURM_USER'), configs['slurmHost'], workspace, os.path.basename(configs['script']))]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    cmdPieces = ['scp', '-o', 'StrictHostKeyChecking=no', '-i', os.getenv('SLURM_KEY'), configs['script'], \
                    '{}@{}:~/jenkins_workspace/{}/.pf-configs/{}'.format(os.getenv('SLURM_USER'), configs['slurmHost'], workspace, os.path.basename(configs['config']))]
    utils.popenWithStdout(cmdPieces, dict(os.environ))
    # run command

    #ssh -o StrictHostKeyChecking=no user@slurm-login-node 'sbatch /path/to/job.sh'
    monitor(configs)

def main(argv):
    configs = dict()
    try:
        opts, args = getopt.getopt(argv[1:], 's:f:h:', ["script=", "config=", "host="])
    except getopt.GetoptError:
        sys.exit()
    for name, value in opts:
        if name in ('-h', '--host'):
            configs['slurmHost'] = value
        elif name in ('-s', '--script'):
            configs['script'] = value
        elif name in ('-f', '--config'):
            configs['config'] = value
    submit(configs)

if __name__ == "__main__":
    main(sys.argv)