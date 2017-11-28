#!/usr/bin/env bash
import os
import logging
import bunch
from infra.runner import Command, Runner


def run_shell(self, wdir=None, runner=None, name=None, env=None,
              **kwargs):
    runner = runner or Runner(working_dir=wdir or self.wdir)
    total_params = self._get_run_opts(env=env, name=name)
    total_params.update(kwargs)
    total_params.update(self.kwargs)
    return runner.run(self.commands, **total_params)


class ShellCommand(Command):
    run = run_shell

    def __init__(self, cmds, name='shell', env=None, wdir=None,
                 **kwargs):
        self.commands = cmds
        self.kwargs = kwargs or {}
        self.cmd_env = env or {}
        self.name = name
        self.wdir = wdir

    def __repr__(self):
        return '{}(cmd_env={self.cmd_env}, **kwargs={self.kwargs})'.format(
            self.__class__.__name__, self=self)

    def __call__(self, **kwargs):
        return self.run(**kwargs)

    def render(self):
        self.__repr__()

    def _get_run_opts(self, env=None, name=None):
        total_env = dict(self.cmd_env)
        total_env.update(env or {})
        run_opts = dict(
            shell=True,
            _log_output=self._logname(name),
            _env=total_env,
            _tmp_script=True
        )
        return run_opts

    def _logname(self, name):
        return "{}".format(name or self.name)


# aliases
def sh(cmds, return_output=False, **kwargs):
    result = ShellCommand(cmds).run(**kwargs)
    if return_output:
        return str(result.output.strip())

