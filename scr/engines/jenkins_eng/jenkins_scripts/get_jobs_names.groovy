// params = [:] // are inserted by jin
// assert (
//     params.lastSuccess &&
//     params.buildName)

import jenkins.*
import hudson.model.*

def walkChildren(items, Closure action) {
  items.each { item ->
    if (item.class.canonicalName != 'com.cloudbees.hudson.plugins.folder.Folder' &&
        item.class.canonicalName != 'org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject') {
      action(item)
    } else {
      walkChildren((item).getItems(), action) // removed: (com.cloudbees.hudson.plugins.folder.Folder) item
    }
  }
}

def printFullName = { item ->
  println item.fullName
}

walkChildren(Hudson.instance.items, printFullName)
println ''