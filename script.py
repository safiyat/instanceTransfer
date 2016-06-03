#! /usr/bin/env python

import argparse
from oslo_utils import uuidutils
import sys
sys.path.insert(0, 'utils.zip')
import keystoneutils
import novautils
import glanceutils
from utils import get_parser

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

Author: Md Safiyat Reza <md.reza@snapdeal.com>
"""


def main(argv):

    p = get_parser()
    # Adding additional hidden args so that it doesn't break.
    p.add_argument('--source-instance', help=argparse.SUPPRESS)
    p.add_argument('--dest-instance', help=argparse.SUPPRESS)
    p.add_argument('--dest-project', help=argparse.SUPPRESS)
    p.add_argument('--move', help=argparse.SUPPRESS)
    os_args = p.parse_args()

    parser = argparse.ArgumentParser(description='Transfer VMs on OpenStack' +
                                     ' from one project to another.')
    parser.add_argument('--source-instance', type=str, required=True,
                        help='UUID of the instance to be transferred.',
                        metavar='instance_uuid',
                        dest='source_instance_uuid')
    parser.add_argument('--dest-instance', type=str, required=False,
                        help='Name of the destination instance after ' +
                        'transfer (default: source instance name).',
                        metavar='instance_name', dest='dest_instance_name')
    parser.add_argument('--dest-project', type=str, required=True,
                        help='Name of the project to which the destination' +
                        ' instance will belong.', metavar='project_name',
                        dest='dest_project_name')
    parser.add_argument('--move', action='store_true')

    args = parser.parse_args()
    source_instance_uuid = args.source_instance_uuid

    if not uuidutils.is_uuid_like(source_instance_uuid):
        print 'Source instance UUID is not a proper UUID. Please correct.'
        sys.exit(-1)

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

    kc = keystoneutils.get_client(os_args)
    nc = novautils.get_client(kc.session)
    gc = glanceutils.get_client(kc.session)

    print "Gathering facts..."
    source_instance = nc.servers.get(source_instance_uuid)

    source_project = kc.projects.get(source_instance.tenant_id)
    dest_project = kc.projects.find(name=args.dest_project_name)

    if source_project == dest_project:
        print "The source and destination projects are same!"
        sys.exit(-1)

    if args.dest_instance_name:
        dest_instance_name = args.dest_instance_name
    else:
        dest_instance_name = source_instance.name

    attached_volume_ids = source_instance.to_dict()[
        'os-extended-volumes:volumes_attached']
    attached_volumes = []
    ephemeral = True
    for volume_id in attached_volume_ids:
        volume = nc.volumes.get(volume_id['id'])
        if volume.attachments[0]['device'] == '/dev/vda':
            ephemeral = False
        attached_volumes.append(volume)

    if ephemeral:
        print "Creating instance snapshot..."
        # gc.


if __name__ == '__main__':
    main(sys.argv)
