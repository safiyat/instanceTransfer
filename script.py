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

def print_objects_created():
    global objects_created
    for object_dict in objects_created:
        key = object_dict.keys()[0]
        print '%s:' % key
        if type(object_dict[key]) is not list:
            object_dict[key] = list(object_dict[key])
        for obj in object_dict[key]:
            print '\t %s' % obj['id']
        print

def create_volume_snapshot(volumes, wait_for_available=10):
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
        ###
        # att = get(volume_info_list, 'id', volume['id'])[0]['attachments']
        # snapshot_info['device'] = get(json.loads(att), 'server_id', source_instance['id'])[0]['device']
        ###
        snapshot_info['device'] = get(json.loads(volume['attachments']), 'server_id', source_instance['id'])[0]['device']
        ###
        s.append(snapshot_info)
    ##########################
    if wait_for_available > 0:
        wait = 0
        again=False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for snapshot in s:
                command = 'cinder snapshot-show %s' % snapshot['id']
                status = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])['status']
                if status == 'error':
                    # clean up and take snapshot again
                    command = 'cinder snapshot-delete %s' % snapshot['id']
                    a = Popen(command.split(), stdout=PIPE, env=env).communicate()[0]
                    command = 'cinder snapshot-create --force True %s' % snapshot['volume_id']
                    snapshot_info = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
                    snapshot_info['bootable'] = snapshot['bootable']
                    snapshot_info['device'] = snapshot['device']
                    snapshot = snapshot_info
                    again = True
                    break
                elif status == 'creating':
                    again = True
                    break
                else:    # status == 'available'
                    snapshot['status'] = status
                    pass
            if again:
                continue
            else:
                break
        if again:    # Loop ended due to timeout
            print 'Error creating volume snapshot!'
            print 'The following entities were created in the process:'
            print_objects_created()
            sys.exit(0)
    ##########################
    return s

def create_volume_from_snapshot(snapshots, wait_for_available=10):
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
    ##########################
    if wait_for_available > 0:
        wait = 0
        again=False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for volume in v:
                command = 'cinder show %s' % volume['id']
                status = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])['status']
                if status == 'error':
                    # clean up and take snapshot again
                    command = 'cinder delete %s' % volume['id']
                    a = Popen(command.split(), stdout=PIPE, env=env).communicate()[0]
                    command = 'cinder create --snapshot-id %s' % volume['snapshot_id']
                    volume_info = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
                    volume_info['bootable'] = volume['bootable']
                    volume_info['device'] = volume['device']
                    volume = volume_info
                    again = True
                    break
                elif status == 'creating':
                    again = True
                    break
                else:    # status == 'available'
                    volume['status'] = status
                    pass
            if again:
                continue
            else:
                break
        if again:    # Loop ended due to timeout
            print 'Error creating volume from snapshot!'
            print 'The following entities were created in the process:'
            print_objects_created()
            sys.exit(0)
    ##########################
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

def boot_from_volume(dest_project_id, bootable_volume_id, flavor, name, wait_for_available=10):
    command = 'nova --os-project-id %s boot --boot-volume %s --flavor %s %s' % (dest_project_id, bootable_volume_id, flavor, name)
    instance = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
    ##########################
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            command = 'nova show %s' % instance['id']
            status = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])['status']
            if status == 'ERROR':
                # clean up and create instance again
                command = 'nova delete %s' % instance['id']
                a = Popen(command.split(), stdout=PIPE, env=env).communicate()[0]
                command = 'nova --os-project-id %s boot --boot-volume %s --flavor %s %s' % (dest_project_id, bootable_volume_id, flavor, name)
                instance = parse_output(Popen(command.split(), stdout=PIPE, env=env).communicate()[0])
                again = True
                break
            elif status == 'BUILD':
                again = True
            else:    # status == 'ACTIVE'
                instance['status'] = status
                break
        if again:    # Loop ended due to timeout
            print 'Error booting instance from volume!'
            print 'The following entities were created in the process:'
            print_objects_created()
            raise Exception()
    ##########################
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

    objects_created = []

    # Instance was booted from a volume
    if any('/dev/vda' in volume['attachments'] for volume in attached_volumes_list):

        # Snapshot the attached volumes
        snapshot_info_list = create_volume_snapshot(attached_volumes_list, 10)
        objects_created.append({'volume_snapshot':snapshot_info_list})
        # Recreate volumes from snapshots
        volume_from_snapshot_list = create_volume_from_snapshot(snapshot_info_list)
        objects_created.append({'volume':volume_from_snapshot_list})
        # Create transfer requests
        transfer_request_list = create_volume_transfer_request(volume_from_snapshot_list)
        objects_created.append({'volume_transfer_request':transfer_request_list})
        # Accept transfer requests
        a = accept_volume_transfer_request(transfer_request_list, dest_project['id'])
        # Boot from volume
        dest_instance = boot_from_volume(dest_project['id'], get(volume_from_snapshot_list, 'device', '/dev/vda')[0]['id'], source_instance['flavor'].split()[0], dest_instance_name)
        objects_created.append({'instance':dest_instance})
        # Attach volumes to the instance
        volume_from_snapshot_list.remove(get(volume_from_snapshot_list, 'device', '/dev/vda')[0])
        attach_volumes(dest_instance['id'], volume_from_snapshot_list)

    # Instance is ephemeral
    else:

        # Snapshot the instance
        source_instance_snapshot = take_snapshot(source_instance['id'], instance_name=source_instance['name'], public=True):
        objects_created.append({'instance_snapshot':source_instance_snapshot})
        # Snapshot the attached volumes
        snapshot_info_list = create_volume_snapshot(attached_volumes_list)
        objects_created.append({'volume_snapshot':snapshot_info_list})
        # Recreate volumes from snapshots
        volume_from_snapshot_list = create_volume_from_snapshot(snapshot_info_list)
        objects_created.append({'volume':volume_from_snapshot_list})
        # Create transfer requests
        transfer_request_list = create_volume_transfer_request(volume_from_snapshot_list)
        objects_created.append({'transfer_request':transfer_request_list})
        # Accept transfer requests
        accept_volume_transfer_request(transfer_request_list, dest_project['id'])
        # Recreate instance from snapshot
        dest_instance = boot_from_image(dest_project['id'], source_instance_snapshot['id'], source_instance['flavor'].split()[0], dest_instance_name)
        objects_created.append({'instance':dest_instance})
        # Attach volumes to the instance
        attach_volumes(dest_instance['id'], volume_from_snapshot_list)


if __name__ == '__main__':
    main(sys.argv)
