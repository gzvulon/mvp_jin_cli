import os
import sys
import logging

from utils import JinException
from infra.runner import Runner


def run_cmd(*args, **kwargs):
    return Runner.run_sh(*args, **kwargs)


def read_content(target_path):
    with open(target_path, 'r') as fd:
        return fd.read()


def write_content(target_path, content):
    dir_path = os.path.dirname(target_path)
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(target_path, 'w') as fd:
        return fd.write(content)


def verify_path_doesnt_exists(dest):
    if os.path.exists(dest):
        raise JinException(
            'Directory {} already exits. use --force to override'.format(dest))


def ensure_dir_exists(dest):
    if not os.path.exists(dest):
        os.makedirs(dest)


def checkout_from_cache(fetched_dir, dest_dir,
                        subdir=None, force=None, strip=False):
    if strip:
        ensure_dir_exists(dest_dir)
    elif not force:
        verify_path_doesnt_exists(dest_dir)
    elif force:
        logging.info('removing {}'.format(dest_dir))
        Runner.run_cmd('rm -rf {}'.format(dest_dir))

    if subdir:
        the_dir = os.path.join(fetched_dir, subdir)
    else:
        the_dir = fetched_dir

    if strip:
        Runner.run_cmd('mv {}/* {}/'.format(the_dir, dest_dir))
    else:
        Runner.run_cmd('mv {} {}'.format(the_dir, dest_dir))

    Runner.run_cmd('rm -rf {}'.format(fetched_dir))
    return fetched_dir


def get_web_file_content(url):
    import requests
    response = requests.get(url)
    if not (200 <= response.status_code < 300):
        raise JinException('Error when request {}'.format(url))
    return response.content.strip()


def restore_user_permissions(dest_dir):
    if os.geteuid() == 0 and os.environ.get('SUDO_UID', None):
        uid = int(os.environ.get('SUDO_UID'))
        gid = int(os.environ.get('SUDO_GID'))
    else:
        uid = os.geteuid()
        gid = os.getegid()
    run_cmd('chown {uid}:{gid} {dest_dir}',
            uid=uid, gid=gid, dest_dir=dest_dir,
            _tmp_script=True)


def ensure_dir(path):
    try:
        os.makedirs(path)
    except OSError:
        if not os.path.isdir(path):
            raise
