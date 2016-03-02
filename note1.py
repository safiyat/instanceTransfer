import keystoneclient.v3.client as ksclient

from novaclient import client as novaclient

import os

def get_keystone_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['password'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['tenant_name'] = os.environ['OS_TENANT_NAME']
    return d

def get_nova_creds():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['api_key'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['project_id'] = os.environ['OS_TENANT_NAME']
    return d



# ks_creds = {}
# ks_creds['controller']= '10.42.206.14'
# ks_creds['username']='osadmin'
# ks_creds['password']='snapdeal@1234'
# ks_creds['tenant_name']='admin'
# ks_creds['auth_url']='http://' + ks_creds['controller'] + ':35357/v3'

# ks_creds = get_keystone_creds()

# keystone = ksclient.Client(auth_url=ks_creds['auth_url'], username=ks_creds['username'], password=ks_creds['password'], tenant_name=ks_creds['tenant_name'])
