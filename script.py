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

def parse_list_output(output):
    lines = output.splitlines()
    # for line in lines:
    #     if len(line.split()) <= 1:
    #         continue
    #     keys = line.split()[1::2]
    #     lines.remove(line)
    #     break
    keys = filter(None, lines[1].split('|'))
    keys = [x.lower().strip() for x in keys]

    r = []
    for line in lines[3:-1]:
        if len(line.split()) <= 1:
            continue
        values = filter(None, line.split('|'))
        values = [x.strip() for x in values]
        record = dict(zip(keys, values))
        r.append(record)
    return r

def parse_output(output):
    lines = output.splitlines()[3:-1]
    r = {}
    for line in lines:
        kv = filter(None, line.split('|'))
        kv = [x.strip() for x in kv]
        r = dict(r.items() + [tuple(kv)])

    return r

def get(list_of_dict, key, value):
    o = filter(lambda dictionary: dictionary[key] == value, list_of_dict)
    return o

def main(argv):
    # print argv
    source_instance=argv[-4]
    source_project=argv[-3]
    dest_instance=argv[-2]
    dest_project=argv[-1]

    # print source_instance, source_project, dest_instance, dest_project

    env = dict(os.environ.copy().items() + read_adminopenrc().items())

    project_list = parse_list_output(Popen('openstack project list'.split(), stdout=PIPE, env=env).communicate()[0])
    instance_list = parse_list_output(Popen('nova list --all-tenants'.split(), stdout=PIPE, env=env).communicate()[0])
    volume_list = parse_list_output(Popen('nova volume-list --all-tenants'.split(), stdout=PIPE, env=env).communicate()[0])

    source_project_id = get(project_list, 'name', source_project)[0]['id']
    dest_project_id = get(project_list, 'name', dest_project)[0]['id']

    similar_instance_list = get(instance_list, 'name', source_instance)
    source_instance_id = get(similar_instance_list, 'tenant id', source_project_id)[0]['id']
    attached_volumes_list = get(volume_list, 'attached to', source_instance_id)

if __name__ == '__main__':
    main(sys.argv)
