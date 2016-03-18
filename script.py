#! /usr/bin/env python

"""
OpenStack Instance Transfer

This script facilitates the transfer of instances between one project and
another.

The script can be thought of being analogous to the `cp` and `mv` commands in
bashutils, albeit copying and moving instances between projects.

Syntax:

    sdc-transfer-instance --source-instance <source-instance-uuid> \
      --dest-project <destination-project-name | destination-project-uuid> \
      --dest-instance <destination-instance-name> [--move]

--source-instance <source-instance-uuid>
    The uuid of the instance to be transferred.
    Required parameter.

--dest-project <destination-project-name | destination-project-uuid>
    The name or the uuid of the destination project in which the project is to
    be transferred.
    Required parameter.

--dest-instance <destination-instance-name>
    The name of the instance to be created in the destination project.
    Required parameter.

--move
    Transfers the instance from the source project to the destination project
    and removes the instance from the source project.
    Equivalent to `mv` command.
    Optional parameter.

Note:
    Please ensure that you have sourced the credentials of an admin user who is
    in both the projects before running the script.

Author: Md Safiiyat Reza <md.reza@snapdeal.com>
"""


import os
import sys
import json
import time
import argparse
import re
from oslo_utils import uuidutils
from subprocess import Popen, PIPE
from distutils.spawn import find_executable


def parse_list_output(output):
    """Parse the output of list commands (like `openstack project list`)."""
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
    """
    Parse the output of commands (like `nova boot`) that print in tabular form.
    """
    lines = output.splitlines()[3:-1]
    r = {}
    for line in lines:
        kv = filter(None, line.split('|'))
        kv = [x.strip() for x in kv]
        r = dict(r.items() + [tuple(kv)])
    return r


def get(list_of_dict, key, value):
    """
    Returns the dictionary in a list of dictionaries that has the value of
    'key' as 'value'.
    """
    o = filter(lambda dictionary: dictionary[key] == value, list_of_dict)
    return o


def print_objects_created(objects_created):
    """
    Print a list of instance/volume snapshots, volumes etc that were created
    during the execution of the script.
    """
    for object_dict in objects_created:
        key = object_dict.keys()[0]
        print '%s:' % key
        if type(object_dict[key]) is not list:
            object_dict[key] = [object_dict[key]]
        for obj in object_dict[key]:
            print '\t %s' % obj['id']
        print


def check_environment():
    """
    Check if the openstack clients are installed and available to call the
    necessary commands.
    """
    if not find_executable('nova'):
        return False
    if not find_executable('openstack'):
        return False
    if not find_executable('glance'):
        return False
    if not find_executable('cinder'):
        return False
    return True


def get_project_list():
    """Return list of all the projects in OpenStack."""
    return parse_list_output(Popen(
        'openstack project list'.split(), stdout=PIPE,
        stderr=PIPE).communicate()[0])


def get_instance_list():
    """Return list of all the instances in OpenStack."""
    return parse_list_output(Popen('nova list --all-tenants'.split(),
                                   stdout=PIPE).communicate()[0])


def get_volume_list():
    """Return list of all the volumes in OpenStack."""
    return parse_list_output(Popen('cinder list --all-tenants'.split(),
                                   stdout=PIPE).communicate()[0])


def get_project(project_name, project_list):
    """
    Get the details of the project by its name/uuid from the project list.
    """
    uuid = re.compile('[0-9a-f]{32}')
    try:
        if uuid.match(project_name):
            project = get(project_list, 'id', project_name)[0]
        else:
            project = get(project_list, 'name', project_name)[0]
    except:
        print "Project '%s' not found." % project_name
        sys.exit(-1)
    return project


def get_lists():
    """Get the list of all the projects, instances and volumes in OpenStack."""
    try:
        project_list = get_project_list()
        instance_list = get_instance_list()
        volume_list = get_volume_list()
    except:
        if 'OS_USERNAME' in os.environ:
            print "Error gathering facts! Please ensure that the user" +\
                " %s has admin privileges." % os.environ['OS_USERNAME']
        else:
            print "Error gathering facts! Please ensure that the openstack" +\
                " credentials of an admin user are set as environment" + \
                " variables."
        sys.exit(-1)
    return project_list, instance_list, volume_list


def get_instance(instance_name, instance_list, project):
    """
    Get the details of the instance by its name/uuid and project from the
    instance list.
    """
    uuid = re.compile('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}' +
                      '-[0-9a-f]{4}-[0-9a-f]{12}')
    try:
        if uuid.match(instance_name):
            instance_id = instance_name
        else:
            similar_instance_list = get(instance_list,
                                        'name', instance_name)
            instance_id = get(similar_instance_list, 'tenant id',
                              project['id'])[0]['id']
        command = 'nova show %s' % instance_id
        instance = parse_output(Popen(command.split(), stdout=PIPE,
                                      stderr=PIPE).communicate()[0])
    except:
        print "Instance '%s' not found in project %s." % \
            (instance_name, project['name'])
        sys.exit(-1)
    if not instance:
        print "Instance '%s' not found in project %s." % \
            (instance_name, project['name'])
        sys.exit(-1)
    return instance


def booted_from_volume(volumes_list):
    """Check if any of the volumes in the volumes_list has been booted from."""
    if any('/dev/vda' in volume['attachments'] for volume in
           volumes_list):
        return True
    return False


def bootable_volume(volumes):
    """Return the volume booted from the list of volumes."""
    for volume in volumes:
        if '/dev/vda' in volume['attachments']:
            return volume


def get_volume_info(volumes):
    """Get the individual volume information about all the volumes by id."""
    if type(volumes) is not list:
        volumes = [volumes]
    volume_info_list = []
    for volume in volumes:
        command = 'cinder show %s' % volume['id']
        volume_info = parse_output(Popen(command.split(), stdout=PIPE
                                         ).communicate()[0])
        att = volume_info['attachments'].replace("'", "\"").replace(
            "u\"", "\"").replace(" None,", " \"None\",")
        volume_info['device'] = json.loads(att)[0]['device']
        volume_info_list.append(volume_info)
    return volume_info_list


def create_volume_snapshot(volumes, source_instance, objects_created,
                           wait_for_available=50):
    """Create snapshots of the volumes."""
    if type(volumes) is not list:
        volumes = [volumes]
    s = []
    for volume in volumes:
        command = 'cinder snapshot-create --force True %s' % volume['id']
        snapshot_info = parse_output(Popen(command.split(),
                                           stdout=PIPE).communicate()[0])
        if volume['bootable'] == 'true':
            snapshot_info['bootable'] = True
        else:
            snapshot_info['bootable'] = False
        att = volume['attachments'].replace("'", "\"").replace(
            "u\"", "\"").replace(" None,", " \"None\",")
        snapshot_info['device'] = get(json.loads(att), 'server_id',
                                      source_instance['id'])[0]['device']
        s.append(snapshot_info)
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for snapshot in s:
                command = 'cinder snapshot-show %s' % snapshot['id']
                status = parse_output(Popen(command.split(), stdout=PIPE
                                            ).communicate()[0])['status']
                if status == 'error':
                    # clean up and take snapshot again
                    command = 'cinder snapshot-delete %s' % snapshot['id']
                    a = Popen(command.split(), stdout=PIPE).communicate()[0]
                    command = 'cinder snapshot-create --force True %s' % \
                              snapshot['volume_id']
                    snapshot_info = parse_output(Popen(command.split(),
                                                       stdout=PIPE
                                                       ).communicate()[0])
                    snapshot_info['bootable'] = snapshot['bootable']
                    snapshot_info['device'] = snapshot['device']
                    snapshot = snapshot_info
                    again = True
                    break
                elif status == 'creating':
                    again = True
                    break
                elif status == 'available':
                    snapshot['status'] = status
                    pass
            if again:
                continue
            else:
                break
        if again:    # Loop ended due to timeout
            print 'Error creating volume snapshot!'
            print 'The following entities were created in the process:'
            print_objects_created(objects_created)
            sys.exit(-1)
    return s


def delete_volume_snapshot(volume_snapshots):
    """Delete snapshots of the volumes."""
    if type(volume_snapshots) is not list:
        volumes = [volume_snapshots]
    command = 'cinder snapshot-delete %s' % \
              " ".join(snapshot['id'] for snapshot in volume_snapshots)
    d = Popen(command.split(), stdout=PIPE).communicate()[0]


def create_volume_from_snapshot(snapshots, objects_created,
                                wait_for_available=10):
    """Create volumes from the snapshots."""
    if type(snapshots) is not list:
        snapshots = [snapshots]
    v = []
    for snapshot in snapshots:
        command = 'cinder create --snapshot-id %s' % snapshot['id']
        volume_from_snapshot = parse_output(Popen(
            command.split(), stdout=PIPE).communicate()[0])
        volume_from_snapshot['device'] = snapshot['device']
        volume_from_snapshot['bootable'] = snapshot['bootable']
        v.append(volume_from_snapshot)
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for volume in v:
                command = 'cinder show %s' % volume['id']
                status = parse_output(Popen(command.split(), stdout=PIPE
                                            ).communicate()[0])['status']
                if status == 'error':
                    # clean up and create volume again
                    command = 'cinder delete %s' % volume['id']
                    a = Popen(command.split(), stdout=PIPE).communicate()[0]
                    command = 'cinder create --snapshot-id %s' % \
                              volume['snapshot_id']
                    volume_info = parse_output(Popen(
                        command.split(), stdout=PIPE).communicate()[0])
                    volume_info['bootable'] = volume['bootable']
                    volume_info['device'] = volume['device']
                    volume = volume_info
                    again = True
                    break
                elif status == 'creating':
                    again = True
                    break
                elif status == 'available':
                    volume['status'] = status
                    pass
            if again:
                continue
            else:
                break
        if again:    # Loop ended due to timeout
            print 'Error creating volume from snapshot!'
            print 'The following entities were created in the process:'
            print_objects_created(objects_created)
            sys.exit(-1)
    return v


def create_volume_transfer_request(volumes):
    """Create transfer requests"""
    if type(volumes) is not list:
        volumes = [volumes]
    t = []
    for volume in volumes:
        command = 'cinder transfer-create %s' % volume['id']
        transfer_request = parse_output(Popen(command.split(), stdout=PIPE
                                              ).communicate()[0])
        t.append(transfer_request)
    return t


def accept_volume_transfer_request(transfer_requests, recipient_project_id):
    """Accept transfer requests"""
    if type(transfer_requests) is not list:
        transfer_requests = [transfer_requests]
    t = []
    for request in transfer_requests:
        command = 'cinder --os-project-id %s transfer-accept %s %s' % \
                  (recipient_project_id, request['id'], request['auth_key'])
        transfer_accept = parse_output(Popen(command.split(), stdout=PIPE
                                             ).communicate()[0])
        t.append(transfer_accept)
    return t


def attach_volumes(instance_id, volumes):
    """Attach volumes to the given instance."""
    if type(volumes) is not list:
        volumes = [volumes]
    for volume in volumes:
        command = 'nova volume-attach %s %s %s' % (instance_id, volume['id'],
                                                   volume['device'])
        dest_attachment = parse_output(Popen(command.split(), stdout=PIPE
                                             ).communicate()[0])


def boot_from_volume(dest_project_id, bootable_volume_id, flavor, name,
                     objects_created, wait_for_available=50):
    """
    Boot an instance from volume in the destination project of the given name
    and flavor.
    """
    command = 'nova --os-project-id %s boot --boot-volume %s --flavor %s %s'\
              % (dest_project_id, bootable_volume_id, flavor, name)
    instance = parse_output(
        Popen(command.split(), stdout=PIPE).communicate()[0])
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            command = 'nova show %s' % instance['id']
            status = parse_output(Popen(command.split(), stdout=PIPE
                                        ).communicate()[0])['status']
            if status == 'ERROR':
                # clean up and create instance again
                command = 'nova delete %s' % instance['id']
                a = Popen(command.split(), stdout=PIPE).communicate()[0]
                command = 'nova --os-project-id %s boot --boot-volume %s' + \
                          '--flavor %s %s' % (dest_project_id,
                                              bootable_volume_id, flavor, name)
                instance = parse_output(Popen(command.split(), stdout=PIPE
                                              ).communicate()[0])
                again = True
            elif status == 'BUILD':
                again = True
            elif status == 'ACTIVE':
                instance['status'] = status
                break
        if again:    # Loop ended due to timeout
            print 'Error booting instance from volume!'
            print 'The following entities were created in the process:'
            print_objects_created(objects_created)
            sys.exit(-1)
    return instance


def boot_from_image(dest_project_id, bootable_image_id, flavor, name,
                    objects_created, wait_for_available=50):
    """
    Boot an instance from image in the destination project of the given name
    and flavor.
    """
    command = 'nova --os-project-id %s boot --image %s --flavor %s %s' % \
              (dest_project_id, bootable_image_id, flavor, name)
    instance = parse_output(Popen(command.split(), stdout=PIPE
                                  ).communicate()[0])
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            command = 'nova show %s' % instance['id']
            status = parse_output(Popen(command.split(), stdout=PIPE
                                        ).communicate()[0])['status']
            if status == 'ERROR':
                # clean up and create instance again
                command = 'nova delete %s' % instance['id']
                a = Popen(command.split(), stdout=PIPE).communicate()[0]
                command = 'nova --os-project-id %s boot --image %s --flavor' +\
                          ' %s %s' % (dest_project_id, bootable_image_id,
                                      flavor, name)
                instance = parse_output(Popen(command.split(), stdout=PIPE
                                              ).communicate()[0])
                again = True
            elif status == 'BUILD':
                again = True
            elif status == 'ACTIVE':
                instance['status'] = status
                break
        if again:    # loop ended due to timeout
            print 'error booting instance from image!'
            print 'the following entities were created in the process:'
            print_objects_created(objects_created)
            sys.exit(-1)
    return instance


def delete_instances(instances, wait_for_available=20):
    """Delete the instances in the list."""
    if type(instances) is not list:
        instances = [instances]
    for instance in instances:
        command = 'nova delete %s' % instance['id']
        a = Popen(command.split(), stdout=PIPE).communicate()[0]
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            for instance in instances:
                command = 'nova show %s' % instance['id']
                show = parse_output(Popen(command.split(), stdout=PIPE,
                                          stderr=PIPE).communicate()[0])
                if 'status' in show:
                    again = True
                    break
            if again:
                continue
            else:
                break
        if again:    # Loop ended due to timeout
            print 'Error deleting instance!!'
            sys.exit(-1)


def delete_volumes(volumes):
    """Delete the volumes in the list."""
    if type(volumes) is not list:
        volumes = [volumes]
    for volume in volumes:
        command = 'cinder delete %s' % volume['id']
        a = Popen(command.split(), stdout=PIPE, stderr=PIPE).communicate()[0]


def take_snapshot(instance_id, objects_created, instance_name=None,
                  public=False, wait_for_available=120):
    """
    Take snapshot of the given instance and set it to public if specified.
    """
    if not instance_name:
        instance_name = instance_id
    command = 'nova image-create --show %s temp-snap-%s' % (instance_id,
                                                            instance_name)
    snapshot = parse_output(Popen(command.split(), stdout=PIPE
                                  ).communicate()[0])
    if wait_for_available > 0:
        wait = 0
        again = False
        while wait < wait_for_available:
            time.sleep(5)
            wait += 5
            again = False
            command = 'glance image-show %s' % snapshot['id']
            status = parse_output(Popen(command.split(), stdout=PIPE
                                        ).communicate()[0])['status']
            if status == 'error':
                # clean up and create snapshot again
                command = 'glance image-delete %s' % snapshot['id']
                a = Popen(command.split(), stdout=PIPE).communicate()[0]
                command = 'nova image-create --show %s temp-snap-%s' % \
                          (instance_id, instance_name)
                snapshot = parse_output(Popen(command.split(), stdout=PIPE
                                              ).communicate()[0])
                again = True
            elif status == 'queued' or status == 'saving':
                again = True
            elif status == 'active':
                snapshot['status'] = status
                break
        if again:    # loop ended due to timeout
            print 'error snapshotting instance!'
            print 'the following entities were created in the process:'
            print_objects_created(objects_created)
            sys.exit(-1)
    if public:
        command = 'glance image-update --visibility public %s' % snapshot['id']
    else:
        command = 'glance image-update --visibility private %s' % \
                  snapshot['id']
    snapshot = parse_output(Popen(
        command.split(), stdout=PIPE).communicate()[0])
    return snapshot


def delete_snapshot(snapshots):
    """Delete image snapshots."""
    if type(snapshots) is not list:
        snapshots = [snapshots]
    command = 'nova image-delete %s' % \
              " ".join(snapshot['id'] for snapshot in snapshots)
    snapshot = parse_output(Popen(
        command.split(), stdout=PIPE).communicate()[0])


def main(argv):

    parser = argparse.ArgumentParser(description='Transfer VMs on OpenStack' +
                                     'from one project to another.')

    parser.add_argument('--source-instance', type=str, required=True,
                        help='Name of the instance to be transferred.',
                        metavar='instance_name', dest='source_instance_name')
    parser.add_argument('--source-project', type=str, required=True,
                        help='Name of the project to which the source' +
                        ' instance belongs.', metavar='project_name',
                        dest='source_project_name')
    parser.add_argument('--dest-instance', type=str, required=True,
                        help='Name of the instance to be transferred to.',
                        metavar='instance_name', dest='dest_instance_name')
    parser.add_argument('--dest-project', type=str, required=True,
                        help='Name of the project to which the destination' +
                        ' instance will belong.', metavar='project_name',
                        dest='dest_project_name')
    parser.add_argument('--move', action='store_true')

    args = parser.parse_args()

    source_instance_name = args.source_instance_name
    source_project_name = args.source_project_name
    dest_instance_name = args.dest_instance_name
    dest_project_name = args.dest_project_name
    if args.move:
        move = True
        print "Are you sure you want to MOVE the instance? The source " + \
            "instance will be deleted."
        captcha = uuidutils.generate_uuid()[:6]
        text = raw_input("Please type '%s' (without quotes) and" % captcha +
                         " press enter to confirm: ")
        if text != captcha:
            print "Incorrect input!"
            sys.exit(-1)
    else:
        move = False

    if check_environment() is not True:
        print "Please install all of openstack, nova, glance and cinder" + \
            "clients before running this script."
        sys.exit(-1)

    print "Gathering facts..."
    project_list, instance_list, volume_list = get_lists()

    source_project = get_project(source_project_name, project_list)
    dest_project = get_project(dest_project_name, project_list)

    if source_project['id'] == dest_project['id']:
        print "The source and destination projects are same!"
        sys.exit(-1)

    source_instance = get_instance(source_instance_name, instance_list,
                                   source_project)

    attached_volumes = get(volume_list, 'attached to',
                           source_instance['id'])
    attached_volumes_list = get_volume_info(attached_volumes)

    objects_created = []

    # Instance was booted from a volume
    if booted_from_volume(attached_volumes_list):
        if not move:
            # Snapshot the attached volumes
            print "Creating volume snapshots..."
            snapshot_info_list = create_volume_snapshot(attached_volumes_list,
                                                        source_instance,
                                                        objects_created)
            objects_created.append({'volume_snapshot': snapshot_info_list})
            # Recreate volumes from snapshots
            print "Creating volumes from created snapshots..."
            volume_from_snapshot_list = create_volume_from_snapshot(
                snapshot_info_list, objects_created)
            objects_created.append({'volume': volume_from_snapshot_list})
        else:
            print "Creating root volume snapshot..."
            root_volume = bootable_volume(attached_volumes_list)
            snapshot_info_list = create_volume_snapshot(root_volume,
                                                        source_instance,
                                                        objects_created)
            objects_created.append({'volume_snapshot': snapshot_info_list})
            print "Deleting source instance (also freeing up attached " + \
                "volumes)..."
            delete_instances(source_instance)
            print "Creating volume from snapshot..."
            volume_from_snapshot = create_volume_from_snapshot(
                snapshot_info_list, objects_created)
            objects_created.append({'volume': volume_from_snapshot})
            attached_volumes_list.remove(root_volume)
            volume_from_snapshot_list = attached_volumes_list + \
                                        volume_from_snapshot
        # Create transfer requests
        print "Initializing transfer requests..."
        transfer_request_list = create_volume_transfer_request(
            volume_from_snapshot_list)
        objects_created.append({'volume_transfer_request':
                                transfer_request_list})
        # Accept transfer requests
        print "Accepting transfer requests..."
        a = accept_volume_transfer_request(transfer_request_list,
                                           dest_project['id'])
        # Boot from volume
        print "Booting from volume..."
        dest_instance = boot_from_volume(dest_project['id'],
                                         get(volume_from_snapshot_list,
                                             'device', '/dev/vda')[0]['id'],
                                         source_instance['flavor'].split()[0],
                                         dest_instance_name, objects_created)
        objects_created.append({'instance': dest_instance})
        # Attach volumes to the instance, after removing vda from the list.
        print "Attaching volumes to the newly booted instance..."
        volume_from_snapshot_list.remove(get(volume_from_snapshot_list,
                                             'device', '/dev/vda')[0])
        attach_volumes(dest_instance['id'], volume_from_snapshot_list)
        # Delete volume snapshots
        print "Cleaning up snapshots..."
        delete_volume_snapshot(snapshot_info_list)
        if move:
            print "Deleting root volume..."
            delete_volumes(root_volume)

    # Instance is ephemeral
    else:
        # Snapshot the instance
        print "Creating instance snapshot..."
        source_instance_snapshot = take_snapshot(
            source_instance['id'], objects_created,
            instance_name=source_instance['name'], public=True)
        objects_created.append({'instance_snapshot': source_instance_snapshot})
        if not move:
            # Snapshot the attached volumes
            print "Creating volume snapshots..."
            snapshot_info_list = create_volume_snapshot(attached_volumes_list,
                                                        source_instance,
                                                        objects_created)
            objects_created.append({'volume_snapshot': snapshot_info_list})
            # Recreate volumes from snapshots
            print "Creating volumes from created snapshots..."
            volume_from_snapshot_list = create_volume_from_snapshot(
                snapshot_info_list, objects_created)
            objects_created.append({'volume': volume_from_snapshot_list})
        else:
            print "Deleting source instance (and freeing up attached " + \
                "volumes)..."
            delete_instances(source_instance)
            volume_from_snapshot_list = attached_volumes_list
        # Create transfer requests
        print "Initializing transfer requests..."
        transfer_request_list = create_volume_transfer_request(
            volume_from_snapshot_list)
        objects_created.append({'transfer_request': transfer_request_list})
        # Accept transfer requests
        print "Accepting transfer requests..."
        a = accept_volume_transfer_request(transfer_request_list,
                                           dest_project['id'])
        # Recreate instance from snapshot
        print "Booting from snapshot..."
        dest_instance = boot_from_image(dest_project['id'],
                                        source_instance_snapshot['id'],
                                        source_instance['flavor'].split()[0],
                                        dest_instance_name, objects_created)
        objects_created.append({'instance': dest_instance})
        # Attach volumes to the instance
        print "Attaching volumes to the newly created instance..."
        attach_volumes(dest_instance['id'], volume_from_snapshot_list)
        if not move:
            # Delete volume snapshots
            print "Cleaning up volume snapshots..."
            delete_volume_snapshot(snapshot_info_list)
        # Delete instance snapshot
        print "Cleaning up instance snapshots..."
        delete_snapshot(source_instance_snapshot)

if __name__ == '__main__':
    main(sys.argv)
