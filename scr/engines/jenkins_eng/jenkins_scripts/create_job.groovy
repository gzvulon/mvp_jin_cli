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
job('hello-world-dsl') {
   steps {
     shell("echo the_dsl 'Hello World!'")
   }
}
"""

create_dsl_job(the_dsl)