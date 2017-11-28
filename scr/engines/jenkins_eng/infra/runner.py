import os
import bunch
import shlex
import logging
import subprocess
import tempfile
import multiprocessing
import signal


class Command(object):
    def render(self):
        raise NotImplementedError()

    def run(self, **kwargs):
        raise NotImplementedError()

def _clean_bash_debug_output(text):
    return "\n".join(
        line for line in text.split('\n')
        if not line.startswith('+ '))


class CmdResult(object):
    def __init__(self, returncode, output):
        self.returncode = returncode
        self.output = _clean_bash_debug_output(output)

    def readlines(self, pattern=None):
        return [x.strip() for x in self.output.split('\n') if x.strip()]

    @property
    def text(self):
        text = self.output[:min(79, len(self.output))].strip()
        return text

    def __repr__(self):
        text = self.output[:min(79, len(self.output))]
        return '{}({}:{})'.format(
            self.__class__.__name__, self.returncode, text)


class AsyncReslut(object):
    """docstring for AsyncReslut"""
    def __init__(self, process, commands, ret_codes=0, log_output=None,
                 cleanup=None):
        self.process = process
        self.commands = commands
        self.cleanup = cleanup or (lambda: None)

        if not hasattr(ret_codes, '__getitem__'):
            self.ret_codes = [ret_codes]
        else:
            self.ret_codes = ret_codes

        if not log_output and logging.getLogger().level <= logging.DEBUG:
            log_output = True
        self.log_output = log_output

    @property
    def _get_log_prefix(self):
        if self.log_output is True:
            prefix = "[{}]".format(self.process.pid)
        elif isinstance(self.log_output, basestring):
            prefix = "[{}.{}]".format(self.log_output, self.process.pid)
        else:
            prefix = None
        return prefix

    def _comunicate_log_output(self):
        process = self.process
        prefix = self._get_log_prefix
        output_log = []
        while True:
            output = process.stdout.readline()  # read(100) # readline()
            if not output and process.poll() is not None:
                break
            if output:
                _out = output.decode('ascii').strip()
                logging.debug("{}{}".format(prefix, _out))
                output_log.append(_out)
        out = "\n".join(output_log)
        err = process.stderr.read()
        return out, err

    def communicate_local(self):
        if self.log_output:
            out, err = self._comunicate_log_output()
        else:
            out, err = self.process.communicate()
        self.cleanup()
        return out.strip(), err, self.process.returncode

    def get(self, raise_on_err=True):
        output, errors, returncode = self.communicate_local()
        if raise_on_err and returncode not in self.ret_codes:
            raise RuntimeError(
                'Error running command: {}. Return code: {}, Error: {}'.format(
                    self.commands, returncode, errors))
        
        res = CmdResult(returncode=returncode, output=output)
        return res


def run_local(cmds, _log_output=False, _ret_codes=0, _cleanup=None,
              **kwargs):
    if isinstance(cmds, basestring):
        commands = cmds
        kwargs['shell'] = True
    else:
        commands = cmds

    logging.debug('run local: {} with {}'.format(commands, kwargs))

    process = subprocess.Popen(
        commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs)

    async_result = AsyncReslut(
        process, commands,
        log_output=_log_output,
        ret_codes=_ret_codes,
        cleanup=_cleanup)
    return async_result


def escape_bash(cmd_lines):
    n_bash = 0
    prev_is_dollar = False
    res = []
    for i, c in enumerate(cmd_lines):
        v = c
        if c == '$':
            prev_is_dollar = True
        elif c == '{' and prev_is_dollar:
            v = '{{'
            prev_is_dollar = False
            n_bash += 1
        elif c == '}' and n_bash > 0:
            v = '}}'
            n_bash -= 1
        res.append(v)
    return "".join(res)


class Runner(object):
    def __init__(self, working_dir=None, env=None):
        self.working_dir = working_dir
        self.env = env or {}

    def _expand_env(self, env):
        total_env = dict(self.env)
        total_env.update(env or {})
        return total_env

    @staticmethod
    def _expand_cmd(cmd_tml, args, kwargs):
        cmd_tml = escape_bash(cmd_tml)
        cmd = cmd_tml.format(*args, **kwargs)
        return cmd

    def _create_tmp_script(self, total_env, cmd_content):
        env_str = " ".join("{0}={1}".format(*x) for x in total_env.items())
        temp = tempfile.NamedTemporaryFile(delete=False, mode='w')
        temp.write('#!/usr/bin/env bash\n')
        temp.write(cmd_content)
        temp.close()
        logger = logging.getLogger()
        bash_log = '-x' if logger.level == logging.DEBUG else ''
        cmd = "{0} env bash {2} -e {1} 2>&1 ".format(
            env_str, temp.name, bash_log)
        cleanup = lambda: os.remove(temp.name)
        logging.debug('temp/%s:\n%s\n---\n%s\n',
                      temp.name, cmd, cmd_content)
        return cmd, cleanup

    def _update_cwd(self, d):
        if not self.working_dir:
            return
        if not os.path.exists(self.working_dir):
            os.makedirs(self.working_dir)
        d['cwd'] = self.working_dir

    def _extract_run_params(self, kwargs):
        rest = {k: kwargs.pop(k) for k in list(kwargs.keys())
                if k.startswith('_')}
        _tmp_script = rest.pop('_tmp_script', False)
        _split = rest.pop('_split', None)
        _raise = rest.pop('_raise', False)
        if _split and _tmp_script:
            raise ValueError('both _split and _tmp_script cannot be True')

        dry = rest.pop('_dry', None)
        total_env = self._expand_env(rest.pop('_env', None))

        return bunch.Bunch(
            dry=dry,
            _split=_split,
            _tmp_script=_tmp_script,
            total_env=total_env,
            _raise=_raise
        ), rest

    def run(self, cmd_tml, *args, **kwargs):
        run_params, rest = self._extract_run_params(kwargs)
        cmd_content = self._expand_cmd(cmd_tml, args, kwargs)
        cmd = cmd_content
        cleanup = None
        shell = True

        if run_params._split:
            cmd = shlex.split(cmd_content)

        if run_params.dry:
            _msg = 'dry run: with env={} opts={} will run {}'.format(
                   run_params.total_env, rest, cmd_content)
            logging.info(_msg)
            return CmdResult(0, _msg)

        self._update_cwd(rest)
        if run_params._tmp_script:
            cmd, cleanup = self._create_tmp_script(
                run_params.total_env, cmd_content)

        async_result = run_local(
            cmd, shell=shell, _cleanup=cleanup,
            env=run_params.total_env, **rest)
        res = async_result.get(raise_on_err=run_params._raise)
        return res

    @staticmethod
    def run_cmd(cmd, *args, **kw):
        return Runner().run(cmd, *args, **kw)

    @staticmethod
    def run_sh(cmd, *args, **kw):
        return Runner().run(cmd, *args, **kw).output

    @staticmethod
    def run_item(item):
        cmd, kwargs = item.to_command()
        return Runner.run_cmd(cmd, **kwargs)

    @staticmethod
    def run_in_parallel(cmds):
        return ParallelRun(cmds, Runner.run_cmd)

    @staticmethod
    def run_items_in_parallel(items):
        return ParallelRun(items, Runner.run_item)


class UrlItem(object):
    def __init__(self, src, dst):
        self.src = src
        self.dst = dst

    def __repr__(self):
        return "{}({})".format(self.__class__.__name__, self.shortname())

    def shortname(self):
        return self.src.split('/')[-1]

    def get_remote_size(self):
        import urllib2
        f = urllib2.urlopen(self.src)
        return int(f.headers["Content-Length"])


def trace_unhandled_exceptions(func):
    import traceback
    import functools

    def wrapped_func(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as ex:
            _msg = 'Concurrent Exception in {}\n{}'.format(
                   getattr(func, '__name__', str(func)),
                   traceback.format_exc())
            logging.error(_msg, ex)
            raise

    if getattr(func, '__module__', None):
        return functools.wraps(func)(wrapped_func)
    else:
        return wrapped_func


@trace_unhandled_exceptions
def run_item(item):
    return item()


class IMultiRun(object):
    pass


class ParallelRun(IMultiRun):
    MAX_IO_BOUND_PROCS = 12

    @staticmethod
    def _make_pool(*args, **kwargs):
        original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
        pool = multiprocessing.Pool(*args, **kwargs)
        signal.signal(signal.SIGINT, original_sigint_handler)
        return pool

    def __init__(self, items, method=run_item, ctx=None):
        self.items = items
        self.method = method
        self.pool = self._make_pool(processes=self.MAX_IO_BOUND_PROCS)
        self.ctx = ctx

    def start_all(self):
        logging.info('started parallel run with {} items'.format(
            len(self.items)))
        results = self.pool.map_async(self.method, self.items)
        return results

    def finish_all(self):
        logging.debug('finished parallel run')
        self.pool.close()
        self.pool.join()

    def __enter__(self):
        return self.start_all()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, KeyboardInterrupt):
            logging.info("Caught KeyboardInterrupt, terminating sdfdsfsdfsdfsdfworkers")
            self.pool.terminate()
        self.finish_all()
        return exc_type is not None


    def wait_all(self, timeout=60 * 60 * 5.0):  # hours
        with self as results:
            return results.get(timeout)


class SequentialRun(IMultiRun):

    def __init__(self, items, method=run_item, ctx=None):
        self.items = items
        self.method = method

    def start_all(self):
        logging.info('started parallel run with {} items'.format(
            len(self.items)))
        results = []
        for item in self.items:
            results.append(self.method(item))
        return results

    def finish_all(self):
        logging.debug('finished parallel run')

    def __enter__(self):
        return self.start_all()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type and issubclass(exc_type, KeyboardInterrupt):
            logging.info("Caught KeyboardInterrupt, terminating workers")
        self.finish_all()
        return exc_type is not None

    def wait_all(self, timeout=60 * 60 * 5.0):  # hours
        return self.start_all()
