// params = [:] // are inserted by jin
assert (
    params.scriptContent
)

import hudson.model.*;
import jenkins.model.*;

import javaposse.jobdsl.dsl.DslScriptLoader
import javaposse.jobdsl.plugin.JenkinsJobManagement
import static java.util.UUID.randomUUID
import java.text.SimpleDateFormat

def create_shell_job(jobDslScript) {
        def env = System.getenv()
        def workspace = new File('.')
        def jobManagement = new JenkinsJobManagement(System.out, [:], workspace)
        new DslScriptLoader(jobManagement).runScript(jobDslScript)
        Jenkins.instance.save()
}

def the_uuid = randomUUID() as String

def date = new Date()
def sdf = new SimpleDateFormat("yyyy-MM-dd--HH-mm-ss")
def the_now = sdf.format(date) 

def the_dsl = """
folder('z_tmp')
job('z_tmp/${the_now}_${the_uuid}') {
   steps {
     shell("${params.scriptContent}")
   }
}
"""

create_shell_job(the_dsl)
return the_dsl