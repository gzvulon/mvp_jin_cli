import os
import logging


def _scripts_dir():
    return os.path.join(os.path.dirname(__file__), 'jenkins_scripts')


def _clean_server_script_output(info):
    r = info.replace('[', '').replace(']', '')
    xs = [x.strip() for x in r.split(',')]
    return xs


def run_server_script(jenkins, name, **params):
    if name.endswith('.groovy'):
        filename = name
    else:
        filename = name + '.groovy'

    if 'jenkins_scripts' in filename:
        dest_path = filename
    else:
        dest_path = os.path.join(_scripts_dir(), filename)

    with open(dest_path) as fp:
        script = fp.read()
    if params:
        params_line = "def params = [{}]\n".format(
            ', '.join("'{0}': '{1}'".format(*r) for r in params.items()))
        script = params_line + script
    logging.debug("running: {}".format(filename))
    info = jenkins.run_script(script)
    return _clean_server_script_output(info)


class JobMenu(object):

    def __init__(self, jenkins):
        self._jenkins = jenkins

    def list(self, all=True, api=False):
        """Lists jobs"""
        results = ["Failure"]
        if all:
            if api:
                all_jobs = self._jenkins.list_jobs()
                results = (job.fullname for job in all_jobs)
            else:
                results = run_server_script(
                    self._jenkins, 'get_jobs_names.groovy')
        else:
            results = run_server_script(
                self._jenkins, 'list_running_jobs.groovy')
        return "\n".join(results)

    def create(self):
        results = run_server_script(self._jenkins, 'create_job.groovy')
        return "\n".join(results)

    def init(self):
        results = run_server_script(self._jenkins, 'init_self_check.groovy')
        return "\n".join(results)

    def run(self, jobname):
        info = self._jenkins.invoke_job(jobname, #parameters,
                                   cause='cli invoke',
                                   wait_started=True,
                                   wait_done=True,
                                   output_progress=True,
                                   short_info=True)
        return "\n".join(report_json(info))
        
def report_json(info):
    import json
    return [
        "===[BUILD_INFO:JSON]===",
        json.dumps(info, indent=4, sort_keys=True),
        "======================"]

