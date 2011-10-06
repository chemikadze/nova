# Copyright 2011 Grid Dynamics
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import json
from urllib import urlencode
import webob

from nova import context
from nova import db
from nova.db.sqlalchemy.api import require_admin_context, require_context
from nova import exception
from nova import test
from nova.tests.api.openstack import fakes

from nova.flags import FLAGS

from nova.api.openstack.contrib.networks import NetworkController


class fake_ref(dict):
    def __getattr__(self, item):
        return self[item]


def init_fake_nets():
    return [fake_ref({'bridge': 'br100', 'vpn_public_port': 1000,
                      'dhcp_start': '10.0.0.3', 'bridge_interface': 'eth0',
                      'updated_at': '2011-08-16 09:26:13.048257', 'id': 1,
                      'cidr_v6': None, 'deleted_at': None,
                      'gateway': '10.0.0.1', 'label': 'mynet_0',
                      'project_id': 'admin',
                      'vpn_private_address': '10.0.0.2', 'deleted': False,
                      'vlan': 100, 'broadcast': '10.0.0.7',
                      'netmask': '255.255.255.248', 'injected': False,
                      'cidr': '10.0.0.0/29',
                      'vpn_public_address': '127.0.0.1', 'multi_host': False,
                      'dns1': None, 'host': 'nsokolov-desktop',
                      'gateway_v6': None, 'netmask_v6': None,
                      'created_at': '2011-08-15 06:19:19.387525'}),
            fake_ref({'bridge': 'br101', 'vpn_public_port': 1001,
                      'dhcp_start': '10.0.0.11', 'bridge_interface': 'eth0',
                      'updated_at': None, 'id': 2, 'cidr_v6': None,
                      'deleted_at': None, 'gateway': '10.0.0.9',
                      'label': 'mynet_1', 'project_id': None,
                      'vpn_private_address': '10.0.0.10', 'deleted': False,
                      'vlan': 101, 'broadcast': '10.0.0.15',
                      'netmask': '255.255.255.248', 'injected': False,
                      'cidr': '10.0.0.10/29', 'vpn_public_address': None,
                      'multi_host': False, 'dns1': None, 'host': None,
                      'gateway_v6': None, 'netmask_v6': None,
                      'created_at': '2011-08-15 06:19:19.885495'})]

fake_nets = init_fake_nets()


@require_admin_context
def db_network_disassociate(context, id):
    global fake_nets
    for net in fake_nets:
        if net['id'] == id:
            net['project_id'] = None
            return net
    raise exception.NetworkNotFound()


@require_admin_context
def db_network_get_all(context):
    global fake_nets
    return fake_nets


@require_context
def db_project_get_networks(context, tenant_id, associate=False):
    global fake_nets
    tenant_nets = []
    for net in fake_nets:
        if net['project_id'] == tenant_id:
            tenant_nets.append(net)
    return tenant_nets


@require_context
def db_network_get(context, network_id):
    global fake_nets
    for net in fake_nets:
        if net['id'] == network_id:
            return net
    raise exception.NetworkNotFound()


@require_context
def db_network_get_by_cidr(context, cidr):
    global fake_nets
    for net in fake_nets:
        if net['cidr'] == cidr:
            return net
    raise exception.NetworkNotFound()


@require_admin_context
def db_network_delete(context, network_id):
    global fake_nets
    fake_nets.remove(db.network_get(context, network_id))


class NetworkExtentionTest(test.TestCase):
    def setUp(self):
        super(NetworkExtentionTest, self).setUp()
        FLAGS.allow_admin_api = True
        self.controller = NetworkController()
        fakes.stub_out_networking(self.stubs)
        fakes.stub_out_rate_limiting(self.stubs)
        self.stubs.Set(db, "network_disassociate",
                       db_network_disassociate)
        self.stubs.Set(db, "network_get_all",
                       db_network_get_all)
        self.stubs.Set(db, "project_get_networks",
                       db_project_get_networks)
        self.stubs.Set(db, "network_get",
                       db_network_get)
        self.stubs.Set(db, "network_get_by_cidr",
                       db_network_get_by_cidr)
        self.stubs.Set(db, "network_delete_safe",
                       db_network_delete)
        self.user = 'user'
        self.project = 'project'
        self.user_context = context.RequestContext(self.user, self.project,
                                                   is_admin=False)
        self.admin_context = context.RequestContext(self.user, self.project,
                                                    is_admin=True)
        global fake_nets
        fake_nets = init_fake_nets()

    def test_network_list_all(self):
        req = webob.Request.blank('/v1.1/os-networks')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'

        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 200)
        res_dict = json.loads(res.body)
        self.assertEquals(res_dict, {'networks': fake_nets})

        req = webob.Request.blank('/v1.1/os-networks')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'

        with self.assertRaises(exception.AdminRequired):
            res = req.get_response(fakes.wsgi_app(
                fake_auth_context=self.user_context))
            self.assertEqual(res.status_int, 500)  # admin required
            res_dict = json.loads(res.body)

            right_ans = {'networks': db_network_get_all(self.user_context)}

    def test_network_disassociate(self):
        req = webob.Request.blank('/v1.1/os-networks/1/action')
        req.method = 'POST'
        req.body = json.dumps({'disassociate': None})
        req.headers['Content-Type'] = 'application/json'

        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 200)
        self.assertEqual(json.loads(res.body), {'disassociated': 1})
        self.assertEqual(db.network_get(self.admin_context, 1)['project_id'],
                         None)

        req = webob.Request.blank(
            '/v1.1/os-networks/12345/action')  # not present
        req.method = 'POST'
        req.body = json.dumps({'disassociate': None})
        req.headers['Content-Type'] = 'application/json'

        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 404)

    def test_network_get(self):
        req = webob.Request.blank('/v1.1/os-networks/1')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 200)
        res_dict = json.loads(res.body)
        waited = {'network': db_network_get(self.admin_context, 1)}
        self.assertEquals(res_dict, waited)

        req = webob.Request.blank('/v1.1/os-networks/1')
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.user_context))
        self.assertEqual(res.status_int, 500)

    def test_network_delete(self):
        req = webob.Request.blank('/v1.1/os-networks/1')
        req.method = 'DELETE'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 202)
        # check it was really deleted
        req = webob.Request.blank('/v1.1/os-networks/1')
        req.method = 'GET'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 404)

        req = webob.Request.blank('/v1.1/os-networks/12345')  # not present
        req.method = 'DELETE'
        req.headers['Content-Type'] = 'application/json'
        res = req.get_response(fakes.wsgi_app(
            fake_auth_context=self.admin_context))
        self.assertEqual(res.status_int, 404)
