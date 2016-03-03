#! /usr/bin/env python

# Input parameters
#     Source Instance Name
#     Source Project Name
#     Destination Instance Name
#     Destination Project Name

import os, sys
import json
from subprocess import Popen, PIPE

def read_adminopenrc(path=None):
    """Read the OpenStack environment variables from the specified path."""
    if path is not None:
        if os.path.isdir(path):
            admin_openrc_path = os.path.join(path, 'admin-openrc.sh')
        else:
            admin_openrc_path = path
    else:
        admin_openrc_path = os.path.join(os.environ['HOME'], 'admin-openrc.sh')
        if os.path.isfile(admin_openrc_path) is False:
            admin_openrc_path = os.path.join('.', 'admin-openrc.sh')

    admin_openrc=open(admin_openrc_path).read()
    ENVIRON={}
    for line in admin_openrc.splitlines():
        key, value = line.split()[1].split('=')
        ENVIRON[key] = value
    return ENVIRON

def main(argv):
    # print argv
    source_instance=argv[-4]
    source_project=argv[-3]
    dest_instance=argv[-2]
    dest_project=argv[-1]

    # print source_instance, source_project, dest_instance, dest_project

    env = dict(os.environ.copy().items() + read_adminopenrc().items())

    project_list = Popen('openstack project list'.split(), stdout=PIPE, env=env).communicate()[0]

if __name__ == '__main__':
    main(sys.argv)
