import os
import bunch


class JinException(Exception):
    pass


def from_ini_params(s):
    lines = []
    if isinstance(s, basestring):
        lines_dirty = (line.strip() for line in s.split(','))
        lines = (line for line in lines_dirty if line)
    elif isinstance(s, list) or isinstance(s, tuple):
        lines = s
    return dict(line.split('=') for line in lines)


def from_build_info_to_build_short_info(result):

    build_info = bunch.bunchify(result)

    def is_param(x):
        klass = x.get('_class', None)
        return klass == "hudson.model.ParametersAction"

    params = next(iter(x.parameters for x in
                       filter(is_param, build_info.actions)), {})

    parameters_real = {p.name: p.value for p in params}

    info = bunch.Bunch({
        'queueId': result['queueId'],
        'number': result['number'],
        'timestamp': result['timestamp'],
        'displayName': result['displayName'],
        'artifacts': result['artifacts'],
        'duration': result['duration'],
        'result': result['result'],
        'fullDisplayName': result['fullDisplayName'],
        'parametersReal': parameters_real,
        'url': result['url']
    })
    return info


def check_root():
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\n"
             "Please try again, this time using 'sudo'. Exiting.")


def get_username():
    username = os.getenv("USER").strip()
    if username == 'root':
        check_root()
        username = os.getenv("SUDO_USER").strip()
    return username
