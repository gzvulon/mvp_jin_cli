import hudson.model.*;
import jenkins.model.*;

import javaposse.jobdsl.dsl.DslScriptLoader
import javaposse.jobdsl.plugin.JenkinsJobManagement

def create_dsl_job(jobDslScript) {
        def env = System.getenv()
        def workspace = new File('.')
        def jobManagement = new JenkinsJobManagement(System.out, [:], workspace)
        new DslScriptLoader(jobManagement).runScript(jobDslScript)
        Jenkins.instance.save()
}

def the_dsl = """

def included_branches = [
    'master',
    '*_PR'
]
def str_included_branches = included_branches.join(" ")

multibranchPipelineJob('sysjin/mvp_jin_cli') {
    branchSources {
        git {
            remote('https://github.com/gzvulon/mvp_jin_cli.git')
            includes(str_included_branches)
        }
    }
    orphanedItemStrategy {
        discardOldItems {
            numToKeep(60)
        }
    }
    triggers {
        periodic(1)
    }
}
"""

create_dsl_job(the_dsl)
