import fire
from bunch import Bunch
import logging
logging.basicConfig(level=logging.DEBUG)

from engines.jenkins_eng.jenkins_server import JenkinsServer
from engines.jenkins_eng.jenkins_scripts_api import JobMenu

class RootMenu(object):

  def __init__(self, 
               server='jenkins', port=8080, 
               username=None, password=None):
    server_url = 'http://{}:{}'.format(server,port)
    self.__jenkins_server = JenkinsServer(server_url,
                                    username=username,
                                    password=password)
    self.job = JobMenu(jenkins=self.__jenkins_server)    
  
if __name__ == '__main__':
  fire.Fire(RootMenu, name='jin')