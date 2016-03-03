#! /usr/bin/env bash

# Input parameters
#     Source Instance Name
#     Source Project Name
#     Destination Instance Name
#     Destination Project Name

source_instance=$1
source_project=$2
dest_instance=$3
dest_project=$4

source admin-openrc.sh

project_list=$(openstack project list)
instance_list=$(nova list --all-tenants)
volume_list=$(nova volume-list --all-tenants)

# Get the project IDs
source_project_id=$(echo "$project_list" | grep -i "$source_project" | awk '{print $2}')
dest_project_id=$(echo "$project_list" | grep -i "$dest_project" | awk '{print $2}')

# Get the instance ID
source_instance_id=$(echo "$instance_list" | awk "/$source_project_id/ && /$source_instance/" | awk '{print $2}')


# echo $source_project_id $dest_project_id $source_instance_id

attached_volumes=$(echo "$volume_list" | grep -i "$source_instance_id" | awk '{print $2}')

bootable_volume=false

for volume in $attached_volumes
do
    if [ -n "$(nova volume-show $volume | awk '/bootable/ && /true/')" ]
    then
        bootable_volume=$volume
        break
    fi
done

# Instance was booted from volume
if [ "$bootable_volume" != false ]
then

    # Create Snapshots
    local index=0
    bootable_snapshot=false
    for volume in $attached_volumes
    do
        volume_snapshot[index]=$(cinder snapshot-create --force True  $volume | grep " id " | awk '{print $4}')
        if [ "$volume" = "$bootable_volume" ]
        then
            bootable_snapshot=$volume_snapshot[index]
        fi
        let index++
    done

    # Recreate volumes from snapshots
    local index=0
    for snapshot in "${volume_snapshot[@]}"
    do
        volume_from_snapshot[index]=$(cinder create --snapshot-id $snapshot | grep " id " | awk '{print $4}')
        if [ "$snapshot" = "$bootable_snapshot" ]
        then
            volume_from_bootable_snapshot=$volume_from_snapshot[index]
        fi
        let index++
    done

    # Create transfer requests
    local index=0
    for volume in "${volume_from_snapshot[@]}"
    do
        output=$(cinder transfer-create $volume)
        transfer_id[index]=$(echo "$output"  | grep -i " id " | awk '{print $4}')
        auth_key[index]=$(echo "$output"  | grep -i "auth_key" | awk '{print $4}')
        let index++
    done

    # Accept transfer requests
    local index=0
    for volume in "${volume_from_snapshot[@]}"
    do
        cinder --os-project-name $dest_project transfer-accept $transfer_id[index] $auth_key[index]
    done

    # Boot from volume
    nova boot --boot-volume $volume_from_bootable_snapshot $dest_instance
fi
