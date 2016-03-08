#! /usr/bin/env python

# Input parameters
#     Source Instance Name
#     Source Project Name
#     Destination Instance Name
#     Destination Project Name

import os, sys
import json
import time
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

def create_volume_snapshot(volumes, wait_for_available=0):
    """Create snapshots of the volumes."""
    if type(volumes) is not list:
        volumes = [volumes]
    s = []
    for volume in volumes:
        command = 'cinder snapshot-create --force True %s' % volume['id']
        snapshot_info = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
        if volume['bootable'] == 'true':
            snapshot_info['bootable'] = True
        else:
            snapshot_info['bootable'] = False
        att = get(volume_info_list, 'id', volume['id'])[0]['attachments']
        snapshot_info['device'] = get(json.loads(att), 'server_id', source_instance['id'])[0]['device']
        s.append(snapshot_info)
    if wait_for_available > 0:
        wait = 0
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for snapshot in s:
                command = 'cinder snapshot-show %s' % snapshot['id']
                status = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])[0]['status']
                if status == 'error':
                    # clean up and take snapshot again
                    pass
                elif status == 'creating':
                    again = True
                    break
                else:    # status == 'available'
                    # do nothing
                    pass
            if again:
                continue
            else:
                break
    return s

def create_volume_from_snapshot(snapshots):
    """Create volumes from the snapshots."""
    if type(snapshots) is not list:
        snapshots = [snapshots]
    v = []
    for snapshot in snapshots:
        command = 'cinder create --snapshot-id %s' % snapshot['id']
        volume_from_snapshot = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
        volume_from_snapshot['device'] = snapshot['device']
        volume_from_snapshot['bootable'] = snapshot['bootable']
        v.append(volume_from_snapshot)
    return v

def create_volume_transfer_request(volumes):
    """Create transfer requests"""
    if type(volumes) is not list:
        volumes = [volumes]
    t = []
    for volume in volume_from_snapshot_list:
        command = 'cinder transfer-create %s' % volume['id']
        transfer_request = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
        t.append(transfer_request)
    return t

def accept_volume_transfer_request(transfer_requests, recipient_project_id):
    """Accept transfer requests"""
    if type(transfer_requests) is not list:
        transfer_requests = [transfer_requests]
    t = []
    for request in transfer_requests:
        command = 'cinder --os-project-id %s transfer-accept %s %s' % (recipient_project_id, request['id'], request['auth_key'])
        transfer_accept = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
        t.append(transfer_accept)
    return t

def attach_volumes(instance_id, volumes):
    """Attach volumes to the given instance."""
    if type(volumes) is not list:
        volumes = [volumes]
    for volume in volumes:
        command = 'nova volume-attach %s %s %s' % (dest_instance['id'], volume['id'], volume['device'])
        dest_attachment = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])

def boot_from_volume(dest_project_id, bootable_volume_id, flavor, name):
    command = 'nova --os-project-id %s boot --boot-volume %s --flavor %s %s' % (dest_project_id, bootable_volume_id, flavor, name)
    instance = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    return instance

def boot_from_image(dest_project_id, bootable_image_id, flavor, name):
    command = 'nova --os-project-id %s boot --image %s --flavor %s %s' % (dest_project_id, bootable_image_id, flavor, name)
    instance = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    return instance

def take_snapshot(instance_id, instance_name=None, public=False):
    if not instance_name:
        instance_name = instance_id
    command = 'nova image-create --show %s temp-snap-%s' % (instance_id, instance_name)
    snapshot = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    if public:
        command = 'glance image-update --visibility public %s' % source_instance_snapshot['id']
    else:
        command = 'glance image-update --visibility private %s' % source_instance_snapshot['id']
    snapshot = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    return snapshot


def main(argv):

    source_instance_name=argv[-4]
    source_project_name=argv[-3]
    dest_instance_name=argv[-2]
    dest_project_name=argv[-1]

    # print source_instance_name, source_project_name, dest_instance_name, dest_project_name

    env = dict(os.environ.copy().items() + read_adminopenrc().items())

    project_list = parse_list_output(Popen('openstack project list'.split(), stdout=PIPE, env=env).communicate()[0])
    instance_list = parse_list_output(Popen('nova list --all-tenants'.split(), stdout=PIPE, env=env).communicate()[0])
    volume_list = parse_list_output(Popen('nova volume-list --all-tenants'.split(), stdout=PIPE, env=env).communicate()[0])

    source_project = get(project_list, 'name', source_project_name)[0]
    dest_project = get(project_list, 'name', dest_project_name)[0]

    similar_instance_list = get(instance_list, 'name', source_instance_name)
    source_instance_id = get(similar_instance_list, 'tenant id', source_project['id'])[0]['id']
    command = 'nova show %s' % source_instance_id
    source_instance = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    attached_volumes_list = get(volume_list, 'attached to', source_instance['id'])

    volume_info_list = []
    for volume in attached_volumes_list:
        command = 'nova volume-show %s' % volume['id']
        volume_info = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
        volume_info_list.append(volume_info)

    attached_volumes_list = volume_info_list

    # Instance was booted from a volume
    if get(attached_volumes_list, 'bootable', 'true'):

        # Snapshot the attached volumes
        snapshot_info_list = create_volume_snapshot(attached_volumes_list)
        # Recreate volumes from snapshots
        volume_from_snapshot_list = create_volume_from_snapshot(snapshot_info_list)
        # Create transfer requests
        transfer_request_list = create_volume_transfer_request(volume_from_snapshot_list)
        # Accept transfer requests
        accept_volume_transfer_request(transfer_request_list, dest_project['id'])
        # Boot from volume
        dest_instance = boot_from_volume(dest_project['id'], get(volume_from_snapshot_list, 'bootable', True)[0]['id'], source_instance['flavor'].split[0], dest_instance_name)
        # Attach volumes to the instance
        attach_volumes(dest_instance['id'], get(volume_from_snapshot_list, 'bootable', False))

    # Instance is ephemeral
    else:

        # Snapshot the instance
        source_instance_snapshot = take_snapshot(source_instance['id'], instance_name=source_instance['name'], public=True):
        # Snapshot the attached volumes
        snapshot_info_list = create_volume_snapshot(attached_volumes_list)
        # Recreate volumes from snapshots
        volume_from_snapshot_list = create_volume_from_snapshot(snapshot_info_list)
        # Create transfer requests
        transfer_request_list = create_volume_transfer_request(volume_from_snapshot_list)
        # Accept transfer requests
        accept_volume_transfer_request(transfer_request_list, dest_project['id'])
        # Recreate instance from snapshot
        dest_instance = boot_from_image(dest_project['id'], source_instance_snapshot['id'], source_instance['flavor'].split()[0], dest_instance_name)
        # Attach volumes to the instance
        attach_volumes(dest_instance['id'], volume_from_snapshot_list)


if __name__ == '__main__':
    main(sys.argv)
