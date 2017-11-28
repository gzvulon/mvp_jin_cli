import json
import bunch
import logging
import os
import webbrowser
import waiting
from fnmatch import fnmatch
from bunch import bunchify

import jenkins
from jenkins import HTTPError, urlopen, BUILD_WITH_PARAMS_JOB, urlencode

import utils
import fs_utils
from infra.runner import UrlItem, ParallelRun


def _get_queue_info_short(d):
    causes = next(a for a in d['actions'] if 'causes' in a)['causes']
    short_causes = [x['shortDescription'] for x in causes]
    p = {
        'name': d['task']['name'],
        'queue': d['url'],
        'blocked': 'blocked' if d['blocked'] else '',
        'why': d['why'],
        'causes': short_causes,
    }
    s = "{name} waiting at {queue} {blocked} " \
        "why:{why} causes:{causes}".format(**p)
    return s


def _is_parametrized_job(job_info):
    for field in ['actions', 'property']:
        if field not in job_info:
            continue
        if any('parameterDefinitions' in el for el in job_info[field]):
            return True
    return False


class BuildSelector(object):
    last = 'lastBuild'
    last_completed = 'lastCompletedBuild'
    last_failed = 'lastFailedBuild'
    last_stable = 'lastStableBuild'
    last_successful = 'lastSuccessfulBuild'
    last_unstable = 'lastUnstableBuild'
    last_unsuccessful = 'lastUnsuccessfulBuild'

    @classmethod
    def is_prop(cls, name):
        return name.startswith('last') and \
            isinstance(cls.__dict__[name], basestring)

    @classmethod
    def keys(cls):
        return [name for name in vars(cls).iterkeys()
                if cls.is_prop(name)]

    @classmethod
    def values(cls):
        return [cls.__dict__[name] for name in cls.keys()
                if cls.is_prop(name)]

    @classmethod
    def items(cls):
        return [(name, getattr(cls, name)) for name in cls.keys()]

    def __contains__(self, value):
        return value in self.values()

    @classmethod
    def last_build_number(cls, job_info, build_type=None):
        build_type = build_type or cls.last_successful
        build_number = int(job_info[build_type]['number'])
        return build_number


class JenkinsServer(jenkins.Jenkins):
    BuildSelector = BuildSelector

    @property
    def settings(self):
        return bunch.Bunch(
            plugins_ignore_list=[
                'docker-plugin',
                'docker-build',
                'docker-slaves']
        )

    def __repr__(self):
        return '{}({})'.format(self.__class__.__name__, self.server)

    def jenkins_open_ex(self, req, add_crumb=True):
        """ Taken from jenkins.Jenkins.jenkins_open implementation.
        returns response with headers.
        """
        try:
            if self.auth:
                req.add_header('Authorization', self.auth)
            if add_crumb:
                self.maybe_add_crumb(req)
            rs = urlopen(req, timeout=self.timeout)
            return rs
        except HTTPError as e:
            if e.code in [401, 403, 500]:
                logging.error('Possibly authentication failed {}: {} '
                              'when running {}'.format(e.code, e.msg, req))
            elif e.code == 404:
                raise logging.error('Requested item could not be found: '
                                    '{}'.format(req))
            raise

    def invoke_job(self, name, parameters=None, token=None,
                   cause=None,
                   wait_started=True, wait_done=True,
                   output_progress=False, output_done=True,
                   open_browser=False, short_info=True):

        wait_started = wait_started or open_browser or wait_done

        logging.info('invoke job:{} parameters:{}'.format(name, parameters))
        job_info = self.get_job_info(name)
        has_params = _is_parametrized_job(job_info)
        params = parameters or {}

        if has_params and cause:
            params['cause'] = cause

        req_url = self.build_job_url_ex(name, params, token,
                                        has_params=has_params)
        logging.info('invoke at {}'.format(req_url))
        response = self.jenkins_open_ex(jenkins.Request(req_url, b''),
                                        add_crumb=False)
        logging.info('running with params: {}'.format(params))
        job_in_queue_url = response.headers['location'] + 'api/json'
        logging.info('enqueued url: {}'.format(job_in_queue_url))

        result = json.loads(
            self.jenkins_open(jenkins.Request(job_in_queue_url)))
        wait_started = wait_started or wait_done
        logging.info("triggered: {}".format(name))

        if wait_started:
            logging.info('\n[wait until:started:{}]\n'.format(name))
            build_number = self._wait_started(job_in_queue_url)
            build_info = self.get_build_info(name, build_number)
            if open_browser:
                webbrowser.open_new_tab('{}/console'.format(build_info['url']))
            if wait_done:
                logging.info("waiting for done: {}".format(name))
                build_info = self.wait_done(name, build_number,
                                            output_progress=output_progress)
            if output_done:
                logging.info(self.get_build_console_output(name, build_number))
            result = build_info

        if result and short_info:
            info = bunch.bunchify(result)
            result = utils.from_build_info_to_build_short_info(info)
        return result

    def _wait_started(self, job_in_queue_url):
        def get_queue_info():
            js = self.jenkins_open(jenkins.Request(job_in_queue_url))
            return json.loads(js)
        q_info = get_queue_info()

        def is_build_started():
            progress = get_queue_info()
            logging.info('waiting for started: {}'.format(
                _get_queue_info_short(progress)))
            if ('executable' in progress and
                    'number' in progress['executable']):
                build_number = progress['executable']['number']
                return build_number
            else:
                return None
        try:
            return waiting.wait(is_build_started)
        except KeyboardInterrupt:
            c = raw_input('choose: [s]top queue, else: deattach').strip()
            if c == 's':
                self.cancel_queue(q_info['id'])
            raise

    def wait_done(self, name, build_number,
                  output_progress=False):
        info = {'out': 0}

        def is_build_done():
            build_info = self.get_build_info(name, build_number)
            if output_progress:
                output = self.get_build_console_output(name, build_number)
                rest = output[info['out']:]
                if rest.strip():
                    logging.info(rest)
                    info['out'] += len(rest)
            if build_info['result']:
                return build_info
            return None

        init_build_info = self.get_build_info(name, build_number)
        logging.info('waiting for done: {}console'.format(
            init_build_info['url']))
        try:
            return waiting.wait(is_build_done)
        except KeyboardInterrupt:
            c = raw_input('choose: [s]top build, else deattach').strip()
            if c == 's':
                self.stop_build(name, build_number)
            raise

    def build_job_url_ex(self, name, parameters=None, token=None,
                         has_params=True):
        """There are issues with triggering builds with and without params
        for jobs which has/hasn't default params
        """
        if has_params:
            folder_url, short_name = self._get_job_folder(name)
            params = dict(folder_url=folder_url, short_name=short_name)
            if token:
                parameters = parameters or {}
                parameters['token'] = token
            url_params = ''
            if parameters:
                url_params = '?' + urlencode(parameters)
            return self._build_url(BUILD_WITH_PARAMS_JOB, params) + url_params
        else:
            return self.build_job_url(name, token=token)

    def get_build_info_ex(self, job_name, build_number=None, depth=1,
                          build_status=BuildSelector.last_successful):
        job_info = self.get_job_info(job_name, depth=1)
        if build_number is None:
            build_number = BuildSelector.last_build_number(job_info,
                                                           build_status)
        return self.get_build_info(job_name, build_number, depth=depth)

    def get_last_build_number(self, job_name,
                              build_status=BuildSelector.last_successful):
        job_info = self.get_job_info(job_name, depth=1)
        build_number = BuildSelector.last_build_number(
            job_info, build_status)
        return build_number

    def fetch(self, job_name,
              cache=None,
              build_number=None,
              build_status=BuildSelector.last_successful,
              build_info=None,
              file_pattern=None):

        if build_info is None:
            build_info = self.get_build_info_ex(job_name,
                                                build_number=build_number,
                                                build_status=build_status)
        build_number = int(build_info['number'])

        cache = cache or '.'
        fs_utils.ensure_dir(cache)
        fs_utils.restore_user_permissions(cache)

        name = 'cache-{}-{}'.format(jobname_to_flat(job_name), build_number)
        dest = os.path.join(cache, name)
        fs_utils.ensure_dir(dest)

        logging.info('fetching artifacts for jenkins-{}-{}'.format(
                     job_name, build_number))

        save_context = self.save_artifacts(dest, build_info,
                                           file_name_pattern=file_pattern)
        return save_context

    def get_build_url(self, build_info):
        raw_build_url = build_info['url']
        parts = raw_build_url.split('/job/')
        parts[0] = self.server
        build_url = '/job/'.join(parts)
        return build_url

    @staticmethod
    def get_artifact_url(art_info, build_url=None):
        from urllib import quote
        relative_path = art_info["relativePath"]
        return "{}artifact/{}".format(build_url, quote(relative_path))

    def get_artifact(self):
        pass

    def save_artifacts(self, dest_dir, build_info,
                       file_name_pattern=None):

        artifacts = build_info["artifacts"]
        build_url = self.get_build_url(build_info)
        deploy_url = os.path.join(dest_dir, '.')

        def mk_item(art_info):
            return UrlItem(self.get_artifact_url(art_info, build_url),
                           os.path.join(deploy_url, art_info["relativePath"]))

        def is_match(art_info):
            if file_name_pattern:
                return fnmatch(art_info["fileName"], file_name_pattern)
            else:
                return True
        items = map(mk_item, filter(is_match, artifacts))
        return ParallelRun(items, retrieve, ctx=dest_dir)

    def get_artifact_build_file_content(self, build_info, path):
        url = self._get_artifacts_url(build_info, path)
        return fs_utils.get_web_file_content(url)

    def _get_artifacts_url(self, build_info, path=None):
        build_url = self.get_build_url(build_info)
        if path:
            url = '{}/artifact/{}'.format(build_url, path)
        else:
            url = '{}/artifact'.format(build_url)
        return url

    def list_jobs(self):
        return bunchify(self.get_all_jobs())

    def get_nodes_info(self, nodes_name_list):
        for worker_name in nodes_name_list:
            try:
                yield self.get_node_info(worker_name, depth=1)
            except jenkins.NotFoundException:
                if worker_name != 'master':
                    logging.warn('worker {} has no info', worker_name)
                yield None

    def _filter_workers(self, workers_list, host=None, node=None):
        if host:
            workers_list = filter(lambda wn: wn.startswith(host), workers_list)
        if node:
            workers_list = filter(lambda wn: wn == node, workers_list)
        return workers_list

    def get_workers(self, host, node_name, is_offline=None):
        workers_list = [node['name'] for node in self.get_nodes()
                        if is_offline is None or node['offline'] is is_offline]
        return self._filter_workers(workers_list, host, node_name)

    def get_plugins_with_version(self):
        plugins_raw = self.get_plugins()
        plugins_dict = [(x[0][0], x[1]) for x in plugins_raw.items()]
        plugins_dict_clean = filter(
            lambda p: p[0] not in self.settings.plugins_ignore_list,
            plugins_dict)
        plugins_versions = [(x[0], x[1]["version"])
                            for x in plugins_dict_clean]
        return plugins_versions

def retrieve(item):
    import urllib
    import humanfriendly
    logging.info('start retrieve: {} [{}]'.format(
        item, humanfriendly.format_size(item.get_remote_size())))
    logging.debug('{} => {}'.format(item.src, item.dst))
    dest_dir = os.path.dirname(item.dst)
    fs_utils.ensure_dir(dest_dir)
    urllib.urlretrieve(item.src, item.dst)
    local_size = humanfriendly.format_size(os.path.getsize(item.dst))
    logging.info('done retrieve: {} [{}]'.format(item, local_size))


def jobname_to_short(fullname):
    return fullname.split('/')[-1]


def jobname_to_flat(fullname):
    return fullname.replace('/', '--')
