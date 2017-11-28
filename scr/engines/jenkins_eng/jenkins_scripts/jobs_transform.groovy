// params = [:] // are inserted by jin
assert (
    params.pattern &&
    params.action)

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

def actions_map = [
  delete: { item ->
    if (item.fullName =~ params.pattern) {
        item.delete()
        println("deleted: ${item.fullName}")
    }
  },
  list: { item ->
    if (item.fullName =~ params.pattern) {
        println("${item.fullName}")
    }
  }
]

def action = actions_map[params.action]
walkChildren(Hudson.instance.items, action)
println ''