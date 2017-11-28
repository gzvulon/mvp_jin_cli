def now = new Date()  // Get the current time
// Get a list of all running jobs
def buildingJobs = Jenkins.instance.getAllItems(Job.class).findAll {
  it.isBuilding() }

def report_lines = ["[START:REPORT:RESULTS_TSV]",
    "progress.%\tduration.minutes\tjob.name\tnode.name"
]

void printAllMethods( obj ){
    if( !obj ){
		println( "Object is null\r\n" );
		return;
    }
	if( !obj.metaClass && obj.getClass() ){
        // printAllMethods( obj.getClass() );
		return;
    }
	def str = "class ${obj.getClass().name} functions:\r\n";
	obj.metaClass.methods.name.unique().each{ 
		str += it+"(); \n";
	}
	println "${str}\r\n";
}

buildingJobs.each { job->
    // Enumerate all runs
    allRuns = job._getRuns()
    allRuns.each { it ->
        def item = null
        try {
            item = it.value
        }
        catch (Exception ex){
            // groovy.lang.MissingPropertyException: No such property: value for class: org.jenkinsci.plugins.workflow.job.WorkflowRun
            item = it
        }
        // If NOT currently building... check the next build for this job
        String jobname = item.getUrl()
        jobname = jobname.replaceAll('job/', '').trim()  // Strip redundant folder info.

        try {
            if (!item.isBuilding()) return
        }
        catch (Exception ex) {
            println "skipping ${jobname}"
            return
        }

        // Access and calculate time information for this build.
        def startedAt = new Date(item.getStartTimeInMillis())
        def duration_mins = ((now.getTime() - item.getStartTimeInMillis()) / 60000).intValue()
        def estDurationMins = (item.getEstimatedDuration() / 60000).intValue()
        def predicted_duration =  estDurationMins > 0 ? estDurationMins : duration_mins * 2
        try {
            def progress = ((100 * duration_mins).intValue() / predicted_duration).intValue()

            def progress_str = "${progress.toString().padLeft(7)}"
            def total_minutes_str = "${predicted_duration.toString().padLeft(7)}"
            def job_str = "${jobname.toString().padRight(40)}"

            // println item.isInProgress()

            def node_name =  'N/A'
            try {
                node_name = item.getBuiltOn().getNodeName()
            }
            catch(Exception ex){
                //printAllMethods(item)
            }

            def line =  "p${progress_str}%\t${total_minutes_str}m\t${job_str}\t${node_name}"
            report_lines.add(line)
        }
        catch (Exception ex){
            println "failed to fetch: ---${duration_mins}--${predicted_duration}--${jobname} ${ex}"
        }
    }
}
report_lines.add("[FINISH:REPORT:RESULTS_TSV]")
return report_lines
